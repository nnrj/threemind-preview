from .continuous_native import NativeContinuousEngine
from .retention import KERNEL_ID, RetentionConfig


class NativeRetentionEngine(NativeContinuousEngine):
    dynamics = KERNEL_ID
    config_type = RetentionConfig
