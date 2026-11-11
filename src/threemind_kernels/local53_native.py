"""Native /5.3; unsupported native builds fail explicitly, without fallback."""

import json
from threemind_runtime.host import NativeEngine
from .local53 import KERNEL_ID, Local53Config


class NativeLocal53Engine(NativeEngine):
    config_type = Local53Config
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not Local53Config:
            raise ValueError("memory/5.3 requires Local53Config")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLocal53

        self._engine = NativeLocal53(
            json.dumps((config or Local53Config()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return Local53Config(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not Local53Config:
            raise ValueError("memory/5.3 requires Local53Config")
        super().reconfigure(config)
