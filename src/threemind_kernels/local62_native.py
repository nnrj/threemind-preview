"""Native /6.2; unsupported native builds fail explicitly, without fallback."""

import json

from threemind_runtime.host import NativeEngine

from .local62 import KERNEL_ID, Local62Config


class NativeLocal62Engine(NativeEngine):
    config_type = Local62Config
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not Local62Config:
            raise ValueError("memory/6.2 requires Local62Config")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal62

        self._engine = NativeLocal62(
            json.dumps((config or Local62Config()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return Local62Config(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not Local62Config:
            raise ValueError("memory/6.2 requires Local62Config")
        super().reconfigure(config)
