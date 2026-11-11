"""An external rotating pointer observed by four directional light sensors.

Clock time is environment state, never a Core annotation. Only measured light
levels are encoded. The same current reading can follow different experiences.
"""

from dataclasses import dataclass
import math
from threemind_core import Stimulus
from threemind_runtime.receptors import ReceptorWiring


@dataclass(frozen=True)
class TeachingClock:
    period_s: float = 4.0
    origin_s: float = 0.0
    phase_rad: float = 0.0
    seed: int = 71
    gain: float = 0.2

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.period_s, self.origin_s, self.phase_rad, self.gain)):
            raise ValueError("finite physical clock parameters required")
        if self.period_s <= 0 or not 0 <= self.gain <= 1:
            raise ValueError("positive period and bounded sensor gain required")

    def sample(self, seconds):
        if not math.isfinite(seconds):
            raise ValueError("finite environment time required")
        angle = (self.phase_rad + 2 * math.pi * (seconds - self.origin_s) / self.period_s) % (2 * math.pi)
        # Directional photometry: positive projected illumination, not time bins
        # assigned to events or objects. Numerical roundoff at zero is removed.
        levels = [max(0.0, math.cos(angle - i * math.pi / 2)) for i in range(4)]
        levels = [0.0 if v < 1e-12 else v for v in levels]
        return {
            "schema": "threemind.teaching-clock/1",
            "environment_s": seconds,
            "pointer_rad": angle,
            "light_levels": levels,
            "period_s": self.period_s,
            "units": "relative irradiance",
        }

    def frame(self, observation):
        if observation.get("schema") != "threemind.teaching-clock/1":
            raise ValueError("clock measurement version")
        levels = observation["light_levels"]
        if len(levels) != 4 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in levels):
            raise ValueError("four bounded actual measurements required")
        wiring = ReceptorWiring(self.seed)
        return Stimulus(
            0,
            tuple((wiring.identity(0xE10000 + i), float(v) * self.gain) for i, v in enumerate(levels) if v),
            intensity=1.0,
        )
