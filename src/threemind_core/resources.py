"""State of explicit scientific resource limits, independent of the host CPU."""

from dataclasses import asdict, dataclass

from .spec import MAX_TIME, timestamp

COUNTERS = (
    "node_capacity_rejections",
    "edge_capacity_rejections",
    "adaptation_budget_skips",
    "propagation_budget_skips",
)


@dataclass(slots=True)
class Resources:
    since_us: str = "0"
    adaptation_period_us: str = "0"
    adaptations_used: int = 0
    node_capacity_rejections: str = "0"
    edge_capacity_rejections: str = "0"
    adaptation_budget_skips: str = "0"
    propagation_budget_skips: str = "0"
    counter_overflowed: bool = False

    def increment(self, key: str, amount: int = 1) -> None:
        value = int(getattr(self, key)) + amount
        if value > MAX_TIME:
            value = MAX_TIME
            self.counter_overflowed = True
        setattr(self, key, str(value))

    def available_adaptations(self, when: int, step: int, limit: int) -> int:
        used = self.adaptations_used if int(self.adaptation_period_us) == when // step * step else 0
        return max(0, limit - used)

    def use_adaptation(self, when: int, step: int) -> None:
        period = when // step * step
        if int(self.adaptation_period_us) != period:
            self.adaptation_period_us = str(period)
            self.adaptations_used = 0
        self.adaptations_used += 1

    def to_dict(self) -> dict:
        return {"schema": "threemind.resources/1", **asdict(self)}

    @classmethod
    def restore(cls, state: dict, time_us: int, step_us: int):
        required = set(cls.__dataclass_fields__) | {"schema"}
        if not isinstance(state, dict) or set(state) != required or state["schema"] != "threemind.resources/1":
            raise ValueError("invalid resource accounting state")
        if type(state["adaptations_used"]) is not int or not 0 <= state["adaptations_used"] <= 2**53 - 1:
            raise ValueError("invalid adaptation usage")
        if type(state["counter_overflowed"]) is not bool:
            raise ValueError("invalid resource counter overflow flag")
        for key in ("since_us", "adaptation_period_us", *COUNTERS):
            if not isinstance(state[key], str) or str(timestamp(state[key])) != state[key]:
                raise ValueError("resource times and counts must be canonical decimal strings")
        if int(state["since_us"]) > time_us or int(state["adaptation_period_us"]) > time_us:
            raise ValueError("resource accounting is in the future")
        if int(state["adaptation_period_us"]) % step_us:
            raise ValueError("resource accounting does not match the numerical lattice")
        return cls(**{k: v for k, v in state.items() if k != "schema"})
