"""Host bridge for the original Python runtime, preserving its epoch/tick model.

Simulation microseconds name environmental epochs only; an epoch may contain
several sequential old Core ticks. Viewing or advancing a partial epoch never
creates a tick. No modern dynamics or backend fallback is used.
"""

from __future__ import annotations

import copy
import heapq
import math
from dataclasses import asdict, dataclass

from threemind_core import StateImage
from threemind_core.spec import timestamp

from .unified.attention import AttentionAdjustment
from .unified.frames import SensoryFrame
from .unified.model import ModelManifest, ModelPackage
from .unified.runtime import ConsciousnessRuntime, RuntimeConfig
from .unified.sensors import TextSensorAdapter

KERNEL_ID = "unified-associative"
STATE_SCHEMA = "threemind.unified-state/1"


@dataclass(frozen=True, slots=True)
class LegacyStimulus:
    """Transport frame with the original unsigned 64-bit receptor identities.

    This is a host envelope, not a replacement of the historical sensory/Core
    algorithm. It intentionally does not pass through causal's uint32 channels.
    """

    time_us: int
    channels: dict[int, float]
    intensity: float = 1.0
    bypass_attention: bool = False
    source: str = "manual"
    external: bool = True
    delay_epochs: int = 0

    def __post_init__(self):
        timestamp(self.time_us)
        if type(self.bypass_attention) is not bool or type(self.external) is not bool:
            raise ValueError("historical frame flags must be boolean")
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("historical frame source must be nonempty")
        if type(self.delay_epochs) is not int or self.delay_epochs < 0:
            raise ValueError("historical input delay must be nonnegative epochs")
        if not math.isfinite(self.intensity) or self.intensity < 0:
            raise ValueError("historical frame intensity must be finite and nonnegative")
        for channel, value in self.channels.items():
            if type(channel) is not int or not 0 <= channel < 2**64 or not math.isfinite(value):
                raise ValueError("historical channels must be uint64 with finite signal values")

    def to_dict(self):
        return {
            "time_us": str(self.time_us),
            "channels": {str(k): v for k, v in sorted(self.channels.items())},
            "intensity": self.intensity,
            "bypass_attention": self.bypass_attention,
            "source": self.source,
            "external": self.external,
            "delay_epochs": self.delay_epochs,
        }

    @classmethod
    def from_dict(cls, value):
        known = {"time_us", "channels", "intensity", "bypass_attention", "source", "external", "delay_epochs"}
        if set(value) - known:
            raise ValueError("unknown historical stimulus fields")
        return cls(
            timestamp(value["time_us"]),
            {int(k): float(v) for k, v in value["channels"].items()},
            float(value.get("intensity", 1.0)),
            value.get("bypass_attention", False),
            value.get("source", "manual"),
            value.get("external", True),
            value.get("delay_epochs", 0),
        )


@dataclass(slots=True)
class UnifiedConfig(RuntimeConfig):
    node_payload: str = "anonymous"
    spatial_embedding: bool = False
    spatial_dimensions: int = 0
    neighborhood_enabled: bool = True
    spatial_radius: float = 2.5
    spatial_competition: float = 0.0
    sensory_encoding: str = "anonymous-distributed"

    def __post_init__(self):
        for key, value in asdict(self).items():
            if isinstance(value, float) and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{key} must be finite and nonnegative")
        self.manifest().validate()
        normalized = RuntimeConfig.from_manifest(self.manifest())
        for key, value in asdict(normalized).items():
            if getattr(self, key) != value:
                raise ValueError(f"{key} is outside the original runtime's supported range")
        if round(self.tick_seconds * 1_000_000) < 1:
            raise ValueError("historical environmental epoch must be positive")
        if not math.isfinite(self.spatial_radius) or self.spatial_radius <= 0:
            raise ValueError("spatial_radius must be positive")

    @property
    def step_us(self):
        return round(self.tick_seconds * 1_000_000)

    @property
    def seed(self):
        return self.random_seed

    def to_dict(self):
        return asdict(self)

    def manifest(self):
        return ModelManifest(
            kernel_id=KERNEL_ID,
            node_payload=self.node_payload,
            spatial_embedding=self.spatial_embedding,
            spatial_dimensions=self.spatial_dimensions,
            parameters=self.to_dict(),
        )

    def runtime(self):
        return RuntimeConfig(**{key: getattr(self, key) for key in RuntimeConfig.__dataclass_fields__})


