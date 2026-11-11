"""OS probes ported from the audited legacy telemetry adapter.

No storage or Core imports. Missing readings carry reasons; probes never infer
temperature, power or per-model memory from unrelated utilization counters.
"""

from __future__ import annotations

import ctypes
import math
import os
import platform
import time
from dataclasses import dataclass
from typing import Any

try:
    import psutil as _psutil
except ImportError:
    _psutil = None

PROBE_ERRORS = (OSError, AttributeError, ValueError, TypeError, NotImplementedError) + (
    (_psutil.Error,) if _psutil else ()
)


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


def _cpu_totals(cpu):
    # Linux guest time is already counted in user/nice; Windows interrupt/DPC
    # is already counted in system time. Do not count either twice.
    total = sum(float(value) for value in cpu)
    total -= sum(float(getattr(cpu, name, 0)) for name in ("guest", "guest_nice", "interrupt", "dpc"))
    return total, float(getattr(cpu, "idle", 0)) + float(getattr(cpu, "iowait", 0))


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
    def unavailable(cls, unit: str, reason: str) -> MetricReading:
        return cls(False, None, unit, None, unavailable_reason=str(reason))

    @classmethod
    def ratio(cls, value: Any, *, unit: str = "ratio", reference_source: str = "physical ratio") -> MetricReading:
        number = _finite(value)
        if number is None:
            return cls.unavailable(unit, "counter returned no finite value")
        return cls(True, number, unit, _clamp01(number), 1.0, unit, reference_source)

    @classmethod
    def scaled(cls, value: Any, *, unit: str, reference: Any, reference_source: str) -> MetricReading:
        number, scale = _finite(value), _finite(reference)
        if number is None:
            return cls.unavailable(unit, "counter returned no finite value")
        if scale is None or scale <= 0.0:
            return cls(True, number, unit, None, unavailable_reason="normalization reference is unavailable")
        return cls(True, number, unit, _clamp01(max(0.0, number) / scale), scale, unit, reference_source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "raw_value": self.raw_value,
            "unit": self.unit,
            "normalized_level": self.normalized_level,
            "reference": self.reference,
            "reference_unit": self.reference_unit,
            "reference_source": self.reference_source,
            "unavailable_reason": self.unavailable_reason,
        }


HOST_REFERENCES: dict[str, float] = {
    "page_in_rate": 256 * 1024 * 1024,
    "page_out_rate": 256 * 1024 * 1024,
    "page_fault_rate": 25_000,
    "disk_read_rate": 256 * 1024 * 1024,
    "disk_write_rate": 256 * 1024 * 1024,
    "disk_read_iops": 20_000,
    "disk_write_iops": 20_000,
    "network_receive_rate": 125 * 1024 * 1024,
    "network_send_rate": 125 * 1024 * 1024,
    "network_receive_packets": 200_000,
    "network_send_packets": 200_000,
    "network_error_rate": 1_000,
    "network_drop_rate": 1_000,
}

PROCESS_REFERENCES: dict[str, float] = {
    "page_fault_rate": 25_000,
    "read_rate": 128 * 1024 * 1024,
    "write_rate": 128 * 1024 * 1024,
    "thread_count": 512,
    "handle_count": 16_384,
    "scheduler_latency_ms": 250,
    "tick_execution_time_ms": 250,
}

RUNTIME_REFERENCES: dict[str, float] = {
    "epoch_execution_time_ms": 250,
    "scheduler_latency_ms": 250,
}


def host_signal_names() -> tuple[str, ...]:
    return (
        "cpu_load",
        "cpu_frequency",
        "memory_pressure",
        "memory_commit_pressure",
        "swap_pressure",
        "page_in_rate",
        "page_out_rate",
        "page_fault_rate",
        "disk_read_rate",
        "disk_write_rate",
        "disk_read_iops",
        "disk_write_iops",
        "network_receive_rate",
        "network_send_rate",
        "network_receive_packets",
        "network_send_packets",
        "network_error_rate",
        "network_drop_rate",
        "battery_level",
        "ac_power",
        "battery_charging",
    )


def process_signal_names() -> tuple[str, ...]:
    return (
        "cpu_load",
        "rss_pressure",
        "private_memory_pressure",
        "page_fault_rate",
        "read_rate",
        "write_rate",
        "thread_count",
        "handle_count",
        "scheduler_latency_ms",
        "tick_execution_time_ms",
    )


