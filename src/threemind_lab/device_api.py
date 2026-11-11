"""Platform management and a separate, bounded device HTTP/WebSocket interface."""

import asyncio
import json
import threading
from contextlib import suppress
from uuid import UUID

from fastapi import HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from threemind_core.spec import timestamp
from threemind_runtime.network import MAX_MESSAGE_BYTES, PROTOCOL, read_message, sequence
from threemind_runtime.network_wiring import read_wiring

from . import devices
from .database import Conflict, Forbidden, NotFound


def credential(request):
    value = request.headers.get("authorization", "")
    if not value.startswith("Bearer ") or len(value) > 140:
        raise Forbidden("请使用设备独立的 Authorization: Bearer 凭据。")
    return value[7:]


async def bounded_body(request):
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_MESSAGE_BYTES:
            raise HTTPException(413, "network message exceeds 128 KiB")
        body.extend(chunk)
    return bytes(body)


def hello(database, project, run_id, device_id, token, message):
    if (
        message.get("type") != "hello"
        or set(message) - {"protocol", "type", "token", "session_id", "source_clock"}
        or not isinstance(message.get("source_clock"), dict)
    ):
        raise ValueError("hello requires source_clock and optional session_id")
    session = devices.open_session(
        database, project, run_id, device_id, token, message["source_clock"], message.get("session_id")
    )
    return {
        "protocol": PROTOCOL,
        "type": "ready",
        "session": devices.public_session(session),
        "max_message_bytes": MAX_MESSAGE_BYTES,
        "timestamps": "integer microseconds encoded as decimal strings",
    }


