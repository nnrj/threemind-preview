"""Independent native memory/5 backend; never executes the reference engine."""

import json

from threemind_runtime.host import NativeEngine

from .local5 import KERNEL_ID, Local5Config


class NativeLocal5Engine(NativeEngine):
    config_type = Local5Config
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not Local5Config:
            raise ValueError("memory/5 requires Local5Config")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal5

        self._engine = NativeLocal5(
            json.dumps((config or Local5Config()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return Local5Config(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not Local5Config:
            raise ValueError("memory/5 requires Local5Config")
        super().reconfigure(config)
