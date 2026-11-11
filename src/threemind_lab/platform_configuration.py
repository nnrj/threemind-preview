"""Versioned host creation defaults/templates; never constructs an engine."""

from copy import deepcopy
from uuid import UUID, uuid4

from fastapi import Request
from psycopg.types.json import Jsonb
from pydantic import Field

from threemind_kernels.registry import DEFAULT_KERNEL, resolve_kernel

from . import auth, permissions
from .configuration import default_spec, require_valid, validate_configuration
from .database import Conflict, NotFound
from .protocols import StrictModel


class DefaultEdit(StrictModel):
    spec: dict
    expected_revision: int = Field(ge=0, strict=True)


class ConfigurationCheck(StrictModel):
    spec: dict


class TemplateCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    spec: dict


class TemplateEdit(TemplateCreate):
    expected_revision: int = Field(ge=1, strict=True)


class TemplateFromRun(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    expected_metadata_revision: int | None = Field(default=None, ge=0, strict=True)


def factory(kernel_id=None):
    kernel = resolve_kernel(kernel_id or DEFAULT_KERNEL)
    return default_spec(kernel_id=kernel.kernel_id)


def template_row(row):
    """Expose the version's scientific identity without introducing a second key."""
    return row | {"kernel_id": resolve_kernel(row["spec"].get("kernel_id")).kernel_id}


def template_spec(spec):
    # A parameter template has no individual's membership in a research design.
    copied = deepcopy(spec)
    for field in ("study_id", "condition", "block_seed"):
        copied[field] = None
    return copied


def save_template(db, user, name, spec, *, source=None):
    identity, source = uuid4(), source or {}
    row = db.execute(
        "INSERT INTO creation_templates(id,name,spec,source,created_by) VALUES(%s,%s,%s,%s,%s) RETURNING *",
        (identity, name, Jsonb(spec), Jsonb(source), user["id"]),
    ).fetchone()
    db.execute(
        "INSERT INTO creation_template_versions(template_id,revision,name,spec,source,actor_id) "
        "VALUES(%s,1,%s,%s,%s,%s)",
        (identity, name, Jsonb(spec), Jsonb(source), user["id"]),
    )
    return template_row(row)


def builtin_templates(kernel_id=None):
    """Named parameter presets, never additional kernel implementations."""
    from threemind_runtime.stimulus_presets import research_presets

    kernel = resolve_kernel(kernel_id).kernel_id if kernel_id is not None else None
    presets = research_presets()
    if kernel in (None, "unified-associative"):
        from threemind_kernels.legacy.unified_adapter import presets as historical_presets

        presets += historical_presets()
    result = []
    for preset in presets:
        if kernel is not None and preset["kernel_id"] != kernel:
            continue
        spec = factory(preset["kernel_id"])
        spec["config"].update(preset["config"])
        row = {
            "id": preset["id"], "name": preset["label"], "kernel_id": preset["kernel_id"],
            "description": preset.get("hint", ""), "spec": spec, "revision": 1,
            "source": {"kind": "builtin-template", "id": preset["id"], "revision": 1,
                       "kernel_id": preset["kernel_id"]},
        }
        if "original_preset" in preset:
            row["original_preset"] = preset["original_preset"]
            row["source_provenance"] = preset["source"]
        result.append(row)
    return result


def _same_kernel(source_kernel, actual_kernel):
    kernel = resolve_kernel(source_kernel).kernel_id
    if actual_kernel is not None and kernel != actual_kernel:
        raise ValueError("creation source kernel differs from the actual configuration")
    return kernel


def _revision(source, minimum):
    value = source.get("revision")
    if type(value) is not int or value < minimum:
        raise ValueError(f"creation source revision must be an integer of at least {minimum}")
    return value


def creation_source(db, project, source, *, database=None, actual_kernel=None):
    """Resolve immutable provenance separately from the scientific RunSpec."""
    if not source:
        return {"kind": "explicit"}
    kind = source.get("kind")
    if kind == "template":
        identity, revision = UUID(str(source.get("id"))), _revision(source, 1)
        row = db.execute(
            "SELECT spec FROM creation_template_versions WHERE template_id=%s AND revision=%s", (identity, revision)
        ).fetchone()
        if not row:
            raise NotFound("configuration template revision does not exist")
        _same_kernel(row["spec"].get("kernel_id"), actual_kernel)
        return {"kind": kind, "id": str(identity), "revision": revision}
    if kind == "builtin-template":
        rows = builtin_templates(source.get("kernel_id") or actual_kernel)
        row = next((item for item in rows if item["id"] == source.get("id")), None)
        if row is None or type(source.get("revision")) is not int or row["revision"] != source["revision"]:
            raise NotFound("built-in template revision does not exist")
        _same_kernel(row["kernel_id"], actual_kernel)
        if source.get("kernel_id") is not None:
            _same_kernel(source["kernel_id"], row["kernel_id"])
        return row["source"] | {"source_spec": row["spec"]} | {
            key: row[key] for key in ("original_preset", "source_provenance") if key in row
        }
    if kind == "project-preset":
        origin, revision = UUID(str(source.get("project_id"))), _revision(source, 0)
        if database is None:
            raise ValueError("project preset provenance requires its source authorization")
        source_actor = (permissions.current_actor() or {}) | {
            "_request_action": "projects.read",
            "_request_resources": [{"kind": "project", "id": str(origin)}],
        }
        token = permissions.actor_context.set(source_actor)
        try:
            permissions.project_access(
                database, source_actor, origin, action="projects.read", resources=source_actor["_request_resources"]
            )
            with database.tx(origin) as source_db:
                row = source_db.execute(
                    "SELECT revision,spec FROM project_run_defaults WHERE project_id=%s", (origin,)
                ).fetchone()
        finally:
            permissions.actor_context.reset(token)
        if not row or row["revision"] != revision:
            raise Conflict("project preset changed; reload before creating")
        _same_kernel(row["spec"].get("kernel_id"), actual_kernel)
        # Legacy project presets have no immutable version table. Preserve the
        # actual copied source separately from the subsequently edited draft.
        return {"kind": kind, "project_id": str(origin), "revision": row["revision"], "source_spec": row["spec"]}
    if kind in ("factory", "system"):
        kernel = _same_kernel(source.get("kernel_id") or actual_kernel, actual_kernel)
        revision = source.get("revision", 0)
        if type(revision) is not int or revision < 0:
            raise ValueError("creation source revision must be a nonnegative integer")
        if (
            kind == "system"
            and not db.execute(
                "SELECT 1 FROM platform_creation_default_versions WHERE kernel_id=%s AND revision=%s",
                (kernel, revision),
            ).fetchone()
        ):
            raise NotFound("system creation default revision does not exist")
        if kind == "factory" and revision != 0:
            raise ValueError("factory defaults use revision zero")
        return {"kind": kind, "kernel_id": kernel, "revision": revision}
    if kind == "explicit":
        if source.get("kernel_id") is not None:
            _same_kernel(source["kernel_id"], actual_kernel)
        return {"kind": kind}
    raise ValueError("unknown creation configuration source")


def register(app):
    def actor(request, write=False):
        user = auth.identity(request, mutate=write)
        permissions.require(app.state.db, user, "system.write" if write else "system.read")
        return user

    def validate(spec):
        return require_valid(validate_configuration(spec, maximum_duration=app.state.settings.max_run_seconds))

    def reader(request):
        return permissions.require(app.state.db, auth.identity(request), "tools.read")

    @app.post("/api/v2/configuration/validate")
    def check(body: ConfigurationCheck, request: Request):
        reader(request)
        return validate_configuration(body.spec, maximum_duration=app.state.settings.max_run_seconds)

    @app.get("/api/v2/configuration/defaults")
    def defaults(request: Request, kernel_id: str | None = None):
        # Shared configuration tools need no project or system-administration grant.
        reader(request)
        spec = factory(kernel_id)
        with app.state.db.tx() as db:
            row = db.execute(
                "SELECT * FROM platform_creation_defaults WHERE kernel_id=%s", (spec["kernel_id"],)
            ).fetchone()
        return (row or {"spec": spec, "revision": 0}) | {"source": "system" if row else "factory", "factory": spec}

    @app.put("/api/v2/configuration/defaults")
    def save_defaults(body: DefaultEdit, request: Request):
        user, spec = actor(request, True), validate(body.spec)
        with app.state.db.tx() as db:
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,738349268))", (spec["kernel_id"],))
            row = db.execute(
                "SELECT revision FROM platform_creation_defaults WHERE kernel_id=%s FOR UPDATE", (spec["kernel_id"],)
            ).fetchone()
            revision = row["revision"] if row else 0
            if revision != body.expected_revision:
                raise Conflict("system creation default changed; reload before saving")
            result = db.execute(
                "INSERT INTO platform_creation_defaults(kernel_id,spec,revision,updated_by) VALUES(%s,%s,%s,%s) ON CONFLICT(kernel_id) DO UPDATE SET spec=EXCLUDED.spec,revision=EXCLUDED.revision,updated_by=EXCLUDED.updated_by,updated_at=now() RETURNING *",
                (spec["kernel_id"], Jsonb(spec), revision + 1, user["id"]),
            ).fetchone()
            db.execute(
                "INSERT INTO platform_creation_default_versions(kernel_id,revision,spec,actor_id) VALUES(%s,%s,%s,%s)",
                (spec["kernel_id"], revision + 1, Jsonb(spec), user["id"]),
            )
            return result

    @app.get("/api/v2/configuration/templates")
    def templates(request: Request, kernel_id: str | None = None):
        reader(request)
        kernel = resolve_kernel(kernel_id).kernel_id if kernel_id is not None else None
        with app.state.db.tx() as db:
            return {
                "items": [template_row(row) for row in db.execute(
                    "SELECT * FROM creation_templates WHERE NOT archived "
                    "AND (%s::text IS NULL OR spec->>'kernel_id'=%s) ORDER BY name,id", (kernel, kernel)
                ).fetchall()],
                "builtins": builtin_templates(kernel),
            }

    @app.get("/api/v2/configuration/templates/{identity}")
    def template(identity: UUID, request: Request):
        reader(request)
        with app.state.db.tx() as db:
            row = db.execute("SELECT * FROM creation_templates WHERE id=%s", (identity,)).fetchone()
        if not row:
            raise NotFound()
        return template_row(row)

    @app.get("/api/v2/configuration/templates/{identity}/versions")
    def versions(identity: UUID, request: Request):
        reader(request)
        with app.state.db.tx() as db:
            return {
                "items": [template_row(row) for row in db.execute(
                    "SELECT * FROM creation_template_versions WHERE template_id=%s ORDER BY revision DESC", (identity,)
                ).fetchall()]
            }

    @app.post("/api/v2/configuration/templates", status_code=201)
    def create(body: TemplateCreate, request: Request):
        user, spec = actor(request, True), validate(template_spec(body.spec))
        with app.state.db.tx() as db:
            return save_template(db, user, body.name, spec)

    @app.post("/api/v2/projects/{project}/runs/{run_id}/configuration-template", status_code=201)
    def from_run(project: UUID, run_id: UUID, body: TemplateFromRun, request: Request):
        user = actor(request, True)
        resources = [{"kind": "project", "id": str(project)}, {"kind": "run", "id": str(run_id)}]
        user = user | {"_request_action": "runs.read", "_request_resources": resources}
        permissions.project_access(app.state.db, user, project, action="runs.read", resources=resources)
        token = permissions.actor_context.set(user)
        try:
            with app.state.db.tx(project, read_only=True) as db:
                row = db.execute(
                    "SELECT id,spec,metadata_revision FROM runs WHERE id=%s AND project_id=%s", (run_id, project)
                ).fetchone()
            if row is None:
                raise NotFound("consciousness does not exist")
            if (body.expected_metadata_revision is not None
                    and row["metadata_revision"] != body.expected_metadata_revision):
                raise Conflict("consciousness configuration changed; reload before saving a template")
            spec = validate(template_spec(row["spec"]))
            source = {"kind": "run-configuration", "project_id": str(project), "run_id": str(run_id),
                      "metadata_revision": row["metadata_revision"]}
            with app.state.db.tx() as db:
                return save_template(db, user, body.name, spec, source=source)
        finally:
            permissions.actor_context.reset(token)

    @app.put("/api/v2/configuration/templates/{identity}")
    def edit(identity: UUID, body: TemplateEdit, request: Request):
        user, spec = actor(request, True), validate(template_spec(body.spec))
        with app.state.db.tx() as db:
            current = db.execute(
                "SELECT * FROM creation_templates WHERE id=%s FOR UPDATE", (identity,)
            ).fetchone()
            if not current or current["archived"] or current["revision"] != body.expected_revision:
                raise Conflict("template changed or no longer available")
            if resolve_kernel(current["spec"].get("kernel_id")).kernel_id != spec["kernel_id"]:
                raise ValueError("a configuration template's kernel is fixed; create a separate template")
            row = db.execute(
                "UPDATE creation_templates SET name=%s,spec=%s,revision=revision+1,updated_at=now() WHERE id=%s AND revision=%s AND NOT archived RETURNING *",
                (body.name, Jsonb(spec), identity, body.expected_revision),
            ).fetchone()
            if not row:
                raise Conflict("template changed or no longer available")
            db.execute(
                "INSERT INTO creation_template_versions(template_id,revision,name,spec,source,actor_id) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (identity, row["revision"], body.name, Jsonb(spec), Jsonb(row["source"]), user["id"]),
            )
            return template_row(row)
