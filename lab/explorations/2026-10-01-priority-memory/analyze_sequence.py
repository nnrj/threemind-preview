"""Order effects and channel-aligned internal differences; no new simulation."""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
from collections import defaultdict

from analyze import integral
from runner import WORK
from sequence import SEEDS, ids

from lab.tools.service_study import new_json, read_json
from threemind_kernels.mechanisms import FastTrace, ShortTermState
from threemind_kernels.novelty import NoveltyConfig

NODE_FIELDS = ("activation", "inhibition", "trace", "support", "stability", "local_plasticity", "associative", "direct")
EDGE_FIELDS = ("weight", "stability", "eligibility")


def state(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def vector(image):
    """Align by anonymous channel, never by order-dependent node identity."""
    channels = {n["id"]: n["channel"] for n in image["nodes"]}
    groups = defaultdict(dict)
    for n in image["nodes"]:
        for field in NODE_FIELDS:
            groups["node:" + field][str(n["channel"])] = n[field]
    for e in image["edges"]:
        key = f"{channels[e['source']]}:{channels[e['target']]}"
        for field in EDGE_FIELDS:
            groups["edge:" + field][key] = e[field]
    cfg = NoveltyConfig(**image["config"])
    for row in image["operator_state"]["short_term"]:
        key = f"{channels[row['source']]}:{channels[row['target']]}"
        current = ShortTermState(**row["state"]).recovered(int(image["time_us"]), cfg.short_term())
        for field in ("available", "active", "utilization"):
            groups["short_term:" + field][key] = getattr(current, field)
    for row in image["operator_state"]["fast"]:
        key = f"{channels[row['source']]}:{channels[row['target']]}"
        groups["fast:efficacy"][key] = FastTrace(**row["state"]).projected(int(image["time_us"]), cfg.fast_trace())
    return dict(groups)


def difference(a, b):
    result = {}
    for group in set(a) | set(b):
        left, right = a.get(group, {}), b.get(group, {})
        result[group] = max((abs(left.get(k, 0.0) - right.get(k, 0.0)) for k in set(left) | set(right)), default=0.0)
    return result


def analyze(name, blocks=None):
    rows, vectors = [], {}
    for path in sorted((WORK / "cases/sequence").rglob("result.json")):
        value = read_json(path)
        if blocks is not None and value["seed"] not in blocks:
            continue
        meta, key = value["extra"], value["key"]
        if meta.get("failure"):
            raise RuntimeError("preserved failed sequence trial: " + key)
        if meta["stage"] == "sequence-train":
            vectors[key] = vector(state(path.parent / "parent-state.json.gz"))
            continue
        before = state(path.parent / "pre-probe.json.gz")
        if not meta["cue"]:
            vectors[key] = vector(before)
        points = state(path.parent / "trajectory.json.gz")
        times = sorted({int(p["time_us"]) for p in points})
        assert times[0] == meta["probe_start_us"] and times[-1] - times[0] == 5_000_000
        assert max(b - a for a, b in itertools.pairwise(times)) <= 20000
        channels = ids(value["seed"])
        row = {k: meta[k] for k in ("tau", "shared", "gap_s", "order", "delay_s", "cue", "parent")}
        row.update(key=key, id=value["id"], seed=value["seed"], edge_count=len(before["edges"]))
        for letter in "ABXYK":
            row["integral_" + letter] = integral(points, channels[letter])
            row["final_" + letter] = next(
                (n["activation"] for n in points[-1]["nodes"] if n["channel"] == channels[letter]), 0.0
            )
        rows.append(row)
    index = {r["key"]: r for r in rows}
    for row in rows:
        if row["cue"]:
            base = index[row["key"].rsplit("/cue", 1)[0] + "/cue0"]
            assert base["parent"] == row["parent"]
            for letter in "ABXYK":
                row["net_" + letter] = row["integral_" + letter] - base["integral_" + letter]
            first, last = row["order"]
            row["recency_margin"] = row["net_" + last] - row["net_" + first]
    pairs = []
    for a in rows:
        if a["order"] != "AB" or not a["cue"]:
            continue
        b = index[a["key"].replace("/AB/", "/BA/")]
        key = a["key"].rsplit("/wait", 1)[0]
        training_diff = difference(vectors[key + "/train"], vectors[key.replace("/AB", "/BA") + "/train"])
        probe_diff = difference(
            vectors[a["key"].rsplit("/cue", 1)[0] + "/cue0"], vectors[b["key"].rsplit("/cue", 1)[0] + "/cue0"]
        )
        margins = [a["recency_margin"], b["recency_margin"]]
        pairs.append(
            {k: a[k] for k in ("seed", "tau", "shared", "gap_s", "delay_s")}
            | {
                "keys": [a["key"], b["key"]],
                "recency_margins": margins,
                "bidirectional_1e9": margins[0] * margins[1] > 0 and min(map(abs, margins)) > 1e-9,
                "bidirectional_1e6": margins[0] * margins[1] > 0 and min(map(abs, margins)) > 1e-6,
                "training_state_difference": training_diff,
                "preprobe_state_difference": probe_diff,
            }
        )
    output = {
        "schema": "threemind.priority-sequence-analysis/1",
        "selected_blocks": sorted({r["seed"] for r in rows}),
        "rows": rows,
        "pairs": pairs,
        "bidirectional_1e9": sum(r["bidirectional_1e9"] for r in pairs),
        "bidirectional_1e6": sum(r["bidirectional_1e6"] for r in pairs),
    }
    new_json(WORK / (name + ".json"), output)
    print(
        json.dumps(
            {k: output[k] for k in ("bidirectional_1e9", "bidirectional_1e6")}
            | {"pairs": len(pairs), "windows": len(rows)}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--block", type=int, choices=SEEDS, action="append")
    args = parser.parse_args()
    analyze(args.name, args.block)
