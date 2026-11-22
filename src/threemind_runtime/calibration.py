"""Isolated sensory/probe measurement; no Lab dependency and no Core rule changes."""

from __future__ import annotations

import io
import json
import time
import zipfile
from collections import Counter
from dataclasses import asdict, replace
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from threemind_core import StateImage

from .bus import InputBus
from .codec import ArtifactCodec
from .host import create_engine
from .inheritance import birth, birth_rule
from .sensory import TEXT_VERSION, TextSensor, TextSensorConfig

VERSION = "threemind.probe-calibration/1"
MAX_CELLS = 2_000_000
MAX_PACKAGE = 64 * 1024 * 1024
FiniteDose = Annotated[float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]


class CalibrationProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cues: list[str] = Field(default_factory=lambda: ["甲", "乙"], min_length=1, max_length=8)
    terms: list[str] = Field(default_factory=lambda: ["松子", "铃铛"], min_length=2, max_length=8)
    intensities: list[FiniteDose] = Field(default_factory=lambda: [1.0, 2.0, 4.0], min_length=1, max_length=6)
    route: Literal["birth", "continuation"] = "birth"
    blank_us: int = Field(default=800000, strict=True, ge=0, le=10_000_000)
    window_us: int = Field(default=1000000, strict=True, ge=20000, le=5_000_000)
    sample_us: int = Field(default=20000, strict=True, ge=1000, le=100000)
    score_from_us: int = Field(default=200000, strict=True, ge=0, le=5_000_000)
    learning_during_probe: bool = Field(default=False, strict=True)

    @field_validator("cues", "terms")
    @classmethod
    def words(cls, values):
        if len(set(values)) != len(values) or any(not x.strip() or len(x) > 128 for x in values):
            raise ValueError("use distinct nonempty texts of at most 128 characters")
        for word in values:
            word.encode("utf-8")
        return values

    @model_validator(mode="after")
    def grid(self):
        if (
            self.window_us % self.sample_us
            or self.score_from_us % self.sample_us
            or self.score_from_us >= self.window_us
            or len(set(self.intensities)) != len(self.intensities)
        ):
            raise ValueError("sample grid must cover the score interval exactly; intensities must be unique")
        return self


