"""Read-only matched analysis; preserve terminal and process outcomes separately."""

import argparse
import csv
import gzip
import itertools
import json
import math
from collections import Counter, defaultdict
from statistics import mean

from common import HERE, WORK, new_json, read_json


def trajectory_value(points, channel):
    samples = sorted(
        {
            int(p["time_us"]): next((n["activation"] for n in p["nodes"] if n["channel"] == channel), 0.0)
            for p in points
        }.items()
    )
    return {
        "integral": math.fsum((a[1] + b[1]) * (b[0] - a[0]) / 2e6 for a, b in itertools.pairwise(samples)),
        "peak": max(v for _, v in samples),
        "terminal": samples[-1][1],
    }


def analyze(name, partial=False):
    rows, counts = [], Counter()
    for path in sorted((WORK / "cases").rglob("result.json")):
        value = read_json(path)
        meta = value["extra"]
        counts[value["key"].split("/")[0]] += 1
        if meta.get("failure"):
            raise RuntimeError("preserved failure: " + value["key"])
        if meta["stage"] != "probe":
            continue
        points = json.loads(gzip.decompress((path.parent / "trajectory.json.gz").read_bytes()))
        times = sorted({int(p["time_us"]) for p in points})
        assert times[0] == meta["probe_start_us"]
        assert times[-1] == int(value["time_us"])
        assert max(b - a for a, b in itertools.pairwise(times)) <= 20000
        before = json.loads(gzip.decompress((path.parent / "pre-probe.json.gz").read_bytes()))
        row = {k: v for k, v in meta.items() if k not in ("schedule", "targets")}
        row.update(
            key=value["key"], id=value["id"], seed=value["seed"], nodes=len(before["nodes"]), edges=len(before["edges"])
        )
        row["queue_count"] = len(before["queue"])
        row["traversed_count"] = len(before["traversed"])
        row["pre_total_activation"] = math.fsum(n["activation"] for n in before["nodes"])
        row["pre_mean_weight"] = mean(e["weight"] for e in before["edges"]) if before["edges"] else 0
        row["pre_mean_stability"] = mean(e["stability"] for e in before["edges"]) if before["edges"] else 0
        for symbol, channel in zip("AB", meta["targets"]):
            node = next((n for n in before["nodes"] if n["channel"] == channel), None)
            row["pre_activation_" + symbol] = node["activation"] if node else 0
            row["pre_inhibition_" + symbol] = node["inhibition"] if node else 0
            for field, x in trajectory_value(points, channel).items():
                row[f"{field}_{symbol}"] = x
        events = [
            json.loads(line) for line in gzip.decompress((path.parent / "events.jsonl.gz").read_bytes()).splitlines()
        ]
        activity = [
            e["payload"] for e in events if e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema")
        ]
        mapping = {n["id"]: n["channel"] for p in points for n in p["nodes"]}
        row["readout_windows"] = len(activity)
        row["readout_decisions"] = [
            {
                "window_id": a.get("window_id"),
                "pattern": a.get("analyses", {}).get("pattern", {}),
                "node_channels": mapping,
            }
            for a in activity
        ]
        rows.append(row)
    index = {r["key"]: r for r in rows}
    incomplete = []
    for row in rows:
        if not row["cue"]:
            continue
        key = row["key"]
        base = (
            key.rsplit("/physical", 1)[0] + "/physical0"
            if row["family"] in ("cut", "recovery")
            else key.rsplit("/cue", 1)[0] + "/cuenone"
        )
        if base not in index:
            incomplete.append(key)
            continue
        baseline = index[base]
        assert baseline["parent"] == row["parent"]
        for letter in "AB":
            row["net_" + letter] = row["integral_" + letter] - baseline["integral_" + letter]
        row["net_A_minus_B"] = row["net_A"] - row["net_B"]
        if row["family"] in ("cut", "recovery"):
            row["margin"] = row["net_A_minus_B"] * (1 if row["sign"] > 0 else -1)
        else:
            row["margin"] = row["net_A_minus_B"] * (-1 if row["order"] == "AB" else 1)
    if incomplete and not partial:
        raise RuntimeError("unmatched windows")
    groups = defaultdict(list)
    pairs = []
    for row in rows:
        if not row["cue"] or "margin" not in row:
            continue
        family = row["family"]
        if family == "cut":
            group = (family, row["mode"], row["learn"], row["groups"])
        elif family == "recovery":
            group = (family, row["mode"], row["learn"], row["delay_s"])
        elif family == "timing":
            group = (family, row["tau"], row["phase_us"], row["maintenance_phase_us"], row["delay_s"])
        elif family == "jitter":
            group = (family, row["variant"], row["delay_s"])
        else:
            group = (family, row["cadence"], row["layout"], row["delay_s"], row["cue_symbol"])
        groups[group].append(row)
        if family not in ("cut", "recovery") and row["order"] == "AB":
            other = index.get(row["key"].replace("/AB/", "/BA/"))
            if other is None or "margin" not in other:
                continue
            margins = [row["margin"], other["margin"]]
            pairs.append(
                {
                    "family": family,
                    "group": group,
                    "seed": row["seed"],
                    "keys": [row["key"], other["key"]],
                    "margins": margins,
                    "bidirectional_1e6": margins[0] * margins[1] > 0 and min(map(abs, margins)) > 1e-6,
                    "bidirectional_1e9": margins[0] * margins[1] > 0 and min(map(abs, margins)) > 1e-9,
                }
            )
    summaries = []
    for key, rs in sorted(groups.items()):
        summaries.append(
            {
                "group": key,
                "n": len(rs),
                "mean_margin": mean(r["margin"] for r in rs),
                "minimum": min(r["margin"] for r in rs),
                "maximum": max(r["margin"] for r in rs),
                "positive": sum(r["margin"] > 1e-6 for r in rs),
                "negative": sum(r["margin"] < -1e-6 for r in rs),
                "zero": sum(abs(r["margin"]) <= 1e-6 for r in rs),
                "terminal_nonzero": sum(max(r["terminal_A"], r["terminal_B"]) > 0 for r in rs),
            }
        )
    result = {
        "counts": dict(counts),
        "partial": partial,
        "unmatched": incomplete,
        "rows": rows,
        "pairs": pairs,
        "summary": summaries,
    }
    # Descriptive checks of registered contrasts; these do not redefine success.
    timing_sets = defaultdict(list)
    for row in rows:
        if row["family"] == "timing" and row["cue"] and "margin" in row:
            timing_sets[(row["seed"], row["tau"], row["phase_us"], row["order"])].append(row)
    checked = [rs for rs in timing_sets.values() if len(rs) == 3]
    fields = ("integral_A", "integral_B", "net_A", "net_B", "margin", "pre_mean_weight")
    result["maintenance_timing_checks"] = {
        "complete_three_timing_sets": len(checked),
        "maximum_range": {
            f: max((max(r[f] for r in rs) - min(r[f] for r in rs) for rs in checked), default=None) for f in fields
        },
    }
    new_json(WORK / (name + ".json"), result)
    print(json.dumps({"counts": counts, "summary": summaries[:32]}, ensure_ascii=False), flush=True)
    return result


def tables(data):
    folder = HERE / "tables"
    folder.mkdir(exist_ok=True)
    simple = [{k: v for k, v in r.items() if k != "readout_decisions"} for r in data["rows"]]
    for name, values in (("windows", simple), ("summary", data["summary"]), ("paired-orders", data["pairs"])):
        fields = sorted(set().union(*(v.keys() for v in values)))
        with (folder / (name + ".csv")).open("x", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in values:
                w.writerow(
                    {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()}
                )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", required=True)
    p.add_argument("--partial", action="store_true")
    p.add_argument("--tables", action="store_true")
    args = p.parse_args()
    data = analyze(args.name, args.partial)
    if args.tables:
        tables(data)
