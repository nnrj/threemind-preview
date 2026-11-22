from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

from threemind_core import Config, StateImage

BASELINE_KERNEL = "threemind.causal/9"
DEFAULT_KERNEL = "threemind.continuous-memory/6.1"


@lru_cache(maxsize=1)
def _baseline():
    return json.loads(files("threemind_kernels").joinpath("baselines/causal9.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class KernelDescriptor:
    kernel_id: str
    state_schema: str
    family: str
    title: str
    hypothesis_id: str
    mechanisms: tuple[tuple[str, str], ...]
    backends: tuple[str, ...]
    observation_quantity: str
    status: str = "preserved"
    capabilities: tuple[str, ...] = ("causal_energy", "causal_attention", "causal_space")

    @property
    def display_name(self) -> str:
        return self.kernel_id.removeprefix("threemind.")

    @property
    def version(self) -> str:
        return self.kernel_id.rsplit("/", 1)[-1] if "/" in self.kernel_id else "historical"

    @property
    def description(self) -> str:
        return self.title

    def config_fields(self) -> dict:
        """Version-owned accepted fields and defaults; never instantiate dynamics."""
        return asdict(self.configuration())

    def to_dict(self) -> dict:
        return {
            "kernel_id": self.kernel_id,
            "state_schema": self.state_schema,
            "family": self.family,
            "title": self.title,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "hypothesis_id": self.hypothesis_id,
            "mechanisms": [{"id": name, "phase": phase} for name, phase in self.mechanisms],
            "backends": list(self.backends),
            "observation_quantity": self.observation_quantity,
            "status": self.status,
            "default": self.kernel_id == DEFAULT_KERNEL,
            "capabilities": list(self.capabilities),
            **({"baseline": copy.deepcopy(_baseline())} if self.kernel_id == BASELINE_KERNEL else {}),
        }

    def configuration(self, value: Any = None):
        if self.kernel_id in tuple(f"threemind.causal/{n}" for n in range(1, 9)):
            from .legacy.causal import configuration

            return configuration(self.kernel_id, value)
        if self.kernel_id == "unified-associative":
            from .legacy.unified_adapter import UnifiedConfig

            if value is None or type(value) is UnifiedConfig:
                return value or UnifiedConfig()
            if not isinstance(value, dict):
                raise ValueError("unified configuration must be an object")
            try:
                return UnifiedConfig(**value)
            except TypeError as exc:
                raise ValueError(str(exc)) from exc
        from .continuous import ContinuousConfig
        from .lif import LifConfig
        from .local import LocalConfig
        from .local5 import Local5Config
        from .local51 import Local51Config
        from .local52 import Local52Config
        from .local53 import Local53Config
        from .local60 import Local60Config
        from .local61 import Local61Config
        from .local62 import Local62Config
        from .local63 import Local63Config
        from .weight_decay import CandidateConfig
        from .memory import MemoryConfig
        from .novelty import NoveltyConfig
        from .retention import RetentionConfig
        from .retention31 import Retention31Config

        config_type = {
            BASELINE_KERNEL: Config,
            "threemind.continuous/1": ContinuousConfig,
            "threemind.continuous-memory/1": MemoryConfig,
            "threemind.continuous-memory/2": NoveltyConfig,
            "threemind.continuous-memory/3": RetentionConfig,
            "threemind.continuous-memory/3.1": Retention31Config,
            "threemind.continuous-memory/4": LocalConfig,
            "threemind.continuous-memory/5": Local5Config,
            "threemind.continuous-memory/5.1": Local51Config,
            "threemind.continuous-memory/5.2": Local52Config,
            "threemind.continuous-memory/5.3": Local53Config,
            "threemind.continuous-memory/6.0": Local60Config,
            "threemind.continuous-memory/6.1": Local61Config,
            "threemind.continuous-memory/6.2": Local62Config,
            "threemind.continuous-memory/6.3": Local63Config,
            "threemind.experimental-weight-decay/1": CandidateConfig,
            "threemind.lif/1": LifConfig,
        }[self.kernel_id]
        if value is None or type(value) is config_type:
            return value or config_type()
        if not isinstance(value, dict):
            raise ValueError("kernel configuration must be an object")  # noqa: TRY004 -- public protocol validation
        try:
            return config_type(**value)
        except TypeError as exc:
            raise ValueError(str(exc)) from exc

    def create(self, config=None, state: StateImage | None = None, *, backend="native"):
        if backend not in self.backends:
            raise ValueError(f"{self.kernel_id} does not support backend {backend!r}; no automatic fallback")
        if state is not None:
            document = state.to_dict()
            if document.get("dynamics") != self.kernel_id or document.get("schema") != self.state_schema:
                raise ValueError("kernel identity or state schema mismatch; conversion is not restoration")
            if config is not None:
                raise ValueError("restoration uses the saved configuration; reconfigure explicitly afterward")
        config = self.configuration(config) if state is None else None
        if self.kernel_id in tuple(f"threemind.causal/{n}" for n in range(1, 9)):
            from .legacy.causal import create

            return create(self.kernel_id, config, state, backend=backend)
        if self.kernel_id == "unified-associative":
            from .legacy.unified_adapter import UnifiedEngine

            return UnifiedEngine(config, state)
        if self.kernel_id == BASELINE_KERNEL:
            if backend == "reference":
                from threemind_core import Engine

                return Engine(config, state)
            from threemind_runtime.host import NativeEngine

            return NativeEngine(config, state)
        if self.kernel_id == "threemind.continuous/1":
            if backend == "reference":
                from .continuous import ContinuousEngine

                return ContinuousEngine(config, state)
            from .continuous_native import NativeContinuousEngine

            return NativeContinuousEngine(config, state)
        if self.kernel_id == "threemind.lif/1":
            if backend == "reference":
                from .lif import LifEngine

                return LifEngine(config, state)
            from .lif_native import NativeLifEngine

            return NativeLifEngine(config, state)
        if self.kernel_id == "threemind.continuous-memory/1":
            if backend == "reference":
                from .memory import MemoryEngine

                return MemoryEngine(config, state)
            from .memory_native import NativeMemoryEngine

            return NativeMemoryEngine(config, state)
        if self.kernel_id == "threemind.continuous-memory/2":
            if backend == "reference":
                from .novelty import NoveltyEngine

                return NoveltyEngine(config, state)
            from .novelty_native import NativeNoveltyEngine

            return NativeNoveltyEngine(config, state)
        if self.kernel_id == "threemind.continuous-memory/3":
            if backend == "reference":
                from .retention import RetentionEngine

                return RetentionEngine(config, state)
            from .retention_native import NativeRetentionEngine

            return NativeRetentionEngine(config, state)
        if self.kernel_id == "threemind.continuous-memory/4":
            if backend == "reference":
                from .local import LocalEngine

                return LocalEngine(config, state)
            from .local_native import NativeLocalEngine

            return NativeLocalEngine(config, state)
        if self.kernel_id == "threemind.continuous-memory/5":
            if backend == "reference":
                from .local5 import Local5Engine

                return Local5Engine(config, state)
            from .local5_native import NativeLocal5Engine

            return NativeLocal5Engine(config, state)
        if self.kernel_id == "threemind.experimental-weight-decay/1":
            if backend == "reference":
                from .weight_decay import CandidateEngine
                return CandidateEngine(config, state)
            from .weight_decay_native import NativeWeightDecayEngine
            return NativeWeightDecayEngine(config, state)
        if self.kernel_id == "threemind.continuous-memory/5.3":
            if backend == "reference":
                from .local53 import Local53Engine
                return Local53Engine(config, state)
            from .local53_native import NativeLocal53Engine
            return NativeLocal53Engine(config, state)
        if self.kernel_id == "threemind.continuous-memory/6.0":
            if backend == "reference":
                from .local60 import Local60Engine
                return Local60Engine(config, state)
            from .local60_native import NativeLocal60Engine
            return NativeLocal60Engine(config, state)
        if self.kernel_id == "threemind.continuous-memory/6.1":
            if backend == "reference":
                from .local61 import Local61Engine
                return Local61Engine(config, state)
            from .local61_native import NativeLocal61Engine
            return NativeLocal61Engine(config, state)
        if self.kernel_id == "threemind.continuous-memory/6.2":
            if backend == "reference":
                from .local62 import Local62Engine
                return Local62Engine(config, state)
            from .local62_native import NativeLocal62Engine
            return NativeLocal62Engine(config, state)
        if self.kernel_id == "threemind.continuous-memory/6.3":
            if backend == "reference":
                from .local63 import Local63Engine
                return Local63Engine(config, state)
            from .local63_native import NativeLocal63Engine
            return NativeLocal63Engine(config, state)
        if self.kernel_id == "threemind.continuous-memory/5.2":
            if backend == "reference":
                from .local52 import Local52Engine
                return Local52Engine(config, state)
            from .local52_native import NativeLocal52Engine
            return NativeLocal52Engine(config, state)
        if self.kernel_id == "threemind.continuous-memory/5.1":
            if backend == "reference":
                from .local51 import Local51Engine

                return Local51Engine(config, state)
            from .local51_native import NativeLocal51Engine

            return NativeLocal51Engine(config, state)
        if self.kernel_id == "threemind.continuous-memory/3.1":
            if backend == "reference":
                from .retention31 import Retention31Engine

                return Retention31Engine(config, state)
            from .retention31_native import NativeRetention31Engine

            return NativeRetention31Engine(config, state)
        raise ValueError(f"implementation unavailable for {self.kernel_id}")


_KERNELS = {
    BASELINE_KERNEL: KernelDescriptor(
        BASELINE_KERNEL,
        "threemind.state/6",
        "continuous",
        "V3 恢复基线 · causal/9",
        "threemind.hypotheses/causal9",
        (("threemind.causal9-transition/1", "hybrid-event-clock"),),
        ("reference", "native"),
        "activation",
    ),
    "threemind.continuous/1": KernelDescriptor(
        "threemind.continuous/1",
        "threemind.continuous-state/1",
        "continuous",
        "连续候选 · 短时突触与局部上下文",
        "threemind.hypotheses/continuous1",
        (
            ("threemind.causal9-transition/1", "hybrid-event-clock"),
            ("threemind.leaky-fast-trace/1", "efficacy-and-emission"),
            ("threemind.tm-synapse/1", "before-emission"),
            ("threemind.local-context-attention/1", "after-arrival"),
        ),
        ("reference", "native"),
        "activation",
        "experimental",
    ),
}

from .lif import KERNEL_ID as LIF_ID
from .memory import KERNEL_ID as MEMORY_ID
from .memory import MECHANISMS as MEMORY_MECHANISMS
from .memory import STATE_SCHEMA as MEMORY_STATE

_KERNELS[MEMORY_ID] = KernelDescriptor(
    MEMORY_ID,
    MEMORY_STATE,
    "continuous",
    "记忆机制研究 · 耗竭、易化与巩固",
    "threemind.hypotheses/continuous-memory1",
    MEMORY_MECHANISMS,
    ("reference", "native"),
    "activation",
    "experimental",
)
from .lif import MECHANISMS as LIF_MECHANISMS
from .lif import STATE_SCHEMA as LIF_STATE

_KERNELS[LIF_ID] = KernelDescriptor(
    LIF_ID,
    LIF_STATE,
    "spiking",
    "脉冲候选 · 膜电位与局部时序学习",
    "threemind.hypotheses/lif1",
    LIF_MECHANISMS,
    ("reference", "native"),
    "normalized-depolarization",
    "experimental",
    ("physical_membrane", "spike_events"),
)


from .novelty import KERNEL_ID as NOVELTY_ID
from .novelty import MECHANISMS as NOVELTY_MECHANISMS
from .novelty import STATE_SCHEMA as NOVELTY_STATE

_KERNELS[NOVELTY_ID] = KernelDescriptor(
    NOVELTY_ID,
    NOVELTY_STATE,
    "continuous",
    "记忆机制校准 · 局部新颖性时序",
    "threemind.hypotheses/continuous-memory2",
    NOVELTY_MECHANISMS,
    ("reference", "native"),
    "activation",
    "experimental",
)


from .retention import KERNEL_ID as RETENTION_ID
from .retention import MECHANISMS as RETENTION_MECHANISMS
from .retention import STATE_SCHEMA as RETENTION_STATE

_KERNELS[RETENTION_ID] = KernelDescriptor(
    RETENTION_ID,
    RETENTION_STATE,
    "continuous",
    "使用依赖保持 · 可选休眠与唤醒",
    "threemind.hypotheses/continuous-memory3",
    RETENTION_MECHANISMS,
    ("reference", "native"),
    "activation",
    "experimental",
)

from .retention31 import HYPOTHESIS_ID as RETENTION31_HYPOTHESIS
from .retention31 import KERNEL_ID as RETENTION31_ID
from .retention31 import MECHANISMS as RETENTION31_MECHANISMS
from .retention31 import STATE_SCHEMA as RETENTION31_STATE

_KERNELS[RETENTION31_ID] = KernelDescriptor(
    RETENTION31_ID,
    RETENTION31_STATE,
    "continuous",
    "使用依赖保持 · 修复零响应节点的局部回收排期",
    RETENTION31_HYPOTHESIS,
    RETENTION31_MECHANISMS,
    ("reference", "native"),
    "activation",
    "experimental",
)


from .local import KERNEL_ID as LOCAL_ID
from .local import MECHANISMS as LOCAL_MECHANISMS
from .local import STATE_SCHEMA as LOCAL_STATE

_KERNELS[LOCAL_ID] = KernelDescriptor(
    LOCAL_ID,
    LOCAL_STATE,
    "continuous",
    "局部事件内核 · 统一接收与局部能量",
    "threemind.hypotheses/continuous-memory4",
    LOCAL_MECHANISMS,
    ("reference", "native"),
    "activation",
    "experimental",
    ("causal_energy", "causal_space", "local_events"),
)


from .local5 import KERNEL_ID as LOCAL5_ID
from .local5 import MECHANISMS as LOCAL5_MECHANISMS
from .local5 import STATE_SCHEMA as LOCAL5_STATE

_KERNELS[LOCAL5_ID] = KernelDescriptor(
    LOCAL5_ID,
    LOCAL5_STATE,
    "continuous",
    "局部事件修订 · 默认采用 /2 接收与学习规则",
    "threemind.hypotheses/continuous-memory5",
    LOCAL5_MECHANISMS,
    ("reference", "native"),
    "activation",
    "experimental",
    ("causal_energy", "causal_space", "local_events"),
)


from .local51 import HYPOTHESIS_ID as LOCAL51_HYPOTHESIS
from .local51 import KERNEL_ID as LOCAL51_ID
from .local51 import MECHANISMS as LOCAL51_MECHANISMS
from .local51 import STATE_SCHEMA as LOCAL51_STATE

_KERNELS[LOCAL51_ID] = KernelDescriptor(
    LOCAL51_ID,
    LOCAL51_STATE,
    "continuous",
    "局部执行性能修订 · 保持 /5 动力学与配置默认值",
    LOCAL51_HYPOTHESIS,
    LOCAL51_MECHANISMS,
    ("reference", "native"),
    "activation",
    "experimental",
    ("causal_energy", "causal_space", "local_events"),
)


from .local52 import HYPOTHESIS_ID as LOCAL52_HYPOTHESIS
from .local52 import KERNEL_ID as LOCAL52_ID
from .local52 import MECHANISMS as LOCAL52_MECHANISMS
from .local52 import STATE_SCHEMA as LOCAL52_STATE

_KERNELS[LOCAL52_ID] = KernelDescriptor(
    LOCAL52_ID, LOCAL52_STATE, "continuous",
    "衰减机制研究 · 指数、对数、幂律与时间尺度回落开关",
    LOCAL52_HYPOTHESIS, LOCAL52_MECHANISMS, ("reference", "native"), "activation",
    "experimental", ("causal_energy", "causal_space", "local_events", "selectable_decay"),
)


from .local53 import HYPOTHESIS_ID as LOCAL53_HYPOTHESIS
from .local53 import KERNEL_ID as LOCAL53_ID
from .local53 import MECHANISMS as LOCAL53_MECHANISMS
from .local53 import STATE_SCHEMA as LOCAL53_STATE

_KERNELS[LOCAL53_ID] = KernelDescriptor(
    LOCAL53_ID, LOCAL53_STATE, "continuous", "单年龄衰减与定向统一传导 · /5.3",
    LOCAL53_HYPOTHESIS, LOCAL53_MECHANISMS, ("reference", "native"), "activation",
    "experimental", ("causal_energy", "causal_space", "local_events", "selectable_decay"),
)
from .local60 import HYPOTHESIS_ID as LOCAL60_HYPOTHESIS
from .local60 import KERNEL_ID as LOCAL60_ID
from .local60 import MECHANISMS as LOCAL60_MECHANISMS
from .local60 import STATE_SCHEMA as LOCAL60_STATE

_KERNELS[LOCAL60_ID] = KernelDescriptor(
    LOCAL60_ID, LOCAL60_STATE, "continuous", "固定函数寻址 · /6.0",
    LOCAL60_HYPOTHESIS, LOCAL60_MECHANISMS, ("reference", "native"), "activation",
    "experimental", ("causal_energy", "causal_space", "local_events", "selectable_decay", "fixed_function_addressing"),
)

from .local61 import HYPOTHESIS_ID as LOCAL61_HYPOTHESIS
from .local61 import KERNEL_ID as LOCAL61_ID
from .local61 import MECHANISMS as LOCAL61_MECHANISMS
from .local61 import STATE_SCHEMA as LOCAL61_STATE

_KERNELS[LOCAL61_ID] = KernelDescriptor(
    LOCAL61_ID, LOCAL61_STATE, "continuous", "局部删除与独立发送门槛 · /6.1",
    LOCAL61_HYPOTHESIS, LOCAL61_MECHANISMS, ("reference", "native"), "activation",
    "experimental", ("causal_energy", "causal_space", "local_events", "selectable_decay", "fixed_function_addressing"),
)

from .local62 import HYPOTHESIS_ID as LOCAL62_HYPOTHESIS
from .local62 import KERNEL_ID as LOCAL62_ID
from .local62 import MECHANISMS as LOCAL62_MECHANISMS
from .local62 import STATE_SCHEMA as LOCAL62_STATE

_KERNELS[LOCAL62_ID] = KernelDescriptor(
    LOCAL62_ID, LOCAL62_STATE, "continuous", "稳定度保持与分类型连接门槛 · /6.2",
    LOCAL62_HYPOTHESIS, LOCAL62_MECHANISMS, ("reference", "native"), "activation",
    "experimental", ("causal_energy", "causal_space", "local_events", "selectable_decay", "fixed_function_addressing"),
)

from .local63 import HYPOTHESIS_ID as LOCAL63_HYPOTHESIS
from .local63 import KERNEL_ID as LOCAL63_ID
from .local63 import MECHANISMS as LOCAL63_MECHANISMS
from .local63 import STATE_SCHEMA as LOCAL63_STATE

_KERNELS[LOCAL63_ID] = KernelDescriptor(
    LOCAL63_ID, LOCAL63_STATE, "continuous", "共享连接状态与抑制分配 · /6.3",
    LOCAL63_HYPOTHESIS, LOCAL63_MECHANISMS, ("reference", "native"), "activation",
    "experimental", ("causal_energy", "causal_space", "local_events", "selectable_decay", "fixed_function_addressing"),
)

_LEGACY_DESCRIPTIONS = {
    1: "历史因果基线",
    2: "历史因果内核 · 可选局部机制",
    3: "历史因果内核 · 容量与预算对照",
    4: "历史因果内核 · 能量供给与消耗",
    5: "历史因果内核 · 输入注意调制",
    6: "历史因果内核 · 因果空间",
    7: "历史因果内核 · 逐帧输入策略",
    8: "历史 V3 恢复内核 · 原能量生命周期",
}
for _version, _description in _LEGACY_DESCRIPTIONS.items():
    _identity = f"threemind.causal/{_version}"
    _schema = "threemind.state/" + (
        "2" if _version <= 2 else "3" if _version == 3 else "4" if _version == 4 else "5" if _version <= 7 else "6"
    )
    _KERNELS[_identity] = KernelDescriptor(
        _identity,
        _schema,
        "continuous",
        _description,
        f"threemind.hypotheses/causal{_version}",
        ((f"threemind.causal{_version}-transition/1", "historical-event-clock"),),
        ("reference", "native"),
        "activation",
        "preserved",
        tuple(
            name
            for minimum, name in ((4, "causal_energy"), (5, "causal_attention"), (6, "causal_space"))
            if _version >= minimum
        ),
    )
_KERNELS["unified-associative"] = KernelDescriptor(
    "unified-associative",
    "threemind.unified-state/1",
    "historical",
    "原始统一关联运行时 · 输入 epoch 与历史 tick",
    "threemind.hypotheses/unified-associative",
    (("threemind.unified-transition/1", "historical-input-epoch"),),
    ("reference",),
    "activation",
    "preserved",
    ("legacy_epoch_clock",),
)


from .weight_decay import KERNEL_ID as WEIGHT_DECAY_ID, STATE_SCHEMA as WEIGHT_DECAY_STATE
from .weight_decay import CandidateConfig, definition as weight_decay_definition
_weight_definition = weight_decay_definition(CandidateConfig())
_KERNELS[WEIGHT_DECAY_ID] = KernelDescriptor(
    WEIGHT_DECAY_ID, WEIGHT_DECAY_STATE, "continuous", "权重依赖衰减 · R48 独立研究内核",
    _weight_definition["hypothesis_id"],
    tuple((r["id"], r["phase"]) for r in _weight_definition["operators"]),
    ("reference", "native"), "activation", "experimental",
    ("causal_energy", "causal_space", "local_events", "selectable_decay"),
)


def resolve_kernel(kernel_id: str | None = None) -> KernelDescriptor:
    identifier = DEFAULT_KERNEL if kernel_id is None else kernel_id
    if not isinstance(identifier, str) or identifier not in _KERNELS:
        raise ValueError(f"unsupported kernel {identifier!r}; no automatic conversion or fallback")
    return _KERNELS[identifier]


def creation_kernel(kernel_id: str | None = None, config=None) -> KernelDescriptor:
    """Explicit typed configurations retain their identity when creation defaults change."""
    if kernel_id is None and config is not None and not isinstance(config, dict):
        for descriptor in _KERNELS.values():
            if type(config) is type(descriptor.configuration()):
                return descriptor
    return resolve_kernel(kernel_id)


def describe_kernel(kernel_id: str | None = None) -> dict:
    return copy.deepcopy(resolve_kernel(kernel_id).to_dict())


def kernel_catalog() -> list[dict]:
    """Only implemented kernels. Pending proposals must not appear executable."""
    return [describe_kernel(identifier) for identifier in _KERNELS]


def state_kernel(image: StateImage) -> KernelDescriptor:
    value = image.to_dict()
    if not isinstance(value, dict) or not isinstance(value.get("dynamics"), str):
        raise ValueError("state must declare its kernel identity")  # noqa: TRY004 -- public protocol validation
    descriptor = resolve_kernel(value["dynamics"])
    if value.get("schema") != descriptor.state_schema:
        raise ValueError("kernel identity and state schema do not match")
    return descriptor
