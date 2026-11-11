"""memory/4: object-owned clocks and receiver-local events, independent of /3 transitions."""

from __future__ import annotations

import copy
import hashlib
import heapq
import math
from dataclasses import asdict, dataclass

from threemind_core import StateImage, Stimulus
from threemind_core.energy import Energy, supply_payload
from threemind_core.energy import observation as energy_observation
from threemind_core.engine import Edge, Node, canonical_bytes
from threemind_core.spec import timestamp

from .local_deadlines import LocalDeadlines
from .mechanisms import FastTrace, ShortTermState, local_attention, number
from .retention import RetentionConfig, crossing, decay, grow

KERNEL_ID = "threemind.continuous-memory/4"
STATE_SCHEMA = "threemind.continuous-memory-state/4.1"
MECHANISMS = (
    ("threemind.object-local-clock/1", "arrivals-emission-expiry"),
    ("threemind.source-independent-reception/1", "receiver-local-arrivals"),
    ("threemind.tm-synapse/1", "before-emission"),
    ("threemind.leaky-fast-trace/1", "efficacy-and-emission"),
    ("threemind.local-context-attention/1", "receiver-local-arrivals"),
    ("threemind.local-contact-learning/1", "delivered-contact-packet"),
    ("threemind.local-arrival-novelty/3", "local-birth-window"),
    ("threemind.adaptive-half-life/2", "local-touch-emission-expiry"),
    ("threemind.local-resource-field/1", "supply-local-uptake-expense"),
    ("threemind.local-awakening/2", "residual-contact-arrivals"),
)


@dataclass(frozen=True, slots=True)
class LocalConfig(RetentionConfig):
    propagation_mode: str = "local-events"
    propagation_phase: str = "aligned"
    arrival_mode: str = "coincident"
    reception_mode: str = "unified"
    energy_model: str = "local-field"
    energy_distribution: str = "counter-random"
    energy_seed: int = 20261009
    energy_region_count: int = 16
    energy_node_capacity: float = 1.0

    def __post_init__(self):
        RetentionConfig.__post_init__(self)
        for key, choices in (
            ("propagation_mode", ("local-events", "scan-control")),
            ("propagation_phase", ("aligned", "asynchronous")),
            ("arrival_mode", ("coincident", "sequential")),
            ("reception_mode", ("unified", "legacy-source")),
            ("energy_model", ("local-field", "global-ledger")),
            ("energy_distribution", ("counter-random", "stream-random")),
        ):
            if getattr(self, key) not in choices:
                raise ValueError(f"unknown {key}")
        for key, high in (("energy_seed", 2**53 - 1), ("energy_region_count", 4096)):
            if type(getattr(self, key)) is not int or not 0 <= getattr(self, key) <= high:
                raise ValueError(f"invalid {key}")
        if self.energy_region_count == 0:
            raise ValueError("energy_region_count must be positive")
        object.__setattr__(
            self,
            "energy_node_capacity",
            number(self.energy_node_capacity, "energy_node_capacity", low=1e-12, high=1e12),
        )
        if self.homeostasis_enabled or self.spatial_competition_rate > 0:
            raise ValueError("memory/4 does not implement global homeostasis/spatial competition")
        if self.edge_birth_policy != "co-stimulus":
            raise ValueError(
                "memory/4 requires delivered-contact co-stimulus birth; global temporal search is unsupported"
            )
        if self.attention_competition_enabled:
            raise ValueError("memory/4 does not rank external inputs globally; use an explicit peripheral")
        for key in ("step_us", "association_window_us", "attention_budget", "target_total_activation"):
            if getattr(self, key) != RetentionConfig.__dataclass_fields__[key].default:
                raise ValueError(f"{key} is inactive metadata in memory/4 and cannot be changed")

    def to_dict(self):
        return asdict(self)


def definition(config):
    return {
        "schema": "threemind.kernel-definition/1",
        "kernel_id": KERNEL_ID,
        "state_schema": STATE_SCHEMA,
        "hypothesis_id": "threemind.hypotheses/continuous-memory4",
        "operators": [{"id": k, "phase": p} for k, p in MECHANISMS],
        "config": config.to_dict(),
    }


def word(seed, domain, serial):
    """Backend-independent counter PRNG; unrelated to learning/host RNG calls."""
    value = (seed ^ (domain * 0x9E3779B97F4A7C15) ^ serial) & ((1 << 64) - 1)
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & ((1 << 64) - 1)
    return value ^ (value >> 31)


@dataclass(slots=True)
class LocalNode(Node):
    state_us: str = "0"
    half_life: float = 30.0
    fatigue: float = 0.0
    salience: float = 0.0
    isolated_us: str = "0"
    region: int = 0
    reserve: float = 0.0
    energy_us: str = "0"
    sleeping: bool = False


@dataclass(slots=True)
class LocalEdge(Edge):
    state_us: str = "0"
    half_life: float = 30.0
    last_pass_us: str = "0"
    sleeping: bool = False
    short_term: dict | None = None
    fast: dict | None = None
    novelty_deadline_us: str | None = None
    novelty_source: float = 0.0
    novelty_target: float = 0.0


