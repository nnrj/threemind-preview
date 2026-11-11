"""Bounded scientific facts shared by human, script, CLI and Agent entry points."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from .experiment_archive import canonical
from .protocols import StrictModel

Status = Literal['planned', 'running', 'completed', 'failed', 'interrupted', 'cancelled', 'unknown']


class ExecutionRecordOptions(StrictModel):
    # Host metadata only; never included in the frozen Core/RunSpec protocol.
    record_executor: Literal['ai', 'human', 'mixed', 'unknown'] = 'human'
    record_classification: Literal['formal', 'calibration', 'development'] = 'formal'


class ExperimentSpec(StrictModel):
    model_config = ConfigDict(extra='forbid', serialize_by_alias=True)
    schema_id: Literal['threemind.research-experiment/1'] = Field(default='threemind.research-experiment/1', alias='schema')
    source_key: str = Field(min_length=1, max_length=400)
    original_id: str | None = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    classification: Literal['formal', 'proposal', 'calibration', 'development'] = 'formal'
    execution_status: Status = 'planned'
    experiment_date: date | None = None
    date_basis: str | None = Field(default=None, max_length=500)
    executor: Literal['ai', 'human', 'mixed', 'unknown'] = 'unknown'
    kernels: list[str] = Field(default_factory=list, max_length=50)
    question: str | None = Field(default=None, max_length=20000)
    protocol: str | None = Field(default=None, max_length=200000)
    protocol_version: str | None = Field(default=None, max_length=200)
    conclusion: str | None = Field(default=None, max_length=200000)
    missing: list[str] = Field(default_factory=list, max_length=200)
    required_roles: list[str] = Field(default_factory=lambda: ['protocol', 'report', 'note'], max_length=30)
    metadata: dict = Field(default_factory=dict)

    @field_validator('metadata')
    @classmethod
    def bounded(cls, value):
        if len(canonical(value)) > 512 * 1024:
            raise ValueError('record metadata exceeds 512 KiB')
        return value


class RegisterRecord(StrictModel):
    request_id: UUID
    spec: ExperimentSpec


class AppendRecord(StrictModel):
    request_id: UUID
    kind: Literal['subject', 'condition', 'stage', 'process', 'result', 'correction', 'gap']
    original_key: str = Field(min_length=1, max_length=400)
    content: dict

    @field_validator('content')
    @classmethod
    def bounded(cls, value):
        if len(canonical(value)) > 1024 * 1024:
            raise ValueError('one process entry exceeds 1 MiB; attach its original instead')
        return value


class EvidenceSpec(StrictModel):
    logical_id: str = Field(min_length=1, max_length=500)
    role: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=500)
    format: str = Field(default='unknown', max_length=150)
    byte_count: int | None = Field(default=None, ge=0, strict=True)
    sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    locator: dict
    stage_key: str | None = Field(default=None, max_length=400)
    dependencies: list[str] = Field(default_factory=list, max_length=1000)


class AttachRecord(StrictModel):
    request_id: UUID
    evidence: EvidenceSpec


class SaveRecordText(StrictModel):
    request_id: UUID
    identity: UUID
    expected_revision: int = Field(default=0, ge=0, strict=True)
    kind: Literal['record', 'report', 'protocol', 'note']
    title: str = Field(min_length=1, max_length=200)
    markdown: str = Field(max_length=1000000)
    revision_reason: str | None = Field(default=None, max_length=2000)


class FinalizeRecord(StrictModel):
    request_id: UUID
    execution_status: Status = 'completed'


class BackfillPlan(StrictModel):
    request_id: UUID
    source_manifest_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    records: list[dict] = Field(min_length=1, max_length=50)


class ApplyBackfill(StrictModel):
    request_id: UUID
    plan_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
