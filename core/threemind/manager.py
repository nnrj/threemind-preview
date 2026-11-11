from __future__ import annotations

from threading import RLock
from typing import Any

from .model import ModelPackage
from .runtime import ConsciousnessRuntime


class RuntimeManager:
    def __init__(self, initial: ConsciousnessRuntime | None = None):
        self._lock = RLock()
        self.instances: dict[str, ConsciousnessRuntime] = (
            {initial.consciousness_id: initial} if initial is not None else {}
        )
        self.active_id: str | None = initial.consciousness_id if initial is not None else None

    def add(self, runtime: ConsciousnessRuntime, *, activate: bool = True) -> ConsciousnessRuntime:
        with self._lock:
            self.instances[runtime.consciousness_id] = runtime
            if activate:
                self.active_id = runtime.consciousness_id
            return runtime

    def replace_active(self, runtime: ConsciousnessRuntime, *, reason: str = "replaced by new consciousness") -> ConsciousnessRuntime:
        """Replace the selected instance rather than retaining a stopped twin.

        This is intentionally distinct from ``add``: multi-instance creation
        keeps an existing consciousness, whereas the legacy "new/overwrite"
        operation promises to replace it.
        """
        with self._lock:
            previous = self.instances.pop(self.active_id, None) if self.active_id is not None else None
            if previous is not None:
                previous.stop(reason)
            self.instances[runtime.consciousness_id] = runtime
            self.active_id = runtime.consciousness_id
            return runtime

    def replace(self, runtime: ConsciousnessRuntime, *, activate: bool = True, reason: str = "replaced by restored archive") -> ConsciousnessRuntime:
        """Replace one instance by identity without leaving its old thread alive.

        Archive restoration keeps a consciousness id, unlike cloning or a
        fresh birth.  Replacing through this method prevents the previous
        runtime for the same id from continuing invisibly in the background.
        """
        with self._lock:
            previous = self.instances.get(runtime.consciousness_id)
            if previous is not None and previous is not runtime:
                previous.stop(reason)
            self.instances[runtime.consciousness_id] = runtime
            if activate:
                self.active_id = runtime.consciousness_id
            return runtime

    def get(self, consciousness_id: str) -> ConsciousnessRuntime:
        with self._lock:
            try:
                return self.instances[consciousness_id]
            except KeyError as exc:
                raise KeyError(f"consciousness not found: {consciousness_id}") from exc

    def activate(self, consciousness_id: str) -> ConsciousnessRuntime:
        runtime = self.get(consciousness_id)
        with self._lock:
            self.active_id = runtime.consciousness_id
        return runtime

    def active(self) -> ConsciousnessRuntime:
        with self._lock:
            if self.active_id is None:
                raise KeyError("no active consciousness")
            consciousness_id = self.active_id
        return self.get(consciousness_id)

    def remove(self, consciousness_id: str, reason: str = "removed") -> None:
        with self._lock:
            runtime = self.instances.pop(consciousness_id)
            runtime.stop(reason)
            if self.active_id == consciousness_id and self.instances:
                self.active_id = next(iter(self.instances))
            elif self.active_id == consciousness_id:
                self.active_id = None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [runtime.metrics() | {"id": runtime.consciousness_id, "status": runtime.life_state, "running": runtime.running(), "active": runtime.consciousness_id == self.active_id, "kernel": runtime.manifest.kernel_id, "parent_id": runtime.package.state.get("parent_id"), "snapshots": len(runtime.package.snapshots), "portraits": len(runtime.package.portraits), "metrics": runtime.metrics()} for runtime in self.instances.values()]

    def stop_all(self) -> None:
        with self._lock:
            for runtime in self.instances.values():
                runtime.stop("Core shutdown")
