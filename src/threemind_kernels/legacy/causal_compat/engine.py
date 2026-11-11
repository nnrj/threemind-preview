from __future__ import annotations

import copy
import hashlib
import heapq
import json
import math
import struct
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from .attention import Attention, modulation_payload
from .energy import Energy, supply_payload
from .resources import Resources
from .spatial import Spatial
from .spec import (
    ATTENTION_DEFAULTS,
    ATTENTION_DYNAMICS,
    ATTENTION_VERSIONS,
    BUDGET_DYNAMICS,
    DYNAMICS,
    ENERGY_DEFAULTS,
    ENERGY_DYNAMICS,
    ENERGY_VERSIONS,
    LEGACY_DYNAMICS,
    MAX_TIME,
    OPTIONAL_DYNAMICS,
    RESOURCE_VERSIONS,
    SPATIAL_VERSIONS,
    STATE_SCHEMAS,
    Config,
    Stimulus,
    timestamp,
)


def canonical_bytes(value: object) -> bytes:
    """Float bits and decimal timestamps survive JSON/binary conversions exactly."""

    def normalize(item: object) -> object:
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("nonfinite state")
            return {"$f64": struct.pack(">d", item).hex()}
        if isinstance(item, dict):
            return {str(k): normalize(v) for k, v in sorted(item.items())}
        if isinstance(item, (list, tuple)):
            return [normalize(v) for v in item]
        return item

    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass(frozen=True, slots=True)
class StateImage:
    """Owned immutable bytes; capturing a running model never shares mutable arrays."""

    payload: bytes
    _digest: str | None = field(default=None, init=False, repr=False, compare=False)

    def to_dict(self) -> dict:
        return json.loads(self.payload)

    @property
    def digest(self) -> str:
        if self._digest is None:
            try:
                from _threemind_native import canonical_hash
            except ImportError:
                digest = hashlib.sha256(canonical_bytes(self.to_dict())).hexdigest()
            else:
                digest = canonical_hash(self.payload)
            object.__setattr__(self, "_digest", digest)
        return self._digest

    @classmethod
    def from_dict(cls, value: dict) -> StateImage:
        return cls(json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True).encode())


@dataclass(slots=True)
class Node:
    id: int
    channel: int
    activation: float = 0.0
    inhibition: float = 0.0
    trace: float = 0.0
    support: float = 0.0
    stability: float = 0.0
    direct: float = 0.0
    associative: float = 0.0
    touches: int = 0
    last_touch_us: str = "0"


@dataclass(slots=True)
class Edge:
    source: int
    target: int
    weight: float
    stability: float = 0.0
    eligibility: float = 0.0
    touches: int = 0
    birth_us: str = "0"
    last_touch_us: str = "0"


