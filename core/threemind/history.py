"""Asynchronous durable checkpoints for external consciousness history.

The associative runtime intentionally owns no database connection.  This host
layer receives immutable copies through :meth:`ConsciousnessRuntime.history_snapshot`
and writes them via the configured persistence backend.  A checkpoint always
contains the complete record history for one consciousness, so coalescing a
busy sequence of requests changes write frequency but never deliberately drops
an individual stimulus, observation, interpretation, or event.
"""

from __future__ import annotations

import time
from queue import Queue
from threading import Event, RLock, Thread
from typing import Any, Callable, Protocol


class HistorySource(Protocol):
    consciousness_id: str

    def history_snapshot(self) -> dict[str, Any]: ...


class PersistenceTarget(Protocol):
    def put(self, key: str, value: dict[str, Any]) -> None: ...


class HistoryCheckpointWriter:
    """Coalesce durable history writes outside the Core tick thread.

    ``schedule`` is safe to call for every frame or event.  At most one write
    per consciousness is active at a time; if records change while it writes,
    the latest complete snapshot is queued again.  A failed backend write is
    retained and retried, rather than silently discarding the history.
    """

    def __init__(self, backend_getter: Callable[[], PersistenceTarget]) -> None:
        self._backend_getter = backend_getter
        self._queue: Queue[str | None] = Queue()
        self._pending: dict[str, HistorySource] = {}
        self._queued: set[str] = set()
        self._lock = RLock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._writes = 0
        self._failures = 0
        self._last_error = ""
        self._last_saved: dict[str, int] = {}

    @staticmethod
    def key(consciousness_id: str) -> str:
        return f"history:{consciousness_id}"

    def start(self) -> None:
        with self._lock:
            self._stop.clear()
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = Thread(target=self._run, name="threemind-history-checkpoint", daemon=True)
            self._thread.start()

    def running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def schedule(self, source: HistorySource) -> None:
        """Request a latest-state checkpoint without blocking the caller."""
        consciousness_id = str(source.consciousness_id)
        with self._lock:
            self._pending[consciousness_id] = source
            if consciousness_id not in self._queued:
                self._queued.add(consciousness_id)
                self._queue.put(consciousness_id)

    def flush(self, *, timeout: float = 10.0) -> bool:
        """Wait for currently requested writes; return false on timeout."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while time.monotonic() <= deadline:
            with self._lock:
                if not self._pending and not self._queued:
                    return True
            time.sleep(.01)
        return False

    def stop(self, *, flush: bool = True, timeout: float = 10.0) -> bool:
        flushed = self.flush(timeout=timeout) if flush else False
        self._stop.set()
        self._queue.put(None)
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=max(.1, timeout))
        with self._lock:
            self._thread = None
        return flushed

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": bool(self._thread and self._thread.is_alive()),
                "pending": len(self._pending),
                "queued": len(self._queued),
                "writes": self._writes,
                "failures": self._failures,
                "last_error": self._last_error,
                "last_saved": dict(self._last_saved),
            }

    def _retry(self, consciousness_id: str, source: HistorySource) -> None:
        """Keep the most recent source alive until a failed backend recovers."""
        with self._lock:
            self._pending[consciousness_id] = source
            self._queued.discard(consciousness_id)
        # A retry delay prevents an unavailable remote backend from spinning a
        # CPU core.  It is not a history retention window; the complete latest
        # checkpoint remains queued while the backend is unavailable.
        if not self._stop.wait(.5):
            with self._lock:
                if consciousness_id in self._pending and consciousness_id not in self._queued:
                    self._queued.add(consciousness_id)
                    self._queue.put(consciousness_id)

    def _run(self) -> None:
        while True:
            consciousness_id = self._queue.get()
            if consciousness_id is None:
                return
            with self._lock:
                source = self._pending.pop(consciousness_id, None)
            if source is None:
                with self._lock:
                    self._queued.discard(consciousness_id)
                continue
            try:
                document = source.history_snapshot()
                document["key"] = self.key(consciousness_id)
                self._backend_getter().put(self.key(consciousness_id), document)
            except Exception as error:  # A database outage must not kill Core.
                with self._lock:
                    self._failures += 1
                    self._last_error = f"{type(error).__name__}: {error}"
                self._retry(consciousness_id, source)
                continue
            with self._lock:
                self._writes += 1
                self._last_error = ""
                try:
                    self._last_saved[consciousness_id] = int(document.get("history_revision", 0))
                except (TypeError, ValueError):
                    self._last_saved[consciousness_id] = 0
                self._queued.discard(consciousness_id)
                # A change may have arrived while the source was copied and
                # saved.  Its pending entry now represents a newer complete
                # checkpoint, so enqueue it without dropping anything.
                if consciousness_id in self._pending and not self._stop.is_set():
                    self._queued.add(consciousness_id)
                    self._queue.put(consciousness_id)
