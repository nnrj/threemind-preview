from uuid import UUID

from fastapi import Query, Request

from . import development


def register_development_routes(app, access):
    prefix = "/api/v2/projects/{project}"

    @app.get(prefix + "/development")
    def sessions(
        project: UUID, request: Request, q: str = Query("", max_length=120), offset: int = Query(0, ge=0, le=100000)
    ):
        access(request, project)
        return development.listing(app.state.db, project, "sessions", q, offset)

    @app.post(prefix + "/development", status_code=201)
    def create(project: UUID, request: Request, body: development.DevelopmentRequest):
        actor = access(request, project, write=True)
        return development.create(app.state.db, project, actor["id"], body, app.state.settings.max_run_seconds)

    @app.get(prefix + "/innate-versions")
    def versions(
        project: UUID, request: Request, q: str = Query("", max_length=120), offset: int = Query(0, ge=0, le=100000)
    ):
        access(request, project)
        return development.listing(app.state.db, project, "versions", q, offset)

    @app.post(prefix + "/innate-versions", status_code=201)
    def register(project: UUID, request: Request, body: development.RegistrationRequest):
        actor = access(request, project, write=True)
        return development.register(app.state.db, project, actor["id"], body)

    @app.get(prefix + "/innate-versions/{version}")
    def detail(project: UUID, version: UUID, request: Request):
        access(request, project)
        return development.version_detail(app.state.db, project, version)

    @app.post(prefix + "/innate-versions/{version}/exports", status_code=202)
    def export(project: UUID, version: UUID, request: Request, body: development.InnateExport):
        access(request, project, write=True)
        with app.state.db.tx(project) as db:
            row = development._version(db, version)
        return app.state.db.enqueue(
            project, "export", {"innate_version_id": str(version), "format": body.format}, row["run_id"]
        )

    @app.get(prefix + "/innate-versions/{version}/exports")
    def exports(project: UUID, version: UUID, request: Request):
        access(request, project)
        with app.state.db.tx(project) as db:
            development._version(db, version)
            return db.execute(
                "SELECT id,status,params,result,error,created_at FROM jobs WHERE kind='export' "
                "AND params->>'innate_version_id'=%s ORDER BY created_at DESC,id DESC LIMIT 30",
                (str(version),),
            ).fetchall()
