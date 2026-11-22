"""Analytic local deletion deadlines; shared decay equations are unchanged."""

import math

from .decay60 import decay_value, grow

__all__ = ["crossing_seconds", "decay_value", "grow"]

# Beyond this horizon, recheck this object alone rather than overflow a clock.
RECHECK_SECONDS = 1e12


def crossing_seconds(value, age, timescale, threshold, config):
    """Time to equality; caller adds a microsecond for strict '<' deletion.

    Solve the single-age curve directly, then invert accumulated decay age.
    A bounded local recheck covers numerically unrepresentable distant tails.
    """
    if threshold <= 0:
        return None
    if value <= threshold:
        return 0.0
    ratio = value / threshold
    curve, switch = config.decay_curve, config.decay_transition_age
    try:
        if curve == "exponential":
            delta = math.log(ratio) / math.log(2.0)
        elif curve == "power-law":
            delta = (1 + age) * (ratio - 1)
        elif curve == "inverse-logarithmic":
            k = math.expm1(1.0)
            base = math.log1p(k * age) if age < 1e300 else math.log(age) + math.log(k)
            delta = (1 / k + age) * math.expm1((ratio - 1) * (1 + base))
        elif age >= switch:
            delta = (1 + switch) * math.log(ratio)
        else:
            target = (1 + age) * ratio - 1
            delta = (
                target - age
                if target <= switch
                else switch - age + (1 + switch) * math.log((1 + target) / (1 + switch))
            )
        rate = config.memory_half_life_decay_rate if config.retention_relaxation_enabled else 0.0
        lower = config.memory_half_life_min_s
        falling_age = math.log(timescale / lower) / rate if rate > 0 else 0.0
        if rate > 0 and delta <= falling_age:
            seconds = timescale * -math.expm1(-rate * delta) / rate
        elif rate > 0:
            seconds = (timescale - lower) / rate + (delta - falling_age) * lower
        else:
            seconds = delta * timescale
    except OverflowError:
        return RECHECK_SECONDS
    return min(RECHECK_SECONDS, max(0.0, seconds))
