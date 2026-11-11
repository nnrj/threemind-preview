"""Run-scoped device credentials and transactional, idempotent carrier admission."""

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4, uuid5

from psycopg.types.json import Jsonb
from pydantic import Field, model_validator

from threemind_core.attention import modulation_payload
from threemind_core.energy import supply_payload
from threemind_core.spec import timestamp
from threemind_runtime.network import PROTOCOL, decode_frames, sequence
from threemind_runtime.network_wiring import make_wiring, validate_wiring

from . import inputs, ports
from .database import Conflict, Forbidden, NotFound
from .protocols import StrictModel


class DeviceConfiguration(StrictModel):
    input: bool = Field(default=True, strict=True)
    output: bool = Field(default=True, strict=True)
    modulation: bool = Field(default=False, strict=True)
    energy: bool = Field(default=False, strict=True)
    packets_per_second: int = Field(default=40, ge=1, le=1000, strict=True)
    maximum_channels: int = Field(default=256, ge=1, le=4096, strict=True)
    lead_us: int = Field(default=500000, ge=1000, le=10000000, strict=True)
    lookahead_us: int = Field(default=10000000, ge=1000, le=100000000, strict=True)
    output_nodes: int = Field(default=256, ge=0, le=4096, strict=True)
    output_edges: int = Field(default=512, ge=0, le=8192, strict=True)

    @model_validator(mode="after")
    def timing(self):
        if self.lead_us > self.lookahead_us:
            raise ValueError("采集提前量不能大于未来时间预算。")
        return self


