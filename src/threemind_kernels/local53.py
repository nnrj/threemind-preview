"""/5.3: single-age decay, clock-based pruning and directed shared transport.

This version deliberately changes dynamics. /5.1 and /5.2 remain executable
under their own identities. Inherited reception, novelty and resource rules
are retained; the explicit overrides below implement the approved changes.
"""

from __future__ import annotations

import copy
import hashlib
import heapq
import math
from dataclasses import asdict, dataclass

from threemind_core import Stimulus
from threemind_core.energy import Energy, supply_payload
from threemind_core.engine import canonical_bytes
from threemind_core.spec import timestamp

from .decay53 import CURVES, decay_value
from .local import word
from .local5 import Local5Node, Local5Edge
from .local51 import Local51Config, Local51Engine, MECHANISMS as PREVIOUS
from .mechanisms import FastTrace, ShortTermState, number
from .retention import grow

KERNEL_ID = "threemind.continuous-memory/5.3"
STATE_SCHEMA = "threemind.continuous-memory-state/5.3"
HYPOTHESIS_ID = "threemind.hypotheses/continuous-memory53"
MECHANISMS = tuple(x for x in PREVIOUS if x[0] != "threemind.adaptive-half-life/2") + (
    ("threemind.single-age-decay/1", "local-settlement"),
    ("threemind.clock-structure-check/1", "after-same-time-emissions"),
    ("threemind.directed-shared-transport/1", "node-offer-edge-transmission"),
)


