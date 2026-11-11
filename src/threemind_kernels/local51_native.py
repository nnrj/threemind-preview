"""Independent native memory/5.1 backend; never executes the reference engine."""

import json

from threemind_runtime.host import NativeEngine

from .local51 import KERNEL_ID, Local51Config


class NativeLocal51Engine(NativeEngine):
    config_type = Local51Config
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not Local51Config:
            raise ValueError("memory/5.1 requires Local51Config")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal51

        self._engine = NativeLocal51(
            json.dumps((config or Local51Config()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return Local51Config(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not Local51Config:
            raise ValueError("memory/5.1 requires Local51Config")
        super().reconfigure(config)
