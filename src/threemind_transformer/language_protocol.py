"""External language instruments: frozen mapping identity and declared information access."""

from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .language_assets import registry
from .protocol import Contract, digest


class LanguageProtocol(Contract):
    schema_id: Literal["threemind.language-adapter/1", "threemind.language-adapter/2"] = "threemind.language-adapter/1"
    feature_layout: Literal["signed-average", "unsigned-peak"] = "signed-average"
    mode: Literal["core", "strict", "assisted"] = "core"
    input_model: Literal["text", "qwen", "scratch"] = "text"
    output_model: Literal["raw", "qwen", "scratch"] = "raw"
    scratch_width: int = Field(default=128, ge=32, le=256)
    scratch_heads: int = Field(default=4, ge=1, le=8)
    scratch_layers: int = Field(default=2, ge=1, le=4)
    scratch_context: int = Field(default=512, ge=64, le=2048)
    input_checkpoint_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    output_checkpoint_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    seed: int = Field(default=17, ge=0, le=2**32 - 1)
    embedding_revision: str = registry()["embedding"]["revision"]
    decoder_revision: str = registry()["decoder"]["revision"]
    embedding_dimensions: int = Field(default=64, ge=32, le=256)
    response_us: int = Field(default=500000, ge=10000, le=10000000)
    sample_us: int = Field(default=20000, ge=1000, le=1000000)
    feature_buckets: int = Field(default=64, ge=16, le=256)
    feature_bins: int = Field(default=4, ge=1, le=16)
    prefix_tokens: int = Field(default=4, ge=1, le=16)
    maximum_tokens: int = Field(default=96, ge=1, le=256)

    @model_validator(mode="after")
    def identity(self):
        if self.schema_id.endswith("/1") and self.feature_layout != "signed-average":
            raise ValueError("alternative observation requires language-adapter/2; legacy mapping is unchanged")
        if self.scratch_width % self.scratch_heads:
            raise ValueError("scratch width must be divisible by attention heads")
        if self.input_model == "scratch" and self.embedding_dimensions > self.scratch_width:
            raise ValueError("sensory dimensions exceed scratch Transformer width")
        if self.input_checkpoint_sha256 and self.input_model != "scratch":
            raise ValueError("input checkpoint belongs to the scratch Transformer route")
        if self.output_checkpoint_sha256 and self.output_model != "scratch":
            raise ValueError("output checkpoint belongs to the scratch Transformer route")
        if (
            self.embedding_revision != registry()["embedding"]["revision"]
            or self.decoder_revision != registry()["decoder"]["revision"]
        ):
            raise ValueError("unsupported language model revision; no automatic model substitution")
        if self.response_us % self.sample_us or self.response_us // self.sample_us > 2000:
            raise ValueError("response window requires whole samples and at most 2000 observations")
        return self

    @model_serializer(mode="wrap")
    def legacy_wire_identity(self, handler):
        value = handler(self)
        if self.schema_id.endswith("/1"):
            value.pop("feature_layout", None)
        return value

    @property
    def mapping_hash(self):
        # Assistance changes exposure, not the measured Core feature basis.
        return digest(self.model_dump(exclude={"mode", "maximum_tokens"}))


class LanguageCompute(Contract):
    compute_device: Literal["cpu", "cuda", "auto"] = "cpu"
    gpu_memory_mib: int = Field(default=3072, ge=128, le=131072)
    gpu_headroom_mib: int = Field(default=512, ge=128, le=32768)
    memory_mib: int = Field(default=8192, ge=2048, le=65536)
    wall_seconds: float = Field(default=300.0, gt=0, le=14400)
    threads: int = Field(default=2, ge=1, le=16)


class CalibrationRow(Contract):
    features: list[float] = Field(min_length=16, max_length=4096)
    text: str = Field(min_length=1, max_length=256)


class LanguageTraining(Contract):
    protocol: LanguageProtocol
    samples: list[CalibrationRow] = Field(min_length=2, max_length=512)
    steps: int = Field(default=100, ge=1, le=2000)
    learning_rate: float = Field(default=0.003, gt=0, le=0.1)
    compute: LanguageCompute = Field(default_factory=LanguageCompute)
    train_decoder: bool = False

    @model_validator(mode="after")
    def dimensions(self):
        if self.protocol.output_model == "raw":
            raise ValueError("choose a Transformer output before training its conversion")
        if self.train_decoder and self.protocol.output_model != "scratch":
            raise ValueError("base weight training is only enabled for the scratch route")
        if any(len(v.features) != self.protocol.feature_buckets * self.protocol.feature_bins for v in self.samples):
            raise ValueError("calibration features differ from declared basis")
        return self


class ScratchTraining(Contract):
    protocol: LanguageProtocol
    texts: list[str] = Field(min_length=1, max_length=512)
    steps: int = Field(default=100, ge=1, le=2000)
    learning_rate: float = Field(default=0.001, gt=0, le=0.1)
    compute: LanguageCompute = Field(default_factory=LanguageCompute)
    role: Literal["input", "output"] = "input"

    @model_validator(mode="after")
    def corpus(self):
        if getattr(self.protocol, self.role + "_model") != "scratch":
            raise ValueError("select scratch Transformer for the trained role")
        sizes = [len(text.encode("utf-8")) + 2 for text in self.texts]
        if any(not text or size > self.protocol.scratch_context for text, size in zip(self.texts, sizes)):
            raise ValueError("each UTF-8 sentence including BOS/EOS must fit scratch context; no truncation")
        if sum(sizes) > 200000:
            raise ValueError("corpus exceeds 200000 byte tokens")
        return self


def adapter_contract():
    from threemind_runtime.external_contracts import language_contract

    return language_contract()
