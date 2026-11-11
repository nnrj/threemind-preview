"""Explicit, typed manual research commands and checkpoint-referenced journals."""

import json
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field, model_validator

from .protocols import StrictModel
from .research_commands import required_action
from .research_operations import record_observation, submit_advance


class ResearchAction(StrictModel):
    request_id: UUID
    kind: Literal["runtime.advance", "observe.summary", "observe.graph", "observe.output", "experiment.note"]
    expected_revision: int | None = Field(None, ge=1, strict=True)
    duration_us: int | None = Field(None, ge=1, le=86_400_000_000, strict=True)
    checkpoint_id: UUID | None = None
    text: str = Field("", max_length=20000, strict=True)

    @model_validator(mode="after")
    def declared_parameters(self):
        if self.kind == "runtime.advance":
            if (
                self.expected_revision is None
                or self.duration_us is None
                or self.checkpoint_id is not None
                or self.text
            ):
                raise ValueError("逐步推进仅接受科学修订号与推进微秒数。")
        elif self.expected_revision is not None or self.duration_us is not None:
            raise ValueError("观察和注记不接受推进参数。")
        elif self.kind != "experiment.note" and self.text:
            raise ValueError("观察命令不接受额外文本。")
        elif self.kind == "experiment.note" and not self.text.strip():
            raise ValueError("请填写注记内容。")
        return self


def register_research_routes(app, access):
    @app.get("/api/v2/projects/{project}/runs/{run_id}/research/evidence/{event_id}")
    def evidence(project: UUID, run_id: UUID, event_id: int, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            from .database import NotFound

            row = db.execute(
                "SELECT id::text AS id,kind,time_us,commit_revision,payload FROM events WHERE run_id=%s AND id=%s",
                (run_id, event_id),
            ).fetchone()
            if row is None:
                raise NotFound()
            return row

    @app.post("/api/v2/projects/{project}/runs/{run_id}/research/actions")
    def action(project: UUID, run_id: UUID, body: ResearchAction, request: Request):
        user = access(request, project, write=True, action=required_action(body.kind))
        if body.kind == "runtime.advance":
            return submit_advance(
                app.state.db,
                project,
                run_id,
                user["id"],
                request_id=body.request_id,
                expected_revision=body.expected_revision,
                duration_us=body.duration_us,
            )
        return record_observation(
            app.state.db,
            project,
            run_id,
            user["id"],
            request_id=body.request_id,
            kind=body.kind,
            checkpoint_id=body.checkpoint_id,
            text=body.text,
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/research/actions")
    def history(
        project: UUID,
        run_id: UUID,
        request: Request,
        before: int | None = Query(None, ge=1),
        ceiling: int | None = Query(None, ge=0),
        plan_id: UUID | None = None,
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        with app.state.db.tx(project) as db:
            from .database import NotFound

            if db.execute("SELECT id FROM runs WHERE id=%s", (run_id,)).fetchone() is None:
                raise NotFound()
            if ceiling is None:
                ceiling = db.execute(
                    "SELECT coalesce(max(ordinal),0) AS n FROM research_operations WHERE run_id=%s", (run_id,)
                ).fetchone()["n"]
            rows = db.execute(
                "SELECT * FROM research_operations WHERE run_id=%s AND ordinal<=%s "
                + ("AND plan_id=%s " if plan_id is not None else "")
                + ("AND ordinal<%s " if before is not None else "")
                + "ORDER BY ordinal DESC LIMIT %s",
                (run_id, ceiling)
                + ((plan_id,) if plan_id is not None else ())
                + ((before,) if before is not None else ())
                + (limit + 1,),
            ).fetchall()
        for row in rows:
            row["ordinal"] = str(row["ordinal"])
        return {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "ceiling": str(ceiling),
            "next": rows[limit - 1]["ordinal"] if len(rows) > limit else None,
        }

    @app.get("/api/v2/projects/{project}/runs/{run_id}/research/export")
    def export(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            from .database import NotFound

            if db.execute("SELECT id FROM runs WHERE id=%s", (run_id,)).fetchone() is None:
                raise NotFound()

        def stream():
            with app.state.db.tx(project, repeatable=True) as db, db.cursor(name="research_export") as cursor:
                cursor.itersize = 20
                cursor.execute("SELECT * FROM research_operations WHERE run_id=%s ORDER BY created_at,id", (run_id,))
                for row in cursor:
                    yield json.dumps(row, default=str, ensure_ascii=False, allow_nan=False) + "\n"

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="research-actions-{run_id}.jsonl"'},
        )
