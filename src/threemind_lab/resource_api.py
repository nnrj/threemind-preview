from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse

from .resource_evidence import export_stream, rows, selection


def register_resource_routes(app, access):
    @app.get("/api/v2/projects/{project}/runs/{run_id}/resources")
    def resource_rows(
        project: UUID,
        run_id: UUID,
        request: Request,
        after: str = "0",
        until: str | None = None,
        limit: int = Query(50, ge=1, le=500),
    ):
        access(request, project)
        return rows(app.state.db, project, run_id, after=after, until=until, limit=limit)

    @app.get("/api/v2/projects/{project}/runs/{run_id}/resources/export")
    def resource_export(
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
            export_stream(app.state.db, project, run_id, after=after, until=until, format=format),
            media_type="text/csv; charset=utf-8" if format == "csv" else "application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="resources-{run_id}.{format}"'},
        )
