from uuid import UUID

from fastapi import Query, Request

from threemind_runtime.calibration import CalibrationProtocol
from threemind_runtime.temporal_probe import TemporalProbeProtocol

from . import calibration
from .protocols import StrictModel


class ProbeRequest(StrictModel):
    operation_id: UUID
    checkpoint_id: UUID | None = None
    protocol: CalibrationProtocol | TemporalProbeProtocol


class TemporalValidation(StrictModel):
    protocol: TemporalProbeProtocol


def register_calibration_routes(app, access):
    prefix = "/api/v2/projects/{project}/runs/{run_id}/calibrations"

    @app.post(prefix + "/validate")
    def validate(project: UUID, run_id: UUID, body: TemporalValidation, request: Request):
        access(request, project)
        app.state.db.get_run(project, run_id)
        return body.model_dump(mode="json", exclude_unset=True)

    @app.get("/api/v2/projects/{project}/storage-audit")
    def storage(project: UUID, request: Request, offset: int = Query(0, ge=0, le=100000)):
        from .storage_audit import scan

        actor = access(request, project)
        from . import permissions
        return scan(app.state.db, project, actor["id"], offset=offset,
                    include_database=permissions.allows(app.state.db, actor, "data.read"))

    @app.post(prefix, status_code=202)
    def start(project: UUID, run_id: UUID, body: ProbeRequest, request: Request):
        actor = access(request, project, write=True)
        return calibration.request(app.state.db, project, run_id, actor["id"], **body.model_dump(exclude_unset=True))

    @app.get(prefix)
    def listing(
        project: UUID, run_id: UUID, request: Request, offset: int = Query(0, ge=0, le=100000), mode: str | None = None
    ):
        access(request, project)
        if mode not in (None, "fixed-window", "temporal"):
            raise ValueError("unknown measurement mode")
        with app.state.db.tx(project) as db:
            rows = db.execute(
                "SELECT c.id,c.checkpoint_id,c.source_hash,c.created_at,j.status,j.error FROM probe_calibrations c "
                "JOIN jobs j ON j.id=c.job_id WHERE c.run_id=%s "
                "AND (%s::text IS NULL OR COALESCE(c.protocol->>'mode','fixed-window')=%s) "
                "ORDER BY c.created_at DESC,c.id DESC LIMIT 21 OFFSET %s",
                (run_id, mode, mode, offset),
            ).fetchall()
        return {"rows": rows[:20], "more": len(rows) > 20}

    @app.get("/api/v2/projects/{project}/calibrations/{ident}")
    def detail(project: UUID, ident: UUID, request: Request):
        access(request, project)
        return calibration.detail(app.state.db, project, ident)

    @app.get("/api/v2/projects/{project}/calibrations/{ident}/result")
    def result(project: UUID, ident: UUID, request: Request):
        access(request, project)
        return calibration.result(app.state.db, project, ident)
