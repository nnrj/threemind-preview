"""Memory/5: local execution with the approved memory/2 learning semantics.

This is a distinct birth identity. Memory/4 remains an executable historical
model; no checkpoint is silently relabelled or upgraded.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from threemind_core.spec import timestamp

from .local import LocalConfig, LocalEdge, LocalEngine, LocalNode
from .local_deadlines import LocalDeadlines
from .mechanisms import local_attention
from .retention import decay

KERNEL_ID = "threemind.continuous-memory/5"
STATE_SCHEMA = "threemind.continuous-memory-state/5"
MECHANISMS = (
    ("threemind.object-local-clock/2", "arrivals-novelty-emission-expiry"),
    ("threemind.source-independent-reception/2", "receiver-local-arrivals"),
    ("threemind.tm-synapse/1", "before-emission"),
    ("threemind.leaky-fast-trace/1", "efficacy-and-emission"),
    ("threemind.local-context-attention/1", "receiver-local-arrivals"),
    ("threemind.local-contact-learning/2", "external-contact-packet"),
    ("threemind.local-arrival-novelty/4", "pre-emission-aligned-window"),
    ("threemind.adaptive-half-life/2", "local-touch-emission-expiry"),
    ("threemind.local-resource-field/1", "supply-local-uptake-expense"),
    ("threemind.local-awakening/2", "residual-contact-arrivals"),
    ("threemind.inhibition-packet-saturation/1", "after-same-time-emissions"),
)


@dataclass(frozen=True, slots=True)
class Local5Config(LocalConfig):
    reception_mode: str = "legacy-source"
    arrival_mode: str = "sequential"

    def __post_init__(self):
        try:
            LocalConfig.__post_init__(self)
        except ValueError as exc:
            raise ValueError(str(exc).replace("memory/4", "memory/5").replace("memory/3", "memory/5")) from exc


@dataclass(slots=True)
class Local5Node(LocalNode):
    last_emit_us: str = "0"


@dataclass(slots=True)
class Local5Edge(LocalEdge):
    completed_period_us: str = "0"


class _Deadlines(LocalDeadlines):
    def set(self, key, when):
        i = self.positions.get(key)
        if (i is None and when is None) or (i is not None and self.heap[i][0] == when):
            return
        super().set(key, when)


def definition(config):
    return {
        "schema": "threemind.kernel-definition/1",
        "kernel_id": KERNEL_ID,
        "state_schema": STATE_SCHEMA,
        "hypothesis_id": "threemind.hypotheses/continuous-memory5",
        "operators": [{"id": key, "phase": phase} for key, phase in MECHANISMS],
        "config": config.to_dict(),
    }


class Local5Engine(LocalEngine):
    dynamics = KERNEL_ID
    state_schema = STATE_SCHEMA
    config_type = Local5Config
    node_type = Local5Node
    edge_type = Local5Edge
    definition = staticmethod(definition)
    restored_learning = True

    def __init__(self, config=None, state=None):
        self._before_emission = False
        self.completed_emission_us = 0
        self._direct_drives = {}
        self._emission_inhibitors = {}
        super().__init__(config, state)
        timers = _Deadlines()
        timers.heap, timers.positions = self.timers.heap, self.timers.positions
        self.timers = timers

    def _project_edge(self, edge, when):
        """Project H by elapsed time, but old eligibility/stability by periods.

        The geometric sum is the original discrete recurrence, including its
        monotone stability clamp. It does not replace it with an ODE integral.
        """
        e, c = copy.copy(edge), self.config
        dt = (when - int(e.state_us)) / 1e6
        if c.consolidation_mode == "adaptive-half-life":
            if dt and c.plasticity:
                e.weight, e.half_life = decay(e.weight, e.half_life, dt, c)
            period = c.propagation_interval_us
            before = self._before_emission and when == self.time_us
            complete = max(0, (when - int(before)) // period * period)
            count = (complete - int(e.completed_period_us)) // period
            if count > 0 and c.plasticity:
                seconds = period / 1e6
                ratio = math.exp(-seconds / c.eligibility_tau) if c.eligibility_decay_enabled else 1.0
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

    def _receive(self, packets):
        if self.config.arrival_mode == "coincident":
            self._receive_group(packets)
            return
        # A legacy periodic signal is one reception packet containing messages
        # from all actual senders. External packets retain separate identities.
        internal = [m for _, messages, direct, _ in packets if not direct for m in messages]
        emitted_internal = False
        for serial, messages, direct, intensity in packets:
            if direct:
                self._receive_group([(serial, messages, True, intensity)])
            elif not emitted_internal:
                self._receive_group([(serial, internal, False, 1.0)])
                emitted_internal = True

    def _settle_edge(self, key):
        self.audit["edge_visits"] += 1
        edge, c = self.edges[key], self.config
        complete = max(
            0, (self.time_us - int(self._before_emission)) // c.propagation_interval_us * c.propagation_interval_us
        )
        if int(edge.state_us) == self.time_us and (
            (c.consolidation_mode == "legacy-stability" and c.plasticity) or int(edge.completed_period_us) == complete
        ):
            return edge
        self.edges[key] = self._project_edge(edge, self.time_us)
        return self.edges[key]

    def _receive_group(self, packets):
        c, inboxes, cohorts = self.config, {}, {}
        for serial, messages, direct, intensity in packets:
            for source, target, value, features in messages:
                inboxes.setdefault(target, []).append((serial, source, value, features, direct, intensity))
        for id, group in sorted(inboxes.items()):
            if id not in self.nodes:
                continue
            values = [m[2] for m in group]
            use = (
                c.context_enabled
                and c.context_mix > 0
                and (c.reception_mode == "unified" or not any(m[4] for m in group))
            )
            if use:
                n = self._settle_node(id)
                # Public restore validates these bounds. Keep the fallback for
                # malformed internal callers rather than bypassing validation.
                single = (
                    len(group) == 1
                    and len(group[0][3]) == 4
                    and all(
                        not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) and -1 <= v <= 1
                        for v in group[0][3]
                    )
                    and not isinstance(values[0], bool)
                    and isinstance(values[0], (int, float))
                    and math.isfinite(values[0])
                    and 0 <= values[0] <= 1e12
                )
                if single:
                    coefficients = [(1.0 - c.context_mix) + c.context_mix]
                    value = sum(v * k for v, k in zip(values, coefficients))
                else:
                    value, coefficients = local_attention(
                        self._features(n),
                        [m[3] for m in group],
                        values,
                        temperature=c.context_temperature,
                        mix=c.context_mix,
                    )
            else:
                value, coefficients = sum(values), [1.0] * len(group)
            direct = all(m[4] for m in group)
            external = [(m, coefficient) for m, coefficient in zip(group, coefficients) if m[4]]
            drive = (
                sum(self._direct_drives.get((m[0], id), m[2]) * coefficient for m, coefficient in external)
                if external
                else None
            )
            amount, impulse = self._touch(id, value, direct, max(m[5] for m in group), drive)
            if not direct and c.reception_mode == "legacy-source":
                self.transport["received"] += sum(values) - value
            if amount <= 0:
                continue
            total = sum(v * k for v, k in zip(values, coefficients))
            for m, coefficient in zip(group, coefficients):
                if m[4]:
                    fraction = m[2] * coefficient / total if total else 0.0
                    cohorts.setdefault(m[0], []).append((id, amount * fraction, impulse * fraction))
        for serial in sorted(cohorts):
            merged = {}
            for id, amount, impulse in cohorts[serial]:
                previous = merged.get(id, (0.0, 0.0))
                merged[id] = previous[0] + amount, previous[1] + impulse
            self._associate([(id, *amounts) for id, amounts in sorted(merged.items())])

    def _validate(self):
        super()._validate()
        period = self.config.propagation_interval_us
        if self.completed_emission_us != self.time_us // period * period:
            raise ValueError("invalid memory/5 completed emission phase")
        for n in self.nodes.values():
            if timestamp(n.last_emit_us) > self.time_us:
                raise ValueError("invalid memory/5 source emission clock")
        for e in self.edges.values():
            complete = timestamp(e.completed_period_us)
            if complete > self.time_us or complete % self.config.propagation_interval_us:
                raise ValueError("invalid memory/5 completed-period anchor")

    def _restore(self, doc):
        if "completed_emission_us" not in doc:
            raise ValueError("missing memory/5 completed emission phase")
        self.completed_emission_us = timestamp(doc["completed_emission_us"])
        if any("last_emit_us" not in n for n in doc.get("nodes", ())):
            raise ValueError("missing memory/5 source emission clock")
        if any("completed_period_us" not in e for e in doc.get("edges", ())):
            raise ValueError("missing memory/5 completed-period anchor")
        super()._restore(doc)
