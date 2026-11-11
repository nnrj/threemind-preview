"""Public, read-only project documentation routes shared by Lab and the reader."""

from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse


def register_document_routes(app):
    @app.get("/api/v2/history")
    def history(request: Request):
        try:
            return request.app.state.documents.history()
        except KeyError:
            raise HTTPException(404, "history catalogue unavailable")

    @app.get("/api/v2/documents")
    def docs(request: Request):
        try:
            return request.app.state.documents.index()
        except (ValueError, FileNotFoundError):
            raise HTTPException(409, "report revision registry failed validation")

    @app.get("/api/v2/documents/content")
    def doc(path: str, request: Request, revision: int | None = Query(None, ge=1), latest: bool = False):
        if revision is not None and latest:
            raise HTTPException(400, "select a fixed revision or latest, not both")
        try:
            return request.app.state.documents.read(path, revision=revision, latest=latest)
        except KeyError:
            raise HTTPException(404, "document not in the project index")
        except ValueError:
            raise HTTPException(409, "report revision registry failed validation")

    @app.get("/api/v2/documents/versions")
    def versions(path: str, request: Request):
        try:
            return request.app.state.documents.versions(path)
        except KeyError:
            raise HTTPException(404, "report has no registered revision series")
        except ValueError:
            raise HTTPException(409, "report revision registry failed validation")

    @app.get("/api/v2/documents/resource")
    def resource(path: str, request: Request):
        try:
            file = request.app.state.documents.resource(path)
        except KeyError:
            raise HTTPException(404, "resource not in the public documentation")
        except ValueError:
            raise HTTPException(409, "registered document resource failed validation")
        return FileResponse(
            file,
            filename=file.name,
            content_disposition_type="inline"
            if file.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
            else "attachment",
        )
