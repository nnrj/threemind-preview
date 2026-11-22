from __future__ import annotations

import asyncio
import hashlib
import json
import re
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from psycopg import errors
from psycopg.types.json import Jsonb
from pydantic import Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel, state_kernel
from threemind_runtime.codec import ArtifactCodec

from . import auth, permissions
from .config import ROOT, Settings
from .configuration import catalogue, default_spec, require_valid, validate_configuration
from .database import Conflict, Database, Forbidden, NotFound
from .documents import Documents
from .protocols import Intervention, RunSpec, StrictModel
from .record_schema import ExecutionRecordOptions
from .study_tools import require_study, study_catalogue, validate_study
from .worker import birth


class Name(StrictModel):
    name: str = Field(min_length=1, max_length=120)


class CreateRun(Name, ExecutionRecordOptions):
    # Preserve raw types until the shared configuration validator sees them.
    # Parsing RunSpec here first would silently coerce e.g. "false" to False.
    spec: dict = Field(default_factory=dict)
    start_immediately: bool = Field(default=True, strict=True)
    creation_source: dict = Field(default_factory=dict)
    execution: dict = Field(default_factory=dict)


class ConfigurationInput(StrictModel):
    spec: dict
    run_id: UUID | None = None


class EditConfiguration(Name):
    expected_metadata_revision: int | None = Field(default=None, ge=0, strict=True)
    spec: dict
    expected_revision: int = Field(ge=0, strict=True)


class DefaultConfiguration(StrictModel):
    spec: dict
    expected_revision: int = Field(ge=0, strict=True)