def parse_protocol(value):
    """Explicit mode preserves old fixed-window jobs without upgrading their evidence."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if value.get("mode") == "temporal":
        from .temporal_probe import TemporalProbeProtocol

        return TemporalProbeProtocol.model_validate(value)
    return CalibrationProtocol.model_validate(value)


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def template(sensor, text):
    """All frames participate; labels never enter the measurement or Core."""
    values = Counter()
    if not sensor.config.enabled:
        return {}
    for frame in sensor.frames(text):
        for channel, value in frame["stimulus"].channels:
            values[channel] += value
    return dict(values)


def transduction(sensor, protocol):
    terms = {word: template(sensor, word) for word in protocol.terms}
    cues = {word: template(sensor, word) for word in protocol.cues}
    shared = Counter(channel for channels in terms.values() for channel in channels)
    direct = set().union(*(set(channels) for channels in cues.values()))
    masks = {
        word: {c: v for c, v in values.items() if c not in direct and shared[c] == 1} for word, values in terms.items()
    }
    return {
        "terms": terms,
        "cues": cues,
        "masks": masks,
        "coverage": {
            w: {
                "channels": len(v),
                "exclusive_channels": len(masks[w]),
                "retained_weight_fraction": sum(masks[w].values()) / sum(v.values()) if sum(v.values()) else 0,
                "scorable": sum(masks[w].values()) > 0,
            }
            for w, v in terms.items()
        },
        "exclusion_scope": "scores only; every node activation remains in the raw package",
    }


def calibrate(
    image: StateImage,
    *,
    seed: int,
    sensor_config: TextSensorConfig,
    protocol: CalibrationProtocol,
    backend="native",
    guard=None,
    provenance=None,
    source_context=None,
):
    """Return a small display result and a complete bounded evidence ZIP.

    Transport counters and signal events come from the existing Core API. Signal
    arrivals may aggregate several accepted edges; they are not per-edge counts.
    No rejected-edge count or unobserved emission is inferred from this trace.
    """
    if getattr(protocol, "mode", None) == "temporal":
        from .temporal_probe import calibrate_temporal

        return calibrate_temporal(
            image,
            seed=seed,
            sensor_config=sensor_config,
            protocol=protocol,
            backend=backend,
            guard=guard,
            provenance=provenance,
            source_context=source_context,
        )
    started, original_hash = time.monotonic(), image.digest
    if len(image.payload) > MAX_PACKAGE:
        raise ValueError("calibration source state exceeds its byte budget")
    state = image.to_dict()
    if len(state["nodes"]) > 2000 or len(state["edges"]) > 100000:
        raise ValueError("calibration budget: at most 2000 nodes and 100000 edges")
    sensor = TextSensor(seed, sensor_config)
    identities = {n["channel"] for n in state["nodes"]}
    for cue in protocol.cues:
        identities.update(template(sensor, cue))
    cells = (
        len(identities)
        * (1 + protocol.window_us // protocol.sample_us)
        * (1 + len(protocol.cues) * len(protocol.intensities))
    )
    if cells > MAX_CELLS or len(image.payload) > MAX_PACKAGE:
        raise ValueError("calibration trace exceeds its declared cell/state budget; reduce probes or sampling")
    mapping = transduction(sensor, protocol)
    origin = birth(image) if protocol.route == "birth" else image
    buffer = io.BytesIO()
    rows, samples_written = [], 0

    def check():
        if time.monotonic() - started > 60 or buffer.tell() > MAX_PACKAGE:
            raise ValueError("calibration time/evidence budget exceeded; no truncated success is returned")
        if guard:
            guard()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        archive.writestr("source.tmind", ArtifactCodec.encode(image))
        cases = [(None, 0.0)] + [(cue, dose) for dose in protocol.intensities for cue in protocol.cues]
        for index, (cue, dose) in enumerate(cases):
            check()
            engine = create_engine(state=origin, backend=backend)
            engine.reconfigure(
                type(engine.config)(**(engine.config.to_dict() | {"plasticity": protocol.learning_during_probe}))
            )
            bus, events, frames, raw, curve = InputBus(engine), [], [], [], []
            event_scalars = 0

            def observe(event, bus=bus, events=events):
                nonlocal event_scalars
                audit = bus.observe(event)
                if event["kind"] != "observation":
                    event_scalars += len(event["payload"].get("values", event["payload"].get("channels", [])))
                    if event_scalars > MAX_CELLS:
                        raise ValueError("calibration event budget exceeded")
                    events.append(event | ({"input_audit": audit} if audit else {}))

            if protocol.route == "continuation":
                engine.advance_to(engine.time_us + protocol.blank_us, observe)
            at = engine.time_us
            probe_event_start = len(events)
            before, probe_origin = engine.metrics()["transport"], engine.capture_state().digest
            available = engine.life != "dead"
            if cue and available and sensor_config.enabled:
                for frame in sensor.frames(cue, dose):
                    stimulus = replace(frame["stimulus"], time_us=at + frame["stimulus"].time_us)
                    entry = bus.schedule(stimulus, {"source": "manual-cli-text", "calibration_case": index})
                    frames.append({"stimulus": stimulus.to_dict(), "labels": frame["labels"], "receipt": entry})
            # Raw retains zeros, identities, all input frames, all signal arrivals
            # and full final state. Term templates are a separate observer view.
            for delta in range(0, protocol.window_us + 1, protocol.sample_us):
                check()
                engine.advance_to(at + delta, observe)
                activity = engine.activations()
                channels = {n["id"]: n["channel"] for n in engine.observation_nodes()}
                by_channel = {channels[n]: v for n, v in activity}
                scores = {
                    word: sum(by_channel.get(c, 0) * w for c, w in mask.items()) / sum(mask.values())
                    if sum(mask.values()) > 0 and available
                    else None
                    for word, mask in mapping["masks"].items()
                }
                metrics = engine.metrics()
                transport = {k: metrics["transport"][k] - v for k, v in before.items()}
                curve.append(
                    {
                        "offset_us": delta,
                        "time_us": str(at + delta),
                        "terms": scores,
                        "activation": metrics["activation"],
                        "saturated_fraction": metrics["saturated_fraction"],
                        "transport": transport,
                        "life": engine.life,
                    }
                )
                raw.append([str(at + delta), activity])
                samples_written += len(activity)
                if samples_written > MAX_CELLS:
                    raise ValueError("calibration actual node samples exceed the declared budget")
            endpoints = {}
            for word in protocol.terms:
                values = [r["terms"][word] for r in curve if r["offset_us"] >= protocol.score_from_us]
                endpoints[word] = (
                    (sum(values) - (values[0] + values[-1]) / 2) / (len(values) - 1)
                    if all(v is not None for v in values)
                    else None
                )
            after = engine.capture_state()
            emitted_after_start = [e for e in events[probe_event_start:] if e["kind"] == "signal"]
            delivered = sum(v for e in emitted_after_start for _, v in e["payload"]["values"])
            row = {
                "id": f"probe-{index}",
                "cue": cue,
                "intensity": dose,
                "available": available,
                "start_us": str(at),
                "start_hash": probe_origin,
                "final_hash": after.digest,
                "endpoint": endpoints,
                "curve": curve,
                "transport": curve[-1]["transport"],
                "delivered_signal_amount": delivered,
                "signal_arrival_groups": len(emitted_after_start),
                "input_frames": frames,
                "life": engine.life,
            }
            rows.append(row)
            archive.writestr(
                f"probes/{index}/trace.json",
                encode(
                    {
                        "row": row,
                        "all_node_activations": raw,
                        "node_channels": channels,
                        "events": events,
                        "input_bus": bus.capture(),
                    }
                ),
            )
            archive.writestr(f"probes/{index}/final.tmind", ArtifactCodec.encode(after))
        for row in rows[1:]:
            row["net_endpoint"] = {
                w: row["endpoint"][w] - rows[0]["endpoint"][w]
                if row["endpoint"][w] is not None and rows[0]["endpoint"][w] is not None
                else None
                for w in protocol.terms
            }
        result = {
            "schema": VERSION,
            "source_hash": original_hash,
            "dynamics": state["dynamics"],
            "backend": backend,
            "sensor_version": TEXT_VERSION,
            "sensor_config": asdict(sensor_config),
            "seed": seed,
            "protocol": protocol.model_dump(),
            "inheritance": birth_rule(state["dynamics"]) if protocol.route == "birth" else None,
            "activation_floor": state["config"]["activation_floor"],
            "propagation_interval_us": state["config"]["propagation_interval_us"],
            "mapping": mapping,
            "rows": rows,
            "source_unchanged": image.digest == original_hash,
            "raw_scope": "all node activations including zeros, frames, arrivals, initial and final model states",
            "signal_scope": "actual arrival groups may combine accepted edges; no rejected-edge count is inferred",
            "samples_written": samples_written,
            "provenance": provenance,
        }
        archive.writestr("result.json", encode(result))
    if buffer.tell() > MAX_PACKAGE:
        raise ValueError("calibration package exceeded its budget")
    return result, buffer.getvalue()
