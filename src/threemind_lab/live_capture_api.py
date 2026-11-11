"""Authenticated live capture controls using bounded, retryable HTTP packets."""

from __future__ import annotations

import asyncio
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Query, Request
from pydantic import Field

from . import live_capture
from .database import NotFound
from .protocols import RunSpec, StrictModel


class OpenCapture(StrictModel):
    session_id: UUID
    name: str = Field(default="连续感官会话", min_length=1, max_length=120)
    kind: Literal["audio", "video", "av"]
    source_clock: dict


class StopCapture(StrictModel):
    reason: Literal["user_stopped", "device_lost", "capture_gap", "queue_overflow", "request_failed", "page_left"] = (
        "user_stopped"
    )


def register_capture_routes(app, access, slots):
    base = "/api/v2/projects/{project}/runs/{run_id}/capture"

    @app.get(base)
    def sessions(
        project: UUID,
        run_id: UUID,
        request: Request,
        limit: int = Query(30, ge=1, le=100),
        offset: int = Query(0, ge=0, le=1000000),
    ):
        access(request, project)
        run = app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            rows = db.execute(
                f"SELECT {live_capture.PUBLIC} FROM capture_sessions WHERE run_id=%s ORDER BY created_at DESC,id LIMIT %s OFFSET %s",
                (run_id, limit + 1, offset),
            ).fetchall()
        spec = RunSpec(**run["spec"])
        return {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "offset": offset,
            "configuration": live_capture.configuration(spec),
        }

    @app.post(base, status_code=201)
    def open_capture(project: UUID, run_id: UUID, body: OpenCapture, request: Request):
        actor = access(request, project, write=True)
        return live_capture.create(app.state.db, project, run_id, actor, **body.model_dump())

    @app.post(base + "/{session_id}/stop")
    def close_capture(project: UUID, run_id: UUID, session_id: UUID, body: StopCapture, request: Request):
        access(request, project, write=True)
        app.state.db.get_run(project, run_id)
        return live_capture.stop(app.state.db, project, run_id, session_id, reason=body.reason)

    @app.get(base + "/{session_id}/packets")
    def packets(
        project: UUID,
        run_id: UUID,
        session_id: UUID,
        request: Request,
        after: int = Query(-1, ge=-1),
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            session = db.execute(
                f"SELECT {live_capture.PUBLIC} FROM capture_sessions WHERE id=%s AND run_id=%s", (session_id, run_id)
            ).fetchone()
            if session is None:
                raise NotFound()
            rows = db.execute(
                "SELECT p.sequence,p.envelope_id,p.sha256,p.metadata,p.created_at,e.status,e.frame_count,e.delivered_count,e.error,e.processed_revision "
                "FROM capture_packets p JOIN input_envelopes e ON e.id=p.envelope_id WHERE p.session_id=%s AND p.run_id=%s AND p.sequence>%s ORDER BY p.sequence LIMIT %s",
                (session_id, run_id, after, limit + 1),
            ).fetchall()
        return {
            "session": session,
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next": rows[min(limit, len(rows)) - 1]["sequence"] if rows else None,
        }

    @app.post(base + "/{session_id}/packets", status_code=202)
    async def receive(project: UUID, run_id: UUID, session_id: UUID, request: Request):
        def authorize_packet():
            actor = access(request, project, write=True)
            spec = RunSpec(**app.state.db.get_run(project, run_id)["spec"])
            return actor, spec.live_capture.max_packet_bytes

        # Pool/SQL waits must not stop the event loop that receives other packet
        # bodies or streams output. Admission still rechecks state in its transaction.
        actor, limit = await asyncio.to_thread(authorize_packet)
        if request.headers.get("content-length") and int(request.headers["content-length"]) > limit:
            raise HTTPException(413, "采集块超过当前上限。")
        if slots.locked():
            raise HTTPException(429, "媒体处理槽位已满，请重试同一序号的原始采集块。")
        await slots.acquire()
        job = None
        try:
            raw = bytearray()
            try:
                async with asyncio.timeout(10):
                    async for part in request.stream():
                        if len(raw) + len(part) > limit:
                            raise HTTPException(413, "采集块超过当前上限。")
                        raw.extend(part)
            except TimeoutError as exc:
                raise HTTPException(408, "采集块传输超时，未确认接收。") from exc
            job = asyncio.create_task(
                asyncio.to_thread(
                    live_capture.accept_packet, app.state.db, project, run_id, session_id, actor, bytes(raw)
                )
            )
            del raw
            job.add_done_callback(lambda done: slots.release())
            return await asyncio.shield(job)
        finally:
            if job is None:
                slots.release()
