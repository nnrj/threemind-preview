"""Read complete evidence, verify dose controls and report primary vs secondary outcomes."""

import csv
import gzip
import json
from collections import Counter, defaultdict
from itertools import pairwise

import numpy as np
from common import WORK, new_json, read_json


def gz(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def analyze():
    rows, retained, replayed = [], [], 0
    for path in sorted((WORK / "cases").rglob("result.json")):
        r = read_json(path)
        meta = r["extra"]
        if meta.get("stage") == "probe" and meta["cue_intensity"] and not r["key"].endswith("/registered"):
            retained.append(r["id"])
            continue
        assert not meta.get("budget_stop"), "incomplete case requires explicit exclusion"
        if meta.get("core_hash_reproduced"):
            replayed += 1
        image = gz(path.parent / "parent-state.json.gz")
        trajectory = gz(path.parent / "trajectory.json.gz")
        mapping = {n["id"]: n["channel"] for n in image["nodes"]}
        row = {
            "id": r["id"],
            "key": r["key"],
            "seed": r["seed"],
            "kernel": r["kernel"],
            "stage": meta["stage"],
            "family": meta["family"],
            "condition": meta["condition"],
            "preset": meta["preset"],
            "template": meta.get("template"),
            "cue": meta.get("cue_intensity"),
            "nodes": len(image["nodes"]),
            "edges": len(image["edges"]),
            "life": r["life"],
            "weight_sum": sum(e["weight"] for e in image["edges"]),
            "stability_sum": sum(e["stability"] for e in image["edges"]),
            "time_us": r["time_us"],
            "wall_seconds": r["wall_seconds"],
            "cross_original_edges": meta.get("cross_original_edges"),
            "unique_channels": meta.get("unique_channels"),
            "reused_channels": meta.get("reused_channels"),
            "input_dose": meta.get("input_dose"),
            "dose_by_channel": meta.get("dose_by_channel"),
            "peak_total": max(p["metrics"]["activation"] for p in trajectory["points"]),
            "peak_saturated_fraction": max(
                (
                    p["metrics"]["saturated_fraction"]
                    for p in trajectory["points"]
                    if p["metrics"]["saturated_fraction"] is not None
                ),
                default=None,
            ),
            "edges_disappeared": sum(not s["right_censored"] for s in trajectory["edge_spans"]),
            "observed_edge_seconds": sum(
                (int(s["end_us"]) - int(s["start_us"])) / 1e6 for s in trajectory["edge_spans"]
            ),
            "novelty": r["metrics"].get("novelty"),
            "transport": r["metrics"]["transport"],
        }
        if meta["stage"] == "probe":
            events = [
                json.loads(line)
                for line in gzip.decompress((path.parent / "events.jsonl.gz").read_bytes()).splitlines()
            ]
            windows = [e["payload"] for e in events if e["kind"] == "temporal_readout"]
            activity = next((w for w in windows if w.get("analysis_schema")), None)
            legacy = next((w for w in windows if not w.get("analysis_schema")), None)
            pattern = activity["analyses"]["pattern"] if activity else {}
            row.update(
                parent=meta["parent"],
                activity_class=activity["classification"] if activity else "no-cue-no-window",
                legacy_class=legacy["classification"] if legacy else "no-cue-no-window",
                pattern_status=pattern.get("status", "no-window"),
                primary_channels=[],
                window_id=activity["window_id"] if activity else None,
            )
            if pattern.get("status") == "converged":
                ranked = sorted(pattern["nodes"], key=lambda n: (-n["activation"], n["node_id"]))
                row.update(
                    primary_time_us=pattern["end_us"],
                    primary_channels=[
                        {"channel": mapping[n["node_id"]], "activation": n["activation"]} for n in ranked
                    ],
                )
            node_curves = defaultdict(list)
            for point in trajectory["points"]:
                for n in point["nodes"]:
                    node_curves[n["channel"]].append((point["relative_us"] / 1e6, n["activation"]))
            row["channel_peaks"] = {str(ch): max(v for _, v in curve) for ch, curve in node_curves.items()}
            row["channel_integrals"] = {
                str(ch): sum((b[0] - a[0]) * a[1] for a, b in pairwise(curve)) for ch, curve in node_curves.items()
            }
            # Channel 102 was never directly probed. It is only a secondary association measure.
            row["association_peak"] = row["channel_peaks"].get("102", 0) if meta["family"] == "intensity" else None
            row["channel_curves"] = {str(ch): curve for ch, curve in node_curves.items()}
            row["observed_times"] = [p["relative_us"] / 1e6 for p in trajectory["points"]]
        if meta["family"] == "equal-drive":
            d = read_json(path.parent / "diagnostics.json")
            row.update(
                diagnostic_hash_verified=d["hash_verified"],
                extra_intensity=sum(v["extra_intensity"] for v in d["records"] if v["kind"] == "consolidation"),
                activated=d["transport"]["activated"],
                received=d["transport"]["received"],
            )
        rows.append(row)
    groups = defaultdict(dict)
    for r in rows:
        if r["family"] == "physical" and r["stage"] == "training":
            groups[(r["seed"], r["preset"], r["template"])][r["condition"]] = r
    for group in groups.values():
        baseline = group["complete"]["dose_by_channel"]
        for condition in ("split", "shuffled"):
            actual = group[condition]["dose_by_channel"]
            assert actual.keys() == baseline.keys()
            assert all(abs(actual[k] - baseline[k]) < 1e-9 for k in baseline), "dose mismatch"
    # Pair each registered cue with the exact parent's no-cue trajectory.
    controls = {r["parent"]: r for r in rows if r["stage"] == "probe" and r["cue"] == 0}
    for r in rows:
        if r["stage"] == "probe" and r["cue"]:
            control = controls[r["parent"]]
            r["peak_total_minus_no_cue"] = r["peak_total"] - control["peak_total"]
            if r["family"] == "intensity":
                r["association_peak_minus_no_cue"] = r["association_peak"] - control["association_peak"]
            channels = set(r["channel_curves"]) | set(control["channel_curves"])
            paired = {}
            for ch in channels:
                left, right = dict(r["channel_curves"].get(ch, [])), dict(control["channel_curves"].get(ch, []))
                # Only jointly observed sample times; no extrapolated tail or invented convergence.
                shared = sorted(set(r["observed_times"]) & set(control["observed_times"]))
                # Complete node snapshots: an absent node has no activation at a sampled time.
                paired[ch] = max((abs(left.get(t, 0) - right.get(t, 0)) for t in shared), default=0)
            r["max_paired_channel_difference"] = max(paired.values(), default=0)
            r["association_max_paired_difference"] = paired.get("102", 0) if r["family"] == "intensity" else None
    result = {
        "cases": len(rows),
        "retained_registration_failures": retained,
        "reproduced_core_hashes": replayed,
        "dose_matched_groups": len(groups),
        "primary_counts": dict(Counter(r.get("pattern_status") for r in rows if r["stage"] == "probe" and r["cue"])),
        "rows": rows,
    }
    new_json(WORK / "analysis-v3.json", result)
    columns = sorted({k for r in rows for k, v in r.items() if not isinstance(v, (dict, list))})
    with (WORK / "summary-v3.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False))
    plot(rows)


def plot(rows):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), layout="constrained")
    for ax, family, conditions, field, title in (
        (
            axes[0],
            "background",
            ["fresh-single", "fresh-group", "repeated-random", "fixed-amplitude", "synthetic", "telemetry"],
            "edges",
            "Edges after background input",
        ),
        (axes[1], "intensity", ["none", "single4", "repeated1"], "weight_sum", "Connection strength after history"),
        (
            axes[2],
            "physical",
            ["complete", "no-proprioception", "split", "shuffled", "untrained"],
            "edges",
            "Edges after physical training",
        ),
    ):
        for j, preset in enumerate(("ordinary", "facilitation")):
            vals = [
                [
                    r[field]
                    for r in rows
                    if r["stage"] == "training"
                    and r["family"] == family
                    and r["condition"] == c
                    and r["preset"] == preset
                ]
                for c in conditions
            ]
            ax.bar(
                np.arange(len(conditions)) + (j - 0.5) * 0.36,
                [np.mean(v) for v in vals],
                width=0.36,
                label=preset,
                color=("#267d6b", "#d09c43")[j],
            )
            for i, v in enumerate(vals):
                ax.scatter([i + (j - 0.5) * 0.36] * len(v), v, color="#24362d", s=9, zorder=3)
        ax.set_title(title)
        ax.set_xticks(range(len(conditions)), conditions, rotation=32, ha="right")
        ax.set_ylabel(field)
    axes[0].legend(frameon=False)
    fig.suptitle("Unchanged continuous-memory/2 • secondary structural observations (not convergence outcomes)")
    fig.savefig(WORK / "overview.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    analyze()
