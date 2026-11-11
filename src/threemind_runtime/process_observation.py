"""Versioned measurement of complete sampled activity, without a Core dependency.

Positive and negative changes are relative to a measured baseline, not causal
attribution. Per-node peaks are never assembled into a fictitious simultaneous
state. Sparse vectors mean zero only within explicitly complete node samples.
"""

from __future__ import annotations

import math
from itertools import pairwise

VERSION = "threemind.process-observation/1"
MAX_VALUES = 2_000_000


def validate_series(series, *, max_values=MAX_VALUES):
    if not isinstance(series, list):
        raise ValueError("observation series must be an array")  # noqa: TRY004 -- public evidence validation
    if len(series) > 100000:
        raise ValueError("observation sample budget exceeded")
    prior, values = None, 0
    for sample in series:
        raw_time = sample["time_us"]
        if isinstance(raw_time, bool) or str(int(raw_time)) != str(raw_time):
            raise ValueError("timestamps must be integer microseconds")
        at = int(raw_time)
        if at < 0 or prior is not None and at <= prior:
            raise ValueError("complete samples need strictly increasing nonnegative timestamps")
        prior = at
        vector = sample.get("activation_vector")
        if not isinstance(vector, dict):
            raise ValueError("complete activation vectors are unavailable; do not infer them from top-k")  # noqa: TRY004
        values += len(vector)
        if values > max_values:
            raise ValueError("observation value budget exceeded")
        for key, value in vector.items():
            if str(int(key)) != key or int(key) < 0 or type(value) not in (int, float):
                raise ValueError("invalid node identity or measurement")
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("activation must be finite and within [0,1]")
    return series


