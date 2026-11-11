"""Bounded temporal-window experiments on independent, fully inherited states."""

import io
import time
import zipfile
from dataclasses import asdict
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .calibration import MAX_PACKAGE, FiniteDose, encode
from .codec import ArtifactCodec
from .host import create_engine
from .inheritance import BIRTH_RULE, birth
from .readout_config import ActivityReadoutConfig, TemporalReadoutConfig
from .readout_session import SESSION_VERSION, ReadoutSession
from .sensory import TEXT_VERSION, TextSensor
from .source_policies import SourcePolicies

VERSION = "threemind.temporal-probe/1"


class TemporalProbeProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["temporal"] = "temporal"
    cues: list[str] = Field(default_factory=lambda: ["甲", "乙"], min_length=1, max_length=8)
    intensities: list[FiniteDose] = Field(default_factory=lambda: [1.0], min_length=1, max_length=6)
    route: Literal["birth", "continuation"] = "continuation"
    blank_us: int = Field(default=0, strict=True, ge=0, le=10_000_000)
    learning_during_probe: bool | None = Field(default=None, strict=True)
    temporal_readout: TemporalReadoutConfig = Field(default_factory=TemporalReadoutConfig)
    activity_readout: ActivityReadoutConfig | None = None
    max_wall_seconds: int = Field(default=60, strict=True, ge=1, le=300)

    @field_validator("cues")
    @classmethod
    def carriers(cls, values):
        if len(set(values)) != len(values) or any(not v.strip() or len(v) > 128 for v in values):
            raise ValueError("use distinct complete UTF-8 carriers, at most 128 characters each")
        for value in values:
            value.encode("utf-8")
        return values

    @field_validator("intensities")
    @classmethod
    def distinct(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("intensities must be distinct")
        return values


def calibrate_temporal(
    image, *, seed, sensor_config, protocol, backend="native", guard=None, provenance=None, source_context=None
):
    started = time.monotonic()
    protocol = TemporalProbeProtocol.model_validate(protocol)
    state = image.to_dict()
    if len(image.payload) > MAX_PACKAGE or len(state["nodes"]) > 2000 or len(state["edges"]) > 100000:
        raise ValueError("temporal probe exceeds the existing 64 MiB / 2000 node / 100000 edge source budget")
    sensor = TextSensor(seed, sensor_config)
    policies = SourcePolicies(**(source_context or {}).get("protocol", {}).get("source_policies", {}))
    origin = birth(image) if protocol.route == "birth" else image
    config = {"structural_readout": {"enabled": False}, "temporal_readout": asdict(protocol.temporal_readout)}
    use_activity = protocol.activity_readout is not None and protocol.activity_readout.enabled
    primary_config = protocol.activity_readout if use_activity else protocol.temporal_readout
    if protocol.activity_readout is not None:
        config["activity_readout"] = asdict(protocol.activity_readout)
    output, rows, exhausted = io.BytesIO(), [], False
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        archive.writestr("source.tmind", ArtifactCodec.encode(image))
        for index, (cue, dose) in enumerate((c, d) for d in protocol.intensities for c in protocol.cues):
            if exhausted or time.monotonic() - started > protocol.max_wall_seconds:
                rows.append(
                    {
                        "id": f"probe-{index}",
                        "cue": cue,
                        "intensity": dose,
                        "classification": "not_observed",
                        "reason": "batch_budget",
                        "temporal": None,
                    }
                )
                continue
            engine = create_engine(state=origin, backend=backend)
            if protocol.learning_during_probe is not None:
                engine.reconfigure(
                    type(engine.config)(**(engine.config.to_dict() | {"plasticity": protocol.learning_during_probe}))
                )
            records, deliveries = [], []
            initial_hash, envelope = engine.capture_state().digest, str(uuid4())
            inherited = None
            if source_context and protocol.route == "continuation":
                readouts = source_context.get("readouts")
                if readouts:
                    inherited = {
                        "schema": SESSION_VERSION,
                        "session_id": readouts["run_id"],
                        "input_bus": source_context.get("input_bus"),
                        "readouts": readouts,
                    }
            session = ReadoutSession(
                engine,
                record=records.append,
                config=config,
                state=inherited,
                policies=policies,
                event_sink=lambda event, audit, deliveries=deliveries: deliveries.append(audit) if audit else None,
            )

            def budget():
                if time.monotonic() - started > protocol.max_wall_seconds:
                    raise TimeoutError("wall_budget")
                # A batch ends before starting another large package; no records are silently omitted.
                if guard:
                    guard()

            reason = None
            try:
                session.advance_to(engine.time_us + protocol.blank_us, guard=budget)
                at = engine.time_us
                if engine.life == "dead":
                    reason = "source_dead"
                elif not sensor.config.enabled:
                    reason = "sensor_disabled"
                elif not policies.resolve("manual-cli-text")["enabled"]:
                    reason = "input_source_disabled"
                elif not primary_config.enabled or not primary_config.trigger_manual:
                    reason = "reader_disabled"
                else:
                    session.schedule(sensor.frames(cue, dose), envelope_id=envelope)
                    deadline = at + primary_config.max_response_us
                    session.advance_to(
                        deadline,
                        guard=budget,
                        stop_when=lambda records=records, envelope=envelope: any(
                            r["kind"] == "temporal_readout"
                            and r["payload"]["envelope_id"] == envelope
                            and (bool(r["payload"].get("analysis_schema")) == use_activity)
                            for r in records
                        ),
                    )
                    session.host.close(engine.time_us, "run_ended")
            except (TimeoutError, MemoryError) as error:
                reason, exhausted = str(error) or "resource_budget", True
                session.host.close(engine.time_us, "run_ended")
            measured = next(
                (
                    r["payload"]
                    for r in records
                    if r["kind"] == "temporal_readout"
                    and r["payload"]["envelope_id"] == envelope
                    and (bool(r["payload"].get("analysis_schema")) == use_activity)
                ),
                None,
            )
            row = {
                "id": f"probe-{index}",
                "cue": cue,
                "intensity": dose,
                "envelope_id": envelope,
                "classification": measured["classification"] if measured else "not_observed",
                "reason": reason or (measured["reason"] if measured else "no_observed_delivery"),
                "start_hash": initial_hash,
                "final_hash": engine.capture_state().digest,
                "temporal": measured,
                "learning_during_probe": engine.config.plasticity,
                "context_inherited": inherited is not None,
            }
            rows.append(row)
            archive.writestr(f"probes/{index}/readouts.json", encode(records))
            archive.writestr(f"probes/{index}/deliveries.json", encode(deliveries))
            archive.writestr(f"probes/{index}/context.json", encode(session.capture()))
            archive.writestr(f"probes/{index}/final.tmind", ArtifactCodec.encode(engine.capture_state()))
            if output.tell() > MAX_PACKAGE // 2:
                exhausted = True
        result = {
            "schema": VERSION,
            "source_hash": image.digest,
            "source_unchanged": image.digest == origin.digest if protocol.route == "continuation" else True,
            "backend": backend,
            "dynamics": state["dynamics"],
            "sensor_version": TEXT_VERSION,
            "sensor_config": asdict(sensor_config),
            "source_policies": asdict(policies),
            "seed": seed,
            "protocol": protocol.model_dump(mode="json"),
            "rows": rows,
            "inheritance": BIRTH_RULE if protocol.route == "birth" else None,
            "provenance": provenance,
            "elapsed_seconds": time.monotonic() - started,
            "batch_budget_reached": exhausted,
            "raw_scope": "complete sampled-node aggregates and recorded window series; not continuous per-node trajectories",
            "missing_values_are_zero": False,
            "rows_are_independent_replicates": False,
        }
        archive.writestr("result.json", encode(result))
    if output.tell() > MAX_PACKAGE:
        raise ValueError("temporal evidence exceeds package budget; no incomplete success is published")
    return result, output.getvalue()