def runtime_signal_names() -> tuple[str, ...]:
    return (
        "thread_cpu_load",
        "epoch_busy_ratio",
        "epoch_execution_time_ms",
        "scheduler_latency_ms",
    )


class SystemTelemetryProbe:
    """Read-only OS and current-process counter probe."""

    def __init__(self, *, psutil_module: Any = _psutil, process_id: int | None = None) -> None:
        self.psutil = psutil_module
        self.process_id = int(process_id or os.getpid())
        self.backend = (
            f"psutil-{getattr(psutil_module, '__version__', 'unknown')}"
            if psutil_module is not None
            else f"{platform.system().lower()}-native"
        )
        self._last_counters: dict[str, tuple[float, float]] = {}
        self._last_cpu_times: tuple[float, float] | None = None
        self._last_native_cpu = self._native_cpu_counters()
        self._process = None
        if self.psutil is not None:
            try:
                self._process = self.psutil.Process(self.process_id)
            except PROBE_ERRORS:
                self._process = None
            self._prime(time.perf_counter())

    @staticmethod
    def _native_cpu_counters() -> tuple[int, int] | None:
        if os.name == "nt":

            class FileTime(ctypes.Structure):
                _fields_ = [("low", ctypes.c_ulong), ("high", ctypes.c_ulong)]

            idle = FileTime()
            kernel = FileTime()
            user = FileTime()
            try:
                if not ctypes.windll.kernel32.GetSystemTimes(
                    ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
                ):
                    return None
            except (AttributeError, OSError):
                return None
            value = lambda raw: (int(raw.high) << 32) | int(raw.low)
            return value(idle), value(kernel) + value(user)
        try:
            with open("/proc/stat", encoding="ascii") as stream:
                fields = stream.readline().split()
            values = [int(value) for value in fields[1:]]
            return values[3] + (values[4] if len(values) > 4 else 0), sum(values)
        except (OSError, ValueError, IndexError):
            return None

    @staticmethod
    def _native_memory() -> tuple[MetricReading, MetricReading, MetricReading]:
        if os.name == "nt":

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong),
                    ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong),
                    ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong),
                    ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(MemoryStatus)
            try:
                ok = bool(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)))
            except (AttributeError, OSError):
                ok = False
            if not ok:
                unavailable = MetricReading.unavailable("ratio", "GlobalMemoryStatusEx failed")
                return unavailable, unavailable, unavailable
            physical = MetricReading.ratio(float(status.memory_load) / 100)
            commit_used = max(0, int(status.total_page_file) - int(status.available_page_file))
            commit = MetricReading.scaled(
                commit_used,
                unit="bytes",
                reference=status.total_page_file,
                reference_source="GlobalMemoryStatusEx commit limit",
            )
            return (
                physical,
                commit,
                MetricReading.unavailable("ratio", "native Windows fallback has no independent swap occupancy"),
            )
        try:
            values: dict[str, int] = {}
            with open("/proc/meminfo", encoding="ascii") as stream:
                for line in stream:
                    name, raw = line.split(":", 1)
                    values[name] = int(raw.strip().split()[0]) * 1024
            total = values.get("MemTotal", 0)
            available = values.get("MemAvailable", values.get("MemFree", 0))
            physical = (
                MetricReading.ratio(1 - available / total)
                if total
                else MetricReading.unavailable("ratio", "MemTotal unavailable")
            )
            commit_limit = values.get("CommitLimit", 0)
            commit = (
                MetricReading.scaled(
                    values.get("Committed_AS"),
                    unit="bytes",
                    reference=commit_limit,
                    reference_source="/proc/meminfo CommitLimit",
                )
                if commit_limit
                else MetricReading.unavailable("ratio", "CommitLimit unavailable")
            )
            swap_total = values.get("SwapTotal", 0)
            swap = (
                MetricReading.scaled(
                    swap_total - values.get("SwapFree", 0),
                    unit="bytes",
                    reference=swap_total,
                    reference_source="/proc/meminfo SwapTotal",
                )
                if swap_total
                else MetricReading.unavailable("ratio", "no swap configured")
            )
            return physical, commit, swap
        except (OSError, ValueError, ZeroDivisionError):
            unavailable = MetricReading.unavailable("ratio", "/proc/meminfo unavailable")
            return unavailable, unavailable, unavailable

    def _prime(self, now: float) -> None:
        try:
            cpu = self.psutil.cpu_times()
            self._last_cpu_times = _cpu_totals(cpu)
        except PROBE_ERRORS:
            self._last_cpu_times = None
        self._prime_named_counters(now)

    def _prime_named_counters(self, now: float) -> None:
        try:
            disk = self.psutil.disk_io_counters()
        except PROBE_ERRORS:
            disk = None
        try:
            network = self.psutil.net_io_counters()
        except PROBE_ERRORS:
            network = None
        try:
            swap = self.psutil.swap_memory()
        except PROBE_ERRORS:
            swap = None
        try:
            process_io = self._process.io_counters() if self._process is not None else None
        except PROBE_ERRORS:
            process_io = None
        try:
            process_memory = self._process.memory_info() if self._process is not None else None
        except PROBE_ERRORS:
            process_memory = None
        try:
            process_times = self._process.cpu_times() if self._process is not None else None
        except PROBE_ERRORS:
            process_times = None
        values = {
            "host.disk_read_bytes": getattr(disk, "read_bytes", None),
            "host.disk_write_bytes": getattr(disk, "write_bytes", None),
            "host.disk_read_count": getattr(disk, "read_count", None),
            "host.disk_write_count": getattr(disk, "write_count", None),
            "host.net_recv_bytes": getattr(network, "bytes_recv", None),
            "host.net_send_bytes": getattr(network, "bytes_sent", None),
            "host.net_recv_packets": getattr(network, "packets_recv", None),
            "host.net_send_packets": getattr(network, "packets_sent", None),
            "host.net_errors": _sum_available([getattr(network, "errin", None), getattr(network, "errout", None)])
            if network is not None
            else None,
            "host.net_drops": _sum_available([getattr(network, "dropin", None), getattr(network, "dropout", None)])
            if network is not None
            else None,
            "host.page_in_bytes": getattr(swap, "sin", None) if os.name != "nt" else None,
            "host.page_out_bytes": getattr(swap, "sout", None) if os.name != "nt" else None,
            "process.read_bytes": getattr(process_io, "read_bytes", None),
            "process.write_bytes": getattr(process_io, "write_bytes", None),
            "process.page_faults": getattr(process_memory, "pfaults", None),
            "process.cpu_time": (getattr(process_times, "user", 0) + getattr(process_times, "system", 0))
            if process_times is not None
            else None,
        }
        for key, value in values.items():
            number = _finite(value)
            if number is not None:
                self._last_counters[key] = (number, now)

    def reset_rate_baselines(self, scopes: set[str] | None = None) -> None:
        """Forget interval counters after a real sensory discontinuity.

        Cumulative OS counters cannot describe an instantaneous level.  If a
        scope was not being sampled while every interested consciousness was
        paused or disconnected, its next reading must establish a fresh
        baseline instead of averaging activity across that unobserved gap.
        """
        selected = {"host", "process"} if scopes is None else set(scopes)
        prefixes = tuple(f"{scope}." for scope in selected)
        self._last_counters = {key: value for key, value in self._last_counters.items() if not key.startswith(prefixes)}
        if "host" in selected:
            self._last_cpu_times = None
            self._last_native_cpu = None

    def _rate(self, key: str, current: Any, now: float) -> float | None:
        number = _finite(current)
        if number is None:
            self._last_counters.pop(key, None)
            return None
        previous = self._last_counters.get(key)
        self._last_counters[key] = (number, now)
        if previous is None or now <= previous[1] or number < previous[0]:
            return None
        return (number - previous[0]) / (now - previous[1])

    def _network_reference(self) -> tuple[float, str]:
        if self.psutil is not None:
            try:
                speeds = [
                    float(stats.speed) * 1_000_000 / 8
                    for name, stats in self.psutil.net_if_stats().items()
                    if stats.isup
                    and float(stats.speed) > 0
                    and name.casefold() != "lo"
                    and "loopback" not in name.casefold()
                ]
                if speeds:
                    # Aggregate OS counters can include several concurrently
                    # active interfaces, so their physical ceiling is the sum
                    # of known link speeds rather than the fastest one alone.
                    return sum(speeds), "combined active interface link speed"
            except PROBE_ERRORS:
                pass
        return HOST_REFERENCES["network_receive_rate"], "configured fallback reference"

    @staticmethod
    def _native_charging() -> bool | None:
        if os.name != "nt":
            return None

        class PowerStatus(ctypes.Structure):
            _fields_ = [
                ("ac", ctypes.c_ubyte),
                ("flag", ctypes.c_ubyte),
                ("percent", ctypes.c_ubyte),
                ("reserved", ctypes.c_ubyte),
                ("life", ctypes.c_ulong),
                ("full", ctypes.c_ulong),
            ]

        status = PowerStatus()
        try:
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)) or status.flag == 255:
                return None
        except (AttributeError, OSError):
            return None
        return bool(status.flag & 8)

    def _host_psutil(self, now: float) -> dict[str, MetricReading]:
        output: dict[str, MetricReading] = {}
        try:
            cpu = self.psutil.cpu_times()
            total, idle = _cpu_totals(cpu)
            if self._last_cpu_times is None or total <= self._last_cpu_times[0]:
                output["cpu_load"] = MetricReading.unavailable("ratio", "CPU interval baseline is not established")
            else:
                output["cpu_load"] = MetricReading.ratio(
                    1 - max(0, idle - self._last_cpu_times[1]) / (total - self._last_cpu_times[0])
                )
            self._last_cpu_times = (total, idle)
        except PROBE_ERRORS as error:
            self._last_cpu_times = None
            output["cpu_load"] = MetricReading.unavailable("ratio", f"CPU unavailable: {error}")
        try:
            frequency = self.psutil.cpu_freq()
            output["cpu_frequency"] = MetricReading.scaled(
                float(frequency.current) * 1e6,
                unit="Hz",
                reference=float(frequency.max) * 1e6,
                reference_source="reported maximum CPU frequency",
            )
        except PROBE_ERRORS as error:
            output["cpu_frequency"] = MetricReading.unavailable("Hz", f"CPU frequency unavailable: {error}")
        try:
            memory = self.psutil.virtual_memory()
            swap = self.psutil.swap_memory()
            output["memory_pressure"] = MetricReading.ratio(float(memory.percent) / 100)
            # Commit pressure must come from a real OS commit counter.
            _native_physical, native_commit, _native_swap = self._native_memory()
            output["memory_commit_pressure"] = native_commit
            output["swap_pressure"] = (
                MetricReading.scaled(
                    float(swap.used),
                    unit="bytes",
                    reference=float(swap.total),
                    reference_source="configured swap capacity",
                )
                if swap.total
                else MetricReading.unavailable("ratio", "no swap configured")
            )
        except PROBE_ERRORS as error:
            for name in ("memory_pressure", "memory_commit_pressure", "swap_pressure"):
                output[name] = MetricReading.unavailable("ratio", f"memory unavailable: {error}")
            swap = None
        for name, attr, key in (
            ("page_in_rate", "sin", "host.page_in_bytes"),
            ("page_out_rate", "sout", "host.page_out_bytes"),
        ):
            if os.name == "nt":
                output[name] = MetricReading.unavailable(
                    "bytes/s", "psutil does not expose Windows system paging bytes"
                )
            else:
                rate = self._rate(key, getattr(swap, attr, None), now)
                output[name] = (
                    MetricReading.scaled(
                        rate, unit="bytes/s", reference=HOST_REFERENCES[name], reference_source="configured reference"
                    )
                    if rate is not None
                    else MetricReading.unavailable("bytes/s", "counter baseline or reset")
                )
        output["page_fault_rate"] = MetricReading.unavailable(
            "faults/s", "global page-fault rate needs a performance-counter plugin"
        )
        try:
            disk = self.psutil.disk_io_counters()
        except PROBE_ERRORS:
            disk = None
        for name, attr, key, unit in (
            ("disk_read_rate", "read_bytes", "host.disk_read_bytes", "bytes/s"),
            ("disk_write_rate", "write_bytes", "host.disk_write_bytes", "bytes/s"),
            ("disk_read_iops", "read_count", "host.disk_read_count", "operations/s"),
            ("disk_write_iops", "write_count", "host.disk_write_count", "operations/s"),
        ):
            rate = self._rate(key, getattr(disk, attr, None), now)
            output[name] = (
                MetricReading.scaled(
                    rate, unit=unit, reference=HOST_REFERENCES[name], reference_source="configured reference"
                )
                if rate is not None
                else MetricReading.unavailable(unit, "counter baseline, reset, or unavailable")
            )
        try:
            network = self.psutil.net_io_counters()
        except PROBE_ERRORS:
            network = None
        link_reference, link_source = self._network_reference()
        for name, attr, key, unit, reference, source in (
            ("network_receive_rate", "bytes_recv", "host.net_recv_bytes", "bytes/s", link_reference, link_source),
            ("network_send_rate", "bytes_sent", "host.net_send_bytes", "bytes/s", link_reference, link_source),
            (
                "network_receive_packets",
                "packets_recv",
                "host.net_recv_packets",
                "packets/s",
                HOST_REFERENCES["network_receive_packets"],
                "configured reference",
            ),
            (
                "network_send_packets",
                "packets_sent",
                "host.net_send_packets",
                "packets/s",
                HOST_REFERENCES["network_send_packets"],
                "configured reference",
            ),
        ):
            rate = self._rate(key, getattr(network, attr, None), now)
            output[name] = (
                MetricReading.scaled(rate, unit=unit, reference=reference, reference_source=source)
                if rate is not None
                else MetricReading.unavailable(unit, "counter baseline, reset, or unavailable")
            )
        for name, key, attrs, unit in (
            ("network_error_rate", "host.net_errors", ("errin", "errout"), "errors/s"),
            ("network_drop_rate", "host.net_drops", ("dropin", "dropout"), "drops/s"),
        ):
            current = _sum_available([getattr(network, attr, None) for attr in attrs]) if network is not None else None
            rate = self._rate(key, current, now)
            output[name] = (
                MetricReading.scaled(
                    rate, unit=unit, reference=HOST_REFERENCES[name], reference_source="configured reference"
                )
                if rate is not None
                else MetricReading.unavailable(unit, "counter baseline, reset, or unavailable")
            )
        try:
            battery = self.psutil.sensors_battery()
        except PROBE_ERRORS:
            battery = None
        if battery is None:
            output["battery_level"] = MetricReading.unavailable("ratio", "no battery counter")
            output["ac_power"] = MetricReading.unavailable("boolean", "no AC counter")
            output["battery_charging"] = MetricReading.unavailable("boolean", "no charging-state counter")
        else:
            output["battery_level"] = MetricReading.ratio(float(battery.percent) / 100)
            plugged = getattr(battery, "power_plugged", None)
            output["ac_power"] = (
                MetricReading.ratio(1 if plugged else 0, unit="boolean")
                if plugged is not None
                else MetricReading.unavailable("boolean", "AC state unavailable")
            )
            charging = self._native_charging()
            output["battery_charging"] = (
                MetricReading.ratio(1 if charging else 0, unit="boolean")
                if charging is not None
                else MetricReading.unavailable("boolean", "reliable charging flag unavailable")
            )
        return output

    def _host_native(self) -> dict[str, MetricReading]:
        counters = self._native_cpu_counters()
        if counters is not None and self._last_native_cpu is not None:
            idle, total = counters[0] - self._last_native_cpu[0], counters[1] - self._last_native_cpu[1]
            cpu = (
                MetricReading.ratio(1 - max(0, idle) / total)
                if total > 0
                else MetricReading.unavailable("ratio", "CPU baseline or reset")
            )
        else:
            cpu = MetricReading.unavailable("ratio", "native CPU counters unavailable")
        self._last_native_cpu = counters
        memory, commit, swap = self._native_memory()
        output = {"cpu_load": cpu, "memory_pressure": memory, "memory_commit_pressure": commit, "swap_pressure": swap}
        units = {
            "cpu_frequency": "Hz",
            "page_in_rate": "bytes/s",
            "page_out_rate": "bytes/s",
            "page_fault_rate": "faults/s",
            "disk_read_rate": "bytes/s",
            "disk_write_rate": "bytes/s",
            "disk_read_iops": "operations/s",
            "disk_write_iops": "operations/s",
            "network_receive_rate": "bytes/s",
            "network_send_rate": "bytes/s",
            "network_receive_packets": "packets/s",
            "network_send_packets": "packets/s",
            "network_error_rate": "errors/s",
            "network_drop_rate": "drops/s",
            "battery_level": "ratio",
            "ac_power": "boolean",
            "battery_charging": "boolean",
        }
        output.update(
            {
                name: MetricReading.unavailable(unit, "install the optional telemetry dependency")
                for name, unit in units.items()
            }
        )
        return output

    def _process_metrics(self, now: float, total_memory: float | None) -> dict[str, MetricReading]:
        if self._process is None:
            return {
                name: MetricReading.unavailable("unknown", "process telemetry requires psutil")
                for name in process_signal_names()
            }
        process = self._process
        output: dict[str, MetricReading] = {}
        try:
            times = process.cpu_times()
            rate = self._rate("process.cpu_time", float(times.user) + float(times.system), now)
            output["cpu_load"] = (
                MetricReading.ratio(rate / max(1, int(self.psutil.cpu_count() or os.cpu_count() or 1)))
                if rate is not None
                else MetricReading.unavailable("ratio", "counter baseline or reset")
            )
        except PROBE_ERRORS as error:
            self._last_counters.pop("process.cpu_time", None)
            output["cpu_load"] = MetricReading.unavailable("ratio", f"process CPU unavailable: {error}")
        try:
            memory = process.memory_info()
            reference = total_memory or float(self.psutil.virtual_memory().total)
            output["rss_pressure"] = MetricReading.scaled(
                memory.rss, unit="bytes", reference=reference, reference_source="host physical memory"
            )
            private = getattr(memory, "private", None)
            if private is None:
                try:
                    # USS is the memory unique to this process and is the
                    # closest portable equivalent to Windows private bytes.
                    private = getattr(process.memory_full_info(), "uss", None)
                except PROBE_ERRORS:
                    private = None
            output["private_memory_pressure"] = (
                MetricReading.scaled(
                    private, unit="bytes", reference=reference, reference_source="host physical memory"
                )
                if private is not None
                else MetricReading.unavailable("bytes", "private memory unavailable")
            )
            faults = getattr(memory, "pfaults", None)
            rate = self._rate("process.page_faults", faults, now)
            output["page_fault_rate"] = (
                MetricReading.scaled(
                    rate,
                    unit="faults/s",
                    reference=PROCESS_REFERENCES["page_fault_rate"],
                    reference_source="configured reference",
                )
                if rate is not None
                else MetricReading.unavailable("faults/s", "counter baseline or unavailable")
            )
        except PROBE_ERRORS as error:
            self._last_counters.pop("process.page_faults", None)
            for name in ("rss_pressure", "private_memory_pressure", "page_fault_rate"):
                output[name] = MetricReading.unavailable("ratio", f"process memory unavailable: {error}")
        try:
            io = process.io_counters()
        except PROBE_ERRORS:
            io = None
        for name, attr, key in (
            ("read_rate", "read_bytes", "process.read_bytes"),
            ("write_rate", "write_bytes", "process.write_bytes"),
        ):
            rate = self._rate(key, getattr(io, attr, None), now)
            output[name] = (
                MetricReading.scaled(
                    rate, unit="bytes/s", reference=PROCESS_REFERENCES[name], reference_source="configured reference"
                )
                if rate is not None
                else MetricReading.unavailable("bytes/s", "counter baseline or unavailable")
            )
        for name, method, unit in (
            ("thread_count", "num_threads", "threads"),
            ("handle_count", "num_handles", "handles"),
        ):
            try:
                value = getattr(process, method)()
            except PROBE_ERRORS:
                value = None
            output[name] = (
                MetricReading.scaled(
                    value, unit=unit, reference=PROCESS_REFERENCES[name], reference_source="configured reference"
                )
                if value is not None
                else MetricReading.unavailable(unit, f"{name} unavailable")
            )
        output["scheduler_latency_ms"] = MetricReading.unavailable(
            "ms", "application host has not supplied scheduler latency"
        )
        output["tick_execution_time_ms"] = MetricReading.unavailable(
            "ms",
            "application host has not supplied a read-only tick execution measurement",
        )
        return output

    def collect(
        self, monotonic_seconds: float, scopes: set[str] | None = None
    ) -> tuple[dict[str, MetricReading], dict[str, MetricReading]]:
        selected = {"host", "process"} if scopes is None else set(scopes)
        host = {
            name: MetricReading.unavailable("unknown", "host telemetry adapter is disabled")
            for name in host_signal_names()
        }
        process = {
            name: MetricReading.unavailable("unknown", "process telemetry adapter is disabled")
            for name in process_signal_names()
        }
        total: float | None = None
        if "host" in selected:
            if self.psutil is not None:
                host = self._host_psutil(monotonic_seconds)
                try:
                    total = float(self.psutil.virtual_memory().total)
                except PROBE_ERRORS:
                    total = None
            else:
                host = self._host_native()
        if "process" in selected:
            if total is None and self.psutil is not None:
                try:
                    total = float(self.psutil.virtual_memory().total)
                except PROBE_ERRORS:
                    total = None
            process = self._process_metrics(monotonic_seconds, total)
        return host, process
