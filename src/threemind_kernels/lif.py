"""Independent adaptive LIF candidate. No baseline equations are replaced.

Physical rows are owned by this kernel. Legacy-shaped graph rows are explicitly
marked observation projections, not membrane recovery state.
"""

from __future__ import annotations

import copy
import hashlib
import heapq
import math
from dataclasses import asdict, dataclass, replace

from threemind_core import StateImage, Stimulus
from threemind_core.engine import Edge, Node, canonical_bytes
from threemind_core.spec import timestamp

from .mechanisms import ShortTermConfig, ShortTermState, cascade, number

KERNEL_ID = "threemind.lif/1"
STATE_SCHEMA = "threemind.lif-state/1"
MECHANISMS = (
    ("threemind.adaptive-rc/1", "passive-evolution"),
    ("threemind.co-input-growth/1", "external-contact"),
    ("threemind.lif-threshold-reset/1", "fixed-grid"),
    ("threemind.arrival-pair-stdp/1", "arrival-and-spike"),
    ("threemind.tm-synapse/1", "before-spike-emission"),
    ("threemind.physical-activity-life/1", "after-arrivals-and-spikes"),
)


@dataclass(frozen=True, slots=True)
class LifConfig:
    step_us: int = 250
    delay_us: int = 1000
    refractory_us: int = 2000
    quiescence_death_us: int = 1_000_000
    seed: int = 20260724
    plasticity: bool = True
    inhibition: bool = True
    leak_enabled: bool = True
    current_decay_enabled: bool = True
    rest_mv: float = -65.0
    reset_mv: float = -65.0
    threshold_mv: float = -50.0
    resistance_mohm: float = 100.0
    membrane_tau_s: float = 0.02
    current_tau_s: float = 0.005
    adaptation_tau_s: float = 0.1
    adaptation_jump_na: float = 0.01
    input_gain_na: float = 1.0
    spike_gain_na: float = 0.3
    voltage_epsilon_mv: float = 0.000001
    current_epsilon_na: float = 0.00000001
    birth_weight: float = 0.05
    stdp_enabled: bool = True
    stdp_tau_pre_s: float = 0.02
    stdp_tau_post_s: float = 0.02
    stdp_a_plus: float = 0.01
    stdp_a_minus: float = 0.0105
    stp_enabled: bool = True
    stp_utilization: float = 0.5
    stp_recovery_tau_s: float = 0.8
    stp_active_tau_s: float = 0.003
    stp_facilitation_tau_s: float = 0.0
    max_nodes: int = 10000
    max_edges: int = 200000

    def __post_init__(self):
        for key, value in asdict(self).items():
            expected = type(type(self).__dataclass_fields__[key].default)
            if expected is bool:
                if type(value) is not bool:
                    raise ValueError(f"{key} must be boolean")
            elif expected is int:
                if key.endswith("_us"):
                    object.__setattr__(self, key, timestamp(value))
                    if getattr(self, key) > 2**53 - 1:
                        raise ValueError(f"{key} exceeds exactly representable configuration range")
                elif type(value) is not int or not 0 <= value <= 2**32 - 1:
                    raise ValueError(f"invalid integer {key}")
            else:
                object.__setattr__(
                    self, key, float(number(value, key, low=-1000 if key.endswith("_mv") else 0, high=1e6))
                )
        if not 1 <= self.step_us <= 1_000_000 or not 1 <= self.delay_us <= 10_000_000:
            raise ValueError("LIF step or delay outside supported microsecond range")
        if not self.rest_mv <= self.reset_mv < self.threshold_mv or self.threshold_mv - self.rest_mv < 0.0001:
            raise ValueError("require rest <= reset < threshold and a positive voltage range")
        for key in (
            "resistance_mohm",
            "membrane_tau_s",
            "current_tau_s",
            "adaptation_tau_s",
            "stdp_tau_pre_s",
            "stdp_tau_post_s",
            "stp_recovery_tau_s",
            "stp_active_tau_s",
        ):
            if getattr(self, key) <= 0:
                raise ValueError(f"{key} must be positive")
        for key in ("birth_weight", "stdp_a_plus", "stdp_a_minus", "stp_utilization"):
            number(getattr(self, key), key, high=1.0)
        if not 0 <= self.voltage_epsilon_mv < self.threshold_mv - self.rest_mv:
            raise ValueError("voltage epsilon must be below threshold range")
        self.short_term()

    @property
    def energy_simulation_enabled(self):
        # This candidate has physical currents, not the causal kernel's energy ledger.
        return False

    def short_term(self):
        return ShortTermConfig(
            self.stp_utilization, self.stp_recovery_tau_s, self.stp_active_tau_s, self.stp_facilitation_tau_s
        )

    def to_dict(self):
        return {key: str(value) if key.endswith("_us") else value for key, value in asdict(self).items()}


