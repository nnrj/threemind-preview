"""Frozen scientific protocol for ecological selection, separate from directed scoring."""

import json
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from threemind_runtime.ecology import EcologySettings

from .development import DevelopmentRequest, validate_spec
from .protocols import RunSpec, StrictModel
from .record_schema import ExecutionRecordOptions


class EcologyProtocol(StrictModel):
    base: RunSpec
    ecology: EcologySettings = Field(default_factory=EcologySettings)
    initial_version_id: UUID | None = None
    external_inputs: bool = Field(default=False, strict=True)

    @field_validator("base", mode="before")
    @classmethod
    def strict_base(cls, value):
        return DevelopmentRequest.strict_protocol(value)

    @field_validator("ecology", mode="before")
    @classmethod
    def strict_ecology(cls, value):
        return value if isinstance(value, EcologySettings) else EcologySettings.model_validate_json(json.dumps(value))

    @model_validator(mode="after")
    def complete_protocol(self):
        if self.base.environment != "world" or self.base.world_protocol is None:
            raise ValueError("生态训练需要可配置的物理世界与躯体协议。")
        self.ecology.validate_world(self.base.world_protocol)
        validate_spec(self.base, None, 86400)
        return self


class EcologyRequest(ExecutionRecordOptions):
    operation_id: UUID
    name: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=8000)
    protocol: EcologyProtocol

    @field_validator("name", "objective")
    @classmethod
    def nonblank(cls, value):
        return DevelopmentRequest.nonblank(value)
