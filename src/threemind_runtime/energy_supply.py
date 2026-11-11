"""An explicit simulated external reservoir. It never filters sensory inputs."""

import math
from copy import deepcopy
from dataclasses import asdict, dataclass, field

from threemind_core.energy import supply_payload
from threemind_core.spec import timestamp


def parameter(default, label, unit, hint, **bounds):
    return field(default=default, metadata={"label": label, "unit": unit, "hint": hint, "immutable": False, **bounds})


@dataclass(frozen=True)
class EnergySupplyConfig:
    enabled: bool = parameter(
        False, "启用外部能量供给", "", "默认关闭。模拟外部储库通过时间戳资源事件供给；内核能量关闭时不供给。"
    )
    rate_per_s: float = parameter(
        0.04,
        "能量供给速率",
        "实验单位／秒",
        "按模拟时间提供有限速率供给，不由宿主 CPU 速度决定。",
        minimum=0,
        maximum=1e12,
    )
    interval_us: int = parameter(
        100000,
        "供给事件间隔",
        "μs",
        "第一次供给位于启动后的一个间隔；暂停后保留已排队事件及周期。",
        minimum=1000,
        maximum=10000000,
    )
    total_supply_limit: float | None = parameter(
        None,
        "外部储库总供给上限",
        "实验单位",
        "留空不限，0 不供给；只计模型实际接受量，暂停、开关和修改参数不补回额度。",
        minimum=0,
        maximum=1e12,
        nullable=True,
    )

    def __post_init__(self):
        if (
            type(self.enabled) is not bool
            or type(self.interval_us) is not int
            or not 1000 <= self.interval_us <= 10000000
        ):
            raise ValueError("invalid external supply switch or interval")
        for key in ("rate_per_s", "total_supply_limit"):
            value = getattr(self, key)
            if value is None and key == "total_supply_limit":
                continue
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
                or not 0 <= value <= 1e12
            ):
                raise ValueError("invalid external supply rate or total limit")
            object.__setattr__(self, key, float(value))
        if self.rate_per_s * (self.interval_us / 1e6) > 1e12:
            raise ValueError("one energy offer exceeds the supported supply amount")


class EnergySupplier:
    def __init__(self, config: EnergySupplyConfig, engine, state=None):
        self.config = config
        self.accepted_total = 0.0
        self.offered_total = 0.0
        self.sequence = 0
        self.pending = None
        self.next_us = engine.time_us + config.interval_us
        if state is not None:
            if (
                not isinstance(state, dict)
                or set(state)
                != {"schema", "configuration", "accepted_total", "offered_total", "sequence", "pending", "next_us"}
                or state["schema"] != "threemind.external-energy/1"
            ):
                raise ValueError("invalid external energy provider state")
            old = EnergySupplyConfig(**state["configuration"])
            for key in ("accepted_total", "offered_total"):
                value = state[key]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (float, int))
                    or not math.isfinite(value)
                    or value < 0
                ):
                    raise ValueError("invalid external energy total")
                setattr(self, key, float(value))
            if type(state["sequence"]) is not int or not 0 <= state["sequence"] < 2**63:
                raise ValueError("invalid external energy sequence")
            self.sequence = state["sequence"]
            self.pending = deepcopy(state["pending"])
            self.next_us = timestamp(state["next_us"])
            if (
                not math.isclose(self.accepted_total, self.offered_total, rel_tol=1e-12)
                and self.accepted_total > self.offered_total
            ):
                raise ValueError("external energy acceptance exceeds offers")
            if self.pending is not None:
                if (
                    not isinstance(self.pending, dict)
                    or set(self.pending) != {"event_id", "time_us", "amount", "sequence"}
                    or type(self.pending["event_id"]) is not int
                    or self.pending["event_id"] < 0
                    or type(self.pending["sequence"]) is not int
                    or self.pending["sequence"] != self.sequence
                    or self.sequence == 0
                    or self.pending["time_us"] != str(self.next_us)
                ):
                    raise ValueError("invalid external energy pending event")
                supply_payload(self.pending["amount"])
                events = engine.capture_state().to_dict()["queue"]
                if not any(
                    q["id"] == self.pending["event_id"]
                    and q["kind"] == "energy"
                    and q["time_us"] == self.pending["time_us"]
                    and q["payload"]["amount"] == self.pending["amount"]
                    and q["payload"]["source"] == "simulated-energy-reservoir"
                    for q in events
                ):
                    raise ValueError("external energy pending event differs from model queue")
            elif self.next_us < engine.time_us or config != old:
                self.next_us = engine.time_us + config.interval_us

    @property
    def deadline(self):
        return int(self.pending["time_us"]) if self.pending else None

    def prepare(self, engine, *, source_enabled=True):
        if self.pending or not source_enabled or not self.config.enabled or not engine.config.energy_simulation_enabled:
            return None
        amount = self.config.rate_per_s * (self.config.interval_us / 1e6)
        if self.config.total_supply_limit is not None:
            amount = min(amount, max(0.0, self.config.total_supply_limit - self.accepted_total))
        if amount <= 0:
            return None
        if self.sequence >= 2**63 - 1:
            raise ValueError("external energy event sequence exhausted")
        if self.next_us < engine.time_us:
            self.next_us = engine.time_us + self.config.interval_us
        event_id = engine.supply_energy(amount, time_us=self.next_us, source="simulated-energy-reservoir")
        self.sequence += 1
        self.offered_total += amount
        self.pending = {"event_id": event_id, "time_us": str(self.next_us), "amount": amount, "sequence": self.sequence}
        return deepcopy(self.pending) | {
            "configuration": asdict(self.config),
            "scope": "explicit-simulated-external-reservoir",
        }

    def delivered(self, event):
        if not self.pending or event["event_id"] != self.pending["event_id"]:
            return None
        if event["kind"] != "energy" or event["time_us"] != self.pending["time_us"]:
            raise ValueError("external energy delivery identity differs")
        self.accepted_total += event["payload"]["accepted"]
        previous = self.pending
        self.pending = None
        self.next_us = int(event["time_us"]) + self.config.interval_us
        return {
            "sequence": previous["sequence"],
            "accepted_total": self.accepted_total,
            "offered_total": self.offered_total,
        }

    def capture(self):
        return {
            "schema": "threemind.external-energy/1",
            "configuration": asdict(self.config),
            "accepted_total": self.accepted_total,
            "offered_total": self.offered_total,
            "sequence": self.sequence,
            "pending": deepcopy(self.pending),
            "next_us": str(self.next_us),
        }