def presets():
    """Original UI presets; they are templates of one runtime, never kernels."""
    source = {
        "revision": "0c5e64a114fa33ca18c7106724388a8b3d0e352d",
        "path": "legacy/ui/src/ManagementPages.tsx",
        "runtime_revision": "97d8592",
    }
    result = []
    for key, label, overrides in (
        ("labeled-feature-v1", "V1 · 符号关联基线", {"node_payload": "labeled", "sensory_encoding": "legacy-labeled"}),
        ("anonymous-sensory-v2", "V2 · 匿名感官模型", {}),
        ("anonymous-spatial-v3", "V3 · 匿名空间模型", {"spatial_embedding": True, "spatial_dimensions": 3}),
    ):
        result.append(
            {
                "id": key,
                "label": label,
                "kernel_id": KERNEL_ID,
                "config": UnifiedConfig(**overrides).to_dict(),
                "original_preset": key,
                "source": dict(source),
            }
        )
    return result


def _tuple(value):
    return tuple(_tuple(v) for v in value) if isinstance(value, list) else value


class _Silence:
    def __init__(self, nodes=(), edges=()):
        self.nodes, self.edges = set(nodes), {tuple(e) for e in edges}

    def node_silenced(self, node):
        return node in self.nodes

    def edge_silenced(self, source, target):
        return (source, target) in self.edges

    def describe(self):
        return {"nodes": sorted(self.nodes), "edges": [list(e) for e in sorted(self.edges)]}


