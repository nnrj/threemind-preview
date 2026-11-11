"""A minimal simulated body between ambient environment and ThreeMind input."""
from __future__ import annotations

import hashlib
import math
import random

from threemind.frames import SensoryFrame


class BodyAdapter:
    """Filters an incoming ambient frame before it reaches the input bus.

    This is deliberately a sensory limitation, not a cognitive selection rule:
    it has thresholds, sampling, adaptation and noise, but no meanings or
    preferences about particular environmental content.
    """

    def __init__(self, seed: int, *, sampling_ticks: int = 1, threshold: float = 0.035, adaptation: float = 0.55, noise: float = 0.02, channel_count: int = 3) -> None:
        self.seed = int(seed)
        self.sampling_ticks = max(1, int(sampling_ticks))
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self.adaptation = max(0.0, min(1.0, float(adaptation)))
        self.noise = max(0.0, min(0.5, float(noise)))
        self.channel_count = max(1, min(64, int(channel_count)))
        self._baseline: dict[int, float] = {}

    def configure(self, config: dict[str, object]) -> None:
        self.sampling_ticks = max(1, int(config.get("sampling_ticks", self.sampling_ticks)))
        self.threshold = max(0.0, min(1.0, float(config.get("threshold", self.threshold))))
        self.adaptation = max(0.0, min(1.0, float(config.get("adaptation", self.adaptation))))
        self.noise = max(0.0, min(0.5, float(config.get("noise", self.noise))))
        self.channel_count = max(1, min(64, int(config.get("channel_count", self.channel_count))) )

    def filter_frame(self, frame: SensoryFrame, tick: int, *, bypass_filter: bool = False) -> SensoryFrame | None:
        """Apply sensory sampling/adaptation to an environmental frame.

        The body does not manufacture the world.  It only decides which
        changes in a supplied environmental field become sensory pulses.
        """
        if tick % self.sampling_ticks:
            return None
        rng = random.SystemRandom()
        # Never select the first N dictionary entries: that accidentally turns
        # carrier insertion order into a congenital body map.  First encode
        # the complete environmental frame, then retain the strongest current
        # sensory changes if this experimental body has a channel capacity.
        raw = list(frame.channels.items())
        sensed: dict[int, float] = {}
        for channel, value in raw:
            value = max(0.0, min(1.0, value + rng.uniform(-self.noise, self.noise)))
            prior = self._baseline.get(channel, value)
            change = abs(value - prior)
            # Adaptation removes part of a stable signal; a small leak keeps the
            # background continuous rather than converting it into a pulse-only world.
            encoded = max(0.0, value * (1.0 - self.adaptation) + change * self.adaptation)
            self._baseline[channel] = prior * .92 + value * .08
            if encoded >= self.threshold:
                sensed[channel] = encoded
        if len(sensed) > self.channel_count:
            sensed = dict(sorted(sensed.items(), key=lambda item: (-item[1], item[0]))[:self.channel_count])
        if not sensed:
            return None
        return SensoryFrame(source="body-filtered-environment", channels=sensed, intensity=frame.intensity, bypass_filter=bypass_filter)


class InteroceptiveAdapter:
    """Optional internal-body signal source, separate from the environment."""

    def __init__(self, seed: int, *, channel_count: int = 2, amplitude: float = .08) -> None:
        self.seed = int(seed); self.channel_count = max(1, min(64, int(channel_count))); self.amplitude = max(0.0, min(1.0, float(amplitude)))

    def configure(self, config: dict[str, object]) -> None:
        self.channel_count = max(1, min(64, int(config.get("channel_count", self.channel_count))))
        self.amplitude = max(0.0, min(1.0, float(config.get("amplitude", self.amplitude))))

    def _channel(self, index: int) -> int:
        key = self.seed.to_bytes(16, "big", signed=False)
        return int.from_bytes(hashlib.blake2b(f"interoception:{index}".encode(), key=key, digest_size=8).digest(), "big") % 8192

    def frame(self, tick: int, *, intensity: float, bypass_filter: bool = False) -> SensoryFrame:
        # This is deliberately an opt-in experimental source, never a default
        # replacement for environmental stimulation.
        values = {self._channel(index): self.amplitude * (0.35 + 0.65 * (math.sin(tick / (9.0 + index * 7.0)) + 1.0) / 2.0) for index in range(self.channel_count)}
        return SensoryFrame(source="interoceptive-body", channels=values, intensity=max(0.0, min(2.0, float(intensity))), external=True, bypass_filter=bypass_filter)


class MetabolicEnergyAdapter:
    """Finite-rate external supply for Core's optional energy ledger.

    This adapter never ranks, filters or weakens sensory channels.  It offers
    at most one configured amount for each observed Core tick and therefore
    cannot manufacture a hidden recovery rule inside the consciousness.
    """

    id = "energy-budget"

    def __init__(self, *, supply_per_tick: float = .004, total_supply_limit: float = 0.0) -> None:
        self.supply_per_tick = max(0.0, float(supply_per_tick))
        self.total_supply_limit = max(0.0, float(total_supply_limit))
        self.supplied_total = 0.0
        self._last_tick: int | None = None

    def configure(self, config: dict[str, object]) -> None:
        self.supply_per_tick = max(0.0, float(config.get("supply_per_tick", self.supply_per_tick)))
        self.total_supply_limit = max(0.0, float(config.get("total_supply_limit", self.total_supply_limit)))

    def supply_for_tick(self, tick: int) -> float:
        current = int(tick)
        if self._last_tick == current:
            return 0.0
        self._last_tick = current
        amount = self.supply_per_tick
        if self.total_supply_limit > 0.0:
            amount = min(amount, max(0.0, self.total_supply_limit - self.supplied_total))
        return amount

    def record_accepted(self, amount: float) -> None:
        """Account only energy that Core actually accepted into its reserve."""
        self.supplied_total += max(0.0, float(amount))

    def status(self) -> dict[str, float | int | None]:
        return {
            "supply_per_tick": self.supply_per_tick,
            "total_supply_limit": self.total_supply_limit,
            "supplied_total": round(self.supplied_total, 8),
            "last_tick": self._last_tick,
        }


# Read-only import compatibility for early, unpublished ThreeMind builds.  The
# behavior is intentionally the new supply adapter, not the old attention
# score/budget modulator.
EnergyBudgetModulator = MetabolicEnergyAdapter
