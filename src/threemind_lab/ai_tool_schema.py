from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .ai_schema import Strict
from .research_commands import PlanLimits


class ExternalTool(Strict):
    enabled: bool = Field(False, strict=True)
    provider_id: UUID | None = None

    @model_validator(mode="after")
    def enabled_provider(self):
        if self.enabled and self.provider_id is None:
            raise ValueError("启用工具需要先选择供应商")
        return self


class EnvironmentTool(ExternalTool):
    automatic: bool = Field(True, strict=True)
    frequency_s: float = Field(12.0, ge=1, le=86400, strict=True)
    cadence_clock: Literal["host", "simulation"] = "host"
    random_frequency: bool = Field(True, strict=True)
    random_seed: int = Field(0, ge=0, le=2**32 - 1, strict=True)
    intensity: float = Field(0.7, gt=0, le=100, strict=True)
    irregularity: float = Field(0.65, ge=0, le=1, strict=True)
    max_text_chars: int = Field(2000, ge=1, le=20000, strict=True)
    scenario: str = Field("", max_length=4000)


class InterpreterTool(ExternalTool):
    frequency_s: float = Field(30.0, ge=2, le=86400, strict=True)
    cadence_clock: Literal["host", "simulation"] = "host"
    periodic_enabled: bool = Field(True, strict=True)
    language: str = Field("zh-CN", min_length=1, max_length=50)
    on_repeatable_structure: bool = Field(False, strict=True)
    active_nodes_enabled: bool = Field(True, strict=True)
    on_manual_stimulus: bool = Field(False, strict=True)
    listen_background_active_nodes: bool = Field(False, strict=True)
    deduplicate_readouts: bool = Field(False, strict=True)
    activation_min: float = Field(0.08, ge=0, le=100, strict=True)
    activation_max: float = Field(1.0, ge=0, le=100, strict=True)
    max_active_nodes: int = Field(200, ge=1, le=2000, strict=True)
    max_edges: int = Field(400, ge=0, le=5000, strict=True)

    @model_validator(mode="after")
    def activation_range(self):
        if self.activation_max < self.activation_min:
            raise ValueError("激活上限不能小于下限")
        return self


class AssistantTool(ExternalTool):
    limits: PlanLimits = Field(default_factory=PlanLimits)
    max_stimulus_chars: int = Field(2000, ge=1, le=20000, strict=True)
    allow_automatic: bool = Field(False, strict=True)
    language: str = Field("zh-CN", min_length=1, max_length=50)


class LabAITools(Strict):
    schema_version: Literal["threemind.lab-ai-tools/2"] = "threemind.lab-ai-tools/2"
    environment: EnvironmentTool = Field(default_factory=EnvironmentTool)
    interpreter: InterpreterTool = Field(default_factory=InterpreterTool)
    assistant: AssistantTool = Field(default_factory=AssistantTool)


class ToolEdit(Strict):
    expected_revision: int = Field(0, ge=0, strict=True)
    config: LabAITools


class ToolRequest(Strict):
    request_id: UUID
    purpose: Literal["environment", "interpretation", "research_plan", "analysis"]
    checkpoint_id: UUID | None = None
    plan_id: UUID | None = None
    objective: str = Field("", max_length=12000)
    mode: Literal["manual", "confirm", "automatic"] = "confirm"


class AnalysisStatement(Strict):
    text: str = Field(min_length=1, max_length=4000)
    source_refs: list[str] = Field(min_length=1, max_length=30)


class ExternalAnalysis(Strict):
    summary: str = Field(min_length=1, max_length=6000)
    observations: list[AnalysisStatement] = Field(default_factory=list, max_length=30)
    interpretation: str = Field("", max_length=12000)
    alternatives: list[str] = Field(default_factory=list, max_length=20)
    conclusion: str = Field("", max_length=6000)
    follow_up: list[str] = Field(default_factory=list, max_length=20)
    confidence: Literal["low", "medium", "high"] = "low"
