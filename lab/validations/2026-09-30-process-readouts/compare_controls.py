"""Use the shared full-vector comparison on the old controlled copies."""

import json
from collections import defaultdict

from calibrate import DEST, SOURCE

from threemind_runtime.observation_cli import load_record
from threemind_runtime.observation_tools import compare_records


def main():
    rows = []
    for path in sorted((SOURCE / "memory-intervention").rglob("events.jsonl.gz")):
        seed, preset, mode, cue, condition = path.relative_to(SOURCE / "memory-intervention").parts[:-1]
        control = SOURCE / "memory" / seed / preset / mode / "wait-300" / cue / "events.jsonl.gz"
        result = compare_records(load_record(path), load_record(control))
        rows.append({"case": str(path.parent.relative_to(SOURCE)), "condition": condition, **result})
    summaries = defaultdict(lambda: {"comparisons": 0, "changed": 0, "identical_samples": 0})
    for row in rows:
        s = summaries[row["condition"]]
        s["comparisons"] += 1
        s["changed"] += row["changed_node_count"] > 0
        s["identical_samples"] += row["matched_samples"] if row["maximum_l1_difference"] == 0 else 0
        assert row["left_unmatched_samples"] == row["right_unmatched_samples"] == 0
    body = json.dumps({"summaries": summaries, "comparisons": rows}, ensure_ascii=False, indent=2).encode()
    if len(body) > 64 * 1024**2:
        raise RuntimeError("comparison evidence budget reached")
    with (DEST / "controlled-comparisons.json").open("xb") as out:
        out.write(body)
    print(json.dumps({"summaries": summaries, "bytes": len(body)}))


if __name__ == "__main__":
    main()
