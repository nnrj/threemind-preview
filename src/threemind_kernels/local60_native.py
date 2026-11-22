"""Native /6.0; unsupported native builds fail explicitly, without fallback."""

import json

from threemind_runtime.host import NativeEngine

from .local60 import KERNEL_ID, Local60Config


class NativeLocal60Engine(NativeEngine):
    config_type = Local60Config
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not Local60Config:
            raise ValueError("memory/6.0 requires Local60Config")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal60

        self._engine = NativeLocal60(
            json.dumps((config or Local60Config()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return Local60Config(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not Local60Config:
            raise ValueError("memory/6.0 requires Local60Config")
        super().reconfigure(config)
