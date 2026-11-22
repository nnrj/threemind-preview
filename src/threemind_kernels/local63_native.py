"""Native /6.3; unsupported native builds fail explicitly, without fallback."""

import json

from threemind_runtime.host import NativeEngine

from .local63 import KERNEL_ID, Local63Config


class NativeLocal63Engine(NativeEngine):
    config_type = Local63Config
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not Local63Config:
            raise ValueError("memory/6.3 requires Local63Config")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal63

        self._engine = NativeLocal63(
            json.dumps((config or Local63Config()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return Local63Config(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not Local63Config:
            raise ValueError("memory/6.3 requires Local63Config")
        super().reconfigure(config)
