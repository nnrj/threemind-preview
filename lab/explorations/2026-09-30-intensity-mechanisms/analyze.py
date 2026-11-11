"""Read-only, fixed-window paired analysis. Never edit or simulate Core."""

import argparse
import csv
import gzip
import itertools
import json
import math
from collections import defaultdict
from statistics import mean

from experiment import WORK, identities

from lab.tools.service_study import new_json, read_json
from threemind_kernels.mechanisms import FastTrace, ShortTermState
from threemind_kernels.novelty import NoveltyConfig


def gz(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def integral(points, channel, field="activation"):
    # The last observation at a timestamp is its post-delivery state.
    values = {int(p["time_us"]): next((n[field] for n in p["nodes"] if n["channel"] == channel), 0.0) for p in points}
    ordered = sorted(values.items())
    return math.fsum((ta[1] + tb[1]) * (tb[0] - ta[0]) / 2e6 for ta, tb in itertools.pairwise(ordered))


def edge_value(state, source, target, field):
    ids = {n["channel"]: n["id"] for n in state["nodes"]}
    return next(
        (e[field] for e in state["edges"] if e["source"] == ids.get(source) and e["target"] == ids.get(target)), 0.0
    )


def local_state(state, source, target):
    """Project lazy operator states to observation time without modifying Core."""
    nodes = {n["channel"]: n for n in state["nodes"]}
    if source not in nodes or target not in nodes:
        return {}
    key = (nodes[source]["id"], nodes[target]["id"])
    edge = next((e for e in state["edges"] if (e["source"], e["target"]) == key), None)
    out = {"source_inhibition": nodes[source]["inhibition"], "target_inhibition": nodes[target]["inhibition"]}
    if edge is None:
        return out
    config = NoveltyConfig(**state["config"])
    when = int(state["time_us"])
    operators = state["operator_state"]
    short = next(
        (r["state"] for r in operators["short_term"] if (r["source"], r["target"]) == key),
        {"time_us": int(edge["birth_us"])},
    )
    projected = ShortTermState(**short).recovered(when, config.short_term())
    fast = next(
        (r["state"] for r in operators["fast"] if (r["source"], r["target"]) == key), {"time_us": int(edge["birth_us"])}
    )
    out.update(
        available=projected.available,
        active=projected.active,
        utilization=projected.utilization,
        next_release_fraction=projected.release(when, config.short_term())[1],
        fast_weight_addition=FastTrace(**fast).efficacy(edge["weight"], when, config.fast_trace()) - edge["weight"],
    )
    return out


def analyze(name):
    rows, failures, training = [], [], []
    for path in sorted((WORK / "cases").rglob("result.json")):
        result = read_json(path)
        meta, folder = result["extra"], path.parent
        if meta.get("failure"):
            failures.append({"key": result["key"], **meta})
            continue
        stage = meta.get("stage")
        if stage not in ("train", "probe"):
            continue
        ids = identities(result["seed"])
        state = gz(folder / ("pre-probe.json.gz" if stage == "probe" else "parent-state.json.gz"))
        row = {
            "key": result["key"],
            "id": result["id"],
            "seed": result["seed"],
            "history": meta["history"],
            "i": meta["factors"][0],
            "f": meta["factors"][1],
            "l": meta["factors"][2],
            "facilitation_tau_s": result["config"]["stp_facilitation_tau_s"],
            "patch": meta.get("patch", {}),
            "life": result["life"],
            "ab_weight": edge_value(state, ids["A"], ids["B"], "weight"),
            "ab_stability": edge_value(state, ids["A"], ids["B"], "stability"),
            "ac_weight": edge_value(state, ids["A"], ids["C"], "weight"),
            "edges": len(state["edges"]),
            "wall_seconds": result["wall_seconds"],
        }
        row["pre_ab_local_state"] = local_state(state, ids["A"], ids["B"])
        if stage == "train":
            training.append(row)
            continue
        points = gz(folder / "trajectory.json.gz")
        times = sorted({p["time_us"] for p in points})
        if not times or times[0] != meta["probe_start_us"] or times[-1] != times[0] + 5_000_000:
            raise RuntimeError(f"incomplete registered observation: {result['key']}")
        row.update(
            delay=meta["delay_s"],
            cue=meta["cue"],
            parent=meta["parent"],
            window_start_us=times[0],
            window_end_us=times[-1],
            max_sample_gap_us=max(b - a for a, b in itertools.pairwise(times)),
            probe_patch=meta.get("probe_patch", {}),
            interventions=meta.get("interventions", []),
        )
        for symbol in "ABCDK":
            row[f"integral_{symbol}"] = integral(points, ids[symbol])
            row[f"inhibition_{symbol}"] = integral(points, ids[symbol], "inhibition")
            row[f"peak_{symbol}"] = max(
                (n["activation"] for p in points for n in p["nodes"] if n["channel"] == ids[symbol]), default=0
            )
        row["saturation_fraction"] = mean(
            sum(n["activation"] >= 0.999 for n in p["nodes"]) / len(p["nodes"]) for p in points if p["nodes"]
        )
        events = [json.loads(line) for line in gzip.decompress((folder / "events.jsonl.gz").read_bytes()).splitlines()]
        activity = next(
            (e["payload"] for e in events if e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema")),
            None,
        )
        legacy = next(
            (
                e["payload"]
                for e in events
                if e["kind"] == "temporal_readout" and not e["payload"].get("analysis_schema")
            ),
            None,
        )
        pattern = activity["analyses"]["pattern"] if activity else {}
        row["pattern_status"] = pattern.get("status", "unobserved")
        row["legacy_classification"] = legacy["classification"] if legacy else "no-input-window"
        row["window_id"] = activity["window_id"] if activity else None
        mapping = {n["id"]: n["channel"] for p in points for n in p["nodes"]}
        ranking = sorted(pattern.get("nodes", []), key=lambda n: (-n["activation"], n["node_id"]))
        row["decision_ranking"] = [{"channel": mapping[n["node_id"]], "activation": n["activation"]} for n in ranking]
        row["decision_B"] = next((n["activation"] for n in row["decision_ranking"] if n["channel"] == ids["B"]), None)
        rows.append(row)
    index = {row["key"]: row for row in rows}
    for row in rows:
        if row["cue"] == 0:
            continue
        # Explicit intervention suffixes must have a matching uncued branch.
        marker = f"/cue{row['cue']}"
        counterpart = row["key"].replace(marker, "/cue0.0", 1)
        baseline = index.get(counterpart)
        if baseline is None:
            row["net_status"] = "missing-matched-no-cue"
            continue
        if (baseline["window_start_us"], baseline["window_end_us"]) != (row["window_start_us"], row["window_end_us"]):
            raise RuntimeError("paired observation windows differ")
        row["net_status"] = "matched"
        for symbol in "ABCDK":
            row[f"net_{symbol}"] = row[f"integral_{symbol}"] - baseline[f"integral_{symbol}"]
        row["selectivity"] = row["net_B"] - row["net_C"]
    groups = defaultdict(list)
    for row in rows:
        if row.get("net_status") == "matched" and row["key"].startswith("matrix/") and row["key"].endswith("/cue0.5"):
            groups[(row["i"], row["f"], row["l"], row["history"], row["delay"])].append(row)
    summary = [
        {
            "i": key[0],
            "f": key[1],
            "l": key[2],
            "history": key[3],
            "delay": key[4],
            "n": len(values),
            "positive_B": sum(v["net_B"] > 1e-9 for v in values),
            **{
                name: mean(v[name] for v in values)
                for name in ("net_B", "net_C", "selectivity", "ab_weight", "saturation_fraction")
            },
        }
        for key, values in sorted(groups.items())
    ]
    out = {
        "schema": "intensity-mechanisms-analysis/1",
        "rows": rows,
        "training": training,
        "failures": failures,
        "groups": summary,
        "scope": "paired fixed-window activation integrals; retain decision-time ranks separately",
    }
    new_json(WORK / f"{name}.json", out)
    with (WORK / f"{name}.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]) if summary else [])
        writer.writeheader()
        writer.writerows(summary)
    print(
        json.dumps(
            {
                "probes": len(rows),
                "training": len(training),
                "failures": len(failures),
                "groups": len(summary),
                "output": str(WORK / f"{name}.json"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    if not args.name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("use a simple analysis name")
    analyze(args.name)
