"""Small, bounded, explicit external learning protocol; no Core mutation API."""

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MODEL_SCHEMA = "threemind.tiny-transformer/1"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


Token = Annotated[int, Field(ge=0, le=4095)]
Sequence = Annotated[list[Token], Field(min_length=2, max_length=129)]


class Architecture(Contract):
    vocabulary: int = Field(default=64, ge=2, le=4096)
    context: int = Field(default=64, ge=2, le=128)
    width: int = Field(default=32, ge=8, le=128)
    heads: int = Field(default=4, ge=1, le=8)
    layers: int = Field(default=2, ge=1, le=3)
    seed: int = Field(default=17, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def divisible(self):
        if self.width % self.heads:
            raise ValueError("model width must be divisible by attention heads")
        return self


class Training(Contract):
    architecture: Architecture = Field(default_factory=Architecture)
    sequences: list[Sequence] = Field(min_length=1, max_length=5000)
    evaluation: list[Sequence] = Field(default_factory=list, max_length=5000)
    steps: int = Field(default=200, ge=1, le=5000)
    batch_size: int = Field(default=8, ge=1, le=32)
    learning_rate: float = Field(default=0.003, gt=0, le=0.1)
    wall_seconds: float = Field(default=30, gt=0, le=300)
    memory_mib: int = Field(default=2048, ge=256, le=4096)
    threads: int = Field(default=2, ge=1, le=4)
    # Omitted in old protocols means CPU. New UI/operation templates request auto explicitly.
    compute_device: Literal["auto", "cpu", "cuda"] = "cpu"
    gpu_memory_mib: int = Field(default=2048, ge=128, le=131072)
    gpu_headroom_mib: int = Field(default=512, ge=128, le=32768)

    @model_validator(mode="after")
    def corpus(self):
        if sum(map(len, self.sequences + self.evaluation)) > 200000:
            raise ValueError("corpus exceeds 200,000 token budget")
        if any(max(s) >= self.architecture.vocabulary for s in self.sequences + self.evaluation):
            raise ValueError("token outside declared vocabulary")
        if any(len(s) > self.architecture.context + 1 for s in self.sequences + self.evaluation):
            raise ValueError("sequence exceeds context; split explicitly rather than silently dropping tokens")
        seen = {tuple(s) for s in self.sequences}
        if any(tuple(s) in seen for s in self.evaluation):
            raise ValueError("held-out evaluation contains an exact training sequence")
        return self


class Prediction(Contract):
    tokens: list[Token] = Field(min_length=1, max_length=128)
    compute_device: Literal["auto", "cpu", "cuda"] = "cpu"
    gpu_memory_mib: int = Field(default=2048, ge=128, le=131072)
    gpu_headroom_mib: int = Field(default=512, ge=128, le=32768)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
