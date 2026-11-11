"""Durable carrier admission and checkpoint-atomic sensory audit."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from contextlib import nullcontext
from dataclasses import asdict

from psycopg.types.json import Jsonb

from threemind_core.spec import timestamp
from threemind_runtime.sensory import TEXT_VERSION, TextSensor, carrier_frames

from .database import Conflict, NotFound
from .database_stream import stream_rows
from .protocols import RunSpec


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def envelope_record(
    envelope_id, adapter_id, source, payload, configuration, frame_count, channel_count, *, version="anonymous-frames/1"
):
    return {
        "id": str(envelope_id),
        "adapter_id": adapter_id,
        "adapter_version": version,
        "source": source,
        "payload": payload,
        "payload_hash": digest(payload),
        "configuration": configuration,
        "configuration_hash": digest(configuration),
        "frame_count": frame_count,
        "channel_count": channel_count,
        "request_hash": digest([adapter_id, payload, configuration]),
    }


def insert_envelope(db, project, run_id, item):
    return db.execute(
        """INSERT INTO input_envelopes(id,project_id,run_id,adapter_id,adapter_version,source,payload,payload_hash,
           configuration,configuration_hash,frame_count,channel_count,request_hash,actor_id,delay_us,requested_time_us)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING RETURNING id""",
        (
            item["id"],
            project,
            run_id,
            item["adapter_id"],
            item["adapter_version"],
            item["source"],
            Jsonb(item["payload"]),
            item["payload_hash"],
            Jsonb(item["configuration"]),
            item["configuration_hash"],
            item["frame_count"],
            item["channel_count"],
            item["request_hash"],
            item.get("actor_id"),
            item.get("delay_us", 0),
            item.get("requested_time_us"),
        ),
    ).fetchone()


def lock_admission(db, run_id, *, continuous=False):
    # Normal producers hold UPDATE; it conflicts with a capture's KEY SHARE.
    # Capture producers additionally serialize with one another using an advisory
    # lock. Both paths acquire the row first, including transaction-owning callers.
    # Hash collisions only serialize unrelated admissions; identities stay distinct.
    lock = "KEY SHARE" if continuous else "UPDATE"
    row = db.execute(f"SELECT * FROM runs WHERE id=%s FOR {lock}", (run_id,)).fetchone()
    if row is None:
        raise NotFound()
    if continuous:
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,738349202))", (str(run_id),))
        row = db.execute("SELECT * FROM runs WHERE id=%s", (run_id,)).fetchone()
    return row


def submit(
    database,
    project,
    run_id,
    actor,
    *,
    adapter_id,
    payload,
    request_id,
    delay_us=0,
    requested_time_us=None,
    prepared=None,
    transaction=None,
    remote=None,
    source_id=None,
    research_plan_id=None,
    admitted_run=None,
):
    # Request identity excludes later server config changes: a retry returns its
    # ORIGINAL acknowledged carrier/configuration, not a second delivery.
    fingerprint = digest([adapter_id, payload, delay_us, requested_time_us])
    if source_id is not None:
        if adapter_id != "text-sensor" or source_id not in ("ui-text", "cli-text", "ai-environment", "ai-debug"):
            raise ValueError("invalid text source identity")
        fingerprint = digest([adapter_id, payload, delay_us, requested_time_us, source_id])
    if len(json.dumps(payload, ensure_ascii=False).encode()) > 4 * 1024 * 1024:
        raise ValueError("单次载体超过 4 MiB 接收预算；整条未接收，不会截断。")
    with database.tx(project) if transaction is None else nullcontext(transaction) as db:
        if admitted_run is not None and (transaction is None or str(admitted_run["id"]) != str(run_id)):
            raise ValueError("prepared admission requires its owning transaction and run")
        row = admitted_run if admitted_run is not None else lock_admission(db, run_id)
        old = db.execute("SELECT * FROM input_envelopes WHERE id=%s", (request_id,)).fetchone()
        if old:
            if str(old["run_id"]) != str(run_id) or old["request_hash"] != fingerprint:
                raise Conflict("该请求标识已用于不同载体；请为新输入使用新的标识。")
            return public_envelope(old)
        from .research_lock import assert_control_available

        assert_control_available(db, run_id, research_plan_id, population_input=True)
        if row["status"] not in ("running", "queued", "paused", "blocked") or row["life"] == "dead":
            raise Conflict("当前实例不能接收输入；已结束的实例请先分叉。")
        spec = RunSpec(**row["spec"])
        source = (
            f"remote:{remote['device_id']}"
            if remote is not None
            else prepared.get("source", f"upload-{payload['kind']}")
            if prepared is not None
            else {"cli-text": "manual-cli-text", "ai-environment": "ai-environment", "ai-debug": "ai-debug"}.get(
                source_id, "manual-text"
            )
            if adapter_id == "text-sensor"
            else "external-transformer-probabilities"
            if adapter_id == "transformer-probability"
            else "manual-anonymous"
        )
        source_policy = spec.source_policies.resolve(source)
        if not source_policy["enabled"]:
            raise Conflict(f"该输入来源已关闭：{source}（{source_policy['reason']}）。请暂停后在来源策略中修改。")
        if spec.study_id:
            raise Conflict("实验协议已冻结，不能添加人工载体；请分叉为独立运行。")
        cp = db.execute(
            "SELECT context FROM checkpoints WHERE run_id=%s ORDER BY revision DESC LIMIT 1", (run_id,)
        ).fetchone()
        if cp and cp["context"].get("source_enabled") is False:
            raise Conflict("该实例已关闭所有输入。")
        if db.execute(
            "SELECT 1 FROM commands WHERE run_id=%s AND kind='close_inputs' AND id>%s", (run_id, row["last_command"])
        ).fetchone():
            raise Conflict("已有关闭输入命令等待执行，未接收新的载体。")
        config = asdict(spec.text_sensor) if adapter_id == "text-sensor" else {}
        legacy_text = adapter_id == "text-sensor" and spec.kernel_id == "unified-associative"
        if legacy_text:
            from .legacy_text import configuration as legacy_configuration

            config = legacy_configuration(spec, run_id)
            if cp:
                # Imported/restored packages retain their own sensory identity.
                _, image = database.load_checkpoint(project, run_id)
                config["sensory_seed"] = image.to_dict()["package"]["state"]["sensory_seed"]
        if prepared is not None:
            root = "auditory_sensor" if payload["kind"] == "audio" else "visual_sensor"
            config = asdict(getattr(spec, root))
            if config != prepared["config"] or spec.seed != prepared["seed"]:
                raise Conflict("解码期间感官配置发生变化；整条未接收，请重新提交。")
        if adapter_id == "text-sensor" and not spec.text_sensor.enabled:
            raise Conflict("该意识的文本感官未启用，请先在参数配置中启用。")
        count = channels = 0
        from .legacy_text import frames as legacy_frames

        decoded = (prepared["frames"] if prepared is not None else legacy_frames(payload, config)
                   if legacy_text else carrier_frames(adapter_id, payload, spec.seed, config))
        for frame in decoded:
            count += 1
            channels += len(frame["stimulus"].channels)
            if count > spec.input_bus.max_pending_frames or channels > spec.input_bus.max_pending_channels:
                raise ValueError("载体超出当前输入总线预算；整条未接收，请提高预算或调整分帧参数。")
        queued = pending_budget(db, run_id)
        if (
            int(queued["frames"]) + count > spec.input_bus.max_pending_frames
            or int(queued["channels"]) + channels > spec.input_bus.max_pending_channels
        ):
            raise Conflict("输入队列已满；整条载体未接收，请等待已接收输入递送，或暂停后提高预算。")
        configuration = {
            "seed": spec.seed,
            "adapter": config,
            "run_revision": row["revision"],
            "source_policy_at_admission": source_policy,
        }
        if remote is not None:
            if adapter_id != "remote-anonymous":
                raise ValueError("device provenance requires remote-anonymous adapter")
            configuration["remote"] = remote
        if prepared is not None:
            configuration.update(
                transduction=prepared["metadata"],
                prepared_frames_hash=digest([f["stimulus"].to_dict() for f in prepared["frames"]]),
            )
        if adapter_id == "text-sensor":
            configuration["transduction"] = ({"version": "legacy-unified-text/97d8592", "configuration": config}
                                              if legacy_text else TextSensor(spec.seed, spec.text_sensor).describe(payload["text"]))
            from threemind_runtime.stimulus_presets import resolve_intensity

            configuration["resolved_intensity"] = resolve_intensity(payload.get("intensity"), payload.get("preset"))
        if adapter_id == "transformer-probability":
            from threemind_transformer.adapter import probability_frame

            configuration["transduction"] = probability_frame(
                payload["response"], payload["channel_ids"], time_us=0, intensity=payload["intensity"]
            )["metadata"] | {"prediction_job_id": payload["prediction_job_id"]}
        item = envelope_record(
            request_id,
            adapter_id,
            source,
            payload,
            configuration,
            count,
            channels,
            version="threemind-network/2"
            if remote is not None
            else prepared["version"]
            if prepared is not None
            else "legacy-unified-text/97d8592" if legacy_text
            else TEXT_VERSION
            if adapter_id == "text-sensor"
            else "threemind.probabilities/1"
            if adapter_id == "transformer-probability"
            else "threemind.stimulus-unit/1"
            if adapter_id == "stimulus-units"
            else "anonymous-frames/1",
        )
        item.update(
            request_hash=fingerprint,
            actor_id=actor["id"],
            delay_us=timestamp(delay_us),
            requested_time_us=timestamp(requested_time_us) if requested_time_us is not None else None,
        )
        if not insert_envelope(db, project, run_id, item):
            raise Conflict("该请求标识不可用，请为新输入使用新的标识。")
        if prepared is not None:
            from .media_store import persist

            persist(db, project, run_id, request_id, payload, prepared)
        command = db.execute(
            "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,'sensory_input',%s) RETURNING id",
            (project, run_id, Jsonb({"envelope_id": str(request_id)})),
        ).fetchone()
        db.execute("UPDATE input_envelopes SET command_id=%s WHERE id=%s", (command["id"], request_id))
        return public_envelope(db.execute("SELECT * FROM input_envelopes WHERE id=%s", (request_id,)).fetchone())


def pending_budget(db, run_id):
    return db.execute(
        """SELECT COALESCE(sum(e.frame_count-e.delivered_count-e.filtered_count),0) AS frames,
               COALESCE(sum(e.channel_count - COALESCE((SELECT sum(f.channel_count) FROM input_frames f
               WHERE f.envelope_id=e.id AND f.status IN ('delivered','filtered')),0)),0) AS channels
               FROM input_envelopes e WHERE run_id=%s AND adapter_id IN ('text-sensor','anonymous-frames','stimulus-units','auditory-sensor','visual-sensor','remote-anonymous','transformer-probability')
               AND status IN ('accepted','scheduled')""",
        (run_id,),
    ).fetchone()


def public_envelope(row):
    return {key: value for key, value in row.items() if key not in ("payload", "request_hash")}


def commit_inputs(db, project, run_id, revision, changes):
    """Called inside the SAME fenced transaction as the matching Core state."""
    from .live_capture import expire

    expire(db, run_id)
    for update in changes.get("device_updates", []):
        if "origin_us" in update:
            db.execute(
                "UPDATE device_sessions SET origin_sim_us=%s,updated_at=now() WHERE id=%s AND run_id=%s",
                (int(update["origin_us"]), update["id"], run_id),
            )
        if "reason" in update:
            db.execute(
                "UPDATE device_sessions SET status='interrupted',reason=%s,updated_at=now() WHERE id=%s AND run_id=%s AND status='active'",
                (update["reason"], update["id"], run_id),
            )
    if changes.get("capture_end_reason"):
        db.execute(
            "UPDATE device_sessions SET status='interrupted',reason=%s,updated_at=now() WHERE run_id=%s AND clock_mode='device' AND status='active'",
            (changes["capture_end_reason"], run_id),
        )
    for update in changes.get("capture_updates", []):
        if "origin_us" in update:
            db.execute(
                "UPDATE capture_sessions SET origin_sim_us=%s,updated_at=now() WHERE id=%s AND run_id=%s",
                (int(update["origin_us"]), update["id"], run_id),
            )
        if "reason" in update:
            db.execute(
                "UPDATE capture_sessions SET status='interrupted',reason=%s,updated_at=now() WHERE id=%s AND run_id=%s",
                (update["reason"], update["id"], run_id),
            )
    if changes.get("capture_end_reason"):
        db.execute(
            "UPDATE capture_sessions SET status='interrupted',reason=%s,updated_at=now() WHERE run_id=%s AND status='active'",
            (changes["capture_end_reason"], run_id),
        )
    affected = set(changes.get("processed_empty", ()))
    for item in changes.get("envelopes", ()):
        insert_envelope(db, project, run_id, item)
        affected.add(item["id"])
    for frame in changes.get("frames", ()):
        affected.add(frame["envelope_id"])
        db.execute(
            """INSERT INTO input_frames(project_id,run_id,envelope_id,frame_index,core_event_id,scheduled_time_us,
               stimulus,labels,channel_count,status,reason,scheduled_revision,source_policy)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(envelope_id,frame_index) DO NOTHING""",
            (
                project,
                run_id,
                frame["envelope_id"],
                frame["frame_index"],
                frame.get("core_event_id"),
                frame["scheduled_time_us"],
                Jsonb(frame["stimulus"]),
                Jsonb(frame.get("labels", {})),
                frame["channel_count"],
                frame.get("status", "scheduled"),
                frame.get("reason"),
                revision,
                Jsonb(frame["source_policy"] | {"resolved_at_us": frame.get("policy_resolved_at_us")})
                if "source_policy" in frame
                else None,
            ),
        )
    for frame in changes.get("delivered", ()):
        affected.add(frame["envelope_id"])
        updated = db.execute(
            """UPDATE input_frames SET status='delivered',delivered_time_us=%s,core_sequence=%s,delivered_revision=%s,input_gate=%s
               WHERE run_id=%s AND envelope_id=%s AND frame_index=%s AND core_event_id=%s RETURNING envelope_id""",
            (
                frame["delivered_time_us"],
                frame["core_sequence"],
                revision,
                Jsonb(frame["input_gate"]) if "input_gate" in frame else None,
                run_id,
                frame["envelope_id"],
                frame["frame_index"],
                frame["core_event_id"],
            ),
        ).fetchone()
        if updated is None:
            raise ValueError("delivered frame has no matching scheduled provenance")
    for envelope_id in affected:
        db.execute(
            """UPDATE input_envelopes e SET delivered_count=q.delivered,filtered_count=q.filtered,
               last_delivery_us=q.last_delivery, status=CASE WHEN q.delivered+q.filtered=e.frame_count THEN 'completed' ELSE 'scheduled' END,
               updated_at=now(), processed_revision=COALESCE(e.processed_revision,%s) FROM (SELECT count(*) FILTER(WHERE status='delivered') AS delivered,
               count(*) FILTER(WHERE status='filtered') AS filtered, max(delivered_time_us) AS last_delivery
               FROM input_frames WHERE envelope_id=%s) q WHERE e.run_id=%s AND e.id=%s""",
            (revision, envelope_id, run_id, envelope_id),
        )
    for item in changes.get("rejected", ()):
        db.execute(
            "UPDATE input_envelopes SET status='rejected',error=%s,updated_at=now(),processed_revision=%s WHERE run_id=%s AND id=%s",
            (item["reason"], revision, run_id, item["envelope_id"]),
        )


def list_envelopes(database, project, run_id, *, after=0, limit=30, source=None, status=None):
    database.get_run(project, run_id)
    with database.tx(project) as db:
        rows = db.execute(
            """SELECT id,ordinal,adapter_id,adapter_version,source,configuration,configuration_hash,payload_hash,
               frame_count,channel_count,delivered_count,filtered_count,status,error,created_at,updated_at
               FROM input_envelopes WHERE run_id=%s AND ordinal>%s
               AND (%s::text IS NULL OR source=%s) AND (%s::text IS NULL OR status=%s) ORDER BY ordinal LIMIT %s""",
            (run_id, after, source, source, status, status, limit + 1),
        ).fetchall()
        counts = db.execute(
            "SELECT status,count(*) AS count FROM input_envelopes WHERE run_id=%s GROUP BY status", (run_id,)
        ).fetchall()
    return {
        "rows": [public_envelope(r) for r in rows[:limit]],
        "more": len(rows) > limit,
        "next": rows[limit - 1]["ordinal"] if len(rows) >= limit else after,
        "counts": counts,
    }


def detail(database, project, run_id, envelope_id, *, after=-1, limit=100):
    with database.tx(project, repeatable=True) as db:
        row = db.execute("SELECT * FROM input_envelopes WHERE id=%s AND run_id=%s", (envelope_id, run_id)).fetchone()
        if row is None:
            raise NotFound()
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


def evidence_rows(db, run_id, revision):
    """Reconstruct statuses at the chosen checkpoint, not today's delivery status."""
    yield from stream_rows(
        db,
        """SELECT e.id AS envelope_id,e.adapter_id,e.adapter_version,e.source,e.payload_hash,e.configuration_hash,
               f.frame_index,f.core_event_id,f.scheduled_time_us,f.stimulus,f.labels,f.reason,f.scheduled_revision,f.source_policy,
               CASE WHEN f.status='delivered' AND f.delivered_revision>%s THEN 'scheduled' ELSE f.status END AS status,
               CASE WHEN f.delivered_revision<=%s THEN f.delivered_time_us END AS delivered_time_us,
               CASE WHEN f.delivered_revision<=%s THEN f.core_sequence END AS core_sequence,
               CASE WHEN f.delivered_revision<=%s THEN f.input_gate END AS input_gate
               FROM input_frames f JOIN input_envelopes e ON e.id=f.envelope_id
               WHERE f.run_id=%s AND f.scheduled_revision<=%s ORDER BY e.ordinal,f.frame_index""",
        (revision, revision, revision, revision, run_id, revision),
    )


