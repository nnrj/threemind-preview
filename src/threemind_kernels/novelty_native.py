from .continuous_native import NativeContinuousEngine
from .novelty import KERNEL_ID, NoveltyConfig


class NativeNoveltyEngine(NativeContinuousEngine):
    dynamics = KERNEL_ID
    config_type = NoveltyConfig