class Login(StrictModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
    remember: bool = Field(default=True, strict=True)


class Command(StrictModel):
    kind: str
    payload: dict = Field(default_factory=dict)


class InputSubmission(StrictModel):
    adapter_id: Literal["text-sensor", "anonymous-frames", "stimulus-units"]
    payload: dict
    request_id: UUID
    delay_us: int = Field(default=0, ge=0, le=10**12, strict=True)
    requested_time_us: str | None = None
    source_id: Literal["ui-text", "cli-text"] | None = None


class Export(StrictModel):
    format: str = "tmind"
    checkpoint_id: UUID | None = None


class InputDiagnosis(StrictModel):
    adapter_id: Literal["text-sensor", "anonymous-frames", "stimulus-units"]
    payload: dict
    duration_us: int = Field(default=500000, ge=0, le=1000000, strict=True)


class RandomFixtureRequest(StrictModel):
    config: dict = Field(default_factory=dict)
    count: int = Field(default=20, ge=1, le=1000, strict=True)
    state: dict | None = None


class DataExport(StrictModel):
    table: str = "nodes"
    format: str = "csv"
    checkpoint_id: UUID | None = None
    revision: int | None = None
    minimum: float = Field(default=0, ge=0, le=1)
    source: str | int | None = None


class Fork(Name):
    checkpoint_id: UUID | None = None
    inherit: bool = False
    inheritance_decay_age: Literal["preserve", "reset"] = "preserve"
    spec: RunSpec | None = None
    paused: bool = Field(False, strict=True)
    background: Literal["preserve", "suspend"] = "preserve"


class Analysis(StrictModel):
    study_id: UUID
    control: str
    treatment: str
    seed: int = 71423


class Member(StrictModel):
    username: str
    role: str


class UserCreate(Login):
    admin: bool = False


def serialize(value):
    if isinstance(value, (UUID,)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    from decimal import Decimal

    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


def create_app(settings: Settings | None = None, database: Database | None = None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.db = database or Database(settings.database_url, checkpoint_backend=settings.checkpoint_backend)
        from .execution_limits import initialize

        try:
            app.state.db.require_current_schema()
            initialize(app.state.db, settings)
            from .ai_secrets import SecretBox

            app.state.db.blobs.secret_box = SecretBox(settings.secret_keys)
            from .research_storage import ResearchStorage

            document_storage = ResearchStorage(repository_root=settings.docs_root)

            def document_resource(name):
                try:
                    return document_storage.resolve_legacy(name)
                except ValueError as error:
                    if str(error).startswith("historical location is not registered:"):
                        return None
                    raise

            app.state.documents = Documents(settings.docs_root, resource_resolver=document_resource)
            yield
        finally:
            if database is None:
                app.state.db.close()

    app = FastAPI(
        title="ThreeMind Lab",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.hosts))

    @app.middleware("http")
    async def origin_guard(request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in settings.origins:
            return JSONResponse({"detail": "origin is not allowed"}, status_code=403)
        # Authentication is a host boundary, never an input to Core. Public
        # initialization/login/shared documents retain their explicit routes.
        path = request.url.path
        public_documents = request.method == "GET" and path in (
            "/api/v2/history",
            "/api/v2/documents",
            "/api/v2/documents/content",
            "/api/v2/documents/versions",
            "/api/v2/documents/resource",
        )
        public = (
            public_documents
            or path
            in (
                "/api/v2/health",
                "/api/v2/login",
                "/api/v2/auth/setup",
                "/api/v2/auth/setup/status",
                "/api/v2/auth/token",
                "/api/v2/auth/refresh",
            )
            or path.startswith("/api/v2/shared-documents/")
        )
        context = permissions.actor_context.set(None)
        try:
            if path.startswith("/api/v2/") and not public:
                user = auth.identity(request, mutate=request.method not in ("GET", "HEAD", "OPTIONS"))
                action = permissions.request_action(request)
                if action and (path.startswith(("/api/v2/admin", "/api/v2/system", "/api/v2/services"))):
                    permissions.require(app.state.db, user, action, resources=permissions.request_resources(request))
            response = await call_next(request)
        except HTTPException as exc:
            response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        except Forbidden as exc:
            response = JSONResponse({"detail": str(exc)}, status_code=403)
        finally:
            permissions.actor_context.reset(context)
        response.headers["X-Content-Type-Options"] = "nosniff"
        shared = request.url.path.startswith(("/shared/", "/api/v2/shared-documents/"))
        response.headers["Referrer-Policy"] = "no-referrer" if shared else "same-origin"
        if shared:
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Conflict)
    async def conflict(_, exc):
        return JSONResponse({"detail": str(exc) or "state conflict"}, status_code=409)

    @app.exception_handler(NotFound)
    async def notfound(_, exc):
        return JSONResponse({"detail": str(exc) or "resource not found"}, status_code=404)

    @app.exception_handler(Forbidden)
    async def forbidden(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(ValueError)
    async def invalid(_, exc):
        if isinstance(exc, ValidationError):
            return JSONResponse(
                {"detail": [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]},
                status_code=422,
            )
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_, exc):
        # Validation errors must not echo passwords or provider credentials.
        return JSONResponse(
            {"detail": [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]}, status_code=422
        )

    @app.exception_handler(errors.UniqueViolation)
    async def duplicate(_, exc):
        return JSONResponse({"detail": "resource already exists"}, status_code=409)

    def access(request, project, *, write=False, owner=False, action=None):
        user = auth.identity(request, mutate=request.method not in ("GET", "HEAD", "OPTIONS"))
        if action:
            user["_request_action"] = action
            permissions.actor_context.set(user)
        request.app.state.db.authorize(user, project, write=write, owner=owner)
        return user

    from .operation_catalog import register as register_operation_catalog
    from .operation_receipts import register as register_operation_receipts

    register_operation_catalog(app)
    register_operation_receipts(app, access)

    from .record_api import register_record_routes

    register_record_routes(app, access)

    from .browsing import register as register_browsing

    register_browsing(app)

    from .organ_stream_api import register_organ_stream

    register_organ_stream(app, access)
    from .adapter_api import register_adapter_routes
    from .ai_api import register_ai_routes
    from .body_api import register_body_routes
    from .device_api import register_device_routes
    from .energy_api import register_energy_routes
    from .input_selection_api import register_input_selection_routes
    from .notebook_api import register_notebook_routes
    from .notification_api import register_notification_routes
    from .research_api import register_research_routes
    from .research_plan_api import register_plan_routes
    from .resource_api import register_resource_routes
    from .spatial_api import register_spatial_routes

    register_resource_routes(app, access)
    from .execution_api import register_execution_routes

    register_execution_routes(app, access)
    register_research_routes(app, access)
    register_plan_routes(app, access)
    register_energy_routes(app, access)
    register_input_selection_routes(app, access)
    register_spatial_routes(app, access)
    register_body_routes(app, access)
    register_device_routes(app, access)
    register_adapter_routes(app, access)
    register_ai_routes(app, access)
    register_notification_routes(app, access)

    from .report_share_api import register_share_routes

    register_share_routes(app, access)
    from .development_api import register_development_routes

    register_development_routes(app, access)
    from .evolution_api import register_evolution_routes

    register_evolution_routes(app, access)
    from .ecology_api import register_ecology_routes

    register_ecology_routes(app, access)
    from .ecology_observer_api import register_observer_routes

    register_observer_routes(app, access)
    from .ecology_ai_api import register_ecology_ai_routes

    register_ecology_ai_routes(app, access)
    from .assessment_api import register_assessment_routes

    register_assessment_routes(app, access)
    from .world_api import register_world_routes

    register_world_routes(app, access)
    from .robot_api import register as register_robot_routes

    register_robot_routes(app, access)

    from .data_api import register as register_data_routes

    register_data_routes(app, access)

    from .permission_api import register_permission_routes as register_permissions
    from .platform_configuration import register as register_platform_configuration
    from .platform_notifications import register as register_platform_notifications

    register_platform_configuration(app)
    register_platform_notifications(app)
    register_permissions(app)

    @app.get("/api/v2/health")
    def health():
        return {"status": "ok", "version": "2.1.0", "mode": settings.mode, "backend": settings.backend}

    @app.get("/api/v2/session")
    def session(request: Request):
        return {
            "user": {k: v for k, v in auth.identity(request).items() if not k.startswith("_")},
            "mode": settings.mode,
            "backend": settings.backend,
        }

    @app.get("/api/v2/session/running-instances")
    def running_instances(request: Request, limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
        user = auth.identity(request)
        if user.get("delegation_id") or not permissions.has_action(user, "runs.read"):
            raise Forbidden("interactive running-instance selection requires instance-read permission")
        all_runs = user["superadmin"] or any(
            g["action"] == "runs.read" and g["scope"] == "all_projects" for g in user["permissions"]
        )
        from .browsing import read_scope

        with read_scope(app.state.db, user) as db:
            rows = db.execute(
                "SELECT r.id,r.name,r.project_id,r.status,r.revision,r.metadata_revision,m.role, "
                "EXISTS(SELECT 1 FROM ecology_members e WHERE e.run_id=r.id) OR EXISTS(SELECT 1 FROM assessment_members a WHERE a.run_id=r.id) OR EXISTS(SELECT 1 FROM evolution_members e WHERE e.run_id=r.id) OR EXISTS(SELECT 1 FROM language_sessions l WHERE l.run_id=r.id) OR EXISTS(SELECT 1 FROM research_plans p WHERE p.run_id=r.id AND p.status IN ('queued','running')) OR r.spec ? 'study_id' AND r.spec->>'study_id' IS NOT NULL AS managed "
                "FROM runs r LEFT JOIN members m ON m.project_id=r.project_id AND m.user_id=%s "
                "WHERE r.status IN ('queued','running') AND (%s OR m.user_id IS NOT NULL) ORDER BY r.created_at,r.id LIMIT %s OFFSET %s",
                (user["id"], all_runs, limit + 1, offset),
            ).fetchall()
        for row in rows:
            can = permissions._scope_allowed(
                user,
                "runs.pause",
                project=row["project_id"],
                member=row["role"] is not None,
                resources=[{"kind": "run", "id": str(row["id"])}, {"kind": "project", "id": str(row["project_id"])}],
            )
            broad_pause = user["superadmin"] or any(
                g["action"] == "runs.pause" and g["scope"] == "all_projects" for g in user["permissions"]
            )
            row["can_pause"] = can and (broad_pause or row["role"] in ("owner", "researcher")) and not row["managed"]
            row["reason"] = (
                "managed-by-experiment" if row["managed"] else None if row["can_pause"] else "no-pause-permission"
            )
            row["pause_payload"] = {"kind": "pause", "payload": {}}
        return {"items": rows[:limit], "next": offset + limit if len(rows) > limit else None}

    @app.post("/api/v2/login")
    def login(body: Login, request: Request, response: Response):
        token, csrf, user = auth.login(app.state.db, body.username, body.password, remember=body.remember)
        response.set_cookie(
            "tm_session",
            token,
            httponly=True,
            secure=settings.secure_cookie,
            samesite="strict",
            max_age=2592000 if body.remember else 43200,
        )
        return {"user": {k: v for k, v in user.items() if not k.startswith("_")}, "csrf": csrf}

    @app.post("/api/v2/logout")
    def logout(request: Request, response: Response):
        auth.logout(request)
        response.delete_cookie("tm_session")
        return {"ok": True}

    @app.get("/api/v2/projects")
    def projects(request: Request):
        return app.state.db.projects(auth.identity(request))

    @app.post("/api/v2/projects", status_code=201)
    def create_project(body: Name, request: Request):
        user = permissions.require(app.state.db, auth.identity(request, mutate=True), "projects.create")
        return app.state.db.create_project(user, body.name)

    @app.get("/api/v2/projects/{project}")
    def project_descriptor(project: UUID, request: Request):
        user = access(request, project)
        grant = permissions.project_access(app.state.db, user, project)
        with app.state.db.tx(project) as db:
            row = db.execute("SELECT * FROM projects WHERE id=%s", (project,)).fetchone()
        return row | {"role": grant.get("role", "viewer")}

    @app.put("/api/v2/projects/{project}")
    def rename_project(project: UUID, body: Name, request: Request):
        actor = access(request, project, write=True, owner=True)
        with app.state.db.tx(project) as db:
            row = db.execute("UPDATE projects SET name=%s WHERE id=%s RETURNING *", (body.name, project)).fetchone()
            if row is None:
                raise NotFound()
            db.execute(
                "INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'project.rename',%s,%s)",
                (actor["id"], str(project), Jsonb({"name": body.name})),
            )
        return row

    @app.get("/api/v2/projects/{project}/runs")
    def runs(
        project: UUID,
        request: Request,
        study_id: UUID | None = None,
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        include_archived: bool = False,
        summary: bool = False,
    ):
        access(request, project)
        return app.state.db.list_runs(
            project, study_id=study_id, limit=limit, offset=offset, include_archived=include_archived, summary=summary
        )

    @app.post("/api/v2/projects/{project}/runs", status_code=201)
    def create_run(project: UUID, body: CreateRun, request: Request):
        actor = access(request, project, write=True)
        spec = require_valid(validate_configuration(body.spec, maximum_duration=settings.max_run_seconds))
        from .execution import select_execution
        from .native_records import register_execution

        execution = select_execution(spec["kernel_id"], body.execution, default=settings.backend)

        with app.state.db.tx(project) as db:
            row = app.state.db.create_run(project, body.name, spec, transaction=db, execution=execution)
            from .platform_configuration import creation_source

            source = creation_source(db, project, body.creation_source, database=app.state.db,
                                     actual_kernel=spec["kernel_id"])
            row = db.execute(
                "UPDATE runs SET creation_source=%s,status=%s WHERE id=%s RETURNING *",
                (Jsonb(source), "queued" if body.start_immediately else "paused", row["id"]),
            ).fetchone()
            register_execution(
                app.state.db,
                db,
                project,
                actor,
                "run",
                row["id"],
                body.name,
                spec,
                executor=body.record_executor,
                classification=body.record_classification,
            )
            if body.start_immediately:
                app.state.db.enqueue(project, "run", run_id=row["id"], transaction=db)
        return row

    @app.get("/api/v2/projects/{project}/runs/{run_id}")
    def run(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        return app.state.db.get_run(project, run_id)

    @app.get("/api/v2/configuration")
    def configuration_catalogue(request: Request, kernel_id: str | None = None):
        auth.identity(request)
        return {**catalogue(kernel_id=kernel_id), "max_run_seconds": settings.max_run_seconds,
                "host_execution": {"default_backend": settings.backend}}

    @app.post("/api/v2/projects/{project}/configuration/validate")
    def check_configuration(project: UUID, body: ConfigurationInput, request: Request):
        access(request, project)
        current, elapsed = None, 0
        if body.run_id:
            row = app.state.db.get_run(project, body.run_id)
            current = row["spec"]
            if row["revision"]:
                with app.state.db.tx(project) as db:
                    cp = db.execute(
                        "SELECT context FROM checkpoints WHERE run_id=%s AND revision=%s",
                        (body.run_id, row["revision"]),
                    ).fetchone()
                elapsed = int(row["time_us"]) - int(cp["context"].get("start_us", row["time_us"]))
        result = validate_configuration(
            body.spec, current=current, elapsed_us=elapsed, maximum_duration=settings.max_run_seconds
        )
        if body.run_id and result["valid"]:
            from .inputs import pending_budget

            with app.state.db.tx(project) as db:
                pending = pending_budget(db, body.run_id)
            for count, field in (("frames", "max_pending_frames"), ("channels", "max_pending_channels")):
                if int(pending[count]) > result["spec"]["input_bus"][field]:
                    result["errors"].append(
                        {"path": f"input_bus.{field}", "message": "新预算小于已接收载体的待递送量。"}
                    )
            result["valid"] = not result["errors"]
        return result

    @app.get("/api/v2/projects/{project}/configuration/defaults")
    def get_defaults(project: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = db.execute("SELECT * FROM project_run_defaults WHERE project_id=%s", (project,)).fetchone()
        return row or {"spec": default_spec(), "revision": 0, "updated_at": None}

    @app.put("/api/v2/projects/{project}/configuration/defaults")
    def set_defaults(project: UUID, body: DefaultConfiguration, request: Request):
        user = access(request, project, write=True)
        spec = require_valid(validate_configuration(body.spec, maximum_duration=settings.max_run_seconds))
        with app.state.db.tx(project) as db:
            # Project lock also serializes the first insert (no settings row yet).
            db.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project,))
            row = db.execute("SELECT revision FROM project_run_defaults WHERE project_id=%s", (project,)).fetchone()
            if (row["revision"] if row else 0) != body.expected_revision:
                raise Conflict("项目默认配置已更新，请重新载入后编辑。")
            return db.execute(
                "INSERT INTO project_run_defaults(project_id,spec,updated_by) VALUES(%s,%s,%s) ON CONFLICT(project_id) DO UPDATE SET spec=EXCLUDED.spec,updated_by=EXCLUDED.updated_by,revision=project_run_defaults.revision+1,updated_at=now() RETURNING *",
                (project, Jsonb(spec), user["id"]),
            ).fetchone()

    @app.put("/api/v2/projects/{project}/runs/{run_id}/configuration")
    def edit_configuration(project: UUID, run_id: UUID, body: EditConfiguration, request: Request):
        from threemind_runtime import create_engine

        user = access(request, project, write=True)
        row = app.state.db.get_run(project, run_id)
        if row["revision"] != body.expected_revision:
            raise Conflict("运行数据版本已更新，请重新载入后编辑。")
        if row["status"] not in ("paused", "blocked"):
            raise Conflict("请先暂停运行；已结束的运行请从检查点分叉。")
        if row["revision"] == 0:
            # A prepared individual has metadata only. Editing must not instantiate
            # its Core, peripherals, random state, or a fabricated checkpoint.
            spec = require_valid(
                validate_configuration(body.spec, current=row["spec"], maximum_duration=settings.max_run_seconds)
            )
            with app.state.db.tx(project) as db:
                locked = db.execute("SELECT * FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
                expected = (
                    body.expected_metadata_revision
                    if body.expected_metadata_revision is not None
                    else row["metadata_revision"]
                )
                if locked["revision"] != 0 or locked["metadata_revision"] != expected or locked["status"] != "paused":
                    raise Conflict("prepared individual changed; reload before editing")
                if db.execute(
                    "SELECT 1 FROM jobs WHERE run_id=%s AND status IN ('pending','leased')", (run_id,)
                ).fetchone():
                    raise Conflict("prepared individual is starting")
                result = db.execute(
                    "UPDATE runs SET name=%s,spec=%s,metadata_revision=metadata_revision+1,updated_at=now() WHERE id=%s RETURNING *",
                    (body.name, Jsonb(spec), run_id),
                ).fetchone()
                db.execute(
                    "INSERT INTO audit(user_id,action,resource,details) VALUES(%s,'run.prepared.configuration',%s,%s)",
                    (
                        user["id"],
                        str(run_id),
                        Jsonb({"before": row["spec"], "after": spec, "metadata_revision": result["metadata_revision"]}),
                    ),
                )
                return result
        cp, image = app.state.db.load_checkpoint(project, run_id)
        if cp["revision"] != body.expected_revision:
            raise Conflict("检查点已更新，请重新载入后编辑。")
        context = dict(cp["context"])
        start = int(context.get("start_us", row["time_us"]))
        spec = require_valid(
            validate_configuration(
                body.spec,
                current=row["spec"],
                elapsed_us=int(row["time_us"]) - start,
                maximum_duration=settings.max_run_seconds,
            )
        )
        from .execution import run_backend

        engine = create_engine(state=image, backend=run_backend(row, default=settings.backend))
        engine.reconfigure(resolve_kernel(spec["kernel_id"]).configuration(spec["config"]))
        if spec["environment"] != row["spec"].get("environment", "mujoco"):
            context.update(environment=None, next_input_us=str(engine.time_us))
        if spec["sample_us"] != row["spec"].get("sample_us", 100000):
            context["next_observation_us"] = str(engine.time_us)
        deadline = RunSpec(**spec).deadline_us(start)
        context.update(end_us=str(deadline) if deadline is not None else None, protocol=spec)
        from .readouts import reconfigure as reconfigure_readouts

        context["readouts"], readout_events = reconfigure_readouts(
            context.get("readouts"), RunSpec(**spec), run_id, engine.time_us
        )
        updated_image = engine.capture_state()
        change = {
            "expected_metadata_revision": body.expected_metadata_revision
            if body.expected_metadata_revision is not None
            else row["metadata_revision"],
            "before": row["spec"],
            "after": spec,
            "name": body.name,
            "user_id": str(user["id"]),
            "applied_at_us": str(engine.time_us),
            "previous_state_hash": image.digest,
            "previous_dynamics": image.to_dict()["dynamics"],
            "dynamics": updated_image.to_dict()["dynamics"],
        }
        app.state.db.save_checkpoint(
            project,
            run_id,
            updated_image,
            context=context,
            expected_revision=body.expected_revision,
            status=row["status"],
            configuration_change=change,
            observations=[engine.metrics()],
            events=[
                {
                    "key": f"configuration:{body.expected_revision + 1}",
                    "kind": "configuration_changed",
                    "time_us": str(engine.time_us),
                    "payload": change,
                },
                *readout_events,
            ],
        )
        return app.state.db.get_run(project, run_id)

    from .organ_controls import register_organ_controls

    register_organ_controls(app, access, edit_configuration)

    @app.post("/api/v2/projects/{project}/runs/{run_id}/commands")
    def command(project: UUID, run_id: UUID, body: Command, request: Request):
        user = auth.identity(request, mutate=True)
        action = permissions.command_action(body.kind)
        user["_request_action"] = action
        permissions.project_access(app.state.db, user, project, write=True, action=action)
        permissions.actor_context.set(user)
        run = app.state.db.get_run(project, run_id)
        if run["spec"].get("study_id") and body.kind in ("stimulus", "intervention", "close_inputs", "robot_control"):
            raise Conflict("配对实验的刺激和干预已冻结；请创建新实验或分叉为独立运行后修改。")
        if body.kind not in (
            "pause",
            "cancel",
            "close_inputs",
            "checkpoint",
            "stimulus",
            "intervention",
            "resume",
            "readout_observe",
            "robot_control",
        ):
            raise ValueError("unsupported command")
        if body.kind == "resume":
            return app.state.db.command(project, run_id, "resume", {})
        if body.kind == "stimulus":
            Stimulus.from_dict({"time_us": "0", **body.payload})
            from .inputs import submit

            return submit(
                app.state.db,
                project,
                run_id,
                user,
                adapter_id="anonymous-frames",
                payload={"frames": [{**body.payload, "time_us": "0"}]},
                request_id=uuid4(),
                requested_time_us=body.payload.get("time_us"),
            )
        elif body.kind == "intervention":
            body.payload = Intervention.model_validate_json(json.dumps(body.payload), strict=True).model_dump()
        elif body.kind == "robot_control":
            from threemind_runtime.robot_protocol import RobotIntervention

            if run["spec"].get("environment") != "robot":
                raise ValueError("意识未接入机器人任务。")
            value = RobotIntervention.model_validate_json(json.dumps(body.payload), strict=True)
            task = run["spec"]["robot_protocol"]
            if value.action in ("force", "actuators") and value.duration_us % task["world"]["physics"]["sample_us"]:
                raise ValueError("干预时长需要是机器人感官／动作周期的整数倍。")
            if value.action == "force" and value.body_id not in {b["id"] for b in task["world"]["bodies"]}:
                raise ValueError("不存在该物理躯体部件。")
            if value.action == "actuators" and len(value.commands) != len(task["world"]["motors"]):
                raise ValueError("请按执行器 ID 排序，为每个执行器提供一个指令。")
            body.payload = value.model_dump(mode="json")
        elif body.kind == "readout_observe":
            cfg = run["spec"].get("activity_readout", {})
            if not cfg.get("enabled") or cfg.get("analysis_version", 1) != 2:
                raise ValueError("无刺激观察需要启用活动过程分析 V2；历史配置不会自动升级。")
            if body.payload:
                raise ValueError("this command has no parameters")
        elif body.payload:
            raise ValueError("this command has no parameters")
        return app.state.db.command(project, run_id, body.kind, body.payload)

    @app.post("/api/v2/projects/{project}/runs/{run_id}/inputs", status_code=202)
    def submit_carrier(project: UUID, run_id: UUID, body: InputSubmission, request: Request):
        from .inputs import submit

        user = access(request, project, write=True)
        return submit(app.state.db, project, run_id, user, **body.model_dump())

    @app.get("/api/v2/projects/{project}/runs/{run_id}/inputs")
    def input_history(
        project: UUID,
        run_id: UUID,
        request: Request,
        after: int = Query(0, ge=0),
        limit: int = Query(30, ge=1, le=200),
        source: str | None = None,
        status: str | None = None,
    ):
        from .inputs import list_envelopes

        access(request, project)
        return list_envelopes(app.state.db, project, run_id, after=after, limit=limit, source=source, status=status)

    @app.post("/api/v2/projects/{project}/runs/{run_id}/input-diagnostics")
    def input_diagnostics(project: UUID, run_id: UUID, request: Request, body: InputDiagnosis):
        from dataclasses import asdict, replace

        from threemind_runtime.sensory import carrier_frames

        from .stimulus_diagnostics import diagnose

        access(request, project, write=True)
        run = app.state.db.get_run(project, run_id)
        _, state = app.state.db.load_checkpoint(project, run_id)
        if state is None:
            raise Conflict("尚无已提交检查点，不能诊断。")
        value = state.to_dict()
        if len(value["nodes"]) > 300 or len(value["edges"]) > 5000:
            raise ValueError("交互诊断预算为 300 节点、5000 连接；较大模型请导出后使用诊断命令。")
        spec = RunSpec.model_validate(run["spec"])
        frames = list(
            carrier_frames(
                body.adapter_id,
                body.payload,
                spec.seed,
                asdict(spec.text_sensor) if body.adapter_id == "text-sensor" else {},
            )
        )
        if len(frames) > 128 or sum(len(f["stimulus"].channels) for f in frames) > 2048:
            raise ValueError("交互诊断载体超过 128 帧或 2048 通道预算。")
        now = int(value["time_us"])
        stimuli = [replace(f["stimulus"], time_us=now + f["stimulus"].time_us) for f in frames]
        if stimuli and max(s.time_us for s in stimuli) > now + body.duration_us:
            raise ValueError("诊断观察窗口不能早于最后递送时间。")
        return diagnose(state, stimuli, now + body.duration_us, max_records=10000)

    @app.post("/api/v2/projects/{project}/input-fixtures/random")
    def random_fixture(project: UUID, request: Request, body: RandomFixtureRequest):
        from threemind_runtime.random_stimuli import RandomStimuli, RandomStimulusConfig

        access(request, project, write=True)
        try:
            fixture = RandomStimuli(RandomStimulusConfig(**body.config), body.state)
        except (TypeError, KeyError) as exc:
            raise ValueError("invalid random fixture configuration or recovery state") from exc
        if body.count * (1 if fixture.config.mode == "fresh-single" else fixture.config.channels) > 16384:
            raise ValueError("random fixture budget exceeded: at most 16384 channel values per request")
        return {"units": [fixture.sample() for _ in range(body.count)], "state": fixture.capture(), "submitted": False}

    @app.get("/api/v2/projects/{project}/runs/{run_id}/inputs/export")
    def input_export(
        project: UUID,
        run_id: UUID,
        request: Request,
        records: Literal["envelopes", "frames"] = "frames",
        format: Literal["jsonl", "csv"] = "jsonl",
        source: str | None = None,
    ):
        from .inputs import export_stream

        access(request, project)
        app.state.db.get_run(project, run_id)
        return StreamingResponse(
            export_stream(app.state.db, project, run_id, records=records, format=format, source=source),
            media_type="application/x-ndjson" if format == "jsonl" else "text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="inputs-{records}.{format}"'},
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/inputs/{envelope_id}")
    def input_detail(
        project: UUID,
        run_id: UUID,
        envelope_id: UUID,
        request: Request,
        after: int = Query(-1, ge=-1),
        limit: int = Query(100, ge=1, le=1000),
    ):
        from .inputs import detail

        access(request, project)
        return detail(app.state.db, project, run_id, envelope_id, after=after, limit=limit)

    @app.get("/api/v2/projects/{project}/runs/{run_id}/sensory")
    def sensory_configuration(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        row = app.state.db.get_run(project, run_id)
        from dataclasses import asdict

        from threemind_runtime.media import MEDIA_CONFIGS

        from .adapter_api import describe, network_bindings
        from .media_codec import capabilities

        spec = RunSpec(**row["spec"])
        with app.state.db.tx(project) as db:
            devices = network_bindings(db, run_id)
        return {
            "seed": spec.seed,
            "network_devices": devices,
            "text_sensor": asdict(spec.text_sensor),
            "input_bus": asdict(spec.input_bus),
            "media_capabilities": capabilities(),
            **{root: asdict(getattr(spec, root)) for root in MEDIA_CONFIGS},
            "adapters": describe(spec.model_dump(), network_count=sum(d["enabled"] for d in devices)),
        }

    media_slots = asyncio.Semaphore(settings.max_media_decoders)
    register_notebook_routes(app, access, media_slots)
    from .report_api import register_report_routes

    register_report_routes(app, access)
    from .media_upload_api import register_media_upload_routes

    register_media_upload_routes(app, access, media_slots)

    @app.post("/api/v2/projects/{project}/runs/{run_id}/media", status_code=202)
    async def media_upload(
        project: UUID,
        run_id: UUID,
        request: Request,
        kind: Literal["audio", "image", "video"],
        request_id: UUID,
        filename: str = Query("carrier.bin", min_length=1, max_length=255),
        intensity: float = Query(1, ge=0, le=100),
        delay_us: int = Query(0, ge=0, le=10**12),
    ):
        from .media_store import accept

        actor = access(request, project, write=True)
        spec = RunSpec(**app.state.db.get_run(project, run_id)["spec"])
        cfg = spec.auditory_sensor if kind == "audio" else spec.visual_sensor
        if not spec.source_policies.resolve(f"upload-{kind}")["enabled"]:
            raise Conflict("该媒体来源已关闭，请暂停后在来源策略中开启。")
        limit = min(cfg.upload_limit_mb, 256) * 1024**2
        declared = request.headers.get("content-length")
        if declared is not None and int(declared) > limit:
            raise HTTPException(413, "超过感官或整文件接收上限；大文件请使用分块上传。")
        if media_slots.locked():
            raise HTTPException(429, "媒体接收与解码槽位已满，请稍后重试。")
        await media_slots.acquire()
        job = None
        try:
            raw = bytearray()
            async for part in request.stream():
                if len(raw) + len(part) > limit:
                    raise HTTPException(413, "媒体原件超出当前感官接收上限，整条未接收。")
                raw.extend(part)
            job = asyncio.create_task(
                asyncio.to_thread(
                    accept,
                    app.state.db,
                    project,
                    run_id,
                    actor,
                    bytes(raw),
                    kind=kind,
                    filename=filename,
                    request_id=request_id,
                    intensity=intensity,
                    delay_us=delay_us,
                )
            )
            del raw
            # A disconnected client cannot release a slot while its decode is still running.
            job.add_done_callback(lambda done: media_slots.release())
            return await asyncio.shield(job)
        finally:
            if job is None:
                media_slots.release()

    @app.get("/api/v2/projects/{project}/runs/{run_id}/media/export")
    def media_export(project: UUID, run_id: UUID, request: Request):
        from .media_store import export_originals

        access(request, project)
        app.state.db.get_run(project, run_id)
        return StreamingResponse(
            export_originals(app.state.db, project, run_id),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="media-originals.zip"'},
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/media/{envelope_id}/original")
    def media_original(project: UUID, run_id: UUID, envelope_id: UUID, request: Request):
        from urllib.parse import quote

        from .media_store import asset_for, chunks

        access(request, project)
        payload = asset_for(app.state.db, project, run_id, envelope_id)
        filename = payload["filename"].replace("\\", "/").rsplit("/", 1)[-1]
        return StreamingResponse(
            chunks(app.state.db, project, payload),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
                "Content-Length": str(payload["byte_length"]),
                "X-Content-SHA256": payload["asset_sha256"],
            },
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/organs")
    def organ_history(
        project: UUID,
        run_id: UUID,
        request: Request,
        before_id: int | None = Query(None, ge=1),
        limit: int = Query(10, ge=1, le=100),
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT id AS sample_id,event_key,time_us,payload,commit_revision FROM events WHERE run_id=%s AND kind='organ_output' AND (%s::bigint IS NULL OR id<%s) ORDER BY id DESC LIMIT %s",
                (run_id, before_id, before_id, limit + 1),
            ).fetchall()
        return {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next": rows[limit - 1]["sample_id"] if len(rows) >= limit else None,
            "scope": "committed-observation-samples",
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/organs/{sample_id}/audio.wav")
    def organ_audio(project: UUID, run_id: UUID, sample_id: int, request: Request):
        from threemind_runtime.media import render_wav

        access(request, project)
        with app.state.db.tx(project) as db:
            row = db.execute(
                "SELECT payload FROM events WHERE run_id=%s AND id=%s AND kind='organ_output'", (run_id, sample_id)
            ).fetchone()
        if row is None:
            raise NotFound()
        return Response(
            render_wav(row["payload"]),
            media_type="audio/wav",
            headers={"Content-Disposition": f'attachment; filename="activity-sample-{sample_id}.wav"'},
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/organs/export")
    def organ_export(project: UUID, run_id: UUID, request: Request):
        from .organs import export_stream

        access(request, project)
        app.state.db.get_run(project, run_id)
        return StreamingResponse(
            export_stream(app.state.db, project, run_id),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": 'attachment; filename="organ-outputs.jsonl"'},
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/input-queue")
    def input_queue(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        row = app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            cp = db.execute(
                "SELECT context FROM checkpoints WHERE run_id=%s AND revision=%s", (run_id, row["revision"])
            ).fetchone()
            pending = list((cp["context"].get("input_bus", {}).get("pending", {}) if cp else {}).values())
            counts = db.execute(
                "SELECT status,count(*) AS count FROM input_envelopes WHERE run_id=%s GROUP BY status", (run_id,)
            ).fetchall()
        return {
            "revision": row["revision"],
            "time_us": row["time_us"],
            "pending_frames": len(pending),
            "pending_channels": sum(item["channel_count"] for item in pending),
            "next": min(pending, key=lambda p: (int(p["scheduled_time_us"]), p["core_event_id"])) if pending else None,
            "envelopes": counts,
            "scope": "committed checkpoint; newly accepted carriers may not be scheduled yet",
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/telemetry")
    def telemetry_samples(
        project: UUID,
        run_id: UUID,
        request: Request,
        scope: str | None = None,
        before_id: int | None = Query(None, ge=1),
        limit: int = Query(1, ge=1, le=100),
    ):
        from dataclasses import asdict

        from threemind_runtime.telemetry import METRICS, SCOPE_LABELS, TELEMETRY_CONFIGS, TELEMETRY_VERSION

        access(request, project)
        run = app.state.db.get_run(project, run_id)
        if scope is not None and scope not in METRICS:
            raise ValueError("unknown telemetry scope")
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT id,time_us,payload,commit_revision FROM events WHERE run_id=%s AND kind='telemetry_sample' "
                "AND (%s::bigint IS NULL OR id<%s) AND (%s::text IS NULL OR payload->'scopes' ? %s) "
                "ORDER BY id DESC LIMIT %s",
                (run_id, before_id, before_id, scope, scope, limit + 1),
            ).fetchall()
        spec = RunSpec(**run["spec"])
        return {
            "schema": TELEMETRY_VERSION,
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next": rows[min(limit, len(rows)) - 1]["id"] if rows else None,
            "metrics": {s: {name: info[0] for name, info in entries.items()} for s, entries in METRICS.items()},
            "scopes": SCOPE_LABELS,
            "configuration": {root: asdict(getattr(spec, root)) for root in TELEMETRY_CONFIGS},
            "source_policies": {
                root: spec.source_policies.resolve(f"{cls.scope}-telemetry") for root, cls in TELEMETRY_CONFIGS.items()
            },
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/telemetry/export")
    def telemetry_export(
        project: UUID, run_id: UUID, request: Request, scope: str | None = None, format: str = "jsonl"
    ):
        from threemind_runtime.telemetry import METRICS

        from .telemetry import export_stream

        access(request, project)
        app.state.db.get_run(project, run_id)
        if format not in ("jsonl", "csv") or scope is not None and scope not in METRICS:
            raise ValueError("unknown telemetry export selection")
        return StreamingResponse(
            export_stream(app.state.db, project, run_id, scope=scope, format=format),
            media_type="text/csv" if format == "csv" else "application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="telemetry.{format}"'},
        )

    from .readouts_api import register_readout_routes

    register_readout_routes(app, access)
    from .conversation_api import register_conversation_routes

    register_conversation_routes(app, access)
    from .source_policy_api import register_source_policy_routes

    register_source_policy_routes(app, access)
    from .live_capture_api import register_capture_routes

    register_capture_routes(app, access, media_slots)
    from .model_library_api import register_library_routes

    register_library_routes(app, access)
    from .species_api import register as register_species

    register_species(app, access)
    from .calibration_api import register_calibration_routes

    register_calibration_routes(app, access)
    from .transformer_tools import register as register_transformer_tools

    register_transformer_tools(app, access)
    from .language_tools import register as register_language_tools

    register_language_tools(app, access)

    from .bundle_api import register as register_bundle_routes

    register_bundle_routes(app, access)

    @app.get("/api/v2/projects/{project}/runs/{run_id}/physical-state")
    def physical_state(
        project: UUID,
        run_id: UUID,
        request: Request,
        checkpoint_id: UUID | None = None,
        after_id: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=5000),
    ):
        access(request, project)
        cp, image = app.state.db.load_checkpoint(project, run_id, checkpoint_id)
        state = image.to_dict()
        membranes = state.get("membranes", [])
        rows = [n for n in membranes if n["id"] > after_id][:limit]
        return {
            "kernel_id": state["dynamics"],
            "supported": state["dynamics"] == "threemind.lif/1",
            "checkpoint_id": str(cp["id"]),
            "revision": cp["revision"],
            "state_hash": image.digest,
            "time_us": state["time_us"],
            "state_time_us": state.get("state_time_us", state["time_us"]),
            "units": {"voltage_mv": "mV", "current_na": "nA", "adaptation_na": "nA", "spikes": "count"},
            "nodes": rows,
            "total_nodes": len(membranes),
            "next_after_id": rows[-1]["id"] if rows and any(n["id"] > rows[-1]["id"] for n in membranes) else None,
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/spikes")
    def spike_events(
        project: UUID,
        run_id: UUID,
        request: Request,
        before_id: int | None = Query(None, ge=1),
        limit: int = Query(100, ge=1, le=500),
    ):
        access(request, project)
        run = app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT id,time_us::text,payload FROM events WHERE run_id=%s AND kind='spikes' "
                "AND (%s::bigint IS NULL OR id<%s) ORDER BY id DESC LIMIT %s",
                (run_id, before_id, before_id, limit + 1),
            ).fetchall()
        return {
            "items": rows[:limit],
            "next_before_id": rows[limit - 1]["id"] if len(rows) > limit else None,
            "recording_enabled": run["spec"].get("record_spikes", True),
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/graph")
    def graph(
        project: UUID,
        run_id: UUID,
        request: Request,
        limit: int = Query(10000, ge=1, le=100000),
        edge_limit: int = Query(1000000, ge=0, le=1000000),
        label_limit: int = Query(0, ge=0, le=500),
        since: int = -1,
        checkpoint_id: UUID | None = None,
    ):
        access(request, project)
        if checkpoint_id is not None:
            if since >= 0:
                identity = app.state.db.checkpoint_identity(project, run_id, checkpoint_id)
                if identity["revision"] == since:
                    return Response(status_code=304)
            cp, image = app.state.db.load_checkpoint(project, run_id, checkpoint_id)
            if cp["revision"] == since:
                return Response(status_code=304)
            state = image.to_dict()
            nodes = state["nodes"][:limit]
            ids = {node["id"] for node in nodes}
            from itertools import islice

            from .graph_annotations import annotations

            edges = list(
                islice((edge for edge in state["edges"] if edge["source"] in ids and edge["target"] in ids), edge_limit)
            )
            legacy_projection = {}
            if state["dynamics"] == "unified-associative":
                from .legacy_graph import PROJECTION, edge_view, state_nodes

                nodes = state_nodes(state, nodes)
                edges = [edge_view(edge) for edge in edges]
                legacy_projection = {"projection": PROJECTION}
            labels = {}
            if label_limit and state["dynamics"] != "unified-associative":
                with app.state.db.tx(project, repeatable=True) as db:
                    labels = annotations(db, run_id, cp["revision"], cp["time_us"], nodes, label_limit)
            return {
                "revision": cp["revision"],
                "time_us": str(cp["time_us"]),
                "sequence": cp["sequence"],
                "checkpoint_id": str(cp["id"]),
                "state_hash": cp["state_hash"],
                "kernel_id": state["dynamics"],
                "observation_quantity": "normalized-depolarization"
                if state["dynamics"] == "threemind.lif/1"
                else "activation",
                "nodes": nodes,
                "edges": edges,
                "total_nodes": len(state["nodes"]),
                "total_edges": len(state["edges"]),
                "complete": len(nodes) == len(state["nodes"]) and len(edges) == len(state["edges"]),
                **labels,
                **legacy_projection,
            }
        with app.state.db.tx(project, repeatable=True) as db:
            run = db.execute("SELECT revision,time_us,sequence,metrics,spec->>'kernel_id' AS kernel_id FROM runs WHERE id=%s", (run_id,)).fetchone()
            if run is None:
                raise NotFound()
            if run["revision"] == since:
                return Response(status_code=304)
            legacy = run["kernel_id"] == "unified-associative"
            legacy_projection = {}
            if legacy:
                from .legacy_graph import PROJECTION
                from .legacy_graph import graph as legacy_graph

                nodes, edges = legacy_graph(db, run_id, limit, edge_limit)
                legacy_projection = {"projection": PROJECTION}
            else:
                nodes, edges = [], []
            nodes = nodes if legacy else db.execute(
                "SELECT id,channel,activation,inhibition,stability,direct,associative,touches FROM nodes WHERE run_id=%s ORDER BY id LIMIT %s",
                (run_id, limit),
            ).fetchall()
            ids = [n["id"] for n in nodes]
            edges = edges if legacy else (
                db.execute(
                    "SELECT source,target,weight,stability FROM edges WHERE run_id=%s AND source=ANY(%s) AND target=ANY(%s) ORDER BY source,target LIMIT %s",
                    (run_id, ids, ids, edge_limit),
                ).fetchall()
                if ids and edge_limit
                else []
            )
            total_nodes = run["metrics"].get("nodes", 0)
            total_edges = run["metrics"].get("edges", 0)
            labels = {}
            if label_limit and not legacy:
                from .graph_annotations import annotations

                labels = annotations(db, run_id, run["revision"], run["time_us"], nodes, label_limit)
        return {
            **run,
            "time_us": str(run["time_us"]),
            "nodes": nodes,
            "edges": edges,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "complete": len(nodes) == total_nodes and len(edges) == total_edges,
            **labels,
            **legacy_projection,
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/data/{table}")
    def graph_query(
        project: UUID,
        run_id: UUID,
        table: str,
        request: Request,
        after: int | None = Query(None, ge=0),
        limit: int = Query(100, ge=1, le=2000),
        minimum: float = Query(0, ge=0, le=1),
        revision: int | None = None,
        source: str | None = None,
        node_id: str | None = None,
        checkpoint_id: UUID | None = None,
    ):
        access(request, project)
        if checkpoint_id or table == "changes":
            from .queries import checkpoint_rows

            cp, image, rows = checkpoint_rows(
                app.state.db, project, run_id, table, checkpoint_id, minimum=minimum, source=source, revision=revision
            )
            legacy = image.to_dict()["dynamics"] == "unified-associative"
            after = after if after is not None else (-1 if table == "nodes" and not legacy else 0)
            legacy_projection = {}
            if legacy:
                from .legacy_graph import PROJECTION

                legacy_projection = {"projection": PROJECTION}
            if legacy and table in ("nodes", "edges"):
                from .legacy_graph import edge_view, state_nodes

                rows = state_nodes(image.to_dict(), rows) if table == "nodes" else [edge_view(row) for row in rows]
            if node_id is not None:
                if table != "nodes":
                    raise ValueError("node_id is only accepted for node queries")
                selected = [row for row in rows if str(row["id"]) == node_id]
            else:
                selected = ([r for r in rows if r["id"] > after] if table == "nodes" and not legacy else rows[after:])[: limit + 1]
            more = len(selected) > limit
            selected = selected[:limit]
            return {
                "rows": selected,
                "more": more,
                "next": (selected[-1]["id"] if table == "nodes" and not legacy else after + len(selected)) if selected else after,
                "revision": cp["revision"],
                "time_us": cp["time_us"],
                "checkpoint_id": str(cp["id"]),
                "state_hash": image.digest,
                **legacy_projection,
            }
        result = app.state.db.query_graph(
            project, run_id, table=table, after=after, limit=limit, minimum=minimum, revision=revision, source=source, node_id=node_id
        )
        if result["kernel_id"] == "unified-associative":
            from .legacy_graph import PROJECTION, node_view

            result["projection"] = PROJECTION
            if table == "nodes":
                result["rows"] = [node_view(row) for row in result["rows"]]
        return result

    @app.post("/api/v2/projects/{project}/runs/{run_id}/data-exports", status_code=202)
    def export_data(project: UUID, run_id: UUID, body: DataExport, request: Request):
        access(request, project, write=True)
        if body.table not in ("nodes", "edges", "changes") or body.format not in ("csv", "jsonl", "parquet"):
            raise ValueError("unsupported data selection/format")
        if body.source is not None:
            kernel = app.state.db.get_run(project, run_id)["spec"]["kernel_id"]
            if kernel == "unified-associative":
                if not str(body.source):
                    raise ValueError("source identity must be nonempty")
            elif int(body.source) < 0:
                raise ValueError("source identity must be nonnegative")
        with app.state.db.tx(project) as db:
            cp = db.execute(
                "SELECT id,revision FROM checkpoints WHERE run_id=%s"
                + (" AND id=%s" if body.checkpoint_id else "")
                + " ORDER BY revision DESC LIMIT 1",
                (run_id, body.checkpoint_id) if body.checkpoint_id else (run_id,),
            ).fetchone()
        if cp is None:
            raise Conflict("no committed state to export")
        if body.revision is not None and body.revision != cp["revision"]:
            raise Conflict("selected data revision changed; refresh the query first")
        return app.state.db.enqueue(
            project, "data_export", {**body.model_dump(mode="json"), "checkpoint_id": str(cp["id"])}, run_id
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/observations")
    def observations(
        project: UUID, run_id: UUID, request: Request, after: str = "0", limit: int = Query(2000, ge=1, le=10000)
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        from threemind_core.spec import timestamp

        value = timestamp(after)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT metrics,quality FROM observations WHERE run_id=%s AND time_us>=%s ORDER BY time_us LIMIT %s",
                (run_id, value, limit + 1),
            ).fetchall()
        return {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next": str(int(rows[limit - 1]["metrics"]["time_us"]) + 1) if len(rows) >= limit else after,
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/events")
    def events(project: UUID, run_id: UUID, request: Request, after: int = 0, kind: str | None = None):
        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            return db.execute(
                "SELECT id,time_us,kind,payload FROM events WHERE run_id=%s AND id>%s AND (%s::text IS NULL OR kind=%s) AND (%s::text IS NOT NULL OR kind NOT IN ('organ_output','telemetry_sample','structural_readout','temporal_readout')) ORDER BY id LIMIT 500",
                (run_id, after, kind, kind, kind),
            ).fetchall()

    @app.get("/api/v2/projects/{project}/runs/{run_id}/checkpoints")
    def checkpoints(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            return db.execute(
                "SELECT id,revision,time_us,state_hash,byte_count,created_at,storage_format,delta_depth,label,tags,pinned,metadata_revision FROM checkpoints WHERE run_id=%s ORDER BY revision DESC LIMIT 200",
                (run_id,),
            ).fetchall()

    @app.post("/api/v2/projects/{project}/runs/{run_id}/exports", status_code=202)
    def export(project: UUID, run_id: UUID, body: Export, request: Request):
        access(request, project, write=True)
        if body.format not in ("tmind", "json", "evidence"):
            raise ValueError("unsupported export format")
        # Pin a durable version now. An export worker never follows a moving 'latest'.
        with app.state.db.tx(project) as db:
            run = db.execute("SELECT status FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
            if run is None:
                raise NotFound()
            if not body.checkpoint_id and run["status"] in ("queued", "running"):
                cmd = db.execute(
                    "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,'checkpoint','{}') RETURNING id",
                    (project, run_id),
                ).fetchone()
                return db.execute(
                    "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'export',%s) RETURNING *",
                    (uuid4(), project, run_id, Jsonb({"format": body.format, "barrier_id": cmd["id"]})),
                ).fetchone()
            cp = db.execute(
                "SELECT id,revision FROM checkpoints WHERE run_id=%s"
                + (" AND id=%s" if body.checkpoint_id else "")
                + " ORDER BY revision DESC LIMIT 1",
                (run_id, body.checkpoint_id) if body.checkpoint_id else (run_id,),
            ).fetchone()
        if cp is None:
            raise Conflict("no committed state yet; request a checkpoint first")
        return app.state.db.enqueue(project, "export", {"format": body.format, "checkpoint_id": str(cp["id"])}, run_id)

    @app.post("/api/v2/projects/{project}/runs/{run_id}/forks", status_code=201)
    def fork(project: UUID, run_id: UUID, body: Fork, request: Request):
        from .execution import select_execution

        actor = access(request, project, write=True)
        permissions.require(
            app.state.db, actor, "runs.read", project=project, resources=permissions.request_resources(request)
        )
        original = app.state.db.get_run(project, run_id)
        cp, image = app.state.db.load_checkpoint(project, run_id, body.checkpoint_id)
        # A selected historical checkpoint may precede a parameter edit. Use its
        # recorded protocol and kernel configuration, never today's run config.
        if cp["context"].get("ecological_campaign_id") and not body.inherit:
            raise Conflict(
                "生态个体的精确续跑需要整个种群恢复点；独立实验请启用继承出生，或导出模型后显式接入新的环境。"
            )
        spec = body.spec or RunSpec(
            **(
                (cp["context"].get("protocol") or original["spec"])
                | {
                    "kernel_id": image.to_dict()["dynamics"],
                    "config": image.to_dict()["config"],
                    "phases": [],
                    "intervention": None,
                }
            )
        )
        spec = spec.model_copy(update={"study_id": None, "condition": None, "block_seed": None})
        if body.background == "suspend":
            from dataclasses import replace

            spec = spec.model_copy(update={"source_policies": replace(spec.source_policies, background_enabled=False)})
        if spec.duration_s is not None and spec.duration_s > settings.max_run_seconds:
            raise ValueError("run duration exceeds this deployment's configured limit")
        descriptor = state_kernel(image)
        if spec.kernel_id != descriptor.kernel_id or descriptor.configuration(spec.config) != descriptor.configuration(
            image.to_dict()["config"]
        ):
            raise ValueError(
                "fork preserves kernel configuration; record parameter interventions through a paired study"
            )
        origin_hash = image.digest
        if not body.inherit and body.inheritance_decay_age != "preserve":
            raise ValueError("decay-age inheritance is a birth option, not an exact-fork option")
        inheritance = None
        if body.inherit:
            from threemind_runtime.inheritance import KERNEL60_BIRTH_RULE, birth_metadata

            metadata = birth_metadata(image, body.inheritance_decay_age)
            if metadata["inheritance_rule"] == KERNEL60_BIRTH_RULE:
                inheritance = {**metadata, "source_state_hash": origin_hash}
            image = birth(image, decay_age=body.inheritance_decay_age)
        row = app.state.db.create_run(
            project,
            body.name,
            spec.model_dump(),
            parent_id=run_id,
            origin_hash=origin_hash,
            origin_checkpoint_id=cp["id"],
            origin_kind="inherited" if body.inherit else "fork",
            execution=select_execution(spec.kernel_id, original.get("execution") or
                                       ({"backend": cp["context"]["backend"]} if cp["context"].get("backend") else {}),
                                       default=settings.backend),
        )
        context = (
            {}
            if body.inherit
            else {
                **cp["context"],
                "initialized": False,
                "replay_loaded": True,
                "start_us": str(cp["time_us"]),
                "phase_index": -1,
                "next_observation_us": str(cp["time_us"]),
                "end_us": str(spec.deadline_us(int(cp["time_us"]))) if spec.duration_s is not None else None,
                "protocol": spec.model_dump(),
            }
        )
        app.state.db.save_checkpoint(
            project,
            row["id"],
            image,
            context={**context, **({"birth": inheritance} if inheritance else {})},
            expected_revision=0,
            status="paused" if body.paused else "queued",
        )
        if not body.paused:
            app.state.db.enqueue(project, "run", run_id=row["id"])
        return app.state.db.get_run(project, row["id"])

    @app.post("/api/v2/projects/{project}/imports", status_code=201)
    async def import_model(project: UUID, request: Request, file: UploadFile, name: str = "Imported model"):
        from .execution import select_execution

        access(request, project, write=True)
        raw = await file.read(settings.max_import_bytes + 1)
        image, profile = await asyncio.to_thread(
            ArtifactCodec.decode, raw, max_bytes=settings.max_import_bytes, with_profile=True
        )
        # Import creates a paused instance; attaching real sensors is an explicit next action.
        state = image.to_dict()
        spec = RunSpec(
            environment="manual",
            kernel_id=state["dynamics"],
            config=state["config"],
            **(
                {
                    "seed": profile["sensory_seed"],
                    **{k: v for k, v in profile.items() if k not in ("schema", "sensory_seed")},
                }
                if profile
                else {}
            ),
        )
        row = await asyncio.to_thread(
            app.state.db.create_run,
            project,
            name[:120],
            spec.model_dump(),
            origin_hash=image.digest,
            origin_kind="imported",
            execution=select_execution(spec.kernel_id, default=settings.backend),
        )
        await asyncio.to_thread(
            app.state.db.save_checkpoint, project, row["id"], image, expected_revision=0, status="paused"
        )
        return row

    @app.get("/api/v2/projects/{project}/jobs")
    def jobs(project: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            return db.execute(
                "SELECT * FROM jobs WHERE project_id=%s ORDER BY created_at DESC LIMIT 200", (project,)
            ).fetchall()

    @app.get("/api/v2/projects/{project}/artifacts")
    def artifacts(project: UUID, request: Request):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
            return db.execute("SELECT * FROM artifacts ORDER BY created_at DESC LIMIT 200").fetchall()

    @app.get("/api/v2/projects/{project}/artifacts/{artifact_id}")
    def download(project: UUID, artifact_id: UUID, request: Request):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
            row = db.execute("SELECT * FROM artifacts WHERE id=%s", (artifact_id,)).fetchone()
        if row is None:
            raise NotFound()

        def chunks():
            from .blob_store import object_chunks

            yield from object_chunks(app.state.db, project, "artifact", artifact_id, actor=actor["id"])

        safe = re.sub(r"[^a-zA-Z0-9._-]", "_", row["name"])
        return StreamingResponse(
            chunks(),
            media_type=row["media_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{safe}"',
                "Content-Length": str(row["bytes"]),
                "ETag": row["sha256"],
            },
        )

    @app.get("/api/v2/study-configuration")
    def study_configuration(request: Request):
        auth.identity(request)
        return study_catalogue()

    @app.post("/api/v2/studies/validate")
    def check_study_without_project(body: dict, request: Request):
        auth.identity(request)
        return validate_study(body, maximum_duration=settings.max_run_seconds)

    @app.post("/api/v2/projects/{project}/studies/validate")
    def check_study(project: UUID, body: dict, request: Request):
        access(request, project)
        return validate_study(body, maximum_duration=settings.max_run_seconds)

    @app.post("/api/v2/projects/{project}/studies", status_code=202)
    def create_study(project: UUID, body: dict, request: Request):
        actor = access(request, project, write=True)
        executor = body.get("record_executor", "human")
        if executor not in ("ai", "human", "mixed", "unknown"):
            raise ValueError("invalid research executor")
        classification = body.get("record_classification", "formal")
        if classification not in ("formal", "calibration", "development"):
            raise ValueError("invalid research classification")
        protocol = require_study(
            {k: v for k, v in body.items() if k not in ("record_executor", "record_classification")},
            maximum_duration=settings.max_run_seconds,
        )
        study = uuid4()
        digest = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()
        with app.state.db.tx(project) as db:
            db.execute(
                "INSERT INTO studies(id,project_id,name,protocol,protocol_hash) VALUES(%s,%s,%s,%s,%s)",
                (study, project, protocol["name"], Jsonb(protocol), digest),
            )
            from .native_records import register_execution

            register_execution(
                app.state.db,
                db,
                project,
                actor,
                "study",
                study,
                protocol["name"],
                protocol,
                executor=executor,
                classification=classification,
            )
            return db.execute(
                "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'study',%s) RETURNING *",
                (uuid4(), project, Jsonb({"study_id": str(study), "protocol": protocol})),
            ).fetchone()

    @app.get("/api/v2/projects/{project}/studies")
    def studies(project: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            return db.execute("SELECT * FROM studies ORDER BY created_at DESC").fetchall()

    @app.get("/api/v2/projects/{project}/study-library")
    def study_library(
        project: UUID,
        request: Request,
        q: str = Query("", max_length=120),
        offset: int = Query(0, ge=0),
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT id,name,protocol_hash,created_at FROM studies WHERE strpos(lower(name),lower(%s))>0 "
                "ORDER BY created_at DESC,id LIMIT %s OFFSET %s",
                (q, limit + 1, offset),
            ).fetchall()
            return {"rows": rows[:limit], "more": len(rows) > limit, "offset": offset}

    @app.get("/api/v2/projects/{project}/studies/{study_id}")
    def study_detail(project: UUID, study_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = db.execute("SELECT * FROM studies WHERE id=%s", (study_id,)).fetchone()
            if row is None:
                raise NotFound()
            return row

    @app.get("/api/v2/projects/{project}/studies/{study_id}/trajectories")
    def trajectories(
        project: UUID,
        study_id: UUID,
        request: Request,
        metric: str = "mean_activation",
        buckets: int = Query(200, ge=10, le=1000),
    ):
        access(request, project)
        from .queries import study_trajectories

        return study_trajectories(app.state.db, project, study_id, metric, buckets)

    @app.post("/api/v2/projects/{project}/analyses", status_code=202)
    def analysis(project: UUID, body: Analysis, request: Request):
        access(request, project, write=True)
        with app.state.db.tx(project) as db:
            if not db.execute("SELECT id FROM studies WHERE id=%s", (body.study_id,)).fetchone():
                raise NotFound()
        return app.state.db.enqueue(project, "analysis", body.model_dump(mode="json"))

    from .document_api import register_document_routes

    register_document_routes(app)

    @app.get("/api/v2/projects/{project}/members")
    def members(project: UUID, request: Request):
        access(request, project)
        with app.state.db.tx() as db:
            return db.execute(
                "SELECT u.id,u.username,m.role FROM members m JOIN users u ON u.id=m.user_id WHERE m.project_id=%s",
                (project,),
            ).fetchall()

    @app.post("/api/v2/projects/{project}/members")
    def set_member(project: UUID, body: Member, request: Request):
        access(request, project, owner=True)
        if body.role not in ("researcher", "viewer"):
            raise ValueError("assign researcher or viewer")
        with app.state.db.tx() as db:
            user = db.execute("SELECT id FROM users WHERE username=%s AND enabled", (body.username,)).fetchone()
            if not user:
                raise NotFound()
            owner = db.execute("SELECT owner_id FROM projects WHERE id=%s", (project,)).fetchone()
            if owner["owner_id"] == user["id"]:
                raise Conflict("project owner cannot be downgraded here")
            db.execute(
                "INSERT INTO members VALUES(%s,%s,%s) ON CONFLICT(project_id,user_id) DO UPDATE SET role=excluded.role",
                (project, user["id"], body.role),
            )
        return {"ok": True}

    def admin(request, mutate=False):
        user = auth.identity(request, mutate=mutate)
        return permissions.require(app.state.db, user, "system.write" if mutate else "system.read")

    @app.get("/api/v2/admin")
    def administration(request: Request):
        actor = admin(request)
        if not permissions.has_action(actor, "system.write") and not permissions.has_action(actor, "accounts.read"):
            raise Forbidden("host administration requires an administration grant")
        with app.state.db.tx() as db:
            return {
                "users": db.execute(
                    "SELECT id,username,admin,enabled,created_at FROM users ORDER BY created_at"
                ).fetchall()
                if permissions.has_action(actor, "accounts.read")
                else [],
                "workers": db.execute(
                    "SELECT id,name,enabled,heartbeat,capabilities FROM workers ORDER BY name"
                ).fetchall()
                if permissions.has_action(actor, "system.write")
                else [],
                "audit": db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100").fetchall()
                if permissions.has_action(actor, "system.write")
                else [],
                "max_active_jobs": db.execute(
                    "SELECT (limits->>'runtime')::integer AS n FROM execution_limits"
                ).fetchone()["n"],
            }

    @app.post("/api/v2/admin/users")
    def user_create(body: UserCreate, request: Request):
        actor = permissions.require(app.state.db, auth.identity(request, mutate=True), "accounts.manage")
        return auth.create_user(app.state.db, body.username, body.password, admin=body.admin, actor=actor)

    @app.post("/api/v2/admin/users/{user_id}/enabled")
    def user_enabled(user_id: UUID, enabled: bool, request: Request):
        actor = permissions.require(app.state.db, auth.identity(request, mutate=True), "accounts.manage")
        return permissions.set_enabled(app.state.db, actor, user_id, enabled)

    @app.post("/api/v2/admin/workers/{worker_id}/enabled")
    def worker_enabled(worker_id: str, enabled: bool, request: Request):
        actor = admin(request, True)
        with app.state.db.tx() as db:
            if not db.execute(
                "UPDATE workers SET enabled=%s WHERE id=%s RETURNING id", (enabled, worker_id)
            ).fetchone():
                raise NotFound()
            db.execute(
                "INSERT INTO audit(user_id,action,resource) VALUES(%s,%s,%s)",
                (actor["id"], "worker.enable" if enabled else "worker.drain", worker_id),
            )
        return {"ok": True}

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "API route not found")
        root = (ROOT / "threemind-ui/dist").resolve()
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        if (root / "index.html").exists():
            return FileResponse(root / "index.html")
        return JSONResponse({"message": "Build threemind-ui or start Vite on port 3001"}, status_code=404)

    return app
