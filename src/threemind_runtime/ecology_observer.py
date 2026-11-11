"""Read-only, deterministic descriptions and sampled warning rules.

Consumes committed evidence, never an Engine. The same evaluator is usable by
Lab workers and independent hosts. No AI, graphics, database or network calls.
"""

from __future__ import annotations

import math
import operator
from copy import deepcopy
from typing import Literal

from pydantic import Field, model_validator

from .world_schema import Model, digest

VERSION = "threemind.ecology-observer/1"
METRICS = {
    "living_bodies": {"zh": "存活躯体", "en": "Living bodies", "clock": "physical"},
    "body_failures": {"zh": "累计失效躯体", "en": "Cumulative body failures", "clock": "physical"},
    "body_failure_fraction": {"zh": "累计躯体失效比例", "en": "Cumulative body failure fraction", "clock": "physical"},
    "viable_cores": {"zh": "尚未死亡的内核（含未激活）", "en": "Non-dead cores (including waiting)", "clock": "model"},
    "births": {"zh": "后代出生数", "en": "Offspring births", "clock": "model"},
    "maximum_generation": {"zh": "最高后代代数", "en": "Maximum generation", "clock": "model"},
    "deferred_population": {"zh": "种群容量暂缓次数", "en": "Population capacity deferrals", "clock": "model"},
    "deferred_budget": {"zh": "后代预算暂缓次数", "en": "Offspring budget deferrals", "clock": "model"},
}
Metric = Literal[
    "living_bodies",
    "body_failures",
    "body_failure_fraction",
    "viable_cores",
    "births",
    "maximum_generation",
    "deferred_population",
    "deferred_budget",
]
OPERATORS = {"gte": operator.ge, "gt": operator.gt, "lte": operator.le, "lt": operator.lt, "eq": operator.eq}


class WarningRule(Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,47}$")
    label: str = Field(default="", max_length=120)
    enabled: bool = True
    metric: Metric = "body_failure_fraction"
    comparison: Literal["gte", "gt", "lte", "lt", "eq"] = "gte"
    threshold: float = Field(default=0.5, ge=0, le=1e12, allow_inf_nan=False)
    hold_us: int = Field(default=0, ge=0, le=10**12)
    cooldown_us: int = Field(default=1_000_000, ge=0, le=10**12)
    maximum_gap_us: int = Field(default=10_000_000, ge=1, le=10**12)


class ObserverConfig(Model):
    schema_id: Literal["threemind.ecology-observer-config/1"] = "threemind.ecology-observer-config/1"
    enabled: bool = False
    narration_enabled: bool = True
    warnings_enabled: bool = True
    start_from: Literal["latest", "beginning"] = "latest"
    rules: list[WarningRule] = Field(default_factory=lambda: [WarningRule(id="body-failures")], max_length=32)

    @model_validator(mode="after")
    def unique_rules(self):
        if len({r.id for r in self.rules}) != len(self.rules):
            raise ValueError("warning rule identities must be unique")
        return self


def catalogue():
    return {
        "version": VERSION,
        "defaults": ObserverConfig().model_dump(mode="json"),
        "schema": ObserverConfig.model_json_schema(),
        "metrics": deepcopy(METRICS),
    }


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def _time(value):
    if type(value) is int and 0 <= value < 2**128:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 39:
        parsed = int(value)
        if parsed < 2**128:
            return parsed
    return None


def _entry(kind, code, text, facts, source, **extra):
    body = {
        "version": VERSION,
        "kind": kind,
        "code": code,
        "text": text,
        "facts": deepcopy(facts),
        "source": deepcopy(source),
        **extra,
    }
    return body | {"content_hash": digest(body)}


def describe_event(event, source):
    """Unknown events remain visible without inventing an interpretation."""
    kind = event.get("kind", "unknown")
    descriptions = {
        "founder_born": ("初始个体出生。", "A founder was born."),
        "individual_born": (
            "后代出生；继承来源见原始事件。",
            "An offspring was born; see the event for its inheritance source.",
        ),
        "body_failed": ("躯体失效；这不等同于内核死亡。", "A body failed; this does not establish Core death."),
        "resource_transfer": ("物理环境记录了一次资源转移。", "The physical environment recorded a resource transfer."),
        "birth_deferred": (
            "一次繁殖被暂缓；原因见原始事件。",
            "A birth was deferred; see the original event for its reason.",
        ),
    }
    zh, en = descriptions.get(
        kind, ("记录了一项尚无文字模板的事件。", "An event without a narration template was recorded.")
    )
    return _entry("event", kind, {"zh": zh, "en": en}, event, source)


