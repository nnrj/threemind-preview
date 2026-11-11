"""Checkpoint-linked live capture admission in the Lab's sole PostgreSQL store."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from threemind_runtime.live_media import LiveMediaEncoder, decode_packet
from threemind_runtime.media import MEDIA_VERSION

from .database import Conflict, NotFound
from .inputs import digest, lock_admission, submit
from .protocols import RunSpec

PUBLIC = "id,run_id,name,kind,status,configuration,source_clock,next_sequence,byte_count,last_capture_us,origin_sim_us,reason,created_at,updated_at"


def expire(db, run_id):
    """Release abandoned device ownership; already committed stimuli remain valid."""
    db.execute(
        "UPDATE capture_sessions SET status='interrupted',reason=CASE "
        "WHEN updated_at < now()-interval '30 seconds' THEN 'idle_timeout' ELSE 'duration_limit' END,updated_at=now() "
        "WHERE run_id=%s AND status='active' AND (updated_at < now()-interval '30 seconds' "
        "OR created_at + ((configuration->'live_capture'->>'max_session_s')::double precision * interval '1 second') < now())",
        (run_id,),
    )


def configuration(spec):
    return {
        "seed": spec.seed,
        "auditory_sensor": asdict(spec.auditory_sensor),
        "visual_sensor": asdict(spec.visual_sensor),
        "live_capture": asdict(spec.live_capture),
        "source_policies": asdict(spec.source_policies),
    }


def require_running(row):
    spec = RunSpec(**row["spec"])
    if row["status"] != "running" or row["life"] == "dead" or spec.study_id or spec.clock != "realtime":
        raise Conflict("连续物理采集需要正在运行的实时意识；冻结实验、暂停或加速状态不能接收。")
    return spec


def create(database, project, run_id, actor, *, session_id, name, kind, source_clock):
    if kind not in ("audio", "video", "av") or not 1 <= len(name) <= 120:
        raise ValueError("采集类型或名称无效。")
    # Metadata documents source clocks; it confers no timestamp accuracy.
    if not isinstance(source_clock, dict) or not source_clock or len(str(source_clock)) > 8192:
        raise ValueError("请声明采集时钟与浏览器处理信息。")
    digest(source_clock)
    with database.tx(project) as db:
        row = db.execute("SELECT * FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
        if row is None:
            raise NotFound()
        expire(db, run_id)
        old = db.execute("SELECT * FROM capture_sessions WHERE id=%s", (session_id,)).fetchone()
        if old:
            if (
                str(old["run_id"]) != str(run_id)
                or old["kind"] != kind
                or old["name"] != name
                or old["source_clock"] != source_clock
            ):
                raise Conflict("该会话标识已用于不同采集。")
            return db.execute(f"SELECT {PUBLIC} FROM capture_sessions WHERE id=%s", (session_id,)).fetchone()
        spec = require_running(row)
        for selected, source in (
            (kind in ("audio", "av"), "live-microphone"),
            (kind in ("video", "av"), "live-camera"),
        ):
            if selected and not spec.source_policies.resolve(source)["enabled"]:
                raise Conflict(f"该实时来源已关闭：{source}。请暂停后在来源策略中开启。")
        if kind in ("audio", "av") and not (spec.live_capture.microphone_enabled and spec.auditory_sensor.enabled):
            raise Conflict("请暂停并在参数配置中开启听觉感官与连续麦克风。")
        if kind in ("video", "av") and not (spec.live_capture.camera_enabled and spec.visual_sensor.enabled):
            raise Conflict("请暂停并在参数配置中开启视觉感官与连续摄像头。")
        if db.execute("SELECT 1 FROM capture_sessions WHERE run_id=%s AND status='active'", (run_id,)).fetchone():
            raise Conflict("该意识已有采集会话，请先结束；音画同步请选择合并会话。")
        encoder = LiveMediaEncoder(spec.seed, spec.auditory_sensor, spec.visual_sensor)
        return db.execute(
            f"INSERT INTO capture_sessions(id,project_id,run_id,actor_id,name,kind,configuration,source_clock,encoder_state,storage_policy) "
            f"VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING {PUBLIC}",
            (
                session_id,
                project,
                run_id,
                actor["id"],
                name,
                kind,
                Jsonb(configuration(spec)),
                Jsonb(source_clock),
                Jsonb(encoder.capture()),
                Jsonb(database.blobs.freeze("media-original")),
            ),
        ).fetchone()


def accept_packet(database, project, run_id, session_id, actor, raw):
    # Decode hard bounds before allocating sample arrays; per-session limits follow.
    packet = decode_packet(raw, max_bytes=8388608)
    sha = hashlib.sha256(raw).hexdigest()
    # Original bytes upload without holding run/session locks. All causal state
    # below is rechecked and committed in the original single transaction.
    with database.tx(project) as carrier_db:
        carrier_session = carrier_db.execute(
            "SELECT storage_policy FROM capture_sessions WHERE id=%s AND run_id=%s", (session_id, run_id)
        ).fetchone()
    if carrier_session is None:
        raise NotFound()
    blob = database.blobs.prepare(
        project,
        "media-original",
        (raw[i : i + 1048576] for i in range(0, len(raw), 1048576)),
        frozen=carrier_session["storage_policy"],
    )
    with database.tx(project) as db:
        # Preserve run-before-session order without waiting for ordinary non-key
        # checkpoint writes. All input producers share the admission budget lock.
        row = lock_admission(db, run_id, continuous=True)
        session = db.execute(
            "SELECT * FROM capture_sessions WHERE id=%s AND run_id=%s FOR UPDATE", (session_id, run_id)
        ).fetchone()
        if session is None:
            raise NotFound()
        previous = db.execute(
            "SELECT envelope_id,sha256,metadata FROM capture_packets WHERE session_id=%s AND sequence=%s",
            (session_id, packet.sequence),
        ).fetchone()
        if previous:
            if previous["sha256"] != sha:
                raise Conflict("同一采集序号已保存不同数据。")
            return {
                "session_id": str(session_id),
                "sequence": packet.sequence,
                "envelope_id": str(previous["envelope_id"]),
                "duplicate": True,
                "metadata": previous["metadata"],
            }
        spec = require_running(row)
        cfg = spec.live_capture
        if session["status"] != "active":
            raise Conflict("该采集会话已结束或中断，请开始新会话。")
        if session["configuration"] != configuration(spec):
            raise Conflict("感官配置已改变，请开始新会话。")
        if session["kind"] not in (packet.kind, "av"):
            raise ValueError("采集块类型不属于该会话。")
        if packet.sequence != session["next_sequence"]:
            raise Conflict("采集序号不连续；请重试尚未确认的原始块。")
        if len(raw) > cfg.max_packet_bytes or session["byte_count"] + len(raw) > cfg.max_session_bytes:
            raise Conflict("采集字节预算已满，请结束当前会话。")
        elapsed = (datetime.now(UTC) - session["created_at"]).total_seconds()
        packet_duration = round(packet.sample_count * 1e6 / packet.sample_rate) if packet.kind == "audio" else 0
        if packet.kind == "audio" and packet_duration > cfg.audio_packet_us + round(1e6 / packet.sample_rate):
            raise ValueError("音频块超过配置的传输时长；请按采样数量分包。")
        if elapsed > cfg.max_session_s or packet.capture_us + packet_duration > cfg.max_session_s * 1000000:
            raise Conflict("采集会话时长已达上限。")
        if packet.capture_us + packet_duration > (elapsed + cfg.delivery_buffer_us / 1e6) * 1e6:
            raise ValueError("采集时间超前于会话物理时长，不能伪造未来采样。")
        encoder = LiveMediaEncoder(spec.seed, spec.auditory_sensor, spec.visual_sensor, session["encoder_state"])
        frames = encoder.consume(packet)
        metadata = packet.metadata() | {
            "source_clock": session["source_clock"],
            "session_id": str(session_id),
            "frames_encoded": len(frames),
            "captured_end_us": str(packet.capture_us + round(packet.sample_count * 1e6 / packet.sample_rate))
            if packet.kind == "audio"
            else str(packet.capture_us),
        }
        envelope_id = uuid5(UUID(str(session_id)), f"packet:{packet.sequence}")
        payload = {
            "kind": packet.kind,
            "asset_sha256": sha,
            "byte_length": len(raw),
            "filename": f"capture-{packet.sequence}.tmv2",
            "intensity": 1.0,
            "stream_session_id": str(session_id),
            "stream_sequence": packet.sequence,
            "capture_us": str(packet.capture_us),
        }
        prepared = {
            "frames": frames,
            "metadata": metadata,
            "raw": raw,
            "seed": spec.seed,
            "version": MEDIA_VERSION,
            "config": asdict(spec.auditory_sensor if packet.kind == "audio" else spec.visual_sensor),
            "source": "live-microphone" if packet.kind == "audio" else "live-camera",
            "blob": blob,
        }
        accepted = submit(
            database,
            project,
            run_id,
            actor,
            adapter_id="auditory-sensor" if packet.kind == "audio" else "visual-sensor",
            payload=payload,
            request_id=envelope_id,
            delay_us=cfg.delivery_buffer_us,
            prepared=prepared,
            transaction=db,
            admitted_run=row,
        )
        db.execute(
            "INSERT INTO capture_packets(project_id,run_id,session_id,sequence,envelope_id,sha256,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (project, run_id, session_id, packet.sequence, envelope_id, sha, Jsonb(metadata)),
        )
        db.execute(
            "UPDATE capture_sessions SET encoder_state=%s,next_sequence=next_sequence+1,byte_count=byte_count+%s,"
            "last_capture_us=GREATEST(COALESCE(last_capture_us,0),%s),updated_at=now() WHERE id=%s",
            (Jsonb(encoder.capture()), len(raw), int(metadata["captured_end_us"]), session_id),
        )
        return {
            "session_id": str(session_id),
            "sequence": packet.sequence,
            "envelope_id": str(accepted["id"]),
            "duplicate": False,
            "metadata": metadata,
        }


def stop(database, project, run_id, session_id, *, reason="user_stopped"):
    if reason not in ("user_stopped", "device_lost", "capture_gap", "queue_overflow", "request_failed", "page_left"):
        raise ValueError("unknown capture termination reason")
    with database.tx(project) as db:
        current = db.execute(
            "SELECT kind,status,encoder_state FROM capture_sessions WHERE id=%s AND run_id=%s FOR UPDATE",
            (session_id, run_id),
        ).fetchone()
        if current is None:
            raise NotFound()
        if current["status"] == "active":
            audio = current["encoder_state"]["audio"]
            if (
                reason == "user_stopped"
                and current["kind"] in ("audio", "av")
                and audio["source_count"]
                and not audio["finished"]
            ):
                reason = "incomplete_audio_tail"
            return db.execute(
                f"UPDATE capture_sessions SET status=CASE WHEN %s='user_stopped' THEN 'stopped' ELSE 'interrupted' END,reason=%s,updated_at=now() "
                f"WHERE id=%s AND run_id=%s RETURNING {PUBLIC}",
                (reason, reason, session_id, run_id),
            ).fetchone()
        row = db.execute(
            f"SELECT {PUBLIC} FROM capture_sessions WHERE id=%s AND run_id=%s", (session_id, run_id)
        ).fetchone()
        if row is None:
            raise NotFound()
        return row
