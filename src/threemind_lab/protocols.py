from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from threemind_kernels.registry import BASELINE_KERNEL, resolve_kernel
from threemind_runtime.body import AmbientConfig, BodyFilterConfig, InteroceptionConfig
from threemind_runtime.energy_supply import EnergySupplyConfig
from threemind_runtime.live_media import LiveCaptureConfig
from threemind_runtime.media import AcousticConfig, AuditoryConfig, ProjectorConfig, VisualConfig
from threemind_runtime.readout_config import ActivityReadoutConfig, StructuralReadoutConfig, TemporalReadoutConfig
from threemind_runtime.robot_protocol import PlaygroundRobotTask, RobotTask, parse_robot
from threemind_runtime.sensory import InputBusConfig, TextSensorConfig
from threemind_runtime.source_policies import SourcePolicies
from threemind_runtime.telemetry import HostTelemetryConfig, ProcessTelemetryConfig, RuntimeTelemetryConfig
from threemind_runtime.world_schema import WorldSpec, parse_world


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


NodeId = Annotated[int, Field(ge=0, le=2**32 - 1, strict=True)]


class Intervention(StrictModel):
    nodes: list[NodeId] = Field(default_factory=list, max_length=100000)
    edges: list[tuple[NodeId, NodeId]] = Field(default_factory=list, max_length=100000)
    lesion: bool = False
    action: Literal["silence", "unsilence", "disconnect_edges", "delete_nodes"] | None = None

    @model_validator(mode="after")
    def valid_action(self):
        if self.action and self.lesion:
            raise ValueError("action 与旧 lesion 参数不能同时指定")
        if self.action == "disconnect_edges" and self.nodes:
            raise ValueError("断连操作请选择连接；删点请使用 delete_nodes")
        return self


class Phase(StrictModel):
    name: str = Field(min_length=1, max_length=40, pattern=r"^[\w\-\u4e00-\u9fff ]+$")
    duration_s: float = Field(gt=0, le=86400)
    input_enabled: bool = True
    close_sources: bool = False


