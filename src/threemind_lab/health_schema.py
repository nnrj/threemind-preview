from typing import Literal

from pydantic import Field, model_validator

from threemind_runtime.ecology_observer import WarningRule

from .protocols import StrictModel

METRICS = {
    "ready_wait_s": {"zh": "可领取任务最长等待时间", "en": "Longest wait among eligible tasks", "unit": "s"},
    "expired_leases": {"zh": "已过期但尚未恢复的租约数", "en": "Expired leases awaiting recovery", "unit": "count"},
    "commit_age_s": {
        "zh": "运行中脑或种群距最近提交边界的最长时间",
        "en": "Longest committed-boundary age of active brains or populations",
        "unit": "s",
    },
    "worker_rss_mib": {"zh": "执行节点进程最高常驻内存", "en": "Maximum worker process RSS", "unit": "MiB"},
    "worker_cpu_percent": {
        "zh": "执行节点进程最高 CPU 占用",
        "en": "Maximum worker process CPU use",
        "unit": "% of one logical CPU",
    },
    "host_memory_percent": {
        "zh": "执行节点所在宿主机最高内存使用率",
        "en": "Maximum memory use of worker hosts",
        "unit": "%",
    },
}


class HealthRule(WarningRule):
    metric: Literal[
        "ready_wait_s", "expired_leases", "commit_age_s", "worker_rss_mib", "worker_cpu_percent", "host_memory_percent"
    ] = "ready_wait_s"
    threshold: float = Field(300.0, ge=0, le=1e12, allow_inf_nan=False)
    hold_us: int = Field(30_000_000, ge=0, le=10**12)
    cooldown_us: int = Field(300_000_000, ge=0, le=10**12)
    maximum_gap_us: int = Field(60_000_000, ge=1, le=10**12)


class HealthConfig(StrictModel):
    enabled: bool = Field(False, strict=True)
    rules: list[HealthRule] = Field(
        default_factory=lambda: [
            HealthRule(id="waiting"),
            HealthRule(id="lease", metric="expired_leases", threshold=1, hold_us=0),
            HealthRule(id="checkpoint", metric="commit_age_s", threshold=180),
            HealthRule(id="memory", metric="host_memory_percent", threshold=95),
        ],
        max_length=16,
    )

    @model_validator(mode="after")
    def unique(self):
        if len({r.id for r in self.rules}) != len(self.rules):
            raise ValueError("执行预警的规则编号不能重复。")
        return self
