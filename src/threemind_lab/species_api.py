from uuid import UUID

from fastapi import HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from . import species_library as library


def register(app, access):
    base = '/api/v2/projects/{project}/species'

    @app.get(base)
    def listing(project: UUID, request: Request, q: str = Query('', max_length=160),
                offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
        access(request, project)
        return library.listing(app.state.db, project, q, offset, limit)

    @app.post(base, status_code=201)
    async def upload(project: UUID, request: Request, file: UploadFile):
        actor = access(request, project, write=True)
        raw = await file.read(library.MAX_BYTES + 1)
        try:
            return library.put(app.state.db, project, actor['id'], raw)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get(base + '/{identity}')
    def detail(project: UUID, identity: UUID, request: Request):
        access(request, project)
        return library.get(app.state.db, project, identity)

    @app.get(base + '/{identity}/download')
    def download(project: UUID, identity: UUID, request: Request):
        access(request, project)
        return Response(library.get(app.state.db, project, identity, raw=True),
                        media_type='application/zip',
                        headers={'Content-Disposition': f'attachment; filename="species-{identity}.tmspecies"'})
