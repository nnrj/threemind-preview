"""Explicit external signal fixtures and a recoverable non-semantic body filter."""

import math
import random
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields

from threemind_core import Stimulus

from .adapters import channel_id


def parameter(default, label, unit, hint, **bounds):
    return field(default=default, metadata={"label": label, "unit": unit, "hint": hint, "immutable": False, **bounds})


class Validated:
    def __post_init__(self):
        for f in fields(self):
            value = getattr(self, f.name)
            expected = type(f.default)
            if expected in (bool, int) and type(value) is not expected:
                raise ValueError(f"{f.name} has invalid type")
            if expected is float:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"{f.name} must be finite")
                object.__setattr__(self, f.name, float(value))
            if value < f.metadata.get("minimum", -math.inf) or value > f.metadata.get("maximum", math.inf):
                raise ValueError(f"{f.name} is outside its range")


@dataclass(frozen=True)
class AmbientConfig(Validated):
    sample_us: int = parameter(
        100000,
        "环境场采样间隔",
        "μs",
        "仅用于显式选择的合成环境场；默认物理环境不使用它。",
        minimum=1000,
        maximum=10000000,
    )
    transient_rate_per_s: float = parameter(
        0.4,
        "扰动出现率",
        "／模拟秒",
        "每个采样间隔按 1−exp(−速率×间隔) 判定一次，最多新增一个扰动。",
        minimum=0,
        maximum=10000,
    )
    transient_amplitude: float = parameter(
        0.12, "扰动幅度", "", "无语义的有限寿命载体，不直接改写模型连接。", minimum=0, maximum=1
    )
    lifetime_min_us: int = parameter(
        200000, "扰动最短寿命", "μs", "以模拟时间计算，在到期时不再出现在载体中。", minimum=1, maximum=10000000000
    )
    lifetime_max_us: int = parameter(
        1400000, "扰动最长寿命", "μs", "最短与最长之间均匀抽样；寿命不是记忆保留时间。", minimum=1, maximum=10000000000
    )
    maximum_transients: int = parameter(
        512, "同时存在的扰动上限", "个", "达到上限时记录未创建数量，不从内核删除节点。", minimum=1, maximum=100000
    )
    intensity: float = parameter(1.0, "环境场输入强度", "", "仅缩放这个外部工具的载体。", minimum=0, maximum=2)

    def __post_init__(self):
        super().__post_init__()
        if self.lifetime_max_us < self.lifetime_min_us:
            raise ValueError("扰动最长寿命不能小于最短寿命。")


@dataclass(frozen=True)
class BodyFilterConfig(Validated):
    enabled: bool = parameter(
        False, "启用环境躯体过滤", "", "仅过滤模拟物理／合成环境载体；不改写文字、文件和网络设备输入。"
    )
    sample_us: int = parameter(
        100000,
        "躯体采样间隔",
        "μs",
        "同一采样时刻的独立载体均可通过，较密采样记录为未感知。",
        minimum=1000,
        maximum=10000000,
    )
    threshold: float = parameter(0.035, "躯体感知阈值", "", "编码幅度低于阈值的通道不递送。", minimum=0, maximum=1)
    adaptation: float = parameter(
        0.55, "躯体适应比例", "", "混合稳定信号泄漏与相对基线的变化；不是内核注意选择。", minimum=0, maximum=1
    )
    noise: float = parameter(
        0.02, "躯体测量噪声", "", "显式模拟测量噪声，均匀分布于正负该幅度；种子与状态可恢复。", minimum=0, maximum=0.5
    )
    channel_count: int = parameter(
        3, "躯体单帧通道容量", "个", "保留当前编码幅度最大的通道，并列按通道编号；记录被过滤量。", minimum=1, maximum=64
    )
    baseline_tau_s: float = parameter(
        1.2,
        "躯体基线时间常数",
        "模拟秒",
        "基线按两次测量的实际模拟间隔更新，不依赖宿主帧率。",
        minimum=0.000001,
        maximum=1e6,
    )
    baseline_capacity: int = parameter(
        4096,
        "躯体基线通道上限",
        "个",
        "达到上限时淘汰最久未观测的基线，计数并记录；不淘汰模型节点。",
        minimum=64,
        maximum=100000,
    )


