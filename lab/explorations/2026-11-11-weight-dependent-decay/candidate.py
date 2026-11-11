"""Isolated R48 candidate. No production kernel or registered default is changed.

Only persistent connection-weight decay differs between arms. Node support,
reception, transmission, reinforcement, resource rules and event order are /5.3.
"""

import math
from dataclasses import dataclass

from threemind_core import StateImage
from threemind_kernels.decay53 import decay_value
from threemind_kernels.local53 import Local53Config, Local53Engine, definition as base_definition

KERNEL_ID = "threemind.experimental-weight-decay/1"
STATE_SCHEMA = "threemind.experimental-weight-decay-state/1"
RULES = ("inverse-logarithmic", "weight-fast", "weight-slow", "matched-fast", "matched-slow")
MIN_RATE = math.log(2.0) / 86400.0
EXTRA_RATES = {"fast": 0.06, "slow": 0.012}
MATCH_WEIGHT = 0.035


def exact_weight(value, seconds, minimum, extra):
    """Exact flow of dw/dt=-w*(minimum+extra*(1-w)), without history lists."""
    if not all(math.isfinite(x) for x in (value, seconds, minimum, extra)):
        raise ValueError("finite quantities required")
    if not 0 <= value <= 1 or seconds < 0 or minimum <= 0 or extra < 0:
        raise ValueError("invalid weight, duration or rates")
    if seconds == 0 or value == 0:
        return value
    alpha = minimum + extra
    z = math.exp(-alpha * seconds)
    # This form avoids cancellation at w=1; no iterative integration.
    denominator = alpha * (1 - value) + minimum * value + extra * value * z
    return alpha * value * z / denominator


@dataclass(frozen=True, slots=True)
class CandidateConfig(Local53Config):
    decay_curve: str = "inverse-logarithmic"
    edge_rule: str = "weight-fast"
    minimum_rate: float = MIN_RATE
    extra_rate: float = EXTRA_RATES["fast"]
    matching_weight: float = MATCH_WEIGHT

    def __post_init__(self):
        Local53Config.__post_init__(self)
        if self.edge_rule not in RULES:
            raise ValueError("unknown experimental rule")
        if self.decay_curve != "inverse-logarithmic":
            raise ValueError("node support reference is fixed to inverse-logarithmic")
        if self.retention_growth_enabled or self.retention_relaxation_enabled:
            raise ValueError("growth and relaxation remain disabled in this candidate")
        if self.reinforcement_age_policy != "keep":
            raise ValueError("reinforcement keeps age in R48")
        exact_weight(0.5, 1, self.minimum_rate, self.extra_rate)
        if not math.isfinite(self.matching_weight) or not 0 < self.matching_weight < 1:
            raise ValueError("invalid matching weight")


def definition(config):
    out = base_definition(config)
    out.update(
        kernel_id=KERNEL_ID, state_schema=STATE_SCHEMA, hypothesis_id="threemind.hypotheses/weight-dependent-decay1"
    )
    out["operators"].append(dict(id="threemind.experimental-weight-dependent-decay/1", phase="connection-projection"))
    return out


class CandidateEngine(Local53Engine):
    dynamics = KERNEL_ID
    state_schema = STATE_SCHEMA
    config_type = CandidateConfig
    definition = staticmethod(definition)

    def _decay_value(self, row, field, seconds):
        c = self.config
        if field != "weight" or c.edge_rule == "inverse-logarithmic":
            return super()._decay_value(row, field, seconds)
        if c.edge_rule.startswith("weight-"):
            value = exact_weight(row.weight, seconds, c.minimum_rate, c.extra_rate)
        else:
            rate = c.minimum_rate + c.extra_rate * (1 - c.matching_weight)
            value = row.weight * math.exp(-rate * seconds)
        object.__setattr__(row, field, value)
        # Retained for full-state compatibility and diagnostics; unused by this law.
        row.decay_age += seconds / row.half_life

    def reconfigure(self, config):
        if any(
            getattr(config, n) != getattr(self.config, n)
            for n in ("edge_rule", "minimum_rate", "extra_rate", "matching_weight")
        ):
            raise ValueError("experimental decay law fixed at birth")
        super().reconfigure(config)


def configuration(seed, rule, energy_seed=None, **kwargs):
    speed = "slow" if rule.endswith("slow") else "fast"
    return CandidateConfig(
        seed=seed,
        energy_seed=seed ^ 0x31E629 if energy_seed is None else energy_seed,
        edge_rule=rule,
        extra_rate=EXTRA_RATES[speed],
        **kwargs,
    )


def create(seed=None, rule=None, state=None, energy_seed=None, **kwargs):
    if state is not None:
        return CandidateEngine(state=StateImage.from_dict(state))
    return CandidateEngine(configuration(seed, rule, energy_seed, **kwargs))


def projected_weight(edge, rule, seconds):
    """Conditional no-further-reinforcement calculation, never a subject advance."""
    c = configuration(1, rule)
    if rule == "inverse-logarithmic":
        return decay_value(edge["weight"], edge["decay_age"], edge["half_life"], seconds, c)[0]
    if rule.startswith("weight-"):
        return exact_weight(edge["weight"], seconds, c.minimum_rate, c.extra_rate)
    return edge["weight"] * math.exp(-(c.minimum_rate + c.extra_rate * (1 - c.matching_weight)) * seconds)
