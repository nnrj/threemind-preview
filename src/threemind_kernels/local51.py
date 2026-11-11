"""Memory/5.1: implementation optimizations with the memory/5 dynamics.

The reference path retains the readable memory/5 transition rules. The only
cached value depends on immutable configuration, never on a node, edge or
simulation timestamp. Historical memory/5 execution is left unchanged.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from .local5 import MECHANISMS, Local5Config, Local5Edge, Local5Engine, Local5Node
from .retention import decay

KERNEL_ID = "threemind.continuous-memory/5.1"
STATE_SCHEMA = "threemind.continuous-memory-state/5.1"
HYPOTHESIS_ID = "threemind.hypotheses/continuous-memory51"


@dataclass(frozen=True, slots=True)
class Local51Config(Local5Config):
    def __post_init__(self):
        try:
            Local5Config.__post_init__(self)
        except ValueError as exc:
            raise ValueError(str(exc).replace("memory/5", "memory/5.1")) from exc


# The public row layouts and operator semantics are identical to memory/5.
Local51Node = Local5Node
Local51Edge = Local5Edge


def definition(config):
    return {
        "schema": "threemind.kernel-definition/1",
        "kernel_id": KERNEL_ID,
        "state_schema": STATE_SCHEMA,
        "hypothesis_id": HYPOTHESIS_ID,
        "operators": [{"id": key, "phase": phase} for key, phase in MECHANISMS],
        "config": config.to_dict(),
    }


class Local51Engine(Local5Engine):
    dynamics = KERNEL_ID
    state_schema = STATE_SCHEMA
    config_type = Local51Config
    definition = staticmethod(definition)

    def __init__(self, config=None, state=None):
        self._eligibility_config = None
        self._eligibility_period_retention = 1.0
        super().__init__(config, state)

    def _project_edge(self, edge, when):
        # Same operation order as /5; only exp(-period / tau) is cached.
        # Identity comparison also invalidates it after explicit reconfigure
        # and restoration. The cache is derived and is never serialized.
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
