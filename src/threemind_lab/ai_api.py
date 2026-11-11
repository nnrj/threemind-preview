from __future__ import annotations

import json
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import Response

from . import ai_providers as providers
from . import auth, permissions
from .ai_schema import Grants, ProviderConfig, ProviderEdit, TestRequest
from .ai_tool_schema import LabAITools, ToolEdit, ToolRequest
from .database import Forbidden, NotFound


def register_ai_routes(app, access):
    prefix = "/api/v2/projects/{project}/ai"
    run_prefix = "/api/v2/projects/{project}/runs/{run_id}/ai-tools"

    @app.get(run_prefix)
    def run_tools(project: UUID, run_id: UUID, request: Request):
        from . import ai_tools

        access(request, project)
        with app.state.db.tx(project) as db:
            ai_tools.get_run(db, run_id)
            current = ai_tools.get(db, run_id)
            schedule = db.execute(
                "SELECT enabled,next_poll_at,state FROM ai_tool_schedules WHERE run_id=%s", (run_id,)
            ).fetchone()
        return current | {
            "schedule": schedule,
            "schema": LabAITools.model_json_schema(),
            "defaults": LabAITools().model_dump(mode="json"),
        }

    @app.put(run_prefix)
    def save_run_tools(project: UUID, run_id: UUID, body: ToolEdit, request: Request):
        from .ai_tools import save

        actor = access(request, project, write=True)
        return save(app.state.db, project, run_id, actor["id"], body)

    @app.post(run_prefix + "/validate")
    def validate_tools(project: UUID, run_id: UUID, body: LabAITools, request: Request):
        from . import ai_tools

        access(request, project)
        with app.state.db.tx(project) as db:
            ai_tools.get_run(db, run_id)
            for tool in (body.environment, body.interpreter, body.assistant):
                if tool.provider_id is not None:
                    providers.get(db, tool.provider_id)
        return {"config": body.model_dump(mode="json")}

    @app.get(run_prefix + "/status")
    def tool_status(project: UUID, run_id: UUID, request: Request):
        from . import ai_tools

        access(request, project)
        with app.state.db.tx(project) as db:
            ai_tools.get_run(db, run_id)
            revision = db.execute("SELECT revision FROM ai_run_tools WHERE run_id=%s", (run_id,)).fetchone()
            schedule = db.execute(
                "SELECT enabled,next_poll_at,state FROM ai_tool_schedules WHERE run_id=%s", (run_id,)
            ).fetchone()
        return {"revision": revision["revision"] if revision else 0, "schedule": schedule}

    @app.post(run_prefix + "/requests", status_code=202)
    def tool_request(project: UUID, run_id: UUID, body: ToolRequest, request: Request):
        from . import ai_tools

        actor = access(request, project, write=True)
        return ai_tools.request(app.state.db, app.state.settings, project, run_id, actor["id"], body)

    @app.get(run_prefix + "/versions")
    def tool_versions(
        project: UUID,
        run_id: UUID,
        request: Request,
        before: int | None = Query(None, ge=1),
        limit: int = Query(20, ge=1, le=100),
    ):
        from . import ai_tools

        access(request, project)
        with app.state.db.tx(project) as db:
            ai_tools.get_run(db, run_id)
            rows = db.execute(
                "SELECT revision,actor_id,created_at,config FROM ai_tool_versions WHERE run_id=%s "
                + ("AND revision<%s " if before else "")
                + "ORDER BY revision DESC LIMIT %s",
                (run_id,) + ((before,) if before else ()) + (limit + 1,),
            ).fetchall()
        return {"items": rows[:limit], "next": rows[limit - 1]["revision"] if len(rows) > limit else None}

    @app.get(run_prefix + "/export")
    def tool_export(project: UUID, run_id: UUID, request: Request):
        from fastapi.responses import StreamingResponse

        from . import ai_tools

        access(request, project)
        with app.state.db.tx(project) as db:
            ai_tools.get_run(db, run_id)

        def stream():
            with app.state.db.tx(project, repeatable=True) as db:
                yield (
                    json.dumps(
                        {
                            "schema": "threemind.lab-ai-tools-history/2",
                            "run_id": str(run_id),
                            "current": ai_tools.get(db, run_id),
                        },
                        default=str,
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                with db.cursor(name="ai_tool_history") as cursor:
                    cursor.execute("SELECT * FROM ai_tool_versions WHERE run_id=%s ORDER BY revision", (run_id,))
                    cursor.itersize = 20
                    for row in cursor:
                        yield json.dumps(row, default=str, ensure_ascii=False) + "\n"

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="ai-tools-{run_id}.jsonl"'},
        )

    def admin(request, mutate=False):
        actor = auth.identity(request, mutate=mutate)
        return permissions.require(app.state.db, actor, "services.manage" if mutate else "services.read")

    @app.get(prefix + "/providers")
    def listing(project: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT " + providers.PUBLIC + " FROM ai_providers ORDER BY (config->>'priority')::integer,created_at"
            ).fetchall()
        return {
            "providers": [
                row
                | {
                    "network_allowed": providers.network_allowed(
                        app.state.settings, ProviderConfig.model_validate(row["config"])
                    )
                }
                for row in rows
            ],
            "secrets_ready": bool(app.state.settings.secret_keys),
            "mode": app.state.settings.mode,
        }

    @app.post(prefix + "/providers", status_code=201)
    def create(project: UUID, body: ProviderEdit, request: Request):
        actor = admin(request, True)
        return providers.save(app.state.db, app.state.settings, project, actor["id"], body)

    @app.put(prefix + "/providers/{provider_id}")
    def edit(project: UUID, provider_id: UUID, body: ProviderEdit, request: Request):
        actor = admin(request, True)
        return providers.save(app.state.db, app.state.settings, project, actor["id"], body, provider_id)

    @app.post(prefix + "/providers/{provider_id}/test", status_code=202)
    def test(project: UUID, provider_id: UUID, body: TestRequest, request: Request):
        actor = access(request, project, write=True)
        return providers.enqueue(
            app.state.db,
            app.state.settings,
            project,
            actor["id"],
            provider_id,
            request_id=body.request_id,
            purpose="provider_test",
            prompt={"system": "You are testing a configured text endpoint.", "user": body.prompt},
        )

    @app.get(prefix + "/calls")
    def calls(
        project: UUID,
        request: Request,
        before: int | None = Query(None, ge=1),
        limit: int = Query(25, ge=1, le=100),
        run_id: UUID | None = None,
        purpose: str | None = None,
    ):
        access(request, project)
        conditions, params = ["true"], []
        for clause, value in (("ordinal<%s", before), ("run_id=%s", run_id), ("purpose=%s", purpose)):
            if value is not None:
                conditions.append(clause)
                params.append(value)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT "
                + providers.CALL_SUMMARY
                + " FROM ai_calls WHERE "
                + " AND ".join(conditions)
                + " ORDER BY ordinal DESC LIMIT %s",
                (*params, limit + 1),
            ).fetchall()
        return {"items": rows[:limit], "next": rows[limit - 1]["ordinal"] if len(rows) > limit else None}

    @app.get(prefix + "/calls/{call_id}")
    def call(project: UUID, call_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            return providers.call_by_id(db, call_id)

    @app.get(prefix + "/calls/{call_id}/status")
    def call_status(project: UUID, call_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = db.execute(
                "SELECT c.id,c.status,c.purpose,c.cancel_requested,c.response_text,c.response_meta,c.result,"
                "c.usage,c.reserved_usd,c.cost_usd,c.error,c.updated_at,j.status AS job_status,j.error AS job_error "
                "FROM ai_calls c JOIN jobs j ON j.id=c.job_id WHERE c.id=%s",
                (call_id,),
            ).fetchone()
        if row is None:
            raise NotFound()
        return row

    @app.post(prefix + "/calls/{call_id}/cancel")
    def cancel(project: UUID, call_id: UUID, request: Request):
        access(request, project, write=True)
        with app.state.db.tx(project) as db:
            row = providers.call_by_id(db, call_id)
            if row["run_id"] is not None:
                from .ai_tools import get_run

                get_run(db, row["run_id"], lock=True)
                row = providers.call_by_id(db, call_id)
            elif row["purpose"] in ("record", "report", "world", "ecology_observation"):
                row = db.execute("SELECT * FROM ai_calls WHERE id=%s FOR UPDATE", (call_id,)).fetchone()
            cancellable = row["status"] not in providers.TERMINAL or (
                row["status"] == "completed" and row["purpose"] != "provider_test" and not row["result"]
            )
            if cancellable:
                db.execute("UPDATE ai_calls SET cancel_requested=true,updated_at=now() WHERE id=%s", (call_id,))
            return {"id": call_id, "status": row["status"], "cancel_requested": row["cancel_requested"] or cancellable}

    @app.get(prefix + "/calls/{call_id}/export")
    def export(project: UUID, call_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = providers.call_by_id(db, call_id)
        return Response(
            json.dumps({"schema": "threemind.ai-call/2", "call": row}, default=str, ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="ai-call-{call_id}.json"'},
        )

    @app.get("/api/v2/admin/ai/providers")
    def platform_list(request: Request):
        actor = admin(request)
        with app.state.db.tx(ai_admin=True) as db:
            rows = db.execute(
                "SELECT " + providers.PUBLIC + " FROM ai_providers WHERE project_id IS NULL ORDER BY created_at"
            ).fetchall()
            grants = db.execute("SELECT * FROM ai_provider_grants").fetchall()
        projects = []
        if permissions.has_action(actor, "projects.read") and not actor.get("delegation_id"):
            projects = [{"id": p["id"], "name": p["name"]} for p in app.state.db.projects(actor)]
        return {
            "providers": [
                row
                | {
                    "network_allowed": providers.network_allowed(
                        app.state.settings, ProviderConfig.model_validate(row["config"])
                    )
                }
                for row in rows
            ],
            "grants": grants,
            "projects": projects,
            "secrets_ready": bool(app.state.settings.secret_keys),
        }

    @app.post("/api/v2/admin/ai/providers", status_code=201)
    def platform_create(body: ProviderEdit, request: Request):
        actor = admin(request, True)
        return providers.save(app.state.db, app.state.settings, None, actor["id"], body, platform=True)

    @app.put("/api/v2/admin/ai/providers/{provider_id}")
    def platform_edit(provider_id: UUID, body: ProviderEdit, request: Request):
        actor = admin(request, True)
        return providers.save(app.state.db, app.state.settings, None, actor["id"], body, provider_id, platform=True)

    @app.put("/api/v2/admin/ai/providers/{provider_id}/grants")
    def platform_grants(provider_id: UUID, body: Grants, request: Request):
        actor = admin(request, True)
        with app.state.db.tx(ai_admin=True) as db:
            providers.provider_lock(db, provider_id)
            row = providers.get(db, provider_id)
            if row["project_id"] is not None:
                raise Forbidden("只有平台供应商可以授权共享")
            if len(set(body.projects)) != len(body.projects):
                raise ValueError("项目授权不能重复")
            found = db.execute("SELECT id FROM projects WHERE id=ANY(%s)", (body.projects,)).fetchall()
            if len(found) != len(body.projects):
                raise NotFound("授权项目不存在")
            db.execute("DELETE FROM ai_provider_grants WHERE provider_id=%s", (provider_id,))
            for project in body.projects:
                db.execute("INSERT INTO ai_provider_grants VALUES(%s,%s)", (provider_id, project))
            db.execute(
                "INSERT INTO audit(user_id,action,resource) VALUES(%s,'ai.provider.grants',%s)",
                (actor["id"], str(provider_id)),
            )
        return {"projects": body.projects}

    @app.get("/api/v2/ai/providers")
    def available_providers(request: Request, project: UUID | None = None):
        """One catalogue; project is an optional authorization filter, never a configuration owner."""
        actor = auth.identity(request)
        if not permissions.has_action(actor, "services.read"):
            raise Forbidden("没有服务目录读取权限")
        if project is not None:
            permissions.project_access(app.state.db, actor, project, action="services.read")
        with app.state.db.tx(ai_admin=True) as db:
            rows = db.execute("SELECT " + providers.PUBLIC + " FROM ai_providers ORDER BY created_at,id").fetchall()
            grants = db.execute("SELECT provider_id,project_id FROM ai_provider_grants").fetchall()
        visible = []
        for row in rows:
            resource = {"kind": "service", "id": str(row["id"])}
            allowed_projects = [
                grant["project_id"]
                for grant in grants
                if grant["provider_id"] == row["id"]
                and (project is None or grant["project_id"] == project)
                and permissions.allows(
                    app.state.db,
                    actor,
                    "services.read",
                    project=grant["project_id"],
                    resources=[resource, {"kind": "project", "id": str(grant["project_id"])}],
                )
            ]
            if project is not None and not allowed_projects:
                continue
            if not allowed_projects and not (
                project is None and permissions.allows(app.state.db, actor, "services.read", resources=[resource])
            ):
                continue
            visible.append(
                row
                | {
                    "authorized_projects": allowed_projects,
                    "can_manage": permissions.allows(app.state.db, actor, "services.manage", resources=[resource]),
                    "can_diagnose": permissions.allows(app.state.db, actor, "services.read", resources=[resource])
                    and permissions.allows(app.state.db, actor, "services.use", resources=[resource]),
                    "network_allowed": providers.network_allowed(
                        app.state.settings, ProviderConfig.model_validate(row["config"])
                    ),
                }
            )
        return {
            "providers": visible,
            "secrets_ready": bool(app.state.settings.secret_keys),
            "mode": app.state.settings.mode,
        }

    @app.get("/api/v2/admin/ai/providers/{provider_id}/versions")
    def provider_versions(
        provider_id: UUID,
        request: Request,
        before: int | None = Query(None, ge=1),
        limit: int = Query(20, ge=1, le=100),
    ):
        admin(request)
        with app.state.db.tx(ai_admin=True) as db:
            providers.get(db, provider_id)
            rows = db.execute(
                "SELECT revision,config,actor_id,created_at,source FROM ai_provider_versions "
                "WHERE provider_id=%s " + ("AND revision<%s " if before else "") + "ORDER BY revision DESC LIMIT %s",
                (provider_id,) + ((before,) if before else ()) + (limit + 1,),
            ).fetchall()
        return {"items": rows[:limit], "next": rows[limit - 1]["revision"] if len(rows) > limit else None}

    @app.post("/api/v2/admin/ai/providers/{provider_id}/test", status_code=202)
    @app.post("/api/v2/ai/providers/{provider_id}/test", status_code=202)
    def platform_test(provider_id: UUID, body: TestRequest, request: Request):
        actor = auth.identity(request, mutate=True)
        permissions.require(
            app.state.db, actor, "services.use", resources=[{"kind": "service", "id": str(provider_id)}]
        )
        return providers.enqueue(
            app.state.db,
            app.state.settings,
            None,
            actor["id"],
            provider_id,
            request_id=body.request_id,
            purpose="provider_test",
            prompt={"system": "You are testing a configured text endpoint.", "user": body.prompt},
        )

    def diagnostic_actor(request, *, mutate=False, row=None, provider_id=None):
        actor = auth.identity(request, mutate=mutate)
        resource = provider_id or (row["provider_id"] if row else None)
        actor = permissions.require(
            app.state.db,
            actor,
            "services.use" if mutate else "services.read",
            resources=[{"kind": "service", "id": str(resource)}] if resource else [],
        )
        if row and (
            row["project_id"] is not None or (not actor["superadmin"] and str(row["actor_id"]) != str(actor["id"]))
        ):
            raise NotFound()
        return actor

    @app.get("/api/v2/ai/calls")
    def diagnostics(
        request: Request,
        provider_id: UUID | None = None,
        before: int | None = Query(None, ge=1),
        limit: int = Query(25, ge=1, le=100),
    ):
        actor = diagnostic_actor(request, provider_id=provider_id)
        clauses, values = ["project_id IS NULL"], []
        for clause, value in (
            ("actor_id=%s", None if actor["superadmin"] else actor["id"]),
            ("provider_id=%s", provider_id),
            ("ordinal<%s", before),
        ):
            if value is not None:
                clauses.append(clause)
                values.append(value)
        with app.state.db.tx(ai_admin=True) as db:
            rows = db.execute(
                "SELECT "
                + providers.CALL_SUMMARY
                + " FROM ai_calls WHERE "
                + " AND ".join(clauses)
                + " ORDER BY ordinal DESC LIMIT %s",
                (*values, limit + 1),
            ).fetchall()
        return {"items": rows[:limit], "next": rows[limit - 1]["ordinal"] if len(rows) > limit else None}

    def diagnostic(request, call_id, *, mutate=False):
        # Identity is checked before any protected row is read; the actual service is checked afterwards.
        auth.identity(request, mutate=mutate)
        with app.state.db.tx(ai_admin=True) as db:
            row = providers.call_by_id(db, call_id)
        diagnostic_actor(request, mutate=mutate, row=row)
        return row

    @app.get("/api/v2/ai/calls/{call_id}")
    def diagnostic_detail(call_id: UUID, request: Request):
        return diagnostic(request, call_id)

    @app.get("/api/v2/ai/calls/{call_id}/status")
    def diagnostic_status(call_id: UUID, request: Request):
        row = diagnostic(request, call_id)
        with app.state.db.tx(ai_admin=True) as db:
            job = db.execute("SELECT status,error FROM jobs WHERE id=%s", (row["job_id"],)).fetchone()
        return {
            key: row[key]
            for key in (
                "id",
                "status",
                "purpose",
                "cancel_requested",
                "response_text",
                "response_meta",
                "usage",
                "reserved_usd",
                "cost_usd",
                "error",
                "updated_at",
            )
        } | {"job_status": job["status"], "job_error": job["error"]}

    @app.post("/api/v2/ai/calls/{call_id}/cancel")
    def diagnostic_cancel(call_id: UUID, request: Request):
        diagnostic(request, call_id, mutate=True)
        with app.state.db.tx(ai_admin=True) as db:
            row = db.execute("SELECT * FROM ai_calls WHERE id=%s FOR UPDATE", (call_id,)).fetchone()
            cancellable = row["status"] not in providers.TERMINAL
            if cancellable:
                db.execute("UPDATE ai_calls SET cancel_requested=true,updated_at=now() WHERE id=%s", (call_id,))
        return {"id": call_id, "status": row["status"], "cancel_requested": row["cancel_requested"] or cancellable}

    @app.get("/api/v2/ai/calls/{call_id}/export")
    def diagnostic_export(call_id: UUID, request: Request):
        row = diagnostic(request, call_id)
        return Response(
            json.dumps({"schema": "threemind.ai-call/2", "call": row}, default=str, ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="ai-call-{call_id}.json"'},
        )
