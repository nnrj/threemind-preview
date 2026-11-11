"""Exchange persistent fields at a causal cut while retaining all receiver signals.

Development-only intervention. Unlike state_exchange/1 this explicitly allows
in-flight signals, retains them byte-for-byte, and cannot exchange fast states.
"""

import argparse
import copy
import gzip
import json
from pathlib import Path

from lab.tools.state_exchange import EDGE_HISTORY, IDENTICAL, NODE_HISTORY, read_image
from threemind_core import StateImage
from threemind_runtime import create_engine

GROUPS = ("W", "S", "N")


def exchange_cut(recipient, donor, groups=(), *, backend="native"):
    groups = tuple(groups)
    if len(set(groups)) != len(groups) or any(g not in GROUPS for g in groups):
        raise ValueError("only distinct W, S, N groups are supported")
    a, b = recipient.to_dict(), donor.to_dict()
    if a.get("schema") != "threemind.continuous-memory-state/2":
        raise ValueError("continuous-memory-state/2 required")
    if any(a[k] != b[k] for k in IDENTICAL):
        raise ValueError("configuration, lifecycle, physical state or clocks differ")
    for s in (a, b):
        if s["silenced_nodes"] or s["silenced_edges"] or s["operator_state"]["novelty"]["pending"]:
            raise ValueError("silencing or unfinished novelty requires a different protocol")
        image = StateImage.from_dict(s)
        if create_engine(state=image, backend=backend).capture_state().digest != image.digest:
            raise ValueError("source does not restore exactly")

    def indices(s):
        nodes = {n["channel"]: n for n in s["nodes"]}
        channels = {n["id"]: n["channel"] for n in s["nodes"]}
        edges = {(channels[e["source"]], channels[e["target"]]): e for e in s["edges"]}
        return nodes, edges

    an, ae = indices(a)
    bn, be = indices(b)
    if an.keys() != bn.keys() or ae.keys() != be.keys():
        raise ValueError("anonymous channel set or directed topology differs")
    changes = []

    def assign(target, source, fields, location):
        for field in fields:
            if target[field] != source[field]:
                changes.append({"location": location + [field], "before": target[field], "after": source[field]})
                target[field] = copy.deepcopy(source[field])

    if "N" in groups:
        for ch, n in an.items():
            assign(n, bn[ch], NODE_HISTORY, ["node", ch])
    for pair, edge in ae.items():
        if "W" in groups:
            assign(edge, be[pair], ("weight",), ["edge", *pair])
        if "S" in groups:
            assign(edge, be[pair], EDGE_HISTORY, ["edge", *pair])
    image = StateImage.from_dict(a)
    if create_engine(state=image, backend=backend).capture_state().digest != image.digest:
        raise ValueError("intervention does not restore exactly")
    original = recipient.to_dict()
    retained = [k for k in a if k not in ("nodes", "edges")]
    assert all(a[k] == original[k] for k in retained)
    assert groups or image.digest == recipient.digest
    return image, {
        "schema": "threemind.research-state-exchange-cut/1",
        "artificial_intervention": True,
        "natural_learning": False,
        "groups": [g for g in GROUPS if g in groups],
        "recipient_sha256": recipient.digest,
        "donor_sha256": donor.digest,
        "after_sha256": image.digest,
        "time_us": a["time_us"],
        "alignment": "anonymous channels; recipient ids and all in-flight signals retained",
        "retained_queue_events": len(a["queue"]),
        "retained_traversed_edges": len(a["traversed"]),
        "unchanged_global_state": retained,
        "changes": changes,
    }


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
        p.error("output and receipt must be new files")
    image, audit = exchange_cut(read_image(args.recipient), read_image(args.donor), args.groups, backend=args.backend)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open("x", encoding="utf-8") as out:
        json.dump(audit, out, ensure_ascii=False, indent=2, allow_nan=False)
    with args.output.open("xb") as out:
        out.write(gzip.compress(image.payload) if args.output.suffix == ".gz" else image.payload)
    print(json.dumps({"output": str(args.output), "receipt": str(receipt), "state_sha256": image.digest}))


if __name__ == "__main__":
    main()
