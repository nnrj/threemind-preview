"""Local numerical primitives. These alone are not an executable new kernel.

All time is simulated time. See docs/*/plans/candidate-mechanisms.md for
equations, units, phases, evidence and limits; no semantic target enters here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from threemind_core.spec import timestamp


def number(value, name, *, low=0.0, high=1e12):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if not low <= value <= high:
        raise ValueError(f"{name} must lie in [{low}, {high}]")
    return float(value)


def elapsed(now, previous):
    now, previous = timestamp(now), timestamp(previous)
    if now < previous:
        raise ValueError("operator time cannot go backwards")
    return (now - previous) / 1e6


def cascade(dt: float, source_tau: float, target_tau: float) -> float:
    """Integral response to exp(-t/source_tau), divided by target_tau.

    Stable for equal or nearly equal time constants; the positive-argument
    expm1 branch is avoided so geological elapsed time cannot overflow.
    """
    rate = 1.0 / target_tau - 1.0 / source_tau
    if rate == 0.0:
        return (dt / target_tau) * math.exp(-dt / target_tau)
    if rate > 0:
        return math.exp(-dt / source_tau) * -math.expm1(-dt * rate) / (target_tau * rate)
    return math.exp(-dt / target_tau) * math.expm1(dt * rate) / (target_tau * rate)


@dataclass(frozen=True)
class ShortTermConfig:
    utilization: float = 0.5
    recovery_tau_s: float = 0.8
    active_tau_s: float = 0.003
    facilitation_tau_s: float = 0.0  # 0 explicitly means no facilitation.

    def __post_init__(self):
        number(self.utilization, "utilization", high=1.0)
        number(self.recovery_tau_s, "recovery_tau_s", low=1e-6, high=1e9)
        number(self.active_tau_s, "active_tau_s", low=1e-6, high=1e9)
        number(self.facilitation_tau_s, "facilitation_tau_s", high=1e9)


@dataclass(frozen=True)
class ShortTermState:
    available: float = 1.0
    active: float = 0.0
    utilization: float = 0.0
    time_us: int = 0

    def __post_init__(self):
        for name in ("available", "active", "utilization"):
            number(getattr(self, name), name, high=1.0)
        if self.available + self.active > 1.0 + 1e-14:
            raise ValueError("short-term resources exceed one")
        timestamp(self.time_us)

    def recovered(self, when: int, config: ShortTermConfig):
        dt = elapsed(when, self.time_us)
        if dt == 0:
            return self
        active = self.active * math.exp(-dt / config.active_tau_s)
        inactive = max(0.0, 1.0 - self.available - self.active)
        # dz/dt = y/tau_active - z/tau_recovery; x = 1-y-z.
        inactive = inactive * math.exp(-dt / config.recovery_tau_s) + self.active * (
            config.recovery_tau_s / config.active_tau_s
        ) * cascade(dt, config.active_tau_s, config.recovery_tau_s)
        available = min(1.0, max(0.0, 1.0 - active - inactive))
        utilization = (
            self.utilization * math.exp(-dt / config.facilitation_tau_s)
            if config.facilitation_tau_s > 0
            else config.utilization
        )
        return ShortTermState(available, active, utilization, timestamp(when))

    def release(self, when: int, config: ShortTermConfig):
        state = self.recovered(when, config)
        u = (
            state.utilization + config.utilization * (1.0 - state.utilization)
            if config.facilitation_tau_s > 0
            else config.utilization
        )
        released = u * state.available
        return ShortTermState(state.available - released, state.active + released, u, timestamp(when)), released


@dataclass(frozen=True)
class FastTraceConfig:
    tau_s: float = 2.0
    learning_rate: float = 0.1
    gain: float = 0.1

    def __post_init__(self):
        number(self.tau_s, "fast tau_s", low=1e-6, high=1e9)
        number(self.learning_rate, "fast learning_rate", high=1.0)
        number(self.gain, "fast gain", high=1.0)


@dataclass(frozen=True)
class FastTrace:
    value: float = 0.0
    time_us: int = 0

    def __post_init__(self):
        number(self.value, "fast trace", high=1.0)
        timestamp(self.time_us)

    def projected(self, when: int, config: FastTraceConfig) -> float:
        return self.value * math.exp(-elapsed(when, self.time_us) / config.tau_s)

    def transmit(self, amount: float, when: int, config: FastTraceConfig):
        amount = number(amount, "transmitted amount")
        value = self.projected(when, config)
        # Bounded local leaky integrator; no target-node state or semantic reward.
        value += -math.expm1(-config.learning_rate * amount) * (1.0 - value)
        return FastTrace(value, timestamp(when))

    def efficacy(self, slow_weight: float, when: int, config: FastTraceConfig) -> float:
        weight = number(slow_weight, "slow weight", high=1.0)
        return min(1.0, weight + config.gain * self.projected(when, config))


def local_attention(query, keys, amounts, *, temperature=1.0, mix=1.0):
    """Allocate reception among already delivered messages at ONE receiver.

    Returns the effective response and all allocation coefficients. Callers retain
    raw arrivals and transmission costs. This is fixed-feature local attention,
    not a trained Transformer and not a causal/semantic relevance detector.
    """
    number(temperature, "temperature", low=1e-6, high=1e6)
    number(mix, "attention mix", high=1.0)
    if not 1 <= len(query) <= 64 or len(keys) != len(amounts):
        raise ValueError("invalid local attention dimensions")
    for value in query:
        number(value, "query", low=-1.0, high=1.0)
    for key in keys:
        if len(key) != len(query):
            raise ValueError("local key dimension differs from query")
        for value in key:
            number(value, "key", low=-1.0, high=1.0)
    for amount in amounts:
        number(amount, "arrival")
    if not amounts:
        return 0.0, []
    scores = [sum(q * k for q, k in zip(query, key)) / math.sqrt(len(query)) / temperature for key in keys]
    maximum = max(scores)
    weights = [math.exp(score - maximum) for score in scores]
    total = sum(weights)
    weights = [weight / total for weight in weights]
    coefficients = [(1.0 - mix) + mix * weight for weight in weights]
    return sum(amount * factor for amount, factor in zip(amounts, coefficients)), coefficients


def membrane_response(
    voltage_mv, current_na, dt_s, *, rest_mv=-65.0, resistance_mohm=100.0, membrane_tau_s=0.02, current_tau_s=0.005
):
    """Exact passive RC response to an exponentially decaying current.

    This primitive deliberately does not hide threshold/reset/refractory inside
    a voltage clip. A complete LIF kernel must separately schedule those events.
    mV = MOhm * nA. No injected current or initial voltage is invented here.
    """
    number(voltage_mv, "voltage_mv", low=-1e9, high=1e9)
    number(rest_mv, "rest_mv", low=-1e9, high=1e9)
    number(current_na, "current_na", low=-1e9, high=1e9)
    number(dt_s, "dt_s", high=1e40)
    number(resistance_mohm, "resistance_mohm", low=1e-6, high=1e9)
    number(membrane_tau_s, "membrane_tau_s", low=1e-6, high=1e9)
    number(current_tau_s, "current_tau_s", low=1e-6, high=1e9)
    voltage = rest_mv + (voltage_mv - rest_mv) * math.exp(-dt_s / membrane_tau_s)
    voltage += resistance_mohm * current_na * cascade(dt_s, current_tau_s, membrane_tau_s)
    return voltage, current_na * math.exp(-dt_s / current_tau_s)
