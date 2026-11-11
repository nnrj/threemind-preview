"""Independent D/F/L research controls; continuous/1 remains preserved.

D-off is an explicit unlimited-resource control with unchanged release gain.
L-off gates positive existing-edge weight/stability updates, not forgetting,
eligibility, node support, edge birth, fast trace or inhibitory dynamics.
"""

from dataclasses import dataclass

from .continuous import MECHANISMS as BASE_MECHANISMS
from .continuous import ContinuousConfig, ContinuousDynamics, ContinuousEngine
from .continuous import definition as base_definition
from .mechanisms import ShortTermState

KERNEL_ID = "threemind.continuous-memory/1"
STATE_SCHEMA = "threemind.continuous-memory-state/1"
MECHANISMS = BASE_MECHANISMS + (
    ("threemind.resource-clamp-control/1", "before-emission"),
    ("threemind.edge-consolidation-control/1", "positive-edge-updates"),
)


@dataclass(frozen=True, slots=True)
class MemoryConfig(ContinuousConfig):
    depletion_enabled: bool = True
    edge_consolidation_enabled: bool = True

    def __post_init__(self):
        ContinuousConfig.__post_init__(self)
        for key in ("depletion_enabled", "edge_consolidation_enabled"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be boolean")


class MemoryDynamics(ContinuousDynamics):
    def _edge_consolidation_enabled(self):
        return self.parameters.edge_consolidation_enabled

    def release_fraction(self, edge):
        p = self.parameters
        if p.depletion_enabled or not p.stp_enabled:
            return super().release_fraction(edge)
        key = edge.source, edge.target
        state = self.short_term_states.get(key, ShortTermState(time_us=int(edge.birth_us)))
        recovered = state.recovered(self.time_us, p.short_term())
        # Preserve utilization history; the research clamp affects only x/y.
        rested_pool = ShortTermState(1.0, 0.0, recovered.utilization, self.time_us)
        after, fraction = rested_pool.release(self.time_us, p.short_term())
        self.short_term_states[key] = ShortTermState(1.0, 0.0, after.utilization, self.time_us)
        return fraction


def definition(config):
    value = base_definition(config)
    value.update(
        kernel_id=KERNEL_ID,
        state_schema=STATE_SCHEMA,
        hypothesis_id="threemind.hypotheses/continuous-memory1",
        operators=[{"id": name, "phase": phase} for name, phase in MECHANISMS],
    )
    return value


class MemoryEngine(ContinuousEngine):
    dynamics = KERNEL_ID
    state_schema = STATE_SCHEMA
    config_type = MemoryConfig
    engine_type = MemoryDynamics
    definition = staticmethod(definition)