def describe_checkpoint(population, status, source):
    # Population is the committed summary, not the first page of individuals.
    facts = {
        key: deepcopy(population.get(key))
        for key in (
            "individuals",
            "living_bodies",
            "viable_cores",
            "births",
            "body_failures",
            "maximum_generation",
            "model_time_us",
            "physical_time_us",
            "pending_delivery_us",
        )
    }
    facts["status"] = status

    def shown(key):
        value = _number(facts[key])
        return "?" if value is None else str(value)

    zh = f"累计个体 {shown('individuals')}；存活躯体 {shown('living_bodies')}；后代出生 {shown('births')}；失效躯体 {shown('body_failures')}。"
    en = f"Historical individuals: {shown('individuals')}; living bodies: {shown('living_bodies')}; offspring births: {shown('births')}; body failures: {shown('body_failures')}."
    if status in ("completed", "cancelled", "paused"):
        zh += " 训练任务当前已停止推进，不能据此判定意识死亡。"
        en += " The training task is not advancing; this does not establish consciousness death."
    return _entry("summary", "checkpoint_summary", {"zh": zh, "en": en}, facts, source)


def evaluate_rules(config: ObserverConfig, population, previous, source, *, metrics=None):
    """Advance a bounded rule state using *sampled* observations, not interpolation.

    A gap invalidates a held condition. A missing value never becomes zero or a
    recovery. Repeated timestamps cannot satisfy a positive duration by polling.
    """
    if not config.enabled or not config.warnings_enabled:
        return [], {}
    metadata = METRICS if metrics is None else metrics
    states, entries = {}, []
    for rule in config.rules:
        if not rule.enabled:
            continue
        state = deepcopy(previous.get(rule.id, {}))
        old_status = state.get("status", "clear")
        now = _time(population.get(metadata[rule.metric]["clock"] + "_time_us"))
        last = _time(state.get("last_us"))
        if now is not None and last is not None and now < last:
            raise ValueError("observer evidence clock moved backwards")
        if rule.metric == "body_failure_fraction":
            count, failures = _number(population.get("individuals")), _number(population.get("body_failures"))
            value = failures / count if count and failures is not None and failures <= count else None
        else:
            value = _number(population.get(rule.metric))
        gap = now is not None and last is not None and now - last > rule.maximum_gap_us
        notices = []
        if value is None or now is None or gap:
            if old_status != "missing":
                notices.append("coverage_gap" if gap else "missing_evidence")
            state = {"status": "missing", "since_us": None, "last_notice_us": None}
            old_status = "missing"
        if value is not None and now is not None:
            hit = OPERATORS[rule.comparison](value, rule.threshold)
            if not hit:
                if old_status == "active":
                    notices.append("cleared")
                elif old_status == "missing":
                    notices.append("coverage_resumed")
                state.update(status="clear", since_us=None)
            else:
                since = _time(state.get("since_us"))
                if since is None:
                    since = now
                state["since_us"] = str(since)
                if now - since >= rule.hold_us:
                    last_notice = _time(state.get("last_notice_us"))
                    if old_status != "active":
                        notices.append("triggered")
                    elif last_notice is not None and now > last_notice and now - last_notice >= rule.cooldown_us:
                        notices.append("reminder")
                    state["status"] = "active"
                else:
                    state["status"] = "pending"
        # Missing clock samples invalidate duration but must not erase the last
        # valid clock, otherwise a later backwards timestamp could pass unnoticed.
        state["last_us"] = str(now if now is not None else last) if now is not None or last is not None else None
        state["value"] = value
        for notice in notices:
            text = {
                "triggered": (
                    "预警条件在已采样恢复点上达到配置要求。",
                    "The warning condition met its requirement at sampled checkpoints.",
                ),
                "reminder": ("预警条件在当前采样仍成立。", "The warning condition still holds at this sample."),
                "cleared": (
                    "当前有效采样不再满足此前预警条件。",
                    "The current valid sample no longer meets the previous warning condition.",
                ),
                "coverage_gap": (
                    "采样间隔超过规则上限；此前持续条件不再成立为已知事实。",
                    "The sampling gap exceeds the rule limit; the previous held condition is no longer established.",
                ),
                "missing_evidence": (
                    "缺少有效数值或时钟，无法判定预警条件。",
                    "A valid value or clock is missing; the warning condition is undetermined.",
                ),
                "coverage_resumed": (
                    "恢复有效采样；没有将缺失区间解释为预警解除。",
                    "Valid sampling resumed; the missing interval was not treated as a clearance.",
                ),
            }[notice]
            facts = {
                "rule": rule.model_dump(mode="json"),
                "value": value,
                "clock": metadata[rule.metric]["clock"],
                "sample_time_us": str(now) if now is not None else None,
                "since_us": state.get("since_us"),
                "sampled_only": True,
            }
            entries.append(
                _entry("warning", notice, dict(zip(("zh", "en"), text, strict=True)), facts, source, rule_id=rule.id)
            )
            if notice in ("triggered", "reminder"):
                state["last_notice_us"] = str(now)
        states[rule.id] = state
    return entries, states