def process_observation(
    series, nodes, *, epsilon=1e-12, delivery_end_us=None, expected_interval_us=None, max_values=MAX_VALUES
):
    """Return compact coverage plus per-node measurements in O(samples + values)."""
    validate_series(series, max_values=max_values)
    if expected_interval_us is not None:
        expected_interval_us = int(expected_interval_us)
        if expected_interval_us <= 0:
            raise ValueError("expected observation interval must be positive")
    if not math.isfinite(epsilon) or not 0 <= epsilon <= 1:
        raise ValueError("invalid observation tolerance")
    if len(nodes) > 100000:
        raise ValueError("observation node budget exceeded")
    baseline = {str(n["node_id"]): float(n.get("baseline_mean", 0)) for n in nodes}
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in baseline.values()):
        raise ValueError("invalid measured baseline")
    if not series:
        return {"schema": VERSION, "status": "not_observed", "sample_count": 0}, {}
    times = [int(s["time_us"]) for s in series]
    span = (times[-1] - times[0]) / 1e6
    rows, timeline, changes, previous = {}, [], {}, {}
    peaks = {"raw": (-1.0, 0), "increase": (-1.0, 0), "decrease": (-1.0, 0)}
    baseline_total = math.fsum(baseline.values())
    for i, sample in enumerate(series):
        at, vector = times[i], sample["activation_vector"]
        dt = (times[i + 1] - at) / 1e6 if i + 1 < len(times) else 0.0
        increase, baseline_retained = [], []
        step_increase, step_decrease, recruited, ended = [], [], 0, 0
        for key in vector.keys() | previous.keys():
            a, old = vector.get(key, 0), previous.get(key, 0)
            difference = a - old
            if i:
                step_increase.append(max(difference, 0))
                step_decrease.append(max(-difference, 0))
            event = changes.setdefault(
                key,
                {
                    "activity_episode_count": 0,
                    "sampled_active_duration_us": 0,
                    "total_activation_variation": 0.0,
                    "maximum_step_increase": 0.0,
                    "maximum_step_decrease": 0.0,
                },
            )
            if len(changes) > 100000:
                raise ValueError("observation node budget exceeded")
            if a > epsilon:
                event["sampled_active_duration_us"] += round(dt * 1e6)
                if old <= epsilon:
                    event["activity_episode_count"] += 1
                    recruited += 1
            elif old > epsilon:
                ended += 1
            if i:
                event["total_activation_variation"] += abs(difference)
                event["maximum_step_increase"] = max(event["maximum_step_increase"], difference)
                event["maximum_step_decrease"] = max(event["maximum_step_decrease"], -difference)
        for key, a in vector.items():
            if a <= 0:
                continue
            b = baseline.get(key, 0.0)
            delta = a - b
            row = rows.setdefault(
                key,
                {
                    "process_peak_activation": 0.0,
                    "process_peak_time_us": None,
                    "first_positive_us": at,
                    "last_positive_us": at,
                    "positive_samples": 0,
                    "positive_change_peak": 0.0,
                    "positive_change_integral": 0.0,
                    "negative_change_peak": 0.0,
                    "negative_change_integral": 0.0,
                    "sampled_activation_integral": 0.0,
                    "positive_change_first_us": None,
                    "positive_change_last_us": None,
                    "input_activation_integral": 0.0,
                    "post_input_activation_integral": 0.0,
                },
            )
            if a > row["process_peak_activation"]:
                row.update(process_peak_activation=a, process_peak_time_us=at)
            row["last_positive_us"] = at
            row["positive_samples"] += 1
            row["sampled_activation_integral"] += a * dt
            row["positive_change_integral"] += max(0, delta) * dt
            row["positive_change_peak"] = max(row["positive_change_peak"], delta)
            row["negative_change_peak"] = max(row["negative_change_peak"], -delta)
            if delta > epsilon:
                if row["positive_change_first_us"] is None:
                    row["positive_change_first_us"] = at
                row["positive_change_last_us"] = at
            if delivery_end_us is not None:
                input_dt = max(0, min(dt, (int(delivery_end_us) - at) / 1e6))
                row["input_activation_integral"] += a * input_dt
                row["post_input_activation_integral"] += a * (dt - input_dt)
            increase.append(max(delta, 0))
            baseline_retained.append(min(a, b))
        totals = {
            "raw": math.fsum(vector.values()),
            "increase": math.fsum(increase),
            "decrease": max(0, baseline_total - math.fsum(baseline_retained)),
        }
        for key, total in totals.items():
            if total > peaks[key][0]:
                peaks[key] = (total, i)
        old_total = math.fsum(previous.values())
        pattern_distance = (
            0.5
            * math.fsum(
                abs(vector.get(k, 0) / totals["raw"] - previous.get(k, 0) / old_total)
                for k in vector.keys() | previous.keys()
            )
            if totals["raw"] > epsilon and old_total > epsilon
            else None
        )
        timeline.append(
            {
                "time_us": str(at),
                "activation_total": totals["raw"],
                "increase_over_baseline": totals["increase"],
                "decrease_below_baseline": totals["decrease"],
                "step_increase": math.fsum(step_increase) if i else None,
                "step_decrease": math.fsum(step_decrease) if i else None,
                "pattern_distance": pattern_distance,
                "newly_active_nodes": recruited,
                "ended_nodes": ended,
            }
        )
        previous = vector
    for key in baseline.keys() | rows.keys():
        if key not in rows:
            rows[key] = {
                "process_peak_activation": 0.0,
                "process_peak_time_us": None,
                "first_positive_us": None,
                "last_positive_us": None,
                "positive_samples": 0,
                "positive_change_peak": 0.0,
                "positive_change_integral": 0.0,
                "negative_change_peak": 0.0,
                "sampled_activation_integral": 0.0,
                "positive_change_first_us": None,
                "positive_change_last_us": None,
                "input_activation_integral": 0.0,
                "post_input_activation_integral": 0.0,
            }
        row, b = rows[key], baseline.get(key, 0)
        row.update(
            changes.get(
                key,
                {
                    "activity_episode_count": 0,
                    "sampled_active_duration_us": 0,
                    "total_activation_variation": 0.0,
                    "maximum_step_increase": 0.0,
                    "maximum_step_decrease": 0.0,
                },
            )
        )
        row["negative_change_integral"] = max(
            0, b * span + row["positive_change_integral"] - row["sampled_activation_integral"]
        )
        if row["positive_samples"] < len(series):
            row["negative_change_peak"] = max(row["negative_change_peak"], b)
        row["response_peak_activation"] = series[peaks["increase"][1]]["activation_vector"].get(key, 0)
        row["response_peak_change"] = row["response_peak_activation"] - b
        if delivery_end_us is None:
            row["input_activation_integral"] = row["post_input_activation_integral"] = None
        row["activity_ended_before_window_end"] = (
            row["last_positive_us"] is not None and row["last_positive_us"] < times[-1]
        )
        # All timestamps in scientific evidence use decimal microsecond strings.
        for field, value in list(row.items()):
            if field.endswith("_us") and value is not None:
                row[field] = str(value)
    gaps = [b - a for a, b in pairwise(times)]
    return {
        "schema": VERSION,
        "status": "recorded",
        "sample_count": len(series),
        "first_sample_us": str(times[0]),
        "last_sample_us": str(times[-1]),
        "maximum_sample_gap_us": str(max(gaps)) if gaps else None,
        "expected_interval_us": str(expected_interval_us) if expected_interval_us is not None else None,
        "sampling_gap_detected": bool(gaps and expected_interval_us is not None and max(gaps) > expected_interval_us),
        "raw_activity_seen": peaks["raw"][0] > 0,
        "increase_seen": peaks["increase"][0] > epsilon,
        "decrease_seen": peaks["decrease"][0] > epsilon,
        "active_node_count": sum(r["positive_samples"] > 0 for r in rows.values()),
        "increased_node_count": sum(r["positive_change_peak"] > epsilon for r in rows.values()),
        "decreased_node_count": sum(r["negative_change_peak"] > epsilon for r in rows.values()),
        "ended_node_count": sum(r["activity_ended_before_window_end"] for r in rows.values()),
        "reactivated_node_count": sum(r["activity_episode_count"] > 1 for r in rows.values()),
        "total_activation_variation": math.fsum(r["total_activation_variation"] for r in rows.values()),
        "maximum_pattern_distance": max(
            (r["pattern_distance"] for r in timeline if r["pattern_distance"] is not None), default=None
        ),
        "timeline": timeline,
        "peaks": {k: {"time_us": str(times[i]), "total": v} for k, (v, i) in peaks.items()},
        "epsilon": epsilon,
        "causal_attribution": "not-established",
        "baseline": "measured pre-window mean; decreases are not proof of inhibitory causation",
        "integration": "left-hold over recorded intervals; no extrapolation past the last sample",
        "sampling": "complete node samples, not continuous coverage between samples",
    }, rows


