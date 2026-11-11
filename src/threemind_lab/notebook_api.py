from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Query, Request, Response
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from . import notebooks
from .note_schema import CollectionEdit, NoteEdit
from .protocols import StrictModel


class Archive(StrictModel):
    expected_revision: int = Field(ge=1, strict=True)
    archived: bool = Field(strict=True)
    operation_id: UUID


def register_notebook_routes(app, access, decode_slots):
    prefix = "/api/v2/projects/{project}"

    @app.get(prefix + "/note-collections")
    def collections(project: UUID, request: Request, archived: bool = False):
        actor = access(request, project)
        return notebooks.collections(app.state.db, project, actor["id"], archived=archived)

    @app.post(prefix + "/note-collections/default")
    def default(project: UUID, request: Request):
        actor = access(request, project, write=True)
        return notebooks.ensure_default(app.state.db, project, actor["id"])

    @app.put(prefix + "/note-collections/{collection}")
    def save_collection(project: UUID, collection: UUID, request: Request, body: CollectionEdit):
        actor = access(request, project, write=True)
        return notebooks.save_collection(app.state.db, project, actor["id"], collection, body)

    @app.post(prefix + "/note-collections/{collection}/archive")
    def archive_collection(project: UUID, collection: UUID, request: Request, body: Archive):
        actor = access(request, project, write=True)
        return notebooks.archive_collection(
            app.state.db, project, actor["id"], collection, body.expected_revision, body.archived
        )

    @app.get(prefix + "/notes")
    def notes(
        project: UUID,
        request: Request,
        kind: Literal["draft", "note"] = "draft",
        collection: UUID | None = None,
        query: str = Query("", max_length=200),
        sort: Literal["updated", "created", "title"] = "updated",
        offset: int = Query(0, ge=0, le=100000),
        archived: bool = False,
        uncategorized: bool = False,
    ):
        actor = access(request, project)
        return notebooks.list_notes(
            app.state.db,
            project,
            actor["id"],
            kind=kind,
            collection=collection,
            query=query,
            sort=sort,
            offset=offset,
            archived=archived,
            uncategorized=uncategorized,
        )

    @app.get(prefix + "/notes/{note}")
    def note(project: UUID, note: UUID, request: Request, revision: int | None = Query(None, ge=1)):
        actor = access(request, project)
        return notebooks.note(app.state.db, project, actor["id"], note, revision)

    @app.put(prefix + "/notes/{note}")
    def save(project: UUID, note: UUID, request: Request, body: NoteEdit):
        actor = access(request, project, write=True)
        return notebooks.save_note(app.state.db, project, actor["id"], note, body)

    @app.get(prefix + "/notes/{note}/versions")
    def versions(project: UUID, note: UUID, request: Request, before: int | None = Query(None, ge=1)):
        actor = access(request, project)
        return notebooks.versions(app.state.db, project, actor["id"], note, before)

    @app.post(prefix + "/notes/{note}/archive")
    def archive_note(project: UUID, note: UUID, request: Request, body: Archive):
        actor = access(request, project, write=True)
        return notebooks.archive_note(
            app.state.db, project, actor["id"], note, body.expected_revision, body.archived, body.operation_id
        )

    @app.get(prefix + "/note-assets")
    def assets(project: UUID, request: Request, offset: int = Query(0, ge=0, le=100000)):
        actor = access(request, project)
        return notebooks.assets(app.state.db, project, actor["id"], offset)

    @app.put(prefix + "/note-assets/{asset}")
    async def upload(
        project: UUID, asset: UUID, request: Request, filename: str = Query("image", min_length=1, max_length=200)
    ):
        actor = await run_in_threadpool(access, request, project, write=True)
        if decode_slots.locked():
            raise HTTPException(429, "image processing slots are busy; retry shortly")
        await decode_slots.acquire()
        try:
            content = bytearray()
            async for part in request.stream():
                if len(content) + len(part) > 8 * 1024 * 1024:
                    raise HTTPException(413, "note image exceeds 8 MiB")
                content.extend(part)
            return await run_in_threadpool(
                notebooks.save_asset, app.state.db, project, actor["id"], asset, filename, bytes(content)
            )
        finally:
            decode_slots.release()

    @app.get(prefix + "/note-assets/{asset}")
    def asset(project: UUID, asset: UUID, request: Request):
        actor = access(request, project)
        row = notebooks.asset(app.state.db, project, actor["id"], asset)
        return Response(bytes(row["content"]), media_type=row["mime"], headers={"Cache-Control": "no-store"})

    @app.delete(prefix + "/note-assets/{asset}")
    def delete_asset(project: UUID, asset: UUID, request: Request):
        actor = access(request, project, write=True)
        return notebooks.delete_asset(app.state.db, project, actor["id"], asset)
