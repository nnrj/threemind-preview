from __future__ import annotations

"""Unified associative runtime.

This is the executable part of a ThreeMind model package.  It deliberately keeps
external carriers (text, an AI stimulus, ambient sensors) outside anonymous
nodes.  A carrier is projected through a consciousness-specific sensory body,
then evolves through attention, local propagation, temporal association,
forgetting, consolidation and homeostasis.
"""

import copy
import heapq
import hashlib
import math
import random
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Protocol

from .model import ModelManifest, ModelPackage
from .frames import OutputBus, OutputFrame, ScheduledSensoryFrame, SensoryFrame
from .attention import AttentionContext, AttentionGate, AttentionModulator


class InterventionPolicyProtocol(Protocol):
    """Optional host experiment boundary; normal runtimes attach nothing."""

    def node_silenced(self, node_id: int) -> bool: ...
    def edge_silenced(self, source: int, target: int) -> bool: ...
    def describe(self) -> dict[str, Any]: ...


@dataclass(slots=True)
class RuntimeConfig:
    tick_seconds: float = 0.10
    activation_decay: float = 0.72
    propagation_gain: float = 0.42
    # Optional numerical observation thresholds.  ``None`` means activity is
    # governed only by the network's own decay / extinction rule.
    propagation_activation_min: float | None = None
    node_activation_floor: float = 0.004
    direct_gain: float = 0.90
    learning_rate: float = 0.055
    edge_decay: float = 0.0025
    edge_birth_weight: float = 0.065
    stability_gain: float = 0.022
    # Match the former anonymous kernel's retention timescale.  Stability is
    # still allowed to decay, but a few repeated, co-active encounters must
    # not be erased by a short idle interval.
    stability_decay: float = 0.00015
    consolidation_first_gain: float = 0.045
    consolidation_repeat_gain: float = 0.018
    consolidation_intensity_gain: float = 0.075
    consolidation_associative_gain: float = 0.010
    consolidation_cap: float = 0.42
    prune_threshold: float = 0.008
    node_support_gain: float = 0.035
    node_support_decay: float = 0.00015
    node_support_prune_threshold: float = 0.006
    node_prune_after: int = 800
    # Keep temporal association local, as in the former anonymous kernel.
    # Wider windows may be selected explicitly by an experiment, but should
    # not turn a slowly changing background into one prolonged co-occurrence.
    association_window: int = 5
    # New connections normally require co-activation in the same sensory
    # event.  The alternate temporal mode intentionally preserves the former
    # broad recent-activity experiment for comparative runs.
    edge_birth_policy: str = "local-coactivation"
    # Retained as an optional environmental competition capacity.  It is
    # ignored by the transparent default path.
    attention_budget: int = 28
    attention_competition_enabled: bool = False
    # Optional, explicitly requested computational budgets.  They are not
    # intrinsic cognitive rules and must never be enabled by default.
    edge_adaptation_limit: int | None = None
    propagation_limit: int | None = None
    edge_birth_activation_product_min: float | None = None
    local_novelty_gain: float = 0.018
    novelty_touch_reference: float = 0.20
    # The historical global clamp is retained as an independently selectable
    # comparison mechanism.  Local inhibition below does not silently enable
    # or replace it.
    homeostasis_enabled: bool = False
    target_total_activation: float = 12.0
    # Topology-local inhibition is part of the normal dynamics by default, but
    # remains explicitly switchable for controlled comparison experiments.
    # Excitatory edges remain directed; inhibition treats either directed edge
    # as physical adjacency and diffuses without duplicating its finite
    # potential at branches.
    topology_inhibition_enabled: bool = True
    inhibition_generation_gain: float = 0.24
    inhibition_decay: float = 0.35
    inhibition_diffusion: float = 0.35
    inhibition_response_gain: float = 2.0
    inhibition_saturation: float = 1.0
    inhibition_propagation_min: float = 0.002
    # Optional experimental energy accounting.  When disabled no energy
    # variable participates in dynamics.  When enabled, Core never creates
    # energy: only the explicit initial condition and external supply API can
    # increase the reserve.
    energy_simulation_enabled: bool = False
    energy_initial_reserve: float = 1.0
    energy_capacity: float = 1.0
    energy_direct_cost: float = 0.035
    energy_associative_cost: float = 0.020
    energy_inhibition_cost: float = 0.010
    irreversible_energy_death_enabled: bool = False
    energy_maintenance_cost_per_node: float = 0.00002
    energy_maintenance_cost_per_edge: float = 0.000004
    energy_starvation_structural_decay: float = 0.006
    energy_starvation_death_ticks: int = 900
    response_epsilon: float = 0.0008
    unresponsive_window: int = 900
    # ``None`` is deliberately unbounded.  Hosts may opt into a package-level
    # resource limit, but Core does not silently impose a semantic ceiling.
    max_nodes: int | None = None
    max_edges: int | None = None
    random_seed: int = 20260724

    @classmethod
    def from_manifest(cls, manifest: ModelManifest) -> "RuntimeConfig":
        config = cls()
        bounds: dict[str, tuple[float, float]] = {
            "tick_seconds": (0.002, 60.0), "activation_decay": (0.0, 1.0),
            "propagation_gain": (0.0, 4.0), "propagation_activation_min": (0.0, 1.0),
            "node_activation_floor": (0.0, 1.0), "direct_gain": (0.0, 4.0),
            "learning_rate": (0.0, 1.0), "edge_decay": (0.0, 1.0),
            "edge_birth_weight": (0.0, 1.0), "stability_gain": (0.0, 1.0),
            "stability_decay": (0.0, 1.0), "prune_threshold": (0.0, 1.0),
            "consolidation_first_gain": (0.0, 1.0), "consolidation_repeat_gain": (0.0, 1.0), "consolidation_intensity_gain": (0.0, 1.0), "consolidation_associative_gain": (0.0, 1.0),
            "consolidation_cap": (0.0, 1.0), "node_support_gain": (0.0, 1.0),
            "node_support_decay": (0.0, 1.0), "node_support_prune_threshold": (0.0, 1.0), "node_prune_after": (1, 10_000_000),
            "association_window": (1, 10_000),
            "attention_budget": (1, 100_000), "target_total_activation": (0.01, 1_000_000),
            "response_epsilon": (0.0, 1.0), "unresponsive_window": (2, 10_000_000),
            "max_nodes": (1, float("inf")), "max_edges": (1, float("inf")),
            "propagation_limit": (1, float("inf")), "edge_adaptation_limit": (1, float("inf")),
            "edge_birth_activation_product_min": (0.0, 1.0),
            "local_novelty_gain": (0.0, 1.0), "novelty_touch_reference": (0.000001, 1.0),
            "inhibition_generation_gain": (0.0, 10.0), "inhibition_decay": (0.0, 1.0),
            "inhibition_diffusion": (0.0, 1.0), "inhibition_response_gain": (0.0, 100.0),
            "inhibition_saturation": (0.000001, 1_000_000.0), "inhibition_propagation_min": (0.0, 1_000_000.0),
            "energy_initial_reserve": (0.0, 1_000_000_000.0), "energy_capacity": (0.000001, 1_000_000_000.0),
            "energy_direct_cost": (0.0, 1_000_000.0), "energy_associative_cost": (0.0, 1_000_000.0),
            "energy_inhibition_cost": (0.0, 1_000_000.0),
            "energy_maintenance_cost_per_node": (0.0, 1_000_000.0),
            "energy_maintenance_cost_per_edge": (0.0, 1_000_000.0),
            "energy_starvation_structural_decay": (0.0, 1.0),
            "energy_starvation_death_ticks": (1, 10_000_000),
            "random_seed": (-2**63, 2**63 - 1),
        }
        integer_names = {"association_window", "attention_budget", "edge_adaptation_limit", "propagation_limit", "unresponsive_window", "max_nodes", "max_edges", "node_prune_after", "energy_starvation_death_ticks", "random_seed"}
        for name, (low, high) in bounds.items():
            if name not in manifest.parameters:
                continue
            raw_value = manifest.parameters[name]
            if raw_value is None:
                continue
            value = int(raw_value) if name in integer_names else float(raw_value)
            setattr(config, name, max(low, min(high, value)))
        # Legacy implicit budget fields are intentionally ignored.  They were
        # shipped as unrequested defaults and must not survive as hidden
        # restrictions after the runtime is upgraded.  Only the explicit
        # `*_limit` / `*_min` fields above may change this behavior.
        if "attention_competition_enabled" in manifest.parameters:
            config.attention_competition_enabled = bool(manifest.parameters["attention_competition_enabled"])
        for name in (
            "homeostasis_enabled", "topology_inhibition_enabled",
            "energy_simulation_enabled", "irreversible_energy_death_enabled",
        ):
            if name in manifest.parameters:
                setattr(config, name, bool(manifest.parameters[name]))
        if "edge_birth_policy" in manifest.parameters:
            policy = str(manifest.parameters["edge_birth_policy"])
            if policy not in {"local-coactivation", "temporal-association"}:
                raise ValueError("unsupported edge_birth_policy")
            config.edge_birth_policy = policy
        return config


