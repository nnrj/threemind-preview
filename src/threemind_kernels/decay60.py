"""Single-value decay laws for /6.0. Queries never change a clock or state."""

import math

from .decay52 import advance_age

CURVES = ("exponential", "power-law", "inverse-logarithmic", "power-exponential")


def log_remaining(curve, age, transition=10.0):
    if not math.isfinite(age) or age < 0 or not math.isfinite(transition) or transition <= 0:
        raise ValueError("finite nonnegative age and positive transition required")
    if curve == "exponential":
        return -math.log(2.0) * age
    if curve == "power-law":
        return -math.log1p(age)
    if curve == "inverse-logarithmic":
        k = math.expm1(1.0)
        inner = math.log1p(k * age) if age < 1e300 else math.log(age) + math.log(k)
        return -math.log1p(inner)
    if curve == "power-exponential":
        return (
            -math.log1p(age) if age <= transition else -math.log1p(transition) - (age - transition) / (1 + transition)
        )
    raise ValueError("unknown decay curve")


def decay_value(value, age, timescale, seconds, config):
    """Return (current value, accumulated normalized age, current timescale).

    A reinforcement changes the current value, not a list of old contributions.
    The exponential tail uses the elapsed age directly to avoid subtracting two
    large, nearly equal logarithms. No threshold-crossing search is needed.
    """
    delta, end = advance_age(
        timescale,
        seconds,
        config.memory_half_life_min_s,
        config.memory_half_life_decay_rate if config.retention_relaxation_enabled else 0.0,
    )
    new_age = age + delta
    curve, switch = config.decay_curve, config.decay_transition_age
    if curve == "exponential":
        log_ratio = -math.log(2.0) * delta
    elif curve == "power-law":
        log_ratio = -math.log1p(delta / (1 + age))
    elif curve == "power-exponential" and age >= switch:
        log_ratio = -delta / (1 + switch)
    else:
        log_ratio = log_remaining(curve, new_age, switch) - log_remaining(curve, age, switch)
    return value * math.exp(min(0.0, log_ratio)), new_age, end


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
