from typing import Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import StreamingResponse

from . import report_shares
from .database import NotFound


def register_share_routes(app, access):
    prefix = "/api/v2/projects/{project}/research-documents/{document}/shares"

    @app.post(prefix, status_code=201)
    def create(project: UUID, document: UUID, request: Request, body: report_shares.ShareRequest):
        actor = access(request, project, owner=True)
        return report_shares.create(app.state.db, project, actor["id"], document, body)

    @app.get(prefix)
    def listing(project: UUID, document: UUID, request: Request, offset: int = Query(0, ge=0, le=100000)):
        actor = access(request, project, owner=True)
        return report_shares.listing(app.state.db, project, actor["id"], document, offset)

    @app.post(prefix + "/{share}/revoke")
    def revoke(project: UUID, document: UUID, share: UUID, request: Request):
        actor = access(request, project, owner=True)
        return report_shares.revoke(app.state.db, project, actor["id"], document, share)

    @app.get("/api/v2/shared-documents/{share}")
    def public(share: UUID):
        return report_shares.public_metadata(app.state.db, share)

    @app.get("/api/v2/shared-documents/{share}/files/{kind}")
    def download(share: UUID, kind: Literal["body", "bundle"]):
        publication = report_shares.resolve(app.state.db, share)
        metadata = publication["metadata"][kind]
        if metadata is None:
            raise NotFound()
        suffix = "html" if kind == "body" else "zip"
        return StreamingResponse(
            report_shares.file_stream(app.state.db, publication, kind),
            media_type=metadata["media_type"],
            headers={
                "Content-Disposition": f'attachment; filename="threemind-share-{share}.{suffix}"',
                "Content-Length": str(metadata["bytes"]),
                "X-Content-SHA256": metadata["sha256"],
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )
