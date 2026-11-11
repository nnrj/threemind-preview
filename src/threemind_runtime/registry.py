"""Inspectable adapter contracts, independent of hosts, databases and Core execution.

Host capability checks and binding policy belong to the application. This
catalogue never imports plugin paths or changes a model when describing it.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, replace

from .body import AmbientConfig, BodyFilterConfig, InteroceptionConfig
from .energy_supply import EnergySupplyConfig
from .live_media import LIVE_VERSION, LiveCaptureConfig
from .media import MEDIA_VERSION, OUTPUT_VERSION, AcousticConfig, AuditoryConfig, ProjectorConfig, VisualConfig
from .network import PROTOCOL
from .readout_config import READOUT_VERSION, ActivityReadoutConfig, StructuralReadoutConfig, TemporalReadoutConfig
from .sensory import TEXT_VERSION, InputBusConfig, TextSensorConfig
from .source_policies import POLICY_VERSION, SourcePolicies
from .telemetry import TELEMETRY_VERSION, HostTelemetryConfig, ProcessTelemetryConfig, RuntimeTelemetryConfig


@dataclass(frozen=True)
class AdapterDescriptor:
    id: str
    name: str
    direction: str
    bus: str
    version: str
    description: str
    root: str | None = None
    config_type: type | None = None
    group: str = "senses"
    tool: str = "history"
    document: str = "v2-inputs.md"
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    selector: tuple[str, str] | None = None
    gate: str | None = "enabled"
    dependencies: tuple[str, ...] = ()
    contract: dict | None = None

    def configuration(self, value=None):
        if value is not None and not isinstance(value, dict):
            raise ValueError("adapter configuration must be an object")
        if self.config_type is None:
            if value:
                raise ValueError(f"{self.id} has no independent adapter configuration")
            return {}
        try:
            return asdict(self.config_type(**deepcopy(value or {})))
        except TypeError as error:
            raise ValueError(f"invalid {self.id} configuration: {error}") from error

    def public(self, spec=None):
        from .adapter_contracts import installed_contract

        if spec is not None and not isinstance(spec, dict):
            raise ValueError("binding configuration must be an object")
        spec = spec or {}
        if self.id == "robot-task" and self.version == "robot-task/1" and (spec.get("robot_protocol") or {}).get("schema_id") == "threemind.robot-task/2":
            from .robot_protocol import parse_robot

            cfg = parse_robot(spec["robot_protocol"]).playground
            return replace(self, version="robot-task/2", capabilities=(f"worker.playground_{cfg.implementation}_{cfg.device}",)).public(spec)
        config = self.configuration(spec.get(self.root, {})) if self.root else {}
        if self.selector:
            selected = spec.get(self.selector[0], "mujoco" if self.selector[0] == "environment" else None)
            enabled = selected == self.selector[1]
        else:
            enabled = bool(config.get(self.gate, False)) if self.gate else True
        return {
            "id": self.id,
            "name": self.name,
            "direction": self.direction,
            "bus": self.bus,
            "version": self.version,
            "description": self.description,
            "configuration_root": self.root,
            "configuration": config,
            "group": self.group,
            "tool": self.tool,
            "document": self.document,
            "ports": {"inputs": list(self.inputs), "outputs": list(self.outputs)},
            "capabilities": list(self.capabilities),
            "dependencies": list(self.dependencies),
            "configured_enabled": enabled,
            "contract": installed_contract(self).model_dump(mode="json"),
        }


class AdapterRegistry:
    def __init__(self, descriptors):
        self.descriptors = {}
        for descriptor in descriptors:
            if descriptor.id in self.descriptors:
                raise ValueError(f"duplicate adapter id: {descriptor.id}")
            if descriptor.direction not in ("input", "output", "duplex", "filter"):
                raise ValueError("invalid adapter direction")
            self.descriptors[descriptor.id] = descriptor

    def describe(self, adapter_id, spec=None):
        try:
            descriptor = self.descriptors[adapter_id]
        except KeyError as error:
            raise ValueError(f"unknown adapter: {adapter_id}") from error
        return descriptor.public(spec)

    def list(self, spec=None):
        return [d.public(spec) for d in self.descriptors.values()]


def default_adapter_registry():
    from .external_contracts import language_contract, probability_contract

    D = AdapterDescriptor
    return AdapterRegistry(
        [
            D(
                "language-transformer",
                "Transformer 语言感官与读出",
                "duplex",
                "InputBus/OutputBus",
                "threemind.language-adapter/1",
                "可选随机权重或固定预训练模型，独立输入/输出，版本冻结，不修改 Core 动力学。",
                tool="language",
                document="language-adapters.md",
                inputs=("language.text", "core.activity"),
                outputs=("core.stimulus", "language.interpretation"),
                contract=language_contract().model_dump(),
            ),
            AdapterDescriptor(
                "stimulus-units",
                "刺激体输入",
                "input",
                "InputBus",
                "threemind.stimulus-unit/1",
                "明确的共同观测转换为匿名刺激；来源和物理量只作证据，不读取内核拓扑。",
                gate=None,
                inputs=("numeric.frames",),
                outputs=("core.stimulus",),
            ),
            D(
                "transformer-probability",
                "外部 Transformer 概率",
                "input",
                "InputBus",
                "threemind.probabilities/1",
                "显式接入经过审计的概率向量；不自动反馈，不读取或改写内部拓扑。",
                gate=None,
                inputs=("token.ids",),
                outputs=("probability.vector",),
                document="v2-kernels.md",
                contract=probability_contract().model_dump(),
            ),
            D(
                "input-bus",
                "输入总线",
                "input",
                "InputBus",
                "input-bus/1",
                "按时间戳排队、背压与逐帧来源关联。",
                "input_bus",
                InputBusConfig,
                "transport",
                gate=None,
                inputs=("carrier.envelope",),
                outputs=("core.stimulus",),
            ),
            D(
                "anonymous-frames",
                "匿名帧接入",
                "input",
                "InputBus",
                "anonymous-frames/1",
                "数值帧直接接入，不读取语义。",
                gate=None,
                inputs=("numeric.frames",),
                outputs=("core.stimulus",),
            ),
            D(
                "source-policy",
                "输入来源与竞争策略",
                "filter",
                "InputBus",
                POLICY_VERSION,
                "类别与来源控制新载体准入，逐帧冻结通道竞争绕过；不改显示与在途承诺。",
                "source_policies",
                SourcePolicies,
                "transport",
                tool="sources",
                document="v2-source-policies.md",
                gate=None,
                inputs=("carrier.source", "source.policy"),
                outputs=("admission.decision", "core.stimulus"),
                dependencies=("input-bus",),
            ),
            D(
                "text-sensor",
                "文本感官",
                "input",
                "InputBus",
                TEXT_VERSION,
                "载体有序分帧；观察标签留在内核外。",
                "text_sensor",
                TextSensorConfig,
                "text",
                inputs=("text.carrier",),
                outputs=("core.stimulus", "observation.labels"),
            ),
            D(
                "mujoco-environment",
                "模拟物理环境",
                "duplex",
                "InputBus / OutputBus",
                "planar-v1",
                "平面躯体、物理力与显式运动反馈。",
                tool="body",
                document="v2-body-tools.md",
                selector=("environment", "mujoco"),
                inputs=("activation.frame",),
                outputs=("physical.measurement",),
                capabilities=("worker.mujoco",),
            ),
            D(
                "physical-world",
                "可配置世界与躯体",
                "duplex",
                "InputBus / OutputBus",
                "world-port-v1",
                "独立物理协议、匿名感官端口与执行器；观察界面不参与物理步进。",
                tool="body",
                document="v2-worlds.md",
                selector=("environment", "world"),
                inputs=("activation.frame",),
                outputs=("physical.measurement",),
                capabilities=("worker.world_v1",),
            ),
            D(
                "ambient-field",
                "合成环境场",
                "input",
                "InputBus",
                "ambient-fixture/1",
                "显式合成实验载体，不能当作物理测量。",
                "ambient_field",
                AmbientConfig,
                "ambient_field",
                "body",
                "v2-body-tools.md",
                selector=("environment", "ambient"),
                outputs=("synthetic.measurement",),
            ),
            D(
                "robot-task",
                "机器人任务",
                "duplex",
                "InputBus / OutputBus",
                "robot-task/1",
                "显式物理躯体、匿名感官、控制模式及任务观察；任务评分不回写内核。",
                tool="body",
                document="plans/robotics-and-language.md",
                selector=("environment", "robot"),
                inputs=("activation.frame",),
                outputs=("physical.measurement",),
                capabilities=("worker.robot_v1",),
            ),
            D(
                "body-filter",
                "环境躯体过滤",
                "filter",
                "InputBus",
                "body-filter/1",
                "采样、阈值、适应与显式测量噪声。",
                "body_filter",
                BodyFilterConfig,
                "body_filter",
                "body",
                "v2-body-tools.md",
                inputs=("physical.measurement", "synthetic.measurement"),
                outputs=("core.stimulus",),
                dependencies=("environment:mujoco|ambient|world|robot",),
            ),
            D(
                "simulated-interoception",
                "模拟内感受",
                "input",
                "InputBus",
                "simulated-interoception/1",
                "可选的周期载体，独立于外部环境选择。",
                "interoception",
                InteroceptionConfig,
                "interoception",
                "body",
                "v2-body-tools.md",
                outputs=("core.stimulus",),
            ),
            D(
                "replay",
                "记录输入重放",
                "input",
                "InputBus",
                "replay/1",
                "保留来源与时间间隔的显式重放。",
                selector=("environment", "replay"),
                inputs=("recorded.frames",),
                outputs=("core.stimulus",),
            ),
            *[
                D(
                    f"{scope}-telemetry",
                    label,
                    "input",
                    "InputBus",
                    TELEMETRY_VERSION,
                    "真实计数与可用性分开记录，缺失值不补零。",
                    root,
                    cls,
                    root,
                    "telemetry",
                    "v2-telemetry.md",
                    inputs=("physical.counter",),
                    outputs=("core.stimulus",),
                    capabilities=(f"worker.telemetry_{scope}",),
                    dependencies=("clock:realtime",),
                )
                for scope, label, root, cls in (
                    ("host", "宿主物理遥测", "host_telemetry", HostTelemetryConfig),
                    ("process", "工作进程遥测", "process_telemetry", ProcessTelemetryConfig),
                    ("runtime", "意识执行反馈", "runtime_telemetry", RuntimeTelemetryConfig),
                )
            ],
            D(
                "auditory-sensor",
                "听觉感官",
                "input",
                "InputBus",
                MEDIA_VERSION,
                "PCM 频带或波形编码；文件解码能力由接口服务提供。",
                "auditory_sensor",
                AuditoryConfig,
                "auditory_sensor",
                "media",
                "v2-media.md",
                inputs=("audio.pcm",),
                outputs=("core.stimulus",),
                capabilities=("api.media_audio",),
            ),
            D(
                "visual-sensor",
                "视觉感官",
                "input",
                "InputBus",
                MEDIA_VERSION,
                "像素转换为局部视网膜块；文件与摄像头各有接入能力。",
                "visual_sensor",
                VisualConfig,
                "visual_sensor",
                "media",
                "v2-media.md",
                inputs=("image.pixels", "video.pixels"),
                outputs=("core.stimulus",),
                capabilities=("api.media_image", "api.media_video"),
            ),
            D(
                "microphone",
                "连续麦克风",
                "input",
                "InputBus",
                LIVE_VERSION,
                "必须由浏览器明确开始，并获得设备权限。",
                "live_capture",
                LiveCaptureConfig,
                "live_capture",
                "capture",
                "v2-live-capture.md",
                gate="microphone_enabled",
                inputs=("audio.pcm",),
                outputs=("core.stimulus",),
                capabilities=("browser.microphone",),
                dependencies=("auditory_sensor.enabled", "clock:realtime"),
            ),
            D(
                "camera",
                "连续摄像头",
                "input",
                "InputBus",
                LIVE_VERSION,
                "原始图像与采集时钟保留；不会自动打开摄像头。",
                "live_capture",
                LiveCaptureConfig,
                "live_capture",
                "capture",
                "v2-live-capture.md",
                gate="camera_enabled",
                inputs=("image.pixels",),
                outputs=("core.stimulus",),
                capabilities=("browser.camera",),
                dependencies=("visual_sensor.enabled", "clock:realtime"),
            ),
            D(
                "acoustic-output-organ",
                "发声器",
                "output",
                "OutputBus",
                OUTPUT_VERSION,
                "匿名活动到振荡器控制值，不做语音合成。",
                "acoustic_output",
                AcousticConfig,
                "acoustic_output",
                "outputs",
                "v2-continuous-output.md",
                inputs=("activation.frame",),
                outputs=("audio.control",),
                capabilities=("browser.audio_output",),
            ),
            D(
                "activation-image-projector",
                "激活图像投影器",
                "output",
                "OutputBus",
                OUTPUT_VERSION,
                "只读的灰度活动投影，区别于三维网络观察。",
                "activation_projector",
                ProjectorConfig,
                "activation_projector",
                "outputs",
                "v2-continuous-output.md",
                inputs=("activation.frame",),
                outputs=("image.pixels",),
            ),
            *[
                D(
                    id,
                    name,
                    "output",
                    "OutputBus",
                    READOUT_VERSION,
                    description,
                    root,
                    cls,
                    root,
                    "readouts",
                    "v2-readouts.md",
                    inputs=("activation.frame", "input.envelope"),
                    outputs=("readout.evidence",),
                )
                for id, name, description, root, cls in (
                    (
                        "structural-readout",
                        "截面结构读出",
                        "完整节点观察上的显式候选子图与复现。",
                        "structural_readout",
                        StructuralReadoutConfig,
                    ),
                    (
                        "temporal-readout",
                        "时序响应读出",
                        "模拟时间窗口、原始轨迹、基线与删失状态。",
                        "temporal_readout",
                        TemporalReadoutConfig,
                    ),
                    (
                        "activity-readout",
                        "活动过程分析",
                        "只读地分析响应模式、幅度、周期及结束，保留独立版本和原始轨迹。",
                        "activity_readout",
                        ActivityReadoutConfig,
                    ),
                )
            ],
            D(
                "energy-supply",
                "模拟外部能量储库",
                "input",
                "ResourcePort",
                "energy-supplier/1",
                "有限速率外部资源，不参与刺激排序。",
                "energy_supply",
                EnergySupplyConfig,
                "energy_supply",
                "energy",
                "v2-energy.md",
                outputs=("energy.supply",),
                dependencies=("config.energy_simulation_enabled",),
            ),
            D(
                "input-modulation",
                "显式输入调制端口",
                "input",
                "ControlPort",
                "input-modulation/1",
                "有期限的标量控制，不开放节点或连接修改。",
                group="attention",
                tool="attention",
                document="v2-attention.md",
                gate=None,
                inputs=("scalar.modulation",),
                outputs=("core.modulation",),
            ),
            D(
                "remote-anonymous",
                "网络设备",
                "duplex",
                "InputBus / OutputBus / ResourcePort",
                PROTOCOL,
                "每台设备独立凭据与能力授权；绑定配置保存在宿主。",
                tool="devices",
                document="v2-network-devices.md",
                inputs=("remote.numeric", "remote.scalar"),
                outputs=("anonymous.output", "receipt.evidence"),
                capabilities=("api.network",),
                dependencies=("device.binding",),
            ),
        ]
    )
