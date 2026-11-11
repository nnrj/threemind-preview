"""Declarative research documents select evidence; they cannot supply measurements."""

import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .note_schema import bounded_text
from .protocols import StrictModel

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$", strict=True)]
Metric = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.]{0,159}$", strict=True)]


class CaptureSource(StrictModel):
    operation_id: UUID
    kind: Literal[
        "trajectory",
        "nodes",
        "edges",
        "analysis",
        "events",
        "evolution",
        "ecology_trajectory",
        "ecology_members",
        "assessment",
        "temporal_windows",
        "temporal_nodes",
        "temporal_series",
    ]
    run_id: UUID | None = None
    checkpoint_id: UUID | None = None
    analysis_artifact_id: UUID | None = None
    evolution_id: UUID | None = None
    evolution_generation: int | None = Field(default=None, ge=0, le=999, strict=True)
    evolution_stage: Literal["selection", "evaluation", "verification"] | None = None
    ecology_id: UUID | None = None
    ecology_checkpoint_id: UUID | None = None
    assessment_id: UUID | None = None
    calibration_id: UUID | None = None
    window_ids: list[Identifier] = Field(default_factory=list, max_length=100)
    metrics: list[Metric] = Field(default_factory=list, max_length=32)
    from_us: str | None = None
    through_us: str | None = None
    event_group: Literal["all", "inputs", "interventions", "lifecycle", "readouts"] = "all"
    event_kinds: list[Metric] = Field(default_factory=list, max_length=64)

    @field_validator("from_us", "through_us")
    @classmethod
    def time(cls, value):
        if value is None:
            return value
        if not value.isascii() or not value.isdigit() or len(value) > 39:
            raise ValueError("source time must be a nonnegative integer string of at most 39 digits")
        return str(int(value))

    @model_validator(mode="after")
    def source(self):
        temporal = self.kind in ("temporal_windows", "temporal_nodes", "temporal_series")
        if not temporal and (self.calibration_id is not None or self.window_ids):
            raise ValueError("temporal selectors require a temporal source")
        if len(set(self.window_ids)) != len(self.window_ids):
            raise ValueError("window identities must be unique")
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("source metrics must be unique")
        if self.kind == "temporal_series" and len(self.window_ids) != 1:
            raise ValueError("a temporal curve selects exactly one window; do not merge overlapping windows")
        if self.calibration_id is not None:
            if any(
                x is not None
                for x in (
                    self.run_id,
                    self.checkpoint_id,
                    self.analysis_artifact_id,
                    self.evolution_id,
                    self.evolution_generation,
                    self.evolution_stage,
                    self.ecology_id,
                    self.ecology_checkpoint_id,
                    self.assessment_id,
                    self.from_us,
                    self.through_us,
                )
            ):
                raise ValueError("select a temporal experiment or a consciousness checkpoint, not both")
            if self.event_group != "all" or self.event_kinds:
                raise ValueError("event filters require an events source")
            return self
        ecological = self.kind in ("ecology_trajectory", "ecology_members")
        if self.kind == "assessment":
            if self.assessment_id is None or any(
                value is not None
                for value in (
                    self.run_id,
                    self.checkpoint_id,
                    self.analysis_artifact_id,
                    self.evolution_id,
                    self.evolution_generation,
                    self.evolution_stage,
                    self.ecology_id,
                    self.ecology_checkpoint_id,
                    self.from_us,
                    self.through_us,
                )
            ):
                raise ValueError("独立评估来源需要且仅需选择评估批次；固定全部已声明试验，不选择部分成功个体。")
        elif self.assessment_id is not None:
            raise ValueError("assessment selector requires an assessment source")
        elif ecological:
            if self.ecology_id is None or any(
                value is not None
                for value in (
                    self.run_id,
                    self.checkpoint_id,
                    self.analysis_artifact_id,
                    self.evolution_id,
                    self.evolution_generation,
                    self.evolution_stage,
                )
            ):
                raise ValueError(
                    "ecological sources require only a population and optional fixed population checkpoint"
                )
            if self.kind == "ecology_members" and (self.from_us is not None or self.through_us is not None):
                raise ValueError("population distributions select a whole checkpoint, not a time interval")
        elif self.ecology_id is not None or self.ecology_checkpoint_id is not None:
            raise ValueError("ecological selectors require an ecological source")
        elif self.kind == "evolution":
            if self.evolution_id is None or self.evolution_generation is None or self.evolution_stage is None:
                raise ValueError("evolution sources require a campaign, generation and stage")
            if any(
                value is not None
                for value in (self.run_id, self.checkpoint_id, self.analysis_artifact_id, self.from_us, self.through_us)
            ):
                raise ValueError("evolution sources cannot also select a run or time interval")
        elif any(value is not None for value in (self.evolution_id, self.evolution_generation, self.evolution_stage)):
            raise ValueError("evolution selectors require an evolution source")
        elif self.kind == "analysis":
            if (
                self.analysis_artifact_id is None
                or self.run_id
                or self.checkpoint_id
                or self.from_us
                or self.through_us
            ):
                raise ValueError("analysis sources require only a completed analysis artifact")
        elif self.run_id is None or self.analysis_artifact_id:
            raise ValueError("run sources require a run and cannot select an analysis artifact")
        if self.kind in ("nodes", "edges") and (self.from_us is not None or self.through_us is not None):
            raise ValueError("network distributions select a checkpoint, not a trajectory interval")
        if self.from_us is not None and self.through_us is not None and int(self.from_us) > int(self.through_us):
            raise ValueError("source interval starts after its end")
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError("source metrics must be unique")
        if self.kind != "events" and (self.event_group != "all" or self.event_kinds):
            raise ValueError("event filters require an events source")
        if len(set(self.event_kinds)) != len(self.event_kinds):
            raise ValueError("event kinds must be unique")
        return self


