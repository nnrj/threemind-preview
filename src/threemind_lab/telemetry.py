"""Physical sampling host and checkpoint-atomic telemetry evidence."""

from __future__ import annotations

import csv
import io
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from threemind_runtime.telemetry import TELEMETRY_CONFIGS, TELEMETRY_VERSION, ExecutionMeter, TelemetryEncoder

from .inputs import envelope_record


class RuntimeTelemetry:
    def __init__(self, spec, run_id, *, clock=time.monotonic, probe=None):
        self.clock, self.run_id = clock, str(run_id)
        self.configs = {
            cls.scope: getattr(spec, root)
            for root, cls in TELEMETRY_CONFIGS.items()
            if getattr(spec, root).enabled and spec.source_policies.resolve(f"{cls.scope}-telemetry")["enabled"]
        }
        self.encoders = {scope: TelemetryEncoder(spec.seed, cfg) for scope, cfg in self.configs.items()}
        self.seed = spec.seed
        self.session_id = str(uuid4())
        now = clock()
        self.next_due = {scope: now + cfg.sample_interval_ms / 1000 for scope, cfg in self.configs.items()}
        # Separate execution windows so independent sampling periods stay honest.
        self.meters = {scope: ExecutionMeter(now) for scope in self.configs if scope != "host"}
        self.probe = probe
        if self.configs and self.probe is None:
            from threemind_runtime.telemetry_probe import SystemTelemetryProbe

            self.probe = SystemTelemetryProbe()
        if self.probe and self.configs:
            self.probe.reset_rate_baselines(set(self.configs) & {"host", "process"})
        self.last = None

    def measured(self, wall_s, cpu_s, latency_s):
        for meter in self.meters.values():
            meter.add(wall_s, cpu_s, latency_s)

    def poll(self, inputs, emit, *, source_enabled):
        now = self.clock()
        due = {scope for scope, deadline in self.next_due.items() if now >= deadline}
        if not due or not source_enabled:
            return
        scopes = due & {"host", "process"}
        host, process = self.probe.collect(now, scopes) if scopes else ({}, {})
        readings = {
            "host": {k: v.to_dict() for k, v in host.items()},
            "process": {k: v.to_dict() for k, v in process.items()},
        }
        context = {}
        for scope in due - {"host"}:
            values, context[scope] = self.meters[scope].close(now)
            if scope == "runtime":
                readings[scope] = values
            else:
                readings[scope].update(
                    {
                        "scheduler_latency_ms": values["scheduler_latency_ms"],
                        "tick_execution_time_ms": values["epoch_execution_time_ms"],
                    }
                )
        sample_id = str(uuid4())
        result = {
            "schema": TELEMETRY_VERSION,
            "sample_id": sample_id,
            "session_id": self.session_id,
            "captured_at_utc": datetime.now(UTC).isoformat(),
            "monotonic_s": now,
            "captured_simulation_us": str(inputs.engine.time_us),
            "worker_pid": os.getpid(),
            "run_id": self.run_id,
            "backend": self.probe.backend,
            "context": context,
            "scopes": {},
        }
        for scope in sorted(due):
            cfg = self.configs[scope]
            # Never backdate physical experience or inject a measurement into the call it measured.
            delivery = inputs.engine.time_us + cfg.sample_interval_ms * 1000
            stimulus, audit = self.encoders[scope].encode(readings[scope], monotonic_s=now, delivery_us=delivery)
            config = {
                "seed": self.seed,
                "scope": scope,
                "parameters": asdict(cfg),
                "session_id": self.session_id,
                "sample_id": sample_id,
                "feedback_delay_us": str(cfg.sample_interval_ms * 1000),
            }
            item = envelope_record(
                inputs.identity(f"telemetry:{sample_id}:{scope}"),
                f"{scope}-telemetry",
                f"{scope}-telemetry",
                {"sample_id": sample_id},
                config,
                1 if stimulus else 0,
                len(stimulus.channels) if stimulus else 0,
                version=TELEMETRY_VERSION,
            )
            inputs.changes["envelopes"].append(item)
            if stimulus:
                inputs.schedule(item, [{"stimulus": stimulus}])
            else:
                inputs.changes.setdefault("processed_empty", []).append(item["id"])
            result["scopes"][scope] = {
                "envelope_id": item["id"],
                "configuration": config,
                "measurements": audit,
                "channel_count": item["channel_count"],
                "scheduled_time_us": str(delivery) if stimulus else None,
                "sampling_lateness_ms": max(0, now - self.next_due[scope]) * 1000,
            }
            self.next_due[scope] = now + cfg.sample_interval_ms / 1000
        self.last = result
        emit(
            {
                "key": f"telemetry:{sample_id}",
                "time_us": str(inputs.engine.time_us),
                "kind": "telemetry_sample",
                "payload": result,
            }
        )

    def capture(self):
        # OS counters are not rewindable. Pending frozen pulses live in InputBus.
        return {
            "version": TELEMETRY_VERSION,
            "session_id": self.session_id,
            "last_sample_id": self.last["sample_id"] if self.last else None,
            "resume": "new physical session; reset counter and encoder baselines",
        }


def export_stream(database, project, run_id, *, scope=None, format="jsonl"):
    with database.tx(project, repeatable=True) as db, db.cursor(name="telemetry_export") as cursor:
        cursor.execute(
            "SELECT id,time_us,payload,commit_revision FROM events WHERE run_id=%s AND kind='telemetry_sample' "
            "AND (%s::text IS NULL OR payload->'scopes' ? %s) ORDER BY id",
            (run_id, scope, scope),
        )
        if format == "csv":
            buffer = io.StringIO(newline="")
            writer = csv.writer(buffer)
            writer.writerow(
                [
                    "sample_id",
                    "scope",
                    "metric",
                    "captured_at_utc",
                    "simulation_us",
                    "scheduled_us",
                    "available",
                    "raw_value",
                    "unit",
                    "normalized_level",
                    "smoothed_level",
                    "rise",
                    "fall",
                    "reference",
                    "reference_source",
                    "unavailable_reason",
                    "envelope_id",
                    "commit_revision",
                ]
            )
            yield ("\ufeff" + buffer.getvalue()).encode()
        for row in cursor:
            if format == "jsonl":
                yield (
                    json.dumps({**row, "time_us": str(row["time_us"])}, ensure_ascii=False, allow_nan=False) + "\n"
                ).encode()
                continue
            sample = row["payload"]
            for name, value in sample["scopes"].items():
                if scope and name != scope:
                    continue
                for metric, reading in value["measurements"].items():
                    raw = reading["raw"]
                    buffer.seek(0)
                    buffer.truncate(0)
                    writer.writerow(
                        [
                            sample["sample_id"],
                            name,
                            metric,
                            sample["captured_at_utc"],
                            str(row["time_us"]),
                            value["scheduled_time_us"],
                            raw.get("available"),
                            raw.get("raw_value"),
                            raw.get("unit"),
                            reading.get("normalized_level"),
                            reading.get("smoothed_level"),
                            reading.get("rise"),
                            reading.get("fall"),
                            reading.get("reference"),
                            reading.get("reference_source"),
                            raw.get("unavailable_reason"),
                            value["envelope_id"],
                            row["commit_revision"],
                        ]
                    )
                    yield buffer.getvalue().encode()
