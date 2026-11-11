"""Versioned experimental continuous kernel, separate from the preserved baseline.

The preserved Engine owns baseline scheduling/local rules. Candidate operators
are separate per-edge state and receiver-local allocations, never UI callbacks.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass

from threemind_core import Config, Engine, StateImage
from threemind_core.engine import canonical_bytes
from threemind_core.spec import timestamp

from .mechanisms import FastTrace, FastTraceConfig, ShortTermConfig, ShortTermState, local_attention, number

KERNEL_ID = "threemind.continuous/1"
STATE_SCHEMA = "threemind.continuous-state/1"
CORE_KEYS = tuple(Config.__dataclass_fields__)
MECHANISMS = (
    ("threemind.causal9-transition/1", "hybrid-event-clock"),
    ("threemind.leaky-fast-trace/1", "efficacy-and-emission"),
    ("threemind.tm-synapse/1", "before-emission"),
    ("threemind.local-context-attention/1", "after-arrival"),
)


@dataclass(frozen=True, slots=True)
class ContinuousConfig(Config):
    stp_enabled: bool = True
    stp_utilization: float = 0.5
    stp_recovery_tau_s: float = 0.8
    stp_active_tau_s: float = 0.003
    stp_facilitation_tau_s: float = 0.0
    fast_enabled: bool = True
    fast_tau_s: float = 2.0
    fast_learning_rate: float = 0.1
    fast_gain: float = 0.1
    context_enabled: bool = True
    context_tau_s: float = 1.0
    context_temperature: float = 1.0
    context_mix: float = 1.0

    def __post_init__(self):
        normalized = Config(**{key: getattr(self, key) for key in CORE_KEYS})
        for key in CORE_KEYS:
            object.__setattr__(self, key, getattr(normalized, key))
        for key in ("stp_enabled", "fast_enabled", "context_enabled"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be boolean")
        for key in self.__dataclass_fields__:
            if key not in CORE_KEYS and not key.endswith("_enabled"):
                object.__setattr__(self, key, number(getattr(self, key), key))
        self.short_term()
        self.fast_trace()
        number(self.context_tau_s, "context_tau_s", low=1e-6, high=1e9)
        number(self.context_temperature, "context_temperature", low=1e-6, high=1e6)
        number(self.context_mix, "context_mix", high=1.0)
        # Prevent unrepresentable traffic before entering partially mutated steps.
        number(self.propagation_rate, "candidate propagation_rate", high=1e9)
        number(self.propagation_rate * (self.propagation_interval_us / 1e6), "candidate emission gain", high=1e12)

    def base(self):
        return Config(**{key: getattr(self, key) for key in CORE_KEYS})

    def to_dict(self):
        return self.base().to_dict() | {key: value for key, value in asdict(self).items() if key not in CORE_KEYS}

    def short_term(self):
        return ShortTermConfig(
            self.stp_utilization, self.stp_recovery_tau_s, self.stp_active_tau_s, self.stp_facilitation_tau_s
        )

    def fast_trace(self):
        return FastTraceConfig(self.fast_tau_s, self.fast_learning_rate, self.fast_gain)


class ContinuousDynamics(Engine):
    """Internal engine; external version/state dispatch is provided by the wrapper."""

    def __init__(self, config: ContinuousConfig, state: StateImage | None = None):
        self.parameters = config
        self.short_term_states = {}
        self.fast_states = {}
        self._messages = []
        super().__init__(config.base(), state)

    def features(self, node):
        return [
            node.activation,
            node.trace,
            node.inhibition / (1.0 + node.inhibition),
            math.exp(-(self.time_us - int(node.last_touch_us)) / 1e6 / self.parameters.context_tau_s),
        ]

    def effective_weight(self, edge):
        p = self.parameters
        if not p.fast_enabled:
            return edge.weight
        state = self.fast_states.get((edge.source, edge.target), FastTrace(time_us=int(edge.birth_us)))
        return state.efficacy(edge.weight, self.time_us, p.fast_trace())

    def release_fraction(self, edge):
        p = self.parameters
        if not p.stp_enabled:
            return 1.0
        key = edge.source, edge.target
        state = self.short_term_states.get(key, ShortTermState(time_us=int(edge.birth_us)))
        state, fraction = state.release(self.time_us, p.short_term())
        self.short_term_states[key] = state
        return fraction

    def record_emission(self, node, edge, amount):
        p = self.parameters
        if p.fast_enabled and self.config.plasticity:
            key = edge.source, edge.target
            state = self.fast_states.get(key, FastTrace(time_us=int(edge.birth_us)))
            self.fast_states[key] = state.transmit(amount, self.time_us, p.fast_trace())
        if p.context_enabled:
            self._messages.append([edge.source, edge.target, amount, self.features(node)])

    def _event(self, when, kind, payload):
        if kind == "signal" and self._messages:
            payload = payload | {"messages": self._messages}
            self._messages = []
        return super()._event(when, kind, payload)

    def _receive_signal(self, payload):
        if not self.parameters.context_enabled or self.parameters.context_mix == 0 or "messages" not in payload:
            return super()._receive_signal(payload)
        by_target = {}
        for source, target, amount, key in payload["messages"]:
            by_target.setdefault(target, []).append((source, amount, key))
        touched, reception = [], []
        for target, raw in payload["values"]:
            messages = by_target[target]
            if target not in self.nodes or target in self.silenced_nodes:
                reception.append({"target": target, "raw": raw, "response": 0.0, "status": "unavailable"})
                continue
            value, coefficients = local_attention(
                self.features(self.nodes[target]),
                [m[2] for m in messages],
                [m[1] for m in messages],
                temperature=self.parameters.context_temperature,
                mix=self.parameters.context_mix,
            )
            amount = self._touch(target, value, direct=False)
            # _touch accounts effective arrival; restore the raw receipt ledger.
            self.transport["received"] += raw - value
            if amount > 0:
                touched.append((target, amount, 0.0))
            reception.append(
                {
                    "target": target,
                    "raw": raw,
                    "response": value,
                    "coefficients": coefficients,
                    "sources": [m[0] for m in messages],
                }
            )
        if self.config.edge_birth_policy == "temporal-association":
            self._associate(touched)
        self._update_touched([(n, amount) for n, amount, _ in touched])
        return payload | {"reception": reception}

    def _remove_edge(self, key):
        super()._remove_edge(key)
        self.short_term_states.pop(key, None)
        self.fast_states.pop(key, None)

    def settle_parameters(self, new: ContinuousConfig):
        if new == self.parameters:
            return
        if self.life == "dead":
            raise ValueError("a dead instance requires an explicit new birth")
        # Settle old rates at the explicit reconfiguration boundary first.
        short = {
            key: state.recovered(self.time_us, self.parameters.short_term())
            for key, state in self.short_term_states.items()
        }
        fast = {
            key: FastTrace(state.projected(self.time_us, self.parameters.fast_trace()), self.time_us)
            for key, state in self.fast_states.items()
        }
        changed_base = new.base() != self.config
        super().reconfigure(new.base())
        if not changed_base:
            self.sequence += 1
        self.short_term_states, self.fast_states, self.parameters = short, fast, new

    def _emit(self):
        # Base scheduling/consolidation is deliberately retained; only the named
        # local operators below alter candidate transmission and reception.
        if (
            not any((self.parameters.stp_enabled, self.parameters.fast_enabled, self.parameters.context_enabled))
            and not self._local_retention_enabled()
        ):
            return super()._emit()
        c = self.config
        dt = c.propagation_interval_us / 1e6
        gain, diffusion = c.propagation_rate * dt, min(1.0, c.inhibition_diffusion_rate * dt)
        for n in self.nodes.values():
            if c.inhibition:
                n.inhibition = self._saturate_inhibition(n.inhibition + n.pending_inhibition)
                n.pending_inhibition = 0.0
            else:
                n.inhibition = n.pending_inhibition = n.generated_inhibition = 0.0
        signals, inhibitors, traversed = {}, {}, set()
        ordered = sorted(self.nodes.values(), key=lambda n: n.id)
        if c.propagation_limit is not None:
            ordered.sort(key=lambda n: (-n.activation, n.id))
        emissions = 0
        for n in ordered:
            if n.id in self.silenced_nodes:
                continue
            self._before_emit_node(n)
            targets = sorted(self.outgoing.get(n.id, ()))
            if c.propagation_limit is not None:
                targets.sort(key=lambda target: (-self.edges[n.id, target].weight, target))
            for target in targets if n.activation > 0 and n.activation >= c.propagation_activation_min else ():
                key = n.id, target
                if key in self.silenced_edges:
                    continue
                e = self.edges[key]
                amount = n.activation * self._inhibitory_response(n) * self.effective_weight(e) * gain
                if c.spatial_embedding and c.neighborhood_enabled:
                    amount *= self.spatial.attenuation(c, n.id, target)
                if amount <= 0 or amount < c.activation_floor:
                    continue
                if c.propagation_limit is not None and emissions >= c.propagation_limit:
                    self.resources.increment("propagation_budget_skips")
                    continue
                amount *= self.release_fraction(e)
                if c.energy_simulation_enabled:
                    amount = self.energy.afford(amount, c.energy_associative_cost, "associative")
                self.transport["sent"] += amount
                if amount <= 0 or amount < c.activation_floor:
                    self.transport["discarded"] += amount
                    continue
                emissions += 1
                signals[target] = signals.get(target, 0.0) + amount
                self.record_emission(n, e, amount)
                traversed.add(key)
                if c.plasticity:
                    if c.edge_adaptation_limit is not None:
                        if not self.resources.available_adaptations(
                            self.time_us, c.propagation_interval_us, c.edge_adaptation_limit
                        ):
                            self.resources.increment("adaptation_budget_skips")
                            continue
                        self.resources.use_adaptation(self.time_us, c.propagation_interval_us)
                    e.eligibility = min(1.0, 0.7 * e.eligibility + amount)
                    if self._edge_consolidation_enabled():
                        e.weight = min(1.0, e.weight + c.associative_gain * amount)
                        e.stability = min(1.0, e.stability + c.stability_gain * amount)
                    e.touches += 1
                    e.last_touch_us = str(self.time_us)
                    self._edge_changed(key)
            if c.inhibition and n.generated_inhibition > 0:
                n.inhibition = self._saturate_inhibition(n.inhibition + n.generated_inhibition)
            n.generated_inhibition = 0.0
            if c.inhibition and n.inhibition >= c.inhibition_propagation_min:
                conductances = []
                for target in sorted(self.incident.get(n.id, ())):
                    for k in ((n.id, target), (target, n.id)):
                        if k in self.edges and k not in self.silenced_edges:
                            self._prepare_edge(k)
                    weights = [
                        self.edges[k].weight
                        for k in ((n.id, target), (target, n.id))
                        if k in self.edges and k not in self.silenced_edges
                    ]
                    if weights and max(weights) > 0:
                        conductances.append((target, max(weights)))
                total = sum(w for _, w in conductances)
                transfer = n.inhibition * diffusion
                if total > 0 and transfer >= c.inhibition_propagation_min:
                    if c.energy_simulation_enabled:
                        transfer = self.energy.afford(transfer, c.energy_inhibition_cost, "inhibition")
                    if transfer >= c.inhibition_propagation_min:
                        n.inhibition -= transfer
                        for target, w in conductances:
                            inhibitors[target] = inhibitors.get(target, 0.0) + transfer * w / total
        for kind, values in (("signal", signals), ("inhibition", inhibitors)):
            if values:
                self._event(
                    self.time_us + c.delay_us,
                    kind,
                    {
                        "values": [
                            [n, self._saturate_inhibition(v) if kind == "inhibition" else v]
                            for n, v in sorted(values.items())
                        ]
                    },
                )
        if c.plasticity:
            retention = math.exp(-dt / c.eligibility_tau) if c.eligibility_decay_enabled else 1.0
            for key, e in self.edges.items():
                e.eligibility *= retention
                if c.stability_decay_enabled:
                    e.stability = max(0.0, e.stability - dt / c.stability_tau * (1.0 - e.eligibility))
                if key not in traversed and not self._adaptive_retention_active():
                    e.weight *= max(0.0, 1.0 - 0.1 * c.forgetting_rate * (1.0 - (0.08 + 0.92 * e.stability))) ** (
                        dt / 0.1
                    )
                    self._legacy_edge_decayed(key)
        self.traversed = traversed
        for n in self.nodes.values():
            n.direct = n.associative = 0.0


def definition(config):
    return {
        "schema": "threemind.kernel-definition/1",
        "kernel_id": KERNEL_ID,
        "state_schema": STATE_SCHEMA,
        "hypothesis_id": "threemind.hypotheses/continuous1",
        "operators": [{"id": name, "phase": phase} for name, phase in MECHANISMS],
        "config": config.to_dict(),
    }


def definition_hash(document):
    return hashlib.sha256(canonical_bytes(document)).hexdigest()


class ContinuousEngine:
    """Public identity and owned recovery state; no storage/network/GUI dependency."""

    dynamics = KERNEL_ID
    state_schema = STATE_SCHEMA
    config_type = ContinuousConfig
    engine_type = ContinuousDynamics
    definition = staticmethod(definition)

    def __init__(self, config: ContinuousConfig | None = None, state: StateImage | None = None):
        if config is not None and type(config) is not self.config_type:
            raise ValueError("continuous kernel requires ContinuousConfig")
        if state is None:
            self._engine = self.engine_type(config or self.config_type())
            return
        if config is not None:
            raise ValueError("restoration uses saved configuration")
        value = state.to_dict()
        if value.get("dynamics") != self.dynamics or value.get("schema") != self.state_schema:
            raise ValueError("continuous kernel state identity mismatch")
        if not {"definition", "definition_hash", "operator_state"}.issubset(value):
            raise ValueError("missing continuous mechanism state")
        config = self.config_type(**value["config"])
        expected = self.definition(config)
        if value.pop("definition") != expected or value.pop("definition_hash") != definition_hash(expected):
            raise ValueError("continuous definition/hash does not match configuration")
        operators = value.pop("operator_state")
        if not isinstance(operators, dict) or set(operators) != {"short_term", "fast"}:
            raise ValueError("invalid continuous operator-state fields")
        value.update(dynamics="threemind.causal/9", schema="threemind.state/6", config=config.base().to_dict())
        self._engine = self.engine_type(config, StateImage.from_dict(value))
        for name, state_type, destination in (
            ("short_term", ShortTermState, self._engine.short_term_states),
            ("fast", FastTrace, self._engine.fast_states),
        ):
            if not isinstance(operators[name], list):
                raise ValueError("operator edge state must be a list")  # noqa: TRY004 -- public protocol validation
            for row in operators[name]:
                if not isinstance(row, dict) or set(row) != {"source", "target", "state"}:
                    raise ValueError("invalid operator edge record")
                key = row["source"], row["target"]
                if any(type(n) is not int for n in key) or key not in self._engine.edges or key in destination:
                    raise ValueError("invalid or duplicate operator edge identity")
                if not isinstance(row["state"], dict) or set(row["state"]) != set(state_type.__dataclass_fields__):
                    raise ValueError("invalid operator history fields")
                saved = dict(row["state"])
                saved["time_us"] = timestamp(saved["time_us"])
                operator = state_type(**saved)
                if not int(self._engine.edges[key].birth_us) <= operator.time_us <= self._engine.time_us:
                    raise ValueError("operator history outside edge lifetime")
                destination[key] = operator
        for _, _, kind, payload in self._engine.queue:
            if kind == "signal":
                self._validate_messages(payload, self._engine.next_node)

    def __getattr__(self, name):
        return getattr(self._engine, name)

    @property
    def config(self):
        return self._engine.parameters

    @staticmethod
    def _validate_messages(payload, next_node):
        if "messages" not in payload:
            if set(payload) != {"values"}:
                raise ValueError("unexpected signal fields")
            return
        if set(payload) != {"values", "messages"}:
            raise ValueError("unexpected contextual signal fields")
        sums, pairs = {}, set()
        for item in payload["messages"]:
            if not isinstance(item, list) or len(item) != 4:
                raise ValueError("invalid message record")
            source, target, amount, key = item
            if (
                any(type(n) is not int or not 1 <= n < next_node for n in (source, target))
                or source == target
                or (source, target) in pairs
            ):
                raise ValueError("invalid or duplicate message endpoints")
            pairs.add((source, target))
            number(amount, "raw message amount")
            if not isinstance(key, list) or len(key) != 4:
                raise ValueError("invalid local feature dimension")
            for item in key:
                number(item, "local feature", high=1.0)
            sums[target] = sums.get(target, 0.0) + amount
        values = dict(payload["values"])
        if (
            len(values) != len(payload["values"])
            or values.keys() != sums.keys()
            or any(
                not math.isclose(values[target], value, rel_tol=1e-12, abs_tol=1e-14) for target, value in sums.items()
            )
        ):
            raise ValueError("raw arrival amounts disagree with contextual messages")

    def capture_state(self):
        value = self._engine.capture_state().to_dict()
        document = self.definition(self.config)

        def rows(states):
            return [
                {"source": source, "target": target, "state": asdict(state) | {"time_us": str(state.time_us)}}
                for (source, target), state in sorted(states.items())
            ]

        value.update(
            schema=self.state_schema,
            dynamics=self.dynamics,
            config=self.config.to_dict(),
            definition=document,
            definition_hash=definition_hash(document),
            operator_state={"short_term": rows(self._engine.short_term_states), "fast": rows(self._engine.fast_states)},
        )
        return StateImage.from_dict(value)

    def reconfigure(self, config):
        if type(config) is not self.config_type:
            raise ValueError("continuous kernel requires ContinuousConfig")
        self._engine.settle_parameters(config)

    def metrics(self):
        return self._engine.metrics() | {
            "kernel_id": self.dynamics,
            "state_schema": self.state_schema,
            "operator_state": {
                "short_term_edges": len(self._engine.short_term_states),
                "fast_edges": len(self._engine.fast_states),
            },
        }

    def graph(self, limit=None):
        return self._engine.graph(limit) | {"kernel_id": self.dynamics, "observation_quantity": "activation"}