class UnifiedEngine:
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None, *, consciousness_id=None):
        if state is not None and config is not None:
            raise ValueError("restoration uses the saved configuration")
        if state is not None and consciousness_id is not None:
            raise ValueError("restoration retains the saved consciousness identity")
        self._pending, self._event_id = [], 0
        self.time_us, self._next_epoch_us, self._sequence = 0, 0, 0
        self._inputs_open = True
        self._original_state = {}
        self._silence = None
        if state is None:
            if config is not None and type(config) is not UnifiedConfig:
                raise ValueError("original unified runtime requires UnifiedConfig")
            self.config = config or UnifiedConfig()
            package = ModelPackage.empty(self.config.manifest())
            if consciousness_id is not None:
                if not isinstance(consciousness_id, str) or not consciousness_id:
                    raise ValueError("historical individual identity must be a nonempty string")
                package.consciousness_id = consciousness_id
            self._engine = ConsciousnessRuntime(package, config=self.config.runtime())
            self._next_epoch_us = self.config.step_us
        else:
            saved = state.to_dict()
            required = {
                "schema",
                "dynamics",
                "config",
                "time_us",
                "next_epoch_us",
                "sequence",
                "event_id",
                "inputs_open",
                "pending",
                "package",
                "manifest",
                "rng_state",
                "attention_adjustment",
                "maintenance_deficit",
                "silence",
                "life",
                "queue",
                "nodes",
                "edges",
            }
            if set(saved) != required or saved["schema"] != STATE_SCHEMA or saved["dynamics"] != KERNEL_ID:
                raise ValueError("original unified state identity or fields mismatch")
            self.config = UnifiedConfig(**saved["config"])
            payload = copy.deepcopy(saved["package"])
            self._original_state = copy.deepcopy(payload["state"])
            package = ModelPackage(manifest=ModelManifest.from_dict(saved["manifest"]), **payload)
            if package.manifest.to_dict() != self.config.manifest().to_dict():
                raise ValueError("unified manifest differs from saved configuration")
            self._engine = ConsciousnessRuntime(package, config=self.config.runtime())
            self._engine._rng.setstate(_tuple(saved["rng_state"]))
            self._engine.attention_gate._tick_adjustment = AttentionAdjustment(**saved["attention_adjustment"])
            self._engine._energy_maintenance_deficit = float(saved["maintenance_deficit"])
            self.time_us = timestamp(saved["time_us"])
            self._next_epoch_us = timestamp(saved["next_epoch_us"])
            if self.life != "dead" and self._next_epoch_us <= self.time_us:
                raise ValueError("invalid historical epoch phase")
            self._sequence, self._event_id = int(saved["sequence"]), int(saved["event_id"])
            if self._sequence < 0 or self._event_id < 0:
                raise ValueError("invalid historical event sequence")
            self._inputs_open = saved["inputs_open"]
            if type(self._inputs_open) is not bool:
                raise ValueError("invalid historical source state")
            ids = set()
            for row in saved["pending"]:
                if (
                    len(row) != 4
                    or type(row[1]) is not int
                    or not 1 <= row[1] <= self._event_id
                    or row[1] in ids
                    or (self.life != "dead" and timestamp(row[0]) < self.time_us)
                ):
                    raise ValueError("invalid historical pending frame")
                ids.add(int(row[1]))
                frame = self._frame(row[2])
                self._stimulus(timestamp(row[0]), frame, row[3])
                heapq.heappush(self._pending, (timestamp(row[0]), int(row[1]), frame, row[3]))
            if saved["silence"] is not None:
                self._silence = _Silence(**saved["silence"])
                self._engine.set_intervention_policy(self._silence)
            projections = self._projections(payload["state"])
            for key, value in projections.items():
                if saved[key] != value:
                    raise ValueError(f"historical read-only {key} projection differs from its original state")

    @staticmethod
    def _frame(value):
        if set(value) != {"source", "channels", "intensity", "external", "bypass_filter"}:
            raise ValueError("historical frame field mismatch")
        stimulus = LegacyStimulus(
            0,
            {int(k): float(v) for k, v in value["channels"].items()},
            float(value["intensity"]),
            value["bypass_filter"],
            value["source"],
            value["external"],
        )
        return SensoryFrame(
            stimulus.source, dict(stimulus.channels), stimulus.intensity, stimulus.external, stimulus.bypass_attention
        )

    @property
    def sequence(self):
        return self._sequence

    @property
    def life(self):
        return self._engine.life_state

    def inject_frame(self, frame, *, time_us=None, delay_epochs=0):
        """Original frame boundary, including original 64-bit literal channels."""
        when = self.time_us if time_us is None else timestamp(time_us)
        if when < self.time_us or not self._inputs_open or self.life == "dead":
            raise ValueError("historical inputs closed or frame is late")
        copied = SensoryFrame(frame.source, dict(frame.channels), frame.intensity, frame.external, frame.bypass_filter)
        self._frame(asdict(copied))
        self._stimulus(when, copied, delay_epochs)
        self._event_id += 1
        heapq.heappush(self._pending, (when, self._event_id, copied, delay_epochs))
        return self._event_id

    def inject(self, stimulus):
        return self.inject_frame(
            SensoryFrame(
                getattr(stimulus, "source", "manual"),
                dict(stimulus.channels),
                stimulus.intensity,
                getattr(stimulus, "external", True),
                stimulus.bypass_attention,
            ),
            time_us=stimulus.time_us,
            delay_epochs=getattr(stimulus, "delay_epochs", 0),
        )

    def text_sensor(self):
        return TextSensorAdapter(
            self._engine.sensory_seed,
            labeled=self.config.node_payload == "labeled",
            encoding=self.config.sensory_encoding,
        )

    def register_channel_labels(self, labels):
        """Original display-only annotation port, never an input stimulus."""
        self._engine.register_channel_labels(labels)

    def enqueue_text(
        self,
        text,
        *,
        intensity=1.0,
        source="manual",
        bypass_attention=False,
        time_us=None,
        frame_characters=24,
        inter_frame_epochs=1,
    ):
        """Convenience host port using the original encoder and epoch spacing."""
        if type(inter_frame_epochs) is not int or inter_frame_epochs < 1:
            raise ValueError("historical text spacing must be positive epochs")
        adapter = self.text_sensor()
        frames = adapter.encode_stream(
            text, intensity=intensity, source=source, bypass_filter=bypass_attention, frame_characters=frame_characters
        )
        self.register_channel_labels(adapter.channel_labels)
        start = self.time_us if time_us is None else timestamp(time_us)
        return [
            self.inject_frame(frame, time_us=start, delay_epochs=i * inter_frame_epochs)
            for i, frame in enumerate(frames)
        ]

    @staticmethod
    def _stimulus(time_us, frame, delay_epochs=0):
        return LegacyStimulus(
            time_us,
            dict(frame.channels),
            frame.intensity,
            frame.bypass_filter,
            frame.source,
            frame.external,
            delay_epochs,
        )

    def _projections(self, raw_state):
        return {
            "life": raw_state["life_state"],
            "nodes": copy.deepcopy(raw_state["nodes"]),
            "edges": copy.deepcopy(raw_state["edges"]),
            "queue": [
                {"id": i, "time_us": str(t), "kind": "stimulus", "payload": self._stimulus(t, f, d).to_dict()}
                for t, i, f, d in sorted(self._pending)
            ],
        }

    def _enqueue(self, time_us, event_id, frame, delay_epochs, observer):
        result = self._engine.enqueue_frame(frame, adapter_id="legacy-unified-host", delay_epochs=delay_epochs)
        heapq.heappop(self._pending)
        # Envelope identity is transport provenance, never a graph quantity.
        old_id = result["envelope_id"]
        stable_id = f"legacy-{self._engine.consciousness_id}-{event_id}"
        for _, _, queued in self._engine._frame_pending:
            if queued.envelope_id == old_id:
                queued.envelope_id = stable_id
                queued.metadata["envelope_id"] = stable_id
        for records in (self._engine.stimuli, self._engine.events, self._engine.package.logs.get("stimuli", [])):
            for row in reversed(records):
                if row.get("envelope_id") == old_id:
                    row["envelope_id"] = stable_id
                    break
        self._sequence += 1
        if observer is not None:
            observer(
                {
                    "sequence": self.sequence,
                    "time_us": str(time_us),
                    "kind": "stimulus",
                    "event_id": event_id,
                    "payload": self._stimulus(time_us, frame, delay_epochs).to_dict(),
                    "delivery_stage": "legacy_input_queue",
                    "legacy_input_epoch": self._engine._input_epoch,
                    "legacy_due_epoch": result["first_due_epoch"],
                    "legacy_envelope_id": stable_id,
                }
            )

    def advance_to(self, target_us, observer=None, *, inputs_only=False):
        target_us = timestamp(target_us)
        if target_us < self.time_us:
            raise ValueError("simulation time cannot go backwards")
        while self.life != "dead":
            pending_time = self._pending[0][0] if self._pending else None
            if pending_time is not None and pending_time <= min(target_us, self._next_epoch_us):
                when, event_id, frame, delay_epochs = self._pending[0]
                self.time_us = when
                self._enqueue(when, event_id, frame, delay_epochs, observer)
            elif self._next_epoch_us <= target_us:
                boundary = self._next_epoch_us
                self._engine.step(ticks=1)
                self.time_us = boundary
                self._next_epoch_us += self.config.step_us
                self._sequence += 1
                if observer is not None:
                    observer(
                        {
                            "sequence": self.sequence,
                            "time_us": str(boundary),
                            "kind": "legacy_epoch",
                            "payload": {
                                "input_epoch": self._engine._input_epoch,
                                "tick": self._engine.tick,
                                "delta": copy.deepcopy(self._engine.latest_output().delta),
                            },
                        }
                    )
            else:
                break
        self.time_us = target_us

    def capture_state(self):
        if self._engine.attention_gate.modulator_ids:
            raise ValueError("external legacy attention modulators require an explicit host checkpoint adapter")
        payload = copy.deepcopy(self._engine.package.to_payload())
        payload["state"] = copy.deepcopy(self._original_state | self._engine.state_dict())
        return StateImage.from_dict(
            {
                "schema": STATE_SCHEMA,
                "dynamics": KERNEL_ID,
                "config": self.config.to_dict(),
                "time_us": str(self.time_us),
                "next_epoch_us": str(self._next_epoch_us),
                "sequence": self.sequence,
                "event_id": self._event_id,
                "inputs_open": self._inputs_open,
                "pending": [[str(t), i, asdict(f), d] for t, i, f, d in sorted(self._pending)],
                "package": payload,
                "manifest": self._engine.manifest.to_dict(),
                "rng_state": self._engine._rng.getstate(),
                "attention_adjustment": asdict(self._engine.attention_gate._tick_adjustment),
                "maintenance_deficit": self._engine._energy_maintenance_deficit,
                "silence": self._silence.describe() if self._silence is not None else None,
                **self._projections(payload["state"]),
            }
        )

    def close_inputs(self):
        self._inputs_open = False
        self._sequence += 1

    def reconfigure(self, config):
        if type(config) is not UnifiedConfig:
            raise ValueError("original unified runtime requires UnifiedConfig")
        for key in (
            "tick_seconds",
            "random_seed",
            "node_payload",
            "spatial_embedding",
            "spatial_dimensions",
            "sensory_encoding",
        ):
            if getattr(config, key) != getattr(self.config, key):
                raise ValueError(f"{key} is immutable after creation")
        self._engine.configure_model(parameters=config.to_dict())
        self.config = config
        self._sequence += 1

    def metrics(self):
        value = self._engine.metrics()
        return {
            **value,
            "kernel_id": KERNEL_ID,
            "time_us": str(self.time_us),
            "state_time_us": str(self._next_epoch_us - self.config.step_us),
            "sequence": self.sequence,
            "life": self.life,
            "nodes": value["node_count"],
            "edges": value["edge_count"],
            "activation": value["total_activation"],
            "inhibition": value["total_inhibition"],
            "mean_weight": value["mean_edge_weight"] if value["edge_count"] else None,
            "input_epoch": self._engine._input_epoch,
        }

    def graph(self, limit=None):
        value = self._engine.graph(limit)
        channels = {node: channel for channel, node in self._engine.receptor_index.items()}
        return {
            **value,
            "nodes": [self._node_projection(n, channels) for n in value["nodes"]],
            "edges": [dict(e, touches=e.get("touch_count")) for e in value["edges"]],
            "kernel_id": KERNEL_ID,
            "time_us": str(self.time_us),
            "sequence": self.sequence,
        }

    def activations(self):
        return [(n["id"], n["activation"]) for n in self._engine.nodes.values()]

    @staticmethod
    def _node_projection(node, channels):
        """Named observation aliases only; no invented missing measurements."""
        return {
            **node,
            "channel": channels.get(node["id"]),
            "direct": node.get("direct_touch"),
            "associative": node.get("associative_touch"),
            "touches": node.get("touch_count"),
            "local_plasticity": node.get("plasticity"),
        }

    def observation_nodes(self):
        channels = {node: channel for channel, node in self._engine.receptor_index.items()}
        return [self._node_projection(n, channels) for n in self._engine.nodes.values()]

    def induced_edges(self, node_ids):
        ids = set(node_ids)
        return [dict(e) for e in self._engine.edges.values() if e["source"] in ids and e["target"] in ids]

    def spatial_geometry(self):
        return {
            "nodes": [{"id": n["id"], "position": n.get("position")} for n in self._engine.nodes.values()],
            "edges": self._engine.spatial_neighbors(),
        }

    def supply_energy(self, amount, *, time_us=None, source="external-energy"):
        if time_us not in (None, self.time_us):
            raise ValueError("historical unified energy port accepts current epoch supply only")
        return self._engine.supply_energy(amount, source=source)

    def modulate_input(self, **kwargs):
        raise ValueError(
            "unified runtime accepts its original external attention plugin protocol, not causal modulation events"
        )

    def intervene(self, *, nodes=(), edges=(), lesion=False, action=None):
        if lesion or action in ("delete_nodes", "disconnect_edges"):
            self._engine.apply_structural_lesion(node_ids=nodes, edge_pairs=edges)
        elif action in (None, "silence"):
            self._silence = _Silence(nodes, edges)
            self._engine.set_intervention_policy(self._silence)
        else:
            raise ValueError("unsupported historical unified intervention")
        self._sequence += 1