class RunSpec(StrictModel):
    # Historical serialized protocols without an identity mean the original baseline.
    # New creation endpoints and the catalogue explicitly select the current default.
    kernel_id: str = BASELINE_KERNEL
    environment: Literal["mujoco", "host", "manual", "replay", "ambient", "world", "robot"] = "mujoco"
    world_protocol: WorldSpec | None = None
    robot_protocol: PlaygroundRobotTask | RobotTask | None = None
    clock: Literal["realtime", "scaled", "unbounded"] = "realtime"
    speed: float = Field(default=1, gt=0, le=1e6)
    duration_s: float | None = Field(default=None, gt=0, le=86400)
    seed: int = Field(default=20260724, ge=0, le=2**32 - 1)
    environment_seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    config: dict = Field(default_factory=dict)
    sample_us: int = Field(default=100000, ge=1000, le=10000000)
    checkpoint_us: int = Field(default=2000000, ge=10000, le=10000000)
    trace: bool = False
    record_spikes: bool = True
    replay: list[dict] = Field(default_factory=list, max_length=100000)
    intervention: Intervention | None = None
    study_id: str | None = None
    condition: str | None = None
    block_seed: int | None = None
    phases: list[Phase] = Field(default_factory=list, max_length=32)
    max_channels: int | None = Field(default=None, ge=1, le=1024)
    actuator_feedback: bool = True
    text_sensor: TextSensorConfig = Field(default_factory=TextSensorConfig)
    input_bus: InputBusConfig = Field(default_factory=InputBusConfig)
    source_policies: SourcePolicies = Field(default_factory=SourcePolicies)
    auditory_sensor: AuditoryConfig = Field(default_factory=AuditoryConfig)
    visual_sensor: VisualConfig = Field(default_factory=VisualConfig)
    acoustic_output: AcousticConfig = Field(default_factory=AcousticConfig)
    activation_projector: ProjectorConfig = Field(default_factory=ProjectorConfig)
    host_telemetry: HostTelemetryConfig = Field(default_factory=HostTelemetryConfig)
    process_telemetry: ProcessTelemetryConfig = Field(default_factory=ProcessTelemetryConfig)
    runtime_telemetry: RuntimeTelemetryConfig = Field(default_factory=RuntimeTelemetryConfig)
    structural_readout: StructuralReadoutConfig = Field(default_factory=StructuralReadoutConfig)
    temporal_readout: TemporalReadoutConfig = Field(default_factory=TemporalReadoutConfig)
    # Missing in historical protocols: do not silently add an observer on restore.
    # The new-consciousness catalogue explicitly enables the new analysis.
    activity_readout: ActivityReadoutConfig = Field(default_factory=lambda: ActivityReadoutConfig(enabled=False))
    live_capture: LiveCaptureConfig = Field(default_factory=LiveCaptureConfig)
    energy_supply: EnergySupplyConfig = Field(default_factory=EnergySupplyConfig)
    ambient_field: AmbientConfig = Field(default_factory=AmbientConfig)
    body_filter: BodyFilterConfig = Field(default_factory=BodyFilterConfig)
    interoception: InteroceptionConfig = Field(default_factory=InteroceptionConfig)

    @field_validator("world_protocol", mode="before")
    @classmethod
    def world_value(cls, value):
        return value if value is None or isinstance(value, WorldSpec) else parse_world(value)

    @field_validator("robot_protocol", mode="before")
    @classmethod
    def robot_value(cls, value):
        return None if value is None else parse_robot(value)

    @model_validator(mode="after")
    def validate_protocol(self):
        if self.environment == "world" and self.world_protocol is None:
            raise ValueError("可配置物理环境需要完整的世界与躯体协议。")
        if self.environment == "robot" and self.robot_protocol is None:
            raise ValueError("机器人环境需要完整的任务、躯体和控制协议。")
        if self.environment == "host" and "host_telemetry" not in self.model_fields_set:
            self.host_telemetry = HostTelemetryConfig(enabled=True)
        try:
            descriptor = resolve_kernel(self.kernel_id)
            descriptor.configuration(self.config)
        except TypeError as exc:
            raise ValueError(str(exc)) from exc
        if self.energy_supply.enabled and "causal_energy" not in descriptor.capabilities:
            raise ValueError("此内核不使用 causal 能量账本，不能启用该供能适配器。膜电流不能冒充能量。")
        if self.kernel_id == "unified-associative":
            from threemind_runtime.sensory import TextSensorConfig

            original_defaults = TextSensorConfig()
            for key in ("encoding", "channel_count", "normalization", "gain", "frame_interval_us"):
                if getattr(self.text_sensor, key) != getattr(original_defaults, key):
                    raise ValueError(f"unified-associative uses its original config.sensory_encoding and epoch transport; text_sensor.{key} is inapplicable")
        if self.duration_s is not None and round(self.duration_s * 1e6) < 1:
            raise ValueError("run duration must be at least one microsecond")
        if self.environment == "host" and self.clock != "realtime":
            raise ValueError("host physical telemetry requires realtime scheduling")
        if (
            any(c.enabled for c in (self.host_telemetry, self.process_telemetry, self.runtime_telemetry))
            and self.clock != "realtime"
        ):
            raise ValueError("物理遥测只能在实时模式运行；加速实验请使用已记录的刺激重放。")
        numerical_step = getattr(descriptor.configuration(self.config), "step_us", None)
        if self.trace and numerical_step is not None and self.sample_us < numerical_step:
            raise ValueError("observation period must not be smaller than the numerical step")
        from threemind_core import Stimulus

        for item in self.replay:
            Stimulus.from_dict(item)
        if self.phases:
            if self.duration_s is None:
                raise ValueError("分阶段实验需要明确的有限观察时长；普通意识可不设时长。")
            if len({p.name for p in self.phases}) != len(self.phases):
                raise ValueError("phase names must be unique")
            if sum(round(p.duration_s * 1e6) for p in self.phases) != round(self.duration_s * 1e6):
                raise ValueError("phase durations must sum to run duration at microsecond precision")
            closed = False
            for phase in self.phases:
                if round(phase.duration_s * 1e6) < 1:
                    raise ValueError("phase duration must be at least one microsecond")
                closed |= phase.close_sources
                if closed and phase.input_enabled:
                    raise ValueError("closed sources cannot be reopened by a later phase")
            if self.environment not in ("mujoco", "replay", "ambient", "world", "robot"):
                raise ValueError("scheduled phases require a simulated, recorded or explicit synthetic environment")
        return self

    def deadline_us(self, start_us: int) -> int | None:
        """An optional experiment endpoint, never a Core lifetime or wall-clock limit."""
        return None if self.duration_s is None else start_us + round(self.duration_s * 1e6)


