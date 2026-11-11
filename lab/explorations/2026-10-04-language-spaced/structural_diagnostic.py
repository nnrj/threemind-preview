"""Exploratory source-basis partition of saved structure; never changes Core."""

import hashlib
import json
from collections import defaultdict

import numpy as np
from experiment import WORK, read_json

from lab.tools.service_study import new_json
from threemind_runtime.codec import ArtifactCodec


def main():
    background_channels = set()
    for line in (WORK / "physical-telemetry.jsonl").read_text(encoding="utf-8").splitlines():
        stimulus = json.loads(line)["stimulus"]
        if stimulus:
            background_channels.update(int(c[0]) for c in stimulus["channels"])
    overlaps = {}
    for seed in (17, 29):
        mask = int.from_bytes(hashlib.blake2s(f"language-input/1:{seed}".encode(), digest_size=4).digest(), "big")
        overlaps[str(seed)] = sorted(background_channels & {mask ^ i for i in range(128)})
    if any(overlaps.values()):
        raise ValueError("actual language/telemetry collision; source partition cannot assume disjoint channels")
    rows = []
    for path in sorted((WORK / "cases").glob("*/checkpoints/*/summary.json")):
        summary = read_json(path)
        if summary["requested_seconds"] not in (530, 830):
            continue
        state = ArtifactCodec.decode((path.parent / "state.tmind").read_bytes()).to_dict()
        mask = int.from_bytes(
            hashlib.blake2s(f"language-input/1:{summary['seed']}".encode(), digest_size=4).digest(), "big"
        )
        origins = {
            n["id"]: "language" if 0 <= (int(n["channel"]) ^ mask) < 128 else "background" for n in state["nodes"]
        }
        nodes, edges = defaultdict(list), defaultdict(list)
        for node in state["nodes"]:
            nodes[origins[node["id"]]].append(node)
        for edge in state["edges"]:
            edges[origins[edge["source"]] + "-to-" + origins[edge["target"]]].append(edge)
        rows.append(
            {
                "source": path.parents[2].name,
                "seconds": summary["requested_seconds"],
                "nodes": {
                    k: {
                        "count": len(v),
                        "activation": sum(n["activation"] for n in v),
                        "touches_min": min(n["touches"] for n in v),
                        "touches_max": max(n["touches"] for n in v),
                    }
                    for k, v in nodes.items()
                },
                "edges": {
                    k: {
                        "count": len(v),
                        "mean_weight": float(np.mean([e["weight"] for e in v])),
                        "max_weight": max(e["weight"] for e in v),
                        "mean_stability": float(np.mean([e["stability"] for e in v])),
                    }
                    for k, v in edges.items()
                },
            }
        )
    target = WORK / "structural-diagnostic.json"
    new_json(
        target,
        {
            "scope": "posthoc description; source basis is an observer annotation, not kernel semantics",
            "recorded_background_channel_count": len(background_channels),
            "actual_language_background_channel_overlap": overlaps,
            "actual_emissions_not_attributed_by_this_static_analysis": True,
            "rows": rows,
        },
    )
    print(str(target))


if __name__ == "__main__":
    main()
