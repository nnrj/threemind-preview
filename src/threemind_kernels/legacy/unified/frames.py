"""Core input protocol: anonymous sensory pulses only."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4
from typing import Any


@dataclass(slots=True)
class SensoryFrame:
    source: str
    channels: dict[int, float]
    intensity: float = 1.0
    external: bool = True
    bypass_filter: bool = False

    @property
    def energy(self) -> float:
        return sum(abs(value) for value in self.channels.values()) * self.intensity


@dataclass(slots=True)
class ScheduledSensoryFrame:
    """One causally ordered delivery unit on the InputBus.

    ``due_epoch`` is host-facing logical time, deliberately distinct from a
    runtime tick.  Several sensory devices may emit during one environmental
    epoch, but they are never merged into one Core event: the runtime advances
    once for each scheduled frame in stable ``sequence`` order.

    The object carries no semantic interpretation of a carrier.  Its optional
    metadata is audit information owned by the host/input boundary.
    """

    frame: SensoryFrame
    due_epoch: int
    sequence: int
    envelope_id: str
    frame_index: int = 0
    frame_count: int = 1
    adapter_id: str = "unknown"
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.frame.source,
            "channels": {str(key): float(value) for key, value in self.frame.channels.items()},
            "intensity": float(self.frame.intensity),
            "external": bool(self.frame.external),
            "bypass_filter": bool(self.frame.bypass_filter),
            "due_epoch": int(self.due_epoch),
            "sequence": int(self.sequence),
            "envelope_id": self.envelope_id,
            "frame_index": int(self.frame_index),
            "frame_count": int(self.frame_count),
            "adapter_id": self.adapter_id,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ScheduledSensoryFrame":
        return cls(
            frame=SensoryFrame(
                source=str(raw.get("source", "unknown")),
                channels={int(key): float(value) for key, value in dict(raw.get("channels", {})).items()},
                intensity=float(raw.get("intensity", 1.0)),
                external=bool(raw.get("external", True)),
                bypass_filter=bool(raw.get("bypass_filter", False)),
            ),
            due_epoch=max(0, int(raw.get("due_epoch", 0))),
            sequence=max(0, int(raw.get("sequence", 0))),
            envelope_id=str(raw.get("envelope_id") or uuid4()),
            frame_index=max(0, int(raw.get("frame_index", 0))),
            frame_count=max(1, int(raw.get("frame_count", 1))),
            adapter_id=str(raw.get("adapter_id", "unknown")),
            metadata=dict(raw.get("metadata", {})),
        )


@dataclass(slots=True, frozen=True)
class OutputFrame:
    """Anonymous projection of one runtime tick onto the output boundary.

    Core publishes activity and topology only: never text, labels, tool names,
    or a destination-specific meaning. ``delta.input_envelopes`` may carry
    opaque transport identities and frame positions for external audit; those
    identities contain no carrier content and are never consulted by dynamics.
    External output adapters interpret the projection.
    """

    consciousness_id: str
    tick: int
    life_state: str
    metrics: dict[str, Any]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    delta: dict[str, Any]


class OutputBus:
    """Read-only fan-out bus for complete anonymous internal activity.

    The retained history is intentionally minimal; consumers receive live
    frames and must opt into their own archival policy rather than causing
    Core to truncate the projection.
    """

    def __init__(self, *, history_size: int = 1) -> None:
        self._history: deque[OutputFrame] = deque(maxlen=max(1, history_size))
        self._subscribers: dict[int, Callable[[OutputFrame], None]] = {}
        self._next_subscriber = 1

    def publish(self, frame: OutputFrame) -> None:
        self._history.append(frame)
        # An observer failure is intentionally unable to change Core dynamics.
        for callback in tuple(self._subscribers.values()):
            try:
                callback(frame)
            except Exception:
                continue

    def latest(self) -> OutputFrame | None:
        return self._history[-1] if self._history else None

    def recent(self, limit: int = 32) -> tuple[OutputFrame, ...]:
        return tuple(self._history)[-max(1, int(limit)):]

    def subscribe(self, callback: Callable[[OutputFrame], None]) -> int:
        token = self._next_subscriber
        self._next_subscriber += 1
        self._subscribers[token] = callback
        return token

    def unsubscribe(self, token: int) -> None:
        self._subscribers.pop(int(token), None)
