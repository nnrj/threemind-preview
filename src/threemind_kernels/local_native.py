"""Independent production memory/4 backend; no reference execution at runtime."""

import json

from threemind_runtime.host import NativeEngine

from .local import KERNEL_ID, LocalConfig


class NativeLocalEngine(NativeEngine):
    config_type = LocalConfig
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not LocalConfig:
            raise ValueError("memory/4 requires LocalConfig")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal

        self._engine = NativeLocal(
            json.dumps((config or LocalConfig()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return LocalConfig(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not LocalConfig:
            raise ValueError("memory/4 requires LocalConfig")
        super().reconfigure(config)
