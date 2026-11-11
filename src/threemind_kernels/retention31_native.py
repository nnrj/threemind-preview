"""Production /3.1 shares the continuous Rust implementation, not Python dynamics."""

from .continuous_native import NativeContinuousEngine
from .retention31 import KERNEL_ID, Retention31Config


class NativeRetention31Engine(NativeContinuousEngine):
    dynamics = KERNEL_ID
    config_type = Retention31Config