def export_stream(database, project, run_id, *, records, format, source=None):
    with database.tx(project, repeatable=True) as db:
        run = db.execute("SELECT revision,time_us FROM runs WHERE id=%s", (run_id,)).fetchone()
        if run is None:
            raise NotFound()
        cursor = db.cursor(name="sensory_export")
        if records == "envelopes":
            cursor.execute(
                "SELECT * FROM input_envelopes WHERE run_id=%s AND (%s::text IS NULL OR source=%s) ORDER BY ordinal",
                (run_id, source, source),
            )
        else:
            cursor.execute(
                "SELECT f.*,e.source,e.adapter_id,e.payload_hash,e.configuration_hash FROM input_frames f JOIN input_envelopes e ON e.id=f.envelope_id WHERE f.run_id=%s AND (%s::text IS NULL OR e.source=%s) ORDER BY e.ordinal,f.frame_index",
                (run_id, source, source),
            )
        if format == "jsonl":
            yield (
                json.dumps(
                    {
                        "schema": "threemind.input-audit/1",
                        "records": records,
                        "run_id": str(run_id),
                        "checkpoint_revision": run["revision"],
                        "scope": "current database snapshot; accepted carriers may not yet be scheduled",
                    }
                )
                + "\n"
            )
        fields = [column.name for column in cursor.description if column.name != "request_hash"]
        if format == "csv":
            header = io.StringIO(newline="")
            csv.writer(header).writerow(fields)
            yield header.getvalue()
        for row in cursor:
            row.pop("request_hash", None)
            if format == "jsonl":
                yield json.dumps(row, ensure_ascii=False, default=str, allow_nan=False) + "\n"
            else:
                buffer = io.StringIO(newline="")
                writer = csv.writer(buffer)
                values = []
                for key in fields:
                    value = row[key]
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False, default=str)
                    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                        value = "'" + value  # Spreadsheet formula safety; JSONL retains exact raw strings.
                    values.append(value)
                writer.writerow(values)
                yield buffer.getvalue()
