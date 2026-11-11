"""Export completed analysis to ordinary CSV without executing Core."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from statistics import mean

from runner import HERE, WORK

from lab.tools.service_study import new_json, read_json


def flattened(row, prefix=""):
    result = {}
    for key, value in row.items():
        name = prefix + key
        if isinstance(value, dict):
            result.update(flattened(value, name + "."))
        elif isinstance(value, list):
            result[name] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            result[name] = value
    return result


def main():
    memory = read_json(WORK / "analysis-final.json")
    reversal = read_json(WORK / "reversal-final.json")
    sequence = read_json(WORK / "sequence-final.json")
    comparisons = read_json(WORK / "comparisons.json")
    assert len(memory["rows"]) == 1296 and len(reversal["rows"]) == 544
    assert len(sequence["rows"]) == 576 and len(sequence["pairs"]) == 144
    assert sequence["selected_blocks"] == [100121, 100122, 100123, 100124]
    groups = defaultdict(list)
    for row in sequence["pairs"]:
        groups[tuple(row[k] for k in ("tau", "shared", "gap_s", "delay_s"))].append(row)
    order_summary = []
    for key, rows in sorted(groups.items()):
        order_summary.append(
            dict(zip(("tau", "shared", "gap_s", "delay_s"), key))
            | {
                "blocks": [r["seed"] for r in rows],
                "bidirectional_1e9": sum(r["bidirectional_1e9"] for r in rows),
                "bidirectional_1e6": sum(r["bidirectional_1e6"] for r in rows),
                "mean_AB_recency_margin": mean(r["recency_margins"][0] for r in rows),
                "mean_BA_recency_margin": mean(r["recency_margins"][1] for r in rows),
            }
        )
    tables = {
        "memory-windows": memory["rows"],
        "memory-summary": memory["summary"],
        "replacement-comparisons": comparisons["comparisons_to_i1f0"],
        "reversal-windows": reversal["rows"],
        "reversal-factorial": reversal["summary"],
        "sequence-windows": sequence["rows"],
        "sequence-state-pairs": sequence["pairs"],
        "sequence-summary": order_summary,
    }
    paths = [HERE / "tables" / (name + ".csv") for name in tables]
    if any(path.exists() for path in paths):
        raise FileExistsError("do not overwrite a previous table export")
    manifest = {}
    for (name, rows), path in zip(tables.items(), paths):
        path.parent.mkdir(exist_ok=True)
        flat = [flattened(row) for row in rows]
        fields = list(dict.fromkeys(k for row in flat for k in row))
        with path.open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(flat)
        manifest[name] = {"rows": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    new_json(WORK / "table-exports.json", manifest)
    print(json.dumps({name: row["rows"] for name, row in manifest.items()}))


if __name__ == "__main__":
    main()
