"""Project-scoped bounded upload transport; admission still uses InputBus."""

import asyncio
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Query, Request
from pydantic import Field

from . import media_uploads as store
from .media_store import CHUNK
from .protocols import StrictModel


class StartUpload(StrictModel):
    request_id: UUID
    kind: Literal["audio", "image", "video"]
    filename: str = Field(min_length=1, max_length=255)
    byte_length: int = Field(gt=0, le=8192 * CHUNK, strict=True)
    intensity: float = Field(default=1.0, ge=0, le=100, strict=True, allow_inf_nan=False)
    delay_us: int = Field(default=0, ge=0, le=10**12, strict=True)


def register_media_upload_routes(app, access, decode_slots):
    prefix = "/api/v2/projects/{project}/runs/{run_id}/media-uploads"
    transfer_slots = asyncio.Semaphore(app.state.settings.max_media_uploads * 2)

    @app.get(prefix)
    def uploads(
        project: UUID,
        run_id: UUID,
        request: Request,
        state: Literal["unfinished", "all"] = "unfinished",
        before: UUID | None = None,
        limit: int = Query(20, ge=1, le=100),
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            # Cleanup only project staging whose decoder lock is no longer held.
            store.expire(db, project)
            anchor = store.find(db, run_id, before) if before else None
            rows = db.execute(
                """SELECT * FROM media_uploads WHERE run_id=%s
                                 AND (%s OR status=ANY(%s)) AND (%s::timestamptz IS NULL OR (created_at,id)<(%s,%s))
                                 ORDER BY created_at DESC,id DESC LIMIT %s""",
                (
                    run_id,
                    state == "all",
                    list(store.ACTIVE),
                    anchor["created_at"] if anchor else None,
                    anchor["created_at"] if anchor else None,
                    before,
                    limit + 1,
                ),
            ).fetchall()
        return {
            "rows": [store.public(row) for row in rows[:limit]],
            "next": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
            "limits": {
                "chunk_bytes": CHUNK,
                "project_active_uploads": app.state.settings.max_media_uploads,
                "project_staged_bytes": str(app.state.settings.max_staged_media_bytes),
                "expires_hours": 24,
            },
        }

    @app.post(prefix, status_code=201)
    def begin(project: UUID, run_id: UUID, request: Request, body: StartUpload):
        actor = access(request, project, write=True)
        return store.begin(
            app.state.db,
            app.state.settings,
            project,
            run_id,
            actor,
            body.request_id,
            body.model_dump(exclude={"request_id", "byte_length"}),
            body.byte_length,
        )

    @app.get(prefix + "/{upload}")
    def status(project: UUID, run_id: UUID, upload: UUID, request: Request):
        access(request, project)
        return store.status(app.state.db, project, run_id, upload)

    @app.get(prefix + "/{upload}/chunks")
    def chunks(
        project: UUID,
        run_id: UUID,
        upload: UUID,
        request: Request,
        after: int = Query(-1, ge=-1),
        limit: int = Query(256, ge=1, le=256),
    ):
        access(request, project)
        with app.state.db.tx(project) as db:
            store.find(db, run_id, upload)
            rows = db.execute(
                """SELECT chunk_index,sha256,octet_length(body) AS byte_length FROM media_upload_chunks
                                 WHERE upload_id=%s AND chunk_index>%s ORDER BY chunk_index LIMIT %s""",
                (upload, after, limit + 1),
            ).fetchall()
        return {"rows": rows[:limit], "next": rows[limit - 1]["chunk_index"] if len(rows) > limit else None}

    @app.put(prefix + "/{upload}/chunks/{index}")
    async def put(
        project: UUID,
        run_id: UUID,
        upload: UUID,
        index: int,
        request: Request,
        sha256: str = Query(pattern=r"^[0-9a-f]{64}$"),
    ):
        actor = access(request, project, write=True)
        if index < 0:
            raise HTTPException(422, "分块序号不能为负。")
        store.status(app.state.db, project, run_id, upload)
        declared = request.headers.get("content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > CHUNK):
            raise HTTPException(413, "单块最多 1 MiB。")
        if transfer_slots.locked():
            raise HTTPException(429, "传输槽位已满，请稍后重试。")
        async with transfer_slots:
            raw = bytearray()
            try:
                async with asyncio.timeout(60):
                    async for part in request.stream():
                        if len(raw) + len(part) > CHUNK:
                            raise HTTPException(413, "分块超过 1 MiB，当前块未接收。")
                        raw.extend(part)
            except TimeoutError as error:
                raise HTTPException(408, "当前分块接收超时，可以继续上传。") from error
            return await asyncio.to_thread(
                store.put, app.state.db, project, run_id, upload, actor, index, bytes(raw), sha256
            )

    @app.post(prefix + "/{upload}/finalize", status_code=202)
    async def finalize(project: UUID, run_id: UUID, upload: UUID, request: Request):
        actor = access(request, project, write=True)
        current = store.status(app.state.db, project, run_id, upload)
        if current["status"] == "accepted":
            return current["receipt"]
        if decode_slots.locked():
            raise HTTPException(429, "媒体解码槽位已满；原件分块已保留，可稍后重试。")
        await decode_slots.acquire()
        try:
            job = asyncio.create_task(asyncio.to_thread(store.finalize, app.state.db, project, run_id, upload, actor))
        except BaseException:
            decode_slots.release()
            raise

        def finished(done):
            decode_slots.release()
            if not done.cancelled():
                done.exception()  # Retrieve errors even when the HTTP client disconnected.

        job.add_done_callback(finished)
        return await asyncio.shield(job)

    @app.delete(prefix + "/{upload}")
    def cancel(project: UUID, run_id: UUID, upload: UUID, request: Request):
        actor = access(request, project, write=True)
        return store.cancel(app.state.db, project, run_id, upload, actor)
