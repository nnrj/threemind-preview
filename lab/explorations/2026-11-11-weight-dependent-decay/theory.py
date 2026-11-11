"""Explicit scalar calculations and same-backend engineering cost, not cultivation."""

import json
import math
import statistics
import time
from pathlib import Path
import argparse
from candidate import MIN_RATE, EXTRA_RATES, MATCH_WEIGHT, RULES, exact_weight, create
from threemind_core import Stimulus


def lifetime(w, lo, extra, threshold=0.008):
    if w <= threshold:
        return 0.0
    a = lo + extra
    return math.log(w * (a - extra * threshold) / (threshold * (a - extra * w))) / a


def measurements():
    weights = (0.008, 0.035, 0.08, 0.2, 0.5, 0.8, 0.9, 0.99, 1.0)
    rows = []
    for speed, extra in EXTRA_RATES.items():
        for w in weights:
            rows.append(
                dict(
                    speed=speed,
                    weight=w,
                    fraction30=exact_weight(w, 30, MIN_RATE, extra) / w,
                    seconds_to_delete=lifetime(w, MIN_RATE, extra),
                    matched_seconds_to_delete=max(0.0, math.log(w / 0.008) / (MIN_RATE + extra * (1 - MATCH_WEIGHT))),
                )
            )

    # r=extra/(minimum+extra). The lifetime-ratio maximum is at r -> 1.
    def logodds(w):
        return math.log(w / (1 - w))

    ratios = {
        str(w): (logodds(w) - logodds(0.008)) / (logodds(0.035) - logodds(0.008)) for w in (0.2, 0.5, 0.8, 0.9, 0.99)
    }
    costs = []
    for rule in RULES:
        for repeat in range(3):
            x = create(98765430 + repeat, rule)
            for i in range(32):
                x.inject(Stimulus(0, ((2 * i + 1, 0.4), (2 * i + 2, 0.4)), 1.0))
            x.advance_to(0)
            t = time.perf_counter()
            x.advance_to(1_000_000)
            wall = time.perf_counter() - t
            before = x.capture_state().digest
            t = time.perf_counter()
            state = x.capture_state().to_dict()
            save = time.perf_counter() - t
            assert before == x.capture_state().digest
            costs.append(
                dict(
                    rule=rule,
                    repeat=repeat,
                    advance_wall_seconds=wall,
                    capture_wall_seconds=save,
                    nodes=len(state["nodes"]),
                    edges=len(state["edges"]),
                    internal_seconds=1,
                )
            )
    return dict(
        schema="threemind.r48-theory-engineering/1",
        minimum_rate=MIN_RATE,
        extra_rates=EXTRA_RATES,
        scalar_rows=rows,
        maximum_lifetime_ratio_relative_to_weight_0035=ratios,
        engine_measurements=costs,
        median_seconds={
            r: statistics.median(x["advance_wall_seconds"] for x in costs if x["rule"] == r) for r in RULES
        },
        scope="Analytic no-reinforcement solutions and Python engineering graphs; not learned subjects or days-long cultivation.",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    r = measurements()
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(r, f, indent=2)
    print(json.dumps(r))
