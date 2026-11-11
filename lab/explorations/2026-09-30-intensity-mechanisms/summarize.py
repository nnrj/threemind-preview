"""Matched comparisons, including full-trajectory restoration checks; no simulation."""

import argparse
from collections import Counter, defaultdict
from statistics import mean

from analyze import gz
from experiment import WORK

from lab.tools.service_study import new_json, read_json


def grouped(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    return [
        dict(zip(keys, key))
        | {
            "n": len(values),
            **{
                name: mean(v[name] for v in values)
                for name in ("net_A", "net_B", "net_C", "net_D", "ab_weight", "saturation_fraction")
            },
            "B_min": min(v["net_B"] for v in values),
            "B_max": max(v["net_B"] for v in values),
        }
        for key, values in sorted(groups.items())
    ]


def compare_traces(left, right):
    def nodes(path):
        return {int(p["time_us"]): {n["id"]: n["activation"] for n in p["nodes"]} for p in gz(path)}

    a, b = nodes(left), nodes(right)
    assert a.keys() == b.keys()
    return max((abs(a[t].get(n, 0) - b[t].get(n, 0)) for t in a for n in a[t].keys() | b[t].keys()), default=0)


def summarize(source, target):
    analysis = read_json(WORK / f"{source}.json")
    rows = analysis["rows"]
    cued = [r for r in rows if r.get("net_status") == "matched"]
    main = [r for r in cued if r["key"].startswith("matrix/") and r["key"].endswith("/cue0.5")]
    index = {r["key"]: r for r in rows}
    comparisons = []
    for candidate in main:
        if candidate["i"] or not candidate["f"] or not candidate["l"] or candidate["history"] != "single4":
            continue
        for control in ("i1f0l1", "i1f1l1"):
            baseline = index.get(candidate["key"].replace("i0f1l1", control))
            if not baseline or "net_B" not in baseline:
                continue
            ratio = candidate["net_B"] / baseline["net_B"] if baseline["net_B"] > 1e-9 else None
            comparisons.append(
                {
                    "seed": candidate["seed"],
                    "delay": candidate["delay"],
                    "reference": control,
                    "candidate": candidate["net_B"],
                    "baseline": baseline["net_B"],
                    "ratio": ratio,
                    "at_least_80_percent": ratio is not None and ratio >= 0.8,
                }
            )
    formation = [r | {"condition": r["key"].split("/")[1]} for r in cued if r["key"].startswith("formation/")]
    formation += [
        r | {"condition": "unchanged"}
        for r in main
        if r["seed"] in (930401, 930411)
        and not r["i"]
        and r["f"] == r["l"]
        and r["delay"] == 30
        and r["history"] in ("single1", "single4")
    ]
    facilitation = [r for r in cued if r["key"].startswith("facilitation/")]
    facilitation += [
        r
        for r in main
        if r["seed"] in (930401, 930411) and not r["i"] and r["l"] and r["delay"] in (1, 30) and r["history"] != "none"
    ]
    sensitivity = [
        r
        for r in cued
        if r["key"].startswith("matrix/")
        and not r["interventions"]
        and r["seed"] in (930401, 930411)
        and not r["i"]
        and r["l"]
        and r["delay"] in (1, 30)
    ]
    expression, phases, connections, restored = [], [], [], []
    for row in cued:
        key = row["key"]
        if "-expression-" in key:
            expression.append(row | {"condition": key.split("-expression-")[1]})
        if "-facilitation-switch-" in key:
            phases.append(row | {"expression_f": int(key.rsplit("-", 1)[1])})
        if "-connection-" in key:
            name = key.split("-connection-")[1]
            connections.append(row | {"condition": name})
            if name == "restore":
                for cue in ("0.0", "0.5"):
                    restored_key = key.replace("/cue0.5", "/cue" + cue)
                    original = restored_key.removesuffix("-connection-restore")
                    restored.append(
                        {
                            "key": restored_key,
                            "max_activation_difference": compare_traces(
                                WORK / "cases" / restored_key / "trajectory.json.gz",
                                WORK / "cases" / original / "trajectory.json.gz",
                            ),
                        }
                    )
    for row in main:
        if row["seed"] in (930401, 930411) and not row["i"] and row["l"] and row["delay"] in (1, 30):
            if row["history"] in ("single4", "repeat"):
                phases.append(row | {"expression_f": row["f"]})
            if not row["f"] and row["history"] == "single4":
                expression.append(row | {"condition": "unchanged"})
                if row["delay"] == 30:
                    connections.append(row | {"condition": "unchanged"})
    result = {
        "source": source,
        "primary_matrix": grouped(main, ("i", "f", "l", "history", "delay")),
        "replacement": comparisons,
        "formation": grouped(formation, ("condition", "f", "l", "history")),
        "facilitation": grouped(facilitation, ("facilitation_tau_s", "history", "delay")),
        "sensitivity": grouped(sensitivity, ("f", "history", "delay", "cue")),
        "expression": grouped(expression, ("condition", "delay")),
        "phases": grouped(phases, ("f", "expression_f", "history", "delay")),
        "connections": grouped(connections, ("condition",)),
        "restorations": restored,
        "reader_pattern_status": dict(Counter(r["pattern_status"] for r in rows)),
        "reader_legacy_classification": dict(Counter(r["legacy_classification"] for r in rows)),
        "target_present_at_pattern_decision": sum((r["decision_B"] or 0) > 0 for r in rows),
        "cued_positive_target_integral": sum(r["net_B"] > 1e-9 for r in cued),
        "cued_negative_target_integral": sum(r["net_B"] < -1e-9 for r in cued),
        "max_sample_gap_us": max(r["max_sample_gap_us"] for r in rows),
    }
    new_json(WORK / f"{target}.json", result)
    print({"source": source, "output": target, "cued": len(cued), "restorations": len(restored)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    for name in (args.source, args.name):
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("use simple names")
    summarize(args.source, args.name)