@dataclass(frozen=True)
class InteroceptionConfig(Validated):
    enabled: bool = parameter(False, "启用模拟内感受", "", "独立的显式周期载体，不是模型自发活动或真实生理测量。")
    sample_us: int = parameter(
        100000,
        "内感受采样间隔",
        "μs",
        "模拟身体按这个间隔生成载体；关闭全部来源后停止。",
        minimum=1000,
        maximum=10000000,
    )
    channel_count: int = parameter(
        2, "内感受通道数", "个", "固定感官种子映射，修改数量不会直接修改模型节点。", minimum=1, maximum=64
    )
    amplitude: float = parameter(
        0.08, "内感受幅度", "", "周期信号的最大幅度，默认低幅；只在显式开启后发生。", minimum=0, maximum=1
    )
    intensity: float = parameter(
        1.0, "内感受输入强度", "", "该外部载体的强度，不向能量账本补给。", minimum=0, maximum=2
    )


BODY_CONFIGS = {"ambient_field": AmbientConfig, "body_filter": BodyFilterConfig, "interoception": InteroceptionConfig}


def _tuples(value):
    return tuple(_tuples(v) for v in value) if isinstance(value, (list, tuple)) else value


class BodyFilter:
    def __init__(self, config, seed, state=None):
        self.config, self.seed = config, seed
        self.rng = random.Random(seed ^ 0x424F4459)
        self.baseline = {}
        self.last_sample_us = None
        self.counters = {
            k: 0 for k in ("frames", "sampling_filtered", "channels_seen", "channels_passed", "baseline_evicted")
        }
        if state:
            if state["schema"] != "threemind.body-filter/1" or state["seed"] != seed:
                raise ValueError("incompatible body filter state")
            if state["rng"] is not None:
                self.rng.setstate(_tuples(state["rng"]))
            self.baseline = {int(k): list(v) for k, v in state["baseline"].items()}
            self.last_sample_us = state["last_sample_us"]
            self.counters.update(state["counters"])
        self._trim()

    def _trim(self):
        excess = len(self.baseline) - self.config.baseline_capacity
        if excess > 0:
            for key in sorted(self.baseline, key=lambda k: (self.baseline[k][1], k))[:excess]:
                del self.baseline[key]
            self.counters["baseline_evicted"] += excess

    def process(self, raw):
        cfg = self.config
        if not cfg.enabled:
            return raw, {"reason": "bypass", "raw_channels": len(raw.channels), "passed_channels": len(raw.channels)}
        self.counters["frames"] += 1
        self.counters["channels_seen"] += len(raw.channels)
        if self.last_sample_us is not None and raw.time_us < self.last_sample_us:
            raise ValueError("body input cannot move backwards")
        if self.last_sample_us is not None and 0 < raw.time_us - self.last_sample_us < cfg.sample_us:
            self.counters["sampling_filtered"] += 1
            return None, {"reason": "body_sampling", "raw_channels": len(raw.channels), "passed_channels": 0}
        self.last_sample_us = raw.time_us
        sensed = []
        for channel, value in sorted(raw.channels):
            value = max(0.0, min(1.0, value + self.rng.uniform(-cfg.noise, cfg.noise)))
            prior, last = self.baseline.get(channel, (value, raw.time_us))
            encoded = min(1.0, value * (1 - cfg.adaptation) + abs(value - prior) * cfg.adaptation)
            alpha = -math.expm1(-(raw.time_us - last) / 1e6 / cfg.baseline_tau_s)
            self.baseline[channel] = [prior + alpha * (value - prior), raw.time_us]
            if encoded > 0 and encoded >= cfg.threshold:
                sensed.append((channel, encoded))
        self._trim()
        selected = sorted(sensed, key=lambda pair: (-pair[1], pair[0]))[: cfg.channel_count]
        self.counters["channels_passed"] += len(selected)
        evidence = {
            "reason": "body_passed" if selected else "body_threshold",
            "raw_channels": len(raw.channels),
            "above_threshold": len(sensed),
            "passed_channels": len(selected),
            "counters": dict(self.counters),
        }
        return (Stimulus(raw.time_us, tuple(selected), raw.intensity) if selected else None), evidence

    def capture(self):
        return {
            "schema": "threemind.body-filter/1",
            "seed": self.seed,
            "configuration": asdict(self.config),
            "rng": self.rng.getstate() if self.counters["frames"] else None,
            "baseline": deepcopy(self.baseline),
            "last_sample_us": self.last_sample_us,
            "counters": dict(self.counters),
        }


