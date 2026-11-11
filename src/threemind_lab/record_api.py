"""Transport only: every writer uses ResearchRecords and its atomic receipts."""

from datetime import date
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse
from pydantic import Field

from . import auth
from .protocols import StrictModel
from .record_schema import (
    AppendRecord,
    ApplyBackfill,
    AttachRecord,
    BackfillPlan,
    FinalizeRecord,
    RegisterRecord,
    SaveRecordText,
)
from .research_records import ResearchRecords


class ResourceGrant(StrictModel):
    project_id: UUID
    resource_id: str = Field(min_length=1, max_length=160)


def register_record_routes(app, access):
    prefix = '/api/v2/projects/{project}/records'

    def service():
        return ResearchRecords(app.state.db)

    @app.get('/api/v2/research-experiments')
    def records(request: Request, project: UUID | None = None, query: str = Query('', max_length=200),
                kernel: str = Query('', max_length=200), executor: str = '', status: str = '', coverage: str = '',
                classification: str = '', from_date: date | None = None, through_date: date | None = None,
                offset: int = Query(0, ge=0, le=100000), limit: int = Query(50, ge=1, le=200)):
        actor = auth.identity(request)
        return service().list(actor, project=project, query=query, kernel=kernel, executor=executor,
                              status=status, coverage=coverage, classification=classification,
                              from_date=from_date, through_date=through_date, offset=offset, limit=limit)

    @app.post(prefix)
    def register(project: UUID, request: Request, body: RegisterRecord):
        return service().register(project, access(request, project, write=True), body)

    @app.get(prefix + '/receipts/{request_id}')
    def receipt(project: UUID, request_id: UUID, request: Request):
        return service().receipt(project, access(request, project), request_id)

    @app.post(prefix + '/backfill-plans')
    def preview_backfill(project: UUID, request: Request, body: BackfillPlan):
        return service().backfill_plan(project, access(request, project, write=True), body)

    @app.post(prefix + '/backfill-plans/{batch}/apply')
    def apply_backfill(project: UUID, batch: UUID, request: Request, body: ApplyBackfill):
        return service().backfill_apply(project, access(request, project, write=True), batch, body)

    @app.get(prefix + '/{experiment}')
    def detail(project: UUID, experiment: UUID, request: Request):
        return service().detail(project, access(request, project), experiment)

    @app.get(prefix + '/{experiment}/entries')
    def entries(project: UUID, experiment: UUID, request: Request, kind: str | None = None,
                offset: int = Query(0, ge=0, le=100000), limit: int = Query(50, ge=1, le=200)):
        return service().entries(project, access(request, project), experiment, kind=kind, offset=offset, limit=limit)

    @app.post(prefix + '/{experiment}/entries')
    def append(project: UUID, experiment: UUID, request: Request, body: AppendRecord):
        return service().append(project, access(request, project, write=True), experiment, body)

    @app.get(prefix + '/{experiment}/evidence')
    def evidence(project: UUID, experiment: UUID, request: Request,
                 offset: int = Query(0, ge=0, le=100000), limit: int = Query(50, ge=1, le=200)):
        return service().evidence(project, access(request, project), experiment, offset=offset, limit=limit)

    @app.post(prefix + '/{experiment}/evidence')
    def attach(project: UUID, experiment: UUID, request: Request, body: AttachRecord):
        return service().attach(project, access(request, project, write=True), experiment, body)

    @app.post(prefix + '/{experiment}/texts')
    def save_text(project: UUID, experiment: UUID, request: Request, body: SaveRecordText):
        return service().save_text(project, access(request, project, write=True), experiment, body)

    @app.get(prefix + '/{experiment}/verify')
    def verify(project: UUID, experiment: UUID, request: Request, hashes: bool = False):
        return service().verify(project, access(request, project), experiment, hashes=hashes)

    @app.post(prefix + '/{experiment}/finalize')
    def finalize(project: UUID, experiment: UUID, request: Request, body: FinalizeRecord):
        return service().finalize(project, access(request, project, write=True), experiment, body)

    @app.get('/api/v2/projects/{project}/record-evidence/{evidence}/preview')
    def evidence_preview(project: UUID, evidence: UUID, request: Request,
                         offset: int = Query(0, ge=0, le=100000), limit: int = Query(50, ge=1, le=100)):
        return service().preview(project, access(request, project), evidence, offset=offset, limit=limit)

    @app.get('/api/v2/projects/{project}/record-evidence/{evidence}/content')
    def evidence_content(project: UUID, evidence: UUID, request: Request):
        actor = access(request, project)
        row = service().evidence_row(project, actor, evidence)
        if row['locator']['kind'] == 'missing':
            from .database import NotFound
            raise NotFound(row['locator']['reason'])
        headers = {'Content-Disposition': f'attachment; filename="{evidence}.bin"'}
        if row['byte_count'] is not None:
            headers['Content-Length'] = str(row['byte_count'])
        return StreamingResponse(service().chunks(project, actor, evidence), media_type='application/octet-stream', headers=headers)

    @app.post('/api/v2/storage/record-evidence-grants')
    def grant(request: Request, body: ResourceGrant):
        from .data_api import host_admin
        return service().grant_resource(body.project_id, host_admin(request, write=True), body.resource_id)
