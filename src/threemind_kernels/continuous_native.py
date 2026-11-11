from __future__ import annotations

import json

from threemind_runtime.host import NativeEngine

from .continuous import KERNEL_ID, ContinuousConfig


class NativeContinuousEngine(NativeEngine):
    dynamics = KERNEL_ID
    config_type = ContinuousConfig

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not self.config_type:
            raise ValueError("continuous kernel requires ContinuousConfig")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeContinuous

        self._engine = NativeContinuous(
            json.dumps((config or self.config_type()).to_dict()),
            state.payload.decode() if state else None,
            **({"kernel": self.dynamics} if self.dynamics != KERNEL_ID else {}),
        )

    @property
    def config(self):
        return self.config_type(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not self.config_type:
            raise ValueError("continuous kernel requires ContinuousConfig")
        super().reconfigure(config)
