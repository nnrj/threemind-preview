from uuid import UUID

from fastapi import Query, Request
from pydantic import Field

from . import ecology_ai as store
from .database import Conflict
from .protocols import StrictModel


class Configuration(StrictModel):
    configuration: store.AIConfig
    expected_revision: int = Field(ge=0, strict=True)


class Resume(StrictModel):
    expected_revision: int = Field(ge=1, strict=True)


def register_ecology_ai_routes(app, access):
    root = "/api/v2/projects/{project}/ecologies/{identity}/observer/ai"

    @app.get(root)
    def detail(project: UUID, identity: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            saved = store.current(db, identity)
            total = db.execute(
                "SELECT count(*) AS n FROM ecology_ai_sources WHERE campaign_id=%s AND configuration_revision=%s",
                (identity, saved["revision"] if saved else 0),
            ).fetchone()["n"]
        return {
            "configuration": saved,
            "calls_in_revision": total,
            "defaults": store.AIConfig().model_dump(mode="json"),
            "template": store.TEMPLATE,
        }

    @app.post(root + "/validate")
    def validate(project: UUID, identity: UUID, request: Request, body: store.AIConfig):
        access(request, project)
        with app.state.db.tx(project) as db:
            store.ecology_observers.subject(db, identity)
        return {"valid": True, "configuration": body.model_dump(mode="json")}

    @app.post(root + "/configuration")
    def configure(project: UUID, identity: UUID, request: Request, body: Configuration):
        actor = access(request, project, write=True)
        return store.configure(
            app.state.db, app.state.settings, project, identity, actor["id"], body.configuration, body.expected_revision
        )

    @app.get(root + "/revisions")
    def revisions(project: UUID, identity: UUID, request: Request, before: int | None = Query(None, ge=1)):
        access(request, project)
        with app.state.db.tx(project) as db:
            store.ecology_observers.subject(db, identity)
            rows = db.execute(
                "SELECT * FROM ecology_ai_revisions WHERE campaign_id=%s AND (%s::bigint IS NULL OR revision<%s) ORDER BY revision DESC LIMIT 31",
                (identity, before, before),
            ).fetchall()
        return {"rows": rows[:30], "more": len(rows) > 30}

    @app.post(root + "/preview")
    def preview(project: UUID, identity: UUID, request: Request, body: store.Scope):
        access(request, project, write=True)
        with app.state.db.tx(project, repeatable=True) as db:
            return store.prepare(db, identity, body)

    @app.post(root + "/requests")
    def generate(project: UUID, identity: UUID, request: Request, body: store.Generation):
        actor = access(request, project, write=True)
        return store.request(app.state.db, app.state.settings, project, identity, actor["id"], body)

    @app.post(root + "/resume")
    def resume(project: UUID, identity: UUID, request: Request, body: Resume):
        actor = access(request, project, write=True)
        with app.state.db.tx(project) as db:
            row = store.current(db, identity, lock=True)
            if row is None or row["revision"] != body.expected_revision:
                raise Conflict("AI 观察配置已改变。")
            if not row["configuration"]["enabled"] or not row["configuration"]["automatic"]:
                raise Conflict("当前未启用自动 AI 观察。")
            db.execute(
                "UPDATE ecology_ai_schedules SET enabled=true,next_poll_at=clock_timestamp(),state=state-'blocked'-'last_error' WHERE campaign_id=%s",
                (identity,),
            )
            db.execute(
                "INSERT INTO audit(user_id,action,resource) VALUES(%s,'ecology.ai.resume',%s)",
                (actor["id"], str(identity)),
            )
        return {"resumed": True}

    @app.get(root + "/calls")
    def calls(project: UUID, identity: UUID, request: Request, before: int | None = Query(None, ge=1)):
        access(request, project)
        with app.state.db.tx(project) as db:
            store.ecology_observers.subject(db, identity)
            rows = db.execute(
                "SELECT c.id,c.ordinal,c.status,jsonb_build_object('application_status',c.result->'application_status',"
                "'summary',c.result->'interpretation'->'summary','error',c.result->'error') AS result,"
                "c.error,c.cancel_requested,c.created_at,c.evidence->'trigger' AS trigger,"
                "c.evidence->>'evidence_hash' AS evidence_hash,s.configuration_revision,s.checkpoint_id,s.first_revision "
                "FROM ecology_ai_sources s JOIN ai_calls c ON c.id=s.call_id WHERE s.campaign_id=%s "
                "AND (%s::bigint IS NULL OR c.ordinal<%s) ORDER BY c.ordinal DESC LIMIT 16",
                (identity, before, before),
            ).fetchall()
        return {"rows": rows[:15], "more": len(rows) > 15}
