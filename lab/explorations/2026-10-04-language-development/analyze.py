"""Predeclared whole-window visual recall and continuous-language analyses."""

import argparse
import json
from collections import defaultdict

import numpy as np
from experiment import END, HERE, WORK, read_json

from lab.tools.language_teaching_world import WORDS, TeachingWorld
from lab.tools.service_study import new_json


def templates(definition):
    channels = definition["basis"]["channels"]
    index = {c: i for i, c in enumerate(channels)}
    world = TeachingWorld(definition["seed"])
    result = np.zeros((4, len(channels) + definition["basis"]["residual_buckets"]))
    for i in range(4):
        for variant in range(8):
            for channel, amount in world.frame(world.sample(i, variant)).channels:
                result[i, index[channel]] += amount / 8
    # Remove physical components shared by all four views, for this declared
    # ANALYSIS instrument only. Complete trajectories and decoder inputs remain intact.
    result -= result.mean(axis=0)
    result /= np.maximum(1e-12, np.linalg.norm(result, axis=1))[:, None]
    return result


def scores(case, template):
    values = [np.asarray(w["projection"]["values"]).mean(axis=0) @ template.T for w in case["windows"]]
    return np.asarray(values)


def prediction(value):
    order = np.argsort(-value)
    return int(order[0]) if value[order[0]] - value[order[1]] > 1e-8 and value[order[0]] > 1e-8 else None


def rows(stage):
    raw = [read_json(p) for p in (WORK / "cases").glob(f"{stage}-*/result.json")]
    probes = [r for r in raw if r.get("kind") == "probe"]
    no_cue = {(r["source"], r["seconds"]): r for r in probes if r["cue"] is None and r["intervention"] == "none"}
    source_templates = {}
    output = []
    for r in probes:
        if r["cue"] is None:
            continue
        if r["source"] not in source_templates:
            definition = read_json(WORK / "cases" / r["source"] / "definition.json")
            source_templates[r["source"]] = templates(definition)
        template = source_templates[r["source"]]
        baseline = no_cue.get((r["source"], r["seconds"]))
        if baseline is None:
            continue
        count = min(4, len(r["windows"]), len(baseline["windows"]))
        if count != 4:
            continue
        value = scores(r, template)[:count]
        difference = value - scores(baseline, template)[:count]
        aggregate = difference.mean(axis=0)
        target = WORDS.index(r["target"])
        transport = {k: sum(w["transport"].get(k, 0) for w in r["windows"][:4]) -
                     sum(w["transport"].get(k, 0) for w in baseline["windows"][:4])
                     for k in r["windows"][0]["transport"]}
        output.append({k: r[k] for k in ("key", "route", "seed", "condition", "seconds", "cue", "cue_index", "intensity", "target")} | {
            "prediction": prediction(aggregate), "target_index": target,
            "correct": prediction(aggregate) == target,
            "margin": float(aggregate[target] - np.max(np.delete(aggregate, target))),
            "response": aggregate.tolist(), "raw_response": value.mean(axis=0).tolist(),
            "windows": difference.tolist(), "transport_difference": transport,
        })
    return raw, output


def paired(output):
    groups = defaultdict(dict)
    for r in output:
        if r["condition"] in ("normal", "reversed"):
            groups[(r["route"], r["seed"], r["seconds"], r["cue_index"], r["intensity"])][r["condition"]] = r
    pairs = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        normal, reverse = items["normal"], items["reversed"]
        pairs.append({"route": key[0], "seed": key[1], "seconds": key[2], "cue_index": key[3], "intensity": key[4],
                      "joint_correct": normal["correct"] and reverse["correct"],
                      "changed_prediction": normal["prediction"] != reverse["prediction"],
                      "mean_margin": (normal["margin"] + reverse["margin"]) / 2})
    return pairs


def selection():
    raw, output = rows("cal")
    comparisons = paired(output)
    expected = 8
    rank = []
    for route in ("text", "sentence", "stream-dense", "stream-sparse"):
        subset = [r for r in comparisons if r["route"] == route and r["seed"] == 17 and r["seconds"] == END]
        if len(subset) != expected:
            raise RuntimeError(f"calibration incomplete: {route} {len(subset)}/{expected}")
        rank.append({"route": route, "joint_correct": sum(r["joint_correct"] for r in subset), "count": len(subset),
                     "mean_margin": float(np.mean([r["mean_margin"] for r in subset]))})
    candidates = sorted([r for r in rank if r["route"] != "text"], key=lambda r: (r["joint_correct"], r["mean_margin"]), reverse=True)
    value = {"schema": "E44-sensory-selection/1", "routes": ["text", candidates[0]["route"]],
             "criterion": "joint reversal accuracy, then mean target margin, on two-second baseline-subtracted visual activity; text retained",
             "rank": rank, "formal_data_seen": False, "rows": output, "pairs": comparisons,
             "calibration_cases": len(raw)}
    if list((WORK / "cases").glob("formal-*")):
        raise RuntimeError("selection must precede formal results")
    new_json(WORK / "selection.json", value)
    new_json(HERE / "selection.json", value)
    print(json.dumps({"routes": value["routes"], "rank": rank}, ensure_ascii=False))


def summary():
    raw, output = rows("formal")
    comparisons = paired(output)
    grouped = defaultdict(list)
    for p in comparisons:
        grouped[(p["route"], p["seed"], p["seconds"], p["intensity"])].append(p)
    summary = [{"route": key[0], "seed": key[1], "seconds": key[2], "intensity": key[3],
                "joint_correct": sum(p["joint_correct"] for p in entries), "count": len(entries),
                "mean_margin": float(np.mean([p["mean_margin"] for p in entries]))}
               for key, entries in grouped.items()]
    result = {"completed_cases": len(list((WORK / "cases").glob("*/result.json"))),
              "formal_cases": len(raw), "summary": summary, "rows": output, "pairs": comparisons}
    print(json.dumps({k: result[k] for k in ("completed_cases", "formal_cases", "summary")}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["select", "summary"])
    args = parser.parse_args()
    selection() if args.operation == "select" else summary()
