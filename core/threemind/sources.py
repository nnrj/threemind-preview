from __future__ import annotations

import queue
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class StimulusEnvelope:
    text: str
    source: str = "manual"
    intensity: float = 1.0
    submitted_at: float = 0.0
    id: str = ""

    def __post_init__(self) -> None:
        self.submitted_at = self.submitted_at or time.time()
        self.id = self.id or str(uuid.uuid4())
        self.intensity = max(0.0, min(2.0, float(self.intensity)))
        if not self.text.strip():
            raise ValueError("stimulus text cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StimulusBus:
    """Thread-safe boundary between external sources and the Core."""

    def __init__(self) -> None:
        self._queue: queue.Queue[StimulusEnvelope] = queue.Queue()

    def publish(self, envelope: StimulusEnvelope) -> dict[str, Any]:
        self._queue.put(envelope)
        return envelope.to_dict()

    def drain(self, limit: int = 64) -> list[StimulusEnvelope]:
        items: list[StimulusEnvelope] = []
        for _ in range(max(1, limit)):
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def size(self) -> int:
        return self._queue.qsize()
