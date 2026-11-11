"""Explicit environmental input selection; default transparent and read-only to topology."""

import heapq
import math
import sys
from copy import deepcopy
from dataclasses import dataclass, field

from .spec import MAX_TIME, Config, Stimulus, timestamp

COUNTERS = ("evaluated_frames", "considered_channels", "passed_channels", "suppressed_channels")
MAX_MODULATORS = 64


def modulation_payload(
    *, source="external-modulator", gain=1.0, budget_multiplier=1.0, competition_enabled=False, ttl_us=30_000_000
):
    if not isinstance(source, str) or not 1 <= len(source) <= 128:
        raise ValueError("invalid modulation source")
    if type(competition_enabled) is not bool or type(ttl_us) is not int or not 1 <= ttl_us <= 10**12:
        raise ValueError("invalid modulation competition switch or duration")
    for value in (gain, budget_multiplier):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 2
        ):
            raise ValueError("modulation gain and budget multiplier must lie in [0, 2]")
    return {
        "source": source,
        "gain": float(gain),
        "budget_multiplier": float(budget_multiplier),
        "competition_enabled": competition_enabled,
        "ttl_us": ttl_us,
    }


@dataclass(slots=True)
class Attention:
    since_us: str = "0"
    evaluated_frames: str = "0"
    considered_channels: str = "0"
    passed_channels: str = "0"
    suppressed_channels: str = "0"
    counter_overflowed: bool = False
    modulators: dict = field(default_factory=dict)

    def increment(self, key, amount):
        total = int(getattr(self, key)) + amount
        if total > MAX_TIME:
            total = MAX_TIME
            self.counter_overflowed = True
        setattr(self, key, str(total))

    def update(self, payload, when):
        modulation_payload(**payload)
        self.modulators = {key: value for key, value in self.modulators.items() if int(value["expires_us"]) > when}
        source = payload["source"]
        if source not in self.modulators and len(self.modulators) >= MAX_MODULATORS:
            return {"status": "rejected", "reason": "active_modulator_limit"}
        expires = when + payload["ttl_us"]
        if expires > MAX_TIME:
            return {"status": "rejected", "reason": "expiry_out_of_range"}
        self.modulators[source] = deepcopy(payload) | {"updated_us": str(when), "expires_us": str(expires)}
        return {"status": "applied", "expires_us": str(expires)}

    def effective(self, when, config: Config):
        gain = budget = 1.0
        competition = config.attention_competition_enabled
        active = []
        for source, value in sorted(self.modulators.items()):
            if when >= int(value["expires_us"]):
                continue
            gain *= value["gain"]
            budget *= value["budget_multiplier"]
            competition = competition or value["competition_enabled"]
            active.append(source)
        gain, budget = min(8.0, gain), min(8.0, budget)
        return {
            "gain": gain,
            "budget_multiplier": budget,
            "competition_enabled": competition,
            "effective_budget": min(100000, int(config.attention_budget * budget)) if competition else None,
            "sources": active,
        }

    def select(self, stimulus: Stimulus, config: Config):
        effective = self.effective(stimulus.time_us, config)
        if not effective["competition_enabled"] and not effective["sources"]:
            return stimulus, None
        count = len(stimulus.channels)
        limit = effective["effective_budget"]
        if effective["gain"] == 0:
            channels = ()
        elif not stimulus.bypass_attention and limit is not None and limit < count:
            # Uniform frame intensity/gain cannot change ordering. Comparing raw
            # amplitude avoids overflow, and ties preserve adapter input order.
            chosen = set(heapq.nsmallest(limit, range(count), key=lambda i: (-stimulus.channels[i][1], i)))
            channels = tuple(value for i, value in enumerate(stimulus.channels) if i in chosen)
        else:
            channels = stimulus.channels
        intensity = stimulus.intensity * effective["gain"]
        limited = not math.isfinite(intensity)
        if limited:
            intensity = sys.float_info.max
        passed = Stimulus(stimulus.time_us, channels, intensity, stimulus.bypass_attention)
        for key, amount in zip(COUNTERS, (1, count, len(channels), count - len(channels)), strict=True):
            self.increment(key, amount)
        return passed, {
            "schema": "threemind.input-selection/1",
            "scope": "one-timestamped-sensory-frame",
            "raw_channels": count,
            "passed_channels": len(channels),
            "suppressed_channels": count - len(channels),
            **effective,
            "intensity_saturated": limited,
            "effective_stimulus": passed.to_dict(),
            **({"competition_bypassed": True} if stimulus.bypass_attention else {}),
        }

    def to_dict(self):
        return {
            "schema": "threemind.attention/1",
            "since_us": self.since_us,
            **{k: getattr(self, k) for k in COUNTERS},
            "counter_overflowed": self.counter_overflowed,
            "modulators": [deepcopy(self.modulators[k]) for k in sorted(self.modulators)],
        }

    @classmethod
    def restore(cls, state, when):
        if (
            not isinstance(state, dict)
            or set(state) != {"schema", "since_us", *COUNTERS, "counter_overflowed", "modulators"}
            or state["schema"] != "threemind.attention/1"
        ):
            raise ValueError("invalid attention ledger schema")
        for key in ("since_us", *COUNTERS):
            value = state[key]
            if not isinstance(value, str) or str(timestamp(value)) != value:
                raise ValueError("invalid attention counter or timestamp")
        if int(state["since_us"]) > when or type(state["counter_overflowed"]) is not bool:
            raise ValueError("invalid attention epoch or counter flag")
        values = state["modulators"]
        if not isinstance(values, list) or len(values) > MAX_MODULATORS:
            raise ValueError("invalid modulation collection")
        result = cls(**{k: state[k] for k in ("since_us", *COUNTERS, "counter_overflowed")})
        previous = None
        for item in values:
            if not isinstance(item, dict) or set(item) != {
                "source",
                "gain",
                "budget_multiplier",
                "competition_enabled",
                "ttl_us",
                "updated_us",
                "expires_us",
            }:
                raise ValueError("invalid saved input modulation")
            modulation_payload(**{k: v for k, v in item.items() if k not in ("updated_us", "expires_us")})
            if previous is not None and previous >= item["source"]:
                raise ValueError("modulation sources must be in canonical order")
            previous = item["source"]
            if any(
                not isinstance(item[k], str) or str(timestamp(item[k])) != item[k] for k in ("updated_us", "expires_us")
            ):
                raise ValueError("invalid modulation timestamp")
            if (
                item["source"] in result.modulators
                or not int(state["since_us"]) <= int(item["updated_us"]) <= when
                or int(item["expires_us"]) != int(item["updated_us"]) + item["ttl_us"]
            ):
                raise ValueError("invalid modulation identity or phase")
            result.modulators[item["source"]] = deepcopy(item)
        if not state["counter_overflowed"] and int(state["considered_channels"]) != int(state["passed_channels"]) + int(
            state["suppressed_channels"]
        ):
            raise ValueError("attention counts do not balance")
        return result
