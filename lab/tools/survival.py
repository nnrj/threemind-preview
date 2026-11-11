"""External task food and survivor selection. These tools never edit Core state.

Quantities come from a physical task's measurement. This module does not infer
success from words, assign correct actions, or clear activation to force death.
"""

from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FoodConfig:
    energy_per_unit: float = 10100.0
    interval_us: int = 1000000

    def __post_init__(self):
        if isinstance(self.energy_per_unit, bool) or not isinstance(self.energy_per_unit, (int, float)):
            raise ValueError("energy_per_unit must be numeric")  # noqa: TRY004 -- unified protocol validation contract
        if not math.isfinite(self.energy_per_unit) or not 0 <= self.energy_per_unit <= 1e12:
            raise ValueError("energy_per_unit outside [0, 1e12]")
        if type(self.interval_us) is not int or not 1000 <= self.interval_us <= 60000000:
            raise ValueError("interval_us outside [1000, 60000000]")


class TaskFood:
    """Monotonic, idempotent outcome receipts and explicitly timed energy offers.

    The task owns deduplication of physical objects (e.g. each grain per batch).
    This account additionally deduplicates retries of the latest task receipt.
    A state snapshot must be saved together with Core's pending event queue.
    """

    schema = "threemind.task-food/1"

    def __init__(self, config: FoodConfig, *, start_us=0, state=None):
        if type(start_us) is not int or start_us < 0:
            raise ValueError("nonnegative integer clock required")
        self.config = config
        self.pending = 0.0
        self.units = 0.0
        self.offered = 0.0
        self.next_us = start_us + config.interval_us
        self.last_receipt = None
        self.last_offer = None
        if state is not None:
            if state.get("schema") != self.schema or state.get("configuration") != asdict(config):
                raise ValueError("food configuration differs from continuation")
            expected = {
                "schema",
                "configuration",
                "pending",
                "units",
                "offered",
                "next_us",
                "last_receipt",
                "last_offer",
            }
            if set(state) != expected:
                raise ValueError("incomplete food state")
            for key in ("pending", "units", "offered"):
                value = state[key]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0
                ):
                    raise ValueError("invalid food balance")
                setattr(self, key, float(value))
            if type(state["next_us"]) is not int or state["next_us"] < 0:
                raise ValueError("invalid food deadline")
            if (
                not math.isfinite(self.pending + self.offered)
                or not math.isfinite(self.units * config.energy_per_unit)
                or not math.isclose(
                    self.pending + self.offered, self.units * config.energy_per_unit, rel_tol=1e-10, abs_tol=1e-8
                )
            ):
                raise ValueError("food receipt balance does not close")
            self.next_us = state["next_us"]
            self.last_receipt = copy.deepcopy(state["last_receipt"])
            self.last_offer = copy.deepcopy(state["last_offer"])
            if self.last_receipt is not None:
                self._receipt(**self.last_receipt)

    @staticmethod
    def _receipt(sequence, time_us, units):
        if type(sequence) is not int or sequence < 0 or type(time_us) is not int or time_us < 0:
            raise ValueError("nonnegative receipt sequence and clock required")
        if isinstance(units, bool) or not isinstance(units, (float, int)) or not math.isfinite(units) or units < 0:
            raise ValueError("nonnegative finite measured units required")
        return {"sequence": sequence, "time_us": time_us, "units": float(units)}

    def credit(self, *, sequence, time_us, units):
        receipt = self._receipt(sequence, time_us, units)
        if self.last_receipt:
            if sequence == self.last_receipt["sequence"] and receipt == self.last_receipt:
                return False
            if sequence <= self.last_receipt["sequence"] or time_us < self.last_receipt["time_us"]:
                raise ValueError("changed, stale or out-of-order outcome receipt")
        amount = units * self.config.energy_per_unit
        if not math.isfinite(amount) or self.pending + amount > 1e12:
            raise ValueError("pending food exceeds one supported energy offer")
        self.pending += amount
        self.units += units
        self.last_receipt = receipt
        return True

    def settle(self, engine, time_us):
        if type(time_us) is not int or time_us < engine.time_us:
            raise ValueError("food cannot be delivered in Core's past")
        if time_us < self.next_us:
            return None
        if self.last_receipt and self.last_receipt["time_us"] > time_us:
            raise ValueError("cannot spend future physical outcomes")
        if engine.life == "dead":
            raise ValueError("food does not resurrect a dead individual")
        offer = None
        if self.pending:
            if not engine.config.energy_simulation_enabled:
                raise ValueError("task food requires finite Core energy accounting")
            offer = {"time_us": time_us, "amount": self.pending, "source": "physical-task-food/1"}
            offer["event_id"] = engine.supply_energy(self.pending, time_us=time_us, source=offer["source"])
            self.offered += self.pending
            self.pending = 0.0
            self.last_offer = offer
        # Missed empty intervals do not manufacture back-paid energy.
        self.next_us += (1 + (time_us - self.next_us) // self.config.interval_us) * self.config.interval_us
        return copy.deepcopy(offer)

    def capture(self):
        return {
            "schema": self.schema,
            "configuration": asdict(self.config),
            "pending": self.pending,
            "units": self.units,
            "offered": self.offered,
            "next_us": self.next_us,
            "last_receipt": copy.deepcopy(self.last_receipt),
            "last_offer": copy.deepcopy(self.last_offer),
        }


def select_survivors(candidates, *, parent_count, offspring_count):
    """Rank only verified horizon survivors; all other living records stay saved.

    Caller supplies measurements from saved Core images, not a manually assigned
    'success'. Censored/failed cases are never silently promoted into parents.
    The returned plan creates no children and mutates no parent.
    """
    if type(parent_count) is not int or not 1 <= parent_count <= 64:
        raise ValueError("parent_count must be in [1,64]")
    if type(offspring_count) is not int or not 1 <= offspring_count <= 256:
        raise ValueError("offspring_count must be in [1,256]")
    if not candidates:
        raise ValueError("cannot declare extinction from an absent cohort")
    identities = [c["id"] for c in candidates]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate candidate identity")
    for c in candidates:
        e = c["energy_reserve"]
        if isinstance(e, bool) or not isinstance(e, (int, float)) or not math.isfinite(e) or e < 0:
            raise ValueError("invalid measured energy reserve")
        if c["life"] not in ("waiting", "active", "dead"):
            raise ValueError("unknown Core lifecycle")
        if type(c["horizon_reached"]) is not bool or type(c["failed"]) is not bool:
            raise ValueError("explicit horizon and failure observations required")
    living = sorted(
        (c for c in candidates if c["life"] == "active" and c["horizon_reached"] and not c["failed"]),
        key=lambda c: (-c["energy_reserve"], c["id"]),
    )
    parents = living[:parent_count]
    return {
        "schema": "threemind.survivor-selection/1",
        "extinct": not any(c["life"] != "dead" for c in candidates),
        "no_eligible_parent": not parents,
        "parents": [c["id"] for c in parents],
        "paused_alive": [c["id"] for c in candidates if c["life"] != "dead" and c not in parents],
        "offspring": [
            {"index": i, "parent": parents[i % len(parents)]["id"]} for i in range(offspring_count) if parents
        ],
        "criterion": "remaining energy among active horizon survivors; ties by stable identity",
    }
