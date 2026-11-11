"""Analyze completed cases without running Core or rewriting evidence."""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import math
from collections import Counter, defaultdict
from statistics import mean

from runner import WORK, identities

from lab.tools.service_study import new_json, read_json
from threemind_kernels.mechanisms import ShortTermState
from threemind_kernels.novelty import NoveltyConfig


def gz(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def integral(points, channel, field="activation"):
    by_time = {int(p["time_us"]): next((n[field] for n in p["nodes"] if n["channel"] == channel), 0.0) for p in points}
    values = sorted(by_time.items())
    return math.fsum((a[1] + b[1]) * (b[0] - a[0]) / 2e6 for a, b in itertools.pairwise(values))


def edge(state, source, target):
    nodes = {n["channel"]: n for n in state["nodes"]}
    if source not in nodes or target not in nodes:
        return {}
    pair = nodes[source]["id"], nodes[target]["id"]
    row = next((e for e in state["edges"] if (e["source"], e["target"]) == pair), None)
    if row is None:
        return {}
    short = next(
        (s["state"] for s in state["operator_state"]["short_term"] if (s["source"], s["target"]) == pair),
        {"time_us": int(row["birth_us"])},
    )
    cfg = NoveltyConfig(**state["config"])
    projected = ShortTermState(**short).recovered(int(state["time_us"]), cfg.short_term())
    return {
        "weight": row["weight"],
        "stability": row["stability"],
        "available": projected.available,
        "utilization": projected.utilization,
        "source_inhibition": nodes[source]["inhibition"],
        "target_inhibition": nodes[target]["inhibition"],
    }


def analyze(name):
    rows, failures, counts = [], [], Counter()
    for path in sorted((WORK / "cases").rglob("result.json")):
        result = read_json(path)
        meta, folder = result["extra"], path.parent
        counts[meta.get("stage", "failure")] += 1
        if meta.get("failure"):
            failures.append({"key": result["key"], **meta})
            continue
        if meta.get("stage") != "probe":
            continue
        state, points, ids = (
            gz(folder / "pre-probe.json.gz"),
            gz(folder / "trajectory.json.gz"),
            identities(result["seed"]),
        )
        times = sorted({int(p["time_us"]) for p in points})
        if times[0] != meta["probe_start_us"] or times[-1] - times[0] != 5_000_000:
            raise RuntimeError(f"incomplete observation: {result['key']}")
        events = [json.loads(line) for line in gzip.decompress((folder / "events.jsonl.gz").read_bytes()).splitlines()]
        activity = next(
            (e["payload"] for e in events if e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema")),
            {},
        )
        legacy = next(
            (
                e["payload"]
                for e in events
                if e["kind"] == "temporal_readout" and not e["payload"].get("analysis_schema")
            ),
            {},
        )
        mapping = {n["id"]: n["channel"] for p in points for n in p["nodes"]}
        pattern = activity.get("analyses", {}).get("pattern", {})
        ranking = sorted(pattern.get("nodes", []), key=lambda n: (-n["activation"], n["node_id"]))
        row = {
            "key": result["key"],
            "id": result["id"],
            "seed": result["seed"],
            "parent": meta["parent"],
            "i": meta["i"],
            "tau": meta["lifelong_tau_s"],
            "history": meta["history"],
            "profile": meta["profile"],
            "interference": meta.get("interference", "none"),
            "cue": meta["cue"],
            "delay": meta["delay_s"],
            "start_us": times[0],
            "end_us": times[-1],
            "max_gap_us": max(b - a for a, b in itertools.pairwise(times)),
            "life": result["life"],
            "ab": edge(state, ids["A"], ids["B"]),
            "ac": edge(state, ids["A"], ids["C"]),
            "window_id": activity.get("window_id"),
            "pattern_status": pattern.get("status", "unobserved"),
            "legacy_classification": legacy.get("classification", "no-input-window"),
            "decision_ranking": [{"channel": mapping[n["node_id"]], "activation": n["activation"]} for n in ranking],
            "saturation_fraction": mean(
                sum(n["activation"] >= 0.999 for n in p["nodes"]) / len(p["nodes"]) for p in points if p["nodes"]
            ),
        }
        for symbol in "ABCDK":
            row[f"integral_{symbol}"] = integral(points, ids[symbol])
            row[f"peak_{symbol}"] = max(
                (n["activation"] for p in points for n in p["nodes"] if n["channel"] == ids[symbol]), default=0
            )
            row[f"decision_{symbol}"] = next(
                (n["activation"] for n in row["decision_ranking"] if n["channel"] == ids[symbol]), 0.0
            )
        rows.append(row)
    index = {r["key"]: r for r in rows}
    for row in rows:
        if not row["cue"]:
            continue
        base = index.get(row["key"].rsplit("/cue", 1)[0] + "/cue0")
        if base is None:
            raise RuntimeError("missing matched uncued case: " + row["key"])
        assert (base["parent"], base["start_us"], base["end_us"]) == (row["parent"], row["start_us"], row["end_us"])
        for symbol in "ABCDK":
            row[f"net_{symbol}"] = row[f"integral_{symbol}"] - base[f"integral_{symbol}"]
        row["selectivity"] = row["net_B"] - row["net_C"]
    groups = defaultdict(list)
    for row in rows:
        if row["cue"]:
            key = tuple(row[k] for k in ("profile", "interference", "i", "tau", "history", "delay"))
            groups[key].append(row)
    summary = []
    for key, values in sorted(groups.items()):
        summary.append(
            dict(zip(("profile", "interference", "i", "tau", "history", "delay"), key))
            | {
                "blocks": [r["seed"] for r in values],
                "positive_B": sum(r["net_B"] > 1e-9 for r in values),
                "positive_B_1e6": sum(r["net_B"] > 1e-6 for r in values),
                "final_B_positive": sum(r["decision_B"] > 1e-9 for r in values),
                "ab_weight": mean(r["ab"].get("weight", 0.0) for r in values),
                "ab_stability": mean(r["ab"].get("stability", 0.0) for r in values),
                **{k: mean(r[k] for r in values) for k in ("net_B", "net_C", "selectivity", "saturation_fraction")},
            }
        )
    outcome = {
        "schema": "threemind.priority-memory-analysis/1",
        "counts": dict(counts),
        "failures": failures,
        "rows": rows,
        "summary": summary,
        "main_process_metric": "matched five-second net B activation integral",
        "legacy_rankings_preserved": True,
    }
    new_json(WORK / f"{name}.json", outcome)
    print(
        json.dumps(
            {"name": name, "counts": dict(counts), "failures": failures, "groups": len(summary)}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", required=True)
    analyze(p.parse_args().name)