def snapshot(database, project, run_id, device_id, token, session_id, after_revision=None):
    with database.tx(project) as db:
        # The run lock also fences concurrent projection commits, so all rows
        # belong to exactly this revision without reconstructing a model image.
        run = devices.lock_run(db, run_id)
        device = devices.authenticate(db, run_id, device_id, token, capability="output", charge=True)
        devices.session_row(db, run_id, device, session_id)
        config = device["configuration"]
        nodes = db.execute(
            "SELECT id,activation,inhibition,stability,direct,associative FROM nodes WHERE run_id=%s ORDER BY id LIMIT %s",
            (run_id, config["output_nodes"]),
        ).fetchall()
        edges = (
            db.execute(
                "SELECT source,target,weight,stability FROM edges WHERE run_id=%s AND source=ANY(%s) AND target=ANY(%s) ORDER BY source,target LIMIT %s",
                (run_id, [n["id"] for n in nodes], [n["id"] for n in nodes], config["output_edges"]),
            ).fetchall()
            if nodes
            else []
        )
    result = {
        "protocol": PROTOCOL,
        "type": "output",
        "run_id": str(run_id),
        "revision": str(run["revision"]),
        "time_us": str(run["time_us"]),
        "state_hash": run["state_hash"],
        "metrics": run["metrics"],
        "nodes": nodes,
        "edges": edges,
        "total_nodes": run["metrics"].get("nodes", 0),
        "total_edges": run["metrics"].get("edges", 0),
        "complete": False,
        "skipped_revisions": max(0, run["revision"] - after_revision - 1) if after_revision is not None else None,
        "scope": "latest committed anonymous projection; not a complete event stream",
    }
    # Numeric fields have bounded size, but configured limits may still exceed
    # the transport budget. Declare truncation instead of dropping a socket.
    while len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode()) > MAX_MESSAGE_BYTES:
        if edges:
            del edges[len(edges) // 2 :]
        elif nodes:
            del nodes[len(nodes) // 2 :]
        else:
            raise ValueError("snapshot metadata exceeds the transport budget")
    result["complete"] = len(nodes) == result["total_nodes"] and len(edges) == result["total_edges"]
    return result


def packet_history(db, run_id, device_id, *, session_id=None, after=-1, limit=30):
    # Session is the pagination domain; otherwise sequence zero in two sessions
    # would be indistinguishable. UI first chooses a concrete session.
    if session_id is None:
        raise ValueError("请选择设备会话。")
    found = db.execute(
        "SELECT id FROM device_sessions WHERE id=%s AND run_id=%s AND device_id=%s", (session_id, run_id, device_id)
    ).fetchone()
    if found is None:
        raise NotFound("device session")
    rows = db.execute(
        """SELECT p.sequence,p.kind,p.sha256,p.receipt,p.envelope_id,p.command_id,p.created_at,
           e.status AS delivery_status,e.error,e.frame_count,e.delivered_count,e.filtered_count,
           e.processed_revision,e.last_delivery_us,
           (SELECT v.payload FROM events v WHERE v.run_id=p.run_id AND v.event_key='port-command:'||p.command_id::text LIMIT 1) AS port_outcome
           FROM device_packets p LEFT JOIN input_envelopes e ON e.id=p.envelope_id
           WHERE p.run_id=%s AND p.session_id=%s AND p.sequence>%s ORDER BY p.sequence LIMIT %s""",
        (run_id, session_id, after, limit + 1),
    ).fetchall()
    for row in rows:
        row["sequence"] = str(row["sequence"])
        row["command_id"] = str(row["command_id"])
    return {
        "rows": rows[:limit],
        "more": len(rows) > limit,
        "next": rows[limit - 1]["sequence"] if len(rows) >= limit else str(after),
    }


def register_device_routes(app, access):
    platform = "/api/v2/projects/{project}/runs/{run_id}/devices"
    network = "/api/v2/network/{project}/{run_id}/{device_id}"
    slots = threading.BoundedSemaphore(32)

    @app.get(platform)
    def listing(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        app.state.db.get_run(project, run_id)
        with app.state.db.tx(project) as db:
            return [
                devices.public(r)
                for r in db.execute(
                    "SELECT * FROM device_bindings WHERE run_id=%s ORDER BY created_at,id", (run_id,)
                ).fetchall()
            ]

    @app.post(platform, status_code=201)
    def create(project: UUID, run_id: UUID, request: Request, body: devices.CreateDevice):
        user = access(request, project, write=True)
        return devices.create(app.state.db, project, run_id, user["id"], body)

    @app.post(platform + "/wiring/validate")
    async def validate_wiring(project: UUID, run_id: UUID, request: Request):
        access(request, project)
        run = await run_in_threadpool(app.state.db.get_run, project, run_id)
        wiring = read_wiring(await bounded_body(request))
        devices.check_wiring_seed(wiring, run)
        return {"valid": True, "wiring": wiring}

    @app.get(platform + "/{device_id}/wiring")
    def wiring(project: UUID, run_id: UUID, device_id: UUID, request: Request):
        access(request, project)
        value = devices.export_wiring(app.state.db, project, run_id, device_id)
        return JSONResponse(
            value,
            headers={
                "Content-Disposition": f'attachment; filename="network-{value["wiring_id"]}.wiring.json"',
                "Cache-Control": "private, no-store",
            },
        )

    @app.put(platform + "/{device_id}")
    def edit(project: UUID, run_id: UUID, device_id: UUID, request: Request, body: devices.EditDevice):
        user = access(request, project, write=True)
        return devices.edit(app.state.db, project, run_id, device_id, user["id"], body)

    @app.post(platform + "/{device_id}/rotate")
    def rotate(project: UUID, run_id: UUID, device_id: UUID, request: Request):
        user = access(request, project, write=True)
        return devices.edit(app.state.db, project, run_id, device_id, user["id"], rotate=True)

    @app.get(platform + "/{device_id}/sessions")
    def sessions(
        project: UUID,
        run_id: UUID,
        device_id: UUID,
        request: Request,
        before: str | None = None,
        limit: int = Query(20, ge=1, le=100),
    ):
        access(request, project)
        with app.state.db.tx(project) as db:
            # Cursor resolves the original database timestamp, preserving all
            # microseconds even when a browser only displays milliseconds.
            rows = db.execute(
                "SELECT * FROM device_sessions WHERE run_id=%s AND device_id=%s AND (%s::uuid IS NULL OR (created_at,id)<(SELECT created_at,id FROM device_sessions WHERE id=%s::uuid)) ORDER BY created_at DESC,id DESC LIMIT %s",
                (run_id, device_id, UUID(before) if before else None, UUID(before) if before else None, limit + 1),
            ).fetchall()
        return {
            "rows": [devices.public_session(r) for r in rows[:limit]],
            "more": len(rows) > limit,
            "next": str(rows[limit - 1]["id"]) if len(rows) >= limit else before,
        }

    @app.get(platform + "/{device_id}/packets")
    def packets(
        project: UUID,
        run_id: UUID,
        device_id: UUID,
        session_id: UUID,
        request: Request,
        after: str = "-1",
        limit: int = Query(30, ge=1, le=100),
    ):
        access(request, project)
        start = -1 if after == "-1" else sequence(after)
        with app.state.db.tx(project) as db:
            return packet_history(db, run_id, device_id, session_id=session_id, after=start, limit=limit)

    @app.post(network + "/sessions", status_code=201)
    async def connect(project: UUID, run_id: UUID, device_id: UUID, request: Request):
        raw = await bounded_body(request)
        message, token = read_message(raw), credential(request)
        if "token" in message:
            raise ValueError("HTTP credentials belong in Authorization header")
        return await run_in_threadpool(hello, app.state.db, project, run_id, device_id, token, message)

    @app.post(network + "/sessions/{session_id}/packets", status_code=202)
    async def receive(project: UUID, run_id: UUID, device_id: UUID, session_id: UUID, request: Request):
        raw = await bounded_body(request)
        return await run_in_threadpool(
            devices.accept,
            app.state.db,
            project,
            run_id,
            device_id,
            credential(request),
            session_id,
            read_message(raw),
            len(raw),
        )

    @app.post(network + "/sessions/{session_id}/close")
    def close(project: UUID, run_id: UUID, device_id: UUID, session_id: UUID, request: Request):
        return devices.close_session(app.state.db, project, run_id, device_id, credential(request), session_id)

    @app.get(network + "/sessions/{session_id}/output")
    def output(
        project: UUID,
        run_id: UUID,
        device_id: UUID,
        session_id: UUID,
        request: Request,
        after_revision: str | None = None,
    ):
        return snapshot(
            app.state.db,
            project,
            run_id,
            device_id,
            credential(request),
            session_id,
            sequence(after_revision) if after_revision is not None else None,
        )

    @app.get(network + "/sessions/{session_id}/receipts")
    def receipts(
        project: UUID,
        run_id: UUID,
        device_id: UUID,
        session_id: UUID,
        request: Request,
        after: str = "-1",
        limit: int = Query(30, ge=1, le=100),
    ):
        with app.state.db.tx(project) as db:
            devices.lock_run(db, run_id)
            devices.authenticate(db, run_id, device_id, credential(request), charge=True)
            return packet_history(
                db,
                run_id,
                device_id,
                session_id=session_id,
                after=-1 if after == "-1" else sequence(after),
                limit=limit,
            )

    @app.get(network + "/sessions/{session_id}/evidence/{envelope_id}")
    def evidence(
        project: UUID,
        run_id: UUID,
        device_id: UUID,
        session_id: UUID,
        envelope_id: UUID,
        request: Request,
        after: int = Query(-1, ge=-1, le=255),
        limit: int = Query(20, ge=1, le=256),
    ):
        with app.state.db.tx(project) as db:
            devices.lock_run(db, run_id)
            devices.authenticate(db, run_id, device_id, credential(request), charge=True)
            own = db.execute(
                "SELECT 1 FROM device_packets p JOIN device_sessions s ON s.id=p.session_id WHERE p.envelope_id=%s AND p.session_id=%s AND s.device_id=%s AND p.run_id=%s",
                (envelope_id, session_id, device_id, run_id),
            ).fetchone()
            if not own:
                raise NotFound("device evidence")
            row = db.execute("SELECT * FROM input_envelopes WHERE id=%s", (envelope_id,)).fetchone()
            frames = db.execute(
                "SELECT * FROM input_frames WHERE envelope_id=%s AND frame_index>%s ORDER BY frame_index LIMIT %s",
                (envelope_id, after, limit + 1),
            ).fetchall()
            return {
                "envelope": row,
                "frames": frames[:limit],
                "more": len(frames) > limit,
                "next": frames[limit - 1]["frame_index"] if len(frames) >= limit else after,
            }

    @app.get(network + "/sessions/{session_id}/observations")
    def observations(
        project: UUID,
        run_id: UUID,
        device_id: UUID,
        session_id: UUID,
        request: Request,
        after_us: str = "0",
        limit: int = Query(50, ge=1, le=200),
    ):
        start = timestamp(after_us)
        with app.state.db.tx(project) as db:
            devices.lock_run(db, run_id)
            device = devices.authenticate(db, run_id, device_id, credential(request), capability="output", charge=True)
            # Ended sessions can still verify history with a current credential.
            if not db.execute(
                "SELECT 1 FROM device_sessions WHERE id=%s AND run_id=%s AND device_id=%s",
                (session_id, run_id, device["id"]),
            ).fetchone():
                raise NotFound("device session")
            rows = db.execute(
                "SELECT time_us,sequence,metrics,quality FROM observations WHERE run_id=%s AND time_us>=%s ORDER BY time_us LIMIT %s",
                (run_id, start, limit + 1),
            ).fetchall()
        return {
            "rows": rows[:limit],
            "more": len(rows) > limit,
            "next_us": str(int(rows[limit - 1]["time_us"]) + 1) if len(rows) >= limit else after_us,
        }

    @app.websocket(network + "/ws")
    async def websocket(socket: WebSocket, project: UUID, run_id: UUID, device_id: UUID):
        if socket.query_params or (
            socket.headers.get("origin") and socket.headers["origin"] not in app.state.settings.origins
        ):
            await socket.close(code=1008)
            return
        if not slots.acquire(blocking=False):
            await socket.close(code=1013)
            return
        receiver = None
        try:
            await socket.accept()
            raw = await asyncio.wait_for(socket.receive_text(), timeout=5)
            message = read_message(raw)
            token = message.get("token")
            ready = await run_in_threadpool(hello, app.state.db, project, run_id, device_id, token, message)
            session_id = ready["session"]["id"]

            async def send(value):
                await asyncio.wait_for(socket.send_json(jsonable_encoder(value)), timeout=5)

            await send(ready)
            loop = asyncio.get_running_loop()
            period, next_output, revision = None, 0, None
            next_auth = loop.time() + 30
            receiver = asyncio.create_task(socket.receive_text())
            while True:
                deadline = min(next_auth, next_output) if period else next_auth
                done, _ = await asyncio.wait({receiver}, timeout=max(0, deadline - loop.time()))
                if loop.time() >= next_auth:
                    # Recheck revocation even when a device is idle. A timeout
                    # neither consumes a sequence nor changes its time origin.
                    await run_in_threadpool(
                        hello,
                        app.state.db,
                        project,
                        run_id,
                        device_id,
                        token,
                        {
                            "type": "hello",
                            "source_clock": ready["session"]["source_clock"],
                            "session_id": str(session_id),
                        },
                    )
                    next_auth = loop.time() + 30
                if period and loop.time() >= next_output:
                    try:
                        output = await run_in_threadpool(
                            snapshot, app.state.db, project, run_id, device_id, token, session_id, revision
                        )
                        if revision is None or int(output["revision"]) != revision:
                            await send(output)
                            revision = int(output["revision"])
                        next_output = loop.time() + period
                    except Conflict as error:
                        period = None
                        await send(
                            {"protocol": PROTOCOL, "type": "error", "detail": str(error), "subscription": "stopped"}
                        )
                if not done:
                    continue
                raw = receiver.result()
                receiver = asyncio.create_task(socket.receive_text())
                try:
                    message = read_message(raw)
                    if message.get("type") in ("subscribe", "unsubscribe"):
                        if set(message) - {"protocol", "type", "interval_ms"}:
                            raise ValueError("unknown subscription fields")
                        interval = message.get("interval_ms", 1000)
                        if type(interval) is not int or not 100 <= interval <= 30000:
                            raise ValueError("output subscription interval_ms must be an integer in [100,30000]")
                        # Authorization is checked even when unsubscribing.
                        await run_in_threadpool(snapshot, app.state.db, project, run_id, device_id, token, session_id)
                        period = interval / 1000 if message["type"] == "subscribe" else None
                        next_output, revision = loop.time() + (period or 0), None
                        result = {
                            "protocol": PROTOCOL,
                            "type": "subscription",
                            "enabled": bool(period),
                            "interval_ms": interval,
                        }
                    elif message.get("type") == "output":
                        if set(message) - {"protocol", "type", "after_revision"}:
                            raise ValueError("unknown output request fields")
                        after = sequence(message["after_revision"]) if "after_revision" in message else None
                        result = await run_in_threadpool(
                            snapshot, app.state.db, project, run_id, device_id, token, session_id, after
                        )
                    elif message.get("type") == "close":
                        if set(message) != {"protocol", "type"}:
                            raise ValueError("unknown close request fields")
                        result = await run_in_threadpool(
                            devices.close_session, app.state.db, project, run_id, device_id, token, session_id
                        )
                        await send(result)
                        await socket.close(code=1000)
                        return
                    else:
                        result = await run_in_threadpool(
                            devices.accept,
                            app.state.db,
                            project,
                            run_id,
                            device_id,
                            token,
                            session_id,
                            message,
                            len(raw.encode()),
                        )
                    await send(result)
                except (ValueError, Conflict) as error:
                    await send({"protocol": PROTOCOL, "type": "error", "detail": str(error)[:1000]})
        except WebSocketDisconnect:
            pass  # Transport disconnect is resumable; it does not reset the session.
        except (Forbidden, NotFound, ValueError, Conflict, TimeoutError, KeyError, RuntimeError):
            # Do not echo hello or credential-bearing errors into logs/frames.
            try:
                await socket.close(code=1008)
            except (WebSocketDisconnect, RuntimeError):
                pass
        finally:
            if receiver is not None:
                receiver.cancel()
                with suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError, KeyError):
                    await receiver
            slots.release()
