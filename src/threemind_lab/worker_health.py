"""Small out-of-band host measurements, never sensory input or Core state."""

import os
import threading
import time
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

_lock = threading.Lock()
_previous = {}


def sample():
    with _lock:
        now, pid = time.monotonic(), os.getpid()
        if _previous.get("pid") == pid and now - _previous["at"] < 5:
            return deepcopy(_previous["value"])
        value = {
            "version": "threemind.worker-health/1",
            "sample_id": str(uuid4()),
            "sampled_at": datetime.now(UTC).isoformat(),
            "scope": "worker process RSS and CPU; physical host memory; child processes excluded",
            "coverage": "unavailable",
            "rss_mib": None,
            "cpu_percent": None,
            "host_memory_percent": None,
        }
        cpu = None
        try:
            import psutil

            process = psutil.Process(pid)
            times = process.cpu_times()
            cpu = times.user + times.system
            if _previous.get("pid") == pid and _previous.get("cpu") is not None:
                value["cpu_percent"] = max(0.0, 100 * (cpu - _previous["cpu"]) / (now - _previous["at"]))
            value.update(
                rss_mib=process.memory_info().rss / 2**20,
                host_memory_percent=psutil.virtual_memory().percent,
                coverage="observed",
            )
        except Exception as error:  # noqa: BLE001 -- optional diagnostics must not break a lease
            value["reason"] = type(error).__name__
        _previous.update(pid=pid, at=now, cpu=cpu, value=value)
        return deepcopy(value)
