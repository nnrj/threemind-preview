"""Durable HTTP outcomes. Pending/unknown outcomes are never blindly executed twice.

Receipts are not a transaction spanning every business service. A crash between
business commit and response commit is explicitly unknown and requires inspection.
"""

import asyncio
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from psycopg.types.json import Jsonb

from .database import Conflict, Forbidden, NotFound
from .operation_catalog import receiptable
from .storage_files import StorageConflict

HEADER = "X-ThreeMind-Request-ID"
MAX_BYTES = 4 * 1024 * 1024


def reserve(database, project, actor, identity, method, path, body):
    digest = hashlib.sha256(
        json.dumps(
            [method, path, body], sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    with database.tx(project) as db:
        inserted = db.execute(
            "INSERT INTO operation_receipts(project_id,actor_id,request_id,fingerprint,method,path,status) "
            "VALUES(%s,%s,%s,%s,%s,%s,'pending') ON CONFLICT DO NOTHING RETURNING request_id",
            (project, actor, identity, digest, method, path),
        ).fetchone()
        if inserted:
            return None
        row = db.execute(
            "SELECT * FROM operation_receipts WHERE project_id=%s AND actor_id=%s AND request_id=%s",
            (project, actor, identity),
        ).fetchone()
        if row["fingerprint"] != digest:
            raise Conflict("请求编号已用于不同操作或参数。请先核对原操作结果。")
        return row


def finish(database, project, actor, identity, response=None, code=None):
    with database.tx(project) as db:
        db.execute(
            "UPDATE operation_receipts SET status=%s,response=%s,response_status=%s,updated_at=now() "
            "WHERE project_id=%s AND actor_id=%s AND request_id=%s",
            ("completed" if response is not None else "unknown", Jsonb(response), code, project, actor, identity),
        )


def register(app, access):
    from . import host_receipts
    from .data_api import host_admin

    @app.get("/api/v2/storage/operation-receipts/{request_id}")
    def host_receipt(request_id: UUID, request: Request):
        actor = host_admin(request)
        return host_receipts.inspect(app.state.db.blobs.storage, actor["id"], request_id)

    @app.get("/api/v2/projects/{project}/operation-receipts/{request_id}")
    def receipt(project: UUID, request_id: UUID, request: Request):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            row = db.execute(
                "SELECT request_id,method,path,status,response_status,response,created_at,updated_at "
                "FROM operation_receipts WHERE project_id=%s AND actor_id=%s AND request_id=%s",
                (project, actor["id"], request_id),
            ).fetchone()
            if row is None:
                raise NotFound("operation receipt")
            return row

    @app.middleware("http")
    async def idempotent(request, call_next):
        identity = request.headers.get(HEADER)
        path = request.url.path
        if not identity or not receiptable(request.method, path):
            return await call_next(request)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "请求回执仅用于有界 JSON 命令；文件请使用分块上传协议。"}, 415)
        try:
            identity = UUID(identity)
            host = path.startswith("/api/v2/storage/")
            project = None if host else UUID(path.split("/")[4])
            if path.endswith("/configuration-template") and "/runs/" in path:
                # The mutation creates a platform template, not a run command.
                # Both grants must be fresh even when replaying an old receipt.
                from . import permissions

                actor = await asyncio.to_thread(access, request, project, action="runs.read")
                await asyncio.to_thread(permissions.require, app.state.db, actor, "system.write")
            else:
                actor = (
                    await asyncio.to_thread(host_admin, request, write=True)
                    if host
                    else await asyncio.to_thread(access, request, project, write=True)
                )
            raw = bytearray()
            async for piece in request.stream():
                raw.extend(piece)
                if len(raw) > MAX_BYTES:
                    return JSONResponse({"detail": "operation body exceeds 4 MiB"}, 413)
            request._body = bytes(raw)
            body = json.loads(raw)
            receipt_path = str(request.url.path) + ("?" + request.url.query if request.url.query else "")
            old = (
                await asyncio.to_thread(
                    host_receipts.reserve,
                    app.state.db.blobs.storage,
                    actor["id"],
                    identity,
                    request.method,
                    receipt_path,
                    body,
                )
                if host
                else await asyncio.to_thread(
                    reserve, app.state.db, project, actor["id"], identity, request.method, receipt_path, body
                )
            )
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, exc.status_code)
        except (ValueError, Conflict, Forbidden, NotFound) as exc:
            return JSONResponse(
                {"detail": str(exc)},
                409 if isinstance(exc, (Conflict, StorageConflict)) else 403 if isinstance(exc, Forbidden) else 422,
            )
        if old:
            if old["status"] == "completed":
                return JSONResponse(
                    old["response"],
                    old["response_status"],
                    headers={HEADER: str(identity), "X-ThreeMind-Replayed": "true"},
                )
            return JSONResponse(
                {
                    "detail": "原操作仍在执行或结果未知；请检查同一编号的回执和对象状态，不要换编号重发。",
                    "request_id": str(identity),
                    "status": old["status"],
                },
                409,
            )
        try:
            response = await call_next(request)
            raw_response = bytearray()
            async for piece in response.body_iterator:
                raw_response.extend(piece)
                if len(raw_response) > MAX_BYTES:
                    raise ValueError("operation response exceeds receipt budget")
            content = json.loads(raw_response)
            if host:
                await asyncio.to_thread(
                    host_receipts.finish,
                    app.state.db.blobs.storage,
                    actor["id"],
                    identity,
                    content,
                    response.status_code,
                )
            else:
                await asyncio.to_thread(
                    finish, app.state.db, project, actor["id"], identity, content, response.status_code
                )
            return JSONResponse(content, response.status_code, headers={HEADER: str(identity)})
        except BaseException:
            # Cancellation/disconnect must leave durable ambiguity instead of permitting duplicate mutation.
            await asyncio.shield(
                asyncio.to_thread(host_receipts.finish, app.state.db.blobs.storage, actor["id"], identity)
                if host
                else asyncio.to_thread(finish, app.state.db, project, actor["id"], identity)
            )
            raise
