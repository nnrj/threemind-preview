"""Optional environmental selection protocol.

The default gate is transparent: every frame reaches the associative network
with its encoded drive unchanged.  Selection is an *opt-in* environmental
constraint, supplied by an external modulator such as a finite-energy body.
It is not an intrinsic preference, utility, reward, or semantic target.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .frames import SensoryFrame


@dataclass(frozen=True, slots=True)
class AttentionContext:
    tick: int
    source: str
    channel: int
    strength: float
    novelty: float
    relevance: float


@dataclass(frozen=True, slots=True)
class AttentionAdjustment:
    """An optional environmental modulation.

    ``competition_enabled`` is deliberately explicit.  A multiplier alone
    never causes the runtime to rank or discard channels; this prevents an
    accidentally installed plugin from silently reinstating a default
    attention bias.
    """
    score_multiplier: float = 1.0
    strength_multiplier: float = 1.0
    budget_multiplier: float = 1.0
    competition_enabled: bool = False


class AttentionModulator(Protocol):
    """An external, carrier-agnostic gate plugin."""

    id: str

    def begin_tick(self, tick: int, frames: Iterable[SensoryFrame]) -> AttentionAdjustment: ...
    def adjust(self, context: AttentionContext) -> AttentionAdjustment: ...


class AttentionGate:
    def __init__(self, modulators: Iterable[AttentionModulator] = ()) -> None:
        self._modulators = list(modulators)
        self._tick_adjustment = AttentionAdjustment()

    @property
    def modulator_ids(self) -> list[str]:
        return [item.id for item in self._modulators]

    def replace(self, modulators: Iterable[AttentionModulator]) -> None:
        self._modulators = list(modulators)
        self._tick_adjustment = AttentionAdjustment()

    def begin_tick(self, tick: int, frames: Iterable[SensoryFrame]) -> None:
        score = strength = budget = 1.0
        competition_enabled = False
        snapshot = tuple(frames)
        for modulator in self._modulators:
            try:
                adjustment = modulator.begin_tick(tick, snapshot)
            except Exception:
                continue
            score *= max(0.0, adjustment.score_multiplier)
            strength *= max(0.0, adjustment.strength_multiplier)
            budget *= max(0.0, adjustment.budget_multiplier)
            competition_enabled = competition_enabled or adjustment.competition_enabled
        self._tick_adjustment = AttentionAdjustment(score, strength, budget, competition_enabled)

    def adjust(self, context: AttentionContext) -> AttentionAdjustment:
        score = self._tick_adjustment.score_multiplier
        strength = self._tick_adjustment.strength_multiplier
        budget = self._tick_adjustment.budget_multiplier
        competition_enabled = self._tick_adjustment.competition_enabled
        for modulator in self._modulators:
            try:
                adjustment = modulator.adjust(context)
            except Exception:
                continue
            score *= max(0.0, adjustment.score_multiplier)
            strength *= max(0.0, adjustment.strength_multiplier)
            budget *= max(0.0, adjustment.budget_multiplier)
            competition_enabled = competition_enabled or adjustment.competition_enabled
        return AttentionAdjustment(score, strength, budget, competition_enabled)
