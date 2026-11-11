"""Recoverable, read-only observation hosting; no Lab, database or UI dependency."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict

from .activity_readout import ActivityReader
from .bus import OutputBus
from .readout_config import READOUT_VERSION, ActivityReadoutConfig, TemporalReadoutConfig
from .readouts import StructuralReader, TemporalReader, signature


class ReadoutHost:
    def __init__(self, spec, run_id, time_us, *, state=None, record):
        self.spec, self.run_id, self.record = spec, str(run_id), record
        self.bytes = 0
        self.deliveries = []
        saved = state if state and state.get("run_id") == self.run_id else {}
        self.observation_metadata = copy.deepcopy(saved.get("observation_metadata", {}))
        self.annotations = copy.deepcopy(saved.get("annotations", {}))
        self.activity_config = getattr(spec, "activity_readout", ActivityReadoutConfig(enabled=False))
        previous_activity = saved.get("activity")
        if previous_activity and asdict(ActivityReadoutConfig(**previous_activity["configuration"])) != asdict(
            self.activity_config
        ):
            old = ActivityReader(ActivityReadoutConfig(**previous_activity["configuration"]), previous_activity)
            for value in old.close(time_us, "configuration_changed"):
                self.emit(value)
            previous_activity = None
        self.activity = ActivityReader(self.activity_config, previous_activity)
        self.next_activity = int(saved.get("next_activity_us", time_us)) if previous_activity else time_us
        previous = saved.get("temporal")
        if previous and previous["configuration"] != asdict(spec.temporal_readout):
            old = TemporalReader(TemporalReadoutConfig(**previous["configuration"]), previous)
            for value in old.close(time_us, "configuration_changed"):
                self.emit(value)
            previous = None
        self.temporal = TemporalReader(spec.temporal_readout, previous)
        previous = saved.get("structural")
        if previous and previous["configuration"] != asdict(spec.structural_readout):
            previous = None
        self.structural = StructuralReader(spec.structural_readout, previous)
        self.next_structural = (
            int(saved.get("next_structural_us", time_us))
            if saved.get("structural", {}).get("configuration") == asdict(spec.structural_readout)
            else time_us
        )
        self.next_temporal = (
            int(saved.get("next_temporal_us", time_us))
            if saved.get("temporal", {}).get("configuration") == asdict(spec.temporal_readout)
            else time_us
        )
        self.bus = OutputBus()
        self.bus.subscribe("research-readouts", self.consume)

    @property
    def enabled(self):
        return (
            self.spec.structural_readout.enabled or self.spec.temporal_readout.enabled or self.activity_config.enabled
        )

    @property
    def next_us(self):
        values = []
        if self.spec.structural_readout.enabled:
            values.append(self.next_structural)
        if self.spec.temporal_readout.enabled:
            values.append(self.next_temporal)
        if self.activity_config.enabled:
            values.append(self.next_activity)
        return min(values) if values else None

    def emit(self, value):
        from .chat_readout import display_readout

        if value["kind"] == "temporal_readout":
            value = value | {
                "analysis_id": value.get("analysis_id", "activity-steady-state"),
                "chat_primary": bool(value.get("analysis_schema")) or not self.activity_config.enabled,
            }
        value = value | self.observation_metadata | {"chat": display_readout(value)}
        # One structural observation per (time, Core sequence, configuration).
        # Hash its identity rather than serializing every raw node a second
        # time. The event payload remains complete and immutable in storage.
        key = value.get("window_id") or signature(
            [
                "threemind.structural-observation-key/1",
                value["schema"],
                value["time_us"],
                value["sequence"],
                value["configuration"],
                value.get("raw_observation", {}).get("schema"),
            ]
        )
        self.bytes += len(json.dumps(value, ensure_ascii=False).encode())
        self.record(
            {
                "key": f"readout:{value['kind']}:{key}",
                "time_us": str(value.get("end_us", value.get("time_us"))),
                "kind": value["kind"],
                "payload": value,
            }
        )

    def delivered(self, provenance):
        if not provenance:
            return
        if self.enabled:
            self.deliveries.append(copy.deepcopy(provenance))
        for key, values in provenance.get("labels", {}).items():
            self.annotations[key] = sorted(set(self.annotations.get(key, [])) | set(values))

    def begin_observation(self, engine, observation_id):
        key = self.activity.begin_observation(engine.time_us, observation_id)
        self.next_activity = engine.time_us
        self.observe(engine)
        return key

    def observe(self, engine, *, force=False):
        at = engine.time_us
        needed = force or bool(self.deliveries) or self.next_us is not None and at >= self.next_us
        if not self.enabled or not needed:
            return
        if getattr(engine, "dynamics", None) == "threemind.lif/1":
            self.observation_metadata = {
                "kernel_id": "threemind.lif/1",
                "observation_quantity": "normalized-depolarization",
                "observation_unit": "1",
                "observation_formula": "clip((V_mV-rest_mV)/(threshold_mV-rest_mV),0,1)",
                "physical_state_source": "checkpoint.membranes; spikes are separately recorded events",
            }
        nodes = engine.observation_nodes()
        present = {str(n["channel"]) for n in nodes}
        self.annotations = {key: values for key, values in self.annotations.items() if key in present}
        labels = {
            str(n["id"]): list(self.annotations[str(n["channel"])])
            for n in nodes
            if str(n["channel"]) in self.annotations
        }
        structural = self.spec.structural_readout.enabled and (force or at >= self.next_structural)
        legacy_due = (
            force
            or bool(self.deliveries)
            or structural
            or self.spec.temporal_readout.enabled
            and at >= self.next_temporal
        )
        selected = self.structural.candidates(nodes) if structural else []
        edges = engine.induced_edges([n["id"] for n in selected]) if selected else []
        frame = {
            "time_us": at,
            "sequence": engine.sequence,
            "nodes": nodes,
            "edges": edges,
            "structural": structural,
            "temporal": self.spec.temporal_readout.enabled
            and (self.activity_config.analysis_version == 1 or legacy_due),
            "activity": self.activity_config.enabled
            and (
                self.activity_config.analysis_version == 1 or force or bool(self.deliveries) or at >= self.next_activity
            ),
            "deliveries": self.deliveries,
            "annotations": labels,
        }
        self.deliveries = []
        # observation_nodes/induced_edges return detached values. This host
        # never reuses the frame after its synchronous evidence subscription.
        self.bus.publish(frame, owned=True)
        if structural:
            self.next_structural = at + self.spec.structural_readout.interval_us
        if self.spec.temporal_readout.enabled and at >= self.next_temporal:
            self.next_temporal = at + self.spec.temporal_readout.interval_us
        if self.activity_config.enabled and at >= self.next_activity:
            self.next_activity = at + self.activity_config.interval_us

    def consume(self, frame):
        if frame["structural"]:
            record = self.structural.consume(
                frame["time_us"], frame["sequence"], frame["nodes"], frame["edges"], annotations=frame["annotations"]
            )
            if record:
                self.emit(record)
        if frame["temporal"]:
            for record in self.temporal.consume(
                frame["time_us"],
                frame["sequence"],
                frame["nodes"],
                frame["deliveries"],
                annotations=frame["annotations"],
            ):
                self.emit(record)
        if frame.get("activity"):
            for record in self.activity.consume(
                frame["time_us"],
                frame["sequence"],
                frame["nodes"],
                frame["deliveries"],
                annotations=frame["annotations"],
            ):
                self.emit(record)

    def capture(self):
        return {
            "schema": READOUT_VERSION,
            "run_id": self.run_id,
            "annotations": copy.deepcopy(self.annotations),
            "next_structural_us": str(self.next_structural),
            "next_temporal_us": str(self.next_temporal),
            "structural": self.structural.capture(),
            "temporal": self.temporal.capture(),
            **(
                {"activity": self.activity.capture(), "next_activity_us": str(self.next_activity)}
                if self.activity_config.enabled or self.activity.windows
                else {}
            ),
            **({"observation_metadata": copy.deepcopy(self.observation_metadata)} if self.observation_metadata else {}),
        }

    def close(self, time_us, reason):
        for value in self.temporal.close(time_us, reason):
            self.emit(value)
        for value in self.activity.close(time_us, reason):
            self.emit(value)
