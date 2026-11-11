import json
from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field

from threemind_core.energy import supply_payload

from . import ports
from .database import NotFound
from .protocols import StrictModel
from .resource_evidence import export_stream, rows, selection


class SupplyRequest(StrictModel):
    request_id: UUID
    amount: float = Field(ge=0, le=1e12, strict=True)
    delay_us: int = Field(default=0, ge=0, le=10**12, strict=True)
    source: str = Field(default="manual-energy-port", min_length=1, max_length=128)


def submit(database, project, run_id, actor_id, request: SupplyRequest):
    return ports.submit(
        database,
        project,
        run_id,
        actor_id,
        kind="energy_supply",
        request_id=request.request_id,
        payload=supply_payload(request.amount, request.source) | {"delay_us": request.delay_us},
        required_flag="energy_simulation_enabled",
    )


def event_export(database, project, run_id, after="0", until=None):
    start, end = selection(after, until)
    with database.tx(project, repeatable=True) as db:
        run = db.execute("SELECT revision,state_hash FROM runs WHERE id=%s", (run_id,)).fetchone()
        if run is None:
            raise NotFound("run")
        yield (
            json.dumps(
                {
                    "selection": {
                        "run_id": str(run_id),
                        **run,
                        "after_us": str(start),
                        "until_us": str(end) if end is not None else None,
                    }
                },
                ensure_ascii=False,
            )
            + "\n"
        ).encode()
        with db.cursor(name="energy_events") as cursor:
            cursor.execute(
                "SELECT event_key,time_us,kind,payload,commit_revision FROM events WHERE run_id=%s AND kind IN ('energy_scheduled','energy_delivered','energy_supply') AND time_us>=%s AND (%s::numeric IS NULL OR time_us<=%s) ORDER BY time_us,id",
                (run_id, start, end, end),
            )
            cursor.itersize = 500
            for row in cursor:
                row["time_us"] = str(row["time_us"])
                yield (json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode()


def register_energy_routes(app, access):
    @app.post("/api/v2/projects/{project}/runs/{run_id}/energy/supply", status_code=202)
    def supply(project: UUID, run_id: UUID, body: SupplyRequest, request: Request):
        user = access(request, project, write=True)
        return submit(app.state.db, project, run_id, user["id"], body)

    @app.get("/api/v2/projects/{project}/runs/{run_id}/energy")
    def evidence(
        project: UUID,
        run_id: UUID,
        request: Request,
        after: str = "0",
        until: str | None = None,
        limit: int = Query(50, ge=1, le=500),
    ):
        access(request, project)
        result = rows(app.state.db, project, run_id, after=after, until=until, limit=limit, field="energy")
        return result

    @app.get("/api/v2/projects/{project}/runs/{run_id}/energy/export")
    def export(
        project: UUID,
        run_id: UUID,
        request: Request,
        after: str = "0",
        until: str | None = None,
        format: Literal["jsonl", "csv"] = "jsonl",
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        selection(after, until)
        return StreamingResponse(
            export_stream(app.state.db, project, run_id, after=after, until=until, format=format, field="energy"),
            media_type="text/csv; charset=utf-8" if format == "csv" else "application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="energy-{run_id}.{format}"'},
        )

    @app.get("/api/v2/projects/{project}/runs/{run_id}/energy/events/export")
    def events(project: UUID, run_id: UUID, request: Request, after: str = "0", until: str | None = None):
        access(request, project)
        app.state.db.get_run(project, run_id)
        selection(after, until)
        return StreamingResponse(
            event_export(app.state.db, project, run_id, after, until),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="energy-events-{run_id}.jsonl"'},
        )
