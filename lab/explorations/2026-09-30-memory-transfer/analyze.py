"""Read-only paired analysis; missing convergence never becomes a fabricated answer."""

import argparse
import gzip
import json
import math
from collections import defaultdict
from itertools import pairwise
from statistics import mean

from common import WORK, new_json, read_json


def gz(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def records():
    rows = []
    curves = {}
    for path in sorted((WORK / "cases").rglob("result.json")):
        r = read_json(path)
        meta = r["extra"]
        image = gz(path.parent / "parent-state.json.gz")
        row = {
            "id": r["id"],
            "key": r["key"],
            "seed": r["seed"],
            "family": meta.get("family", "interrupted"),
            "stage": meta.get("stage"),
            "preset": meta.get("preset"),
            "mode": meta.get("mode"),
            "life": r["life"],
            "state_sha256": r["state_sha256"],
            "time_us": int(r["time_us"]),
            "nodes": len(image["nodes"]),
            "edges": len(image["edges"]),
            "weight_sum": math.fsum(e["weight"] for e in image["edges"]),
            "stability_sum": math.fsum(e["stability"] for e in image["edges"]),
            "wall_seconds": r["wall_seconds"],
            "config": r["config"],
            "extra": meta,
        }
        for key in (
            "parent",
            "delay_s",
            "cue",
            "expected",
            "targets",
            "assignment",
            "domain",
            "sign",
            "order",
            "force",
            "test_force",
            "consolidation",
            "episodes",
            "behavior",
        ):
            if key in meta:
                row[key] = meta[key]
        if meta.get("stage") == "probe":
            events = [
                json.loads(line)
                for line in gzip.decompress((path.parent / "events.jsonl.gz").read_bytes()).splitlines()
            ]
            windows = [e["payload"] for e in events if e["kind"] == "temporal_readout"]
            activity = next((w for w in windows if w.get("analysis_schema")), None)
            pattern = activity["analyses"]["pattern"] if activity else {}
            points = gz(path.parent / "trajectory.json.gz")
            mapping = {n["id"]: n["channel"] for p in points for n in p["nodes"]}
            mapping.update({n["id"]: n["channel"] for n in image["nodes"]})
            status = pattern.get("status", "no-window")
            ranking = (
                sorted(pattern["nodes"], key=lambda n: (-n["activation"], n["node_id"]))
                if status == "converged"
                else []
            )
            rank = [
                {"channel": mapping[n["node_id"]], "activation": n["activation"], "rank": i + 1}
                for i, n in enumerate(ranking)
            ]
            values = {n["channel"]: n["activation"] for n in rank}
            target = [values.get(ch, 0.0) for ch in meta["targets"]]
            winner = None
            outcome = "not-converged"
            if status == "converged":
                if max(target) <= 1e-8:
                    outcome = "target-not-elicited"
                elif abs(target[0] - target[1]) <= 1e-6:
                    outcome = "tie"
                else:
                    winner = int(target[1] > target[0])
                    outcome = "correct" if winner == meta.get("expected") else "opposite"
            row.update(
                pattern_status=status,
                activity_class=activity["classification"] if activity else "no-window",
                window_id=activity["window_id"] if activity else None,
                decision_us=pattern.get("end_us"),
                primary_ranking=rank,
                primary_targets=target,
                winner=winner,
                primary_outcome=outcome,
                primary_selectivity=None
                if status != "converged" or sum(target) <= 1e-8 or meta.get("expected") is None
                else (target[meta["expected"]] - target[1 - meta["expected"]]) / sum(target),
            )
            curves[row["id"]] = {p["relative_us"]: {n["channel"]: n["activation"] for n in p["nodes"]} for p in points}
            target_series = [
                [
                    (p["relative_us"], next((n["activation"] for n in p["nodes"] if n["channel"] == ch), 0.0))
                    for p in points
                ]
                for ch in meta["targets"]
            ]
            row["trajectory_target_peaks"] = [max(v for _, v in xs) for xs in target_series]
            row["trajectory_target_integrals"] = [
                sum((b[0] - a[0]) / 1e6 * a[1] for a, b in pairwise(xs)) for xs in target_series
            ]
            expected = meta.get("expected")
            integrals = row["trajectory_target_integrals"]
            row["secondary_correct"] = (
                expected is not None
                and row["trajectory_target_peaks"][expected] > 1e-5
                and integrals[expected] - integrals[1 - expected] > 1e-6
            )
            row["peak_saturated_fraction"] = max((p["metrics"]["saturated_fraction"] or 0 for p in points), default=0)
        rows.append(row)
    controls = {
        (r["seed"], r["preset"], r["mode"], r.get("delay_s")): r
        for r in rows
        if r["family"] == "memory" and r["stage"] == "probe" and r["cue"] == "none"
    }
    for row in rows:
        if row["family"] != "memory" or row["stage"] != "probe" or row["cue"] == "none":
            continue
        control = controls[(row["seed"], row["preset"], row["mode"], row["delay_s"])]
        assert control["parent"] == row["parent"]
        left, right = curves[row["id"]], curves[control["id"]]
        assert left.keys() == right.keys(), "paired observation schedules differ; do not fill missing time"
        deltas = [[(t, left[t].get(ch, 0) - right[t].get(ch, 0)) for t in sorted(left)] for ch in row["targets"]]
        row["target_delta_peaks"] = [max(v for _, v in xs) for xs in deltas]
        row["target_delta_minima"] = [min(v for _, v in xs) for xs in deltas]
        row["target_delta_integrals"] = [sum((b[0] - a[0]) / 1e6 * a[1] for a, b in pairwise(xs)) for xs in deltas]
        row["measurable_cue_effect"] = row["target_delta_peaks"][row["expected"]] > 1e-5
        row["supported_recall"] = row["primary_outcome"] == "correct" and row["measurable_cue_effect"]
        row["secondary_correct"] = (
            row["measurable_cue_effect"]
            and row["target_delta_integrals"][row["expected"]] - row["target_delta_integrals"][1 - row["expected"]]
            > 1e-6
        )
    for row in rows:
        if row["family"] != "transfer" or row["stage"] != "probe":
            continue
        control = controls[row["seed"], row["preset"], row["mode"], 1]
        assert row["parent"] == control["parent"]
        a = {t + row["extra"]["begin_us"]: v for t, v in curves[row["id"]].items()}
        b = {t + control["extra"]["begin_us"]: v for t, v in curves[control["id"]].items()}
        common = sorted(a.keys() & b.keys())
        assert len(common) >= 40, "insufficient recorded no-cue overlap"
        deltas = [[(t, a[t].get(ch, 0) - b[t].get(ch, 0)) for t in common] for ch in row["targets"]]
        peaks = [max(v for _, v in xs) for xs in deltas]
        integrals = [sum((y[0] - x[0]) / 1e6 * x[1] for x, y in pairwise(xs)) for xs in deltas]
        row["paired_transfer_interval_s"] = (common[-1] - common[0]) / 1e6
        row["paired_transfer_target_peaks"] = peaks
        row["paired_transfer_target_integrals"] = integrals
        expected = row["expected"]
        row["paired_transfer_correct"] = peaks[expected] > 1e-5 and integrals[expected] - integrals[1 - expected] > 1e-6
    baselines = {
        (r["seed"], r["preset"], r["mode"], r.get("cue")): r
        for r in rows
        if r["family"] == "memory" and r["stage"] == "probe" and r["delay_s"] == 300
    }
    for row in rows:
        if row["family"] != "memory-intervention" or row["stage"] != "probe":
            continue
        base = baselines[row["seed"], row["preset"], row["mode"], row["cue"]]
        no_cue = baselines[row["seed"], row["preset"], row["mode"], "none"]
        assert base["parent"] == no_cue["parent"] == row["parent"]
        a, b, n = curves[row["id"]], curves[base["id"]], curves[no_cue["id"]]
        assert a.keys() == b.keys() == n.keys()
        row["baseline_id"] = base["id"]
        row["intervention_condition"] = row["extra"]["intervention"]["condition"]
        row["max_pointwise_activation_difference"] = max(
            abs(a[t].get(ch, 0) - b[t].get(ch, 0)) for t in a for ch in a[t].keys() | b[t].keys()
        )
        expected = row["expected"]
        before = base["target_delta_integrals"][expected]
        after = row["trajectory_target_integrals"][expected] - no_cue["trajectory_target_integrals"][expected]
        row["baseline_cue_integral"] = before
        row["intervened_cue_integral"] = after
        row["integral_suppression_fraction"] = 1 - after / before if abs(before) > 1e-8 else None
        if row["intervention_condition"] == "restore":
            assert row["max_pointwise_activation_difference"] < 1e-12, "restoration failed full-trajectory comparison"
    for row in rows:
        if row["family"] != "transfer-trace":
            continue
        raw = gz(WORK / "cases" / row["key"] / "input-trajectory.json.gz")
        snapshots = {p["relative_us"]: p for p in raw}
        points = [snapshots[t] for t in sorted(snapshots)]
        phases = []
        for name, start, end in (
            ("during-input", 0, 400000),
            ("post-input-tail", 400000, 600000),
            ("original-score-window", 600000, 5600000),
        ):
            phase = {"name": name, "start_us": start, "end_us": end}
            for field in ("activation", "inhibition", "direct", "associative"):
                phase[field + "_means"] = [
                    sum(
                        max(0, min(b["relative_us"], end) - max(a["relative_us"], start))
                        * next((n[field] for n in a["nodes"] if n["channel"] == ch), 0.0)
                        for a, b in pairwise(points)
                    )
                    / (end - start)
                    for ch in row["targets"]
                ]
            phases.append(phase)
        row["input_phases"] = phases
        row["inspection_preserved_core_hash"] = row["state_sha256"] == row["extra"]["original_state_sha256"]
        assert row["inspection_preserved_core_hash"]
    return rows


def summarize(rows):
    groups = defaultdict(list)
    for r in rows:
        if r["stage"] != "probe" or r.get("expected") is None:
            continue
        key = (r["family"], r["preset"], r["mode"], r.get("delay_s"), r.get("assignment"), r.get("domain"))
        groups[key].append(r)
    summary = []
    for key, values in sorted(groups.items(), key=lambda v: str(v[0])):
        by_seed = defaultdict(list)
        for r in values:
            by_seed[r["seed"]].append(r)
        paired = [v for v in by_seed.values() if {r["expected"] for r in v} == {0, 1} and len(v) == 2]
        correct = sum(r["primary_outcome"] == "correct" for r in values)
        readable = sum(r["winner"] is not None for r in values)
        summary.append(
            dict(zip(("family", "preset", "mode", "delay_s", "assignment", "domain"), key))
            | {
                "n": len(values),
                "seeds": sorted(by_seed),
                "converged": sum(r["pattern_status"] == "converged" for r in values),
                "correct": correct,
                "readable": readable,
                "correct_expression_fraction": correct / len(values),
                "conditional_accuracy": correct / readable if readable else None,
                "bidirectional_correct": sum(all(r["primary_outcome"] == "correct" for r in pair) for pair in paired),
                "bidirectional_total": len(paired),
                "measurable_cue_effect": sum(r.get("measurable_cue_effect", False) for r in values),
                "supported_recall": sum(r.get("supported_recall", False) for r in values),
                "secondary_correct": sum(r.get("secondary_correct", False) for r in values),
                "secondary_bidirectional_correct": sum(
                    all(r.get("secondary_correct", False) for r in pair) for pair in paired
                ),
                "mean_selectivity": mean(v for r in values if (v := r.get("primary_selectivity")) is not None)
                if any(r.get("primary_selectivity") is not None for r in values)
                else None,
                "per_seed": [
                    {
                        "seed": seed,
                        "correct": sum(r["primary_outcome"] == "correct" for r in rs),
                        "n": len(rs),
                        "supported_recall": sum(r.get("supported_recall", False) for r in rs),
                    }
                    for seed, rs in sorted(by_seed.items())
                ],
            }
        )
    behavior = []
    training = {
        (r["seed"], r["preset"], r["mode"], r["force"], r["consolidation"]): r
        for r in rows
        if r["family"] == "adaptation" and r["stage"] == "training"
    }
    for key, r in training.items():
        if not key[-1] or key[:-1] + (False,) not in training:
            continue
        off = training[key[:-1] + (False,)]
        values, controls = r["episodes"], off["episodes"]
        behavior.append(
            {
                "seed": key[0],
                "preset": key[1],
                "mode": key[2],
                "force": key[3],
                "on_id": r["id"],
                "off_id": off["id"],
                "on_mse": [e["position_mse"] for e in values],
                "off_mse": [e["position_mse"] for e in controls],
                "on_improvement": values[0]["position_mse"] - values[2]["position_mse"],
                "off_improvement": controls[0]["position_mse"] - controls[2]["position_mse"],
                "consolidation_benefit": controls[2]["position_mse"] - values[2]["position_mse"],
            }
        )
    return {"groups": summary, "behavior_pairs": behavior}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="New derived result name; existing files are never overwritten")
    args = parser.parse_args()
    if not args.name.replace("-", "").isalnum():
        raise ValueError("simple output name required")
    rows = records()
    result = {
        "rows": rows,
        **summarize(rows),
        "complete_cases": len(rows),
        "simulation_wall_seconds": sum(r["wall_seconds"] for r in rows),
    }
    new_json(WORK / f"{args.name}.json", result)
    print(
        json.dumps(
            {"cases": len(rows), "groups": len(result["groups"]), "behavior_pairs": len(result["behavior_pairs"])}
        )
    )


if __name__ == "__main__":
    main()