@dataclass
class Membrane:
    id: int
    channel: int
    voltage_mv: float
    current_na: float = 0.0
    adaptation_na: float = 0.0
    refractory_until_us: int = 0
    last_spike_us: int | None = None
    spikes: int = 0
    touches: int = 0
    birth_us: int = 0
    last_touch_us: int = 0


@dataclass
class Synapse:
    id: int
    source: int
    target: int
    weight: float
    pre: float = 0.0
    post: float = 0.0
    trace_time_us: int = 0
    birth_us: int = 0
    last_touch_us: int = 0
    touches: int = 0


def definition(config):
    return {
        "schema": "threemind.kernel-definition/1",
        "kernel_id": KERNEL_ID,
        "state_schema": STATE_SCHEMA,
        "hypothesis_id": "threemind.hypotheses/lif1",
        "operators": [{"id": name, "phase": phase} for name, phase in MECHANISMS],
        "config": config.to_dict(),
    }


def document_hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def stored(row):
    return {
        key: str(value) if key.endswith("_us") and value is not None else value for key, value in asdict(row).items()
    }


class LifEngine:
    dynamics = KERNEL_ID

    def __init__(self, config: LifConfig | None = None, state: StateImage | None = None):
        if config is not None and type(config) is not LifConfig:
            raise ValueError("LIF requires LifConfig")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        self.config = config or LifConfig()
        self.time_us = self.state_time_us = self.sequence = self.next_event = 0
        self.next_node = self.next_synapse = 1
        self.next_step_us = self.config.step_us
        self.life, self.sources_open, self.quiet_since_us = "waiting", True, None
        self.nodes, self.edges, self.channels = {}, {}, {}
        self.outgoing, self.incoming, self.short_term = {}, {}, {}
        self.active, self.silenced_nodes, self.silenced_edges = set(), set(), set()
        self.queue = []
        self.transport = {"sent_na": 0.0, "received_na": 0.0, "unavailable_na": 0.0}
        self.rejected = {"nodes": 0, "edges": 0}
        if state is not None:
            try:
                self._restore(state)
            except (KeyError, TypeError, OverflowError) as exc:
                raise ValueError("malformed LIF recovery state") from exc

    def _event(self, when, kind, payload):
        timestamp(when)
        event_id = self.next_event
        self.next_event += 1
        heapq.heappush(self.queue, (when, event_id, kind, payload))
        return event_id

    def inject(self, stimulus):
        stimulus = Stimulus.from_dict(stimulus.to_dict())
        if self.life == "dead" or not self.sources_open:
            raise ValueError("inputs are closed or this consciousness is dead")
        if stimulus.time_us < self.time_us:
            raise ValueError("cannot schedule an input in the past")
        return self._event(stimulus.time_us, "stimulus", stimulus.to_dict())

    def close_inputs(self):
        if self.sources_open:
            self.sources_open = False
            self.sequence += 1

    def supply_energy(self, *args, **kwargs):
        raise ValueError("LIF does not implement the causal energy port; currents are not an energy ledger")

    def modulate_input(self, *args, **kwargs):
        raise ValueError("LIF does not implement causal input-attention modulation")

    def _present(self, node):
        c = self.config
        return (
            abs(node.voltage_mv - c.rest_mv) > 0
            and abs(node.voltage_mv - c.rest_mv) >= c.voltage_epsilon_mv
            or node.current_na > 0
            and node.current_na >= c.current_epsilon_na
            or node.adaptation_na > 0
            and node.adaptation_na >= c.current_epsilon_na
        )

    def _project(self, node, when):
        c = self.config
        result = replace(node)
        start = self.state_time_us
        if when <= start:
            return result
        # Refractory clamp consumes time but does not erase arriving currents.
        held = min(when, max(start, node.refractory_until_us)) - start
        if held:
            seconds = held / 1e6
            result.voltage_mv = c.reset_mv
            if c.current_decay_enabled:
                result.current_na *= math.exp(-seconds / c.current_tau_s)
            result.adaptation_na *= math.exp(-seconds / c.adaptation_tau_s)
            start += held
        dt = (when - start) / 1e6
        if dt:

            def coupling(tau, decays=True):
                if not c.leak_enabled:
                    return tau / c.membrane_tau_s * -math.expm1(-dt / tau) if decays else dt / c.membrane_tau_s
                return cascade(dt, tau, c.membrane_tau_s) if decays else -math.expm1(-dt / c.membrane_tau_s)

            voltage = c.rest_mv + (result.voltage_mv - c.rest_mv) * (
                math.exp(-dt / c.membrane_tau_s) if c.leak_enabled else 1.0
            )
            voltage += c.resistance_mohm * result.current_na * coupling(c.current_tau_s, c.current_decay_enabled)
            if c.inhibition:
                voltage -= c.resistance_mohm * result.adaptation_na * coupling(c.adaptation_tau_s)
            result.voltage_mv = voltage
            if c.current_decay_enabled:
                result.current_na *= math.exp(-dt / c.current_tau_s)
            result.adaptation_na *= math.exp(-dt / c.adaptation_tau_s)
        if not c.inhibition:
            result.adaptation_na = 0.0
        if not all(math.isfinite(v) for v in (result.voltage_mv, result.current_na, result.adaptation_na)):
            raise ValueError("nonfinite membrane state; reduce input or physical gain")
        return result

    def _relax(self, when):
        for identity in sorted(self.active):
            self.nodes[identity] = self._project(self.nodes[identity], when)
        self.state_time_us = when

    def _current(self, identity, amount):
        self.transport["received_na"] += amount
        if identity not in self.nodes or identity in self.silenced_nodes:
            self.transport["unavailable_na"] += amount
            return
        if amount <= 0:
            return
        node = self.nodes[identity]
        node.current_na += amount
        if not math.isfinite(node.current_na):
            raise ValueError("nonfinite membrane current; experiment requires a bounded input protocol")
        node.touches += 1
        node.last_touch_us = self.state_time_us
        self.active.add(identity)

    def _grow(self, contacts):
        c = self.config
        if not c.plasticity or c.birth_weight == 0:
            return
        for source, a in contacts:
            for target, b in contacts:
                key = source, target
                if source == target or key in self.edges:
                    continue
                if len(self.edges) >= c.max_edges:
                    self.rejected["edges"] += 1
                    continue
                self.edges[key] = Synapse(
                    self.next_synapse,
                    source,
                    target,
                    c.birth_weight * a * b,
                    trace_time_us=self.state_time_us,
                    birth_us=self.state_time_us,
                    last_touch_us=self.state_time_us,
                )
                self.next_synapse += 1
                self.outgoing.setdefault(source, set()).add(target)
                self.incoming.setdefault(target, set()).add(source)

    def _stdp_relax(self, edge):
        dt = (self.state_time_us - edge.trace_time_us) / 1e6
        edge.pre *= math.exp(-dt / self.config.stdp_tau_pre_s)
        edge.post *= math.exp(-dt / self.config.stdp_tau_post_s)
        edge.trace_time_us = self.state_time_us

    def _input(self, payload):
        stimulus = Stimulus.from_dict(payload)
        contacts = []
        for channel, amplitude in stimulus.channels:
            amount = amplitude * stimulus.intensity * self.config.input_gain_na
            if amount <= 0:
                continue
            identity = self.channels.get(channel)
            if identity is None:
                if len(self.nodes) >= self.config.max_nodes:
                    self.rejected["nodes"] += 1
                    continue
                identity = self.next_node
                self.next_node += 1
                self.nodes[identity] = Membrane(
                    identity,
                    channel,
                    self.config.rest_mv,
                    birth_us=self.state_time_us,
                    last_touch_us=self.state_time_us,
                )
                self.channels[channel] = identity
            self._current(identity, amount)
            if identity not in self.silenced_nodes:
                contacts.append((identity, min(1.0, amplitude * stimulus.intensity)))
        self._grow(contacts)

    def _arrival(self, payload):
        for source, target, synapse_id, amount in payload["messages"]:
            self._current(target, amount)
            edge = self.edges.get((source, target))
            if (
                edge is None
                or edge.id != synapse_id
                or target in self.silenced_nodes
                or not self.config.plasticity
                or not self.config.stdp_enabled
            ):
                continue
            self._stdp_relax(edge)
            edge.weight = max(0.0, edge.weight - self.config.stdp_a_minus * edge.post)
            edge.pre += 1.0
            edge.touches += 1
            edge.last_touch_us = self.state_time_us

    def _spikes(self):
        c, now = self.config, self.state_time_us
        firing = [
            n
            for n in sorted(self.active)
            if n not in self.silenced_nodes
            and self.nodes[n].refractory_until_us <= now
            and self.nodes[n].voltage_mv >= c.threshold_mv
        ]
        messages = []
        for identity in firing:
            node = self.nodes[identity]
            node.spikes += 1
            node.last_spike_us = now
            node.voltage_mv = c.reset_mv
            node.refractory_until_us = timestamp(now + c.refractory_us)
            if c.inhibition:
                node.adaptation_na += c.adaptation_jump_na
            for source in sorted(self.incoming.get(identity, ())):
                if (source, identity) in self.silenced_edges or not c.plasticity or not c.stdp_enabled:
                    continue
                edge = self.edges[source, identity]
                self._stdp_relax(edge)
                edge.weight = min(1.0, edge.weight + c.stdp_a_plus * edge.pre)
                edge.post += 1.0
                edge.touches += 1
                edge.last_touch_us = now
        # All postsynaptic updates finish before emissions: same-time node order is not a teaching signal.
        for identity in firing:
            for target in sorted(self.outgoing.get(identity, ())):
                key = identity, target
                if key in self.silenced_edges:
                    continue
                edge = self.edges[key]
                amount = edge.weight * c.spike_gain_na
                if amount <= 0:
                    continue
                if c.stp_enabled:
                    resource = self.short_term.get(key, ShortTermState(time_us=edge.birth_us))
                    self.short_term[key], fraction = resource.release(now, c.short_term())
                    amount *= fraction
                if amount > 0:
                    messages.append([identity, target, edge.id, amount])
                    self.transport["sent_na"] += amount
        if messages:
            self._event(now + c.delay_us, "spike_arrival", {"messages": messages})
        return firing

    def _life(self):
        c, now = self.config, self.state_time_us
        live = set()
        for identity in self.active:
            node = self.nodes[identity]
            if self._present(node):
                live.add(identity)
            else:
                node.voltage_mv, node.current_na, node.adaptation_na = c.rest_mv, 0.0, 0.0
        self.active = live
        if live:
            self.life, self.quiet_since_us = "alive", None
        elif self.life == "alive":
            if self.quiet_since_us is None:
                self.quiet_since_us = now
            if now - self.quiet_since_us >= c.quiescence_death_us:
                self.life = "dead"

    def advance_to(self, target_us, observer=None, *, inputs_only=False, record_spikes=False):
        target = timestamp(target_us)
        if target < self.time_us:
            raise ValueError("time cannot go backwards")
        if self.life == "dead":
            return
        while True:
            candidates = []
            if self.queue:
                candidates.append(self.queue[0][0])
            if self.active:
                candidates.append(self.next_step_us)
            if self.quiet_since_us is not None:
                candidates.append(self.quiet_since_us + self.config.quiescence_death_us)
            if not candidates or min(candidates) > target:
                break
            now = min(candidates)
            self._relax(now)
            self.time_us = now
            while self.queue and self.queue[0][0] == now:
                _, event_id, kind, payload = heapq.heappop(self.queue)
                if kind == "stimulus":
                    self._input(payload)
                else:
                    self._arrival(payload)
                self.sequence += 1
                if observer is not None and (not inputs_only or kind == "stimulus"):
                    observer(
                        {
                            "kind": kind,
                            "event_id": event_id,
                            "time_us": str(now),
                            "sequence": self.sequence,
                            "payload": copy.deepcopy(payload),
                        }
                    )
            # Threshold testing occurs only on the fixed simulation lattice.
            if now % self.config.step_us == 0:
                firing = self._spikes()
                self.sequence += 1
                if observer is not None and (not inputs_only or record_spikes) and firing:
                    observer(
                        {"kind": "spikes", "time_us": str(now), "sequence": self.sequence, "payload": {"nodes": firing}}
                    )
            self.next_step_us = timestamp((now // self.config.step_us + 1) * self.config.step_us)
            self._life()
            if self.life == "dead":
                return
        self.time_us = target

    def _node_rows(self, when):
        c = self.config
        result = []
        for identity in sorted(self.nodes):
            physical = self._project(self.nodes[identity], when)
            # Derived transport-compatible display scalar; raw voltage/current remain available.
            activation = min(1.0, max(0.0, (physical.voltage_mv - c.rest_mv) / (c.threshold_mv - c.rest_mv)))
            result.append(
                asdict(
                    Node(
                        identity,
                        physical.channel,
                        activation=activation,
                        inhibition=physical.adaptation_na,
                        touches=physical.touches,
                        last_touch_us=str(physical.last_touch_us),
                        birth_us=str(physical.birth_us),
                    )
                )
            )
        return result

    def observation_nodes(self):
        return self._node_rows(self.time_us)

    def physical_nodes(self):
        return [stored(self._project(self.nodes[n], self.time_us)) for n in sorted(self.nodes)]

    def activations(self):
        return [(n["id"], n["activation"]) for n in self.observation_nodes()]

    def induced_edges(self, node_ids):
        selected = set(node_ids)
        return [
            asdict(
                Edge(
                    e.source,
                    e.target,
                    e.weight,
                    touches=e.touches,
                    birth_us=str(e.birth_us),
                    last_touch_us=str(e.last_touch_us),
                )
            )
            for _, e in sorted(self.edges.items())
            if e.source in selected and e.target in selected
        ]

    def graph(self, limit=None):
        nodes = self.observation_nodes()
        if limit is not None:
            nodes = sorted(nodes, key=lambda n: (-n["activation"], n["id"]))[:limit]
        return {
            "nodes": nodes,
            "edges": self.induced_edges(n["id"] for n in nodes),
            "time_us": str(self.time_us),
            "sequence": self.sequence,
            "life": self.life,
            "kernel_id": KERNEL_ID,
            "observation_quantity": "normalized-depolarization",
            "physical_nodes": self.physical_nodes()
            if limit is None
            else [n for n in self.physical_nodes() if n["id"] in {v["id"] for v in nodes}],
        }

    def metrics(self):
        physical = self.physical_nodes()
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "life": self.life,
            "time_us": str(self.time_us),
            "sequence": self.sequence,
            "activation": sum(v for _, v in self.activations()),
            "kernel_id": KERNEL_ID,
            "state_schema": STATE_SCHEMA,
            "observation_quantity": "normalized-depolarization",
            "spikes": sum(n["spikes"] for n in physical),
            "active_membranes": sum(self._present(self._project(n, self.time_us)) for n in self.nodes.values()),
            "transport": dict(self.transport),
            "capacity_rejections": dict(self.rejected),
        }

    def spatial_geometry(self):
        raise ValueError("LIF has no causal spatial embedding; display layout is not physical projection")

    def _remove_edge(self, key):
        if key not in self.edges:
            return
        del self.edges[key]
        self.short_term.pop(key, None)
        self.silenced_edges.discard(key)
        self.outgoing[key[0]].discard(key[1])
        self.incoming[key[1]].discard(key[0])

    def intervene(self, *, nodes=(), edges=(), lesion=False, action=None):
        if self.life == "dead":
            raise ValueError("a dead consciousness cannot be changed")
        if action is not None and lesion:
            raise ValueError("use action or lesion, not both")
        action = action or ("delete_nodes" if lesion else "silence")
        selected, links = set(nodes), {tuple(e) for e in edges}
        if not selected <= self.nodes.keys() or not links <= self.edges.keys():
            raise ValueError("damage requires existing node and edge identities")
        if (
            action not in ("delete_nodes", "disconnect_edges", "silence", "unsilence")
            or action == "disconnect_edges"
            and selected
        ):
            raise ValueError("invalid structural operation")
        self._relax(self.time_us)
        self.next_step_us = timestamp((self.time_us // self.config.step_us + 1) * self.config.step_us)
        if action in ("silence", "unsilence"):
            if action == "silence":
                self.silenced_nodes |= selected
                self.silenced_edges |= links
                for identity in selected:
                    n = self.nodes[identity]
                    n.voltage_mv, n.current_na, n.adaptation_na = self.config.rest_mv, 0.0, 0.0
                    self.active.discard(identity)
            else:
                self.silenced_nodes -= selected
                self.silenced_edges -= links
        else:
            for key in links | {k for k in self.edges if k[0] in selected or k[1] in selected}:
                self._remove_edge(key)
            for identity in selected:
                del self.channels[self.nodes[identity].channel]
                del self.nodes[identity]
                self.active.discard(identity)
                self.silenced_nodes.discard(identity)
        self.sequence += 1
        self._life()

    def reconfigure(self, config):
        if type(config) is not LifConfig:
            raise ValueError("LIF requires LifConfig")
        if config == self.config:
            return
        if self.life == "dead":
            raise ValueError("cannot reconfigure a dead consciousness")
        for key in ("step_us", "seed", "rest_mv", "reset_mv", "threshold_mv"):
            if getattr(config, key) != getattr(self.config, key):
                raise ValueError(f"{key} is immutable after creation")
        self._relax(self.time_us)
        self.next_step_us = timestamp((self.time_us // self.config.step_us + 1) * self.config.step_us)
        for e in self.edges.values():
            self._stdp_relax(e)
        self.short_term = {
            key: s.recovered(self.time_us, self.config.short_term()) for key, s in self.short_term.items()
        }
        self.config = config
        self.sequence += 1
        self._life()

    def capture_state(self):
        document = definition(self.config)
        # Projections are fixed at the settled state time, so observation horizons don't rewrite physics.
        nodes = self._node_rows(self.state_time_us)
        return StateImage.from_dict(
            {
                "schema": STATE_SCHEMA,
                "dynamics": KERNEL_ID,
                "config": self.config.to_dict(),
                "definition": document,
                "definition_hash": document_hash(document),
                "time_us": str(self.time_us),
                "state_time_us": str(self.state_time_us),
                "next_step_us": str(self.next_step_us),
                "sequence": self.sequence,
                "next_event": self.next_event,
                "next_node": self.next_node,
                "next_synapse": self.next_synapse,
                "life": self.life,
                "sources_open": self.sources_open,
                "quiet_since_us": None if self.quiet_since_us is None else str(self.quiet_since_us),
                "nodes": nodes,
                "edges": self.induced_edges(self.nodes),
                "membranes": [stored(self.nodes[n]) for n in sorted(self.nodes)],
                "synapses": [stored(e) for _, e in sorted(self.edges.items())],
                "active": sorted(self.active),
                "silenced_nodes": sorted(self.silenced_nodes),
                "silenced_edges": [list(k) for k in sorted(self.silenced_edges)],
                "short_term": [
                    {"source": a, "target": b, "state": stored(s)} for (a, b), s in sorted(self.short_term.items())
                ],
                "queue": [{"time_us": str(t), "id": i, "kind": k, "payload": p} for t, i, k, p in sorted(self.queue)],
                "transport": dict(self.transport),
                "capacity_rejections": dict(self.rejected),
            }
        )

    def _restore(self, image):
        value = image.to_dict()
        if value.get("dynamics") != KERNEL_ID or value.get("schema") != STATE_SCHEMA:
            raise ValueError("LIF state identity mismatch")
        c = LifConfig(**value["config"])
        document = definition(c)
        if value.get("definition") != document or value.get("definition_hash") != document_hash(document):
            raise ValueError("LIF definition mismatch")
        self.config = c
        for key in ("time_us", "state_time_us", "next_step_us"):
            setattr(self, key, timestamp(value[key]))
        if self.state_time_us > self.time_us or self.next_step_us != (self.state_time_us // c.step_us + 1) * c.step_us:
            raise ValueError("inconsistent LIF clocks")
        for key in ("sequence", "next_event", "next_node", "next_synapse"):
            if type(value[key]) is not int or not 0 <= value[key] < 2**63:
                raise ValueError("invalid LIF identity counter")
            setattr(self, key, value[key])
        self.quiet_since_us = None if value["quiet_since_us"] is None else timestamp(value["quiet_since_us"])
        if self.quiet_since_us is not None and self.quiet_since_us > self.state_time_us:
            raise ValueError("future quiet period")
        self.life, self.sources_open = value["life"], value["sources_open"]
        if self.life not in ("waiting", "alive", "dead") or type(self.sources_open) is not bool:
            raise ValueError("invalid lifecycle state")

        def restore_rows(rows, cls):
            for row in rows:
                if not isinstance(row, dict) or set(row) != set(cls.__dataclass_fields__):
                    raise ValueError("invalid physical row fields")
                normalized = {
                    key: timestamp(v) if key.endswith("_us") and v is not None else v for key, v in row.items()
                }
                for key, v in normalized.items():
                    if key in ("voltage_mv", "current_na", "adaptation_na", "weight", "pre", "post"):
                        number(
                            v,
                            key,
                            low=-1.7976931348623157e308 if key == "voltage_mv" else 0,
                            high=1.7976931348623157e308,
                        )
                    elif v is not None and (type(v) is not int or v < 0):
                        raise ValueError("invalid physical identity, time or count")
                yield cls(**normalized)

        for n in restore_rows(value["membranes"], Membrane):
            if (
                not 1 <= n.id < self.next_node
                or n.channel > 2**32 - 1
                or n.id in self.nodes
                or n.channel in self.channels
            ):
                raise ValueError("invalid membrane identity")
            if (
                not n.birth_us <= n.last_touch_us <= self.state_time_us
                or n.last_spike_us is not None
                and n.last_spike_us > self.state_time_us
            ):
                raise ValueError("invalid membrane history")
            if (
                (n.last_spike_us is None) != (n.spikes == 0)
                or (n.last_spike_us is None and n.refractory_until_us != 0)
                or (n.last_spike_us is not None and n.refractory_until_us < n.last_spike_us)
            ):
                raise ValueError("inconsistent spike history")
            self.nodes[n.id], self.channels[n.channel] = n, n.id
        edge_ids = set()
        for e in restore_rows(value["synapses"], Synapse):
            key = e.source, e.target
            if (
                e.source not in self.nodes
                or e.target not in self.nodes
                or e.source == e.target
                or key in self.edges
                or e.id in edge_ids
                or not 1 <= e.id < self.next_synapse
                or e.weight > 1
            ):
                raise ValueError("invalid synapse identity")
            if (
                not e.birth_us <= e.last_touch_us <= self.state_time_us
                or not e.birth_us <= e.trace_time_us <= self.state_time_us
            ):
                raise ValueError("invalid synapse history")
            self.edges[key] = e
            edge_ids.add(e.id)
            self.outgoing.setdefault(e.source, set()).add(e.target)
            self.incoming.setdefault(e.target, set()).add(e.source)
        self.active, self.silenced_nodes = set(value["active"]), set(value["silenced_nodes"])
        self.silenced_edges = {tuple(k) for k in value["silenced_edges"]}
        if (
            not self.active <= self.nodes.keys()
            or not self.silenced_nodes <= self.nodes.keys()
            or not self.silenced_edges <= self.edges.keys()
        ):
            raise ValueError("invalid active or silenced identity")
        if self.active != {identity for identity, node in self.nodes.items() if self._present(node)}:
            raise ValueError("active membrane index differs from physical activity")
        if self.active & self.silenced_nodes:
            raise ValueError("silenced membranes cannot carry activity")
        if self.life in ("waiting", "dead") and self.active or self.active and self.quiet_since_us is not None:
            raise ValueError("lifecycle disagrees with membrane activity")
        if self.life == "waiting" and (any(n.spikes for n in self.nodes.values()) or self.quiet_since_us is not None):
            raise ValueError("waiting state cannot contain previous spikes or a quiet timer")
        if self.life != "waiting" and not self.active:
            if self.quiet_since_us is None:
                raise ValueError("inactive consciousness requires a quiet timer")
            expired = self.state_time_us - self.quiet_since_us >= c.quiescence_death_us
            if (self.life == "dead") != expired:
                raise ValueError("death and quiet deadline disagree")
        for row in value["short_term"]:
            key = row["source"], row["target"]
            state = ShortTermState(**(row["state"] | {"time_us": timestamp(row["state"]["time_us"])}))
            if (
                key not in self.edges
                or key in self.short_term
                or not self.edges[key].birth_us <= state.time_us <= self.state_time_us
            ):
                raise ValueError("invalid short-term history")
            self.short_term[key] = state
        events = set()
        for row in value["queue"]:
            when, event_id, kind, payload = timestamp(row["time_us"]), row["id"], row["kind"], row["payload"]
            if (
                when < self.time_us
                or type(event_id) is not int
                or not 0 <= event_id < self.next_event
                or event_id in events
            ):
                raise ValueError("invalid pending event")
            if kind == "stimulus":
                if Stimulus.from_dict(payload).time_us != when:
                    raise ValueError("stimulus clock mismatch")
            elif kind == "spike_arrival":
                if set(payload) != {"messages"}:
                    raise ValueError("invalid spike arrival")
                for source, target, synapse_id, amount in payload["messages"]:
                    if any(
                        type(n) is not int or not 1 <= n < bound
                        for n, bound in (
                            (source, self.next_node),
                            (target, self.next_node),
                            (synapse_id, self.next_synapse),
                        )
                    ):
                        raise ValueError("invalid in-flight identity")
                    number(amount, "arrival amount", high=1.7976931348623157e308)
            else:
                raise ValueError("unknown LIF event")
            events.add(event_id)
            heapq.heappush(self.queue, (when, event_id, kind, payload))
        self.transport, self.rejected = value["transport"], value["capacity_rejections"]
        for key in ("sent_na", "received_na", "unavailable_na"):
            number(self.transport[key], key, high=1.7976931348623157e308)
        if set(self.transport) != {"sent_na", "received_na", "unavailable_na"} or set(self.rejected) != {
            "nodes",
            "edges",
        }:
            raise ValueError("invalid transport or capacity fields")
        if any(type(v) is not int or v < 0 for v in self.rejected.values()):
            raise ValueError("invalid capacity count")
        # Reject extra keys, duplicate arrays, forged projections and lossy coercions.
        if self.capture_state().digest != image.digest:
            raise ValueError("LIF state contains inconsistent projections or fields")
