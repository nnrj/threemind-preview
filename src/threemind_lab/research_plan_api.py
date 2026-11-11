"""Project-scoped validation, frozen plans and explicit execution controls."""

import json
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field

from . import research_plans
from .database import NotFound
from .protocols import StrictModel
from .research_commands import ResearchProtocol, StageProtocol, catalog, parse_protocol, template


class PlanCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    request_id: UUID
    expected_revision: int = Field(ge=1, strict=True)
    protocol: ResearchProtocol | StageProtocol
    derived_from: UUID | None = None


class PlanControl(StrictModel):
    action: str
    request_id: UUID
    expected_step: int = Field(ge=0, le=20000, strict=True)
    expected_revision: int = Field(ge=1, strict=True)


class TemplateRequest(StrictModel):
    name: str
    first: str = Field("甲", max_length=20000)
    second: str = Field("乙", max_length=20000)
    repeats: int = Field(3, ge=1, le=12, strict=True)
    wait_us: int = Field(100000, ge=1, le=86400000000, strict=True)


def register_plan_routes(app, access):
    prefix = "/api/v2/projects/{project}/runs/{run_id}/research"

    @app.get(prefix + "/commands")
    def commands(project: UUID, run_id: UUID, request: Request):
        access(request, project, action="runs.read")
        with app.state.db.tx(project) as db:
            if not db.execute("SELECT 1 FROM runs WHERE id=%s", (run_id,)).fetchone():
                raise NotFound()
        return catalog()

    @app.post(prefix + "/plans/validate")
    def validate(project: UUID, run_id: UUID, body: ResearchProtocol | StageProtocol, request: Request):
        access(request, project, action="runs.read")
        with app.state.db.tx(project) as db:
            if not db.execute("SELECT 1 FROM runs WHERE id=%s", (run_id,)).fetchone():
                raise NotFound()
        return {"valid": True, "protocol": body.model_dump(), "totals": body.totals()}

    @app.post(prefix + "/templates")
    def templates(project: UUID, run_id: UUID, body: TemplateRequest, request: Request):
        access(request, project, action="runs.read")
        with app.state.db.tx(project) as db:
            if not db.execute("SELECT 1 FROM runs WHERE id=%s", (run_id,)).fetchone():
                raise NotFound()
        return template(**body.model_dump())

    @app.post(prefix + "/plans", status_code=201)
    def create(project: UUID, run_id: UUID, body: PlanCreate, request: Request):
        actor = access(request, project, write=True, action="research.write")
        return research_plans.create(app.state.db, project, run_id, actor["id"], **body.model_dump())

    @app.get(prefix + "/plans")
    def listing(
        project: UUID,
        run_id: UUID,
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ):
        access(request, project)
        with app.state.db.tx(project) as db:
            if not db.execute("SELECT 1 FROM runs WHERE id=%s", (run_id,)).fetchone():
                raise NotFound()
            rows = db.execute(
                "SELECT id,name,status,next_step,expected_revision,origin,protocol_hash,created_at,updated_at,error,"
                "protocol FROM research_plans WHERE run_id=%s "
                "ORDER BY created_at DESC,id LIMIT %s OFFSET %s",
                (run_id, limit + 1, offset),
            ).fetchall()
        for row in rows:
            row["step_count"] = parse_protocol(row.pop("protocol")).step_count
        return {"rows": rows[:limit], "more": len(rows) > limit, "offset": offset}

    @app.get(prefix + "/plans/{plan_id}")
    def detail(project: UUID, run_id: UUID, plan_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = research_plans.get(db, run_id, plan_id)
            row["cursor"] = parse_protocol(row["protocol"]).cursor_at(row["next_step"])
            return row

    @app.post(prefix + "/plans/{plan_id}/control")
    def control(project: UUID, run_id: UUID, plan_id: UUID, body: PlanControl, request: Request):
        actor = access(request, project, write=True, action="runs.resume" if body.action == "start" else "runs.pause")
        return research_plans.control(app.state.db, project, run_id, plan_id, actor["id"], **body.model_dump())

    @app.get(prefix + "/plans/{plan_id}/status")
    def status(project: UUID, run_id: UUID, plan_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            row = db.execute(
                "SELECT id,status,next_step,step_attempt,wait_target_us,expected_revision,expected_command,"
                "job_id,stop_requested,cancel_requested,error,updated_at,protocol FROM research_plans WHERE run_id=%s AND id=%s",
                (run_id, plan_id),
            ).fetchone()
            if row is None:
                raise NotFound()
            row["cursor"] = parse_protocol(row.pop("protocol")).cursor_at(row["next_step"])
            return row

    @app.get(prefix + "/plans/{plan_id}/export")
    def export(project: UUID, run_id: UUID, plan_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            research_plans.get(db, run_id, plan_id)

        def stream():
            with app.state.db.tx(project, repeatable=True) as db:
                plan = research_plans.get(db, run_id, plan_id)
                yield json.dumps({"type": "frozen_plan", "value": plan}, default=str, ensure_ascii=False) + "\n"
                with db.cursor(name="plan_receipts") as cursor:
                    cursor.itersize = 20
                    cursor.execute(
                        "SELECT * FROM research_operations WHERE run_id=%s AND plan_id=%s ORDER BY ordinal",
                        (run_id, plan_id),
                    )
                    for row in cursor:
                        yield json.dumps({"type": "operation", "value": row}, default=str, ensure_ascii=False) + "\n"

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="research-plan-{plan_id}.jsonl"'},
        )
