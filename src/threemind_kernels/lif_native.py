from __future__ import annotations

import json

from threemind_runtime.host import NativeEngine

from .lif import KERNEL_ID, LifConfig


class NativeLifEngine(NativeEngine):
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not LifConfig:
            raise ValueError("LIF kernel requires LifConfig")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeLif

        self._engine = NativeLif(
            json.dumps((config or LifConfig()).to_dict()), state.payload.decode() if state else None
        )

    @property
    def config(self):
        return LifConfig(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not LifConfig:
            raise ValueError("LIF kernel requires LifConfig")
        super().reconfigure(config)

    def physical_nodes(self):
        return json.loads(self._engine.physical_nodes_json())

    def advance_to(self, target_us, observer=None, *, inputs_only=False, record_spikes=False):
        for event in json.loads(self._engine.advance(str(target_us), observer is not None, inputs_only, record_spikes)):
            observer(event)
