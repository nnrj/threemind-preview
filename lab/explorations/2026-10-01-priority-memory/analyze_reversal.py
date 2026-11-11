"""Phase-resolved paired analysis of the registered sensory replay experiment."""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import math
from collections import defaultdict
from statistics import mean

from runner import WORK

from lab.tools.service_study import new_json, read_json


def integral(points, channel, start, end):
    samples = {
        int(p["time_us"]): next((n["activation"] for n in p["nodes"] if n["channel"] == channel), 0.0)
        for p in points
        if start <= int(p["time_us"]) <= end
    }
    values = sorted(samples.items())
    assert values[0][0] == start and values[-1][0] == end
    return math.fsum((a[1] + b[1]) * (b[0] - a[0]) / 2e6 for a, b in itertools.pairwise(values))


def analyze(name):
    rows = []
    for path in sorted((WORK / "cases/reversal").rglob("result.json")):
        value = read_json(path)
        meta = value["extra"]
        if meta.get("failure"):
            raise RuntimeError("preserved failure must be resolved separately: " + value["key"])
        points = json.loads(gzip.decompress((path.parent / "trajectory.json.gz").read_bytes()))
        start = meta["start_us"]
        times = sorted({int(p["time_us"]) for p in points})
        assert times[0] == start and times[-1] == start + 5_600_000
        assert max(b - a for a, b in itertools.pairwise(times)) <= 20000
        row = {
            k: meta[k]
            for k in (
                "mode",
                "sign",
                "variant",
                "physical",
                "parent",
                "targets",
                "expected",
                "exact_replay",
                "unsilenced_edges",
            )
        }
        row.update(key=value["key"], id=value["id"], seed=value["seed"])
        for phase, a, b in (
            ("input", 0, 400000),
            ("after", 400000, 5600000),
            ("followup", 600000, 5600000),
            ("whole", 0, 5600000),
        ):
            row[phase] = [integral(points, target, start + a, start + b) for target in meta["targets"]]
        row["final"] = [
            next((n["activation"] for n in points[-1]["nodes"] if n["channel"] == target), 0.0)
            for target in meta["targets"]
        ]
        rows.append(row)
    index = {r["key"]: r for r in rows}
    groups = defaultdict(list)
    for row in rows:
        if not row["physical"]:
            continue
        base = index[row["key"].removesuffix("1") + "0"]
        assert row["parent"] == base["parent"]
        for phase in ("input", "after", "followup", "whole"):
            net = [a - b for a, b in zip(row[phase], base[phase])]
            row["net_" + phase] = net
            row["margin_" + phase] = net[row["expected"]] - net[1 - row["expected"]]
        groups[(row["mode"], row["variant"])].append(row)
    summary = []
    for (mode, variant), group in sorted(groups.items()):
        summary.append(
            {
                "mode": mode,
                "variant": variant,
                "pairs": len(group),
                "blocks": sorted({r["seed"] for r in group}),
                **{
                    f"{phase}_{name}": fn([r["margin_" + phase] for r in group])
                    for phase in ("input", "after", "followup", "whole")
                    for name, fn in (
                        ("mean", mean),
                        ("original", lambda x: sum(v > 1e-9 for v in x)),
                        ("reversed", lambda x: sum(v < -1e-9 for v in x)),
                        ("absent", lambda x: sum(abs(v) <= 1e-9 for v in x)),
                    )
                },
            }
        )
    result = {
        "schema": "threemind.reversal-analysis/1",
        "rows": rows,
        "summary": summary,
        "exact_replays": sum(r["exact_replay"] is True for r in rows),
    }
    new_json(WORK / (name + ".json"), result)
    print(
        json.dumps({"name": name, "cases": len(rows), "groups": len(summary), "exact_replays": result["exact_replays"]})
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", required=True)
    analyze(p.parse_args().name)
