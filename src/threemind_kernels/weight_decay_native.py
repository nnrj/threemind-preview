"""Native isolated weight-dependent candidate; unsupported native builds fail explicitly, without fallback."""

import json
from threemind_runtime.host import NativeEngine
from .weight_decay import KERNEL_ID, CandidateConfig


class NativeWeightDecayEngine(NativeEngine):
    config_type = CandidateConfig
    dynamics = KERNEL_ID

    def __init__(self, config=None, state=None):
        if config is not None and type(config) is not CandidateConfig:
            raise ValueError("experimental weight decay requires CandidateConfig")
        if state is not None and config is not None:
            raise ValueError("restoration uses saved configuration")
        from _threemind_native import NativeWeightDecay

        self._engine = NativeWeightDecay(
            json.dumps((config or CandidateConfig()).to_dict()), None if state is None else state.payload.decode()
        )

    @property
    def config(self):
        return CandidateConfig(**json.loads(self._engine.config_json()))

    def reconfigure(self, config):
        if type(config) is not CandidateConfig:
            raise ValueError("experimental weight decay requires CandidateConfig")
        super().reconfigure(config)