class LocalEngine:
    dynamics = KERNEL_ID
    state_schema = STATE_SCHEMA
    config_type = LocalConfig
    node_type = LocalNode
    edge_type = LocalEdge
    definition = staticmethod(definition)
    restored_learning = False

    def __init__(self, config=None, state=None):
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        if config is not None and type(config) is not self.config_type:
            raise ValueError(
                f"{self.dynamics.removeprefix('threemind.continuous-')} requires {self.config_type.__name__}"
            )
        self.config = config or self.config_type()
        self.nodes, self.edges, self.receptors = {}, {}, {}
        self.outgoing, self.incident, self.regions = {}, {}, {}
        self.active, self.silenced_nodes, self.silenced_edges = set(), set(), set()
        self.queue, self.timers = [], LocalDeadlines()
        self.pending_novelty = {}  # Derived index; version 4 does not use it.
        self.time_us = self.sequence = self.next_event = self.next_node = 0
        self.sources_open, self.life, self.quiet_since_us = True, "waiting", None
        self.transport = dict.fromkeys(("sent", "received", "activated", "discarded"), 0.0)
        self.audit = dict.fromkeys(
            (
                "node_visits",
                "edge_visits",
                "scan_visits",
                "expiry_checks",
                "nodes_deleted",
                "edges_deleted",
                "nodes_awakened",
                "edges_awakened",
            ),
            0,
        )
        self.energy = Energy.initial(self.config)
        self.pools = {
            r: self.energy.reserve / self.config.energy_region_count for r in range(self.config.energy_region_count)
        }
        self.energy_serial = 0
        self.energy_rng = word(self.config.energy_seed, 3, 0)
        if self.config.energy_model == "local-field":
            self.energy.reserve = 0.0
        else:
            self.pools = {r: 0.0 for r in self.pools}
        if state is not None:
            self._restore(state.to_dict())

    def _event(self, when, kind, payload):
        event = self.next_event
        self.next_event += 1
        heapq.heappush(self.queue, (when, event, kind, payload))
        return event

    def inject(self, stimulus):
        when = timestamp(stimulus.time_us)
        if when < self.time_us or self.life == "dead" or not self.sources_open:
            raise ValueError("input violates causal/lifecycle boundary")
        return self._event(when, "stimulus", stimulus.to_dict())

    def close_inputs(self):
        self.sources_open = False

    def supply_energy(self, amount, *, time_us=None, source="external-energy"):
        payload = supply_payload(amount, source)
        when = self.time_us if time_us is None else timestamp(time_us)
        if not self.config.energy_simulation_enabled or when < self.time_us or self.life == "dead":
            raise ValueError("energy input violates configuration or causal boundary")
        return self._event(when, "energy", payload)

    def modulate_input(self, **kwargs):
        raise ValueError(
            f"{self.dynamics.removeprefix('threemind.continuous-')} input modulation belongs to an explicit peripheral"
        )

    def _soft(self, value):
        c = self.config
        return c.inhibition_saturation * math.tanh(max(0.0, value) / c.inhibition_saturation)

    def _response(self, n):
        c = self.config
        return (1 / (1 + c.inhibition_response_gain * self._soft(n.inhibition)) if c.inhibition else 1) / (
            1 + (n.fatigue if c.strong_fatigue_enabled else 0.0)
        )

    def _project_node(self, node, when):
        n, c = copy.copy(node), self.config
        dt = (when - int(n.state_us)) / 1e6
        if self.restored_learning and dt == 0:
            return n
        for key, tau, enabled in (
            ("activation", c.activation_tau, c.activation_decay_enabled),
            ("trace", c.trace_tau, c.trace_decay_enabled),
            ("inhibition", c.inhibition_tau, c.inhibition_decay_enabled),
        ):
            if enabled:
                setattr(n, key, getattr(n, key) * math.exp(-dt / tau))
        if n.activation < c.activation_floor:
            n.activation = 0.0
        if c.plasticity and c.support_decay_enabled:
            if c.node_retention_mode == "automatic":
                n.support, n.half_life = decay(n.support, n.half_life, dt, c)
            else:
                n.support = max(0.0, n.support - dt / c.support_tau * (1 - n.stability))
        if self.restored_learning:
            if n.fatigue != 0 or n.salience != 0:
                recovery = math.exp(-dt / c.strong_fatigue_tau_s)
                n.fatigue *= recovery
                n.salience *= recovery
        else:
            n.fatigue *= math.exp(-dt / c.strong_fatigue_tau_s)
            n.salience *= math.exp(-dt / c.strong_fatigue_tau_s)
        n.state_us = str(when)
        return n

    def _settle_node(self, id):
        self.audit["node_visits"] += 1
        n = self.nodes[id]
        if not self.restored_learning or int(n.state_us) != self.time_us:
            n = self._project_node(n, self.time_us)
            self.nodes[id] = n
        if n.activation == 0:
            self.active.discard(id)
            if self.life != "waiting" and not self.active and self.quiet_since_us is None:
                self.quiet_since_us = self.time_us
        return n

    def _project_edge(self, edge, when):
        e, c = copy.copy(edge), self.config
        dt = (when - int(e.state_us)) / 1e6
        if self.restored_learning and dt == 0:
            return e
        if c.plasticity and c.consolidation_mode == "adaptive-half-life":
            e.weight, e.half_life = decay(e.weight, e.half_life, dt, c)
            old = e.eligibility
            if c.eligibility_decay_enabled:
                e.eligibility *= math.exp(-dt / c.eligibility_tau)
            if c.stability_decay_enabled:
                integrated = (
                    old * c.eligibility_tau * (-math.expm1(-dt / c.eligibility_tau))
                    if c.eligibility_decay_enabled
                    else old * dt
                )
                e.stability = max(0.0, e.stability - (dt - integrated) / c.stability_tau)
        e.state_us = str(when)
        return e

    def _settle_edge(self, key):
        self.audit["edge_visits"] += 1
        self.edges[key] = self._project_edge(self.edges[key], self.time_us)
        return self.edges[key]

    def _delay(self, seconds):
        return self.time_us + max(1, math.ceil(seconds * 1e6) + 1)

    def _node_timers(self, n):
        c, id = self.config, n.id
        if n.activation > c.activation_floor and c.activation_decay_enabled and c.activation_floor > 0:
            self.timers.set((1, id, 0), self._delay(c.activation_tau * math.log(n.activation / c.activation_floor)))
        else:
            self.timers.discard((1, id, 0))
        connected = any(not self.edges[k].sleeping for k in self.incident.get(id, ()))
        if c.retain_nodes or not c.plasticity or connected:
            self.timers.discard((3, id, 0))
            return
        inactive = (
            c.activation_tau * math.log(n.activation / c.activation_floor)
            if n.activation > c.activation_floor and c.activation_decay_enabled and c.activation_floor > 0
            else 0.0
        )
        if n.activation > 0 and (not c.activation_decay_enabled or c.activation_floor == 0):
            return
        if c.node_retention_mode == "automatic":
            seconds = (
                crossing(n.support, n.half_life, 0.006, c)
                if c.support_decay_enabled
                else (0.0 if n.support < 0.006 else None)
            )
        elif c.prune_support == 0:
            seconds = max(
                0.0, (max(int(n.isolated_us), int(n.last_touch_us)) + c.dead_node_retention_us - self.time_us) / 1e6
            )
        else:
            rate = (1 - n.stability) / c.support_tau if c.support_decay_enabled else 0
            seconds = (
                max(0.0, (n.support - c.prune_support) / rate)
                if rate
                else (0.0 if n.support < c.prune_support else None)
            )
            if seconds is not None:
                seconds = max(seconds, (int(n.last_touch_us) + c.node_prune_after_us - self.time_us) / 1e6)
        self.timers.set((3, id, 0), None if seconds is None else self._delay(max(inactive, seconds)))

    def _edge_timer(self, e):
        c, key = self.config, (e.source, e.target)
        if not c.plasticity:
            self.timers.discard((2, *key))
        elif c.consolidation_mode == "adaptive-half-life":
            seconds = crossing(e.weight, e.half_life, c.dormant_prune_weight if e.sleeping else c.prune_weight, c)
            self.timers.set((2, *key), None if seconds is None else self._delay(seconds))
        else:
            period = c.propagation_interval_us
            current_due = (
                self.restored_learning
                and self._before_emission
                and self.time_us > 0
                and (self.time_us % period == 0 and int(e.completed_period_us) < self.time_us)
            )
            self.timers.set((2, *key), self.time_us if current_due else (self.time_us // period + 1) * period)
        if e.novelty_deadline_us is not None:
            self.timers.set((4, *key), int(e.novelty_deadline_us))

    def _pulse(self, n, *, after=False):
        c = self.config
        if (
            n.sleeping
            or n.id in self.silenced_nodes
            or not (n.activation > 0 or n.inhibition >= c.inhibition_propagation_min or n.pending_inhibition > 0)
        ):
            self.timers.discard((0, n.id, 0))
            return
        key = (0, n.id, 0)
        if key in self.timers.positions and not after:
            return
        period = c.propagation_interval_us
        when = (
            self.time_us + period
            if after or c.propagation_phase == "asynchronous"
            else max(period, ((self.time_us + period - 1) // period) * period)
        )
        if self.restored_learning and c.propagation_phase == "aligned" and not after:
            when = max(when, self.completed_emission_us + period)
        self.timers.set(key, when)

    def _birth(self, channel):
        c, id = self.config, self.next_node
        if c.max_nodes is not None and len(self.nodes) >= c.max_nodes:
            return None
        self.next_node += 1
        region = word(c.energy_seed, 1, id) % c.energy_region_count
        n = self.node_type(
            id,
            channel,
            birth_us=str(self.time_us),
            last_touch_us=str(self.time_us),
            state_us=str(self.time_us),
            isolated_us=str(self.time_us),
            energy_us=str(self.time_us),
            half_life=c.memory_half_life_min_s,
            region=region,
        )
        self.nodes[id], self.receptors[channel] = n, id
        self.regions.setdefault(region, set()).add(id)
        if c.energy_simulation_enabled and c.energy_starvation_damage_enabled:
            self.timers.set((5, id, 0), self.time_us + c.propagation_interval_us)
        return id

    def _uptake(self, region):
        c = self.config
        ids = sorted(self.regions.get(region, ()))
        for id in ids:
            self._maintenance(self._settle_node(id))
        requests = [(id, max(0.0, c.energy_node_capacity - self.nodes[id].reserve)) for id in ids]
        total = sum(v for _, v in requests)
        amount = min(self.pools.get(region, 0.0), total)
        if total > 0:
            for id, request in requests:
                self.nodes[id].reserve += amount * (request / total)
            self.pools[region] = max(0.0, self.pools.get(region, 0.0) - amount)

    def _expense(self, n, value, cost, kind):
        c = self.config
        if not c.energy_simulation_enabled or cost <= 0:
            return value
        if c.energy_model == "global-ledger":
            return self.energy.afford(value, cost, kind)
        accepted = min(value, n.reserve / cost)
        used = min(n.reserve, accepted * cost)
        n.reserve = max(0.0, n.reserve - used)
        self.energy._add("consumed_" + kind, used)
        self.energy._add("unserved_total", max(0.0, value * cost - used))
        return accepted

    def _maintenance(self, n):
        c = self.config
        dt = (self.time_us - int(n.energy_us)) / 1e6
        n.energy_us = str(self.time_us)
        if not c.energy_simulation_enabled or not c.energy_starvation_damage_enabled or dt <= 0:
            return
        required = dt * (
            c.energy_maintenance_cost_per_node + len(self.outgoing.get(n.id, ())) * c.energy_maintenance_cost_per_edge
        )
        paid = self._expense(n, required, 1.0, "maintenance")
        deficit = dt * (1 - paid / required) if required else 0
        factor = math.exp(-c.energy_starvation_structural_decay * deficit)
        n.support *= factor
        for key in tuple(self.outgoing.get(n.id, ())):
            e = self._settle_edge(key)
            e.weight *= factor
            e.stability *= factor
            self._edge_timer(e)

    def _touch(self, id, raw, direct, intensity=1.0, drive=None):
        c = self.config
        if id not in self.nodes or id in self.silenced_nodes or raw <= 0:
            return (0.0, 0.0)
        n = self._settle_node(id)
        if n.sleeping:
            if not c.revival_enabled or raw < c.node_wake_threshold:
                return (0.0, 0.0)
            n.sleeping = False
            self.audit["nodes_awakened"] += 1
        self._maintenance(n)
        arrived = (
            self._expense(n, raw, c.energy_direct_cost, "direct") if direct or c.reception_mode == "unified" else raw
        )
        response = self._response(n)
        amount = arrived * response
        self.transport["received"] += arrived
        if self.restored_learning and amount <= 0:
            self._node_timers(n)
            self._pulse(n)
            return (0.0, 0.0)
        initial = n.touches == 0
        delta = min(1 - n.activation, amount)
        n.activation += delta
        self.transport["activated"] += delta
        n.trace = min(1.0, n.trace + amount)
        if direct:
            n.direct = max(n.direct, amount)
        else:
            n.associative += amount
        n.last_touch_us = str(self.time_us)
        n.isolated_us = str(self.time_us)
        n.touches += 1
        if c.inhibition:
            n.generated_inhibition += delta * c.inhibition_gain
        strength = max(
            0.0, (intensity if self.restored_learning else raw if c.reception_mode == "unified" else intensity) - 1
        )
        n.salience += amount * strength
        if c.strong_fatigue_enabled:
            n.fatigue += amount * strength * c.strong_fatigue_gain
        impulse = 0.0
        if c.plasticity:
            dose = amount * 0.1 * (1 + n.salience)
            if c.node_retention_mode == "automatic":
                n.half_life = grow(n.half_life, dose, c)
                n.support = 1 - (1 - n.support) * math.exp(-c.memory_weight_learning_rate * dose)
            else:
                n.support = min(1.0, n.support + c.support_gain * amount)
            if self.restored_learning and drive is not None and (direct or c.reception_mode == "unified"):
                fraction = amount / (raw * response) if raw * response > 0 else 0.0
                impulse = min(
                    c.consolidation_cap,
                    drive
                    * fraction
                    * n.local_plasticity
                    * (c.first_gain * initial + c.repeat_gain + c.intensity_gain * strength),
                )
            elif not self.restored_learning and (direct or c.reception_mode == "unified"):
                impulse = min(
                    c.consolidation_cap,
                    raw * n.local_plasticity * (c.first_gain * initial + c.repeat_gain + c.intensity_gain * strength),
                )
            n.stability = min(1.0, n.stability + 0.5 * c.stability_gain * n.activation)
            n.local_plasticity = max(0.12, 1 - 0.72 * n.stability)
        novelty_keys = self.pending_novelty.get(id, ()) if self.restored_learning else self.incident.get(id, ())
        for key in novelty_keys:
            e = self.edges[key]
            if (
                c.plasticity
                and e.novelty_deadline_us is not None
                and (not direct or (not self.restored_learning and c.reception_mode == "unified"))
            ):
                if key[0] == id:
                    e.novelty_source += amount
                else:
                    e.novelty_target += amount
        if n.activation > 0:
            self.active.add(id)
            self.life, self.quiet_since_us = "active", None
        self._node_timers(n)
        self._pulse(n)
        return amount, impulse

    def _associate(self, contacts):
        c = self.config
        if not c.plasticity:
            return
        connected = (
            {id for id, _, _ in contacts if any(not self.edges[k].sleeping for k in self.incident.get(id, ()))}
            if self.restored_learning
            else None
        )
        for a, av, ai in contacts:
            for b, bv, bi in contacts:
                key = a, b
                if a == b or key in self.silenced_edges or a not in self.nodes or b not in self.nodes:
                    continue
                score = self.nodes[a].activation * self.nodes[b].activation if self.restored_learning else av * bv
                if score <= 0 or (key not in self.edges and score < c.edge_birth_activation_product_min):
                    continue
                if c.spatial_embedding and c.neighborhood_enabled:
                    from threemind_core.spatial import position

                    pa, pb = position(c.seed, a, c.spatial_dimensions), position(c.seed, b, c.spatial_dimensions)
                    if math.sqrt(sum((x - y) ** 2 for x, y in zip(pa, pb))) > c.spatial_radius:
                        continue
                impulse = min(c.consolidation_cap, ai + bi)
                if key not in self.edges:
                    if c.max_edges is not None and len(self.edges) >= c.max_edges:
                        continue
                    e = self.edge_type(
                        a,
                        b,
                        min(1.0, c.birth_weight * (0.5 + score) + 0.18 * impulse),
                        stability=min(1.0, impulse),
                        eligibility=impulse,
                        birth_us=str(self.time_us),
                        last_touch_us=str(self.time_us),
                        state_us=str(self.time_us),
                        half_life=c.memory_half_life_min_s,
                    )
                    if self.restored_learning:
                        e.completed_period_us = str(
                            max(
                                0,
                                (self.time_us - int(self._before_emission))
                                // c.propagation_interval_us
                                * c.propagation_interval_us,
                            )
                        )
                    eligible = (
                        (a in connected or b in connected)
                        if self.restored_learning
                        else (self.incident.get(a) or self.incident.get(b))
                    )
                    if eligible:
                        if c.novelty_mode == "arrival-window" and (
                            not self.restored_learning or c.local_novelty_gain > 0
                        ):
                            if self.restored_learning:
                                period = c.propagation_interval_us
                                deadline = (
                                    max(
                                        period,
                                        self.completed_emission_us + period,
                                        ((self.time_us + period - 1) // period) * period,
                                    )
                                    + c.delay_us
                                )
                                e.novelty_deadline_us = str(deadline)
                                e.novelty_source = self.nodes[a].associative
                                e.novelty_target = self.nodes[b].associative
                                for id in key:
                                    self.pending_novelty.setdefault(id, set()).add(key)
                            else:
                                e.novelty_deadline_us = str(self.time_us + c.propagation_interval_us + c.delay_us)
                        else:
                            reentry = (
                                max(av, bv)
                                if c.reception_mode == "unified" and not self.restored_learning
                                else max(self.nodes[a].associative, self.nodes[b].associative)
                            )
                            bonus = (
                                c.local_novelty_gain * max(0.0, 1 - reentry / c.novelty_touch_reference)
                                if reentry > 0
                                else 0
                            )
                            e.weight = min(1.0, e.weight + bonus)
                            e.stability = min(1.0, e.stability + bonus)
                    self.edges[key] = e
                    self.outgoing.setdefault(a, set()).add(key)
                    self.incident.setdefault(a, set()).add(key)
                    self.incident.setdefault(b, set()).add(key)
                else:
                    e = self._settle_edge(key)
                    if e.sleeping:
                        continue
                    if c.edge_consolidation_enabled:
                        if self.restored_learning:
                            previous = (
                                (self.time_us - int(self._before_emission))
                                // c.propagation_interval_us
                                * c.propagation_interval_us
                                if c.propagation_phase == "aligned"
                                else int(self.nodes[a].last_emit_us)
                            )
                            internal = 1 if int(e.last_pass_us) > 0 and int(e.last_pass_us) == previous else 0.45
                        else:
                            internal = 1 if int(e.last_pass_us) == self.time_us else 0.45
                        e.weight = min(
                            1.0, e.weight + c.learning_rate * score * internal * (1 - e.weight) + 0.08 * impulse
                        )
                        e.stability = min(
                            1.0, e.stability + c.stability_gain * score * (1 + math.log1p(e.touches)) + impulse
                        )
                    e.eligibility = min(1.0, e.eligibility + 0.3 * score + 0.25 * impulse)
                    e.touches += 1
                    e.last_touch_us = str(self.time_us)
                self._edge_timer(e)
                for id in key:
                    self.timers.discard((3, id, 0))

    def _features(self, n):
        return [
            n.activation,
            n.trace,
            n.inhibition / (1 + n.inhibition),
            math.exp(-(self.time_us - int(n.last_touch_us)) / 1e6 / self.config.context_tau_s),
        ]

    def _receive(self, packets):
        c, inboxes, cohorts = self.config, {}, {}
        for serial, messages, direct, intensity in packets:
            for source, target, value, features in messages:
                inboxes.setdefault(target, []).append((serial, source, value, features, direct, intensity))
        for id, batch in sorted(inboxes.items()):
            if id not in self.nodes:
                continue
            groups = [batch] if c.arrival_mode == "coincident" else [[m] for m in batch]
            for group in groups:
                values = [m[2] for m in group]
                use = (
                    c.context_enabled
                    and c.context_mix > 0
                    and (c.reception_mode == "unified" or not any(m[4] for m in group))
                )
                if use:
                    n = self._settle_node(id)
                    value, coeff = local_attention(
                        self._features(n),
                        [m[3] for m in group],
                        values,
                        temperature=c.context_temperature,
                        mix=c.context_mix,
                    )
                else:
                    value, coeff = sum(values), [1.0] * len(group)
                direct = all(m[4] for m in group)
                amount, impulse = self._touch(id, value, direct, max(m[5] for m in group))
                if amount <= 0:
                    continue
                total = sum(v * k for v, k in zip(values, coeff))
                for m, k in zip(group, coeff):
                    if c.reception_mode == "unified" or m[4]:
                        fraction = m[2] * k / total if total else 0
                        cohorts.setdefault(m[0], []).append((id, amount * fraction, impulse * fraction))
        for serial in sorted(cohorts):
            merged = {}
            for id, amount, impulse in cohorts[serial]:
                old = merged.get(id, (0.0, 0.0))
                merged[id] = old[0] + amount, old[1] + impulse
            self._associate([(id, *values) for id, values in sorted(merged.items())])

    def _emit(self, id):
        if id not in self.nodes or id in self.silenced_nodes:
            return
        c, n = self.config, self._settle_node(id)
        self._maintenance(n)
        if c.inhibition:
            n.inhibition = self._soft(n.inhibition + n.pending_inhibition)
        n.pending_inhibition = 0.0
        messages, inhibitors = [], []
        features = self._features(n) if self.restored_learning else None
        fast_config = short_config = None
        flux = n.activation * self._response(n) * c.propagation_rate * c.propagation_interval_us / 1e6
        for key in sorted(self.outgoing.get(id, ())):
            if key in self.silenced_edges:
                continue
            e = self._settle_edge(key)
            if e.sleeping:
                continue
            weight = e.weight
            if c.fast_enabled:
                f = (
                    FastTrace(**(e.fast | {"time_us": int(e.fast["time_us"])}))
                    if e.fast
                    else FastTrace(time_us=int(e.birth_us))
                )
                if self.restored_learning:
                    if fast_config is None:
                        fast_config = c.fast_trace()
                    fast_value = f.projected(self.time_us, fast_config)
                    weight = min(1.0, weight + fast_config.gain * fast_value)
                else:
                    weight = f.efficacy(weight, self.time_us, c.fast_trace())
            amount = flux * weight
            if c.spatial_embedding and (not self.restored_learning or c.neighborhood_enabled):
                from threemind_core.spatial import position

                pa, pb = (
                    position(c.seed, e.source, c.spatial_dimensions),
                    position(c.seed, e.target, c.spatial_dimensions),
                )
                amount *= math.exp(-math.sqrt(sum((a - b) ** 2 for a, b in zip(pa, pb))) / c.spatial_radius)
            if n.activation < c.propagation_activation_min or amount < c.activation_floor or amount <= 0:
                continue
            if c.stp_enabled:
                if self.restored_learning and short_config is None:
                    short_config = c.short_term()
                st = (
                    ShortTermState(**(e.short_term | {"time_us": int(e.short_term["time_us"])}))
                    if e.short_term
                    else ShortTermState(time_us=int(e.birth_us))
                )
                if not c.depletion_enabled:
                    st = st.recovered(self.time_us, short_config if self.restored_learning else c.short_term())
                    st = ShortTermState(1.0, 0.0, st.utilization, self.time_us)
                st, fraction = st.release(self.time_us, short_config if self.restored_learning else c.short_term())
                if not c.depletion_enabled:
                    st = ShortTermState(1.0, 0.0, st.utilization, self.time_us)
                e.short_term = asdict(st)
                e.short_term["time_us"] = str(st.time_us)
                amount *= fraction
            amount = self._expense(n, amount, c.energy_associative_cost, "associative")
            self.transport["sent"] += amount
            if amount < c.activation_floor or amount <= 0:
                self.transport["discarded"] += amount
                continue
            messages.append([id, e.target, amount, features if self.restored_learning else self._features(n)])
            e.last_pass_us = str(self.time_us)
            if c.fast_enabled and c.plasticity:
                if self.restored_learning:
                    fast_value += -math.expm1(-fast_config.learning_rate * amount) * (1.0 - fast_value)
                    e.fast = asdict(FastTrace(fast_value, self.time_us))
                else:
                    f = (
                        FastTrace(**(e.fast | {"time_us": int(e.fast["time_us"])}))
                        if e.fast
                        else FastTrace(time_us=int(e.birth_us))
                    )
                    e.fast = asdict(f.transmit(amount, self.time_us, c.fast_trace()))
                e.fast["time_us"] = str(self.time_us)
            if c.plasticity:
                e.eligibility = min(1.0, 0.7 * e.eligibility + amount)
                if c.edge_consolidation_enabled:
                    e.weight = min(1.0, e.weight + c.associative_gain * amount)
                    e.stability = min(1.0, e.stability + c.stability_gain * amount)
                    if c.consolidation_mode == "adaptive-half-life":
                        e.half_life = grow(e.half_life, amount * 0.1, c)
                e.touches += 1
                e.last_touch_us = str(self.time_us)
                self._edge_timer(e)
        if c.revival_enabled and flux > 0:
            for key in sorted(self.incident.get(id, ())):
                if self.edges[key].sleeping and key not in self.silenced_edges:
                    self._event(self.time_us + c.delay_us, "wake", {"edge": list(key), "sender": id, "value": flux})
        if messages:
            self._event(self.time_us + c.delay_us, "signal", {"messages": messages})
        if c.inhibition:
            n.inhibition = self._soft(n.inhibition + n.generated_inhibition)
        n.generated_inhibition = 0.0
        conductances = []
        transfer = n.inhibition * min(1.0, c.inhibition_diffusion_rate * c.propagation_interval_us / 1e6)
        incident = (
            self.incident.get(id, ())
            if (not self.restored_learning or (c.inhibition and transfer >= c.inhibition_propagation_min))
            else ()
        )
        for key in sorted(incident):
            if key not in self.silenced_edges and not self.edges[key].sleeping:
                e = self._settle_edge(key)
                conductances.append((e.target if e.source == id else e.source, e.weight))
        weights = {}
        for target, w in conductances:
            weights[target] = max(weights.get(target, 0.0), w)
        total = sum(weights.values())
        if c.inhibition and total > 0 and transfer >= c.inhibition_propagation_min:
            transfer = self._expense(n, transfer, c.energy_inhibition_cost, "inhibition")
            if not self.restored_learning or transfer >= c.inhibition_propagation_min:
                n.inhibition -= transfer
                inhibitors = [[t, transfer * w / total] for t, w in sorted(weights.items())]
        if inhibitors:
            if self.restored_learning:
                for target, amount in inhibitors:
                    self._emission_inhibitors[target] = self._emission_inhibitors.get(target, 0.0) + amount
            else:
                self._event(self.time_us + c.delay_us, "inhibition", {"values": inhibitors})
        if self.restored_learning:
            n.last_emit_us = str(self.time_us)
        n.direct = n.associative = 0.0
        self._node_timers(n)
        self._pulse(n, after=True)

    def _drop_novelty_index(self, key):
        for id in key:
            entries = self.pending_novelty.get(id)
            if entries is not None:
                entries.discard(key)
                if not entries:
                    del self.pending_novelty[id]

    def _remove_edge(self, key, explicit=False):
        if key not in self.edges:
            return
        c, e = self.config, self._settle_edge(key)
        if not explicit and not e.sleeping and c.dormant_traces_enabled and e.weight >= c.dormant_prune_weight:
            e.sleeping = True
            self._edge_timer(e)
        else:
            del self.edges[key]
            if self.restored_learning:
                self._drop_novelty_index(key)
            self.outgoing.get(e.source, set()).discard(key)
            for id in key:
                self.incident.get(id, set()).discard(key)
            for kind in (2, 4):
                self.timers.discard((kind, *key))
            self.audit["edges_deleted"] += 1
        for id in key:
            if id in self.nodes:
                n = self._settle_node(id)
                if not any(not self.edges[k].sleeping for k in self.incident.get(id, ())):
                    n.isolated_us = str(self.time_us)
                    n.sleeping = n.activation == 0 and bool(self.incident.get(id))
                self._node_timers(n)

    def _delete_node(self, id):
        if id not in self.nodes:
            return
        for key in tuple(self.incident.get(id, ())):
            self._remove_edge(key, True)
        n = self.nodes.pop(id)
        self.receptors.pop(n.channel, None)
        self.regions.get(n.region, set()).discard(id)
        self.outgoing.pop(id, None)
        self.incident.pop(id, None)
        if self.restored_learning:
            self.pending_novelty.pop(id, None)
        self.active.discard(id)
        if self.life != "waiting" and not self.active and self.quiet_since_us is None:
            self.quiet_since_us = self.time_us
        for kind in (0, 1, 3, 5):
            self.timers.discard((kind, id, 0))
        self.energy._add("discarded_total", n.reserve)
        self.audit["nodes_deleted"] += 1

    def _expiry(self, kind, a, b):
        self.audit["expiry_checks"] += 1
        c, key = self.config, (a, b)
        if kind == 5 and a in self.nodes:
            n = self._settle_node(a)
            self._maintenance(n)
            self._node_timers(n)
            if c.energy_simulation_enabled and c.energy_starvation_damage_enabled:
                self.timers.set((5, a, 0), self.time_us + c.propagation_interval_us)
        elif kind in (1, 3) and a in self.nodes:
            n = self._settle_node(a)
            if kind == 3:
                floor = 0.006 if c.node_retention_mode == "automatic" else c.prune_support
                eligible = (
                    n.support < floor
                    if floor > 0
                    else self.time_us - max(int(n.isolated_us), int(n.last_touch_us)) >= c.dead_node_retention_us
                )
                if c.node_retention_mode == "manual" and floor > 0:
                    eligible = eligible and self.time_us - int(n.last_touch_us) > c.node_prune_after_us
                if (
                    not c.retain_nodes
                    and n.activation == 0
                    and not any(not self.edges[k].sleeping for k in self.incident.get(a, ()))
                    and eligible
                ):
                    self._delete_node(a)
                    return
            self._node_timers(n)
            self._pulse(n)
        elif kind in (2, 4) and key in self.edges:
            e = self._settle_edge(key)
            if kind == 4:
                reentry = max(e.novelty_source, e.novelty_target)
                if (
                    c.plasticity
                    and reentry > 0
                    and not e.sleeping
                    and key not in self.silenced_edges
                    and not any(id in self.silenced_nodes for id in key)
                ):
                    bonus = c.local_novelty_gain * max(0.0, 1 - reentry / c.novelty_touch_reference)
                    e.weight = min(1.0, e.weight + bonus)
                    e.stability = min(1.0, e.stability + bonus)
                e.novelty_deadline_us = None
                if self.restored_learning:
                    self._drop_novelty_index(key)
            elif c.plasticity and c.consolidation_mode == "legacy-stability":
                dt = c.propagation_interval_us / 1e6
                if c.eligibility_decay_enabled:
                    e.eligibility *= math.exp(-dt / c.eligibility_tau)
                if c.stability_decay_enabled:
                    e.stability = max(0.0, e.stability - dt / c.stability_tau * (1 - e.eligibility))
                if int(e.last_pass_us) != self.time_us:
                    e.weight *= max(0.0, 1 - 0.1 * c.forgetting_rate * (1 - (0.08 + 0.92 * e.stability))) ** (dt / 0.1)
                if self.restored_learning:
                    e.completed_period_us = str(self.time_us)
            if e.weight < (c.dormant_prune_weight if e.sleeping else c.prune_weight):
                self._remove_edge(key)
            else:
                self._edge_timer(e)

    def advance_to(self, target_us, observer=None, *, inputs_only=False):
        target_us = timestamp(target_us)
        if target_us < self.time_us:
            raise ValueError("simulation time cannot go backwards")
        while self.life != "dead":
            candidates = ([self.queue[0][0]] if self.queue else []) + (
                [self.timers.heap[0][0]] if self.timers.heap else []
            )
            if self.quiet_since_us is not None:
                candidates.append(self.quiet_since_us + self.config.quiescence_death_us)
            if not candidates or min(candidates) > target_us:
                break
            self.time_us = min(candidates)
            if self.restored_learning:
                self._before_emission = self.time_us % self.config.propagation_interval_us == 0 and (
                    self.time_us > self.completed_emission_us
                )
                self._direct_drives = {}
            packets, wake, energy_regions = [], {}, set()
            while self.queue and self.queue[0][0] == self.time_us:
                _, serial, kind, payload = heapq.heappop(self.queue)
                observed_payload = payload
                if kind == "stimulus":
                    s = Stimulus.from_dict(payload)
                    messages = []
                    for channel, value in sorted(s.channels):
                        raw = value * s.intensity * self.config.direct_gain
                        if self.restored_learning or self.config.reception_mode == "legacy-source":
                            raw = min(1.0, raw)
                        if raw <= 0:
                            continue
                        id = self.receptors.get(channel)
                        if id is None:
                            id = self._birth(channel)
                        if id is not None:
                            messages.append([-1, id, raw, [0.0] * 4])
                            if self.restored_learning:
                                self._direct_drives[serial, id] = value * s.intensity
                            if not self.restored_learning or self.config.energy_simulation_enabled:
                                energy_regions.add(self.nodes[id].region)
                    packets.append((serial, messages, True, s.intensity))
                elif kind == "signal":
                    packets.append((serial, payload["messages"], False, 1.0))
                    if not self.restored_learning or self.config.energy_simulation_enabled:
                        energy_regions.update(
                            self.nodes[m[1]].region for m in payload["messages"] if m[1] in self.nodes
                        )
                elif kind == "inhibition":
                    for id, value in payload["values"]:
                        if id in self.nodes and id not in self.silenced_nodes and self.config.inhibition:
                            n = self._settle_node(id)
                            n.pending_inhibition += value
                            self._pulse(n)
                elif kind == "wake":
                    key = tuple(payload["edge"])
                    if (
                        self.config.revival_enabled
                        and key not in self.silenced_edges
                        and not any(id in self.silenced_nodes for id in key)
                    ):
                        arrivals = wake.setdefault(key, {})
                        target = key[1] if payload["sender"] == key[0] else key[0]
                        arrivals[target] = arrivals.get(target, 0.0) + payload["value"]
                elif kind == "energy":
                    c = self.config
                    if c.energy_model == "global-ledger":
                        before = self.energy.supplied_total
                        accepted = self.energy.supply(payload["amount"], c.energy_capacity, True)["accepted"]
                        self.energy._add("discarded_total", payload["amount"] - (self.energy.supplied_total - before))
                    else:
                        self.energy._add("offered_total", payload["amount"])
                        if c.energy_distribution == "counter-random":
                            random = word(c.energy_seed, 2, self.energy_serial)
                        else:
                            self.energy_rng = (self.energy_rng * 6364136223846793005 + 1442695040888963407) & (
                                (1 << 64) - 1
                            )
                            random = self.energy_rng >> 32
                        region = random % c.energy_region_count
                        self.energy_serial += 1
                        amount = min(payload["amount"], max(0.0, c.energy_capacity - self.pools.get(region, 0.0)))
                        self.pools[region] = self.pools.get(region, 0.0) + amount
                        self.energy._add("supplied_total", amount)
                        self.energy._add("discarded_total", payload["amount"] - amount)
                        energy_regions.add(region)
                        accepted = amount
                    # Describe the delivery without replacing its scheduled input.
                    observed_payload = payload | {
                        "offered": payload["amount"],
                        "accepted": accepted,
                        "status": "accepted",
                    }
                self.sequence += 1
                if observer is not None and (not inputs_only or kind in ("stimulus", "energy")):
                    observer(
                        {
                            "sequence": self.sequence,
                            "time_us": str(self.time_us),
                            "kind": kind,
                            "event_id": serial,
                            "payload": copy.deepcopy(observed_payload),
                        }
                    )
            if self.config.energy_simulation_enabled and self.config.energy_model == "local-field":
                for region in sorted(energy_regions):
                    self._uptake(region)
            for key, arrivals in sorted(wake.items()):
                if key in self.edges and self.edges[key].sleeping:
                    e = self._settle_edge(key)
                    value = sum(arrivals.values())
                    if value >= self.config.edge_wake_threshold:
                        e.sleeping = False
                        self.audit["edges_awakened"] += 1
                        self._edge_timer(e)
                    for target, amount in sorted(arrivals.items()):
                        packets.append((-(key[0] + 1), [[-1, target, amount, [0.0] * 4]], False, 1.0))
            self._receive(packets)
            due = list(self.timers.due(self.time_us))
            if self.restored_learning:
                for kind, a, b in due:
                    if kind == 4:
                        self._expiry(kind, a, b)
                self._emission_inhibitors = {}
            pulses = [a for kind, a, b in due if kind == 0]
            if self.config.propagation_mode == "scan-control" and pulses:
                requested = set(pulses)
                pulses = [id for id in sorted(self.nodes) if id in requested]
                self.audit["scan_visits"] += len(self.nodes)
            for id in pulses:
                self._emit(id)
            if self.restored_learning:
                if self._emission_inhibitors:
                    self._event(
                        self.time_us + self.config.delay_us,
                        "inhibition",
                        {
                            "values": [
                                [id, self._soft(value)] for id, value in sorted(self._emission_inhibitors.items())
                            ]
                        },
                    )
                self._before_emission = False
                self.completed_emission_us = (
                    self.time_us // self.config.propagation_interval_us * self.config.propagation_interval_us
                )
            for kind, a, b in due:
                if kind != 0 and (not self.restored_learning or kind != 4):
                    self._expiry(kind, a, b)
            if (
                self.quiet_since_us is not None
                and not self.active
                and self.time_us - self.quiet_since_us >= self.config.quiescence_death_us
            ):
                self.life = "dead"
                self.energy.death_us = str(self.time_us)
        if self.life != "dead":
            self.time_us = target_us
        if self.restored_learning:
            self._before_emission = False
            self.completed_emission_us = (
                self.time_us // self.config.propagation_interval_us * self.config.propagation_interval_us
            )

    def intervene(self, *, nodes=(), edges=(), lesion=False, action=None):
        if action and lesion:
            raise ValueError("use action or lesion")
        action = action or ("delete_nodes" if lesion and nodes else "disconnect_edges" if lesion else "silence")
        if action not in ("silence", "restore", "delete_nodes", "disconnect_edges"):
            raise ValueError("unsupported intervention")
        for id in nodes:
            if action == "delete_nodes":
                self._delete_node(id)
            elif action == "restore":
                self.silenced_nodes.discard(id)
                if id in self.nodes:
                    self._pulse(self._settle_node(id))
            else:
                self.silenced_nodes.add(id)
                self.timers.discard((0, id, 0))
        for key in map(tuple, edges):
            if action == "disconnect_edges":
                self._remove_edge(key, True)
                self.silenced_edges.add(key)
            elif action == "restore":
                self.silenced_edges.discard(key)
            else:
                self.silenced_edges.add(key)

    def reconfigure(self, config):
        immutable = (
            "seed",
            "step_us",
            "propagation_interval_us",
            "energy_initial_reserve",
            "consolidation_mode",
            "memory_growth_formula",
            "novelty_mode",
            "propagation_mode",
            "propagation_phase",
            "arrival_mode",
            "reception_mode",
            "energy_model",
            "energy_distribution",
            "energy_seed",
            "energy_region_count",
        )
        if type(config) is not self.config_type or any(
            getattr(config, k) != getattr(self.config, k) for k in immutable
        ):
            raise ValueError(
                f"{self.dynamics.removeprefix('threemind.continuous-')} identity, clocks and model choices are fixed at birth"
            )
        # Explicit paused configuration intervention: permitted one-time full settlement.
        for id in tuple(self.nodes):
            self._maintenance(self._settle_node(id))
        for key in tuple(self.edges):
            self._settle_edge(key)
            e = self.edges[key]
            if e.short_term:
                st = ShortTermState(**(e.short_term | {"time_us": int(e.short_term["time_us"])})).recovered(
                    self.time_us, self.config.short_term()
                )
                e.short_term = asdict(st) | {"time_us": str(st.time_us)}
            if e.fast:
                old = FastTrace(**(e.fast | {"time_us": int(e.fast["time_us"])}))
                f = FastTrace(old.projected(self.time_us, self.config.fast_trace()), self.time_us)
                e.fast = asdict(f) | {"time_us": str(f.time_us)}
        self.config = config
        if config.energy_model == "global-ledger":
            self.energy.resize(config.energy_capacity)
        else:
            for region in self.pools:
                excess = max(0.0, self.pools[region] - config.energy_capacity)
                self.pools[region] -= excess
                self.energy._add("discarded_total", excess)
        if not config.dormant_traces_enabled:
            for key in tuple(self.edges):
                if self.edges[key].sleeping:
                    self._remove_edge(key, True)
            for n in self.nodes.values():
                n.sleeping = False
        for id in tuple(self.nodes):
            n = self._settle_node(id)
            n.half_life = min(config.memory_half_life_max_s, max(config.memory_half_life_min_s, n.half_life))
            if n.reserve > config.energy_node_capacity:
                self.energy._add("discarded_total", n.reserve - config.energy_node_capacity)
                n.reserve = config.energy_node_capacity
            n.energy_us = str(self.time_us)
            self._node_timers(n)
            self._pulse(n)
            self.timers.set(
                (5, n.id, 0),
                self.time_us + config.propagation_interval_us
                if config.energy_simulation_enabled and config.energy_starvation_damage_enabled
                else None,
            )
        for e in self.edges.values():
            e.half_life = min(config.memory_half_life_max_s, max(config.memory_half_life_min_s, e.half_life))
            self._edge_timer(e)

    def activations(self):
        return [(id, self._project_node(n, self.time_us).activation) for id, n in sorted(self.nodes.items())]

    def observation_nodes(self):
        return [asdict(self._project_node(n, self.time_us)) for _, n in sorted(self.nodes.items())]

    def induced_edges(self, node_ids):
        selected = set(node_ids)
        return [
            asdict(self._project_edge(e, self.time_us))
            for key, e in sorted(self.edges.items())
            if key[0] in selected and key[1] in selected and not e.sleeping
        ]

    def graph(self, limit=None):
        nodes = self.observation_nodes()
        nodes = nodes if limit is None else nodes[:limit]
        edges = self.induced_edges(n["id"] for n in nodes)
        return {"nodes": nodes, "edges": edges, "kernel_id": self.dynamics, "observation_quantity": "activation"}

    def spatial_geometry(self):
        from threemind_core.spatial import position

        c = self.config
        return {
            "schema": "threemind.spatial-observation/1",
            "nodes": [{"id": id, "position": position(c.seed, id, c.spatial_dimensions)} for id in sorted(self.nodes)]
            if c.spatial_embedding
            else [],
            "edges": [],
            "parameters": {"spatial_embedding": c.spatial_embedding},
            "seed": c.seed,
        }

    def metrics(self):
        nodes = self.observation_nodes()
        edges = [self._project_edge(e, self.time_us) for e in self.edges.values() if not e.sleeping]
        energy = self.energy.to_dict()
        if self.config.energy_model == "local-field":
            energy["reserve"] = sum(self.pools.values()) + sum(n.reserve for n in self.nodes.values())
        energy = energy_observation(energy, self.config.to_dict(), self.time_us)
        count = len(nodes)
        activation = sum(n["activation"] for n in nodes)
        return {
            "time_us": str(self.time_us),
            "state_time_us": str(self.time_us),
            "quiet_since_us": None if self.quiet_since_us is None else str(self.quiet_since_us),
            "sequence": self.sequence,
            "life": self.life,
            "nodes": count,
            "edges": len(edges),
            "activation": activation,
            "mean_activation": activation / count if count else None,
            "mean_weight": sum(e.weight for e in edges) / len(edges) if edges else None,
            "active_fraction": sum(n["activation"] > self.config.activation_floor for n in nodes) / count
            if count
            else None,
            "saturated_fraction": sum(n["activation"] >= 0.95 for n in nodes) / count if count else None,
            "edge_density": len(edges) / (count * (count - 1)) if count > 1 else None,
            "inhibition": sum(n["inhibition"] for n in nodes),
            "pending_events": len(self.queue) + len(self.timers.heap),
            "resources": None,
            "attention": None,
            "transport": self.transport.copy(),
            "energy": energy,
            "local_audit": self.audit.copy(),
            "dynamics": self.dynamics,
            "kernel_id": self.dynamics,
            "state_schema": self.state_schema,
        }

    def capture_state(self):
        doc = {
            "schema": self.state_schema,
            "dynamics": self.dynamics,
            "config": self.config.to_dict(),
            "definition": self.definition(self.config),
            "time_us": str(self.time_us),
            "sequence": self.sequence,
            "next_event": self.next_event,
            "next_node": self.next_node,
            "sources_open": self.sources_open,
            "life": self.life,
            "quiet_since_us": None if self.quiet_since_us is None else str(self.quiet_since_us),
            "nodes": [asdict(n) for _, n in sorted(self.nodes.items())],
            "edges": [asdict(e) for _, e in sorted(self.edges.items())],
            "queue": [{"time_us": str(t), "id": id, "kind": k, "payload": p} for t, id, k, p in sorted(self.queue)],
            "timers": self.timers.rows(),
            "active": sorted(self.active),
            "silenced_nodes": sorted(self.silenced_nodes),
            "silenced_edges": [list(k) for k in sorted(self.silenced_edges)],
            "transport": self.transport.copy(),
            "audit": self.audit.copy(),
            "energy": self.energy.to_dict(),
            "pools": [[r, v] for r, v in sorted(self.pools.items())],
            "energy_serial": self.energy_serial,
            "energy_rng": str(self.energy_rng),
        }
        if self.restored_learning:
            doc["completed_emission_us"] = str(self.completed_emission_us)
        doc["definition_hash"] = hashlib.sha256(canonical_bytes(doc["definition"])).hexdigest()
        return StateImage.from_dict(doc)

    def _restore(self, doc):
        if doc.get("schema") != self.state_schema or doc.get("dynamics") != self.dynamics:
            raise ValueError(
                f"{self.dynamics.removeprefix('threemind.continuous-')} identity mismatch; conversion is not restoration"
            )
        if set(doc) != set(self.capture_state().to_dict()):
            raise ValueError(f"invalid {self.dynamics.removeprefix('threemind.continuous-')} state fields")
        self.config = self.config_type(**doc["config"])
        expected = self.definition(self.config)
        if (
            doc.get("definition") != expected
            or doc.get("definition_hash") != hashlib.sha256(canonical_bytes(expected)).hexdigest()
        ):
            raise ValueError(f"{self.dynamics.removeprefix('threemind.continuous-')} definition/hash mismatch")
        self.time_us = timestamp(doc["time_us"])
        for key in ("sequence", "next_event", "next_node", "sources_open", "life", "energy_serial"):
            setattr(self, key, doc[key])
        self.quiet_since_us = None if doc["quiet_since_us"] is None else timestamp(doc["quiet_since_us"])
        self.transport, self.audit = doc["transport"], doc["audit"]
        self.energy = Energy.restore(doc["energy"], self.time_us, self.config)
        self.pools = dict(doc["pools"])
        self.energy_rng = int(doc["energy_rng"])
        for row in doc["nodes"]:
            n = self.node_type(**row)
            if (
                n.id in self.nodes
                or n.channel in self.receptors
                or not 0 <= int(n.state_us) <= self.time_us
                or not 0 <= n.region < self.config.energy_region_count
            ):
                raise ValueError("invalid local node history")
            self.nodes[n.id], self.receptors[n.channel] = n, n.id
            self.regions.setdefault(n.region, set()).add(n.id)
        for row in doc["edges"]:
            e = self.edge_type(**row)
            key = e.source, e.target
            if key in self.edges or any(id not in self.nodes for id in key) or int(e.state_us) > self.time_us:
                raise ValueError("invalid local edge history")
            self.edges[key] = e
            self.outgoing.setdefault(e.source, set()).add(key)
            for id in key:
                self.incident.setdefault(id, set()).add(key)
                if self.restored_learning and e.novelty_deadline_us is not None:
                    self.pending_novelty.setdefault(id, set()).add(key)
        for row in doc["queue"]:
            t = timestamp(row["time_us"])
            if (
                t < self.time_us
                or row["id"] >= self.next_event
                or row["kind"] not in ("stimulus", "signal", "inhibition", "wake", "energy")
            ):
                raise ValueError("invalid local queued event")
            heapq.heappush(self.queue, (t, row["id"], row["kind"], row["payload"]))
        for kind, a, b, t in doc["timers"]:
            key = kind, a, b
            if (
                kind not in range(6)
                or timestamp(t) < self.time_us
                or key in self.timers.positions
                or (kind in (0, 1, 3, 5) and a not in self.nodes)
                or (kind in (2, 4) and (a, b) not in self.edges)
            ):
                raise ValueError("invalid local deadline")
            self.timers.set(key, timestamp(t))
        self.active, self.silenced_nodes = set(doc["active"]), set(doc["silenced_nodes"])
        self.silenced_edges = set(map(tuple, doc["silenced_edges"]))
        if not self.active <= self.nodes.keys() or any(n.id >= self.next_node for n in self.nodes.values()):
            raise ValueError("invalid local identities")
        # Missing expiry records must not silently make objects immortal.
        for n in self.nodes.values():
            if (
                n.activation > self.config.activation_floor
                and self.config.activation_decay_enabled
                and self.config.activation_floor > 0
                and (1, n.id, 0) not in self.timers.positions
            ):
                raise ValueError("missing node activation deadline")
        self._validate()

    def _validate(self):
        c = self.config
        if set(self.audit) != {
            "node_visits",
            "edge_visits",
            "scan_visits",
            "expiry_checks",
            "nodes_deleted",
            "edges_deleted",
            "nodes_awakened",
            "edges_awakened",
        } or set(self.transport) != {"sent", "received", "activated", "discarded"}:
            raise ValueError("invalid local audit or transport fields")
        if any(type(v) is not int or not 0 <= v < 2**64 for v in self.audit.values()):
            raise ValueError("invalid local audit counter")
        for v in self.transport.values():
            number(v, "transport counter", high=1.7976931348623157e308)
        if self.life not in ("waiting", "active", "dead") or (
            self.quiet_since_us is not None and self.quiet_since_us > self.time_us
        ):
            raise ValueError("invalid lifecycle")
        for key in ("sequence", "next_event", "next_node", "energy_serial", "energy_rng"):
            if type(getattr(self, key)) is not int or not 0 <= getattr(self, key) < 2**64:
                raise ValueError("invalid local counter")
        if type(self.sources_open) is not bool or set(self.pools) != set(range(c.energy_region_count)):
            raise ValueError("invalid local identities or pools")
        for v in self.pools.values():
            number(v, "local energy pool", high=c.energy_capacity)
        for n in self.nodes.values():
            for t in (n.state_us, n.birth_us, n.last_touch_us, n.isolated_us, n.energy_us):
                if timestamp(t) > self.time_us:
                    raise ValueError("invalid node clock")
            if (
                type(n.id) is not int
                or type(n.channel) is not int
                or not 0 <= n.channel < 2**32
                or type(n.touches) is not int
                or n.touches < 0
                or type(n.sleeping) is not bool
            ):
                raise ValueError("invalid local node identity")
            for k, v in asdict(n).items():
                if isinstance(v, (int, float)) and k not in ("id", "channel", "touches", "region", "sleeping"):
                    number(v, "local node value", high=1.7976931348623157e308)
            if (
                any(getattr(n, k) > 1 for k in ("activation", "trace", "support", "stability", "local_plasticity"))
                or n.reserve > c.energy_node_capacity
                or not c.memory_half_life_min_s <= n.half_life <= c.memory_half_life_max_s
            ):
                raise ValueError("invalid local node bounds")
            if (
                c.energy_simulation_enabled
                and c.energy_starvation_damage_enabled
                and (5, n.id, 0) not in self.timers.positions
            ):
                raise ValueError("missing node energy deadline")
            if (
                not n.sleeping
                and n.id not in self.silenced_nodes
                and (n.activation > 0 or n.inhibition >= c.inhibition_propagation_min or n.pending_inhibition > 0)
                and (0, n.id, 0) not in self.timers.positions
            ):
                raise ValueError("missing node emission deadline")
            if (
                c.plasticity
                and not c.retain_nodes
                and not any(not self.edges[k].sleeping for k in self.incident.get(n.id, ()))
                and (n.activation == 0 or (c.activation_decay_enabled and c.activation_floor > 0))
            ):
                floor = 0.006 if c.node_retention_mode == "automatic" else c.prune_support
                deletable = (
                    n.support < floor
                    or (c.node_retention_mode == "manual" and floor == 0)
                    or (c.support_decay_enabled and (c.node_retention_mode == "automatic" or n.stability < 1))
                )
                if deletable and (3, n.id, 0) not in self.timers.positions:
                    raise ValueError("missing node reclamation deadline")
        for key, e in self.edges.items():
            for t in (e.state_us, e.birth_us, e.last_touch_us, e.last_pass_us):
                if timestamp(t) > self.time_us:
                    raise ValueError("invalid edge clock")
            for k in ("weight", "stability", "eligibility", "novelty_source", "novelty_target"):
                number(getattr(e, k), "local edge value", high=1.7976931348623157e308)
            if (
                key[0] == key[1]
                or any(getattr(e, k) > 1 for k in ("weight", "stability", "eligibility"))
                or not c.memory_half_life_min_s <= e.half_life <= c.memory_half_life_max_s
            ):
                raise ValueError("invalid local edge bounds")
            if e.short_term:
                ShortTermState(**(e.short_term | {"time_us": timestamp(e.short_term["time_us"])})).recovered(
                    self.time_us, c.short_term()
                )
            if e.fast:
                FastTrace(**(e.fast | {"time_us": timestamp(e.fast["time_us"])})).projected(
                    self.time_us, c.fast_trace()
                )
            expiring = (
                c.consolidation_mode == "legacy-stability"
                or crossing(e.weight, e.half_life, c.dormant_prune_weight if e.sleeping else c.prune_weight, c)
                is not None
            )
            if c.plasticity and expiring and (2, *key) not in self.timers.positions:
                raise ValueError("missing connection expiry deadline")
            if e.novelty_deadline_us is not None and (4, *key) not in self.timers.positions:
                raise ValueError("missing novelty deadline")
        seen = set()
        for t, id, kind, payload in self.queue:
            if id in seen:
                raise ValueError("duplicate queued event")
            seen.add(id)
            if kind == "stimulus":
                s = Stimulus.from_dict(payload)
                if s.time_us != t:
                    raise ValueError("queued stimulus clock mismatch")
            elif kind == "energy":
                supply_payload(**payload)
            elif kind == "signal":
                for source, target, value, features in payload["messages"]:
                    if (
                        type(source) is not int
                        or not -1 <= source < 2**63
                        or type(target) is not int
                        or not 0 <= target < 2**64
                    ):
                        raise ValueError("invalid queued signal identities")
                    number(value, "queued signal", high=1e12)
                    if len(features) != 4 or any(not math.isfinite(v) or not -1 <= v <= 1 for v in features):
                        raise ValueError("invalid queued features")
            elif kind == "inhibition":
                for id, value in payload["values"]:
                    if type(id) is not int or not 0 <= id < 2**64:
                        raise ValueError("invalid queued inhibition identity")
                    number(value, "queued inhibition", high=1e12)
            elif kind == "wake":
                if (
                    len(payload["edge"]) != 2
                    or any(type(id) is not int or not 0 <= id < 2**64 for id in payload["edge"])
                    or payload["sender"] not in payload["edge"]
                ):
                    raise ValueError("invalid wake sender")
                number(payload["value"], "queued wake", high=1e12)