class ConsciousnessRuntime:
    """A package-driven, locally propagating associative graph.

    ``node_payload=anonymous`` stores only internal node identifiers and state.
    The per-consciousness sensory seed makes the same external carrier project
    differently in different consciousnesses, while a resumed package retains
    its own mapping.
    """

    def __init__(self, package: ModelPackage | None = None, *, config: RuntimeConfig | None = None) -> None:
        self.package = package or ModelPackage.empty()
        self.manifest = self.package.manifest
        self.manifest.validate()
        # Remove historical implicit truncation defaults from loaded packages.
        # Explicit replacement fields (`edge_adaptation_limit`, etc.) are the
        # sole supported way to opt into a limit.
        for legacy_name in ("max_edge_adaptations", "max_propagations", "propagation_threshold"):
            self.manifest.parameters.pop(legacy_name, None)
        self.config = config or RuntimeConfig.from_manifest(self.manifest)
        state = self.package.state
        self.tick = int(state.get("tick", 0))
        self.life_state = str(state.get("life_state", "active"))
        self.death_reason = state.get("death_reason")
        self.nodes: dict[int, dict[str, Any]] = {}
        self.edges: dict[tuple[int, int], dict[str, Any]] = {}
        # Runtime adjacency is an implementation index, not additional model
        # state.  It lets propagation remain local without a global edge scan.
        self._outgoing: dict[int, set[int]] = {}
        # Physical adjacency for optional local inhibitory diffusion.  It is
        # an index derived from directed edges, never extra model topology.
        self._incident: dict[int, set[int]] = {}
        self._spatial_edge_keys: set[tuple[int, int]] = set()
        # Historical stimuli, observations and interpretations are research
        # records.  Presentation layers page or virtualise them; Core must not
        # silently erase them merely because an experiment remains running.
        self.events: list[dict[str, Any]] = list(state.get("events", []))
        self.stimuli: list[dict[str, Any]] = list(state.get("stimuli", []))
        self.interpretations: list[dict[str, Any]] = list(state.get("interpretations", []))
        self._history_revision = int(state.get("history_revision", 0))
        self.sources: dict[str, bool] = dict(state.get("sources", {"manual": True, "ambient": True, "ai": True}))
        self.filter_bypass_sources: set[str] = set(state.get("filter_bypass_sources", []))
        derived_seed = int.from_bytes(hashlib.blake2b(self.package.consciousness_id.encode(), digest_size=8).digest(), "big")
        self.sensory_seed = int(state.get("sensory_seed", derived_seed))
        self.receptor_index: dict[int, int] = {int(key): int(value) for key, value in state.get("receptor_index", {}).items()}
        # Readable material is model-package observation metadata, not graph
        # state. It is never consulted by graph dynamics.
        self.channel_labels: dict[int, str] = {int(key): str(value) for key, value in state.get("channel_labels", {}).items()}
        self.node_annotations: dict[int, dict[str, str]] = {
            int(key): {str(field): str(value) for field, value in raw.items() if str(value)}
            for key, raw in state.get("node_annotations", {}).items() if isinstance(raw, dict)
        }
        self._next_node_id = int(state.get("next_node_id", max([0, *[int(key) for key in state.get("nodes", []) if isinstance(key, int)]]) + 1))
        self._recent: deque[set[int]] = deque((set(map(int, group)) for group in state.get("recent", [])), maxlen=int(self.config.association_window))
        self._rng = random.Random(int(state.get("rng_seed", self.config.random_seed)) ^ self.sensory_seed)
        self._unresponsive_ticks = int(state.get("unresponsive_ticks", 0))
        self._last_total_activation = float(state.get("last_total_activation", 0.0))
        self._observation_occurrences: dict[str, list[int]] = {str(key): [int(tick) for tick in value] for key, value in state.get("observation_occurrences", {}).items()}
        self._observation_cooldowns: dict[str, int] = {str(key): int(value) for key, value in state.get("observation_cooldowns", {}).items()}
        self._last_delta: dict[str, Any] = dict(state.get("last_delta", {}))
        # Output provenance is deliberately separate from graph state.  It
        # lets external observers distinguish an activity continuation caused
        # by the ambient field from one caused by a manual carrier, including
        # the quiet ticks immediately after a sensory frame was delivered.
        # It is never consulted by any activation, association, or forgetting
        # rule.
        self._last_sensory_sources: list[str] = [
            str(source) for source in state.get("last_sensory_sources", [])
        ]
        self.trace_enabled = bool(state.get("trace_enabled", False))
        self.trace_entries: list[dict[str, Any]] = list(state.get("trace_entries", []))[-20_000:]
        self.energy_reserve = (
            min(self.config.energy_capacity, max(0.0, float(state.get("energy_reserve", self.config.energy_initial_reserve))))
            if self.config.energy_simulation_enabled else 0.0
        )
        self.energy_supplied_total = float(state.get("energy_supplied_total", 0.0))
        self.energy_consumed_total = float(state.get("energy_consumed_total", 0.0))
        self._energy_starved_ticks = int(state.get("energy_starved_ticks", 0))
        self._energy_maintenance_deficit = 0.0
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._paused = False
        # The InputBus is an ordered transport queue rather than a bag of
        # simultaneous frames.  It is intentionally separate from graph
        # state: adapters create frames, the queue preserves their causal
        # ordering, and the graph sees exactly one frame per advance.
        self._input_epoch = int(state.get("input_epoch", 0))
        self._input_sequence = int(state.get("input_sequence", 0))
        self._frame_pending: list[tuple[int, int, ScheduledSensoryFrame]] = []
        for raw in state.get("input_queue", []):
            try:
                scheduled = ScheduledSensoryFrame.from_dict(dict(raw))
            except (TypeError, ValueError):
                continue
            self._input_sequence = max(self._input_sequence, scheduled.sequence)
            heapq.heappush(self._frame_pending, (scheduled.due_epoch, scheduled.sequence, scheduled))
        self.attention_gate = AttentionGate()
        # Deliberately absent during normal operation.  An experiment host may
        # attach a visible policy to an isolated clone; the policy is not
        # model state and is never restored from a consciousness package.
        self._intervention_policy: InterventionPolicyProtocol | None = None
        # The output bus is a one-way observation boundary. It is not an input
        # source and it cannot modify graph state.
        self.output_bus = OutputBus()
        self._load_graph_state(state)
        self.output_bus.publish(self._make_output_frame())

    @property
    def consciousness_id(self) -> str: return self.package.consciousness_id

    @property
    def consciousness_name(self) -> str: return self.package.consciousness_name

    @property
    def edge_count(self) -> int: return len(self.edges)

    def _node_silenced(self, node_id: int) -> bool:
        return bool(self._intervention_policy and self._intervention_policy.node_silenced(int(node_id)))

    def _edge_silenced(self, source: int, target: int) -> bool:
        return bool(self._intervention_policy and self._intervention_policy.edge_silenced(int(source), int(target)))

    def set_intervention_policy(self, policy: InterventionPolicyProtocol | None) -> dict[str, Any] | None:
        """Attach or clear an explicit experiment-only functional policy."""
        with self._lock:
            self._intervention_policy = policy
            return copy.deepcopy(policy.describe()) if policy is not None else None

    def intervention_status(self) -> dict[str, Any] | None:
        policy = self._intervention_policy
        return copy.deepcopy(policy.describe()) if policy is not None else None

    def apply_structural_lesion(
        self,
        *,
        node_ids: Iterable[int] = (),
        edge_pairs: Iterable[tuple[int, int]] = (),
        intervention_id: str = "",
        label: str = "experimental structural lesion",
    ) -> dict[str, Any]:
        """Permanently remove selected structure from an experiment clone.

        This is never called by normal graph evolution.  The host must expose
        it as an explicit intervention, and the removal is written to the
        audit log so it cannot be mistaken for endogenous forgetting.
        """
        with self._lock:
            selected_nodes = {int(value) for value in node_ids}
            selected_edges = {(int(source), int(target)) for source, target in edge_pairs}
            selected_edges.update(key for key in self.edges if key[0] in selected_nodes or key[1] in selected_nodes)
            removed_edges = sorted(key for key in selected_edges if key in self.edges)
            for key in removed_edges:
                self._remove_edge(key)
            removed_nodes = sorted(node_id for node_id in selected_nodes if node_id in self.nodes)
            for node_id in removed_nodes:
                self.nodes.pop(node_id, None)
                self._outgoing.pop(node_id, None)
                self._incident.pop(node_id, None)
                for channel, receptor in list(self.receptor_index.items()):
                    if receptor == node_id:
                        self.receptor_index.pop(channel, None)
            event = {
                "tick": self.tick,
                "kind": "experimental_structural_lesion",
                "intervention_id": str(intervention_id),
                "label": str(label),
                "removed_node_ids": removed_nodes,
                "removed_edge_pairs": [list(pair) for pair in removed_edges],
            }
            self.events.append(event)
            self.package.logs.setdefault("interventions", []).append(copy.deepcopy(event))
            self._history_revision += 1
            self._last_delta = {
                **self._last_delta,
                "tick": self.tick,
                "removed_nodes": removed_nodes,
                "removed_edges": [list(pair) for pair in removed_edges],
                "intervention_id": str(intervention_id),
            }
            self.output_bus.publish(self._make_output_frame())
            return copy.deepcopy(event)

    def _load_graph_state(self, state: dict[str, Any]) -> None:
        for raw in state.get("nodes", []):
            node = dict(raw); node["id"] = int(node["id"])
            legacy_label = node.pop("label", None)
            if legacy_label and node["id"] not in self.node_annotations:
                self.node_annotations[node["id"]] = {"label": str(legacy_label)[:80]}
            node.setdefault("activation", 0.0); node.setdefault("previous_activation", 0.0)
            node.setdefault("trace", 0.0); node.setdefault("plasticity", 1.0)
            node.setdefault("support", 0.0)
            node.setdefault("stability", 0.0); node.setdefault("born_tick", self.tick)
            node.setdefault("last_touched_tick", self.tick); node.setdefault("touch_count", 0)
            node.setdefault("direct_touch", 0.0); node.setdefault("associative_touch", 0.0)
            node.setdefault("inhibition", 0.0); node.setdefault("pending_inhibition", 0.0)
            node.setdefault("position", self._position(node["id"]))
            self.nodes[node["id"]] = node
        for raw in state.get("edges", []):
            edge = dict(raw); source, target = int(edge["source"]), int(edge["target"])
            edge.update(source=source, target=target)
            edge.setdefault("stability", 0.0); edge.setdefault("eligibility", 0.0)
            edge.setdefault("born_tick", self.tick); edge.setdefault("last_touched_tick", self.tick)
            edge.setdefault("touch_count", 0); edge.setdefault("vector", self._edge_vector(source, target))
            edge.setdefault("formation_associative_touch", 0.0); edge.setdefault("local_novelty", 0.0)
            self._add_edge((source, target), edge)
        if self.nodes:
            self._next_node_id = max(self._next_node_id, max(self.nodes) + 1)

    def _source_kind(self, source: str) -> str:
        return "ai" if source.startswith("ai") else "ambient" if source.startswith(("ambient", "body", "interoceptive", "host-load", "network")) else "manual"

    @staticmethod
    def _is_background_source(source: str) -> bool:
        """Classify physical/background sensory carriers for output observers.

        This is provenance only.  It does not alter source enablement,
        attention, receptor creation, or any graph rule.  Network and AI
        carriers are deliberately excluded: the background listener is meant
        to observe the ambient/body field when no manual or AI text arrived.
        """
        return source.startswith(("ambient", "body", "interoceptive", "host-load"))

    def receive_frame(self, frame: SensoryFrame, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Receive an already-projected anonymous sensory frame.

        This is the Core-facing input boundary.  Text, images and tool output
        belong to adapters outside this runtime; the optional metadata is only
        retained in the external stimulus log and is never assigned to nodes.
        """
        with self._lock:
            if self.life_state == "dead": raise RuntimeError("consciousness is dead")
            source_kind = self._source_kind(frame.source)
            if not self.sources.get(source_kind, True): raise RuntimeError(f"stimulus source is disabled: {source_kind}")
            audit = dict(metadata or {})
            envelope_id = str(audit.get("envelope_id") or uuid.uuid4())
            adapter_id = str(audit.get("adapter_id") or "synchronous-input")
            record = {"tick": self.tick + 1, "source": frame.source, "intensity": frame.intensity, **audit, "envelope_id": envelope_id, "adapter_id": adapter_id}
            self.stimuli.append(record)
            self._history_revision += 1
            event = {"tick": self.tick + 1, "kind": "stimulus", "source": frame.source, "intensity": frame.intensity, "feature_count": len(frame.channels), **audit, "envelope_id": envelope_id, "adapter_id": adapter_id}
            self.events.append(event)
            self.package.logs.setdefault("stimuli", []).append(event)
            self._advance([frame], delivery_contexts=[{
                "envelope_id": envelope_id,
                "frame_index": 0,
                "frame_count": 1,
                "sequence": None,
                "adapter_id": adapter_id,
                "source": frame.source,
            }]); event["tick"] = self.tick
            return event

    def enqueue_frame(
        self,
        frame: SensoryFrame,
        *,
        metadata: dict[str, Any] | None = None,
        adapter_id: str = "unknown",
        delay_epochs: int = 0,
    ) -> dict[str, Any]:
        """Schedule one anonymous frame through the InputBus.

        This is the normal production input boundary.  ``receive_frame`` is
        retained as a synchronous diagnostic/test primitive; application
        callers should use this method or :meth:`enqueue_frames` so a request
        cannot collapse a carrier into a single graph transition.
        """
        return self.enqueue_frames(
            (frame,), metadata=metadata, adapter_id=adapter_id,
            inter_frame_epochs=1, initial_delay_epochs=delay_epochs,
        )

    def enqueue_frames(
        self,
        frames: Iterable[SensoryFrame],
        *,
        metadata: dict[str, Any] | None = None,
        adapter_id: str = "unknown",
        inter_frame_epochs: int = 1,
        initial_delay_epochs: int = 0,
    ) -> dict[str, Any]:
        """Enqueue a complete carrier as ordered causal frames.

        No frame is sampled, merged, or discarded.  A source adapter chooses
        the framing; this scheduler preserves the resulting order and makes
        delivery auditable through an envelope id and per-frame events.
        """
        frame_list = tuple(frames)
        if not frame_list:
            raise ValueError("cannot enqueue an empty sensory frame stream")
        spacing = int(inter_frame_epochs)
        if spacing < 1:
            raise ValueError("inter_frame_epochs must be positive")
        delay = int(initial_delay_epochs)
        if delay < 0:
            raise ValueError("initial_delay_epochs cannot be negative")
        with self._lock:
            if self.life_state == "dead":
                raise RuntimeError("consciousness is dead")
            source_kind = self._source_kind(frame_list[0].source)
            if not self.sources.get(source_kind, True):
                raise RuntimeError(f"stimulus source is disabled: {source_kind}")
            envelope_id = str(uuid.uuid4())
            start_epoch = self._input_epoch + 1 + delay
            common = dict(metadata or {})
            record = {
                "tick": self.tick,
                "input_epoch": self._input_epoch,
                "source": frame_list[0].source,
                "intensity": float(frame_list[0].intensity),
                "envelope_id": envelope_id,
                "adapter_id": str(adapter_id),
                "frame_count": len(frame_list),
                "delivery_state": "queued",
                **common,
            }
            self.stimuli.append(record)
            self._history_revision += 1
            event = {
                "tick": self.tick,
                "input_epoch": self._input_epoch,
                "kind": "stimulus_queued",
                "source": frame_list[0].source,
                "intensity": float(frame_list[0].intensity),
                "feature_count": sum(len(frame.channels) for frame in frame_list),
                "envelope_id": envelope_id,
                "adapter_id": str(adapter_id),
                "frame_count": len(frame_list),
                "inter_frame_epochs": spacing,
                **common,
            }
            self.events.append(event)
            self.package.logs.setdefault("stimuli", []).append(event)
            for index, frame in enumerate(frame_list):
                self._input_sequence += 1
                delivery_metadata = {
                    "envelope_id": envelope_id,
                    "frame_index": index,
                    "frame_count": len(frame_list),
                    "adapter_id": str(adapter_id),
                }
                scheduled = ScheduledSensoryFrame(
                    frame=frame,
                    due_epoch=start_epoch + index * spacing,
                    sequence=self._input_sequence,
                    envelope_id=envelope_id,
                    frame_index=index,
                    frame_count=len(frame_list),
                    adapter_id=str(adapter_id),
                    metadata=delivery_metadata,
                )
                heapq.heappush(self._frame_pending, (scheduled.due_epoch, scheduled.sequence, scheduled))
            return {
                "queued": True,
                "envelope_id": envelope_id,
                "frame_count": len(frame_list),
                "first_due_epoch": start_epoch,
                "last_due_epoch": start_epoch + (len(frame_list) - 1) * spacing,
                "queue_size": len(self._frame_pending),
            }

    def _take_due_frames(self) -> list[ScheduledSensoryFrame]:
        """Advance host logical time and return the next ordered epoch.

        Frames sharing one environmental epoch remain distinct events.  They
        are processed sequentially by the run loop instead of being combined
        into a co-activation set.
        """
        self._input_epoch += 1
        due: list[ScheduledSensoryFrame] = []
        while self._frame_pending and self._frame_pending[0][0] <= self._input_epoch:
            _epoch, _sequence, scheduled = heapq.heappop(self._frame_pending)
            due.append(scheduled)
        return due

    def _record_frame_delivery(self, scheduled: ScheduledSensoryFrame) -> None:
        event = {
            "tick": self.tick,
            "input_epoch": self._input_epoch,
            "kind": "stimulus_frame_delivered",
            "source": scheduled.frame.source,
            "intensity": float(scheduled.frame.intensity),
            "feature_count": len(scheduled.frame.channels),
            "envelope_id": scheduled.envelope_id,
            "frame_index": scheduled.frame_index,
            "frame_count": scheduled.frame_count,
            "adapter_id": scheduled.adapter_id,
            "due_epoch": scheduled.due_epoch,
            "sequence": scheduled.sequence,
        }
        self.events.append(event)
        self.package.logs.setdefault("stimuli", []).append(event)

    def queue_size(self) -> int:
        with self._lock:
            return len(self._frame_pending)

    def input_queue_status(self) -> dict[str, Any]:
        with self._lock:
            next_item = self._frame_pending[0][2] if self._frame_pending else None
            return {
                "input_epoch": self._input_epoch,
                "queued_frames": len(self._frame_pending),
                "next_due_epoch": next_item.due_epoch if next_item else None,
                "next_envelope_id": next_item.envelope_id if next_item else None,
            }

    def _create_receptor(self, channel: int) -> int | None:
        if self.config.max_nodes is not None and len(self.nodes) >= self.config.max_nodes: return None
        node_id = self._next_node_id; self._next_node_id += 1
        node = {"id": node_id, "activation": 0.0, "previous_activation": 0.0, "trace": 0.0, "plasticity": 1.0, "stability": 0.0, "support": 0.0, "born_tick": self.tick, "last_touched_tick": self.tick, "touch_count": 0, "direct_touch": 0.0, "associative_touch": 0.0, "inhibition": 0.0, "pending_inhibition": 0.0, "position": self._position(node_id)}
        self.nodes[node_id] = node; self.receptor_index[channel] = node_id
        if channel in self.channel_labels:
            self.node_annotations[node_id] = {**self.node_annotations.get(node_id, {}), "label": self.channel_labels[channel]}
        return node_id

    def register_channel_labels(self, labels: dict[int, str]) -> None:
        """Register display-only sensory labels in the package annotation map.

        Adapters call this before submitting a frame. Updating a label never
        changes graph quantities or creates a response by itself.
        """
        with self._lock:
            for raw_channel, raw_label in labels.items():
                channel, label = int(raw_channel), str(raw_label)[:80]
                if not label:
                    continue
                self.channel_labels[channel] = label
                node_id = self.receptor_index.get(channel)
                if node_id is not None and node_id in self.nodes:
                    self.node_annotations[node_id] = {**self.node_annotations.get(node_id, {}), "label": label}

    def node_label(self, node_id: int) -> str | None:
        """Return an external display annotation, never a graph attribute."""
        label = self.node_annotations.get(int(node_id), {}).get("label")
        return label or None

    def _add_edge(self, key: tuple[int, int], edge: dict[str, Any]) -> None:
        self.edges[key] = edge
        source, target = int(key[0]), int(key[1])
        self._outgoing.setdefault(source, set()).add(target)
        self._incident.setdefault(source, set()).add(target)
        self._incident.setdefault(target, set()).add(source)
        if self.manifest.spatial_embedding and self._edge_distance(edge) <= max(1e-6, float(self.manifest.parameters.get("spatial_radius", 1.0))):
            self._spatial_edge_keys.add(key)

    def _remove_edge(self, key: tuple[int, int]) -> None:
        self.edges.pop(key, None)
        self._spatial_edge_keys.discard(key)
        source, target = int(key[0]), int(key[1])
        targets = self._outgoing.get(source)
        if targets is not None:
            targets.discard(target)
            if not targets:
                self._outgoing.pop(source, None)
        # A reverse directed edge still constitutes the same physical
        # adjacency, so only remove the undirected index when both directions
        # are gone.
        if (target, source) not in self.edges:
            for node_id, neighbour in ((source, target), (target, source)):
                neighbours = self._incident.get(node_id)
                if neighbours is not None:
                    neighbours.discard(neighbour)
                    if not neighbours:
                        self._incident.pop(node_id, None)

    def _filter_channels(self, frames: list[SensoryFrame], delta: dict[str, Any]) -> list[tuple[int, int, float, float, float]]:
        """Pass encoded sensory drive through a transparent default boundary.

        Novelty and relevance deliberately do not participate here.  They are
        properties of local graph history and propagation, so they are handled
        during edge adaptation rather than used to pre-select a stimulus.
        """
        candidates: list[tuple[float, int, int, float, float, float]] = []
        transparent: list[tuple[int, int, float, float, float]] = []
        self.attention_gate.begin_tick(self.tick, frames)
        budget_multiplier = 1.0
        total = 0
        competition_requested = self.config.attention_competition_enabled
        for frame_index, frame in enumerate(frames):
            for channel, raw in frame.channels.items():
                total += 1
                # This is the adapter-encoded physical drive, not an
                # attention-derived score.  Do not clamp it to one: a stronger
                # external frame must remain distinguishable by local learning.
                raw_drive = max(0.0, float(raw) * max(0.0, float(frame.intensity)))
                modulation = self.attention_gate.adjust(AttentionContext(self.tick, frame.source, channel, raw_drive, 0.0, 0.0))
                budget_multiplier = min(budget_multiplier, modulation.budget_multiplier)
                effective_drive = raw_drive * max(0.0, modulation.strength_multiplier)
                item = (effective_drive * max(0.0, modulation.score_multiplier), frame_index, channel, raw_drive, effective_drive, float(frame.intensity))
                competition_requested = competition_requested or modulation.competition_enabled
                if frame.bypass_filter or not competition_requested:
                    transparent.append((frame_index, channel, raw_drive, effective_drive, float(frame.intensity)))
                else:
                    candidates.append(item)
        if not competition_requested:
            delta["accepted_features"] = len(transparent)
            delta["filtered_features"] = 0
            delta["attention_mode"] = "transparent"
            delta["attention_budget"] = None
            delta["attention_modulators"] = self.attention_gate.modulator_ids
            return transparent
        # Stable sorting deliberately has no hidden channel-id or seeded bias.
        # Ties preserve arrival order from the adapter frame.
        candidates.sort(key=lambda item: item[0], reverse=True)
        effective_budget = max(1, int(self.config.attention_budget * max(.01, budget_multiplier)))
        accepted = transparent + [(frame_index, channel, raw_drive, effective_drive, frame_intensity) for _, frame_index, channel, raw_drive, effective_drive, frame_intensity in candidates[:max(0, effective_budget - len(transparent))]]
        delta["accepted_features"] = len(accepted); delta["filtered_features"] = max(0, total - len(accepted))
        delta["attention_budget"] = effective_budget
        delta["attention_mode"] = "environmental_competition"
        delta["attention_modulators"] = self.attention_gate.modulator_ids
        return accepted

    def _consume_energy(self, requested_activity: float, cost_per_unit: float) -> float:
        """Return the physically affordable fraction of a local operation.

        This ledger is deliberately absent when energy simulation is off.  It
        has no internal recovery path; only ``supply_energy`` can replenish it.
        """
        requested = max(0.0, float(requested_activity))
        cost = max(0.0, float(cost_per_unit))
        if not self.config.energy_simulation_enabled or requested <= 0.0 or cost <= 0.0:
            return 1.0
        required = requested * cost
        consumed = min(self.energy_reserve, required)
        self.energy_reserve = max(0.0, self.energy_reserve - consumed)
        self.energy_consumed_total += consumed
        return min(1.0, consumed / required) if required > 0.0 else 1.0

    def supply_energy(self, amount: float, *, source: str = "external-energy-adapter") -> dict[str, Any]:
        """Supply finite experimental energy from outside Core dynamics.

        The source label is audit metadata only.  Supplying energy while the
        simulation is disabled is rejected so no hidden reserve can influence
        a later run merely because an adapter happened to be attached.
        """
        with self._lock:
            if self.life_state == "dead":
                raise RuntimeError("consciousness is dead")
            if not self.config.energy_simulation_enabled:
                raise RuntimeError("energy simulation is disabled")
            offered = max(0.0, float(amount))
            before = self.energy_reserve
            self.energy_reserve = min(self.config.energy_capacity, before + offered)
            accepted = self.energy_reserve - before
            self.energy_supplied_total += accepted
            event = {
                "consciousness_id": self.consciousness_id,
                "tick": self.tick, "kind": "energy_supplied", "source": str(source),
                "offered": offered, "accepted": accepted, "reserve": self.energy_reserve,
            }
            self.package.logs.setdefault("energy", []).append(event)
            self.events.append(dict(event))
            self._history_revision += 1
            return event

    def _apply_energy_maintenance(self) -> None:
        self._energy_maintenance_deficit = 0.0
        if not self.config.energy_simulation_enabled or not self.config.irreversible_energy_death_enabled:
            return
        required = (
            len(self.nodes) * self.config.energy_maintenance_cost_per_node
            + len(self.edges) * self.config.energy_maintenance_cost_per_edge
        )
        if required <= 0.0:
            return
        affordable = self._consume_energy(required, 1.0)
        self._energy_maintenance_deficit = max(0.0, 1.0 - affordable)

    def _saturate_inhibition(self, value: float) -> float:
        cap = max(1e-9, self.config.inhibition_saturation)
        return cap * math.tanh(max(0.0, float(value)) / cap)

    def _inhibitory_response(self, node: dict[str, Any]) -> float:
        if not self.config.topology_inhibition_enabled:
            return 1.0
        inhibition = self._saturate_inhibition(float(node.get("inhibition", 0.0)))
        return 1.0 / (1.0 + self.config.inhibition_response_gain * inhibition)

    def _prepare_inhibition(self) -> None:
        if not self.config.topology_inhibition_enabled:
            for node in self.nodes.values():
                node["inhibition"] = 0.0
                node["pending_inhibition"] = 0.0
            return
        retention = 1.0 - self.config.inhibition_decay
        for node in self.nodes.values():
            carried = float(node.get("inhibition", 0.0)) * retention
            incoming = float(node.get("pending_inhibition", 0.0))
            node["inhibition"] = self._saturate_inhibition(carried + incoming)
            node["pending_inhibition"] = 0.0

    def _decay_nodes(self) -> dict[int, float]:
        baseline: dict[int, float] = {}
        for node in self.nodes.values():
            node["previous_activation"] = float(node["activation"]); node["direct_touch"] = 0.0; node["associative_touch"] = 0.0
            node["activation"] *= self.config.activation_decay; node["trace"] *= .82
            if self._node_silenced(int(node["id"])):
                node["activation"] = 0.0
                node["direct_touch"] = 0.0
                node["associative_touch"] = 0.0
            node["support"] = max(0.0, float(node.get("support", 0.0)) - self.config.node_support_decay * (1.0 - float(node.get("stability", 0.0))))
            if node["activation"] < self.config.node_activation_floor: node["activation"] = 0.0
            baseline[int(node["id"])] = float(node["activation"])
        return baseline

    def _apply_direct(self, accepted: Iterable[tuple[int, int, float, float, float]], delta: dict[str, Any]) -> tuple[set[int], dict[int, float], list[set[int]]]:
        direct: set[int] = set(); impulses: dict[int, float] = {}; event_groups: dict[int, set[int]] = {}
        for frame_index, channel, raw_drive, effective_drive, frame_intensity in accepted:
            node_id = self.receptor_index.get(channel)
            if node_id is not None and self._node_silenced(node_id):
                continue
            response = self._inhibitory_response(self.nodes[node_id]) if node_id is not None and node_id in self.nodes else 1.0
            requested_touch = min(1.0, effective_drive * self.config.direct_gain) * response
            energy_fraction = self._consume_energy(requested_touch, self.config.energy_direct_cost)
            touch = requested_touch * energy_fraction
            if touch <= 0.0:
                continue
            # Creating topology is itself part of the affordable local
            # operation.  A depleted optional energy ledger must not leave a
            # zero-activation receptor behind merely because a carrier was
            # inspected before its physical cost was checked.
            if node_id is None:
                node_id = self._create_receptor(channel)
            if node_id is None:
                continue
            node = self.nodes[node_id]
            node["activation"] = min(1.0, float(node["activation"]) + touch); node["direct_touch"] = max(float(node["direct_touch"]), touch); node["trace"] = min(1.0, float(node["trace"]) + touch)
            # Local, carrier-agnostic consolidation.  This has no input-gate
            # score: repeated direct and associative contact both strengthen
            # the topology through their own activity history.
            initial_contact = 1.0 if int(node.get("touch_count", 0)) == 0 else 0.0
            impulse = effective_drive * energy_fraction * float(node.get("plasticity", 1.0)) * (
                self.config.consolidation_first_gain * initial_contact
                + self.config.consolidation_repeat_gain
                + self.config.consolidation_intensity_gain * max(0.0, frame_intensity - 1.0)
            )
            impulses[node_id] = max(impulses.get(node_id, 0.0), min(self.config.consolidation_cap, impulse))
            direct.add(node_id); event_groups.setdefault(frame_index, set()).add(node_id); delta["created_nodes"].add(node_id) if int(node["touch_count"]) == 0 else None
        return direct, impulses, list(event_groups.values())

    def _propagate(self, direct: set[int], delta: dict[str, Any]) -> tuple[set[int], set[tuple[int, int]]]:
        associated: set[int] = set(); traversed: set[tuple[int, int]] = set(); additions: dict[int, float] = {}
        minimum = self.config.propagation_activation_min
        frontier = [
            node_id for node_id, node in self.nodes.items()
            if float(node["activation"]) > 0.0 and (minimum is None or float(node["activation"]) >= minimum)
        ]
        if self.config.propagation_limit is not None:
            frontier.sort(key=lambda node_id: float(self.nodes[node_id]["activation"]), reverse=True)
        remaining = self.config.propagation_limit
        for source in frontier:
            if self._node_silenced(source):
                continue
            targets = self._outgoing.get(source, ())
            ordered_targets = sorted(targets, key=lambda target: float(self.edges[(source, target)]["weight"]), reverse=True) if remaining is not None else sorted(targets)
            for target in ordered_targets:
                if remaining is not None and remaining <= 0: break
                edge = self.edges.get((source, target))
                if edge is None: continue
                if self._edge_silenced(source, target): continue
                target_node = self.nodes.get(target)
                if target_node is None: continue
                source_response = self._inhibitory_response(self.nodes[source])
                target_response = self._inhibitory_response(target_node)
                amount = float(self.nodes[source]["activation"]) * source_response * float(edge["weight"]) * self.config.propagation_gain * (1.0 - float(target_node["activation"])) * target_response
                if self.manifest.spatial_embedding and self.manifest.parameters.get("neighborhood_enabled", True):
                    radius = max(1e-6, float(self.manifest.parameters.get("spatial_radius", 1.0))); distance = self._edge_distance(edge)
                    if distance > radius: continue
                    amount *= max(0.0, 1.0 - distance / radius)
                if amount < self.config.node_activation_floor: continue
                amount *= self._consume_energy(amount, self.config.energy_associative_cost)
                if amount < self.config.node_activation_floor: continue
                additions[target] = additions.get(target, 0.0) + amount; edge["eligibility"] = min(1.0, float(edge.get("eligibility", 0.0)) * .7 + amount); edge["last_touched_tick"] = self.tick; edge["touch_count"] = int(edge.get("touch_count", 0)) + 1
                traversed.add((source, target))
                if remaining is not None: remaining -= 1
        for target, amount in additions.items():
            if self._node_silenced(target):
                continue
            node = self.nodes[target]; node["activation"] = min(1.0, float(node["activation"]) + amount); node["associative_touch"] = float(node["associative_touch"]) + amount; node["trace"] = min(1.0, float(node["trace"]) + amount)
            if target not in direct: associated.add(target)
        return associated, traversed

    def _physical_conductance(self, source: int, target: int) -> float:
        values = [
            float(edge.get("weight", 0.0))
            for key in ((source, target), (target, source))
            if (edge := self.edges.get(key)) is not None
        ]
        return max(values, default=0.0)

    def _update_local_inhibition(self, baseline: dict[int, float], delta: dict[str, Any]) -> None:
        if not self.config.topology_inhibition_enabled:
            delta["inhibition_generated"] = 0.0
            delta["inhibition_transferred"] = 0.0
            delta["inhibition_transfer_count"] = 0
            return
        generated_total = 0.0
        for node_id, node in self.nodes.items():
            rise = max(0.0, float(node["activation"]) - float(baseline.get(node_id, 0.0)))
            generated = rise * self.config.inhibition_generation_gain
            if generated > 0.0:
                node["inhibition"] = self._saturate_inhibition(float(node.get("inhibition", 0.0)) + generated)
                generated_total += generated

        pending: dict[int, float] = {}
        transferred_total = 0.0
        transfer_count = 0
        for source in sorted(self.nodes):
            node = self.nodes[source]
            field = max(0.0, float(node.get("inhibition", 0.0)))
            neighbours = sorted(self._incident.get(source, ()))
            if field < self.config.inhibition_propagation_min or not neighbours:
                continue
            conductances = [(target, self._physical_conductance(source, target)) for target in neighbours]
            conductances = [(target, value) for target, value in conductances if value > 0.0]
            total_conductance = sum(value for _target, value in conductances)
            if total_conductance <= 0.0:
                continue
            offered = field * self.config.inhibition_diffusion
            affordable = self._consume_energy(offered, self.config.energy_inhibition_cost)
            transferred = offered * affordable
            if transferred < self.config.inhibition_propagation_min:
                continue
            node["inhibition"] = max(0.0, field - transferred)
            for target, conductance in conductances:
                share = transferred * conductance / total_conductance
                if share <= 0.0:
                    continue
                pending[target] = pending.get(target, 0.0) + share
                transfer_count += 1
            transferred_total += transferred
        for target, amount in pending.items():
            node = self.nodes.get(target)
            if node is not None:
                node["pending_inhibition"] = self._saturate_inhibition(float(node.get("pending_inhibition", 0.0)) + amount)
        delta["inhibition_generated"] = round(generated_total, 8)
        delta["inhibition_transferred"] = round(transferred_total, 8)
        delta["inhibition_transfer_count"] = transfer_count

    def _can_connect_spatially(self, source: int, target: int) -> bool:
        if not self.manifest.spatial_embedding or not self.manifest.parameters.get("neighborhood_enabled", True): return True
        return self._distance_nodes(source, target) <= max(1e-6, float(self.manifest.parameters.get("spatial_radius", 1.0)))

    def _adapt_edges(self, direct: set[int], associated: set[int], direct_groups: list[set[int]], traversed: set[tuple[int, int]], direct_impulses: dict[int, float], delta: dict[str, Any]) -> None:
        touched = direct | associated
        prior = set().union(*self._recent) if self._recent else set(); candidates: list[tuple[float, int, int]] = []
        degree_before = {node_id: 0 for node_id in self.nodes}
        for source, target in self.edges:
            degree_before[source] = degree_before.get(source, 0) + 1
            degree_before[target] = degree_before.get(target, 0) + 1
        if self.config.edge_birth_policy == "temporal-association":
            groups = [(prior | touched, touched)]
        else:
            # Local co-activation is a physical event boundary, not a global
            # capacity limit.  A single weak environmental disturbance may
            # leave an isolated trace; it must not automatically bind to every
            # recently active node merely because it arrived later in time.
            groups = [(group, group) for group in direct_groups]
        for sources, targets in groups:
            for source in sources:
                if source not in self.nodes or float(self.nodes[source]["activation"]) <= 0: continue
                for target in targets:
                    if source == target or self._edge_silenced(source, target) or not self._can_connect_spatially(source, target): continue
                    score = float(self.nodes[source]["activation"]) * float(self.nodes[target]["activation"])
                    # A zero score cannot alter an edge.  Any additional minimum
                    # is an optional package intervention applied below.
                    if score > 0.0: candidates.append((score, source, target))
        # An explicit experiment may opt into a candidate budget.  Without
        # one, no ranking or truncation is applied: all local co-active pairs
        # are allowed to adapt in their natural arrival order.
        minimum = self.config.edge_birth_activation_product_min
        if minimum is not None:
            candidates = [item for item in candidates if item[0] >= minimum]
        if self.config.edge_adaptation_limit is not None:
            candidates.sort(reverse=True)
            candidates = candidates[:self.config.edge_adaptation_limit]
        slots = None if self.config.max_edges is None else max(0, int(self.config.max_edges) - len(self.edges))
        for score, source, target in candidates:
            key = (source, target); edge = self.edges.get(key)
            if edge is None:
                if slots is not None and slots <= 0: continue
                consolidation = min(self.config.consolidation_cap, direct_impulses.get(source, 0.0) + direct_impulses.get(target, 0.0))
                # Local novelty is intentionally not an input-gate heuristic.
                # A new edge receives this small one-off bonus only when a
                # pre-existing connected neighbourhood has weak but non-zero
                # associative re-entry.  Zero propagation does not count as
                # novelty; neither does merely creating an isolated edge.
                associative_touch = max(
                    float(self.nodes[source].get("associative_touch", 0.0)),
                    float(self.nodes[target].get("associative_touch", 0.0)),
                )
                touches_existing_neighbourhood = bool(degree_before.get(source, 0) or degree_before.get(target, 0))
                local_novelty = 0.0
                if touches_existing_neighbourhood and associative_touch > 0.0:
                    local_novelty = max(0.0, 1.0 - min(1.0, associative_touch / self.config.novelty_touch_reference))
                novelty_bonus = self.config.local_novelty_gain * local_novelty
                edge = {
                    "source": source, "target": target,
                    "weight": min(1.0, self.config.edge_birth_weight * (.5 + score) + consolidation * .18 + novelty_bonus),
                    "stability": min(1.0, consolidation + novelty_bonus),
                    "eligibility": consolidation,
                    "born_tick": self.tick, "last_touched_tick": self.tick,
                    "touch_count": 0, "vector": self._edge_vector(source, target),
                    "formation_associative_touch": associative_touch,
                    "local_novelty": local_novelty,
                }
                self._add_edge(key, edge); delta["created_edges"].add(key)
                if slots is not None: slots -= 1
                if local_novelty > 0.0:
                    delta.setdefault("locally_novel_edges", set()).add(key)
            else:
                old = float(edge["weight"]); internal = 1.0 if key in traversed else .45
                consolidation = min(self.config.consolidation_cap, direct_impulses.get(source, 0.0) + direct_impulses.get(target, 0.0))
                edge["weight"] = min(1.0, old + self.config.learning_rate * score * internal * (1.0 - old) + consolidation * .08); edge["eligibility"] = min(1.0, float(edge.get("eligibility", 0.0)) + score * .3 + consolidation * .25)
                associative_consolidation = self.config.consolidation_associative_gain * float(edge.get("eligibility", 0.0)) if key in traversed else 0.0
                edge["stability"] = min(1.0, float(edge.get("stability", 0.0)) + self.config.stability_gain * score * (1.0 + math.log1p(int(edge.get("touch_count", 0)))) + consolidation + associative_consolidation); edge["last_touched_tick"] = self.tick; edge["touch_count"] = int(edge.get("touch_count", 0)) + 1
                if float(edge["weight"]) - old > self.config.response_epsilon: delta["strengthened_edges"].add(key)

    def _forget_and_prune(self, traversed: set[tuple[int, int]], delta: dict[str, Any]) -> None:
        for key, edge in list(self.edges.items()):
            old = float(edge["weight"]); edge["eligibility"] = float(edge.get("eligibility", 0.0)) * .78
            edge["stability"] = max(0.0, float(edge.get("stability", 0.0)) - self.config.stability_decay * (1.0 - float(edge["eligibility"])))
            if key not in traversed: edge["weight"] *= max(0.0, 1.0 - self.config.edge_decay * (1.0 - (.08 + .92 * float(edge["stability"]))))
            if self.config.irreversible_energy_death_enabled and self._energy_maintenance_deficit > 0.0:
                erosion = self.config.energy_starvation_structural_decay * self._energy_maintenance_deficit
                edge["stability"] = max(0.0, float(edge["stability"]) - erosion)
                edge["weight"] *= max(0.0, 1.0 - erosion)
            if old - float(edge["weight"]) > self.config.response_epsilon: delta["weakened_edges"].add(key)
            if float(edge["weight"]) < self.config.prune_threshold: self._remove_edge(key); delta["removed_edges"].add(key)
        connected = {part for edge in self.edges for part in edge}
        for node_id, node in list(self.nodes.items()):
            if self.config.irreversible_energy_death_enabled and self._energy_maintenance_deficit > 0.0:
                node["support"] = max(0.0, float(node.get("support", 0.0)) - self.config.energy_starvation_structural_decay * self._energy_maintenance_deficit)
            # Nodes disappear only after their support state itself has faded,
            # not because a separate wall-clock pruning rule selected them.
            if node_id not in connected and float(node["activation"]) == 0 and float(node.get("support", 0.0)) < self.config.node_support_prune_threshold and self.tick - int(node.get("last_touched_tick", self.tick)) > self.config.node_prune_after:
                self.nodes.pop(node_id); delta["removed_nodes"].add(node_id)
                for channel, receptor in list(self.receptor_index.items()):
                    if receptor == node_id: self.receptor_index.pop(channel)

    def _homeostasis(self) -> None:
        if not self.config.homeostasis_enabled:
            return
        total = sum(float(node["activation"]) for node in self.nodes.values())
        if total > self.config.target_total_activation:
            scale = self.config.target_total_activation / total
            for node in self.nodes.values(): node["activation"] *= scale

    def _update_nodes(self, touched: set[int]) -> None:
        for node_id in touched:
            node = self.nodes[node_id]; node["last_touched_tick"] = self.tick; node["touch_count"] = int(node["touch_count"]) + 1
            node["stability"] = min(1.0, float(node["stability"]) + self.config.stability_gain * float(node["activation"]) * .5); node["support"] = min(1.0, float(node.get("support", 0.0)) + self.config.node_support_gain * (float(node["direct_touch"]) + float(node["associative_touch"]))); node["plasticity"] = max(.12, 1.0 - float(node["stability"]) * .72)

    def _apply_competition(self) -> None:
        competition = max(0.0, min(1.0, float(self.manifest.parameters.get("spatial_competition", 0.0))))
        if not (competition and self.manifest.spatial_embedding): return
        for edge in self.spatial_neighbors():
            source, target = self.nodes.get(edge["source"]), self.nodes.get(edge["target"])
            if source and target and float(source["activation"]) > float(target["activation"]): target["activation"] *= 1.0 - competition * .12

    def _update_lifecycle(self, delta: dict[str, Any]) -> None:
        total = sum(float(node["activation"]) for node in self.nodes.values()); delta["activation_delta"] = abs(total - self._last_total_activation); self._last_total_activation = total
        if self.config.energy_simulation_enabled and self.energy_reserve <= 1e-12 and (self.nodes or self.edges):
            self._energy_starved_ticks += 1
        else:
            self._energy_starved_ticks = 0
        delta["energy_starved_ticks"] = self._energy_starved_ticks
        if self.config.irreversible_energy_death_enabled and self._energy_starved_ticks >= self.config.energy_starvation_death_ticks:
            self.die("irreversible energy starvation")
            return
        structural = sum(len(delta[name]) for name in ("created_nodes", "created_edges", "removed_nodes", "removed_edges", "strengthened_edges", "weakened_edges"))
        responsive = structural > 0 or delta["activation_delta"] > self.config.response_epsilon or bool(delta["associated_nodes"])
        self._unresponsive_ticks = self._unresponsive_ticks + 1 if delta["external_energy"] > 0 and not responsive else 0
        if self._unresponsive_ticks >= self.config.unresponsive_window: self.die("external stimulus continued but the network stopped changing")
        elif self._unresponsive_ticks >= self.config.unresponsive_window // 2: self.life_state = "unresponsive"
        elif ((self.config.max_nodes is not None and len(self.nodes) >= self.config.max_nodes) or (self.config.max_edges is not None and len(self.edges) >= self.config.max_edges)): self.life_state = "unstable"
        else: self.life_state = "active"

    def _advance(self, frames: list[SensoryFrame], *, delivery_contexts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if self.life_state == "dead": return self.metrics()
        self.tick += 1
        energy_before = self.energy_reserve
        dynamics_before = {
            int(node_id): {
                "activation": float(node.get("activation", 0.0)),
                "inhibition": float(node.get("inhibition", 0.0)),
                "support": float(node.get("support", 0.0)),
            }
            for node_id, node in self.nodes.items()
        } if self.trace_enabled else {}
        frame_sources = [str(frame.source) for frame in frames]
        if frame_sources:
            self._last_sensory_sources = list(frame_sources)
        causal_sources = list(self._last_sensory_sources)
        delta: dict[str, Any] = {
            "tick": self.tick,
            "external_energy": sum(frame.energy for frame in frames if frame.external),
            "frame_sources": frame_sources,
            # Host/input-boundary causal identities are projected outward for
            # audit and temporal readout only.  No dynamics method consults
            # this field, and it deliberately contains no carrier semantics.
            "input_envelopes": copy.deepcopy(delivery_contexts or []),
            # A passive output can emerge on a subsequent decay/propagation
            # tick, after the frame itself has left the input queue.  Retain
            # just the source provenance of the last delivered sensory frame
            # so presentation adapters can classify it honestly.
            "causal_sources": causal_sources,
            "background_only": bool(causal_sources) and all(self._is_background_source(source) for source in causal_sources),
            "created_nodes": set(), "created_edges": set(), "removed_nodes": set(), "removed_edges": set(),
            "strengthened_edges": set(), "weakened_edges": set(), "direct_nodes": set(),
            "associated_nodes": set(), "locally_novel_edges": set(),
        }
        self._apply_energy_maintenance()
        self._prepare_inhibition()
        baseline = self._decay_nodes(); accepted = self._filter_channels(frames, delta); direct, direct_impulses, direct_groups = self._apply_direct(accepted, delta); associated, traversed = self._propagate(direct, delta); delta["associated_nodes"] = associated
        delta["direct_nodes"] = direct
        self._adapt_edges(direct, associated, direct_groups, traversed, direct_impulses, delta); self._forget_and_prune(traversed, delta); self._apply_competition(); self._homeostasis(); self._update_local_inhibition(baseline, delta); self._update_nodes(direct | associated); self._recent.append(set(direct | associated)); self._update_lifecycle(delta)
        delta["energy_simulation_enabled"] = self.config.energy_simulation_enabled
        delta["energy_reserve_before"] = round(energy_before, 8) if self.config.energy_simulation_enabled else None
        delta["energy_reserve_after"] = round(self.energy_reserve, 8) if self.config.energy_simulation_enabled else None
        delta["energy_consumed"] = round(max(0.0, energy_before - self.energy_reserve), 8) if self.config.energy_simulation_enabled else 0.0
        delta["energy_maintenance_deficit"] = round(self._energy_maintenance_deficit, 8)
        if self.trace_enabled:
            node_dynamics: list[dict[str, Any]] = []
            for node_id, node in self.nodes.items():
                before = dynamics_before.get(int(node_id), {"activation": 0.0, "inhibition": 0.0, "support": 0.0})
                after = {
                    "activation": float(node.get("activation", 0.0)),
                    "inhibition": float(node.get("inhibition", 0.0)),
                    "support": float(node.get("support", 0.0)),
                }
                # Detailed tracing is explicitly opt-in, so preserve every
                # numerically real change rather than reusing the much larger
                # lifecycle responsiveness threshold as a storage filter.
                changed = any(abs(after[name] - float(before[name])) > 1e-12 for name in after)
                if changed or float(node.get("direct_touch", 0.0)) > 0.0 or float(node.get("associative_touch", 0.0)) > 0.0:
                    node_dynamics.append({
                        "id": int(node_id), "before": before, "after": after,
                        "direct_touch": round(float(node.get("direct_touch", 0.0)), 8),
                        "associative_touch": round(float(node.get("associative_touch", 0.0)), 8),
                        "pending_inhibition": round(float(node.get("pending_inhibition", 0.0)), 8),
                    })
            delta["node_dynamics"] = node_dynamics
        self._last_delta = {key: sorted(value) if isinstance(value, set) else value for key, value in delta.items()}
        if self.trace_enabled:
            self.trace_entries.append(copy.deepcopy(self._last_delta))
            self.trace_entries = self.trace_entries[-20_000:]
            self.package.logs["trace"] = self.trace_entries
        self.output_bus.publish(self._make_output_frame())
        return self.metrics()

    def _advance_input_epoch(self) -> None:
        """Run one environmental epoch without ever merging due frames."""
        with self._lock:
            due = self._take_due_frames()
        if due:
            # Individual causal frames receive individual Core transitions.
            # The lock is intentionally released between them so HTTP/status
            # observers remain responsive while a long carrier is arriving.
            for scheduled in due:
                with self._lock:
                    if self.life_state == "dead" or self._paused:
                        return
                    self._advance([scheduled.frame], delivery_contexts=[{
                        "envelope_id": scheduled.envelope_id,
                        "frame_index": scheduled.frame_index,
                        "frame_count": scheduled.frame_count,
                        "sequence": scheduled.sequence,
                        "adapter_id": scheduled.adapter_id,
                        "source": scheduled.frame.source,
                    }])
                    self._record_frame_delivery(scheduled)
        else:
            with self._lock:
                if self.life_state != "dead" and not self._paused:
                    self._advance([])

    def step(self, *, ticks: int = 1) -> dict[str, Any]:
        if ticks < 1: raise ValueError("ticks must be positive")
        # An explicit caller-requested number of environmental epochs is not a
        # semantic budget.  In particular, an offline CLI operation must be
        # able to drain every frame of a long, faithfully retained carrier.
        for _ in range(ticks):
            if self.life_state == "dead" or self._paused:
                break
            self._advance_input_epoch()
        return self.metrics()

    def start(self, *, paused: bool = False) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive(): self._paused = bool(paused); return
            self._stop_event.clear(); self._paused = bool(paused); self._thread = threading.Thread(target=self._run_loop, name="threemind-core", daemon=True); self._thread.start()

    def _run_loop(self) -> None:
        while not self._stop_event.wait(max(.002, self.config.tick_seconds)):
            if self._paused or self.life_state == "dead": continue
            self._advance_input_epoch()

    def pause(self) -> None: self._paused = True
    def resume(self) -> None:
        if self.life_state == "dead": raise RuntimeError("consciousness is dead")
        self._paused = False
    def stop(self, reason: str = "runtime stopped") -> None: self._stop_event.set(); self.die(reason)
    def running(self) -> bool: return bool(self._thread and self._thread.is_alive())

    def set_source(self, source: str, enabled: bool, *, confirm_last: bool = False) -> dict[str, bool]:
        if source not in {"manual", "ambient", "ai"}: raise ValueError(f"unknown stimulus source: {source}")
        if not enabled and not confirm_last and not any(value for key, value in self.sources.items() if key != source): raise ValueError("disabling the last stimulus source requires explicit confirmation")
        self.sources[source] = bool(enabled); return dict(self.sources)

    def source_status(self) -> dict[str, bool]: return dict(self.sources)

    def set_trace(self, enabled: bool) -> bool:
        with self._lock:
            next_enabled = bool(enabled)
            if self.trace_enabled == next_enabled:
                return self.trace_enabled
            self.trace_enabled = next_enabled
            if self.trace_enabled:
                # A full, non-causal observation keyframe lets an external
                # dynamics analyser reconstruct every following sparse delta.
                # The keyframe is output-only metadata and is never read by
                # activation, learning, forgetting, or inhibition rules.
                self.trace_entries = [{
                    "kind": "dynamics_keyframe",
                    "tick": self.tick,
                    "node_count": len(self.nodes),
                    "edge_count": len(self.edges),
                    "nodes": [
                        {
                            "id": int(node_id),
                            "activation": round(float(node.get("activation", 0.0)), 8),
                            "inhibition": round(float(node.get("inhibition", 0.0)), 8),
                            "support": round(float(node.get("support", 0.0)), 8),
                        }
                        for node_id, node in self.nodes.items()
                    ],
                    "edges": [
                        {
                            "source": int(edge["source"]),
                            "target": int(edge["target"]),
                            "weight": round(float(edge.get("weight", 0.0)), 8),
                            "stability": round(float(edge.get("stability", 0.0)), 8),
                        }
                        for edge in self.edges.values()
                    ],
                    "energy_reserve": round(self.energy_reserve, 8) if self.config.energy_simulation_enabled else None,
                }]
                self.package.logs["trace"] = self.trace_entries
            self._history_revision += 1
            return self.trace_enabled

    def set_filter_bypass_sources(self, sources: Iterable[str]) -> list[str]:
        allowed = {"manual", "ambient", "ai"}
        self.filter_bypass_sources = {str(source) for source in sources if str(source) in allowed}
        return sorted(self.filter_bypass_sources)

    def set_attention_modulators(self, modulators: Iterable[AttentionModulator]) -> list[str]:
        with self._lock:
            self.attention_gate.replace(modulators)
            return self.attention_gate.modulator_ids

    def configure_model(self, *, parameters: dict[str, Any], spatial_dimensions: int | None = None) -> None:
        with self._lock:
            energy_was_enabled = self.config.energy_simulation_enabled
            if spatial_dimensions is not None: self.manifest.spatial_dimensions = int(spatial_dimensions)
            for name, value in parameters.items():
                if value is None:
                    self.manifest.parameters.pop(name, None)
                else:
                    self.manifest.parameters[name] = value
            self.manifest.validate(); self.config = RuntimeConfig.from_manifest(self.manifest)
            if not self.config.energy_simulation_enabled:
                self.energy_reserve = 0.0
                self._energy_starved_ticks = 0
            elif not energy_was_enabled:
                self.energy_reserve = min(self.config.energy_capacity, self.config.energy_initial_reserve)
                self._energy_starved_ticks = 0
            else:
                self.energy_reserve = min(self.config.energy_capacity, self.energy_reserve)
            if not self.config.topology_inhibition_enabled:
                for node in self.nodes.values():
                    node["inhibition"] = 0.0
                    node["pending_inhibition"] = 0.0
            self._recent = deque(self._recent, maxlen=int(self.config.association_window))
            for node in self.nodes.values(): node["position"] = self._position(int(node["id"]))
            for edge in self.edges.values(): edge["vector"] = self._edge_vector(int(edge["source"]), int(edge["target"]))
            self._reindex_spatial_edges()

    def _reindex_spatial_edges(self) -> None:
        self._spatial_edge_keys.clear()
        if not self.manifest.spatial_embedding:
            return
        radius = max(1e-6, float(self.manifest.parameters.get("spatial_radius", 1.0)))
        for key, edge in self.edges.items():
            if self._edge_distance(edge) <= radius:
                self._spatial_edge_keys.add(key)

    def _position(self, node_id: int) -> list[float] | None:
        if not self.manifest.spatial_embedding: return None
        values = []
        for index in range(self.manifest.spatial_dimensions):
            digest = hashlib.blake2b(f"{self.sensory_seed}:{node_id}:{index}".encode(), digest_size=4).digest(); values.append(int.from_bytes(digest, "big") / 2**31 - 1.0)
        return values

    def _edge_vector(self, source: int, target: int) -> list[float] | None:
        a, b = self.nodes.get(source, {}).get("position"), self.nodes.get(target, {}).get("position")
        return [round(float(y) - float(x), 8) for x, y in zip(a, b)] if a is not None and b is not None else None
    def _edge_distance(self, edge: dict[str, Any]) -> float: return math.sqrt(sum(float(value) ** 2 for value in (edge.get("vector") or [])))
    def _distance_nodes(self, source: int, target: int) -> float:
        vector = self._edge_vector(source, target) or []; return math.sqrt(sum(value * value for value in vector))

    def spatial_neighbors(self) -> list[dict[str, Any]]:
        if not self.manifest.spatial_embedding: return []
        return [{**self.edges[key], "distance": self._edge_distance(self.edges[key])} for key in self._spatial_edge_keys if key in self.edges]
    def spatial_clusters(self) -> dict[int, int]:
        parent: dict[int, int] = {}
        def find(value: int) -> int:
            while parent.get(value, value) != value: parent[value] = parent[parent[value]]; value = parent[value]
            return value
        for edge in self.spatial_neighbors():
            a, b = int(edge["source"]), int(edge["target"]); parent.setdefault(a, a); parent.setdefault(b, b); parent[find(a)] = find(b)
        roots = {root: index for index, root in enumerate(sorted({find(value) for value in parent}), 1)}; return {node: roots[find(node)] for node in parent}
    def spatial_cluster_count(self) -> int: return len(set(self.spatial_clusters().values()))

    def metrics(self) -> dict[str, Any]:
        activations = [float(node["activation"]) for node in self.nodes.values()]; weights = [float(edge["weight"]) for edge in self.edges.values()]
        inhibitions = [float(node.get("inhibition", 0.0)) for node in self.nodes.values()]
        return {"id": self.consciousness_id, "tick": self.tick, "consciousness_id": self.consciousness_id, "name": self.consciousness_name, "life_state": self.life_state, "death_reason": self.death_reason, "node_count": len(self.nodes), "edge_count": len(self.edges), "active_nodes": sum(value > self.config.node_activation_floor for value in activations), "total_activation": round(sum(activations), 6), "total_inhibition": round(sum(inhibitions), 6), "inhibited_nodes": sum(value > self.config.inhibition_propagation_min for value in inhibitions), "mean_edge_weight": round(sum(weights) / len(weights), 6) if weights else 0.0, "mean_stability": round(sum(float(node["stability"]) for node in self.nodes.values()) / len(self.nodes), 6) if self.nodes else 0.0, "kernel_id": self.manifest.kernel_id, "spatial_embedding": self.manifest.spatial_embedding, "spatial_dimensions": self.manifest.spatial_dimensions, "topology_inhibition_enabled": self.config.topology_inhibition_enabled, "energy_simulation_enabled": self.config.energy_simulation_enabled, "energy_reserve": round(self.energy_reserve, 8) if self.config.energy_simulation_enabled else None, "energy_capacity": self.config.energy_capacity if self.config.energy_simulation_enabled else None, "energy_starved_ticks": self._energy_starved_ticks if self.config.energy_simulation_enabled else 0, "trace_enabled": self.trace_enabled, "sources": self.source_status(), "attention_modulators": self.attention_gate.modulator_ids, "queued_stimuli": self.queue_size(), "input_epoch": self._input_epoch, "spatial_neighbor_edges": len(self.spatial_neighbors()), "spatial_clusters": self.spatial_cluster_count(), "history_revision": self._history_revision, "intervention": self.intervention_status(), "last_delta": self._last_delta}

    def _make_output_frame(self) -> OutputFrame:
        """Produce the complete anonymous output projection.

        Individual observers may explicitly request a reduced interpretation,
        but the output boundary itself must not silently discard activity.
        """
        ranked = tuple(self.nodes.values())
        nodes = tuple({
            "id": int(node["id"]), "activation": round(float(node["activation"]), 8),
            "trace": round(float(node["trace"]), 8), "stability": round(float(node["stability"]), 8),
            "inhibition": round(float(node.get("inhibition", 0.0)), 8),
            "pending_inhibition": round(float(node.get("pending_inhibition", 0.0)), 8),
            "touch_count": int(node["touch_count"]), "direct_touch": round(float(node.get("direct_touch", 0.0)), 8),
            "associative_touch": round(float(node.get("associative_touch", 0.0)), 8),
            "position": list(node["position"]) if node.get("position") is not None else None,
        } for node in ranked)
        edges = tuple({
            "source": int(edge["source"]), "target": int(edge["target"]),
            "weight": round(float(edge["weight"]), 8), "stability": round(float(edge.get("stability", 0.0)), 8),
        } for edge in self.edges.values())
        return OutputFrame(
            consciousness_id=self.consciousness_id, tick=self.tick, life_state=self.life_state,
            metrics=self.metrics(), nodes=nodes, edges=edges, delta=copy.deepcopy(self._last_delta),
        )

    def latest_output(self) -> OutputFrame:
        """Return the most recently published output-bus frame."""
        frame = self.output_bus.latest()
        if frame is None:  # Defensive only: an initial frame is published above.
            raise RuntimeError("output bus has no published frame")
        return frame

    def record_observation(self, event: dict[str, Any]) -> dict[str, Any]:
        """Persist an observation made by an external output adapter."""
        with self._lock:
            stored = {**event, "consciousness_id": self.consciousness_id, "tick": int(event.get("tick", self.tick))}
            self.events.append(stored)
            self.package.logs.setdefault("observations", []).append(stored)
            self._history_revision += 1
            return stored

    def observe(self, config: dict[str, Any]) -> dict[str, Any]:
        threshold = float(config.get("activation_threshold", .055)); min_nodes = int(config.get("min_nodes", 3)); max_nodes = int(config.get("max_nodes", 7)); min_edges = int(config.get("min_internal_edges", 2)); window = int(config.get("recurrence_window_ticks", 240)); min_occurrences = int(config.get("min_occurrences", 4)); min_span = int(config.get("min_span_ticks", 8)); cooldown = int(config.get("alert_cooldown_ticks", 1200))
        selected = sorted((node for node in self.nodes.values() if float(node["activation"]) >= threshold), key=lambda node: float(node["activation"]), reverse=True)[:max_nodes]
        if len(selected) < min_nodes: return {"current": {"tick": self.tick, "text": "(no repeatable structural pattern)", "occurrences": 0, "internal_edges": 0, "repeatable": False}, "events": self.package.logs.get("observations", [])[-100:], "config": config}
        ids = {int(node["id"]) for node in selected}; internal = [edge for edge in self.edges.values() if int(edge["source"]) in ids and int(edge["target"]) in ids]
        if len(internal) < min_edges: return {"current": {"tick": self.tick, "text": "(no repeatable structural pattern)", "occurrences": 0, "internal_edges": len(internal), "repeatable": False}, "events": self.package.logs.get("observations", [])[-100:], "config": config}
        fingerprint = [(round(float(node["activation"]) * 5), round(float(node["stability"]) * 5), min(4, int(node["touch_count"]) // 3)) for node in selected]
        edge_fingerprint = sorted((round(float(edge["weight"]) * 5), round(float(edge.get("stability", 0.0)) * 5)) for edge in internal)
        signature = hashlib.blake2b(repr((sorted(fingerprint), edge_fingerprint)).encode(), digest_size=8).hexdigest()
        occurrences = [tick for tick in self._observation_occurrences.get(signature, []) if self.tick - tick <= window] + [self.tick]; self._observation_occurrences[signature] = occurrences
        # Core intentionally has no access to display annotations. Readable
        # rendering belongs to output adapters at the output boundary.
        text = f"anonymous structure {signature}"
        current = {"tick": self.tick, "text": text, "signature": signature, "node_ids": sorted(ids), "internal_edges": len(internal), "mean_activation": round(sum(float(node["activation"]) for node in selected) / len(selected), 6), "occurrences": len(occurrences), "repeatable": False}
        if len(occurrences) >= min_occurrences and occurrences[-1] - occurrences[0] >= min_span and self.tick - self._observation_cooldowns.get(signature, -cooldown) >= cooldown:
            current["repeatable"] = True; self._observation_cooldowns[signature] = self.tick
            event = {"id": f"struct-{self.consciousness_id[:8]}-{signature}-{self.tick}", "kind": "repeatable_anonymous_structure", "consciousness_id": self.consciousness_id, "tick": self.tick, "first_seen_tick": occurrences[0], "last_seen_tick": occurrences[-1], "occurrences": len(occurrences), "signature": signature, "node_ids": sorted(ids), "internal_edges": len(internal), "mean_activation": current["mean_activation"], "readout": text, "delivery": {"state": "not_configured"}}
            self.events.append(event); self.package.logs.setdefault("observations", []).append(event)
        return {"current": current, "events": self.package.logs.get("observations", [])[-100:], "config": config}

    def graph(self, limit: int | None = None) -> dict[str, Any]:
        """Return a full graph by default; ``limit`` is an explicit view choice."""
        ranked = sorted(self.nodes.values(), key=lambda node: (float(node["activation"]), float(node["trace"]), float(node["stability"])), reverse=True)
        if limit is not None:
            ranked = ranked[:max(1, int(limit))]
        allowed = {node["id"] for node in ranked}; clusters = self.spatial_clusters()
        nodes = [{**dict(node), "feature": "", "direct": float(node.get("direct_touch", 0.0)), "associative": float(node.get("associative_touch", 0.0)), "source": "anonymous", "cluster": clusters.get(int(node["id"]))} for node in ranked]
        edges = [{**dict(edge), "touched": int(edge.get("last_touched_tick", -1)) == self.tick} for edge in self.edges.values() if edge["source"] in allowed and edge["target"] in allowed]
        return {"metrics": self.metrics(), "manifest": self.manifest.to_dict(), "nodes": nodes, "edges": edges, "neighbors": self.spatial_neighbors() if self.manifest.spatial_embedding else []}

    def observation_snapshot(self) -> dict[str, Any]:
        """Compatibility snapshot for external interpreters, sourced from OutputBus."""
        output = self.latest_output()
        return {
            "metrics": output.metrics,
            "output_frame": {
                "tick": output.tick, "life_state": output.life_state,
                "nodes": list(output.nodes), "edges": list(output.edges), "delta": output.delta,
            },
            "recent_stimuli": self.stimuli[-12:],
            "recent_events": self.events[-12:],
        }
    def record_interpretation(self, text: str, *, provider_id: str, trigger: str = "periodic", important: bool = False) -> dict[str, Any]:
        with self._lock:
            event = {"tick": self.tick, "text": str(text), "provider_id": provider_id, "trigger": trigger, "important": bool(important), "created_at": time.time()}; self.interpretations.append(event); self.events.append({"tick": self.tick, "kind": "interpretation", "trigger": trigger, "important": bool(important)}); self.package.logs.setdefault("interpretations", []).append(event); self._history_revision += 1; return event
    def die(self, reason: str = "stopped") -> None:
        with self._lock:
            if self.life_state == "dead": return
            self.life_state = "dead"; self.death_reason = str(reason); event = {"tick": self.tick, "kind": "death", "reason": self.death_reason}; self.events.append(event); self.package.logs.setdefault("events", []).append(event); self._history_revision += 1

    def history_snapshot(self) -> dict[str, Any]:
        """Copy the complete externally observable history under the runtime lock.

        The host persistence service consumes this immutable copy on its own
        worker thread.  Core therefore remains independent of files,
        databases, and transport latency, while a graceful restart can recover
        the same research records that the live management view exposes.

        This is deliberately a full checkpoint rather than an event delta:
        coalescing redundant writes cannot discard an intervening stimulus or
        readout, because a later checkpoint contains every earlier record.
        """
        with self._lock:
            logs = copy.deepcopy(self.package.logs)
            return {
                "record_type": "history_checkpoint",
                "consciousness_id": self.consciousness_id,
                "consciousness_name": self.consciousness_name,
                "tick": self.tick,
                "life_state": self.life_state,
                "death_reason": self.death_reason,
                "history_revision": self._history_revision,
                "captured_at": time.time(),
                "events": copy.deepcopy(self.events),
                "stimuli": copy.deepcopy(self.stimuli),
                "interpretations": copy.deepcopy(self.interpretations),
                "observations": copy.deepcopy(logs.get("observations", [])),
                "trace_entries": copy.deepcopy(self.trace_entries),
                "logs": logs,
            }

    def state_dict(self) -> dict[str, Any]:
        with self._lock:
            queued = [scheduled.to_dict() for _epoch, _sequence, scheduled in sorted(self._frame_pending)]
            return {"tick": self.tick, "life_state": self.life_state, "death_reason": self.death_reason, "nodes": list(self.nodes.values()), "edges": list(self.edges.values()), "events": self.events, "stimuli": self.stimuli, "logs": self.package.logs, "sources": self.source_status(), "filter_bypass_sources": sorted(self.filter_bypass_sources), "interpretations": self.interpretations, "history_revision": self._history_revision, "sensory_seed": self.sensory_seed, "receptor_index": self.receptor_index, "channel_labels": self.channel_labels, "node_annotations": self.node_annotations, "next_node_id": self._next_node_id, "recent": [sorted(group) for group in self._recent], "unresponsive_ticks": self._unresponsive_ticks, "last_total_activation": self._last_total_activation, "observation_occurrences": self._observation_occurrences, "observation_cooldowns": self._observation_cooldowns, "last_delta": self._last_delta, "last_sensory_sources": list(self._last_sensory_sources), "trace_enabled": self.trace_enabled, "trace_entries": self.trace_entries[-20_000:], "energy_reserve": self.energy_reserve, "energy_supplied_total": self.energy_supplied_total, "energy_consumed_total": self.energy_consumed_total, "energy_starved_ticks": self._energy_starved_ticks, "input_epoch": self._input_epoch, "input_sequence": self._input_sequence, "input_queue": queued}
    def save_package(self, path: str, *, archive: dict[str, Any] | None = None) -> str:
        """Persist a model package with explicit artifact provenance.

        A package save is not silently a snapshot.  The optional archive
        descriptor belongs to the saved file and is intentionally outside the
        network state, so archive-management code can be exact without
        feeding persistence metadata back into consciousness dynamics.
        """
        with self._lock:
            self.package.state = self.state_dict()
            self.package.archive = dict(archive or {
                "id": str(uuid.uuid4()),
                "kind": "package",
                "label": self.consciousness_name,
                "created_at": time.time(),
                "automatic": False,
                "reason": "package_save",
            })
            self.package.save(path)
            return path

    def capture_snapshot_package(
        self,
        *,
        portrait: bool = False,
        label: str | None = None,
        automatic: bool = False,
        reason: str = "manual",
    ) -> ModelPackage:
        """Capture an immutable archive package without performing file I/O.

        The Core records the archival event and takes a coherent package copy
        while holding its own lock.  Compression and disk/database work can
        then happen outside the runtime tick on an archive writer thread.
        """
        with self._lock:
            created_at = time.time()
            kind = "portrait" if portrait else "snapshot"
            record_id = str(uuid.uuid4())
            archive = {
                "id": record_id,
                "kind": kind,
                "label": label or kind,
                "created_at": created_at,
                "automatic": bool(automatic),
                "reason": str(reason),
            }
            event = {
                "tick": self.tick,
                "kind": "archive_created",
                "archive_id": record_id,
                "archive_kind": kind,
                "automatic": bool(automatic),
                "reason": str(reason),
                "label": archive["label"],
                "created_at": created_at,
            }
            self.events.append(event)
            self.package.logs.setdefault("events", []).append(dict(event))
            self._history_revision += 1
            self.package.state = self.state_dict()
            record = {
                **archive,
                "tick": self.tick,
                "saved_at": created_at,
                "metrics": self.metrics(),
                "state": copy.deepcopy(self.package.state),
            }
            (self.package.portraits if portrait else self.package.snapshots).append(record)
            self.package.archive = dict(archive)
            return copy.deepcopy(self.package)

    def snapshot(
        self,
        path: str,
        *,
        portrait: bool = False,
        label: str | None = None,
        automatic: bool = False,
        reason: str = "manual",
    ) -> str:
        """Capture an auditable snapshot or portrait and write one archive.

        The record keeps the exact state used by the file, plus whether it was
        manually requested or produced by a named automatic rule.  This is
        observational metadata only; it never alters graph evolution.
        """
        package = self.capture_snapshot_package(
            portrait=portrait,
            label=label,
            automatic=automatic,
            reason=reason,
        )
        package.save(path)
        return path
