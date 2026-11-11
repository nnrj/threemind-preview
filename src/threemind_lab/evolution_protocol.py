"""Explicit experimental rules for acquired-network inheritance and selection.

No objective is selected by default, and no genetic operator edits Core graphs.
"""

import json
import math
import random
import statistics
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .development import validate_spec
from .protocols import RunSpec, StrictModel
from .record_schema import ExecutionRecordOptions

SELECTION_METRICS = {
    "task_reward": ("官方任务末步评分", "任务分", "保留官方任务评分定义，仅用于外部选择，不输入内核。"),
    "task_reward_total": ("官方任务累计评分", "任务分", "按官方动作周期累计，评估时须统一回合长度。"),
    "task_success": ("机器人任务完成", "0 / 1", "由声明的环境目标评定，只用于外部选择。"),
    "task_distance": ("终点目标距离", "m", "任务对象或端点与目标的距离；不是内核奖励。"),
    "task_best_distance": ("最小目标距离", "m", "评估期间实际观测的最小距离。"),
    "task_distance_improvement": ("目标距离改善", "m", "初始距离减终点距离。"),
    "task_mechanical_work_j": ("执行器机械功绝对值累计", "J", "不等同 Core 能量账本或电机电耗。"),
    "task_contact_samples": ("发生接触的采样次数", "次", "包含躯体与地面接触；无预设好坏。"),
    "observed_lifetime_s": ("已观测存续时长", "模拟秒", "未死亡个体的结果在实验终点右删失，并非完整寿命。"),
    "not_dead_at_end": ("终点未进入内核死亡", "0 / 1", "只反映 Core 生命状态，不代表意识质量或生态繁殖成功。"),
    "nodes": ("终点节点数", "节点", "规模指标；更多不必然更好。"),
    "edges": ("终点连接数", "连接", "规模指标；更多不必然更好。"),
    "activation": ("终点总激活", "激活", "内核观测量，不能等同于智能。"),
    "mean_activation": ("终点平均激活", "激活 / 节点", "无节点时缺失，不补零。"),
    "active_fraction": ("终点活动比例", "比例", "无节点时缺失，不补零。"),
    "edge_density": ("终点连接密度", "比例", "不足两个节点时缺失，不补零。"),
    "mean_weight": ("终点平均连接权重", "权重", "没有连接时缺失，不补零。"),
    "energy_reserve": ("终点能量储备", "实验单位", "需要开启 Core 能量模拟；单位未经物理标定。"),
    "energy_consumed": ("评估累计能量消耗", "实验单位", "累计账本量；需要开启 Core 能量模拟。"),
    "energy_supplied": ("评估累计接收供给", "实验单位", "由声明的供给协议决定，不等同于环境觅食。"),
    "energy_unserved": ("评估累计未满足需求", "实验单位", "需要开启 Core 能量模拟。"),
}
Seed = Annotated[int, Field(ge=0, le=2**32 - 1, strict=True)]


class SelectionCriterion(StrictModel):
    metric: str
    direction: Literal["maximize", "minimize"]
    aggregate: Literal["mean", "median", "worst"] = "mean"

    @field_validator("metric")
    @classmethod
    def known_metric(cls, value):
        if value not in SELECTION_METRICS:
            raise ValueError("筛选指标必须来自已实现的指标目录。")
        return value


