"""Optional finite external resource ledger; never a sensory or semantic source."""

import math
import sys
from dataclasses import asdict, dataclass

from .spec import Config, timestamp

ENERGY_TOTALS = (
    "offered_total",
    "supplied_total",
    "consumed_direct",
    "consumed_associative",
    "consumed_inhibition",
    "consumed_maintenance",
    "unserved_total",
    "discarded_total",
)


def supply_payload(amount, source="external-energy") -> dict:
    if (
        isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or not math.isfinite(amount)
        or not 0 <= amount <= 1e12
    ):
        raise ValueError("energy supply must be a finite amount in [0, 1e12]")
    if not isinstance(source, str) or not 1 <= len(source) <= 128:
        raise ValueError("invalid energy source metadata")
    return {"amount": float(amount), "source": source}


@dataclass(slots=True)
class Energy:
    since_us: str = "0"
    reserve: float = 1.0
    initial_total: float = 1.0
    offered_total: float = 0.0
    supplied_total: float = 0.0
    consumed_direct: float = 0.0
    consumed_associative: float = 0.0
    consumed_inhibition: float = 0.0
    consumed_maintenance: float = 0.0
    unserved_total: float = 0.0
    discarded_total: float = 0.0
    last_settlement_us: str = "0"
    last_maintenance_deficit: float = 0.0
    starved_since_us: str | None = None
    death_us: str | None = None
    counter_overflowed: bool = False

    @classmethod
    def initial(cls, config: Config, when=0):
        reserve = min(config.energy_initial_reserve, config.energy_capacity)
        return cls(
            since_us=str(when),
            reserve=reserve,
            initial_total=config.energy_initial_reserve,
            discarded_total=config.energy_initial_reserve - reserve,
            last_settlement_us=str(when),
        )

    def _add(self, name: str, amount: float):
        value = getattr(self, name) + amount
        if not math.isfinite(value):
            value = sys.float_info.max
            self.counter_overflowed = True
        setattr(self, name, value)

    def afford(self, requested: float, cost: float, kind: str) -> float:
        if requested <= 0 or cost <= 0:
            return requested
        accepted = min(requested, self.reserve / cost)
        consumed = min(self.reserve, accepted * cost)
        self.reserve = max(0.0, self.reserve - consumed)
        self._add(f"consumed_{kind}", consumed)
        self._add("unserved_total", max(0.0, requested * cost - consumed))
        return accepted

    def supply(self, amount: float, capacity: float, enabled: bool):
        self._add("offered_total", amount)
        accepted = min(amount, max(0.0, capacity - self.reserve)) if enabled else 0.0
        self.reserve += accepted
        self._add("supplied_total", accepted)
        return {
            "offered": amount,
            "accepted": accepted,
            "reserve": self.reserve,
            "status": "accepted" if enabled else "disabled",
        }

    def resize(self, capacity: float):
        discarded = max(0.0, self.reserve - capacity)
        self.reserve = min(self.reserve, capacity)
        self._add("discarded_total", discarded)

    def maintain(self, when: int, duration_us: int, nodes: int, edges: int, config: Config) -> float:
        if not (config.energy_simulation_enabled and config.irreversible_energy_death_enabled):
            return 0.0
        required = (
            duration_us
            / 1e6
            * (nodes * config.energy_maintenance_cost_per_node + edges * config.energy_maintenance_cost_per_edge)
        )
        paid = self.afford(required, 1.0, "maintenance")
        deficit = max(0.0, 1.0 - paid / required) if required > 0 else 0.0
        erosion_seconds = duration_us / 1e6 * deficit
        self.last_settlement_us = str(when)
        self.last_maintenance_deficit = deficit
        return erosion_seconds

    def to_dict(self):
        return {"schema": "threemind.energy/1", **asdict(self)}

    @classmethod
    def restore(cls, state: dict, when: int, config: Config):
        if (
            not isinstance(state, dict)
            or set(state) != set(cls.__dataclass_fields__) | {"schema"}
            or state["schema"] != "threemind.energy/1"
        ):
            raise ValueError("invalid energy ledger schema")
        times = ("since_us", "last_settlement_us", "starved_since_us", "death_us")
        for key in times:
            value = state[key]
            if value is None and key in ("starved_since_us", "death_us"):
                continue
            if not isinstance(value, str) or str(timestamp(value)) != value or int(value) > when:
                raise ValueError("invalid energy timestamp")
        if int(state["last_settlement_us"]) < int(state["since_us"]):
            raise ValueError("invalid maintenance accounting phase")
        if type(state["counter_overflowed"]) is not bool:
            raise ValueError("invalid energy counter flag")
        for key in set(cls.__dataclass_fields__) - set(times) - {"counter_overflowed"}:
            value = state[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("invalid energy accounting value")
        if state["reserve"] > config.energy_capacity or state["last_maintenance_deficit"] > 1:
            raise ValueError("invalid energy reserve or maintenance deficit")
        if state["starved_since_us"] is not None and not (
            config.energy_simulation_enabled and config.irreversible_energy_death_enabled and state["reserve"] == 0
        ):
            raise ValueError("starvation requires enabled zero-reserve accounting")
        return cls(
            **{
                k: float(v) if k not in times and k != "counter_overflowed" else v
                for k, v in state.items()
                if k != "schema"
            }
        )