class AmbientField:
    """Opt-in synthetic carrier fixture. Never presented as measured physical input."""

    def __init__(self, config, seed, state=None, *, environment_seed=None):
        self.config, self.seed = config, seed
        self.environment_seed = environment_seed
        self.rng = random.Random((seed if environment_seed is None else environment_seed) ^ 0x414D4249)
        self.phase, self.fast_offset, self.drift = (
            self.rng.random() * math.tau,
            self.rng.randrange(11),
            self.rng.random(),
        )
        self.transients = {}
        self.sequence = self.rejected_transients = 0
        if state:
            if (
                state["schema"] != "threemind.ambient-fixture/1"
                or state["seed"] != seed
                or state.get("environment_seed") != environment_seed
            ):
                raise ValueError("incompatible ambient fixture state")
            for key in ("phase", "fast_offset", "drift", "sequence", "rejected_transients"):
                setattr(self, key, state[key])
            self.rng.setstate(_tuples(state["rng"]))
            self.transients = {int(k): int(v) for k, v in state["transients"].items()}

    def sample(self, start_us):
        cfg = self.config
        when = start_us + cfg.sample_us
        dt = cfg.sample_us / 1e6
        self.drift += -math.expm1(-dt / 0.663) * (self.rng.random() - self.drift)
        slow = min(7, int((math.sin(when / 4.7e6 + self.phase) + 1) * 4))
        fast = (when // 100000 + self.fast_offset) % 11
        drift = min(12, int(self.drift * 13))
        values = [
            (channel_id(self.seed, "ambient-fixture-slow", slow), 0.42),
            (channel_id(self.seed, "ambient-fixture-fast", fast), 0.2),
            (channel_id(self.seed, "ambient-fixture-drift", drift), 0.3),
        ]
        self.transients = {k: expiry for k, expiry in self.transients.items() if when < expiry}
        if self.rng.random() < -math.expm1(-cfg.transient_rate_per_s * dt):
            self.sequence += 1
            channel = channel_id(self.seed, "ambient-fixture-disturbance", self.sequence)
            expiry = when + self.rng.randint(cfg.lifetime_min_us, cfg.lifetime_max_us)
            if len(self.transients) < cfg.maximum_transients:
                self.transients[channel] = expiry
            else:
                self.rejected_transients += 1
        result = [("ambient-fixture", Stimulus(when, tuple(values), cfg.intensity))]
        if self.transients and cfg.transient_amplitude > 0:
            result.append(
                (
                    "ambient-disturbance",
                    Stimulus(when, tuple((k, cfg.transient_amplitude) for k in sorted(self.transients)), cfg.intensity),
                )
            )
        return result

    def capture(self):
        return {
            "schema": "threemind.ambient-fixture/1",
            "seed": self.seed,
            "configuration": asdict(self.config),
            "rng": self.rng.getstate(),
            "phase": self.phase,
            "fast_offset": self.fast_offset,
            "drift": self.drift,
            "sequence": self.sequence,
            "rejected_transients": self.rejected_transients,
            "transients": dict(self.transients),
            **({"environment_seed": self.environment_seed} if self.environment_seed is not None else {}),
        }


def interoceptive_frame(config, seed, when):
    channels = tuple(
        (
            channel_id(seed, "simulated-interoception", index),
            config.amplitude * (0.35 + 0.65 * (math.sin(when / 1e6 / (0.9 + index * 0.7)) + 1) / 2),
        )
        for index in range(config.channel_count)
    )
    return Stimulus(when, channels, config.intensity)


class EnvironmentHost:
    """Owns external state, independent of any database or Core internals."""

    def __init__(self, spec, now, *, state=None, environment_state=None, next_input_us=None):
        from .adapters import PlanarBody

        self.spec = spec
        self.environment_seed = getattr(spec, "environment_seed", None)
        state = state or {}
        if state and (
            state.get("schema") != "threemind.body-tools/1"
            or state.get("seed") != spec.seed
            or state.get("environment_seed") != self.environment_seed
        ):
            raise ValueError("incompatible external body tools")
        saved_ambient = state.get("ambient") if state.get("environment") == spec.environment else None
        self.ambient = (
            AmbientField(spec.ambient_field, spec.seed, saved_ambient, environment_seed=self.environment_seed)
            if spec.environment == "ambient"
            else None
        )
        self.body = BodyFilter(spec.body_filter, spec.seed, state.get("body_filter"))
        self.next_environment_us = max(
            now, int(next_input_us if next_input_us is not None else state.get("next_environment_us", now))
        )
        interoception_deadline = int(state.get("next_interoception_us", now))
        # An inactive sensor has no pending sample. Preserve its recorded clock
        # across resume; enabling it later clamps the deadline to the current time.
        self.next_interoception_us = (
            max(now, interoception_deadline) if spec.interoception.enabled else interoception_deadline
        )
        self.interoceptive_samples = state.get("interoceptive_samples", 0)
        self.environment_samples = state.get("environment_samples", 0)
        # Allocate optional graphics resources only after other recovery fields
        # have validated, so an invalid body filter cannot leak an RGB context.
        self.physical = (
            PlanarBody(spec.seed, environment_state, environment_seed=self.environment_seed)
            if spec.environment == "mujoco"
            else None
        )
        if spec.environment == "world":
            from .world import PhysicalWorld

            self.physical = PhysicalWorld(
                spec.world_protocol, spec.seed, environment_state, environment_seed=self.environment_seed
            )
        if spec.environment == "robot":
            from .robot_factory import create_robot_world

            self.physical = create_robot_world(
                spec.robot_protocol, spec.seed, environment_state, environment_seed=self.environment_seed
            )

    def deadline(self, source_enabled=True):
        if not source_enabled:
            return None
        times = []
        if self.physical or self.ambient:
            times.append(self.next_environment_us)
        if self.spec.interoception.enabled:
            times.append(self.next_interoception_us)
        return min(times, default=None)

    def poll(self, engine, emit, *, source_enabled=True):
        if not source_enabled:
            return
        now = engine.time_us
        if (self.physical or self.ambient) and now >= self.next_environment_us:
            if self.physical:
                graph = engine.activations() if self.spec.actuator_feedback else None
                frames = [("mujoco", self.physical.sample(now, graph))]
                period = self.physical.period_us
            else:
                frames = self.ambient.sample(now)
                period = self.spec.ambient_field.sample_us
            for index, (source, raw) in enumerate(frames):
                effective, evidence = self.body.process(raw)
                world_provenance = {}
                if self.spec.environment in ("world", "robot"):
                    world_provenance = {
                        "world_hash": self.physical.protocol_hash,
                        "physical_hash": self.physical.physical_hash,
                        "mujoco_version": self.physical.mj.__version__,
                        "encoding": "world-port-v1",
                        "frame_grouping": "whole-body-sample",
                    }
                    if self.spec.environment == "robot":
                        world_provenance.update(robot_task_hash=self.physical.task.digest,
                                                control_mode=self.physical.task.control.mode)
                    evidence = evidence | {
                        "world": {
                            "physical_time_us": str(self.physical.elapsed_us),
                            "delivery_time_us": str(raw.time_us),
                            "measurements": deepcopy(self.physical.last_measurements),
                            "controls": deepcopy(self.physical.last_controls),
                            **(
                                {"stimulus_unit": self.physical.stimulus_unit(raw, capture_us=self.physical.elapsed_us)}
                                if self.physical.spec.schema_id == "threemind.world/2" and raw.channels
                                else {}
                            ),
                        }
                    }
                emit(
                    f"environment:{now}:{index}",
                    source,
                    effective if effective is not None else Stimulus(raw.time_us, (), raw.intensity),
                    raw_stimulus=raw,
                    filter_reason=None if effective is not None else evidence["reason"],
                    transduction=evidence,
                    configuration={
                        "seed": self.spec.seed,
                        "environment": self.spec.environment,
                        "actuator_feedback": self.spec.actuator_feedback,
                        "period_us": period,
                        "body_filter": asdict(self.spec.body_filter),
                        "ambient_field": asdict(self.spec.ambient_field) if self.ambient else None,
                        **world_provenance,
                        **({"environment_seed": self.environment_seed} if self.environment_seed is not None else {}),
                    },
                )
                self.environment_samples += 1
            self.next_environment_us = now + period
        if self.spec.interoception.enabled and now >= self.next_interoception_us:
            cfg = self.spec.interoception
            when = now + cfg.sample_us
            raw = interoceptive_frame(cfg, self.spec.seed, when)
            emit(
                f"interoception:{now}",
                "simulated-interoception",
                raw,
                configuration={"seed": self.spec.seed, **asdict(cfg)},
            )
            self.interoceptive_samples += 1
            self.next_interoception_us = when

    def capture(self):
        return {
            "schema": "threemind.body-tools/1",
            "seed": self.spec.seed,
            "environment": self.spec.environment,
            "ambient": self.ambient.capture() if self.ambient else None,
            "body_filter": self.body.capture(),
            "next_environment_us": str(self.next_environment_us),
            "next_interoception_us": str(self.next_interoception_us),
            "interoceptive_samples": self.interoceptive_samples,
            "environment_samples": self.environment_samples,
            **({"environment_seed": self.environment_seed} if self.environment_seed is not None else {}),
        }

    def physical_state(self):
        return self.physical.capture() if self.physical else None

    def close(self):
        if self.physical is not None and hasattr(self.physical, "close"):
            self.physical.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