class EvolutionProtocol(StrictModel):
    schema_id: Literal["threemind.evolution/1"] = "threemind.evolution/1"
    inheritance_rule: Literal["threemind.birth/1"] = "threemind.birth/1"
    selection_mode: Literal["directed"] = "directed"
    initial_version_id: UUID | None = None
    generations: int = Field(ge=1, le=1000, strict=True)
    population_size: int = Field(ge=2, le=64, strict=True)
    survivor_count: int = Field(ge=1, le=64, strict=True)
    development: RunSpec
    evaluation: RunSpec
    development_seeds: list[list[Seed]] = Field(min_length=1, max_length=1000)
    evaluation_seeds: list[Seed] = Field(min_length=1, max_length=32)
    verification_seeds: list[Seed] = Field(min_length=1, max_length=32)
    criteria: list[SelectionCriterion] = Field(min_length=1, max_length=8)

    @field_validator("development", "evaluation", mode="before")
    @classmethod
    def scientific_types(cls, value):
        if isinstance(value, RunSpec):
            return value
        return RunSpec.model_validate_json(json.dumps(value, allow_nan=False), strict=True)

    @model_validator(mode="after")
    def coherent(self):
        if self.survivor_count > self.population_size:
            raise ValueError("父本数量不能超过每代个体数。")
        if len(self.development_seeds) != self.generations or any(
            len(row) != self.population_size for row in self.development_seeds
        ):
            raise ValueError("发育种子表必须覆盖每一代的每一个体。")
        training = [seed for row in self.development_seeds for seed in row]
        if (
            len(set(training)) != len(training)
            or len(set(self.evaluation_seeds)) != len(self.evaluation_seeds)
            or len(set(self.verification_seeds)) != len(self.verification_seeds)
        ):
            raise ValueError("发育种子不能重复，评估环境种子也不能重复。")
        if set(training) & set(self.evaluation_seeds):
            raise ValueError("评估环境种子不能与发育环境种子重叠。")
        if set(self.verification_seeds) & (set(training) | set(self.evaluation_seeds)):
            raise ValueError("最终验证环境不能与发育或筛选评估环境重叠。")
        if len({criterion.metric for criterion in self.criteria}) != len(self.criteria):
            raise ValueError("同一个筛选指标只能声明一次；列表顺序表示优先级。")
        for spec in (self.development, self.evaluation):
            if spec.duration_s is None:
                raise ValueError("分代筛选需要有限的发育和评估观察时长；持续发育可使用普通意识或生态环境。")
            if spec.environment not in ("mujoco", "ambient", "world", "robot") or spec.environment_seed is not None:
                raise ValueError("当前多代训练使用模拟物理或合成环境，随机化统一由种子表分配；基础环境种子须留空。")
            if any(getattr(spec, scope + "_telemetry").enabled for scope in ("host", "process", "runtime")):
                raise ValueError("可重放多代协议不能启用宿主或执行进程遥测刺激。")
            if spec.clock == "realtime":
                raise ValueError("多代训练请选择尽速或指定倍率时钟；物理部署使用普通运行入口。")
            validate_spec(spec, None, 86400)
        validate_spec(self.evaluation, {"protocol": self.development.model_dump()}, 86400)
        if any(c.metric.startswith("task_") for c in self.criteria):
            if self.evaluation.environment != "robot" or self.evaluation.robot_protocol.objective == "observe":
                raise ValueError("机器人筛选指标需要明确的机器人任务，不能把仅观察当作成功。")
            reference = self.evaluation.robot_protocol.schema_id == "threemind.robot-task/2"
            supported = {"task_distance", "task_best_distance", "task_distance_improvement", "task_reward", "task_reward_total"}
            if reference and any(c.metric.startswith("task_") and c.metric not in supported for c in self.criteria):
                raise ValueError("Playground 请选择已定义的距离或官方评分；不把没有定义的成功或成本当成零。")
            if not reference and any(c.metric in ("task_reward", "task_reward_total") for c in self.criteria):
                raise ValueError("官方任务评分仅适用于 Playground 协议。")
        if any(c.metric.startswith("energy_") for c in self.criteria) and not self.evaluation.config.get(
            "energy_simulation_enabled", False
        ):
            raise ValueError("能量筛选指标需要在发育与评估的共同 Core 配置中开启能量模拟。")
        return self


class EvolutionRequest(ExecutionRecordOptions):
    operation_id: UUID
    name: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=8000)
    protocol: EvolutionProtocol

    @field_validator("name", "objective")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("名称与实验目标不能为空。")
        return value.strip()


def seed_plan(generations: int, population: int, blocks: int, verification_blocks: int, seed: int):
    if not (
        1 <= generations <= 1000
        and 2 <= population <= 64
        and 1 <= blocks <= 32
        and 1 <= verification_blocks <= 32
        and 0 <= seed < 2**32
    ):
        raise ValueError("种子计划的范围无效。")
    count = generations * population
    values = random.Random(seed).sample(range(2**32), count + blocks + verification_blocks)
    return {
        "development_seeds": [values[i * population : (i + 1) * population] for i in range(generations)],
        "evaluation_seeds": values[count : count + blocks],
        "verification_seeds": values[count + blocks :],
    }


def endpoints(run, criteria):
    """Read committed endpoints, never sample/re-run a candidate during selection."""
    metrics = run["metrics"]
    values = {}
    for criterion in criteria:
        if criterion.metric == "observed_lifetime_s":
            value = int(run["time_us"]) / 1e6
        elif criterion.metric == "not_dead_at_end":
            value = int(run["life"] != "dead")
        else:
            value = metrics.get(criterion.metric)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"评估指标 {criterion.metric} 缺失或不是有限数值；不会补零或忽略该环境。")
        values[criterion.metric] = value
    return {
        "values": values,
        "life": run["life"],
        "time_us": str(run["time_us"]),
        "lifetime_right_censored": run["life"] != "dead",
    }


def rank_candidates(rows, criteria):
    """Lexicographic objectives, then the declared slot. Missing blocks are fatal."""
    ranked = []
    for row in rows:
        scores, key = {}, []
        for criterion in criteria:
            values = [block["values"][criterion.metric] for block in row["blocks"]]
            if not values or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values
            ):
                raise ValueError("评估环境不完整，不能筛选。")
            if criterion.aggregate == "mean":
                score = math.fsum(v / len(values) for v in values)
            elif criterion.aggregate == "median":
                score = statistics.median(values)
            else:
                score = min(values) if criterion.direction == "maximize" else max(values)
            if not math.isfinite(score):
                raise ValueError("汇总结果超出有限数值范围。")
            scores[criterion.metric] = score
            key.append(-score if criterion.direction == "maximize" else score)
        ranked.append(row | {"scores": scores, "sort_key": (*key, row["slot"])})
    ranked.sort(key=lambda row: row["sort_key"])
    return [
        {key: value for key, value in row.items() if key != "sort_key"} | {"rank": i + 1}
        for i, row in enumerate(ranked)
    ]
