"""Numerical summaries from complete records; never changes models or evidence."""

import gzip
import json
from collections import Counter

from common import WORK, encoded, read_json
from experiment import symbols


def gzread(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def rows():
    for path in sorted((WORK / "cases" / "execution2").rglob("result.json")):
        result = read_json(path)
        yield path.parent, result


def network(state, channels):
    ids = {n["channel"]: n["id"] for n in state["nodes"]}
    edges = {(e["source"], e["target"]): e for e in state["edges"]}
    output = {}
    for a, b in (("A", "B"), ("A", "D")):
        edge = edges.get((ids.get(channels[a]), ids.get(channels[b])), {})
        for attribute in ("weight", "stability", "eligibility", "touches"):
            output[f"{a}{b}_{attribute}"] = edge.get(attribute, 0)
    return output


def analyze():
    cases = list(rows())
    by_id = {result["id"]: folder for folder, result in cases}
    summaries = []
    for folder, result in cases:
        meta = result["extra"]
        family = meta.get("family") or result["key"].split("/")[1]
        state = gzread(folder / "parent-state.json.gz")
        channels = symbols(result["seed"])
        if meta.get("family") == "novelty":
            ch = meta.get("pattern_channels", meta.get("channels"))
            channels = dict(zip("ABDC", ch))
        entry = {
            "key": result["key"],
            "id": result["id"],
            "seed": result["seed"],
            "kernel": result["kernel"],
            "family": family,
            "stage": meta.get("stage", "training"),
            **{
                k: meta.get(k)
                for k in (
                    "age_s",
                    "protocol",
                    "condition",
                    "gain",
                    "cue_intensity",
                    "mode",
                    "dose",
                    "phase_us",
                    "phase",
                )
            },
            "wall_seconds": result["wall_seconds"],
            "saturated_fraction": result["metrics"].get("saturated_fraction"),
            "nodes": len(state["nodes"]),
            "edges": len(state["edges"]),
            "life": result["life"],
            **network(state, channels),
        }
        if "novelty" in result["metrics"]:
            entry["novelty"] = result["metrics"]["novelty"]
        if (folder / "first-window.json.gz").exists():
            first = gzread(folder / "first-window.json.gz")
            entry["first_window_novelty"] = first["operator_state"]["novelty"]["audit"]
            entry["first_window_structure"] = network(first, channels)
        if (folder / "response.json.gz").exists():
            initial = gzread(by_id[meta["parent"]] / "parent-state.json.gz")
            entry.update({"initial_" + k: v for k, v in network(initial, channels).items()})
            entry["parent_id"] = meta["parent"]
            response = gzread(folder / "response.json.gz")
            for name, channel in channels.items():
                values = [sum(n["activation"] for n in r["nodes"] if n["channel"] == channel) for r in response["rows"]]
                entry[name + "_integral"] = sum(values) * 0.1
                entry[name + "_peak"] = max(values, default=0)
            entry["control_integral"] = sum(r["control"] for r in response["rows"]) * 0.1
            entry["travel"] = response["final_body"]["x"]
            reads = [
                r["payload"]
                for r in map(json.loads, gzip.decompress((folder / "events.jsonl.gz").read_bytes()).splitlines())
                if r["kind"] == "temporal_readout"
            ]
            old = next((r for r in reads if not r.get("analysis_schema")), {})
            new = next((r for r in reads if r.get("analysis_schema")), {})
            entry["old_class"] = old.get("classification")
            entry["new_class"] = new.get("classification")
            entry["pattern_status"] = new.get("analyses", {}).get("pattern", {}).get("status")
            entry["rank_time_us"] = new.get("ranking_time_us")
            ids = {n["channel"]: n["id"] for n in state["nodes"]}
            ranked = (new.get("primary_result") or {}).get("nodes", [])
            for name, channel in channels.items():
                node_id = ids.get(channel)
                positions = [i + 1 for i, n in enumerate(ranked) if n["node_id"] == node_id]
                entry[name + "_rank"] = positions[0] if positions else None
                entry[name + "_decision_activation"] = next(
                    (n["activation"] for n in ranked if n["node_id"] == node_id), 0
                )
        summaries.append(entry)
    # Cue and no-cue have their own complete cloned histories. Subtraction is an external measurement only.
    for entry in summaries:
        if entry["stage"] != "probe" or not entry.get("cue_intensity"):
            continue
        matched = [
            e
            for e in summaries
            if e["stage"] == "probe"
            and e.get("cue_intensity") == 0
            and all(
                e.get(k) == entry.get(k)
                for k in (
                    "seed",
                    "family",
                    "protocol",
                    "condition",
                    "gain",
                    "age_s",
                    "mode",
                    "dose",
                    "phase_us",
                    "phase",
                )
            )
        ]
        if len(matched) == 1:
            control = matched[0]
            for name in "ABCD":
                entry[name + "_cue_integral"] = entry[name + "_integral"] - control[name + "_integral"]
            entry["cue_control_integral"] = entry["control_integral"] - control["control_integral"]
            entry["no_cue_id"] = control["id"]
    output = {
        "cases": len(summaries),
        "compute_seconds": sum(e["wall_seconds"] for e in summaries),
        "families": dict(Counter(str(e["family"]) for e in summaries)),
        "new_classes": dict(Counter(str(e.get("new_class")) for e in summaries if e["stage"] == "probe")),
        "rows": summaries,
    }
    (WORK / "analysis-current.json").write_bytes(encoded(output))
    print(json.dumps({k: v for k, v in output.items() if k != "rows"}))
    return output


if __name__ == "__main__":
    analyze()