class Commentary(StrictModel):
    id: Identifier
    type: Literal["commentary"] = "commentary"
    markdown: str = Field(max_length=100000, strict=True)
    section: Literal["purpose", "methods", "results", "discussion", "limitations", "hypothesis", "other"] = "other"

    @field_validator("markdown")
    @classmethod
    def text(cls, value):
        return bounded_text(value, 300000)


class Chart(StrictModel):
    id: Identifier
    type: Literal["chart"] = "chart"
    source: UUID
    metric: Metric
    chart: Literal["line", "scatter", "histogram", "bar"] = "line"
    title: str = Field(default="", max_length=200, strict=True)
    bins: int = Field(default=30, ge=5, le=100, strict=True)
    analysis_metric: str | None = Field(default=None, min_length=1, max_length=300, strict=True)


class DataTable(StrictModel):
    id: Identifier
    type: Literal["table"] = "table"
    source: UUID
    metrics: list[Metric] = Field(min_length=1, max_length=16)
    title: str = Field(default="", max_length=200, strict=True)


class Fact(StrictModel):
    id: Identifier
    type: Literal["fact"] = "fact"
    source: UUID
    metric: Metric
    statistic: Literal["first", "last", "minimum", "maximum", "mean", "count", "missing"] = "last"
    label: str = Field(default="", max_length=200, strict=True)


class RecordBlock(StrictModel):
    id: Identifier
    type: Literal["record_block"] = "record_block"
    record_id: UUID
    revision: int = Field(ge=1, strict=True)
    block_id: Identifier


class AssessmentSummary(StrictModel):
    id: Identifier
    type: Literal["assessment_summary"] = "assessment_summary"
    source: UUID


Block = Annotated[Commentary | Chart | DataTable | Fact | RecordBlock | AssessmentSummary, Field(discriminator="type")]


class DocumentSpec(StrictModel):
    schema_version: Literal["threemind.research-document/1"] = "threemind.research-document/1"
    kind: Literal["record", "report"]
    title: str = Field(min_length=1, max_length=200, strict=True)
    sources: list[UUID] = Field(default_factory=list, max_length=32)
    blocks: list[Block] = Field(default_factory=list, max_length=100)

    @field_validator("title")
    @classmethod
    def title_text(cls, value):
        if not value.strip():
            raise ValueError("a research document title is required")
        return bounded_text(value, 800)

    @model_validator(mode="after")
    def references(self):
        if len(json.dumps(self.model_dump(mode="json"), ensure_ascii=False).encode()) > 1024 * 1024:
            raise ValueError("research document exceeds 1 MiB; split it into smaller records")
        if len(set(self.sources)) != len(self.sources) or len({block.id for block in self.blocks}) != len(self.blocks):
            raise ValueError("source references and block identifiers must be unique")
        for block in self.blocks:
            for key in ("title", "label"):
                if hasattr(block, key):
                    bounded_text(getattr(block, key), 800)
            if isinstance(block, DataTable) and len(set(block.metrics)) != len(block.metrics):
                raise ValueError("table metrics must be unique")
            if isinstance(block, RecordBlock):
                if self.kind != "report":
                    raise ValueError("only a report can reference fixed record blocks")
            elif not isinstance(block, Commentary) and block.source not in self.sources:
                raise ValueError("a data block references a source outside this document")
        return self


class SaveDocument(StrictModel):
    operation_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    spec: DocumentSpec
    review: Literal["draft", "reviewed"] = "draft"
    ai_call_id: UUID | None = None