class Engine:
    """Hybrid event/clock dynamics. No wall clock, persistence, labels or observers.

    Numerical work occurs on a fixed lattice and at actual event timestamps.
    An advance request between boundaries only moves the observation horizon;
    it cannot introduce an extra numerical step. State retains this phase.
    """

    def __init__(self, config: Config | None = None, state: StateImage | None = None, *, dynamics: str = DYNAMICS) -> None:
        self.config = config or Config()
        self.dynamics = dynamics
        self.resources = Resources()
        self.energy = Energy.initial(self.config)
        self.attention = Attention()
        self.spatial = Spatial()
        self.time_us = 0
        self.state_time_us = 0
        self.next_step_us = self.config.step_us
        self.sequence = 0
        self.next_event = 0
        self.next_node = 1
        self.sources_open = True
        self.life = "waiting"
        self.nodes: dict[int, Node] = {}
        self.edges: dict[tuple[int, int], Edge] = {}
        self.receptors: dict[int, int] = {}
        self.outgoing: dict[int, set[int]] = {}
        self.incident: dict[int, set[int]] = {}
        self.queue: list[tuple[int, int, str, dict]] = []
        self.silenced_nodes: set[int] = set()
        self.silenced_edges: set[tuple[int, int]] = set()
        if state is not None:
            self._restore(state)

    def _event(self, when: int, kind: str, payload: dict) -> None:
        timestamp(when)
        self.next_event += 1
        heapq.heappush(self.queue, (when, self.next_event, kind, payload))

    def inject(self, stimulus: Stimulus) -> int:
        if self.life == "dead":
            raise ValueError("a dead instance requires an explicit new birth")
        if not self.sources_open:
            raise ValueError("inputs are closed")
        if stimulus.time_us < self.time_us:
            raise ValueError("late stimulus violates the causal boundary")
        if stimulus.bypass_attention and self.dynamics != DYNAMICS:
            self._relax(self.time_us)
            self._upgrade_attention()
            self.dynamics = DYNAMICS
        self._event(stimulus.time_us, "stimulus", stimulus.to_dict())
        return self.next_event

    def close_inputs(self) -> None:
        self.sources_open = False
        self.sequence += 1
        self._lifecycle()

    def supply_energy(self, amount: float, *, time_us: int | None = None, source="external-energy") -> int:
        if not self.sources_open:
            raise ValueError("external inputs and supply are closed")
        if self.life == "dead":
            raise ValueError("a dead instance requires an explicit new birth")
        if not self.config.energy_simulation_enabled:
            raise ValueError("energy simulation is disabled")
        when = self.time_us if time_us is None else timestamp(time_us)
        if when < self.time_us:
            raise ValueError("late energy supply violates the causal boundary")
        self._event(when, "energy", supply_payload(amount, source))
        return self.next_event

    def reconfigure(self, config: Config) -> None:
        """Apply an explicit intervention at the current observation horizon.

        Materialize elapsed time under the OLD parameters. Preserve the solver
        lattice and every in-flight event; new delays affect future emissions.
        Calling this with an identical configuration is an exact no-op.
        """
        if any(getattr(config, k) != getattr(self.config, k) for k in ("step_us", "seed", "energy_initial_reserve")):
            raise ValueError("step_us, seed and energy_initial_reserve are immutable after creation")
        if config == self.config:
            return
        if self.life == "dead":
            raise ValueError("a dead instance requires an explicit new birth")
        self._relax(self.time_us)
        before = self.config
        self.config = config
        if config.has_spatial_changes() and self.dynamics not in SPATIAL_VERSIONS:
            self._upgrade_attention()
            self.dynamics = DYNAMICS
        elif config.has_attention_changes() and self.dynamics not in ATTENTION_VERSIONS:
            self._upgrade_attention()
        elif config.has_energy_changes() and self.dynamics not in ENERGY_VERSIONS:
            if self.dynamics != BUDGET_DYNAMICS:
                self.resources = Resources(since_us=str(self.time_us))
            self.dynamics = ENERGY_DYNAMICS
            self.energy = Energy.initial(config, self.time_us)
        elif config.has_budget_limits() and self.dynamics not in RESOURCE_VERSIONS:
            self.dynamics = BUDGET_DYNAMICS
            self.resources = Resources(since_us=str(self.time_us))
        elif config.has_optional_changes() and self.dynamics == LEGACY_DYNAMICS:
            self.dynamics = OPTIONAL_DYNAMICS
        if self.dynamics in ENERGY_VERSIONS:
            self.energy.resize(config.energy_capacity)
            if (before.energy_simulation_enabled, before.irreversible_energy_death_enabled) != (
                config.energy_simulation_enabled,
                config.irreversible_energy_death_enabled,
            ):
                self.energy.starved_since_us = None
                self.energy.last_settlement_us = str(self.time_us)
                self.energy.last_maintenance_deficit = 0.0
        for node in self.nodes.values():
            node.inhibition = min(node.inhibition, config.inhibition_saturation)
        self.spatial.sync(config, self.nodes)
        self._homeostasis()
        self._energy_lifecycle()
        self.sequence += 1

    def _upgrade_attention(self):
        if self.dynamics in ATTENTION_VERSIONS:
            return
        if self.dynamics not in RESOURCE_VERSIONS:
            self.resources = Resources(since_us=str(self.time_us))
        if self.dynamics not in ENERGY_VERSIONS:
            self.energy = Energy.initial(self.config, self.time_us)
        self.attention = Attention(since_us=str(self.time_us))
        self.dynamics = ATTENTION_DYNAMICS

    def modulate_input(self, *, time_us=None, **adjustment):
        payload = modulation_payload(**adjustment)
        if not self.sources_open:
            raise ValueError("external inputs and control ports are closed")
        when = self.time_us if time_us is None else timestamp(time_us)
        if self.life == "dead":
            raise ValueError("a dead instance requires an explicit new birth")
        if when < self.time_us or when > MAX_TIME - payload["ttl_us"]:
            raise ValueError("modulation timestamp violates the causal boundary")
        if self.dynamics not in ATTENTION_VERSIONS:
            self._relax(self.time_us)
            self._upgrade_attention()
        self._event(when, "modulation", payload)
        return self.next_event

    def _maintain_energy(self, when: int, duration_us: int):
        c = self.config
        if not (c.energy_simulation_enabled and c.irreversible_energy_death_enabled):
            return
        duration = self.energy.maintain(when, duration_us, len(self.nodes), len(self.edges), c)
        if duration > 0 and c.energy_starvation_structural_decay > 0:
            factor = math.exp(-c.energy_starvation_structural_decay * duration)
            for n in self.nodes.values():
                n.support *= factor
            for e in self.edges.values():
                e.weight *= factor
                e.stability *= factor

    def _energy_deadline(self):
        if self.energy.starved_since_us is None:
            return None
        return max(self.time_us, int(self.energy.starved_since_us) + self.config.energy_starvation_death_us)

    def _energy_lifecycle(self):
        c = self.config
        if self.life == "dead":
            return
        if (
            c.energy_simulation_enabled
            and c.irreversible_energy_death_enabled
            and self.energy.reserve == 0
            and (self.nodes or self.edges)
        ):
            if self.energy.starved_since_us is None:
                self.energy.starved_since_us = str(self.time_us)
            if self.time_us - int(self.energy.starved_since_us) >= c.energy_starvation_death_us:
                for n in self.nodes.values():
                    n.activation = n.direct = n.associative = n.inhibition = n.trace = 0.0
                self.queue.clear()
                self.sources_open = False
                self.life = "dead"
                self.energy.death_us = str(self.time_us)
        else:
            self.energy.starved_since_us = None

    def advance_to(
        self, target_us: int, observer: Callable[[dict], None] | None = None, *, inputs_only: bool = False
    ) -> None:
        target_us = timestamp(target_us)
        if target_us < self.time_us:
            raise ValueError("simulation time cannot go backwards")
        if target_us > MAX_TIME - self.config.step_us - self.config.delay_us:
            raise ValueError("time too close to representational limit")
        while self.life != "dead":
            # Empty systems can skip geological spans without iterating empty ticks.
            if not self.nodes:
                if not self.queue or self.queue[0][0] > target_us:
                    self.time_us = target_us
                    self.state_time_us = target_us
                    self.next_step_us = (target_us // self.config.step_us + 1) * self.config.step_us
                    break
                event_time = self.queue[0][0]
                self.next_step_us = max(
                    self.next_step_us,
                    ((event_time + self.config.step_us - 1) // self.config.step_us) * self.config.step_us,
                )
            else:
                event_time = self.next_step_us
            if self.queue:
                event_time = min(event_time, self.queue[0][0])
            deadline = self._energy_deadline()
            if deadline is not None:
                event_time = min(event_time, deadline)
            if event_time > target_us:
                break
            self._relax(event_time)
            self.time_us = event_time
            # All already scheduled events at t arrive before emission at t.
            while self.queue and self.queue[0][0] == event_time:
                _, event_id, kind, payload = heapq.heappop(self.queue)
                observed_payload = payload
                selection = None
                if kind == "stimulus":
                    stimulus = Stimulus.from_dict(payload)
                    if self.dynamics in ATTENTION_VERSIONS:
                        stimulus, selection = self.attention.select(stimulus, self.config)
                    self._stimulate(stimulus)
                elif kind == "signal":
                    touched = []
                    for node_id, value in payload["values"]:
                        amount = self._touch(node_id, value, direct=False)
                        if amount > 0:
                            touched.append((node_id, amount, 0.0))
                    if self.config.edge_birth_policy == "temporal-association":
                        self._associate(touched)
                elif kind == "inhibition":
                    for node_id, value in payload["values"]:
                        if node_id in self.nodes and self.config.inhibition:
                            n = self.nodes[node_id]
                            n.inhibition = min(self.config.inhibition_saturation, n.inhibition + value)
                elif kind == "energy":
                    observed_payload = payload | self.energy.supply(
                        payload["amount"], self.config.energy_capacity, self.config.energy_simulation_enabled
                    )
                elif kind == "modulation":
                    observed_payload = payload | self.attention.update(payload, self.time_us)
                self.sequence += 1
                if observer is not None and (not inputs_only or kind in ("stimulus", "energy", "modulation")):
                    observer(
                        {
                            "sequence": self.sequence,
                            "time_us": str(event_time),
                            "kind": kind,
                            "event_id": event_id,
                            "payload": copy.deepcopy(observed_payload),
                            **({"input_gate": selection} if selection is not None else {}),
                        }
                    )
            self._homeostasis()
            if event_time == self.next_step_us:
                self._emit()
                self._prune()
                self.next_step_us += self.config.step_us
                self.sequence += 1
                if observer is not None and not inputs_only:
                    observer(
                        {
                            "sequence": self.sequence,
                            "time_us": str(event_time),
                            "kind": "observation",
                            "payload": self.metrics(),
                        }
                    )
            self._lifecycle()
        # A dead instance's causal time is its actual extinction boundary.
        if self.life != "dead":
            self.time_us = target_us

    def _relax(self, when: int) -> None:
        dt = (when - self.state_time_us) / 1_000_000
        if dt <= 0:
            return
        c = self.config
        a, tr, inh = (math.exp(-dt / tau) for tau in (c.activation_tau, c.trace_tau, c.inhibition_tau))
        stable = math.exp(-dt / c.stability_tau)
        support = math.exp(-dt / c.support_tau)
        for n in self.nodes.values():
            n.activation *= a
            n.trace *= tr
            n.inhibition *= inh
            n.direct *= a
            n.associative *= a
            if n.activation < c.activation_floor:
                n.activation = 0.0
            if n.inhibition < c.activation_floor:
                n.inhibition = 0.0
            if c.plasticity:
                n.stability *= stable
                n.support *= support
        if c.plasticity:
            for e in self.edges.values():
                # Exact integrated protection for s(t)=s0 exp(-t/tau).
                protected_time = dt - c.stability_tau * (
                    math.log1p(4 * e.stability) - math.log1p(4 * e.stability * stable)
                )
                e.weight *= math.exp(-c.forgetting_rate * max(0.0, protected_time))
                e.stability *= stable
                e.eligibility *= tr
        self._maintain_energy(when, when - self.state_time_us)
        self.state_time_us = when

    def _touch(self, node_id: int, value: float, *, direct: bool) -> float:
        if node_id not in self.nodes or node_id in self.silenced_nodes or value <= 0:
            return 0.0
        n, c = self.nodes[node_id], self.config
        response = 1 / (1 + c.inhibition_response_gain * n.inhibition) if c.inhibition else 1.0
        amount = min(1.0 - n.activation, max(0.0, value) * response)
        if direct and c.energy_simulation_enabled:
            amount = self.energy.afford(amount, c.energy_direct_cost, "direct")
        n.activation += amount
        n.trace = min(1.0, n.trace + amount)
        if direct:
            n.direct += amount
        else:
            n.associative += amount
        if amount > 0:
            n.touches += 1
            n.last_touch_us = str(self.time_us)
            if c.plasticity:
                n.support = min(1.0, n.support + c.support_gain * amount)
                n.stability = min(1.0, n.stability + c.stability_gain * amount)
            if c.inhibition:
                # Generation has a positive delay, including self inhibition.
                self._event(
                    self.time_us + c.delay_us, "inhibition", {"values": [[node_id, amount * c.inhibition_gain]]}
                )
        return amount

    def _stimulate(self, stimulus: Stimulus) -> None:
        touched: list[tuple[int, float, float]] = []
        c = self.config
        for channel, value in sorted(stimulus.channels):
            drive = min(1.0, value * stimulus.intensity * c.direct_gain)
            if drive <= 0:
                continue
            node_id = self.receptors.get(channel)
            if node_id is None:
                if c.max_nodes is not None and len(self.nodes) >= c.max_nodes:
                    self.resources.increment("node_capacity_rejections")
                    continue
                node_id = self.next_node
                self.next_node += 1
                self.nodes[node_id] = Node(node_id, channel)
                self.receptors[channel] = node_id
            n = self.nodes[node_id]
            initial = n.touches == 0
            amount = self._touch(node_id, drive, direct=True)
            if amount > 0:
                consolidation = min(
                    c.consolidation_cap,
                    drive
                    * (c.first_gain * initial + c.repeat_gain + c.intensity_gain * max(0.0, stimulus.intensity - 1)),
                )
                touched.append((node_id, amount, consolidation))
                self.life = "active"
        self._associate(touched)

    def _associate(self, touched: list[tuple[int, float, float]]) -> None:
        c = self.config
        if not c.plasticity or not touched:
            return
        self.spatial.sync(c, self.nodes)
        sources = touched
        if c.edge_birth_policy == "temporal-association":
            impulses = {node: impulse for node, _, impulse in touched}
            sources = [
                (n.id, 0.0, impulses.get(n.id, 0.0))
                for n in sorted(self.nodes.values(), key=lambda n: n.id)
                if n.touches > 0
                and n.activation > 0
                and n.id not in self.silenced_nodes
                and self.time_us - int(n.last_touch_us) <= c.association_window_us
            ]
        # Freeze pre-event neighbourhood membership: an edge born earlier in
        # this batch must not manufacture its own novelty prerequisite.
        connected = {n for n, neighbours in self.incident.items() if neighbours} if c.local_novelty_gain else set()

        def candidates():
            for source, _, source_impulse in sources:
                for target, _, target_impulse in touched:
                    if source == target or (source, target) in self.silenced_edges:
                        continue
                    if not self.spatial.allowed(c, source, target):
                        continue
                    score = self.nodes[source].activation * self.nodes[target].activation
                    if (source, target) not in self.edges and score < c.edge_birth_activation_product_min:
                        continue
                    yield score, source, target, source_impulse, target_impulse

        choices = candidates()
        if c.edge_adaptation_limit is not None:
            available = self.resources.available_adaptations(self.time_us, c.step_us, c.edge_adaptation_limit)
            selected = []
            count = 0
            for score, source, target, si, ti in choices:
                count += 1
                candidate = (score, -source, -target, si, ti)
                if available:
                    if len(selected) < available:
                        heapq.heappush(selected, candidate)
                    elif candidate > selected[0]:
                        heapq.heapreplace(selected, candidate)
            self.resources.increment("adaptation_budget_skips", count - len(selected))
            choices = (
                (score, -source, -target, si, ti) for score, source, target, si, ti in sorted(selected, reverse=True)
            )
        for score, source, target, source_impulse, target_impulse in choices:
            if c.edge_adaptation_limit is not None:
                self.resources.use_adaptation(self.time_us, c.step_us)
            key = (source, target)
            if key not in self.edges:
                if c.max_edges is not None and len(self.edges) >= c.max_edges:
                    self.resources.increment("edge_capacity_rejections")
                    continue
                reentry = max(self.nodes[source].associative, self.nodes[target].associative)
                novelty = 0.0
                if (source in connected or target in connected) and reentry > 0:
                    novelty = c.local_novelty_gain * max(0.0, 1 - reentry / c.novelty_touch_reference)
                weight = min(1.0, c.birth_weight * score + source_impulse + target_impulse + novelty)
                self.edges[key] = Edge(source, target, weight, stability=novelty, birth_us=str(self.time_us))
                self.outgoing.setdefault(source, set()).add(target)
                self.incident.setdefault(source, set()).add(target)
                self.incident.setdefault(target, set()).add(source)
            e = self.edges[key]
            e.weight = min(1.0, e.weight + c.learning_rate * score)
            e.stability = min(1.0, e.stability + c.stability_gain * score + source_impulse + target_impulse)
            e.eligibility = min(1.0, e.eligibility + score)
            e.touches += 1
            e.last_touch_us = str(self.time_us)

    def _homeostasis(self) -> None:
        if not self.config.homeostasis_enabled:
            return
        total = sum(n.activation for n in self.nodes.values())
        if total > self.config.target_total_activation:
            scale = self.config.target_total_activation / total
            for node in self.nodes.values():
                node.activation *= scale
                node.direct *= scale
                node.associative *= scale

    def _emit(self) -> None:
        c = self.config
        dt = c.step_us / 1_000_000
        self.spatial.sync(c, self.nodes)
        if c.spatial_embedding and c.spatial_competition_rate > 0:
            # A frozen boundary snapshot makes this independent of edge traversal.
            weaker = {}
            for source, target in sorted(self.edges):
                if (
                    source in self.silenced_nodes
                    or target in self.silenced_nodes
                    or (source, target) in self.silenced_edges
                ):
                    continue
                if (
                    self.spatial.distance(source, target) <= c.spatial_radius
                    and self.nodes[source].activation > self.nodes[target].activation
                ):
                    weaker[target] = weaker.get(target, 0) + 1
            for target, count in weaker.items():
                factor = math.exp(-c.spatial_competition_rate * dt * count)
                node = self.nodes[target]
                node.activation *= factor
                node.direct *= factor
                node.associative *= factor
        gain = -math.expm1(-c.propagation_rate * dt)
        diffusion = -math.expm1(-c.inhibition_diffusion_rate * dt)
        signals: dict[int, float] = {}
        inhibitors: dict[int, float] = {}
        sources = sorted(self.nodes)
        if c.propagation_limit is not None:
            sources.sort(key=lambda node: (-self.nodes[node].activation, node))
        emissions = 0
        for source in sources:
            n = self.nodes[source]
            if source in self.silenced_nodes:
                n.activation = 0.0
                continue
            response = 1 / (1 + c.inhibition_response_gain * n.inhibition) if c.inhibition else 1.0
            if n.activation > 0 and n.activation >= c.propagation_activation_min:
                targets = sorted(self.outgoing.get(source, ()))
                if c.propagation_limit is not None:
                    targets.sort(key=lambda target: (-self.edges[source, target].weight, target))
                for target in targets:
                    if target in self.silenced_nodes or (source, target) in self.silenced_edges:
                        continue
                    e = self.edges[source, target]
                    amount = n.activation * response * e.weight * gain
                    if c.spatial_embedding and c.neighborhood_enabled:
                        attenuation = self.spatial.attenuation(c, source, target)
                        if attenuation <= 0:
                            continue
                        amount *= attenuation
                    if amount > 0 and c.propagation_limit is not None:
                        if emissions >= c.propagation_limit:
                            self.resources.increment("propagation_budget_skips")
                            continue
                        emissions += 1
                    # Contributions are accumulated before thresholding; fan-in is not discarded.
                    if c.energy_simulation_enabled:
                        amount = self.energy.afford(amount, c.energy_associative_cost, "associative")
                    signals[target] = signals.get(target, 0.0) + amount
                    if c.plasticity and amount > 0:
                        if c.edge_adaptation_limit is not None:
                            if not self.resources.available_adaptations(
                                self.time_us, c.step_us, c.edge_adaptation_limit
                            ):
                                self.resources.increment("adaptation_budget_skips")
                                continue
                            self.resources.use_adaptation(self.time_us, c.step_us)
                        e.eligibility = min(1.0, e.eligibility + amount)
                        e.weight = min(1.0, e.weight + c.associative_gain * amount)
                        e.stability = min(1.0, e.stability + c.stability_gain * amount)
                        e.touches += 1
                        e.last_touch_us = str(self.time_us)
            if c.inhibition and n.inhibition > 0:
                conductances = []
                for target in sorted(self.incident.get(source, ())):
                    weights = [
                        self.edges[key].weight
                        for key in ((source, target), (target, source))
                        if key in self.edges and key not in self.silenced_edges
                    ]
                    if weights:
                        conductances.append((target, max(weights)))
                total = sum(w for _, w in conductances)
                transfer = n.inhibition * diffusion
                if total > 0 and transfer >= max(c.activation_floor, c.inhibition_propagation_min) * dt:
                    if c.energy_simulation_enabled:
                        transfer = self.energy.afford(transfer, c.energy_inhibition_cost, "inhibition")
                    n.inhibition -= transfer
                    for target, weight in conductances:
                        inhibitors[target] = inhibitors.get(target, 0.0) + transfer * weight / total
        for kind, values in (("signal", signals), ("inhibition", inhibitors)):
            minimum = (
                max(c.activation_floor, c.inhibition_propagation_min) if kind == "inhibition" else c.activation_floor
            )
            data = [[n, v] for n, v in sorted(values.items()) if v >= minimum * dt]
            if data:
                self._event(self.time_us + c.delay_us, kind, {"values": data})

    def _remove_edge(self, key: tuple[int, int]) -> None:
        if self.edges.pop(key, None) is None:
            return
        source, target = key
        self.outgoing.get(source, set()).discard(target)
        if (target, source) not in self.edges:
            self.incident.get(source, set()).discard(target)
            self.incident.get(target, set()).discard(source)

    def _prune(self) -> None:
        if not self.config.plasticity and not (
            self.config.energy_simulation_enabled
            and self.config.irreversible_energy_death_enabled
            and self.energy.last_maintenance_deficit > 0
        ):
            return
        for key in [key for key, edge in self.edges.items() if edge.weight < self.config.prune_weight]:
            self._remove_edge(key)
        for node_id in list(self.nodes):
            n = self.nodes[node_id]
            if (
                n.activation == 0
                and n.inhibition == 0
                and n.support < self.config.prune_support
                and not self.incident.get(node_id)
            ):
                del self.nodes[node_id]
                self.receptors.pop(n.channel, None)

    def _lifecycle(self) -> None:
        self._energy_lifecycle()
        if self.life == "dead":
            return
        pending = any(
            kind == "stimulus"
            and any(v > 0 for _, v in payload["channels"])
            and payload["intensity"] > 0
            or kind == "signal"
            for _, _, kind, payload in self.queue
        )
        activity = any(n.activation > 0 for n in self.nodes.values())
        if self.life != "waiting" and not self.sources_open and not activity and not pending:
            self.life = "dead"

    def intervene(self, *, nodes: list[int] = (), edges: list[tuple[int, int]] = (), lesion: bool = False) -> None:
        if any(n not in self.nodes for n in nodes) or any(tuple(e) not in self.edges for e in edges):
            raise ValueError("intervention target does not exist")
        self.silenced_nodes.update(nodes)
        self.silenced_edges.update(tuple(e) for e in edges)
        if lesion:
            for key in list(self.edges):
                if key in self.silenced_edges or key[0] in self.silenced_nodes or key[1] in self.silenced_nodes:
                    self._remove_edge(key)
        for node_id in nodes:
            self.nodes[node_id].activation = 0.0
        self.sequence += 1

    def capture_state(self) -> StateImage:
        return StateImage.from_dict(
            {
                "schema": STATE_SCHEMAS[self.dynamics],
                "dynamics": self.dynamics,
                "config": self.config.to_dict(),
                "time_us": str(self.time_us),
                "state_time_us": str(self.state_time_us),
                "next_step_us": str(self.next_step_us),
                "sequence": self.sequence,
                "next_event": self.next_event,
                "next_node": self.next_node,
                "sources_open": self.sources_open,
                "life": self.life,
                "nodes": [asdict(self.nodes[i]) for i in sorted(self.nodes)],
                "edges": [asdict(self.edges[i]) for i in sorted(self.edges)],
                "queue": [{"time_us": str(t), "id": i, "kind": k, "payload": p} for t, i, k, p in sorted(self.queue)],
                "silenced_nodes": sorted(self.silenced_nodes),
                "silenced_edges": [list(e) for e in sorted(self.silenced_edges)],
                **({"resources": self.resources.to_dict()} if self.dynamics in RESOURCE_VERSIONS else {}),
                **({"energy": self.energy.to_dict()} if self.dynamics in ENERGY_VERSIONS else {}),
                **({"attention": self.attention.to_dict()} if self.dynamics in ATTENTION_VERSIONS else {}),
            }
        )

    def _restore(self, image: StateImage) -> None:
        s = image.to_dict()
        required = {
            "schema",
            "dynamics",
            "config",
            "time_us",
            "state_time_us",
            "next_step_us",
            "sequence",
            "next_event",
            "next_node",
            "sources_open",
            "life",
            "nodes",
            "edges",
            "queue",
            "silenced_nodes",
            "silenced_edges",
        }
        if s.get("dynamics") in RESOURCE_VERSIONS:
            required.add("resources")
        if s.get("dynamics") in ENERGY_VERSIONS:
            required.add("energy")
        if s.get("dynamics") in ATTENTION_VERSIONS:
            required.add("attention")
        if set(s) != required:
            raise ValueError("unexpected or missing state fields")
        if s["schema"] != STATE_SCHEMAS.get(s["dynamics"]):
            raise ValueError("unsupported state schema or dynamics version")
        self.config = Config(**s["config"])
        self.dynamics = s["dynamics"]
        if self.dynamics == LEGACY_DYNAMICS and self.config.has_optional_changes():
            raise ValueError("causal/1 cannot contain causal/2 mechanisms")
        if self.dynamics not in RESOURCE_VERSIONS and self.config.has_budget_limits():
            raise ValueError("resource budgets require causal/3")
        if self.dynamics not in ENERGY_VERSIONS and self.config.has_energy_changes():
            raise ValueError("legacy dynamics cannot contain energy accounting")
        if self.dynamics not in ATTENTION_VERSIONS and self.config.has_attention_changes():
            raise ValueError("legacy dynamics cannot contain attention selection")
        if self.dynamics not in SPATIAL_VERSIONS and self.config.has_spatial_changes():
            raise ValueError("legacy dynamics cannot contain causal spatial rules")
        self.time_us, self.state_time_us, self.next_step_us = (
            timestamp(s[n]) for n in ("time_us", "state_time_us", "next_step_us")
        )
        if self.state_time_us > self.time_us or self.next_step_us <= self.state_time_us:
            raise ValueError("invalid numerical phase")
        if self.dynamics in RESOURCE_VERSIONS:
            self.resources = Resources.restore(s["resources"], self.time_us, self.config.step_us)
        if self.dynamics in ENERGY_VERSIONS:
            self.energy = Energy.restore(s["energy"], self.time_us, self.config)
        if self.dynamics in ATTENTION_VERSIONS:
            self.attention = Attention.restore(s["attention"], self.time_us)
        for name in ("sequence", "next_event", "next_node"):
            if type(s[name]) is not int or not 0 <= s[name] < 2**63:
                raise ValueError("invalid state counter")
        if s["next_node"] < 1:
            raise ValueError("invalid next node counter")
        self.sequence, self.next_event, self.next_node = (s[n] for n in ("sequence", "next_event", "next_node"))
        self.sources_open, self.life = s["sources_open"], s["life"]
        if type(self.sources_open) is not bool or self.life not in ("waiting", "active", "dead"):
            raise ValueError("invalid lifecycle")
        for raw in s["nodes"]:
            n = Node(**raw)
            if (
                type(n.id) is not int
                or type(n.channel) is not int
                or n.id in self.nodes
                or n.channel in self.receptors
                or not 0 < n.id < self.next_node
                or not 0 <= n.channel < 2**32
            ):
                raise ValueError("invalid/duplicate node identity")
            for name in ("activation", "inhibition", "trace", "support", "stability", "direct", "associative"):
                v = getattr(n, name)
                if (
                    isinstance(v, bool)
                    or not isinstance(v, (float, int))
                    or not math.isfinite(v)
                    or not 0 <= v <= (self.config.inhibition_saturation if name == "inhibition" else 1.0) + 1e-14
                ):
                    raise ValueError("invalid node state")
            if (
                timestamp(n.last_touch_us) > self.state_time_us
                or type(n.touches) is not int
                or not 0 <= n.touches < 2**63
            ):
                raise ValueError("invalid node history")
            self.nodes[n.id], self.receptors[n.channel] = n, n.id
        for raw in s["edges"]:
            e = Edge(**raw)
            key = e.source, e.target
            if key in self.edges or e.source == e.target or e.source not in self.nodes or e.target not in self.nodes:
                raise ValueError("invalid edge endpoints")
            if any(
                isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not 0 <= v <= 1
                for v in (e.weight, e.stability, e.eligibility)
            ):
                raise ValueError("invalid edge state")
            if (
                not timestamp(e.birth_us) <= timestamp(e.last_touch_us) <= self.state_time_us
                or type(e.touches) is not int
                or not 0 <= e.touches < 2**63
            ):
                raise ValueError("invalid edge history")
            self.edges[key] = e
            self.outgoing.setdefault(e.source, set()).add(e.target)
            self.incident.setdefault(e.source, set()).add(e.target)
            self.incident.setdefault(e.target, set()).add(e.source)
        ids = set()
        for event in s["queue"]:
            t, i, kind, payload = timestamp(event["time_us"]), event["id"], event["kind"], event["payload"]
            if (
                t < self.time_us
                or i in ids
                or not 0 < i <= self.next_event
                or kind not in ("stimulus", "signal", "inhibition", "energy", "modulation")
            ):
                raise ValueError("invalid pending event")
            ids.add(i)
            if kind == "stimulus":
                if "bypass_attention" in payload and self.dynamics != DYNAMICS:
                    raise ValueError("per-frame attention bypass requires causal/7")
                if Stimulus.from_dict(payload).time_us != t:
                    raise ValueError("stimulus timestamp differs from envelope")
            elif kind == "energy":
                if self.dynamics not in ENERGY_VERSIONS or set(payload) != {"amount", "source"}:
                    raise ValueError("invalid pending energy supply")
                supply_payload(**payload)
            elif kind == "modulation":
                if self.dynamics not in ATTENTION_VERSIONS or set(payload) != {
                    "source",
                    "gain",
                    "budget_multiplier",
                    "competition_enabled",
                    "ttl_us",
                }:
                    raise ValueError("invalid pending modulation")
                modulation_payload(**payload)
            elif any(type(n) is not int or not math.isfinite(v) or v < 0 for n, v in payload["values"]):
                raise ValueError("invalid pending signal")
            heapq.heappush(self.queue, (t, i, kind, payload))
        self.silenced_nodes = set(s["silenced_nodes"])
        self.silenced_edges = {tuple(e) for e in s["silenced_edges"]}
        if self.energy.death_us is not None and (self.life != "dead" or self.energy.death_us != str(self.time_us)):
            raise ValueError("invalid energy death boundary")

    def activations(self) -> list[tuple[int, float]]:
        """Ordered physical readout, without materializing connections or node history."""
        decay = math.exp(-(self.time_us - self.state_time_us) / 1e6 / self.config.activation_tau)
        return [(i, self.nodes[i].activation * decay) for i in sorted(self.nodes)]

    def observation_nodes(self) -> list[dict]:
        """Full anonymous observation, projected to the horizon without relaxation."""
        dt = (self.time_us - self.state_time_us) / 1e6
        c = self.config
        scales = {
            k: math.exp(-dt / tau)
            for k, tau in (
                ("activation", c.activation_tau),
                ("direct", c.activation_tau),
                ("associative", c.activation_tau),
                ("inhibition", c.inhibition_tau),
                ("trace", c.trace_tau),
            )
        }
        if c.plasticity:
            scales.update(stability=math.exp(-dt / c.stability_tau), support=math.exp(-dt / c.support_tau))
        result = []
        for i in sorted(self.nodes):
            row = asdict(self.nodes[i])
            for key, scale in scales.items():
                row[key] *= scale
            result.append(row)
        return result

    def induced_edges(self, node_ids) -> list[dict]:
        selected = set(node_ids)
        dt = (self.time_us - self.state_time_us) / 1e6
        c = self.config
        stable = math.exp(-dt / c.stability_tau)
        result = []
        for source in sorted(selected):
            for target in sorted(self.outgoing.get(source, set()) & selected):
                row = asdict(self.edges[source, target])
                if c.plasticity:
                    protected = dt - c.stability_tau * (
                        math.log1p(4 * row["stability"]) - math.log1p(4 * row["stability"] * stable)
                    )
                    row["weight"] *= math.exp(-c.forgetting_rate * max(0, protected))
                    row["stability"] *= stable
                    row["eligibility"] *= math.exp(-dt / c.trace_tau)
                result.append(row)
        return result

    def graph(self, limit: int | None = None) -> dict:
        # Analytic observation at the requested horizon does not mutate the engine.
        dt = (self.time_us - self.state_time_us) / 1_000_000
        decay = math.exp(-dt / self.config.activation_tau)
        ids = sorted(self.nodes)[:limit] if limit is not None else sorted(self.nodes)
        selected = set(ids)
        nodes = []
        for i in ids:
            row = asdict(self.nodes[i])
            row["activation"] *= decay
            nodes.append(row)
        return {
            "nodes": nodes,
            "edges": [asdict(e) for e in self.edges.values() if e.source in selected and e.target in selected],
            "sequence": self.sequence,
            "time_us": str(self.time_us),
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "complete": len(ids) == len(self.nodes),
        }

    def metrics(self) -> dict:
        dt = (self.time_us - self.state_time_us) / 1_000_000
        decay = math.exp(-dt / self.config.activation_tau)
        count = len(self.nodes)
        activation = sum(n.activation for n in self.nodes.values()) * decay
        return {
            "time_us": str(self.time_us),
            "state_time_us": str(self.state_time_us),
            "sequence": self.sequence,
            "life": self.life,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "activation": activation,
            "mean_activation": activation / count if count else None,
            "active_fraction": sum(n.activation * decay > self.config.activation_floor for n in self.nodes.values())
            / count
            if count
            else None,
            "saturated_fraction": sum(n.activation * decay >= 0.95 for n in self.nodes.values()) / count
            if count
            else None,
            "edge_density": len(self.edges) / (count * (count - 1)) if count > 1 else None,
            "inhibition": sum(n.inhibition for n in self.nodes.values()) * math.exp(-dt / self.config.inhibition_tau),
            "pending_events": len(self.queue),
            "mean_weight": sum(e.weight for e in self.edges.values()) / len(self.edges) if self.edges else None,
            "resources": self.resources.to_dict()
            | {
                "limits": {
                    k: getattr(self.config, k)
                    for k in ("max_nodes", "max_edges", "propagation_limit", "edge_adaptation_limit")
                },
                "step_us": self.config.step_us,
            }
            if self.dynamics in RESOURCE_VERSIONS
            else None,
            "energy": self.energy.to_dict()
            | {
                "parameters": {k: getattr(self.config, k) for k in ENERGY_DEFAULTS},
                "settled_state_time_us": str(self.state_time_us),
            }
            if self.dynamics in ENERGY_VERSIONS
            else None,
            "attention": self.attention.to_dict()
            | {
                "parameters": {k: getattr(self.config, k) for k in ATTENTION_DEFAULTS},
                "effective": self.attention.effective(self.time_us, self.config),
            }
            if self.dynamics in ATTENTION_VERSIONS
            else None,
            "spatial": self.spatial.summary(self.config, self.nodes, self.edges)
            if self.dynamics in SPATIAL_VERSIONS
            else None,
        }

    def spatial_geometry(self):
        """Explicit complete derived geometry query; no coordinates are fed back from a view."""
        if self.dynamics not in SPATIAL_VERSIONS:
            raise ValueError("this dynamics version has no causal spatial contract")
        self.spatial.sync(self.config, self.nodes)
        return self.spatial.geometry(self.config, self.nodes, self.edges)
