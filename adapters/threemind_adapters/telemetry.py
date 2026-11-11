"""Physical host telemetry exposed as anonymous sensory frames.

This module belongs to the application-side adapter layer. It observes OS
counters, records their provenance, and maps available measurements to
anonymous non-negative channels. It never reads or changes ThreeMind nodes,
edges, attention, energy, or learning rules.

The collector and encoders are deliberately separate. One collector samples
the computer once; one encoder per consciousness maps that shared sample with
its sensory seed. Unavailable counters remain unavailable--temperature, fan,
GPU, SMART and power values are never estimated from unrelated utilisation.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import platform
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from threemind.frames import SensoryFrame

try:  # Optional: service startup must not depend on psutil.
    import psutil as _psutil  # type: ignore
except ImportError:  # pragma: no cover - exercised in an isolated test
    _psutil = None


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _sum_available(values: list[Any]) -> float | None:
    """Sum a compound counter only when every component is observable."""
    numbers = [_finite(value) for value in values]
    if any(number is None for number in numbers):
        return None
    return sum(number for number in numbers if number is not None)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True, slots=True)
class MetricReading:
    available: bool
    raw_value: float | None
    unit: str
    normalized_level: float | None
    reference: float | None = None
    reference_unit: str | None = None
    reference_source: str | None = None
    unavailable_reason: str | None = None

    @classmethod
    def unavailable(cls, unit: str, reason: str) -> "MetricReading":
        return cls(False, None, unit, None, unavailable_reason=str(reason))

    @classmethod
    def ratio(cls, value: Any, *, unit: str = "ratio", reference_source: str = "physical ratio") -> "MetricReading":
        number = _finite(value)
        if number is None:
            return cls.unavailable(unit, "counter returned no finite value")
        return cls(True, number, unit, _clamp01(number), 1.0, unit, reference_source)

    @classmethod
    def scaled(cls, value: Any, *, unit: str, reference: Any, reference_source: str) -> "MetricReading":
        number, scale = _finite(value), _finite(reference)
        if number is None:
            return cls.unavailable(unit, "counter returned no finite value")
        if scale is None or scale <= 0.0:
            return cls.unavailable(unit, "normalization reference is unavailable")
        return cls(True, number, unit, _clamp01(max(0.0, number) / scale), scale, unit, reference_source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available, "raw_value": self.raw_value,
            "unit": self.unit, "normalized_level": self.normalized_level,
            "reference": self.reference, "reference_unit": self.reference_unit,
            "reference_source": self.reference_source,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    sample_id: str
    captured_at_utc: str
    monotonic_seconds: float
    backend: str
    host: dict[str, MetricReading]
    process: dict[str, MetricReading]
    duration_ms: float
    recent_error: str | None = None
    runtime: dict[str, MetricReading] = field(default_factory=dict)
    scope: str = "shared"
    owner_consciousness_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def metrics(self, scope: str) -> dict[str, MetricReading]:
        if scope == "host": return self.host
        if scope == "process": return self.process
        if scope == "runtime": return self.runtime
        raise ValueError(f"unknown telemetry scope: {scope}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id, "captured_at_utc": self.captured_at_utc,
            "monotonic_seconds": self.monotonic_seconds, "backend": self.backend,
            "duration_ms": self.duration_ms, "recent_error": self.recent_error,
            "scope": self.scope,
            "owner_consciousness_id": self.owner_consciousness_id,
            "context": dict(self.context),
            "host": {name: value.to_dict() for name, value in self.host.items()},
            "process": {name: value.to_dict() for name, value in self.process.items()},
            "runtime": {name: value.to_dict() for name, value in self.runtime.items()},
        }


class TelemetryProbe(Protocol):
    backend: str
    def collect(self, monotonic_seconds: float, scopes: set[str] | None = None) -> tuple[dict[str, MetricReading], dict[str, MetricReading]]: ...


class TelemetryPlugin(Protocol):
    """Optional reliable counter extension (GPU, thermal, SMART, power...).

    Plugins must expose measurements and provenance directly.  A plugin may
    report a metric as unavailable, but must never estimate one physical
    quantity from an unrelated counter.  Registration belongs to the host
    application; Core has no dependency on this interface.
    """

    plugin_id: str
    def collect(self, monotonic_seconds: float) -> tuple[dict[str, MetricReading], dict[str, MetricReading]]: ...


HOST_REFERENCES: dict[str, float] = {
    "page_in_rate": 256 * 1024 * 1024, "page_out_rate": 256 * 1024 * 1024,
    "page_fault_rate": 25_000, "disk_read_rate": 256 * 1024 * 1024,
    "disk_write_rate": 256 * 1024 * 1024, "disk_read_iops": 20_000,
    "disk_write_iops": 20_000, "network_receive_rate": 125 * 1024 * 1024,
    "network_send_rate": 125 * 1024 * 1024, "network_receive_packets": 200_000,
    "network_send_packets": 200_000, "network_error_rate": 1_000,
    "network_drop_rate": 1_000,
}
PROCESS_REFERENCES: dict[str, float] = {
    "page_fault_rate": 25_000, "read_rate": 128 * 1024 * 1024,
    "write_rate": 128 * 1024 * 1024, "thread_count": 512,
    "handle_count": 16_384, "scheduler_latency_ms": 250,
    "tick_execution_time_ms": 250,
}
RUNTIME_REFERENCES: dict[str, float] = {
    "epoch_execution_time_ms": 250,
    "scheduler_latency_ms": 250,
}


def host_signal_names() -> tuple[str, ...]:
    return (
        "cpu_load", "cpu_frequency", "memory_pressure", "memory_commit_pressure",
        "swap_pressure", "page_in_rate", "page_out_rate", "page_fault_rate",
        "disk_read_rate", "disk_write_rate", "disk_read_iops", "disk_write_iops",
        "network_receive_rate", "network_send_rate", "network_receive_packets",
        "network_send_packets", "network_error_rate", "network_drop_rate",
        "battery_level", "ac_power", "battery_charging",
    )


def process_signal_names() -> tuple[str, ...]:
    return (
        "cpu_load", "rss_pressure", "private_memory_pressure", "page_fault_rate",
        "read_rate", "write_rate", "thread_count", "handle_count",
        "scheduler_latency_ms", "tick_execution_time_ms",
    )


def runtime_signal_names() -> tuple[str, ...]:
    return (
        "thread_cpu_load", "epoch_busy_ratio", "epoch_execution_time_ms",
        "scheduler_latency_ms",
    )


@lru_cache(maxsize=512)
def _telemetry_channel_map(seed: int) -> dict[tuple[str, str, str], int]:
    """Allocate stable, distinct anonymous channels for built-in signals."""
    key = (int(seed) % (1 << 128)).to_bytes(16, "big", signed=False)
    tokens = [
        (scope, metric, component)
        for scope, names in (
            ("host", host_signal_names()),
            ("process", process_signal_names()),
            ("runtime", runtime_signal_names()),
        )
        for metric in names
        for component in ("level", "rise", "fall")
    ]
    occupied: set[int] = set()
    result: dict[tuple[str, str, str], int] = {}
    for token in tokens:
        digest = hashlib.blake2b(":".join(token).encode("utf-8"), key=key, digest_size=16).digest()
        channel = int.from_bytes(digest[:8], "big") % 8192
        # An odd step traverses the complete power-of-two channel space.
        step = (int.from_bytes(digest[8:], "big") % 8192) | 1
        while channel in occupied:
            channel = (channel + step) % 8192
        occupied.add(channel)
        result[token] = channel
    return result


def default_telemetry_config(scope: str) -> dict[str, Any]:
    if scope == "host":
        names, references = host_signal_names(), HOST_REFERENCES
    elif scope == "process":
        names, references = process_signal_names(), PROCESS_REFERENCES
    elif scope == "runtime":
        names, references = runtime_signal_names(), RUNTIME_REFERENCES
    else:
        raise ValueError(f"unknown telemetry scope: {scope}")
    return {
        "sample_interval_ms": 1000, "smoothing": 0.8,
        "levels_enabled": True, "changes_enabled": True,
        "signals": {
            name: {"level": True, "change": True, "gain": 1.0,
                   **({"reference": references[name], "reference_override": False} if name in references else {})}
            for name in names
        },
    }


class SystemTelemetryProbe:
    """Read-only OS and current-process counter probe."""

    def __init__(self, *, psutil_module: Any = _psutil, process_id: int | None = None) -> None:
        self.psutil = psutil_module
        self.process_id = int(process_id or os.getpid())
        self.backend = f"psutil-{getattr(psutil_module, '__version__', 'unknown')}" if psutil_module is not None else f"{platform.system().lower()}-native"
        self._last_counters: dict[str, tuple[float, float]] = {}
        self._last_cpu_times: tuple[float, float] | None = None
        self._last_native_cpu = self._native_cpu_counters()
        self._process = None
        if self.psutil is not None:
            try: self._process = self.psutil.Process(self.process_id)
            except Exception: self._process = None
            self._prime(time.perf_counter())

    @staticmethod
    def _native_cpu_counters() -> tuple[int, int] | None:
        if os.name == "nt":
            class FileTime(ctypes.Structure):
                _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]
            idle = FileTime(); kernel = FileTime(); user = FileTime()
            try:
                if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)): return None
            except (AttributeError, OSError): return None
            value = lambda raw: (int(raw.high) << 32) | int(raw.low)
            return value(idle), value(kernel) + value(user)
        try:
            with open("/proc/stat", encoding="ascii") as stream: fields = stream.readline().split()
            values = [int(value) for value in fields[1:]]
            return values[3] + (values[4] if len(values) > 4 else 0), sum(values)
        except (OSError, ValueError, IndexError): return None

    @staticmethod
    def _native_memory() -> tuple[MetricReading, MetricReading, MetricReading]:
        if os.name == "nt":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]
            status = MemoryStatus(); status.length = ctypes.sizeof(MemoryStatus)
            try: ok = bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)))
            except (AttributeError, OSError): ok = False
            if not ok:
                unavailable = MetricReading.unavailable("ratio", "GlobalMemoryStatusEx failed")
                return unavailable, unavailable, unavailable
            physical = MetricReading.ratio(float(status.memory_load) / 100)
            commit_used = max(0, int(status.total_page_file) - int(status.available_page_file))
            commit = MetricReading.scaled(commit_used, unit="bytes", reference=status.total_page_file, reference_source="GlobalMemoryStatusEx commit limit")
            return physical, commit, MetricReading.unavailable("ratio", "native Windows fallback has no independent swap occupancy")
        try:
            values: dict[str, int] = {}
            with open("/proc/meminfo", encoding="ascii") as stream:
                for line in stream:
                    name, raw = line.split(":", 1); values[name] = int(raw.strip().split()[0]) * 1024
            total = values.get("MemTotal", 0); available = values.get("MemAvailable", values.get("MemFree", 0))
            physical = MetricReading.ratio(1 - available / total) if total else MetricReading.unavailable("ratio", "MemTotal unavailable")
            commit_limit = values.get("CommitLimit", 0)
            commit = MetricReading.scaled(values.get("Committed_AS"), unit="bytes", reference=commit_limit, reference_source="/proc/meminfo CommitLimit") if commit_limit else MetricReading.unavailable("ratio", "CommitLimit unavailable")
            swap_total = values.get("SwapTotal", 0)
            swap = MetricReading.scaled(swap_total - values.get("SwapFree", 0), unit="bytes", reference=swap_total, reference_source="/proc/meminfo SwapTotal") if swap_total else MetricReading.unavailable("ratio", "no swap configured")
            return physical, commit, swap
        except (OSError, ValueError, ZeroDivisionError):
            unavailable = MetricReading.unavailable("ratio", "/proc/meminfo unavailable")
            return unavailable, unavailable, unavailable

    def _prime(self, now: float) -> None:
        try:
            cpu = self.psutil.cpu_times()
            self._last_cpu_times = (sum(float(value) for value in cpu), float(getattr(cpu, "idle", 0)) + float(getattr(cpu, "iowait", 0)))
        except Exception: self._last_cpu_times = None
        self._prime_named_counters(now)

    def _prime_named_counters(self, now: float) -> None:
        try: disk = self.psutil.disk_io_counters()
        except Exception: disk = None
        try: network = self.psutil.net_io_counters()
        except Exception: network = None
        try: swap = self.psutil.swap_memory()
        except Exception: swap = None
        try: process_io = self._process.io_counters() if self._process is not None else None
        except Exception: process_io = None
        try: process_memory = self._process.memory_info() if self._process is not None else None
        except Exception: process_memory = None
        try: process_times = self._process.cpu_times() if self._process is not None else None
        except Exception: process_times = None
        values = {
            "host.disk_read_bytes": getattr(disk, "read_bytes", None),
            "host.disk_write_bytes": getattr(disk, "write_bytes", None),
            "host.disk_read_count": getattr(disk, "read_count", None),
            "host.disk_write_count": getattr(disk, "write_count", None),
            "host.net_recv_bytes": getattr(network, "bytes_recv", None),
            "host.net_send_bytes": getattr(network, "bytes_sent", None),
            "host.net_recv_packets": getattr(network, "packets_recv", None),
            "host.net_send_packets": getattr(network, "packets_sent", None),
            "host.net_errors": _sum_available([getattr(network, "errin", None), getattr(network, "errout", None)]) if network is not None else None,
            "host.net_drops": _sum_available([getattr(network, "dropin", None), getattr(network, "dropout", None)]) if network is not None else None,
            "host.page_in_bytes": getattr(swap, "sin", None) if os.name != "nt" else None,
            "host.page_out_bytes": getattr(swap, "sout", None) if os.name != "nt" else None,
            "process.read_bytes": getattr(process_io, "read_bytes", None),
            "process.write_bytes": getattr(process_io, "write_bytes", None),
            "process.page_faults": getattr(process_memory, "pfaults", None),
            "process.cpu_time": (getattr(process_times, "user", 0) + getattr(process_times, "system", 0)) if process_times is not None else None,
        }
        for key, value in values.items():
            number = _finite(value)
            if number is not None: self._last_counters[key] = (number, now)

    def reset_rate_baselines(self, scopes: set[str] | None = None) -> None:
        """Forget interval counters after a real sensory discontinuity.

        Cumulative OS counters cannot describe an instantaneous level.  If a
        scope was not being sampled while every interested consciousness was
        paused or disconnected, its next reading must establish a fresh
        baseline instead of averaging activity across that unobserved gap.
        """
        selected = {"host", "process"} if scopes is None else set(scopes)
        prefixes = tuple(f"{scope}." for scope in selected)
        self._last_counters = {
            key: value
            for key, value in self._last_counters.items()
            if not key.startswith(prefixes)
        }
        if "host" in selected:
            self._last_cpu_times = None
            self._last_native_cpu = None

    def _rate(self, key: str, current: Any, now: float) -> float | None:
        number = _finite(current)
        if number is None: return None
        previous = self._last_counters.get(key); self._last_counters[key] = (number, now)
        if previous is None or now <= previous[1] or number < previous[0]: return None
        return (number - previous[0]) / (now - previous[1])

    def _network_reference(self) -> tuple[float, str]:
        if self.psutil is not None:
            try:
                speeds = [
                    float(stats.speed) * 1_000_000 / 8
                    for name, stats in self.psutil.net_if_stats().items()
                    if stats.isup and float(stats.speed) > 0 and name.casefold() != "lo" and "loopback" not in name.casefold()
                ]
                if speeds:
                    # Aggregate OS counters can include several concurrently
                    # active interfaces, so their physical ceiling is the sum
                    # of known link speeds rather than the fastest one alone.
                    return sum(speeds), "combined active interface link speed"
            except Exception: pass
        return HOST_REFERENCES["network_receive_rate"], "configured fallback reference"

    @staticmethod
    def _native_charging() -> bool | None:
        if os.name != "nt": return None
        class PowerStatus(ctypes.Structure):
            _fields_ = [
                ("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("percent", ctypes.c_ubyte),
                ("reserved", ctypes.c_ubyte), ("life", ctypes.c_ulong), ("full", ctypes.c_ulong),
            ]
        status = PowerStatus()
        try:
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)) or status.flag == 255: return None
        except (AttributeError, OSError): return None
        return bool(status.flag & 8)

    def _host_psutil(self, now: float) -> dict[str, MetricReading]:
        output: dict[str, MetricReading] = {}
        try:
            cpu = self.psutil.cpu_times(); total = sum(float(value) for value in cpu)
            idle = float(getattr(cpu, "idle", 0)) + float(getattr(cpu, "iowait", 0))
            if self._last_cpu_times is None or total <= self._last_cpu_times[0]:
                output["cpu_load"] = MetricReading.unavailable("ratio", "CPU interval baseline is not established")
            else: output["cpu_load"] = MetricReading.ratio(1 - max(0, idle - self._last_cpu_times[1]) / (total - self._last_cpu_times[0]))
            self._last_cpu_times = (total, idle)
        except Exception as error: output["cpu_load"] = MetricReading.unavailable("ratio", f"CPU unavailable: {error}")
        try:
            frequency = self.psutil.cpu_freq()
            output["cpu_frequency"] = MetricReading.scaled(float(frequency.current) * 1e6, unit="Hz", reference=float(frequency.max) * 1e6, reference_source="reported maximum CPU frequency")
        except Exception as error: output["cpu_frequency"] = MetricReading.unavailable("Hz", f"CPU frequency unavailable: {error}")
        try:
            memory = self.psutil.virtual_memory(); swap = self.psutil.swap_memory()
            output["memory_pressure"] = MetricReading.ratio(float(memory.percent) / 100)
            # ``virtual_memory().available`` is not the inverse of committed
            # virtual memory.  On Windows in particular, treating
            # ``RAM + pagefile - available RAM`` as committed bytes counts the
            # entire pagefile as used.  Prefer the platform's real commit
            # counters; retain an explicit estimate only when they are absent.
            _native_physical, native_commit, _native_swap = self._native_memory()
            if native_commit.available:
                output["memory_commit_pressure"] = native_commit
            else:
                commit_limit = float(memory.total) + float(swap.total)
                committed_estimate = max(0.0, float(memory.total) - float(memory.available)) + float(swap.used)
                output["memory_commit_pressure"] = (
                    MetricReading.scaled(
                        committed_estimate,
                        unit="bytes",
                        reference=commit_limit,
                        reference_source="physical-use plus reported swap-use estimate",
                    )
                    if commit_limit
                    else MetricReading.unavailable("ratio", "commit limit unavailable")
                )
            output["swap_pressure"] = MetricReading.scaled(float(swap.used), unit="bytes", reference=float(swap.total), reference_source="configured swap capacity") if swap.total else MetricReading.unavailable("ratio", "no swap configured")
        except Exception as error:
            for name in ("memory_pressure", "memory_commit_pressure", "swap_pressure"):
                output[name] = MetricReading.unavailable("ratio", f"memory unavailable: {error}")
            swap = None
        for name, attr, key in (("page_in_rate", "sin", "host.page_in_bytes"), ("page_out_rate", "sout", "host.page_out_bytes")):
            if os.name == "nt": output[name] = MetricReading.unavailable("bytes/s", "psutil does not expose Windows system paging bytes")
            else:
                rate = self._rate(key, getattr(swap, attr, None), now) if swap is not None else None
                output[name] = MetricReading.scaled(rate, unit="bytes/s", reference=HOST_REFERENCES[name], reference_source="configured reference") if rate is not None else MetricReading.unavailable("bytes/s", "counter baseline or reset")
        output["page_fault_rate"] = MetricReading.unavailable("faults/s", "global page-fault rate needs a performance-counter plugin")
        try: disk = self.psutil.disk_io_counters()
        except Exception: disk = None
        for name, attr, key, unit in (
            ("disk_read_rate", "read_bytes", "host.disk_read_bytes", "bytes/s"),
            ("disk_write_rate", "write_bytes", "host.disk_write_bytes", "bytes/s"),
            ("disk_read_iops", "read_count", "host.disk_read_count", "operations/s"),
            ("disk_write_iops", "write_count", "host.disk_write_count", "operations/s"),
        ):
            rate = self._rate(key, getattr(disk, attr, None), now) if disk is not None else None
            output[name] = MetricReading.scaled(rate, unit=unit, reference=HOST_REFERENCES[name], reference_source="configured reference") if rate is not None else MetricReading.unavailable(unit, "counter baseline, reset, or unavailable")
        try: network = self.psutil.net_io_counters()
        except Exception: network = None
        link_reference, link_source = self._network_reference()
        for name, attr, key, unit, reference, source in (
            ("network_receive_rate", "bytes_recv", "host.net_recv_bytes", "bytes/s", link_reference, link_source),
            ("network_send_rate", "bytes_sent", "host.net_send_bytes", "bytes/s", link_reference, link_source),
            ("network_receive_packets", "packets_recv", "host.net_recv_packets", "packets/s", HOST_REFERENCES["network_receive_packets"], "configured reference"),
            ("network_send_packets", "packets_sent", "host.net_send_packets", "packets/s", HOST_REFERENCES["network_send_packets"], "configured reference"),
        ):
            rate = self._rate(key, getattr(network, attr, None), now) if network is not None else None
            output[name] = MetricReading.scaled(rate, unit=unit, reference=reference, reference_source=source) if rate is not None else MetricReading.unavailable(unit, "counter baseline, reset, or unavailable")
        for name, key, attrs, unit in (
            ("network_error_rate", "host.net_errors", ("errin", "errout"), "errors/s"),
            ("network_drop_rate", "host.net_drops", ("dropin", "dropout"), "drops/s"),
        ):
            current = _sum_available([getattr(network, attr, None) for attr in attrs]) if network is not None else None
            rate = self._rate(key, current, now)
            output[name] = MetricReading.scaled(rate, unit=unit, reference=HOST_REFERENCES[name], reference_source="configured reference") if rate is not None else MetricReading.unavailable(unit, "counter baseline, reset, or unavailable")
        try: battery = self.psutil.sensors_battery()
        except Exception: battery = None
        if battery is None:
            output["battery_level"] = MetricReading.unavailable("ratio", "no battery counter")
            output["ac_power"] = MetricReading.unavailable("boolean", "no AC counter")
            output["battery_charging"] = MetricReading.unavailable("boolean", "no charging-state counter")
        else:
            output["battery_level"] = MetricReading.ratio(float(battery.percent) / 100)
            plugged = getattr(battery, "power_plugged", None)
            output["ac_power"] = MetricReading.ratio(1 if plugged else 0, unit="boolean") if plugged is not None else MetricReading.unavailable("boolean", "AC state unavailable")
            charging = self._native_charging()
            output["battery_charging"] = MetricReading.ratio(1 if charging else 0, unit="boolean") if charging is not None else MetricReading.unavailable("boolean", "reliable charging flag unavailable")
        return output

    def _host_native(self) -> dict[str, MetricReading]:
        counters = self._native_cpu_counters()
        if counters is not None and self._last_native_cpu is not None:
            idle, total = counters[0] - self._last_native_cpu[0], counters[1] - self._last_native_cpu[1]
            cpu = MetricReading.ratio(1 - max(0, idle) / total) if total > 0 else MetricReading.unavailable("ratio", "CPU baseline or reset")
        else: cpu = MetricReading.unavailable("ratio", "native CPU counters unavailable")
        self._last_native_cpu = counters
        memory, commit, swap = self._native_memory()
        output = {"cpu_load": cpu, "memory_pressure": memory, "memory_commit_pressure": commit, "swap_pressure": swap}
        units = {
            "cpu_frequency": "Hz", "page_in_rate": "bytes/s", "page_out_rate": "bytes/s", "page_fault_rate": "faults/s",
            "disk_read_rate": "bytes/s", "disk_write_rate": "bytes/s", "disk_read_iops": "operations/s", "disk_write_iops": "operations/s",
            "network_receive_rate": "bytes/s", "network_send_rate": "bytes/s", "network_receive_packets": "packets/s", "network_send_packets": "packets/s",
            "network_error_rate": "errors/s", "network_drop_rate": "drops/s", "battery_level": "ratio", "ac_power": "boolean", "battery_charging": "boolean",
        }
        output.update({name: MetricReading.unavailable(unit, "install the optional telemetry dependency") for name, unit in units.items()})
        return output

    def _process_metrics(self, now: float, total_memory: float | None) -> dict[str, MetricReading]:
        if self._process is None:
            return {name: MetricReading.unavailable("unknown", "process telemetry requires psutil") for name in process_signal_names()}
        process = self._process; output: dict[str, MetricReading] = {}
        try:
            times = process.cpu_times(); rate = self._rate("process.cpu_time", float(times.user) + float(times.system), now)
            output["cpu_load"] = MetricReading.ratio(rate / max(1, int(self.psutil.cpu_count() or os.cpu_count() or 1))) if rate is not None else MetricReading.unavailable("ratio", "counter baseline or reset")
        except Exception as error: output["cpu_load"] = MetricReading.unavailable("ratio", f"process CPU unavailable: {error}")
        try:
            memory = process.memory_info(); reference = total_memory or float(self.psutil.virtual_memory().total)
            output["rss_pressure"] = MetricReading.scaled(memory.rss, unit="bytes", reference=reference, reference_source="host physical memory")
            private = getattr(memory, "private", None)
            if private is None:
                try:
                    # USS is the memory unique to this process and is the
                    # closest portable equivalent to Windows private bytes.
                    private = getattr(process.memory_full_info(), "uss", None)
                except Exception:
                    private = None
            output["private_memory_pressure"] = MetricReading.scaled(private, unit="bytes", reference=reference, reference_source="host physical memory") if private is not None else MetricReading.unavailable("bytes", "private memory unavailable")
            faults = getattr(memory, "pfaults", None); rate = self._rate("process.page_faults", faults, now)
            output["page_fault_rate"] = MetricReading.scaled(rate, unit="faults/s", reference=PROCESS_REFERENCES["page_fault_rate"], reference_source="configured reference") if rate is not None else MetricReading.unavailable("faults/s", "counter baseline or unavailable")
        except Exception as error:
            for name in ("rss_pressure", "private_memory_pressure", "page_fault_rate"): output[name] = MetricReading.unavailable("ratio", f"process memory unavailable: {error}")
        try: io = process.io_counters()
        except Exception: io = None
        for name, attr, key in (("read_rate", "read_bytes", "process.read_bytes"), ("write_rate", "write_bytes", "process.write_bytes")):
            rate = self._rate(key, getattr(io, attr, None), now) if io is not None else None
            output[name] = MetricReading.scaled(rate, unit="bytes/s", reference=PROCESS_REFERENCES[name], reference_source="configured reference") if rate is not None else MetricReading.unavailable("bytes/s", "counter baseline or unavailable")
        for name, method, unit in (("thread_count", "num_threads", "threads"), ("handle_count", "num_handles", "handles")):
            try: value = getattr(process, method)()
            except Exception: value = None
            output[name] = MetricReading.scaled(value, unit=unit, reference=PROCESS_REFERENCES[name], reference_source="configured reference") if value is not None else MetricReading.unavailable(unit, f"{name} unavailable")
        output["scheduler_latency_ms"] = MetricReading.unavailable("ms", "application host has not supplied scheduler latency")
        output["tick_execution_time_ms"] = MetricReading.unavailable(
            "ms",
            "application host has not supplied a read-only tick execution measurement",
        )
        return output

    def collect(self, monotonic_seconds: float, scopes: set[str] | None = None) -> tuple[dict[str, MetricReading], dict[str, MetricReading]]:
        selected = {"host", "process"} if scopes is None else set(scopes)
        host = {name: MetricReading.unavailable("unknown", "host telemetry adapter is disabled") for name in host_signal_names()}
        process = {name: MetricReading.unavailable("unknown", "process telemetry adapter is disabled") for name in process_signal_names()}
        total: float | None = None
        if "host" in selected:
            if self.psutil is not None:
                host = self._host_psutil(monotonic_seconds)
                try: total = float(self.psutil.virtual_memory().total)
                except Exception: total = None
            else: host = self._host_native()
        if "process" in selected:
            if total is None and self.psutil is not None:
                try: total = float(self.psutil.virtual_memory().total)
                except Exception: total = None
            process = self._process_metrics(monotonic_seconds, total)
        return host, process


class HostTelemetryCollector:
    """Thread-safe shared physical sampler, independent of Core tick speed."""

    def __init__(self, probe: TelemetryProbe | None = None, *, clock: Any = time.perf_counter, plugins: list[TelemetryPlugin] | None = None) -> None:
        self.probe = probe or SystemTelemetryProbe(); self.clock = clock
        self._lock = RLock(); self._last_sample: TelemetrySample | None = None
        self._active_scopes: set[str] = set()
        self._scheduler_latency_ms: float | None = None
        self._tick_execution_ms: float | None = None
        self._plugins: dict[str, TelemetryPlugin] = {str(plugin.plugin_id): plugin for plugin in (plugins or [])}
        self._plugin_errors: dict[str, str] = {}

    def register_plugin(self, plugin: TelemetryPlugin) -> None:
        with self._lock:
            self._plugins[str(plugin.plugin_id)] = plugin
            self._plugin_errors.pop(str(plugin.plugin_id), None)

    def unregister_plugin(self, plugin_id: str) -> None:
        with self._lock:
            self._plugins.pop(str(plugin_id), None)
            self._plugin_errors.pop(str(plugin_id), None)

    def set_scheduler_latency(self, milliseconds: float | None) -> None:
        with self._lock: self._scheduler_latency_ms = _finite(milliseconds)

    def set_tick_execution_time(self, milliseconds: float | None) -> None:
        with self._lock: self._tick_execution_ms = _finite(milliseconds)

    def sample(self, scopes: set[str] | None = None) -> TelemetrySample:
        requested = {"host", "process"} if scopes is None else set(scopes)
        with self._lock:
            newly_active = requested - self._active_scopes
            self._active_scopes = set(requested)
        reset = getattr(self.probe, "reset_rate_baselines", None)
        if newly_active and callable(reset):
            reset(newly_active)
        started = float(self.clock()); recent_error = None
        try: host, process = self.probe.collect(started, scopes)
        except Exception as error:
            recent_error = f"{type(error).__name__}: {error}"
            host = {name: MetricReading.unavailable("unknown", recent_error) for name in host_signal_names()}
            process = {name: MetricReading.unavailable("unknown", recent_error) for name in process_signal_names()}
        with self._lock:
            latency = self._scheduler_latency_ms
            tick_execution = self._tick_execution_ms
            plugins = tuple(self._plugins.items())
        for plugin_id, plugin in plugins:
            try:
                plugin_host, plugin_process = plugin.collect(started)
                host.update(plugin_host); process.update(plugin_process)
                with self._lock: self._plugin_errors.pop(plugin_id, None)
            except Exception as error:
                with self._lock: self._plugin_errors[plugin_id] = f"{type(error).__name__}: {error}"
        if latency is not None:
            process["scheduler_latency_ms"] = MetricReading.scaled(max(0, latency), unit="ms", reference=PROCESS_REFERENCES["scheduler_latency_ms"], reference_source="configured reference")
        if tick_execution is not None:
            process["tick_execution_time_ms"] = MetricReading.scaled(max(0, tick_execution), unit="ms", reference=PROCESS_REFERENCES["tick_execution_time_ms"], reference_source="measured ThreeMind runtime epoch duration")
        finished = float(self.clock())
        sample = TelemetrySample(str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), started, self.probe.backend, host, process, max(0, finished - started) * 1000, recent_error)
        with self._lock: self._last_sample = sample
        return sample

    def clear_process_observations(self) -> None:
        """Remove stale app-host timing when process sensing is not active."""
        with self._lock:
            self._scheduler_latency_ms = None
            self._tick_execution_ms = None

    def deactivate(self, scopes: set[str] | None = None) -> None:
        """Mark physical scopes unobserved without fabricating zero samples."""
        with self._lock:
            if scopes is None:
                self._active_scopes.clear()
            else:
                self._active_scopes.difference_update(scopes)

    def status(self) -> dict[str, Any]:
        with self._lock: sample = self._last_sample
        dependency = "full" if getattr(self.probe, "psutil", _psutil) is not None else "partial"
        if sample is None:
            return {"backend": self.probe.backend, "dependency": dependency, "last_sample_time": None, "available_metrics": {"host": [], "process": []}, "unavailable_metrics": {"host": {}, "process": {}}, "recent_error": None, "plugins": sorted(self._plugins), "plugin_errors": dict(self._plugin_errors)}
        return {
            "backend": sample.backend, "dependency": dependency,
            "last_sample_time": sample.captured_at_utc, "last_sample_id": sample.sample_id,
            "last_duration_ms": sample.duration_ms,
            "available_metrics": {scope: [name for name, value in sample.metrics(scope).items() if value.available] for scope in ("host", "process")},
            "unavailable_metrics": {scope: {name: value.unavailable_reason for name, value in sample.metrics(scope).items() if not value.available} for scope in ("host", "process")},
            "recent_error": sample.recent_error,
            "plugins": sorted(self._plugins), "plugin_errors": dict(self._plugin_errors),
        }


@dataclass(frozen=True, slots=True)
class EncodedTelemetry:
    frame: SensoryFrame | None
    audit: dict[str, Any]


class TelemetrySensoryAdapter:
    """Per-consciousness anonymous encoder for a shared telemetry sample."""

    def __init__(self, seed: int, *, scope: str, config: dict[str, Any] | None = None) -> None:
        if scope not in {"host", "process", "runtime"}: raise ValueError("telemetry scope must be host, process or runtime")
        self.seed = int(seed); self.scope = scope; self.config = default_telemetry_config(scope)
        self._smoothed: dict[str, float] = {}; self._previous: dict[str, float] = {}; self._last_sample_id: str | None = None
        self.configure(config or {})

    @property
    def id(self) -> str:
        return {
            "host": "host-telemetry-field",
            "process": "process-telemetry-field",
            "runtime": "runtime-telemetry-field",
        }[self.scope]

    def configure(self, config: dict[str, Any]) -> None:
        merged = json.loads(json.dumps(self.config))
        for key in ("sample_interval_ms", "smoothing", "levels_enabled", "changes_enabled"):
            if key in config: merged[key] = config[key]
        if isinstance(config.get("signals"), dict):
            for name, values in config["signals"].items():
                if name in merged["signals"] and isinstance(values, dict): merged["signals"][name].update(values)
        merged["sample_interval_ms"] = max(250, min(60_000, int(merged["sample_interval_ms"])))
        merged["smoothing"] = max(0, min(.999, float(merged["smoothing"])))
        merged["levels_enabled"] = bool(merged["levels_enabled"]); merged["changes_enabled"] = bool(merged["changes_enabled"])
        for values in merged["signals"].values():
            values["level"] = bool(values.get("level", True)); values["change"] = bool(values.get("change", True))
            values["gain"] = max(0, min(100, float(values.get("gain", 1))))
            if "reference" in values:
                values["reference"] = max(1e-12, float(values["reference"]))
                values["reference_override"] = bool(values.get("reference_override", False))
        self.config = merged

    def reset_baseline(self) -> None:
        self._smoothed.clear(); self._previous.clear(); self._last_sample_id = None

    def _channel(self, metric: str, component: str) -> int:
        token = (self.scope, metric, component)
        try:
            return _telemetry_channel_map(self.seed)[token]
        except KeyError as error:
            raise ValueError(f"undeclared telemetry signal channel: {self.scope}.{metric}.{component}") from error

    def encode(self, sample: TelemetrySample, *, intensity: float = 1, bypass_filter: bool = False) -> EncodedTelemetry:
        if self._last_sample_id == sample.sample_id: return EncodedTelemetry(None, {"sample_id": sample.sample_id, "scope": self.scope, "state": "duplicate-sample"})
        self._last_sample_id = sample.sample_id; channels: dict[int, float] = {}; measurements: dict[str, Any] = {}
        smoothing = float(self.config["smoothing"])
        for name, reading in sample.metrics(self.scope).items():
            signal = self.config["signals"].get(name)
            if signal is None: continue
            if not reading.available or reading.normalized_level is None:
                # A missing interval cannot support a physical derivative.
                # Reappearance therefore establishes a new baseline instead
                # of treating the unobserved gap as one large rise or fall.
                self._smoothed.pop(name, None)
                self._previous.pop(name, None)
                measurements[name] = {**reading.to_dict(), "delivered": False}; continue
            reference_override = bool(signal.get("reference_override", False))
            reference = _finite(signal.get("reference")) if reference_override else None
            normalized = _clamp01(max(0, reading.raw_value or 0) / reference) if reference is not None and reference > 0 and reading.raw_value is not None else _clamp01(reading.normalized_level)
            reference_source = "adapter configured reference" if reference is not None else reading.reference_source
            old_smoothed = self._smoothed.get(name); smoothed = normalized if old_smoothed is None else old_smoothed * smoothing + normalized * (1 - smoothing)
            previous = self._previous.get(name); rise = max(0, smoothed - previous) if previous is not None else 0; fall = max(0, previous - smoothed) if previous is not None else 0
            self._smoothed[name] = smoothed; self._previous[name] = smoothed; gain = float(signal["gain"]); metric_channels: dict[str, int] = {}
            if self.config["levels_enabled"] and signal["level"] and smoothed * gain > 0:
                channel = self._channel(name, "level"); channels[channel] = smoothed * gain; metric_channels["level"] = channel
            if self.config["changes_enabled"] and signal["change"] and previous is not None:
                if rise * gain > 0: channel = self._channel(name, "rise"); channels[channel] = rise * gain; metric_channels["rise"] = channel
                if fall * gain > 0: channel = self._channel(name, "fall"); channels[channel] = fall * gain; metric_channels["fall"] = channel
            measurements[name] = {**reading.to_dict(), "normalized_level": normalized, "smoothed_level": smoothed, "rise": rise, "fall": fall, "gain": gain, "smoothing": smoothing, "reference": reference or reading.reference, "reference_source": reference_source, "reference_override": reference_override, "channels": metric_channels, "delivered": bool(metric_channels), "change_baseline_established": previous is not None}
        # Reuse the established ambient source class so Core remains entirely
        # unaware of telemetry adapter identities.  ``adapter_id`` and
        # ``envelope_id`` preserve the exact provenance outside Core.
        frame = SensoryFrame(source=f"ambient-{self.scope}-telemetry", channels=channels, intensity=max(0, min(2, float(intensity))), external=True, bypass_filter=bypass_filter) if channels else None
        input_frame = (
            {
                "source": frame.source,
                "channels": {str(channel): float(value) for channel, value in frame.channels.items()},
                "intensity": float(frame.intensity),
                "external": bool(frame.external),
                "bypass_filter": bool(frame.bypass_filter),
            }
            if frame is not None
            else None
        )
        return EncodedTelemetry(frame, {"sample_id": sample.sample_id, "scope": self.scope, "owner_consciousness_id": sample.owner_consciousness_id, "sample_context": dict(sample.context), "adapter_id": self.id, "backend": sample.backend, "captured_at_utc": sample.captured_at_utc, "monotonic_seconds": sample.monotonic_seconds, "levels_enabled": self.config["levels_enabled"], "changes_enabled": self.config["changes_enabled"], "measurements": measurements, "input_frame": input_frame, "channel_count": len(channels), "state": "encoded" if frame else "no-positive-enabled-channel"})


class HostTelemetryAdapter(TelemetrySensoryAdapter):
    def __init__(self, seed: int, *, config: dict[str, Any] | None = None) -> None: super().__init__(seed, scope="host", config=config)


class ProcessTelemetryAdapter(TelemetrySensoryAdapter):
    def __init__(self, seed: int, *, config: dict[str, Any] | None = None) -> None: super().__init__(seed, scope="process", config=config)


class RuntimeTelemetryAdapter(TelemetrySensoryAdapter):
    def __init__(self, seed: int, *, config: dict[str, Any] | None = None) -> None: super().__init__(seed, scope="runtime", config=config)


class TelemetryAuditStore:
    """Indexed app-side audit: one shared raw sample, many delivery links."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True); self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL"); self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("CREATE TABLE IF NOT EXISTS telemetry_samples (sample_id TEXT PRIMARY KEY, captured_at_utc TEXT NOT NULL, monotonic_seconds REAL NOT NULL, backend TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'shared', owner_consciousness_id TEXT, payload_json TEXT NOT NULL)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS telemetry_deliveries (delivery_id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT NOT NULL, consciousness_id TEXT NOT NULL, adapter_id TEXT NOT NULL, envelope_id TEXT, created_at_utc TEXT NOT NULL, audit_json TEXT NOT NULL, FOREIGN KEY(sample_id) REFERENCES telemetry_samples(sample_id))")
        sample_columns = {str(row[1]) for row in self._connection.execute("PRAGMA table_info(telemetry_samples)").fetchall()}
        if "scope" not in sample_columns:
            self._connection.execute("ALTER TABLE telemetry_samples ADD COLUMN scope TEXT NOT NULL DEFAULT 'shared'")
        if "owner_consciousness_id" not in sample_columns:
            self._connection.execute("ALTER TABLE telemetry_samples ADD COLUMN owner_consciousness_id TEXT")
        self._connection.execute("CREATE INDEX IF NOT EXISTS telemetry_delivery_consciousness ON telemetry_deliveries(consciousness_id,delivery_id)")
        self._connection.execute("CREATE INDEX IF NOT EXISTS telemetry_delivery_adapter ON telemetry_deliveries(adapter_id,delivery_id)")
        self._connection.execute("CREATE INDEX IF NOT EXISTS telemetry_sample_scope_owner ON telemetry_samples(scope,owner_consciousness_id,captured_at_utc)"); self._connection.commit()
        self._last_error = ""
        self._writes = 0

    def record_sample(self, sample: TelemetrySample) -> None:
        with self._lock:
            try:
                self._connection.execute("INSERT OR IGNORE INTO telemetry_samples(sample_id,captured_at_utc,monotonic_seconds,backend,scope,owner_consciousness_id,payload_json) VALUES (?,?,?,?,?,?,?)", (sample.sample_id, sample.captured_at_utc, sample.monotonic_seconds, sample.backend, sample.scope, sample.owner_consciousness_id, json.dumps(sample.to_dict(), ensure_ascii=False, separators=(",", ":"))))
                self._connection.commit(); self._writes += 1; self._last_error = ""
            except Exception as error:
                self._last_error = f"{type(error).__name__}: {error}"
                raise

    def record_delivery(self, *, sample_id: str, consciousness_id: str, adapter_id: str, envelope_id: str | None, audit: dict[str, Any]) -> None:
        with self._lock:
            try:
                self._connection.execute("INSERT INTO telemetry_deliveries(sample_id,consciousness_id,adapter_id,envelope_id,created_at_utc,audit_json) VALUES (?,?,?,?,?,?)", (sample_id, consciousness_id, adapter_id, envelope_id, datetime.now(timezone.utc).isoformat(), json.dumps(audit, ensure_ascii=False, separators=(",", ":"))))
                self._connection.commit(); self._writes += 1; self._last_error = ""
            except Exception as error:
                self._last_error = f"{type(error).__name__}: {error}"
                raise

    def record_batch(self, sample: TelemetrySample, deliveries: list[dict[str, Any]]) -> None:
        """Commit one shared sample and all per-consciousness links atomically."""
        with self._lock:
            try:
                self._connection.execute("INSERT OR IGNORE INTO telemetry_samples(sample_id,captured_at_utc,monotonic_seconds,backend,scope,owner_consciousness_id,payload_json) VALUES (?,?,?,?,?,?,?)", (sample.sample_id, sample.captured_at_utc, sample.monotonic_seconds, sample.backend, sample.scope, sample.owner_consciousness_id, json.dumps(sample.to_dict(), ensure_ascii=False, separators=(",", ":"))))
                created_at = datetime.now(timezone.utc).isoformat()
                self._connection.executemany(
                    "INSERT INTO telemetry_deliveries(sample_id,consciousness_id,adapter_id,envelope_id,created_at_utc,audit_json) VALUES (?,?,?,?,?,?)",
                    [(sample.sample_id, str(row["consciousness_id"]), str(row["adapter_id"]), row.get("envelope_id"), created_at, json.dumps(row["audit"], ensure_ascii=False, separators=(",", ":"))) for row in deliveries],
                )
                self._connection.commit(); self._writes += 1; self._last_error = ""
            except Exception as error:
                self._connection.rollback(); self._last_error = f"{type(error).__name__}: {error}"
                raise

    def status(self) -> dict[str, Any]:
        with self._lock: return {"path": str(self.path), "writes": self._writes, "recent_error": self._last_error}

    def list_deliveries(self, *, consciousness_id: str | None = None, adapter_id: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        clauses: list[str] = []; values: list[Any] = []
        if consciousness_id: clauses.append("d.consciousness_id=?"); values.append(consciousness_id)
        if adapter_id: clauses.append("d.adapter_id=?"); values.append(adapter_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            total = int(self._connection.execute(f"SELECT COUNT(*) FROM telemetry_deliveries d {where}", values).fetchone()[0])
            rows = self._connection.execute(f"SELECT d.delivery_id,d.sample_id,d.consciousness_id,d.adapter_id,d.envelope_id,d.created_at_utc,d.audit_json,s.scope,s.owner_consciousness_id,s.payload_json FROM telemetry_deliveries d JOIN telemetry_samples s ON s.sample_id=d.sample_id {where} ORDER BY d.delivery_id DESC LIMIT ? OFFSET ?", [*values, max(1, min(10_000, int(limit))), max(0, int(offset))]).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            sample = json.loads(row[9]); sample.setdefault("scope", row[7]); sample.setdefault("owner_consciousness_id", row[8]); sample.setdefault("context", {})
            items.append({"delivery_id": row[0], "sample_id": row[1], "consciousness_id": row[2], "adapter_id": row[3], "envelope_id": row[4], "created_at_utc": row[5], "audit": json.loads(row[6]), "sample": sample})
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def list_samples(self, *, scope: str | None = None, consciousness_id: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        clauses: list[str] = []; values: list[Any] = []
        if scope: clauses.append("scope=?"); values.append(scope)
        if consciousness_id: clauses.append("owner_consciousness_id=?"); values.append(consciousness_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            total = int(self._connection.execute(f"SELECT COUNT(*) FROM telemetry_samples {where}", values).fetchone()[0])
            rows = self._connection.execute(f"SELECT scope,owner_consciousness_id,payload_json FROM telemetry_samples {where} ORDER BY captured_at_utc DESC LIMIT ? OFFSET ?", [*values, max(1, min(10_000, int(limit))), max(0, int(offset))]).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            sample = json.loads(row[2]); sample.setdefault("scope", row[0]); sample.setdefault("owner_consciousness_id", row[1]); sample.setdefault("context", {})
            items.append(sample)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def close(self) -> None:
        with self._lock: self._connection.close()
