"""continuous-memory/3: object-local retention; historical kernels are unchanged."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from threemind_core import StateImage
from threemind_core.engine import Edge
from threemind_core.spec import timestamp

from .local_deadlines import LocalDeadlines
from .mechanisms import number
from .novelty import MECHANISMS as PREVIOUS_MECHANISMS
from .novelty import NoveltyConfig, NoveltyDynamics, NoveltyEngine
from .novelty import definition as previous_definition

KERNEL_ID = "threemind.continuous-memory/3"
STATE_SCHEMA = "threemind.continuous-memory-state/3.1"
MECHANISMS = PREVIOUS_MECHANISMS + (
    ("threemind.adaptive-half-life/2", "local-touch-emission-expiry"),
    ("threemind.strong-input-fatigue/2", "accepted-input"),
    ("threemind.optional-dormancy/2", "local-expiry"),
    ("threemind.local-awakening/1", "same-time-local-arrivals"),
)
BASE_KEYS = tuple(NoveltyConfig.__dataclass_fields__)
NODE_SUPPORT_FLOOR = 0.006
DOSE_SECONDS = 0.1
AUDIT_KEYS = (
    "dormant_created",
    "dormant_expired",
    "revived",
    "nodes_awakened",
    "nodes_deleted",
    "node_settlements",
    "edge_settlements",
    "expiry_checks",
)


@dataclass(frozen=True, slots=True)
class RetentionConfig(NoveltyConfig):
    consolidation_mode: str = "adaptive-half-life"
    memory_growth_formula: str = "log-saturating"
    node_retention_mode: str = "automatic"
    retain_nodes: bool = False
    dead_node_retention_us: int = 80_000_000
    dormant_traces_enabled: bool = False
    revival_enabled: bool = False
    node_wake_threshold: float | None = None
    edge_wake_threshold: float | None = None
    memory_half_life_min_s: float = 30.0
    memory_half_life_max_s: float = 2_592_000.0
    memory_half_life_decay_rate: float = 0.125
    memory_learning_gain: float = 0.2
    memory_weight_learning_rate: float = 0.55
    strong_fatigue_enabled: bool = True
    strong_fatigue_tau_s: float = 5.0
    strong_fatigue_gain: float = 1.0
    dormant_prune_weight: float = 1e-8

    def __post_init__(self):
        base = NoveltyConfig(**{k: getattr(self, k) for k in BASE_KEYS})
        for k in BASE_KEYS:
            object.__setattr__(self, k, getattr(base, k))
        if self.propagation_limit is not None or self.edge_adaptation_limit is not None:
            raise ValueError("memory/3 does not support propagation/adaptation quotas; pace the host instead")
        for key, choices in (
            ("consolidation_mode", ("adaptive-half-life", "legacy-stability")),
            ("memory_growth_formula", ("log-saturating", "linear-saturating")),
            ("node_retention_mode", ("automatic", "manual")),
        ):
            if getattr(self, key) not in choices:
                raise ValueError(f"unknown {key}")
        for key in EXTRA_KEYS:
            value = getattr(self, key)
            if key in BOOL_KEYS:
                if type(value) is not bool:
                    raise ValueError(f"{key} must be boolean")
            elif key == "dead_node_retention_us":
                if type(value) is not int or not 1 <= value <= 2**53 - 1:
                    raise ValueError("dead_node_retention_us must be a positive safe integer")
            elif key.endswith("wake_threshold"):
                if value is not None:
                    object.__setattr__(self, key, number(value, key, low=1e-12, high=1e12))
            elif key not in ("consolidation_mode", "node_retention_mode", "memory_growth_formula"):
                object.__setattr__(self, key, number(value, key, high=1e12))
        if not 1e-6 <= self.memory_half_life_min_s < self.memory_half_life_max_s:
            raise ValueError("half-life bounds must satisfy 1e-6 <= min < max")
        if self.strong_fatigue_tau_s < 1e-6 or not 0 < self.dormant_prune_weight <= 1 or self.prune_support > 1:
            raise ValueError("invalid retention bounds")
        if self.dormant_traces_enabled and self.dormant_prune_weight >= self.prune_weight:
            raise ValueError("enabled dormancy requires dormant floor < prune_weight")
        if not self.dormant_traces_enabled:
            object.__setattr__(self, "revival_enabled", False)
        if self.revival_enabled and (self.node_wake_threshold is None or self.edge_wake_threshold is None):
            raise ValueError("awakening requires explicit positive node_wake_threshold and edge_wake_threshold")


EXTRA_KEYS = tuple(k for k in RetentionConfig.__dataclass_fields__ if k not in BASE_KEYS)
BOOL_KEYS = ("retain_nodes", "dormant_traces_enabled", "revival_enabled", "strong_fatigue_enabled")


def decay(weight, half_life, dt, p):
    end = max(p.memory_half_life_min_s, half_life - p.memory_half_life_decay_rate * dt)
    falling = (
        min(dt, max(0.0, half_life - p.memory_half_life_min_s) / p.memory_half_life_decay_rate)
        if p.memory_half_life_decay_rate
        else 0.0
    )
    integral = math.log(half_life / end) / p.memory_half_life_decay_rate if falling > 0 else 0.0
    integral += (dt - falling) / end
    return weight * math.exp(-math.log(2.0) * integral), end


def grow(h, dose, p):
    if dose <= 0:
        return h
    if p.memory_growth_formula == "linear-saturating":
        return min(p.memory_half_life_max_s, h + p.memory_half_life_min_s * p.memory_learning_gain * dose)
    xmax = math.log(p.memory_half_life_max_s / p.memory_half_life_min_s)
    x = math.log(h / p.memory_half_life_min_s)
    return min(
        p.memory_half_life_max_s,
        p.memory_half_life_min_s * math.exp(xmax - (xmax - x) * math.exp(-p.memory_learning_gain * dose / xmax)),
    )


def crossing(q, h, floor, p):
    """Seconds to the passive threshold, inverse of decay; no numerical polling."""
    if floor <= 0:
        return None
    if q <= floor:
        return 0.0
    need = math.log(q / floor) / math.log(2.0)
    r, low = p.memory_half_life_decay_rate, p.memory_half_life_min_s
    if r == 0:
        return need * h
    fall = math.log(h / low) / r
    if need <= fall:
        return h * -math.expm1(-r * need) / r
    return (h - low) / r + (need - fall) * low


class RetentionDynamics(NoveltyDynamics):
    birth_expiry_enabled = False  # Preserved /3 behavior; fixed at birth by the kernel identity.

    def __init__(self, config, state=None):
        # Values are H and the object's own last materialization time.
        self.memory_nodes, self.memory_edges, self.dormant = {}, {}, {}
        self.isolated, self.fatigue, self.salience = {}, {}, {}
        self.contacts, self.sleeping = {}, set()
        self.wake_edges, self.wake_nodes = {}, {}
        self.deadlines = LocalDeadlines()
        self._strong_intensity = 1.0
        self.retention_audit = dict.fromkeys(AUDIT_KEYS, 0)
        super().__init__(config, state)

    def _adaptive_retention_active(self):
        return self.parameters.consolidation_mode == "adaptive-half-life"

    def _automatic_node_retention(self):
        return self.parameters.node_retention_mode == "automatic"

    def _local_retention_enabled(self):
        return True

    def _node_became_quiet(self, node_id):
        if self.contacts.get(node_id) and not self.incident.get(node_id):
            self.sleeping.add(node_id)

    def _support_changed(self, node_id):
        self._schedule_node(node_id)

    def _legacy_edge_decayed(self, key):
        if self.edges[key].weight < self.config.prune_weight:
            self.deadlines.set((1, *key), self.time_us)

    def _round_expiry(self, seconds):
        if seconds is None or not math.isfinite(seconds):
            return None
        # Structural decisions retain the established post-emission lattice.
        earliest = self.time_us + max(1, math.ceil(seconds * 1e6))
        base, period = self.next_propagation_us, self.config.propagation_interval_us
        return base + max(0, (earliest - base + period - 1) // period) * period

    def _node_value(self, node_id, when):
        n = self.nodes[node_id]
        h, t = self.memory_nodes[node_id]
        if self.config.plasticity and self.config.support_decay_enabled and self._automatic_node_retention():
            return decay(n.support, h, (when - t) / 1e6, self.parameters)
        return n.support, h

    def _edge_value(self, key, when):
        if key in self.edges:
            e, (h, t) = self.edges[key], self.memory_edges[key]
        else:
            e, h, t = self.dormant[key]
        if self.config.plasticity:
            dt = (when - t) / 1e6
            if self._adaptive_retention_active():
                return decay(e.weight, h, dt, self.parameters)
            if key in self.dormant:
                return e.weight * math.exp(-self.config.forgetting_rate * dt), h
        return e.weight, h

    def _settle_node(self, node_id):
        if node_id not in self.memory_nodes:
            self.memory_nodes[node_id] = [self.parameters.memory_half_life_min_s, self.time_us]
            self.isolated[node_id] = self.time_us
        q, h = self._node_value(node_id, self.time_us)
        self.nodes[node_id].support = q
        self.memory_nodes[node_id] = [h, self.time_us]
        self.retention_audit["node_settlements"] += 1

    def _prepare_edge(self, key):
        if key not in self.memory_edges or self.memory_edges[key][1] == self.time_us:
            return
        q, h = self._edge_value(key, self.time_us)
        self.edges[key].weight = q
        self.memory_edges[key] = [h, self.time_us]
        self.retention_audit["edge_settlements"] += 1

    def _schedule_node(self, node_id):
        key = (0, node_id, 0)
        if self.parameters.retain_nodes or not self.config.plasticity or self.incident.get(node_id):
            self.deadlines.discard(key)
            return
        n, c, p = self.nodes[node_id], self.config, self.parameters
        if n.activation > 0 and (not c.activation_decay_enabled or c.activation_floor <= 0):
            self.deadlines.discard(key)
            return
        inactive = (
            max(
                0.0,
                c.activation_tau * math.log(n.activation / c.activation_floor)
                - (self.time_us - self.state_time_us) / 1e6,
            )
            if n.activation > c.activation_floor
            else 0.0
        )
        if self._automatic_node_retention():
            q, h = self._node_value(node_id, self.time_us)
            delay = (
                crossing(q, h, NODE_SUPPORT_FLOOR, p)
                if c.support_decay_enabled
                else (0.0 if q < NODE_SUPPORT_FLOOR else None)
            )
        elif c.prune_support == 0:
            delay = max(
                0.0, (max(self.isolated[node_id], int(n.last_touch_us)) + p.dead_node_retention_us - self.time_us) / 1e6
            )
        else:
            rate = (1 - n.stability) / c.support_tau if c.support_decay_enabled else 0.0
            delay = (
                max(0.0, (n.support - c.prune_support) / rate)
                if rate > 0
                else (0.0 if n.support < c.prune_support else None)
            )
            if delay is not None:
                delay = max(delay, (int(n.last_touch_us) + c.node_prune_after_us + 1 - self.time_us) / 1e6)
        self.deadlines.set(key, self._round_expiry(max(inactive, delay)) if delay is not None else None)

    def _edge_changed(self, key):
        if key not in self.memory_edges:
            self._drop_dormant(key)
            self.memory_edges[key] = [self.parameters.memory_half_life_min_s, self.time_us]
        for n in key:
            self.isolated.pop(n, None)
            self.deadlines.discard((0, n, 0))
        self._schedule_edge(key)

    def _schedule_edge(self, key):
        if not self.config.plasticity:
            self.deadlines.discard((1, *key))
            return
        if self._adaptive_retention_active():
            q, h = self._edge_value(key, self.time_us)
            t = self._round_expiry(crossing(q, h, self.config.prune_weight, self.parameters))
        else:
            # Legacy forgetting already runs at the original propagation phase.
            t = self._round_expiry(0) if self.edges[key].weight < self.config.prune_weight else None
        self.deadlines.set((1, *key), t)

    def _schedule_dormant(self, key):
        q, h = self._edge_value(key, self.time_us)
        if self._adaptive_retention_active():
            delay = crossing(q, h, self.parameters.dormant_prune_weight, self.parameters)
        else:
            rate = self.config.forgetting_rate
            delay = (
                max(0.0, math.log(q / self.parameters.dormant_prune_weight) / rate)
                if q > 0 and rate
                else (0.0 if q < self.parameters.dormant_prune_weight else None)
            )
        self.deadlines.set((2, *key), self._round_expiry(delay) if self.config.plasticity else None)

    def _local_factor(self, mapping, node_id):
        v, t = mapping.get(node_id, (0.0, self.time_us))
        return v * math.exp(-(self.time_us - t) / 1e6 / self.parameters.strong_fatigue_tau_s)

    def _inhibitory_response(self, node):
        return super()._inhibitory_response(node) / (1 + self._local_factor(self.fatigue, node.id))

    def _touch(self, node_id, value, *, direct):
        if node_id not in self.nodes or node_id in self.silenced_nodes or value <= 0:
            return 0.0
        if node_id in self.sleeping and self.parameters.revival_enabled:
            self.wake_nodes[node_id] = self.wake_nodes.get(node_id, 0.0) + value
            return 0.0
        self._settle_node(node_id)
        amount = super()._touch(node_id, value, direct=direct)
        if amount > 0:
            if not self.incident.get(node_id):
                self.isolated[node_id] = self.time_us
            salience = self._local_factor(self.salience, node_id)
            if direct and self._strong_intensity > 1:
                extra = amount * (self._strong_intensity - 1)
                if self.config.energy_simulation_enabled:
                    extra = self.energy.afford(extra, self.config.energy_direct_cost, "direct")
                salience = min(1e12, salience + extra)
                self.salience[node_id] = [salience, self.time_us]
                if self.parameters.strong_fatigue_enabled:
                    self.fatigue[node_id] = [
                        min(
                            1e12,
                            self._local_factor(self.fatigue, node_id) + extra * self.parameters.strong_fatigue_gain,
                        ),
                        self.time_us,
                    ]
            if self.config.plasticity and self._automatic_node_retention():
                dose = amount * DOSE_SECONDS * (1 + salience)
                self.memory_nodes[node_id][0] = grow(self.memory_nodes[node_id][0], dose, self.parameters)
                n = self.nodes[node_id]
                n.support = 1 - (1 - n.support) * math.exp(-self.parameters.memory_weight_learning_rate * dose)
            self._schedule_node(node_id)
        elif self.birth_expiry_enabled:
            # A born object needs a lifecycle even when energy/gating accepts no signal.
            # No support, dose, touch reward or half-life growth is granted here.
            self._schedule_node(node_id)
        return amount

    def _stimulate(self, stimulus):
        self._strong_intensity = stimulus.intensity
        try:
            super()._stimulate(stimulus)
        finally:
            self._strong_intensity = 1.0

    def _update_touched(self, touched):
        super()._update_touched(touched)
        for node, _ in touched:
            self._schedule_node(node)

    def effective_weight(self, edge):
        self._prepare_edge((edge.source, edge.target))
        return super().effective_weight(edge)

    def record_emission(self, node, edge, amount):
        super().record_emission(node, edge, amount)
        key = edge.source, edge.target
        if self.config.plasticity and self._adaptive_retention_active() and self.parameters.edge_consolidation_enabled:
            self.memory_edges[key][0] = grow(self.memory_edges[key][0], amount * DOSE_SECONDS, self.parameters)
        self._schedule_edge(key)

    def _edge_capacity_used(self, key=None):
        return len(self.edges) + len(self.dormant) - int(key in self.dormant)

    def _drop_dormant(self, key):
        self.deadlines.discard((2, *key))
        if self.dormant.pop(key, None) is not None:
            for n in key:
                self.contacts[n].discard(key)
                if not self.contacts[n]:
                    del self.contacts[n]
        self.wake_edges.pop(key, None)

    def _remove_edge(self, key):
        super()._remove_edge(key)
        self.traversed.discard(key)
        self.memory_edges.pop(key, None)
        self.deadlines.discard((1, *key))
        for n in key:
            if n in self.nodes and not self.incident.get(n):
                self.isolated.setdefault(n, self.time_us)
                self._schedule_node(n)

    def _before_emit_node(self, node):
        if not self.parameters.revival_enabled or node.id in self.silenced_nodes:
            return
        amount = (
            node.activation
            * self._inhibitory_response(node)
            * self.config.propagation_rate
            * self.config.propagation_interval_us
            / 1e6
        )
        if amount <= 0 or amount < self.config.activation_floor:
            return
        for key in self.contacts.get(node.id, ()):
            if key not in self.silenced_edges:
                self.wake_edges[key] = self.wake_edges.get(key, 0.0) + amount

    def _settle_local_arrivals(self):
        super()._settle_local_arrivals()
        pending, self.wake_nodes = self.wake_nodes, {}
        for n, value in sorted(pending.items()):
            if n in self.sleeping and value >= self.parameters.node_wake_threshold and n not in self.silenced_nodes:
                self.sleeping.remove(n)
                self.retention_audit["nodes_awakened"] += 1
                amount = self._touch(n, value, direct=False)
                if amount > 0:
                    self._update_touched([(n, amount)])

    def _prune(self):
        if not self.config.plasticity:
            self.wake_edges.clear()
            return
        for kind, a, b in self.deadlines.due(self.time_us):
            self.retention_audit["expiry_checks"] += 1
            key = a, b
            if kind == 1 and key in self.edges:
                self._prepare_edge(key)
                e = self.edges[key]
                if e.weight < self.config.prune_weight:
                    h = self.memory_edges[key][0]
                    self._remove_edge(key)
                    if self.parameters.dormant_traces_enabled and e.weight >= self.parameters.dormant_prune_weight:
                        self.dormant[key] = [e, h, self.time_us]
                        for n in key:
                            self.contacts.setdefault(n, set()).add(key)
                            if not self.incident.get(n) and self.nodes[n].activation == 0:
                                self.sleeping.add(n)
                        self._schedule_dormant(key)
                        self.retention_audit["dormant_created"] += 1
                else:
                    self._schedule_edge(key)
            elif kind == 2 and key in self.dormant:
                q, h = self._edge_value(key, self.time_us)
                if q < self.parameters.dormant_prune_weight:
                    self._drop_dormant(key)
                    self.retention_audit["dormant_expired"] += 1
                else:
                    self._schedule_dormant(key)
            elif kind == 0 and a in self.nodes:
                self._settle_node(a)
                n, c, p = self.nodes[a], self.config, self.parameters
                eligible = (
                    n.support < NODE_SUPPORT_FLOOR
                    if self._automatic_node_retention()
                    else (
                        n.support < c.prune_support and self.time_us - int(n.last_touch_us) > c.node_prune_after_us
                        if c.prune_support > 0
                        else self.time_us - max(self.isolated.get(a, self.time_us), int(n.last_touch_us))
                        >= p.dead_node_retention_us
                    )
                )
                if not p.retain_nodes and n.activation == 0 and not self.incident.get(a) and eligible:
                    self._delete_local_node(a)
                else:
                    if n.activation == 0 and not self.incident.get(a) and self.contacts.get(a):
                        self.sleeping.add(a)
                    self._schedule_node(a)
        pending, self.wake_edges = self.wake_edges, {}
        for key, amount in sorted(pending.items()):
            if (
                key not in self.dormant
                or amount < self.parameters.edge_wake_threshold
                or key in self.silenced_edges
                or any(n in self.silenced_nodes for n in key)
            ):
                continue
            q, h = self._edge_value(key, self.time_us)
            edge = self.dormant[key][0]
            self._drop_dormant(key)
            if q < self.parameters.dormant_prune_weight:
                continue
            edge.weight = q
            self.edges[key] = edge
            self.memory_edges[key] = [h, self.time_us]
            self.outgoing.setdefault(key[0], set()).add(key[1])
            self.incident.setdefault(key[0], set()).add(key[1])
            self.incident.setdefault(key[1], set()).add(key[0])
            self._edge_changed(key)
            self.retention_audit["revived"] += 1

    def _delete_local_node(self, n):
        for key in tuple(self.contacts.get(n, ())):
            self._drop_dormant(key)
        self.receptors.pop(self.nodes[n].channel, None)
        del self.nodes[n]
        self.memory_nodes.pop(n, None)
        self.isolated.pop(n, None)
        self.fatigue.pop(n, None)
        self.salience.pop(n, None)
        self.sleeping.discard(n)
        self.wake_nodes.pop(n, None)
        self.silenced_nodes.discard(n)
        self.deadlines.discard((0, n, 0))
        self.retention_audit["nodes_deleted"] += 1

    def intervene(self, *, nodes=(), edges=(), lesion=False, action=None):
        action = action or ("delete_nodes" if lesion and nodes else "disconnect_edges" if lesion else "silence")
        touched = set(nodes)
        for key in edges:
            touched.update(key)
            if action in ("disconnect_edges", "delete_nodes", "silence"):
                self._drop_dormant(tuple(key))
        for n in nodes:
            if action in ("disconnect_edges", "delete_nodes", "silence"):
                for key in tuple(self.contacts.get(n, ())):
                    self._drop_dormant(key)
        super().intervene(nodes=nodes, edges=edges, lesion=lesion, action=action)
        for n in touched:
            if n not in self.nodes:
                if n in self.memory_nodes:
                    self.retention_audit["nodes_deleted"] += 1
                for m in (self.memory_nodes, self.isolated, self.fatigue, self.salience, self.wake_nodes):
                    m.pop(n, None)
                self.sleeping.discard(n)
                self.deadlines.discard((0, n, 0))
            elif not self.incident.get(n):
                self.isolated.setdefault(n, self.time_us)
                self._schedule_node(n)

    def settle_parameters(self, new):
        for k in (
            "consolidation_mode",
            "memory_growth_formula",
            "novelty_mode",
            "step_us",
            "seed",
            "energy_initial_reserve",
        ):
            if getattr(new, k) != getattr(self.parameters, k):
                raise ValueError(f"{k} is immutable; choose a new birth")
        if new == self.parameters:
            return
        if self.life == "dead":
            raise ValueError("a dead instance requires an explicit new birth")
        # Explicit configuration intervention, not a runtime maintenance pass.
        for n in self.nodes:
            self._settle_node(n)
        for k in self.edges:
            self._prepare_edge(k)
        for k, row in self.dormant.items():
            q, h = self._edge_value(k, self.time_us)
            row[0].weight, row[1], row[2] = q, h, self.time_us
        for m in (self.fatigue, self.salience):
            for n in m:
                m[n] = [self._local_factor(m, n), self.time_us]
        super().settle_parameters(new)
        self.deadlines = LocalDeadlines()
        for rows in (self.memory_nodes, self.memory_edges):
            for row in rows.values():
                row[0] = min(new.memory_half_life_max_s, max(new.memory_half_life_min_s, row[0]))
        for key in tuple(self.dormant):
            if not new.dormant_traces_enabled or self.dormant[key][0].weight < new.dormant_prune_weight:
                self._drop_dormant(key)
            else:
                self.dormant[key][1] = min(
                    new.memory_half_life_max_s, max(new.memory_half_life_min_s, self.dormant[key][1])
                )
                self._schedule_dormant(key)
        if not new.revival_enabled:
            self.sleeping.clear()
            self.wake_nodes.clear()
            self.wake_edges.clear()
        if not new.strong_fatigue_enabled:
            self.fatigue.clear()
        for n in self.nodes:
            self._schedule_node(n)
        for k in self.edges:
            self._schedule_edge(k)

    def observation_nodes(self):
        rows = super().observation_nodes()
        if self._automatic_node_retention():
            for row in rows:
                row["support"] = self._node_value(row["id"], self.time_us)[0]
        return rows

    def induced_edges(self, node_ids):
        rows = super().induced_edges(node_ids)
        for row in rows:
            row["weight"] = self._edge_value((row["source"], row["target"]), self.time_us)[0]
        return rows

    def graph(self, limit=None):
        value = super().graph(limit)
        for row in value["nodes"]:
            if self._automatic_node_retention():
                row["support"] = self._node_value(row["id"], self.time_us)[0]
        for row in value["edges"]:
            row["weight"] = self._edge_value((row["source"], row["target"]), self.time_us)[0]
        return value

    def metrics(self):
        value = super().metrics()
        value["mean_weight"] = (
            sum(self._edge_value(k, self.time_us)[0] for k in self.edges) / len(self.edges) if self.edges else None
        )
        return value


def definition(config):
    result = previous_definition(config)
    result.update(
        kernel_id=KERNEL_ID,
        state_schema=STATE_SCHEMA,
        hypothesis_id="threemind.hypotheses/continuous-memory3",
        operators=[{"id": name, "phase": phase} for name, phase in MECHANISMS],
    )
    return result


class RetentionEngine(NoveltyEngine):
    dynamics, state_schema = KERNEL_ID, STATE_SCHEMA
    config_type, engine_type = RetentionConfig, RetentionDynamics
    definition = staticmethod(definition)

    def __init__(self, config=None, state=None):
        saved = None
        if state is not None:
            value = state.to_dict()
            if value.get("schema") != self.state_schema:
                raise ValueError("pre-repair memory/3 state cannot silently resume under repaired dynamics")
            if value.get("config", {}).get("revival_enabled") and not value["config"].get("dormant_traces_enabled"):
                raise ValueError("awakening requires dormancy")
            saved = value.get("operator_state", {}).pop("retention", None)
            if saved is None:
                raise ValueError("missing retention state")
            state = StateImage.from_dict(value)
        super().__init__(config, state)
        if saved is not None:
            self._restore_retention(saved)

    def capture_state(self):
        value = super().capture_state().to_dict()
        value["operator_state"]["retention"] = {
            "nodes": [[n, h, str(t)] for n, (h, t) in sorted(self.memory_nodes.items())],
            "edges": [[a, b, h, str(t)] for (a, b), (h, t) in sorted(self.memory_edges.items())],
            "dormant": [[asdict(e), h, str(t)] for _, (e, h, t) in sorted(self.dormant.items())],
            "isolated": [[n, str(t)] for n, t in sorted(self.isolated.items())],
            "fatigue": [[n, v, str(t)] for n, (v, t) in sorted(self.fatigue.items())],
            "salience": [[n, v, str(t)] for n, (v, t) in sorted(self.salience.items())],
            "sleeping": sorted(self.sleeping),
            "deadlines": self.deadlines.rows(),
            "audit": dict(self.retention_audit),
        }
        return StateImage.from_dict(value)

    def _restore_retention(self, saved):
        if set(saved) != {
            "nodes",
            "edges",
            "dormant",
            "isolated",
            "fatigue",
            "salience",
            "sleeping",
            "deadlines",
            "audit",
        }:
            raise ValueError("invalid retention state fields")
        p = self.config

        def time(v):
            t = timestamp(v)
            if t > self.time_us:
                raise ValueError("future retention anchor")
            return t

        def half(h):
            return number(h, "half-life", low=p.memory_half_life_min_s, high=p.memory_half_life_max_s)

        try:
            for n, h, t in saved["nodes"]:
                if (
                    type(n) is not int
                    or n not in self.nodes
                    or n in self.memory_nodes
                    or time(t) < int(self.nodes[n].birth_us)
                ):
                    raise ValueError("invalid node retention state")
                self.memory_nodes[n] = [half(h), time(t)]
            for a, b, h, t in saved["edges"]:
                k = a, b
                if (
                    any(type(n) is not int for n in k)
                    or k not in self.edges
                    or k in self.memory_edges
                    or time(t) < int(self.edges[k].birth_us)
                ):
                    raise ValueError("invalid edge retention state")
                self.memory_edges[k] = [half(h), time(t)]
            if set(self.memory_nodes) != set(self.nodes) or set(self.memory_edges) != set(self.edges):
                raise ValueError("missing retention anchors")
            for row, h, t in saved["dormant"]:
                e = Edge(**row)
                k = e.source, e.target
                if (
                    not p.dormant_traces_enabled
                    or k in self.edges
                    or k in self.dormant
                    or k[0] == k[1]
                    or any(n not in self.nodes for n in k)
                ):
                    raise ValueError("invalid dormant contact")
                number(e.weight, "dormant weight", low=p.dormant_prune_weight, high=1)
                for field in ("stability", "eligibility"):
                    number(getattr(e, field), field, high=1)
                if (
                    type(e.touches) is not int
                    or e.touches < 0
                    or not timestamp(e.birth_us) <= timestamp(e.last_touch_us) <= time(t)
                ):
                    raise ValueError("invalid dormant history")
                self.dormant[k] = [e, half(h), time(t)]
                for n in k:
                    self.contacts.setdefault(n, set()).add(k)
            for n, t in saved["isolated"]:
                if (
                    n not in self.nodes
                    or n in self.isolated
                    or self.incident.get(n)
                    or time(t) < int(self.nodes[n].birth_us)
                ):
                    raise ValueError("invalid isolation clock")
                self.isolated[n] = time(t)
            if set(self.isolated) != {n for n in self.nodes if not self.incident.get(n)}:
                raise ValueError("missing isolation clock")
            for name in ("fatigue", "salience"):
                dest = getattr(self, name)
                for n, v, t in saved[name]:
                    if (
                        type(n) is not int
                        or n not in self.nodes
                        or n in dest
                        or (name == "fatigue" and not p.strong_fatigue_enabled)
                        or time(t) < int(self.nodes[n].birth_us)
                    ):
                        raise ValueError("invalid local fatigue state")
                    dest[n] = [number(v, name, high=1e12), time(t)]
            for n in saved["sleeping"]:
                if n not in self.nodes or n in self.sleeping or not p.dormant_traces_enabled:
                    raise ValueError("invalid sleeping node")
                self.sleeping.add(n)
            for kind, a, b, t in saved["deadlines"]:
                k = kind, a, b
                valid = (
                    (kind == 0 and b == 0 and a in self.nodes)
                    or (kind == 1 and (a, b) in self.edges)
                    or (kind == 2 and (a, b) in self.dormant)
                )
                if (
                    any(type(v) is not int for v in k)
                    or not valid
                    or k in self.deadlines.positions
                    or timestamp(t) <= self.time_us
                    or (timestamp(t) - self.next_propagation_us) % p.propagation_interval_us
                ):
                    raise ValueError("invalid local expiry")
                self.deadlines.set(k, timestamp(t))
            if set(saved["audit"]) != set(AUDIT_KEYS) or any(
                type(v) is not int or v < 0 for v in saved["audit"].values()
            ):
                raise ValueError("invalid retention audit")
            self._engine.retention_audit = dict(saved["audit"])
            # One-time restore validation: omission must not suspend forgetting.
            original = self.deadlines
            self._engine.deadlines = LocalDeadlines()
            try:
                for n in self.nodes:
                    self._engine._schedule_node(n)
                for k in self.edges:
                    self._engine._schedule_edge(k)
                for k in self.dormant:
                    self._engine._schedule_dormant(k)
                expected = {k: t for t, k in self.deadlines.heap}
                actual = {k: t for t, k in original.heap}
                if expected.keys() != actual.keys() or any(
                    abs(expected[k] - actual[k]) > p.propagation_interval_us for k in expected
                ):
                    raise ValueError("missing or inconsistent local expiry")
            finally:
                self._engine.deadlines = original
        except (KeyError, TypeError, OverflowError) as exc:
            raise ValueError("invalid retention state") from exc

    def metrics(self):
        return super().metrics() | {
            "retention": dict(self.retention_audit)
            | {
                "dormant": len(self.dormant),
                "isolated": len(self.isolated),
                "node_half_life_max_s": max((self._node_value(n, self.time_us)[1] for n in self.nodes), default=0.0),
                "half_life_max_s": max((self._edge_value(k, self.time_us)[1] for k in self.edges), default=0.0),
            }
        }
