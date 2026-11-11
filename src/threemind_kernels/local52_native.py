"""Native /5.2; unsupported native builds fail explicitly, without fallback."""

import json
from threemind_runtime.host import NativeEngine
from .local52 import KERNEL_ID, Local52Config


class NativeLocal52Engine(NativeEngine):
    config_type = Local52Config
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not Local52Config:
            raise ValueError("memory/5.2 requires Local52Config")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal52

        self._engine = NativeLocal52(
            json.dumps((config or Local52Config()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return Local52Config(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not Local52Config:
            raise ValueError("memory/5.2 requires Local52Config")
        super().reconfigure(config)
