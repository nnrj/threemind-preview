"""Native /6.1; unsupported native builds fail explicitly, without fallback."""

import json

from threemind_runtime.host import NativeEngine

from .local61 import KERNEL_ID, Local61Config


class NativeLocal61Engine(NativeEngine):
    config_type = Local61Config
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not Local61Config:
            raise ValueError("memory/6.1 requires Local61Config")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal61

        self._engine = NativeLocal61(
            json.dumps((config or Local61Config()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return Local61Config(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not Local61Config:
            raise ValueError("memory/6.1 requires Local61Config")
        super().reconfigure(config)
