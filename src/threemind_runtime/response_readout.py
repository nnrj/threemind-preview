"""Read sampled responses without a minimum holding time or a Core dependency.

Response snapshots and sustained stability answer different questions. Peaks,
entries and changes of the leading nodes are observations, not semantic answers
or proof of competitive causation. Never assemble different node peaks into one
purported simultaneous output.
"""

from __future__ import annotations

import math

from .process_observation import validate_series

VERSION = "threemind.response-readout/1"


def response_readout(series, nodes, *, node_ids=None, expected_interval_us, epsilon=1e-12):
    validate_series(series)
    if type(epsilon) not in (int, float) or not math.isfinite(epsilon) or not 0 <= epsilon <= 1:
        raise ValueError("invalid response tolerance")
    if isinstance(expected_interval_us, bool) or str(int(expected_interval_us)) != str(expected_interval_us):
        raise ValueError("expected observation interval must be an integer")
    interval = int(expected_interval_us)
    if interval <= 0:
        raise ValueError("expected observation interval must be positive")
    if not isinstance(nodes, list) or len(nodes) > 100000:
        raise ValueError("observation node budget exceeded")
    known = {int(n["node_id"]) for n in nodes}
    known.update(int(k) for s in series for k in s["activation_vector"])
    if len(known) > 100000:
        raise ValueError("observation node budget exceeded")
    if node_ids is not None:
        if not isinstance(node_ids, list) or not 1 <= len(node_ids) <= 4096:
            raise ValueError("select 1 to 4096 unique node IDs, or omit selection for all nodes")
        if any(type(i) is not int or i < 0 for i in node_ids) or len(set(node_ids)) != len(node_ids):
            raise ValueError("node IDs must be unique nonnegative integers")
        if set(node_ids) - known:
            raise ValueError("selected node IDs are absent from the complete record")
    selected = known if node_ids is None else set(node_ids)
    keys = {str(i) for i in selected}
    samples = [
        {"time_us": s["time_us"], "activation_vector": {k: v for k, v in s["activation_vector"].items() if k in keys}}
        for s in series
    ]
    timeline, episodes, events = [], [], []
    active_episode, previous, gaps = None, None, 0
    marked = {}  # At most one snapshot per source sample, with all applicable reasons.

    def mark(index, reason, **extra):
        entry = marked.setdefault(index, {"reasons": []})
        if reason not in entry["reasons"]:
            entry["reasons"].append(reason)
        entry.update(extra)

    for index, sample in enumerate(samples):
        at = int(sample["time_us"])
        vector = sample["activation_vector"]
        total = math.fsum(vector.values())
        maximum = max(vector.values(), default=0.0)
        # Tolerance only labels numerical activity/ties; raw values are retained.
        active = maximum > epsilon
        leaders = sorted(int(k) for k, v in vector.items() if active and maximum - v <= epsilon)
        gap = previous is not None and at - int(previous["time_us"]) > interval
        if gap:
            gaps += 1
        if active_episode is not None and (gap or not active):
            active_episode["end_reason"] = "sampling_gap" if gap else "inactive_sample"
            active_episode["end_observed_us"] = None if gap else str(at)
            active_episode["right_censored"] = gap
            active_episode = None
        if active:
            if active_episode is None:
                active_episode = {
                    "index": len(episodes),
                    "first_sample_index": index,
                    "start_us": str(at),
                    "last_active_us": str(at),
                    "sample_count": 0,
                    "left_censored": index == 0 or gap,
                    "right_censored": True,
                    "end_reason": "window_end",
                    "end_observed_us": None,
                    "peak_sample_index": index,
                    "peak_activation_total": total,
                }
                episodes.append(active_episode)
                mark(index, "already_active" if active_episode["left_censored"] else "response_entry")
            active_episode["sample_count"] += 1
            active_episode["last_active_us"] = str(at)
            if total > active_episode["peak_activation_total"]:
                active_episode["peak_activation_total"] = total
                active_episode["peak_sample_index"] = index
            if previous is not None and previous["active"] and not gap and leaders != previous["leader_ids"]:
                mark(index, "leader_change")
        timeline.append(
            {
                "time_us": str(at),
                "activation_total": total,
                "active": active,
                "leader_ids": leaders,
                "episode_index": active_episode["index"] if active else None,
                "gap_before": gap,
            }
        )
        previous = timeline[-1]

    # Local crests, including a plateau followed by a fall. Reset at every gap;
    # no inferred continuity or interpolation through missing measurements.
    rising = False
    plateau_start = 0
    for i in range(1, len(timeline)):
        a, b = timeline[i - 1], timeline[i]
        if b["gap_before"]:
            rising, plateau_start = False, i
            continue
        delta = b["activation_total"] - a["activation_total"]
        if delta > epsilon:
            rising, plateau_start = True, i
        elif delta < -epsilon:
            if rising and timeline[plateau_start]["active"]:
                mark(plateau_start, "observed_peak", peak_confirmed_at_us=b["time_us"], plateau_end_us=a["time_us"])
            rising, plateau_start = False, i

    for episode in episodes:
        peak = episode["peak_sample_index"]
        mark(peak, "episode_maximum")
        episode["observed_span_us"] = str(int(episode["last_active_us"]) - int(episode["start_us"]))
        # A sole sampled point has unknown duration, never zero actual duration.
        episode["duration_resolved"] = episode["sample_count"] > 1

    for index, meta in sorted(marked.items()):
        point = timeline[index]
        ranking = sorted(
            ({"node_id": int(k), "activation": v} for k, v in samples[index]["activation_vector"].items() if v > 0),
            key=lambda n: (-n["activation"], n["node_id"]),
        )
        episode = episodes[point["episode_index"]]
        events.append(
            {
                "index": len(events),
                "sample_index": index,
                "episode_index": episode["index"],
                "time_us": point["time_us"],
                "activation_total": point["activation_total"],
                "leader_ids": point["leader_ids"],
                "lead_margin": ranking[0]["activation"] - ranking[1]["activation"]
                if len(ranking) > 1
                else ranking[0]["activation"],
                "ranking": ranking,
                "episode_sample_count": episode["sample_count"],
                "episode_left_censored": episode["left_censored"],
                "episode_right_censored": episode["right_censored"],
                "episode_observed_span_us": episode["observed_span_us"],
                "episode_end_observed_us": episode["end_observed_us"],
                **meta,
            }
        )
    strongest = max(events, key=lambda e: e["activation_total"], default=None)
    return {
        "schema": VERSION,
        "configuration": {"epsilon": epsilon, "expected_interval_us": str(interval), "minimum_duration_us": "0"},
        "selection": {"mode": "all_nodes" if node_ids is None else "explicit_nodes", "node_ids": sorted(selected)},
        "status": "response_observed" if events else "no_active_sample" if samples else "not_observed",
        "raw_activity_seen": any(p["activation_total"] > 0 for p in timeline),
        "sample_count": len(samples),
        "sampling_gap_count": gaps,
        "episode_count": len(episodes),
        "event_count": len(events),
        "strongest_event_index": strongest["index"] if strongest else None,
        "episodes": episodes,
        "events": events,
        "timeline": timeline,
        "scope": "Observed responses, not sustained stability or semantic correctness. Rankings use one actual sample; zero nodes are implicit. Gaps and sub-sample durations remain unknown.",
    }
