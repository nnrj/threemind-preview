"""Explicit endpoint tests of independent births; no fitness or Core mutation."""

import json
import math
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .development import validate_spec
from .evolution_protocol import SELECTION_METRICS, Seed
from .protocols import RunSpec, StrictModel
from .record_schema import ExecutionRecordOptions

VERSION = "threemind.assessment/1"


class Criterion(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,47}$")
    metric: str
    operator: Literal["gt", "gte", "lt", "lte", "eq"] = "gte"
    threshold: float = Field(allow_inf_nan=False, strict=True)
    required_fraction: float = Field(default=1, gt=0, le=1, allow_inf_nan=False, strict=True)

    @field_validator("metric")
    @classmethod
    def available_metric(cls, value):
        if value not in SELECTION_METRICS:
            raise ValueError("评估指标必须来自实际实现的测量目录。")
        return value


class AssessmentProtocol(StrictModel):
    schema_id: Literal["threemind.assessment/1"] = VERSION
    inheritance_rule: Literal["threemind.birth/1"] = "threemind.birth/1"
    source_version_id: UUID
    evaluation: RunSpec
    environment_seeds: list[Seed] = Field(min_length=1, max_length=32)
    excluded_environment_seeds: list[Seed] = Field(default_factory=list, max_length=4096)
    criteria: list[Criterion] = Field(min_length=1, max_length=8)

    @field_validator("evaluation", mode="before")
    @classmethod
    def strict_science(cls, value):
        if isinstance(value, RunSpec):
            return value
        return RunSpec.model_validate_json(json.dumps(value, allow_nan=False), strict=True)

    @model_validator(mode="after")
    def coherent(self):
        if len(set(self.environment_seeds)) != len(self.environment_seeds):
            raise ValueError("评估环境种子不能重复。")
        if set(self.environment_seeds) & set(self.excluded_environment_seeds):
            raise ValueError("评估种子与明确排除的训练／选择种子重叠。")
        if len({rule.id for rule in self.criteria}) != len(self.criteria):
            raise ValueError("评估规则编号不能重复。")
        spec = self.evaluation
        if spec.duration_s is None:
            raise ValueError("终点评估需要有限的观察时长；该限制不适用于普通意识。")
        if spec.environment not in ("mujoco", "ambient", "world") or spec.environment_seed is not None:
            raise ValueError("独立评估使用模拟环境；环境随机化由种子表统一分配。")
        if any(getattr(spec, scope + "_telemetry").enabled for scope in ("host", "process", "runtime")):
            raise ValueError("独立评估不能混入宿主或执行进程遥测刺激。")
        if spec.clock == "realtime":
            raise ValueError("独立评估请选择尽速或指定倍率时钟。")
        validate_spec(spec, None, 86400)
        if any(c.metric.startswith("energy_") for c in self.criteria) and not spec.config.get(
            "energy_simulation_enabled", False
        ):
            raise ValueError("能量评估需要模型的能量模拟已开启。")
        return self


class AssessmentRequest(ExecutionRecordOptions):
    operation_id: UUID
    name: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=8000)
    protocol: AssessmentProtocol

    @field_validator("name", "objective")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("评估名称和目标不能为空。")
        return value.strip()


def decide(value, criterion):
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    threshold = criterion.threshold
    return {
        "gt": value > threshold,
        "gte": value >= threshold,
        "lt": value < threshold,
        "lte": value <= threshold,
        "eq": value == threshold,
    }[criterion.operator]


def summarize(trials, criteria):
    """All declared trials stay in the denominator, including failed/missing ones.

    This is a finite test-set decision, never a confidence interval or estimate
    of the probability of succeeding in an unobserved physical environment.
    """
    result = []
    total = len(trials)
    for criterion in criteria:
        answers = [
            decide(row["values"].get(criterion.metric), criterion) if row["complete"] else None for row in trials
        ]
        passed = sum(answer is True for answer in answers)
        failed = sum(answer is False for answer in answers)
        unknown = total - passed - failed
        lower = passed / total if total else None
        upper = (passed + unknown) / total if total else None
        status = (
            "satisfied"
            if lower is not None and lower >= criterion.required_fraction
            else "not_satisfied"
            if upper is not None and upper < criterion.required_fraction
            else "undetermined"
        )
        result.append(
            {
                "criterion": criterion.model_dump(mode="json"),
                "status": status,
                "total": total,
                "satisfied": passed,
                "not_satisfied": failed,
                "undetermined": unknown,
                "fraction_lower_bound": lower,
                "fraction_upper_bound": upper,
                "bound_is_confidence_interval": False,
            }
        )
    return result
