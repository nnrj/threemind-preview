"""Read-only, explicitly scoped response analysis over complete saved samples."""

from __future__ import annotations

import math
from collections import deque

from .process_observation import process_observation, validate_series

VERSION = "threemind.target-observation/1"


def target_observation(
    series,
    nodes,
    node_ids,
    *,
    expected_interval_us,
    epsilon=1e-12,
    settle_us=800000,
    pattern_drift_max=0.08,
    amplitude_drift_max=0.12,
    response_floor=1e-8,
):
    """Keep presence, local pattern stability and local steady activity separate.

    Sparse zeros are interpreted only in complete saved samples. Unknown target
    identities are rejected. Global classifications and the source are untouched.
    """
    validate_series(series)
    if not isinstance(node_ids, list) or not 1 <= len(node_ids) <= 256:
        raise ValueError("choose 1 to 256 explicit node IDs")
    if any(type(n) is not int or n < 0 for n in node_ids) or len(set(node_ids)) != len(node_ids):
        raise ValueError("target node IDs must be distinct nonnegative integers")
    if type(settle_us) is not int or not 1 <= settle_us <= 60000000:
        raise ValueError("local stability window must be 1 to 60000000 microseconds")
    for value in (epsilon, pattern_drift_max, amplitude_drift_max, response_floor):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("observation tolerances must be finite within [0,1]")
    if type(expected_interval_us) is not int or expected_interval_us < 1:
        raise ValueError("expected sample interval must be positive integer microseconds")
    known = {int(n["node_id"]) for n in nodes}
    known.update(int(k) for sample in series for k in sample["activation_vector"])
    if missing := set(node_ids) - known:
        raise ValueError(f"target identities not present in this record: {sorted(missing)}")
    keys = {str(n) for n in node_ids}
    selected = [
        {"time_us": s["time_us"], "activation_vector": {k: v for k, v in s["activation_vector"].items() if k in keys}}
        for s in series
    ]
    selected_nodes = [n for n in nodes if str(n["node_id"]) in keys]
    process, measurements = process_observation(
        selected,
        selected_nodes,
        epsilon=epsilon,
        expected_interval_us=expected_interval_us,
    )
    # A known inactive node still has a measured zero, distinct from an unknown ID.
    missing_rows = keys - measurements.keys()
    if missing_rows and selected:
        _, measurements = process_observation(
            selected,
            selected_nodes + [{"node_id": int(k), "baseline_mean": 0} for k in missing_rows],
            epsilon=epsilon,
            expected_interval_us=expected_interval_us,
        )
    tail, work = deque(), 0
    first_pattern = first_steady = None
    last = {"status": "not_observed", "pattern_stable": None, "amplitude_stable": None}
    for index, sample in enumerate(selected):
        at = int(sample["time_us"])
        if tail and at - int(tail[-1]["time_us"]) > expected_interval_us:
            tail.clear()  # A missing interval cannot establish continuous stability.
        tail.append(sample)
        while len(tail) > 1 and int(tail[1]["time_us"]) <= at - settle_us:
            tail.popleft()
        span = at - int(tail[0]["time_us"])
        total = math.fsum(sample["activation_vector"].values())
        last = {"status": "insufficient_span", "pattern_stable": None, "amplitude_stable": None}
        if total <= response_floor:
            last["status"] = "below_activity_floor"
            continue
        if span < settle_us:
            continue
        # Once both first decisions are known, only the terminal tail is needed.
        if first_steady is not None and index != len(selected) - 1:
            continue
        work += len(tail) * len(keys)
        if work > 5000000:
            raise ValueError("local analysis comparison budget exceeded; use a shorter observation/window")
        totals = [math.fsum(s["activation_vector"].values()) for s in tail]
        if min(totals) <= response_floor:
            last["status"] = "activity_interrupted"
            continue
        drift = max(
            0.5
            * math.fsum(
                abs(s["activation_vector"].get(k, 0) / amount - sample["activation_vector"].get(k, 0) / total)
                for k in keys
            )
            for s, amount in zip(tail, totals)
        )
        amplitude = (max(totals) - min(totals)) / max(totals)
        pattern_ok, amplitude_ok = drift <= pattern_drift_max, amplitude <= amplitude_drift_max
        last = {
            "status": "local_steady" if pattern_ok and amplitude_ok else "local_pattern" if pattern_ok else "changing",
            "pattern_stable": pattern_ok,
            "amplitude_stable": amplitude_ok,
            "maximum_pattern_distance": drift,
            "relative_amplitude_span": amplitude,
            "start_us": str(tail[0]["time_us"]),
            "end_us": str(at),
        }
        decision = {
            "time_us": str(at),
            "tail": dict(last),
            "ranking": [
                {"node_id": int(k), "activation": sample["activation_vector"].get(k, 0)}
                for k in sorted(keys, key=lambda k: (-sample["activation_vector"].get(k, 0), int(k)))
            ],
        }
        if pattern_ok and first_pattern is None:
            first_pattern = decision
        if pattern_ok and amplitude_ok and first_steady is None:
            first_steady = decision
    for key, row in measurements.items():
        row["terminal_activation"] = selected[-1]["activation_vector"].get(key, 0) if selected else None
    return {
        "schema": VERSION,
        "configuration": {
            "node_ids": sorted(node_ids),
            "epsilon": epsilon,
            "settle_us": settle_us,
            "pattern_drift_max": pattern_drift_max,
            "amplitude_drift_max": amplitude_drift_max,
            "response_floor": response_floor,
            "expected_interval_us": expected_interval_us,
        },
        "process": process,
        "nodes": [{"node_id": int(k), **row} for k, row in sorted(measurements.items(), key=lambda kv: int(kv[0]))],
        "first_pattern_convergence": first_pattern,
        "first_steady_convergence": first_steady,
        "terminal_local_state": last,
        "scope": "explicit observer-selected nodes; complete global evidence remains unchanged",
        "selection": "not automatically preregistered; record the selection rule before confirmatory testing",
        "causal_attribution": "response and local stability are descriptive; require matched controls for causation",
    }