class CreateDevice(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    configuration: DeviceConfiguration = Field(default_factory=DeviceConfiguration)
    lifetime_days: int = Field(default=30, ge=1, le=365, strict=True)
    wiring: dict | None = None

    @model_validator(mode="after")
    def wiring_manifest(self):
        if self.wiring is not None:
            self.wiring = validate_wiring(self.wiring)
        return self


class EditDevice(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    configuration: DeviceConfiguration
    enabled: bool = Field(strict=True)


class SourceClock(StrictModel):
    mode: Literal["device", "simulation"]
    description: str = Field(default="", max_length=240)


def public(row):
    return {k: v for k, v in row.items() if k not in ("token_hash", "rate_window", "rate_count")}


def public_session(row):
    return public(row) | {"next_sequence": str(row["next_sequence"]), "byte_count": str(row["byte_count"])}


def lock_run(db, run_id):
    run = db.execute("SELECT * FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
    if run is None:
        raise NotFound("run")
    return run


def create(database, project, run_id, actor, request):
    key, token = uuid4(), secrets.token_urlsafe(32)
    with database.tx(project) as db:
        run = lock_run(db, run_id)
        wiring = request.wiring or make_wiring(run["spec"].get("seed", 20260724), key)
        check_wiring_seed(wiring, run)
        if db.execute(
            "SELECT 1 FROM device_bindings WHERE run_id=%s AND wiring_id=%s", (run_id, wiring["wiring_id"])
        ).fetchone():
            raise Conflict("此意识已绑定该接线，请编辑或轮换已有设备的凭据。")
        count = db.execute("SELECT count(*) AS n FROM device_bindings WHERE run_id=%s", (run_id,)).fetchone()["n"]
        if count >= 256:
            raise Conflict("每个意识最多保留 256 个设备绑定。")
        row = db.execute(
            """INSERT INTO device_bindings(id,project_id,run_id,name,issuer_id,token_hash,configuration,expires_at,wiring_id)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (
                key,
                project,
                run_id,
                request.name,
                actor,
                inputs.digest(token),
                Jsonb(request.configuration.model_dump()),
                datetime.now(UTC) + timedelta(days=request.lifetime_days),
                wiring["wiring_id"],
            ),
        ).fetchone()
        audit(db, actor, "create", key)
    return {"device": public(row), "token": token}


def check_wiring_seed(wiring, run):
    if wiring["sensory_seed"] != run["spec"].get("seed", 20260724):
        raise Conflict("接线清单的感官种子与此意识不一致，请使用对应模型或其继承副本。")


def export_wiring(database, project, run_id, device_id):
    with database.tx(project) as db:
        run = lock_run(db, run_id)
        device = db.execute(
            "SELECT wiring_id FROM device_bindings WHERE id=%s AND run_id=%s", (device_id, run_id)
        ).fetchone()
        if device is None:
            raise NotFound("device")
        return make_wiring(run["spec"].get("seed", 20260724), device["wiring_id"])


def audit(db, actor, action, key):
    db.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,%s,%s)", (actor, "device." + action, str(key)))


def edit(database, project, run_id, device_id, actor, request=None, *, rotate=False):
    token = secrets.token_urlsafe(32) if rotate else None
    with database.tx(project) as db:
        lock_run(db, run_id)
        row = db.execute(
            "SELECT * FROM device_bindings WHERE id=%s AND run_id=%s FOR UPDATE", (device_id, run_id)
        ).fetchone()
        if row is None:
            raise NotFound("device")
        if rotate:
            db.execute(
                "UPDATE device_bindings SET token_hash=%s,token_generation=token_generation+1,issuer_id=%s,expires_at=now()+interval '30 days',updated_at=now() WHERE id=%s",
                (inputs.digest(token), actor, device_id),
            )
        else:
            db.execute(
                "UPDATE device_bindings SET name=%s,configuration=%s,enabled=%s,updated_at=now() WHERE id=%s",
                (request.name, Jsonb(request.configuration.model_dump()), request.enabled, device_id),
            )
        # Configuration is a contract for a session. Changes never silently alter it.
        db.execute(
            "UPDATE device_sessions SET status='revoked',reason=%s,updated_at=now() WHERE device_id=%s AND status='active'",
            ("credential_rotated" if rotate else "binding_edited", device_id),
        )
        audit(db, actor, "rotate" if rotate else "edit", device_id)
        row = public(db.execute("SELECT * FROM device_bindings WHERE id=%s", (device_id,)).fetchone())
    return {"device": row, **({"token": token} if token else {})}


def authenticate(db, run_id, device_id, token, *, capability=None, charge=False):
    row = db.execute(
        """SELECT d.*,u.enabled AS issuer_enabled,m.role AS issuer_role FROM device_bindings d
           JOIN users u ON u.id=d.issuer_id LEFT JOIN members m ON m.project_id=d.project_id AND m.user_id=d.issuer_id
           WHERE d.id=%s AND d.run_id=%s FOR UPDATE OF d""",
        (device_id, run_id),
    ).fetchone()
    if (
        row is None
        or not isinstance(token, str)
        or len(token) > 128
        or not hmac.compare_digest(row["token_hash"], inputs.digest(token))
        or not row["enabled"]
        or row["expires_at"] <= datetime.now(UTC)
        or not row["issuer_enabled"]
        or row["issuer_role"] not in ("owner", "researcher")
    ):
        raise Forbidden("设备凭据无效、已失效，或签发者已失去项目权限。")
    if capability and not row["configuration"].get(capability):
        raise Forbidden(f"设备未获授权：{capability}")
    if charge:
        now = datetime.now(UTC)
        count = row["rate_count"] if (now - row["rate_window"]).total_seconds() < 1 else 0
        if count >= row["configuration"]["packets_per_second"]:
            raise Conflict("设备请求频率超出绑定预算；请稍后重试，序号未消耗。")
        db.execute(
            "UPDATE device_bindings SET rate_window=%s,rate_count=%s WHERE id=%s",
            (row["rate_window"] if count else now, count + 1, device_id),
        )
    return row


def session_row(db, run_id, device, session_id):
    row = db.execute(
        "SELECT * FROM device_sessions WHERE id=%s AND device_id=%s AND run_id=%s FOR UPDATE",
        (session_id, device["id"], run_id),
    ).fetchone()
    if row is None:
        raise NotFound("device session")
    if row["status"] != "active" or row["token_generation"] != device["token_generation"]:
        raise Conflict("设备会话已结束；请建立新会话，不能重绑旧采集时钟。")
    return row


def delivery_session(db, run_id, session_id):
    row = db.execute(
        """SELECT s.*,d.enabled AND d.expires_at>now() AND d.token_generation=s.token_generation
           AND u.enabled AND COALESCE(m.role IN ('owner','researcher'),false) AS authorized
           FROM device_sessions s JOIN device_bindings d ON d.id=s.device_id JOIN users u ON u.id=d.issuer_id
           LEFT JOIN members m ON m.project_id=d.project_id AND m.user_id=d.issuer_id
           WHERE s.id=%s AND s.run_id=%s""",
        (session_id, run_id),
    ).fetchone()
    if row and not row["authorized"]:
        row["status"] = "revoked"
    return row


def open_session(database, project, run_id, device_id, token, source_clock, session_id=None):
    clock = SourceClock(**source_clock).model_dump()
    with database.tx(project) as db:
        run = lock_run(db, run_id)
        device = authenticate(db, run_id, device_id, token, charge=True)
        if session_id is not None:
            row = session_row(db, run_id, device, UUID(str(session_id)))
            if row["source_clock"] != clock:
                raise Conflict("重连必须保留原有的源时钟声明。")
            return row
        if clock["mode"] == "device" and (
            run["spec"].get("clock", "realtime") != "realtime" or run["status"] != "running"
        ):
            raise Conflict("物理采集时钟需要正在运行的实时时间模式。")
        count = db.execute(
            "SELECT count(*) AS n FROM device_sessions WHERE device_id=%s AND status='active'", (device_id,)
        ).fetchone()["n"]
        if count >= 8:
            raise Conflict("设备最多同时保持 8 个会话；请先关闭不用的会话。")
        return db.execute(
            """INSERT INTO device_sessions(id,project_id,run_id,device_id,token_generation,clock_mode,source_clock)
               VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (uuid4(), project, run_id, device_id, device["token_generation"], clock["mode"], Jsonb(clock)),
        ).fetchone()


def close_session(database, project, run_id, device_id, token, session_id):
    with database.tx(project) as db:
        lock_run(db, run_id)
        device = authenticate(db, run_id, device_id, token, charge=True)
        session_row(db, run_id, device, session_id)
        db.execute(
            "UPDATE device_sessions SET status='closed',reason='device_closed',updated_at=now() WHERE id=%s",
            (session_id,),
        )
    return {"status": "closed"}


def accept(database, project, run_id, device_id, token, session_id, message, byte_count):
    # Charge authenticated attempts independently of scientific admission. A
    # rejected carrier consumes no sequence/queue budget, but cannot bypass the
    # device's request rate by repeatedly sending expensive invalid packets.
    with database.tx(project) as db:
        lock_run(db, run_id)
        authenticate(db, run_id, device_id, token, charge=True)
    kind, index = message.get("type"), sequence(message.get("sequence"))
    capability = {"input": "input", "modulation": "modulation", "energy": "energy"}.get(kind)
    if capability is None:
        raise ValueError("unsupported device packet type")
    keys = {"protocol", "type", "sequence"} | ({"frames", "capture_us"} if kind == "input" else {"value", "delay_us"})
    if set(message) - keys or message.get("protocol") != PROTOCOL:
        raise ValueError("unknown device packet fields or protocol")
    fingerprint = inputs.digest(message)
    with database.tx(project) as db:
        run = lock_run(db, run_id)
        device = authenticate(db, run_id, device_id, token, capability=capability)
        session = session_row(db, run_id, device, session_id)
        previous = db.execute(
            "SELECT sha256,receipt FROM device_packets WHERE session_id=%s AND sequence=%s", (session_id, index)
        ).fetchone()
        if previous:
            if previous["sha256"] != fingerprint:
                raise Conflict("该设备序号已用于不同内容，不能覆盖原始包。")
            return previous["receipt"]
        if index != session["next_sequence"]:
            raise Conflict(f"设备包序号不连续，应为 {session['next_sequence']}。")
        if session["clock_mode"] == "device" and (
            run["status"] != "running" or run["spec"].get("clock", "realtime") != "realtime"
        ):
            raise Conflict("物理采集会话不能向暂停或非实时实例继续发送。")
        config, packet_id = device["configuration"], uuid5(UUID(str(session_id)), str(index))
        provenance = {
            "device_id": str(device_id),
            "wiring_id": str(device["wiring_id"]),
            "session_id": str(session_id),
            "sequence": str(index),
            "source_clock": session["source_clock"],
            "configuration": config,
        }
        envelope, command, capture, last = None, None, session["last_capture_us"], session["last_frame_us"]
        if kind == "input":
            capture = timestamp(message.get("capture_us", "0"))
            if session["clock_mode"] == "simulation" and capture != 0:
                raise ValueError("模拟时钟使用绝对帧时间，capture_us 必须为 0。")
            if session["clock_mode"] == "device" and (
                (last is None and capture != 0)
                or (session["last_capture_us"] is not None and capture < int(session["last_capture_us"]))
            ):
                raise ValueError("首个采集包 capture_us 必须为 0，后续不能倒退。")
            frames, mapping = decode_frames(
                message.get("frames"),
                seed=run["spec"].get("seed", 20260724),
                wiring_id=device["wiring_id"],
                maximum_channels=config["maximum_channels"],
                maximum_span_us=config["lookahead_us"],
            )
            for frame in frames:
                frame["time_us"] = str(timestamp(int(frame["time_us"]) + capture))
            first, last_frame = int(frames[0]["time_us"]), int(frames[-1]["time_us"])
            if last is not None and first < int(last):
                raise ValueError("设备帧时间不能越过前一个包的结尾而倒退。")
            origin = int(session["origin_sim_us"] or 0)
            now = int(run["time_us"])
            if session["clock_mode"] == "simulation":
                if first < now or last_frame > now + config["lookahead_us"]:
                    raise ValueError("模拟帧时间已过去，或超出设备未来时间预算。")
            elif session["origin_sim_us"] is not None:
                if first + origin < now or last_frame + origin > now + config["lookahead_us"]:
                    raise ValueError("采集时间已迟到或超出未来预算；不会改写时间戳。")
            elif last_frame + config["lead_us"] > config["lookahead_us"]:
                raise ValueError("未绑定时钟的采集数据超出未来时间预算。")
            result = inputs.submit(
                database,
                project,
                run_id,
                {"id": device["issuer_id"]},
                adapter_id="remote-anonymous",
                request_id=packet_id,
                payload={
                    "frames": frames,
                    "remote": message,
                    "device_session_id": str(session_id),
                    "capture_us": str(capture),
                },
                delay_us=config["lead_us"] if session["clock_mode"] == "device" else 0,
                requested_time_us=None if session["clock_mode"] == "device" else 0,
                transaction=db,
                remote=provenance | {"mapping": mapping},
            )
            envelope, command, last = result["id"], result["command_id"], last_frame
        else:
            value = message.get("value")
            if not isinstance(value, dict):
                raise ValueError("scalar device packet requires value object")
            delay = timestamp(message.get("delay_us", "0"))
            if delay > config["lookahead_us"]:
                raise ValueError("端口延时超出设备未来时间预算。")
            # A re-deployed credential must update the same explicit modulator,
            # not accidentally stack a second controller under a new auth ID.
            source = f"remote:{device['wiring_id']}"
            try:
                payload = (
                    supply_payload(source=source, **value)
                    if kind == "energy"
                    else modulation_payload(source=source, **value)
                )
            except TypeError as error:
                raise ValueError("unknown or missing scalar port fields") from error
            result = ports.submit(
                database,
                project,
                run_id,
                device["issuer_id"],
                kind="energy_supply" if kind == "energy" else "input_modulation",
                request_id=packet_id,
                payload=payload | {"delay_us": delay, "device": provenance, "raw_packet": message},
                required_flag="energy_simulation_enabled" if kind == "energy" else None,
                transaction=db,
            )
            command = result["id"]
        receipt = {
            "protocol": PROTOCOL,
            "type": "receipt",
            "session_id": str(session_id),
            "sequence": str(index),
            "status": "accepted",
            "meaning": "database acceptance; delivery requires committed runtime evidence",
            "envelope_id": str(envelope) if envelope else None,
            "command_id": str(command),
            "sha256": fingerprint,
        }
        db.execute(
            "INSERT INTO device_packets(project_id,run_id,session_id,sequence,kind,sha256,receipt,envelope_id,command_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (project, run_id, session_id, index, kind, fingerprint, Jsonb(receipt), envelope, command),
        )
        db.execute(
            "UPDATE device_sessions SET next_sequence=%s,last_capture_us=%s,last_frame_us=%s,byte_count=byte_count+%s,updated_at=now() WHERE id=%s",
            (index + 1, capture, last, byte_count, session_id),
        )
        return receipt
