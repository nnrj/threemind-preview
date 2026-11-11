"""Versioned physical telemetry encoding; all graph changes belong to Core.

This module has no OS dependency. A host supplies timestamped measurements;
encoding can be tested or replayed without measuring the current computer.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields

from threemind_core import Stimulus

from .media import parameter, validate_parameters
from .receptors import ReceptorWiring

TELEMETRY_VERSION = "physical-telemetry/3"
SCOPE_LABELS = {"host": "宿主", "process": "进程", "runtime": "实例"}
# Order is part of receptor wiring. Never insert/reorder existing entries.
METRICS = {
    "host": {
        "cpu_load": ("CPU 利用率", 1.0),
        "cpu_frequency": ("CPU 频率", 4e9),
        "memory_pressure": ("物理内存压力", 1.0),
        "memory_commit_pressure": ("提交内存压力", 1.0),
        "swap_pressure": ("交换空间压力", 1.0),
        "page_in_rate": ("换页读入", 256 * 1024.0**2),
        "page_out_rate": ("换页写出", 256 * 1024.0**2),
        "page_fault_rate": ("系统缺页率", 25000.0),
        "disk_read_rate": ("磁盘读取", 256 * 1024.0**2),
        "disk_write_rate": ("磁盘写入", 256 * 1024.0**2),
        "disk_read_iops": ("磁盘读取 IOPS", 20000.0),
        "disk_write_iops": ("磁盘写入 IOPS", 20000.0),
        "network_receive_rate": ("网络接收", 125 * 1024.0**2),
        "network_send_rate": ("网络发送", 125 * 1024.0**2),
        "network_receive_packets": ("网络接收包率", 200000.0),
        "network_send_packets": ("网络发送包率", 200000.0),
        "network_error_rate": ("网络错误率", 1000.0),
        "network_drop_rate": ("网络丢包率", 1000.0),
        "battery_level": ("电池电量", 1.0),
        "ac_power": ("交流供电", 1.0),
        "battery_charging": ("电池充电状态", 1.0),
    },
    "process": {
        "cpu_load": ("进程 CPU 利用率", 1.0),
        "rss_pressure": ("进程驻留内存", 1.0),
        "private_memory_pressure": ("进程私有内存", 1.0),
        "page_fault_rate": ("进程缺页率", 25000.0),
        "read_rate": ("进程读取", 128 * 1024.0**2),
        "write_rate": ("进程写入", 128 * 1024.0**2),
        "thread_count": ("进程线程数", 512.0),
        "handle_count": ("进程句柄数", 16384.0),
        "scheduler_latency_ms": ("当前运行调度延迟", 250.0),
        "tick_execution_time_ms": ("当前运行内核调用耗时", 250.0),
    },
    "runtime": {
        "thread_cpu_load": ("实例线程 CPU 占比", 1.0),
        "epoch_busy_ratio": ("实例内核调用忙碌占比", 1.0),
        "epoch_execution_time_ms": ("实例平均内核调用耗时", 250.0),
        "scheduler_latency_ms": ("实例平均调度延迟", 250.0),
    },
}


@dataclass(frozen=True)
class SignalConfig:
    level: bool = parameter(True, "水平通道")
    change: bool = parameter(True, "变化通道")
    gain: float = parameter(1.0, "增益", 0, 100)
    reference_override: bool = parameter(False, "手动归一化尺度", hint="关闭时使用探针提供的尺度。")
    reference: float = parameter(1.0, "参考尺度", 1e-12, 1e18, hint="单位与原始测量一致；仅手动尺度开启时生效。")

    def __post_init__(self):
        validate_parameters(self)


@dataclass(frozen=True)
class TelemetryConfig:
    # Missing historical fields mean 1; creation services explicitly choose .2.
    intensity: float = parameter(
        1.0, "总输入强度", 0, 100, hint="原始物理量与通道映射保持不变；0 表示不施加输入量。新建默认 0.2。"
    )
    enabled: bool = parameter(False, "启用", hint="来自真实物理计数，仅允许实时调度；会作为刺激影响模型。")
    sample_interval_ms: int = parameter(1000, "真实采样间隔", 100, 60000, unit="ms")
    smoothing_tau_s: float = parameter(
        4.481420117724551,
        "平滑时间常数",
        0,
        3600,
        unit="s",
        hint="指数平滑；0 关闭平滑。默认在 1 秒间隔下保留旧值的 80%。",
    )
    levels_enabled: bool = parameter(True, "全部水平通道")
    changes_enabled: bool = parameter(True, "全部变化通道")
    signals: dict[str, SignalConfig] = field(default_factory=dict)

    def __post_init__(self):
        for f in fields(self):
            if f.name == "signals":
                continue
            value, kind = getattr(self, f.name), type(f.default)
            if not (type(value) is kind or kind is float and type(value) is int):
                raise ValueError(f"telemetry.{f.name}: invalid type")
            if kind in (int, float) and (
                not math.isfinite(value) or not f.metadata["minimum"] <= value <= f.metadata["maximum"]
            ):
                raise ValueError(f"telemetry.{f.name}: outside supported range")
        scope = self.scope
        if not isinstance(self.signals, dict) or set(self.signals) - set(METRICS[scope]):
            raise ValueError(f"unknown {scope} telemetry signal")
        normalized = {}
        for name, (_, reference) in METRICS[scope].items():
            value = self.signals.get(name, SignalConfig(reference=reference))
            normalized[name] = SignalConfig(**value) if isinstance(value, dict) else value
            if not isinstance(normalized[name], SignalConfig):
                raise ValueError(f"invalid telemetry signal: {name}")  # noqa: TRY004 -- public configuration validation
        object.__setattr__(self, "signals", normalized)


@dataclass(frozen=True)
class HostTelemetryConfig(TelemetryConfig):
    scope = "host"


@dataclass(frozen=True)
class ProcessTelemetryConfig(TelemetryConfig):
    scope = "process"


@dataclass(frozen=True)
class RuntimeTelemetryConfig(TelemetryConfig):
    scope = "runtime"


TELEMETRY_CONFIGS = {
    "host_telemetry": HostTelemetryConfig,
    "process_telemetry": ProcessTelemetryConfig,
    "runtime_telemetry": RuntimeTelemetryConfig,
}


def telemetry_parameters():
    """Same typed fields provide GUI entries and portable validation contracts."""
    for root, cls in TELEMETRY_CONFIGS.items():
        config = cls()
        for f in fields(config):
            if f.name == "signals":
                for name, signal in config.signals.items():
                    for sf in fields(signal):
                        yield (
                            root,
                            f"signals.{name}.{sf.name}",
                            sf,
                            getattr(signal, sf.name),
                            METRICS[cls.scope][name][0],
                        )
            else:
                yield root, f.name, f, getattr(config, f.name), SCOPE_LABELS[cls.scope]


class TelemetryEncoder(ReceptorWiring):
    def __init__(self, seed, config: TelemetryConfig, state=None):
        super().__init__(seed)
        self.config = config
        self.previous = {}
        self.last_time = None
        self.version = TELEMETRY_VERSION
        if state:
            legacy = state.get("version") == "physical-telemetry/2"
            saved_config = dict(state.get("config", {}))
            if legacy:
                if "intensity" in saved_config:
                    raise ValueError("legacy telemetry cannot declare intensity")
                saved_config["intensity"] = 1.0
            if (
                state.get("version") not in ("physical-telemetry/2", TELEMETRY_VERSION)
                or saved_config != asdict(config)
                or state.get("seed") != seed
            ):
                raise ValueError("telemetry encoder state/config mismatch")
            self.version = state["version"]
            self.previous = dict(state["previous"])
            self.last_time = state["last_time"]
            if (
                set(self.previous) - set(METRICS[config.scope])
                or self.last_time is not None
                and (type(self.last_time) not in (float, int) or not math.isfinite(self.last_time))
                or any(
                    type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1
                    for v in self.previous.values()
                )
            ):
                raise ValueError("invalid telemetry baseline")

    def capture(self):
        return {
            "version": self.version,
            "config": {
                k: v for k, v in asdict(self.config).items() if k != "intensity" or self.version == TELEMETRY_VERSION
            },
            "seed": self.seed,
            "previous": dict(self.previous),
            "last_time": self.last_time,
        }

    def encode(self, measurements: dict, *, monotonic_s: float, delivery_us: int):
        if not math.isfinite(monotonic_s) or self.last_time is not None and monotonic_s <= self.last_time:
            raise ValueError("telemetry samples require increasing monotonic timestamps")
        dt = None if self.last_time is None else monotonic_s - self.last_time
        self.last_time = monotonic_s
        alpha = math.exp(-dt / self.config.smoothing_tau_s) if dt and self.config.smoothing_tau_s else 0.0
        channels, audit = [], {}
        scope_index = list(METRICS).index(self.config.scope)
        for index, name in enumerate(METRICS[self.config.scope]):
            signal = self.config.signals[name]
            raw = dict(measurements.get(name, {"available": False, "unavailable_reason": "metric not supplied"}))
            value = raw.get("normalized_level")
            if raw.get("available") and signal.reference_override and raw.get("raw_value") is not None:
                value = raw["raw_value"] / signal.reference
            if not raw.get("available") or value is None or not math.isfinite(value):
                self.previous.pop(name, None)
                audit[name] = {"raw": raw, "encoded": False, "channels": {}}
                continue
            value = min(1.0, max(0.0, value))
            old = self.previous.get(name)
            smoothed = value if old is None else alpha * old + (1 - alpha) * value
            self.previous[name] = smoothed
            values = (
                smoothed,
                max(0, smoothed - old) if old is not None else 0,
                max(0, old - smoothed) if old is not None else 0,
            )
            emitted = {}
            for component, amount in enumerate(values):
                enabled = (
                    self.config.levels_enabled and signal.level
                    if component == 0
                    else self.config.changes_enabled and signal.change
                )
                amplitude = min(1.0, amount * signal.gain)
                if self.config.enabled and enabled and amplitude > 0:
                    receptor = self.identity(0x3000000 + scope_index * 4096 + index * 3 + component)
                    channels.append((receptor, amplitude))
                    emitted[("level", "rise", "fall")[component]] = receptor
            audit[name] = {
                "raw": raw,
                "normalized_level": value,
                "smoothed_level": smoothed,
                "rise": values[1],
                "fall": values[2],
                "baseline_established": old is not None,
                "encoded": bool(emitted),
                "channels": emitted,
                "reference": signal.reference if signal.reference_override else raw.get("reference"),
                "reference_source": "explicit adapter reference"
                if signal.reference_override
                else raw.get("reference_source"),
            }
        return (Stimulus(delivery_us, tuple(sorted(channels)), self.config.intensity) if channels else None), audit


class ExecutionMeter:
    """Only time spent inside this runtime's Core advance calls is attributed."""

    def __init__(self, start_s):
        self.start_s = start_s
        self.wall_s = self.cpu_s = self.latency_s = 0.0
        self.calls = 0

    def add(self, wall_s, cpu_s, latency_s):
        if not all(math.isfinite(x) and x >= 0 for x in (wall_s, cpu_s, latency_s)):
            raise ValueError("invalid execution measurement")
        self.wall_s += wall_s
        self.cpu_s += cpu_s
        self.latency_s += latency_s
        self.calls += 1

    def close(self, now_s):
        elapsed = now_s - self.start_s
        output = {}
        for name, (value, unit, reference) in {
            "thread_cpu_load": (self.cpu_s / elapsed if elapsed > 0 else None, "ratio", 1.0),
            "epoch_busy_ratio": (self.wall_s / elapsed if elapsed > 0 else None, "ratio", 1.0),
            "epoch_execution_time_ms": (self.wall_s * 1000 / self.calls if self.calls else None, "ms", 250.0),
            "scheduler_latency_ms": (self.latency_s * 1000 / self.calls if self.calls else None, "ms", 250.0),
        }.items():
            output[name] = {
                "available": value is not None,
                "raw_value": value,
                "unit": unit,
                "normalized_level": min(1.0, value / reference) if value is not None else None,
                "reference": reference,
                "reference_source": "measured Core calls / monotonic interval",
                "unavailable_reason": None if value is not None else "no measured Core calls",
            }
        context = {
            "interval_s": elapsed,
            "core_calls": self.calls,
            "core_wall_s": self.wall_s,
            "thread_cpu_s": self.cpu_s,
        }
        self.__init__(now_s)
        return output, context
