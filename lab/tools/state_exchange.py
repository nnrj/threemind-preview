"""Audited, channel-aligned snapshot exchange for development research only.

No live model is edited. Only explicitly supported snapshot groups are copied.
This is an artificial intervention, not ordinary learning or inheritance.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path

from threemind_core import StateImage
from threemind_runtime import create_engine

NODE_HISTORY = ("support", "stability", "local_plasticity", "touches", "birth_us", "last_touch_us")
NODE_DYNAMIC = (
    "activation",
    "inhibition",
    "trace",
    "direct",
    "associative",
    "pending_inhibition",
    "generated_inhibition",
)
EDGE_HISTORY = ("stability", "eligibility", "touches", "birth_us", "last_touch_us")
GROUPS = ("W", "S", "N", "D")
IDENTICAL = (
    "schema",
    "dynamics",
    "config",
    "definition",
    "definition_hash",
    "time_us",
    "state_time_us",
    "next_step_us",
    "next_propagation_us",
    "life",
    "sources_open",
    "quiet_since_us",
    "energy",
    "attention",
)


def exchange(recipient: StateImage, donor: StateImage, groups=(), *, backend="native"):
    """Return a new validated image and exhaustive receipt; never mutate inputs."""
    groups = tuple(groups)
    if len(set(groups)) != len(groups) or any(g not in GROUPS for g in groups):
        raise ValueError("unknown or duplicate state group")
    a, b = recipient.to_dict(), donor.to_dict()
    if a.get("schema") != "threemind.continuous-memory-state/2":
        raise ValueError("this exchange protocol supports continuous-memory-state/2 only")
    if any(a[k] != b[k] for k in IDENTICAL):
        raise ValueError("configuration, lifecycle, physical state or clocks differ")
    for state in (a, b):
        if state["queue"] or state["traversed"] or state["operator_state"]["novelty"]["pending"]:
            raise ValueError("exchange requires settled snapshots without queued or pending events")
        if state["silenced_nodes"] or state["silenced_edges"]:
            raise ValueError("silenced states require a separately defined exchange protocol")
        restored = create_engine(state=StateImage.from_dict(state), backend=backend).capture_state()
        if restored.digest != StateImage.from_dict(state).digest:
            raise ValueError("source restoration is not exact")

    def indices(state):
        nodes = {n["channel"]: n for n in state["nodes"]}
        channels = {n["id"]: n["channel"] for n in state["nodes"]}
        edges = {(channels[e["source"]], channels[e["target"]]): e for e in state["edges"]}
        return nodes, channels, edges

    an, _, ae = indices(a)
    bn, bc, be = indices(b)
    if an.keys() != bn.keys() or ae.keys() != be.keys():
        raise ValueError("channel set or directed topology differs")
    changes = []

    def assign(target, source, fields, identity):
        for field in fields:
            if target[field] != source[field]:
                changes.append({"location": identity + [field], "before": target[field], "after": source[field]})
                target[field] = copy.deepcopy(source[field])

    for channel, target in an.items():
        if "N" in groups:
            assign(target, bn[channel], NODE_HISTORY, ["node", channel])
        if "D" in groups:
            assign(target, bn[channel], NODE_DYNAMIC, ["node", channel])
    for pair, target in ae.items():
        if "W" in groups:
            assign(target, be[pair], ("weight",), ["edge", *pair])
        if "S" in groups:
            assign(target, be[pair], EDGE_HISTORY, ["edge", *pair])
    if "D" in groups:
        for name in ("short_term", "fast"):
            old = a["operator_state"][name]
            mapped = []
            for row in b["operator_state"][name]:
                source, target = bc[row["source"]], bc[row["target"]]
                mapped.append(
                    {"source": an[source]["id"], "target": an[target]["id"], "state": copy.deepcopy(row["state"])}
                )
            mapped.sort(key=lambda r: (r["source"], r["target"]))
            if mapped != old:
                changes.append({"location": ["operator_state", name], "before": old, "after": mapped})
                a["operator_state"][name] = mapped
    image = StateImage.from_dict(a)
    restored = create_engine(state=image, backend=backend).capture_state()
    if restored.digest != image.digest:
        raise ValueError("exchange does not round-trip exactly")
    if not groups and image.digest != recipient.digest:
        raise AssertionError("sham exchange changed state")
    return image, {
        "schema": "threemind.research-state-exchange/1",
        "artificial_intervention": True,
        "natural_learning": False,
        "groups": [g for g in GROUPS if g in groups],
        "recipient_sha256": recipient.digest,
        "donor_sha256": donor.digest,
        "after_sha256": image.digest,
        "time_us": a["time_us"],
        "alignment": "anonymous channel and directed channel pair; recipient node ids retained",
        "changes": changes,
        "unchanged_global_state": [k for k in a if k not in ("nodes", "edges", "operator_state")],
    }


def read_image(path):
    raw = path.read_bytes()
    return StateImage(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("recipient", type=Path)
    p.add_argument("donor", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--groups", nargs="*", choices=GROUPS, default=[])
    p.add_argument("--backend", choices=("native", "reference"), default="native")
    args = p.parse_args()
    receipt = args.output.with_name(args.output.name + ".intervention.json")
    if args.output.exists() or receipt.exists():
        p.error("output and intervention receipt must both be new paths")
    image, audit = exchange(read_image(args.recipient), read_image(args.donor), args.groups, backend=args.backend)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open("x", encoding="utf-8") as out:
        json.dump(audit, out, ensure_ascii=False, indent=2, allow_nan=False)
    with args.output.open("xb") as out:
        out.write(gzip.compress(image.payload) if args.output.suffix == ".gz" else image.payload)
    print(json.dumps({"output": str(args.output), "receipt": str(receipt), "state_sha256": image.digest}))


if __name__ == "__main__":
    main()
