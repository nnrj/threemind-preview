"""Explicit scalar input port and committed evidence; never a semantic control channel."""

import json
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field

from threemind_core.attention import modulation_payload

from . import ports
from .database import NotFound
from .protocols import StrictModel
from .resource_evidence import export_stream, rows, selection


class ModulationRequest(StrictModel):
    request_id: UUID
    source: str = Field(default="manual-input-port", min_length=1, max_length=128)
    gain: float = Field(default=1.0, ge=0, le=2, strict=True)
    budget_multiplier: float = Field(default=1.0, ge=0, le=2, strict=True)
    competition_enabled: bool = Field(default=False, strict=True)
    ttl_us: int = Field(default=30_000_000, ge=1, le=10**12, strict=True)
    delay_us: int = Field(default=0, ge=0, le=10**12, strict=True)


def submit(database, project, run_id, actor_id, request: ModulationRequest):
    payload = modulation_payload(**request.model_dump(exclude={"request_id", "delay_us"}))
    return ports.submit(
        database,
        project,
        run_id,
        actor_id,
        kind="input_modulation",
        request_id=request.request_id,
        payload=payload | {"delay_us": request.delay_us},
    )


def journal(database, project, run_id, *, after=0, limit=50, export=False):
    with database.tx(project, repeatable=True) as db:
        if db.execute("SELECT 1 FROM runs WHERE id=%s", (run_id,)).fetchone() is None:
            raise NotFound("run")
        query = """SELECT id,time_us,kind,payload,commit_revision FROM events WHERE run_id=%s AND id>%s
                   AND kind IN ('input_modulation','input_modulation_scheduled','input_modulation_delivered') ORDER BY id"""
        if export:
            with db.cursor(name="input_modulation_journal") as cursor:
                cursor.execute(query, (run_id, after))
                cursor.itersize = 500
                for row in cursor:
                    yield (json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode()
        else:
            values = db.execute(query + " LIMIT %s", (run_id, after, limit + 1)).fetchall()
            yield {
                "rows": values[:limit],
                "more": len(values) > limit,
                "next": values[limit - 1]["id"] if len(values) >= limit else after,
            }


def register_input_selection_routes(app, access):
    @app.post("/api/v2/projects/{project}/runs/{run_id}/attention/modulate", status_code=202)
    def modulate(project: UUID, run_id: UUID, body: ModulationRequest, request: Request):
        user = access(request, project, write=True)
        return submit(app.state.db, project, run_id, user["id"], body)

    @app.get("/api/v2/projects/{project}/runs/{run_id}/attention")
    def evidence(
        project: UUID,
        run_id: UUID,
        request: Request,
        after: str = "0",
        until: str | None = None,
        limit: int = Query(50, ge=1, le=500),
    ):
        access(request, project)
        return rows(app.state.db, project, run_id, after=after, until=until, limit=limit, field="attention")

    @app.get("/api/v2/projects/{project}/runs/{run_id}/attention/export")
    def export(
        project: UUID,
        run_id: UUID,
        request: Request,
        after: str = "0",
        until: str | None = None,
        format: Literal["csv", "jsonl"] = "jsonl",
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        selection(after, until)
        return StreamingResponse(
            export_stream(app.state.db, project, run_id, after=after, until=until, format=format, field="attention"),
            media_type="text/csv; charset=utf-8" if format == "csv" else "application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="attention-{run_id}.{format}"'},
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/attention/events")
    def events(
        project: UUID, run_id: UUID, request: Request, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)
    ):
        access(request, project)
        return next(journal(app.state.db, project, run_id, after=after, limit=limit))

    @app.get("/api/v2/projects/{project}/runs/{run_id}/attention/events/export")
    def event_export(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        app.state.db.get_run(project, run_id)
        return StreamingResponse(
            journal(app.state.db, project, run_id, export=True),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="input-modulations-{run_id}.jsonl"'},
        )