def compare_observations(left, right, *, relative=False, epsilon=1e-12):
    """Compare all measured nodes at exactly matched times, never interpolate."""
    validate_series(left)
    validate_series(right)
    if not math.isfinite(epsilon) or not 0 <= epsilon <= 1:
        raise ValueError("invalid observation tolerance")

    def indexed(series):
        origin = int(series[0]["time_us"]) if relative and series else 0
        return {int(s["time_us"]) - origin: s["activation_vector"] for s in series}

    a, b = indexed(left), indexed(right)
    times = sorted(a.keys() & b.keys())
    rows, trajectory = {}, []
    for at in times:
        changes = {}
        for key in sorted(a[at].keys() | b[at].keys(), key=int):
            delta = a[at].get(key, 0) - b[at].get(key, 0)
            row = rows.setdefault(
                key,
                {
                    "node_id": int(key),
                    "maximum_absolute_difference": 0.0,
                    "difference_at_maximum": 0.0,
                    "peak_time_us": None,
                    "first_difference_us": None,
                    "last_difference_us": None,
                },
            )
            if len(rows) > 100000:
                raise ValueError("comparison node budget exceeded")
            if abs(delta) > row["maximum_absolute_difference"]:
                row.update(maximum_absolute_difference=abs(delta), difference_at_maximum=delta, peak_time_us=str(at))
            if abs(delta) > epsilon:
                if row["first_difference_us"] is None:
                    row["first_difference_us"] = str(at)
                row["last_difference_us"] = str(at)
            changes[key] = delta
        trajectory.append(
            {
                "time_us": str(at),
                "l1_difference": math.fsum(abs(d) for d in changes.values()),
                "positive_difference": math.fsum(max(0, d) for d in changes.values()),
                "negative_difference": math.fsum(max(0, -d) for d in changes.values()),
            }
        )
    ordered = sorted(rows.values(), key=lambda r: (-r["maximum_absolute_difference"], r["node_id"]))
    return {
        "schema": "threemind.observation-comparison/1",
        "status": "compared" if times else "no_shared_samples" if left and right else "not_observed",
        "alignment": "relative-to-first-sample" if relative else "absolute-simulation-time",
        "matched_samples": len(times),
        "left_unmatched_samples": len(a) - len(times),
        "right_unmatched_samples": len(b) - len(times),
        "epsilon": epsilon,
        "changed_node_count": sum(r["maximum_absolute_difference"] > epsilon for r in ordered),
        "maximum_l1_difference": max((r["l1_difference"] for r in trajectory), default=None),
        "nodes": ordered,
        "series": trajectory,
        "scope": "full recorded activation vectors; assumes corresponding node identities; no semantic mask",
        "causal_attribution": "requires same-source controlled copies; arbitrary comparisons are descriptive",
    }
