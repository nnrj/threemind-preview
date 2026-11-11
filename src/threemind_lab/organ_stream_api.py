"""Bounded committed-output monitor. Browser playback is never an input port."""

import asyncio
import json
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from .database import Forbidden, NotFound
from .organs import latest


def register_organ_stream(app, access):
    slots = asyncio.Semaphore(32)

    @app.get("/api/v2/projects/{project}/runs/{run_id}/organs/monitor")
    async def monitor(project: UUID, run_id: UUID, request: Request):
        origin = request.headers.get("origin")
        if origin and origin not in app.state.settings.origins:
            raise HTTPException(403, "origin is not allowed")
        if slots.locked():
            raise HTTPException(429, "输出查看连接已满，请稍后重试。")

        def read(cursor):
            # Recheck revocation/session expiry during a long-lived connection.
            access(request, project)
            return latest(app.state.db, project, run_id, cursor)

        await slots.acquire()
        try:
            initial = await asyncio.to_thread(read, 0)
        except BaseException:
            slots.release()
            raise

        async def messages():
            value, cursor = initial, 0
            try:
                while not await request.is_disconnected():
                    yield "event: output\ndata: " + json.dumps(value, default=str, separators=(",", ":")) + "\n\n"
                    cursor = value["cursor"]
                    if value["status"] not in ("running", "queued"):
                        yield "event: ended\ndata: " + json.dumps({"reason": value["status"]}) + "\n\n"
                        break
                    await asyncio.sleep(0.25)
                    try:
                        value = await asyncio.to_thread(read, cursor)
                    except (HTTPException, Forbidden, NotFound):
                        yield 'event: ended\ndata: {"reason":"access_unavailable"}\n\n'
                        break
            finally:
                slots.release()

        return StreamingResponse(
            messages(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
        )