class Arm(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    config_patch: dict = Field(default_factory=dict)
    intervention: Intervention | None = None
    phases: list[Phase] | None = None
    max_channels: int | None = Field(default=None, ge=1, le=1024)
    actuator_feedback: bool | None = None
    energy_supply: EnergySupplyConfig | None = None
    body_filter: BodyFilterConfig | None = None
    interoception: InteroceptionConfig | None = None
    runtime_patch: dict = Field(default_factory=dict)


# Changes apply after shared development. Identity, external clock and recording
# membership stay common; typed Runtime components keep their actual validators.
ARM_LEGACY_ROOTS = ("phases", "max_channels", "actuator_feedback", "energy_supply", "body_filter", "interoception")
ARM_RUNTIME_ROOTS = {
    "max_channels",
    "actuator_feedback",
    "sample_us",
    "checkpoint_us",
    "trace",
    "record_spikes",
    "text_sensor",
    "input_bus",
    "source_policies",
    "auditory_sensor",
    "visual_sensor",
    "acoustic_output",
    "activation_projector",
    "host_telemetry",
    "process_telemetry",
    "runtime_telemetry",
    "structural_readout",
    "temporal_readout",
    "activity_readout",
    "live_capture",
    "energy_supply",
    "ambient_field",
    "body_filter",
    "interoception",
}


def resolve_arm(base: RunSpec, arm: Arm) -> RunSpec:
    """The one execution/validation path for historical and new condition forms."""
    unknown = set(arm.runtime_patch) - ARM_RUNTIME_ROOTS
    if unknown:
        raise ValueError(f"条件 {arm.name}：不能在 runtime_patch 修改 {', '.join(sorted(unknown))}")
    updates = {"config": base.config | arm.config_patch, "intervention": arm.intervention}
    source = base.model_dump()
    for name in ARM_LEGACY_ROOTS:
        if getattr(arm, name) is not None:
            if name in arm.runtime_patch:
                raise ValueError(f"条件 {arm.name}：{name} 不能同时使用旧字段和 runtime_patch")
            updates[name] = arm.model_dump()[name]
    for name, patch in arm.runtime_patch.items():
        if isinstance(source[name], dict):
            if not isinstance(patch, dict):
                raise ValueError(f"条件 {arm.name}：{name} 必须是字段对象")  # noqa: TRY004 — protocol validation
            updates[name] = source[name] | patch
        else:
            updates[name] = patch
    if updates["intervention"] is not None:
        updates["intervention"] = arm.intervention.model_dump()
    return RunSpec.model_validate_json(json.dumps(source | updates, allow_nan=False), strict=True)


class StudySpec(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    base: RunSpec = Field(default_factory=lambda: RunSpec(clock="unbounded", duration_s=10))
    warmup_s: float = Field(default=2, ge=0, le=300)
    seeds: list[int] = Field(default_factory=lambda: [11, 23, 47, 89], min_length=2, max_length=64)
    arms: list[Arm] = Field(
        default_factory=lambda: [Arm(name="完整可塑性"), Arm(name="关闭可塑性", config_patch={"plasticity": False})],
        min_length=2,
        max_length=12,
    )
    replay_blocks: dict[str, list[dict]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_study(self):
        if self.base.duration_s is None:
            raise ValueError("配对实验需要有限的观察时长，以确定比较终点；普通意识可持续运行。")
        if self.base.environment_seed is not None:
            raise ValueError("配对实验的环境随机化由独立区组种子列表管理；基础协议的独立环境种子须为空。")
        if any(getattr(self.base, key) is not None for key in ("study_id", "condition", "block_seed")):
            raise ValueError("study base must not carry membership from another experiment")
        if self.base.environment not in ("mujoco", "replay", "ambient", "world", "robot"):
            raise ValueError("paired studies require a recorded or simulated environment")
        if any(c.enabled for c in (self.base.host_telemetry, self.base.process_telemetry, self.base.runtime_telemetry)):
            raise ValueError("配对实验不能混入各分支分别采集的物理遥测；请预先记录并重放同源刺激。")
        if len(set(self.seeds)) != len(self.seeds) or any(not 0 <= s < 2**32 for s in self.seeds):
            raise ValueError("use unique independent environmental seeds")
        if len({a.name for a in self.arms}) != len(self.arms):
            raise ValueError("condition names must be unique")
        if self.base.environment == "replay":
            from threemind_core import Stimulus

            if set(self.replay_blocks) != set(map(str, self.seeds)):
                raise ValueError(
                    "replay studies need one independently acquired replay_blocks entry per seed; repeating one deterministic recording is not independent replication"
                )
            for block in self.replay_blocks.values():
                if len(block) > 100000:
                    raise ValueError("replay block exceeds event budget")
                for event in block:
                    Stimulus.from_dict(event)
        descriptor = resolve_kernel(self.base.kernel_id)
        base_config = descriptor.configuration(self.base.config)
        for arm in self.arms:
            descriptor.configuration(self.base.config | arm.config_patch)
            if self.base.kernel_id == "threemind.lif/1":
                for key in ("rest_mv", "reset_mv", "threshold_mv"):
                    if key in arm.config_patch and arm.config_patch[key] != getattr(base_config, key):
                        raise ValueError(f"{key} 创建后不可修改，请创建独立实验。")
            if (
                "energy_initial_reserve" in arm.config_patch
                and arm.config_patch["energy_initial_reserve"] != base_config.energy_initial_reserve
            ):
                raise ValueError(
                    "paired continuation cannot assign a new initial reserve; use an explicit external supply"
                )
            if "step_us" in arm.config_patch and arm.config_patch["step_us"] != base_config.step_us:
                raise ValueError(
                    "paired continuation preserves the numerical lattice; use separate runs for step-size convergence"
                )
            if "seed" in arm.config_patch and arm.config_patch["seed"] != base_config.seed:
                raise ValueError(
                    "paired continuation preserves Core identity; use independent runs for different Core seeds"
                )
            resolved = resolve_arm(self.base, arm)
            if any(
                c.enabled for c in (resolved.host_telemetry, resolved.process_telemetry, resolved.runtime_telemetry)
            ):
                raise ValueError(f"条件 {arm.name}：配对实验不能分别采集物理遥测，请使用同源重放。")
            from .configuration import PROTOCOL_IMMUTABLE

            # Receptor identities are shared with the already developed brain.
            for path in sorted(p for p in PROTOCOL_IMMUTABLE if "." in p):
                root, key = path.split(".", 1)
                if getattr(getattr(resolved, root), key) != getattr(getattr(self.base, root), key):
                    raise ValueError(f"条件 {arm.name}：{path} 属于共同感官身份；比较不同身份请创建独立实验。")
            if arm.phases is not None and [(p.name, round(p.duration_s * 1e6)) for p in arm.phases] != [
                (p.name, round(p.duration_s * 1e6)) for p in self.base.phases
            ]:
                raise ValueError("paired phase names and durations must match; only source gating may differ")
        return self


def phase_at(spec: RunSpec, elapsed_us: int):
    """Half-open delivery intervals, relative to the post-warmup branch origin."""
    start = 0
    for index, phase in enumerate(spec.phases):
        end = start + round(phase.duration_s * 1e6)
        if elapsed_us < end:
            return index, phase, start, end
        start = end
    return None


def filter_stimulus(spec: RunSpec, stimulus, origin_us: int):
    from dataclasses import replace

    from threemind_core import Stimulus

    phase = phase_at(spec, stimulus.time_us - origin_us)
    if spec.phases and (phase is None or not phase[1].input_enabled):
        return None
    channels = stimulus.channels
    if spec.kernel_id == "unified-associative" and isinstance(channels, dict):
        if spec.max_channels is not None and len(channels) > spec.max_channels:
            channels = dict(sorted(channels.items(), key=lambda item: (-item[1], item[0]))[:spec.max_channels])
        return replace(stimulus, channels=channels)
    if spec.max_channels is not None and len(channels) > spec.max_channels:
        # An explicit receptor bandwidth control, outside the anonymous core.
        channels = tuple(sorted(sorted(channels, key=lambda c: (-c[1], c[0]))[: spec.max_channels]))
    return Stimulus(stimulus.time_us, channels, stimulus.intensity, bypass_attention=stimulus.bypass_attention)
