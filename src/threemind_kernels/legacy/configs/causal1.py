from __future__ import annotations

import math
from dataclasses import asdict, dataclass

SCHEMA = "threemind.state/2"
DYNAMICS = "threemind.causal/1"
MAX_TIME = 2**128 - 1


def timestamp(value: int | str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("time must be an integer number of microseconds")  # noqa: TRY004 -- public protocol validation contract
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
        raise ValueError("time must be an unsigned decimal integer")
    result = int(value)
    if not 0 <= result <= MAX_TIME:
        raise ValueError("time exceeds the unsigned 128-bit microsecond range")
    return result


@dataclass(frozen=True, slots=True)
class Config:
    step_us: int = 10_000
    delay_us: int = 10_000
    activation_tau: float = 0.3044
    trace_tau: float = 0.504
    inhibition_tau: float = 0.2321
    stability_tau: float = 666.667
    support_tau: float = 666.667
    propagation_rate: float = 4.2
    direct_gain: float = 0.9
    learning_rate: float = 0.0055  # Weight impulse per delivered external event, not per solver step.
    birth_weight: float = 0.065
    first_gain: float = 0.045
    repeat_gain: float = 0.018
    intensity_gain: float = 0.075
    associative_gain: float = 0.01
    stability_gain: float = 0.022
    support_gain: float = 0.035
    forgetting_rate: float = 0.025
    inhibition_gain: float = 0.24
    inhibition_diffusion_rate: float = 3.5
    inhibition_response_gain: float = 2.0
    activation_floor: float = 0.00001
    prune_weight: float = 0.008
    prune_support: float = 0.00001
    plasticity: bool = True
    inhibition: bool = True
    seed: int = 20260724

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if name in ("plasticity", "inhibition"):
                if type(value) is not bool:
                    raise ValueError(f"{name} must be boolean")
            elif name in ("step_us", "delay_us", "seed"):
                if type(value) is not int or not 0 <= value <= 2**53 - 1:
                    raise ValueError(f"{name} must be a safe unsigned integer")
            elif (
                isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0
            ):
                raise ValueError(f"{name} must be finite and nonnegative")
            else:
                object.__setattr__(self, name, float(value))
        if self.step_us < 1 or self.delay_us < 1:
            raise ValueError("numerical step and causal delay must be positive")
        if any(
            getattr(self, n) <= 0
            for n in ("activation_tau", "trace_tau", "inhibition_tau", "stability_tau", "support_tau")
        ):
            raise ValueError("time constants must be positive")
        if not 0 < self.activation_floor < 1 or self.birth_weight > 1 or self.prune_weight >= 1:
            raise ValueError("invalid activation/weight threshold")


@dataclass(frozen=True, slots=True)
class Stimulus:
    time_us: int
    channels: tuple[tuple[int, float], ...]
    intensity: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "time_us", timestamp(self.time_us))
        object.__setattr__(self, "intensity", float(self.intensity))
        if not math.isfinite(self.intensity) or self.intensity < 0:
            raise ValueError("intensity must be finite and nonnegative")
        seen: set[int] = set()
        for channel, value in self.channels:
            if type(channel) is not int or not 0 <= channel < 2**32 or channel in seen:
                raise ValueError("channels must be unique unsigned 32-bit integers")
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("channel amplitude must lie in [0, 1]")
            seen.add(channel)
        object.__setattr__(self, "channels", tuple((channel, float(value)) for channel, value in self.channels))

    def to_dict(self) -> dict:
        return {"time_us": str(self.time_us), "channels": [list(c) for c in self.channels], "intensity": self.intensity}

    @classmethod
    def from_dict(cls, data: dict) -> Stimulus:
        if set(data) - {"time_us", "channels", "intensity"}:
            raise ValueError("unknown stimulus fields")
        return cls(
            timestamp(data["time_us"]),
            tuple((c, float(v)) for c, v in data["channels"]),
            float(data.get("intensity", 1.0)),
        )
