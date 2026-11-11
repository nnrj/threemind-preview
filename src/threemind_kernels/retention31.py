"""memory/3.1: retain /3 learning, but schedule zero-response objects locally."""

from dataclasses import dataclass

from .retention import MECHANISMS as PREVIOUS_MECHANISMS
from .retention import RetentionConfig, RetentionDynamics, RetentionEngine
from .retention import definition as previous_definition

KERNEL_ID = "threemind.continuous-memory/3.1"
STATE_SCHEMA = "threemind.continuous-memory-state/3.2"
HYPOTHESIS_ID = "threemind.hypotheses/continuous-memory3.1"
MECHANISMS = PREVIOUS_MECHANISMS + (
    ("threemind.zero-response-local-expiry/1", "after-local-reception"),
)


@dataclass(frozen=True, slots=True)
class Retention31Config(RetentionConfig):
    """Identical parameters; a distinct type preserves explicit factory routing."""


class Retention31Dynamics(RetentionDynamics):
    birth_expiry_enabled = True


def definition(config):
    value = previous_definition(config)
    value.update(
        kernel_id=KERNEL_ID,
        state_schema=STATE_SCHEMA,
        hypothesis_id=HYPOTHESIS_ID,
        operators=[{"id": name, "phase": phase} for name, phase in MECHANISMS],
    )
    return value


class Retention31Engine(RetentionEngine):
    dynamics, state_schema = KERNEL_ID, STATE_SCHEMA
    config_type, engine_type = Retention31Config, Retention31Dynamics
    definition = staticmethod(definition)
