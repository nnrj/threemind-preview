from .continuous_native import NativeContinuousEngine
from .memory import KERNEL_ID, MemoryConfig


class NativeMemoryEngine(NativeContinuousEngine):
    dynamics = KERNEL_ID
    config_type = MemoryConfig