@dataclass(frozen=True, slots=True)
class Local53Config(Local51Config):
    decay_curve: str = "inverse-logarithmic"
    decay_transition_age: float = 10.0
    reinforcement_age_policy: str = "keep"
    retention_growth_enabled: bool = False
    retention_relaxation_enabled: bool = False
    structure_check_interval_us: int = 100_000
    signal_threshold_enabled: bool = True
    signal_threshold: float = 0.0004
    weight_gate_enabled: bool = False
    weight_gate: float = 0.008
    inhibitory_learning_enabled: bool = True
    # Historical field retained only as an explicitly enabled sender control.
    inhibition_sender_gate_enabled: bool = False

    def __post_init__(self):
        Local51Config.__post_init__(self)
        if self.decay_curve not in CURVES or self.reinforcement_age_policy not in ("keep", "reset"):
            raise ValueError("unknown decay curve or reinforcement age policy")
        if self.consolidation_mode != "adaptive-half-life" or self.node_retention_mode != "automatic":
            raise ValueError("/5.3 uses single-age persistent decay for both connections and nodes")
        for name in (
            "retention_growth_enabled",
            "retention_relaxation_enabled",
            "signal_threshold_enabled",
            "weight_gate_enabled",
            "inhibitory_learning_enabled",
            "inhibition_sender_gate_enabled",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        for name in ("signal_threshold", "weight_gate", "decay_transition_age"):
            object.__setattr__(self, name, number(getattr(self, name), name, high=1e12))
        if self.decay_transition_age <= 0 or self.weight_gate > 1:
            raise ValueError("invalid transition age or weight gate")
        if self.weight_gate_enabled and self.weight_gate < self.prune_weight:
            raise ValueError("weight gate must be at least the deletion threshold")
        if type(self.structure_check_interval_us) is not int or not 1 <= self.structure_check_interval_us < 2**53:
            raise ValueError("structure check interval must be a positive safe integer")


def _assign_value(row, name, value):
    # Only a positive, actually accepted reinforcement resets age. Projection
    # bypasses this setter. This derived policy flag is restored from config.
    if name in ("support", "weight") and getattr(row, "_reset_age", False):
        old = getattr(row, name, None)
        if old is not None and value > old:
            object.__setattr__(row, "decay_age", 0.0)
    object.__setattr__(row, name, value)


@dataclass
class Local53Node(Local5Node):
    decay_age: float = 0.0
    __setattr__ = _assign_value


@dataclass
class Local53Edge(Local5Edge):
    decay_age: float = 0.0
    __setattr__ = _assign_value


def definition(config):
    return {
        "schema": "threemind.kernel-definition/1",
        "kernel_id": KERNEL_ID,
        "state_schema": STATE_SCHEMA,
        "hypothesis_id": HYPOTHESIS_ID,
        "operators": [{"id": k, "phase": p} for k, p in MECHANISMS],
        "config": config.to_dict(),
    }


class Local53Engine(Local51Engine):
    dynamics = KERNEL_ID
    state_schema = STATE_SCHEMA
    config_type = Local53Config
    definition = staticmethod(definition)

    def __init__(self, config=None, state=None):
        super().__init__(config, state)
        if state is None:
            self.transport.update(
                dict.fromkeys(
                    (
                        "offered_excitation",
                        "offered_inhibition",
                        "transmitted_excitation",
                        "transmitted_inhibition",
                        "received_inhibition",
                        "blocked_weight",
                        "blocked_signal",
                        "blocked_dormancy",
                        "blocked_energy",
                    ),
                    0.0,
                )
            )

    def node_type(self, *args, **kwargs):
        row = Local53Node(*args, **kwargs)
        row._reset_age = self.config.reinforcement_age_policy == "reset"
        return row

    def edge_type(self, *args, **kwargs):
        row = Local53Edge(*args, **kwargs)
        row._reset_age = self.config.reinforcement_age_policy == "reset"
        return row

    def _decay_value(self, row, field, seconds):
        value, age, h = decay_value(getattr(row, field), row.decay_age, row.half_life, seconds, self.config)
        object.__setattr__(row, field, value)
        row.decay_age, row.half_life = age, h

    def _structure_timer(self):
        if self.nodes and self.config.plasticity:
            interval = self.config.structure_check_interval_us
            # Never move an already-due check behind a same-time input.
            key = (6, 0, 0)
            if key not in self.timers.positions:
                self.timers.set(key, (self.time_us // interval + 1) * interval)
        else:
            self.timers.discard((6, 0, 0))

    def _node_timers(self, n):
        c = self.config
        if n.activation > c.activation_floor and c.activation_decay_enabled and c.activation_floor > 0:
            self.timers.set((1, n.id, 0), self._delay(c.activation_tau * math.log(n.activation / c.activation_floor)))
        else:
            self.timers.discard((1, n.id, 0))
        self._structure_timer()

    def _edge_timer(self, e):
        self._structure_timer()
        if e.novelty_deadline_us is not None:
            self.timers.set((4, e.source, e.target), int(e.novelty_deadline_us))

    def _expiry(self, kind, a, b):
        if kind == 6:
            self.audit["scan_visits"] += len(self.edges) + len(self.nodes)
            # Same-time inputs, novelty, and emissions have already run.
            for key in sorted(self.edges):
                e = self._settle_edge(key)
                floor = self.config.dormant_prune_weight if e.sleeping else self.config.prune_weight
                if e.weight < floor:
                    self._remove_edge(key)
            for id in sorted(self.nodes):
                super()._expiry(3, id, 0)
            self._structure_timer()
        elif kind == 4:
            # Novelty changes a weight; removal still waits for the clock check.
            self.audit["expiry_checks"] += 1
            key = a, b
            if key not in self.edges:
                return
            e, c = self._settle_edge(key), self.config
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
            self._drop_novelty_index(key)
        else:
            super()._expiry(kind, a, b)

    def reconfigure(self, config):
        if type(config) is not self.config_type or any(
            getattr(config, k) != getattr(self.config, k)
            for k in ("decay_curve", "decay_transition_age", "reinforcement_age_policy", "structure_check_interval_us")
        ):
            raise ValueError("decay law, age policy and structure clock are fixed at birth")
        super().reconfigure(config)

    def _emit(self, id):
        if id not in self.nodes or id in self.silenced_nodes:
            return
        c, n = self.config, self._settle_node(id)
        self._maintenance(n)
        if c.inhibition:
            n.inhibition = self._soft(n.inhibition + n.pending_inhibition)
        n.pending_inhibition = 0.0
        features = self._features(n)
        positive = n.activation * self._response(n) * c.propagation_rate * c.propagation_interval_us / 1e6
        if n.activation < c.propagation_activation_min:
            positive = 0.0
        if c.inhibition:
            n.inhibition = self._soft(n.inhibition + n.generated_inhibition)
        n.generated_inhibition = 0.0
        negative = (
            n.inhibition * min(1.0, c.inhibition_diffusion_rate * c.propagation_interval_us / 1e6)
            if c.inhibition
            else 0.0
        )
        if c.inhibition_sender_gate_enabled and negative < c.inhibition_propagation_min:
            negative = 0.0
        keys = sorted(k for k in self.outgoing.get(id, ()) if k not in self.silenced_edges)
        self.transport["offered_excitation"] += len(keys) * positive
        self.transport["offered_inhibition"] += len(keys) * negative
        # The node pays for its offers, including sleeping/weak connections.
        p_cost = len(keys) * positive * c.energy_associative_cost
        i_cost = len(keys) * negative * c.energy_inhibition_cost
        requested = p_cost + i_cost
        scale = 1.0
        if c.energy_simulation_enabled and requested > 0:
            available = self.energy.reserve if c.energy_model == "global-ledger" else n.reserve
            scale = min(1.0, available / requested)
            self._expense(n, len(keys) * positive * scale, c.energy_associative_cost, "associative")
            self._expense(n, len(keys) * negative * scale, c.energy_inhibition_cost, "inhibition")
            self.energy._add("unserved_total", requested * (1.0 - scale))
        self.transport["blocked_energy"] += len(keys) * (positive + negative) * (1.0 - scale)
        positive *= scale
        negative *= scale
        messages = []
        for key in keys:
            e = self._settle_edge(key)
            if positive <= 0 and negative <= 0:
                continue
            if e.sleeping:
                self.transport["blocked_dormancy"] += positive + negative
                continue
            fast = (
                FastTrace(**(e.fast | {"time_us": int(e.fast["time_us"])}))
                if e.fast
                else FastTrace(time_us=int(e.birth_us))
            )
            fast_value = fast.projected(self.time_us, c.fast_trace()) if c.fast_enabled else 0.0
            weight = min(1.0, e.weight + c.fast_trace().gain * fast_value) if c.fast_enabled else e.weight
            fraction = 1.0
            if c.stp_enabled:
                sc = c.short_term()
                st = (
                    ShortTermState(**(e.short_term | {"time_us": int(e.short_term["time_us"])}))
                    if e.short_term
                    else ShortTermState(time_us=int(e.birth_us))
                )
                if not c.depletion_enabled:
                    st = st.recovered(self.time_us, sc)
                    st = ShortTermState(1.0, 0.0, st.utilization, self.time_us)
                st, fraction = st.release(self.time_us, sc)
                if not c.depletion_enabled:
                    st = ShortTermState(1.0, 0.0, st.utilization, self.time_us)
                e.short_term = asdict(st) | {"time_us": str(st.time_us)}
            distance = 1.0
            if c.spatial_embedding and c.neighborhood_enabled:
                from threemind_core.spatial import position

                pa, pb = (
                    position(c.seed, e.source, c.spatial_dimensions),
                    position(c.seed, e.target, c.spatial_dimensions),
                )
                distance = math.exp(-math.sqrt(sum((a - b) ** 2 for a, b in zip(pa, pb))) / c.spatial_radius)
            transmitted = []
            for signal in (positive, negative):
                amount = weight * signal * fraction * distance
                self.transport["sent"] += amount
                reason = (
                    "blocked_weight"
                    if c.weight_gate_enabled and e.weight < c.weight_gate
                    else ("blocked_signal" if c.signal_threshold_enabled and amount < c.signal_threshold else None)
                )
                if reason:
                    self.transport[reason] += amount
                    self.transport["discarded"] += amount
                    amount = 0.0
                transmitted.append(amount)
            pos, neg = transmitted
            self.transport["transmitted_excitation"] += pos
            self.transport["transmitted_inhibition"] += neg
            if pos > 0:
                messages.append([id, e.target, pos, features])
            if neg > 0:
                self._emission_inhibitors[e.target] = self._emission_inhibitors.get(e.target, 0.0) + neg
            if pos > 0 or neg > 0:
                e.last_pass_us = str(self.time_us)
            learned = pos + (neg if c.inhibitory_learning_enabled else 0.0)
            if c.plasticity and learned > 0:
                if c.fast_enabled:
                    fast_value += -math.expm1(-c.fast_trace().learning_rate * learned) * (1.0 - fast_value)
                    e.fast = asdict(FastTrace(fast_value, self.time_us)) | {"time_us": str(self.time_us)}
                e.eligibility = min(1.0, 0.7 * e.eligibility + learned)
                if c.edge_consolidation_enabled:
                    e.weight = min(1.0, e.weight + c.associative_gain * learned)
                    e.stability = min(1.0, e.stability + c.stability_gain * learned)
                    if c.retention_growth_enabled:
                        e.half_life = grow(e.half_life, learned * 0.1, c)
                e.touches += 1
                e.last_touch_us = str(self.time_us)
                self._edge_timer(e)
        if messages:
            self._event(self.time_us + c.delay_us, "signal", {"messages": messages})
        # Inhibition is a node emission budget; fan-out and failed delivery do
        # not feed back from the connection into the node's generation rule.
        if keys:
            n.inhibition = max(0.0, n.inhibition - negative)
        if c.revival_enabled and positive > 0:
            for key in sorted(self.incident.get(id, ())):
                if self.edges[key].sleeping and key not in self.silenced_edges:
                    self._event(self.time_us + c.delay_us, "wake", {"edge": list(key), "sender": id, "value": positive})
        n.last_emit_us = str(self.time_us)
        n.direct = n.associative = 0.0
        self._node_timers(n)
        self._pulse(n, after=True)

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
                self._decay_value(n, "support", dt)
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

    def _project_edge(self, edge, when):
        # Same operation order as /5; only exp(-period / tau) is cached.
        # Identity comparison also invalidates it after explicit reconfigure
        # and restoration. The cache is derived and is never serialized.
        e, c = copy.copy(edge), self.config
        dt = (when - int(e.state_us)) / 1e6
        if c.consolidation_mode == "adaptive-half-life":
            if dt and c.plasticity:
                self._decay_value(e, "weight", dt)
            period = c.propagation_interval_us
            before = self._before_emission and when == self.time_us
            complete = max(0, (when - int(before)) // period * period)
            count = (complete - int(e.completed_period_us)) // period
            if count > 0 and c.plasticity:
                seconds = period / 1e6
                if self._eligibility_config is not c:
                    self._eligibility_period_retention = (
                        math.exp(-seconds / c.eligibility_tau) if c.eligibility_decay_enabled else 1.0
                    )
                    self._eligibility_config = c
                ratio = self._eligibility_period_retention
                retained = ratio**count
                total = e.eligibility * (count if ratio == 1.0 else ratio * (1 - retained) / (1 - ratio))
                if c.stability_decay_enabled:
                    e.stability = max(0.0, e.stability - seconds / c.stability_tau * (count - total))
                if c.eligibility_decay_enabled:
                    e.eligibility *= retained
            e.completed_period_us = str(complete)
        elif not c.plasticity:
            period = c.propagation_interval_us
            before = self._before_emission and when == self.time_us
            e.completed_period_us = str(max(0, (when - int(before)) // period * period))
        e.state_us = str(when)
        return e

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
                if c.retention_growth_enabled:
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

    def _pulse(self, n, *, after=False):
        c = self.config
        if (
            n.sleeping
            or n.id in self.silenced_nodes
            or not (n.activation > 0 or (c.inhibition and n.inhibition > 0) or n.pending_inhibition > 0)
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

    def _restore(self, doc):
        if "completed_emission_us" not in doc:
            raise ValueError("missing /5.3 emission phase")
        self.completed_emission_us = timestamp(doc["completed_emission_us"])
        for group in ("nodes", "edges"):
            for row in doc.get(group, ()):
                if "decay_age" not in row or ("last_emit_us" if group == "nodes" else "completed_period_us") not in row:
                    raise ValueError("missing /5.3 age or phase")
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
                kind not in (0, 1, 4, 5, 6)
                or (kind == 6 and (a, b) != (0, 0))
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
        } or set(self.transport) != {
            "sent",
            "received",
            "activated",
            "discarded",
            "offered_excitation",
            "offered_inhibition",
            "transmitted_excitation",
            "transmitted_inhibition",
            "received_inhibition",
            "blocked_weight",
            "blocked_signal",
            "blocked_dormancy",
            "blocked_energy",
        }:
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
                and (n.activation > 0 or (c.inhibition and n.inhibition > 0) or n.pending_inhibition > 0)
                and (0, n.id, 0) not in self.timers.positions
            ):
                raise ValueError("missing node emission deadline")
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

        period = c.propagation_interval_us
        if self.completed_emission_us != self.time_us // period * period:
            raise ValueError("invalid 5.3 completed emission phase")
        for n in self.nodes.values():
            if timestamp(n.last_emit_us) > self.time_us:
                raise ValueError("invalid source emission clock")
        for e in self.edges.values():
            if timestamp(e.completed_period_us) > self.time_us or int(e.completed_period_us) % period:
                raise ValueError("invalid completed-period anchor")
        for rows in (self.nodes.values(), self.edges.values()):
            for row in rows:
                number(row.decay_age, "decay age", high=1.7976931348623157e308)
                if row.decay_age > (int(row.state_us) - int(row.birth_us)) * 1.000001:
                    raise ValueError("decay age exceeds elapsed time at minimum legal scale")
        key = (6, 0, 0)
        if self.nodes and c.plasticity and key not in self.timers.positions:
            raise ValueError("missing structure clock")
        if key in self.timers.positions:
            due = self.timers.heap[self.timers.positions[key]][0]
            expected = (self.time_us // c.structure_check_interval_us + 1) * c.structure_check_interval_us
            if due != expected:
                raise ValueError("invalid structure clock phase")

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
                            self.transport["received_inhibition"] += value
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
