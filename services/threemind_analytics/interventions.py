from __future__ import annotations

"""Experiment-only intervention policies and their durable audit records."""

import copy
import time
import uuid
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable


@dataclass(slots=True)
class InterventionPolicy:
    """A visible, reversible functional-silencing policy.

    Core treats this through a generic optional boundary.  With no policy
    attached, every check is a no-op and normal dynamics are byte-for-byte on
    the same path as before.
    """

    intervention_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: str = "silence"
    node_ids: frozenset[int] = field(default_factory=frozenset)
    edge_pairs: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    label: str = "experimental intervention"

    def node_silenced(self, node_id: int) -> bool:
        return int(node_id) in self.node_ids

    def edge_silenced(self, source: int, target: int) -> bool:
        return (int(source), int(target)) in self.edge_pairs or self.node_silenced(source) or self.node_silenced(target)

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.intervention_id,
            "mode": self.mode,
            "label": self.label,
            "node_ids": sorted(self.node_ids),
            "edge_pairs": [list(pair) for pair in sorted(self.edge_pairs)],
        }


class InterventionStore:
    """Small indexed records over the configured generic persistence backend."""

    INDEX_KEY = "threemind:intervention-pairs:index:v1"

    def __init__(self, backend_getter: Callable[[], Any]) -> None:
        self._backend_getter = backend_getter
        self._lock = RLock()

    @staticmethod
    def key(pair_id: str) -> str:
        return f"threemind:intervention-pair:{pair_id}"

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            stored = copy.deepcopy(record)
            stored.setdefault("id", str(uuid.uuid4()))
            stored["record_type"] = "threemind_intervention_pair/v1"
            stored["updated_at"] = time.time()
            backend = self._backend_getter()
            backend.put(self.key(str(stored["id"])), stored)
            index = backend.get(self.INDEX_KEY)
            rows = list(index.get("items", [])) if isinstance(index, dict) else []
            rows = [row for row in rows if isinstance(row, dict) and row.get("id") != stored["id"]]
            rows.append({key: stored.get(key) for key in ("id", "title", "status", "created_at", "updated_at", "source_consciousness_id", "control_runtime_id", "intervention_runtime_id", "mode")})
            rows.sort(key=lambda row: float(row.get("updated_at") or 0), reverse=True)
            backend.put(self.INDEX_KEY, {"record_type": "threemind_intervention_index/v1", "items": rows})
            return stored

    def get(self, pair_id: str) -> dict[str, Any] | None:
        value = self._backend_getter().get(self.key(pair_id))
        return copy.deepcopy(value) if isinstance(value, dict) else None

    def list(self) -> list[dict[str, Any]]:
        value = self._backend_getter().get(self.INDEX_KEY)
        return copy.deepcopy(value.get("items", [])) if isinstance(value, dict) else []
