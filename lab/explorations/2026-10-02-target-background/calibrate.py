"""Reanalyze selected historical windows; never run or overwrite their models."""

import gzip
import hashlib
import json

from common import OLD, ROOT, WORK, ids, new_json, read_json, write_gzip

from threemind_runtime.observation_tools import analyze_targets


def calibrate():
    rows, hashes = [], {}
    for path in sorted((OLD / "cases/replication-v2").glob("*/*/*/dense/wait*/cue*/result.json")):
        result = read_json(path)
        folder = path.parent
        events_file, state_file = folder / "events.jsonl.gz", folder / "parent-state.json.gz"
        for source in (path, events_file, state_file):
            hashes[source.relative_to(ROOT).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
        events = [json.loads(line) for line in gzip.decompress(events_file.read_bytes()).splitlines()]
        state = json.loads(gzip.decompress(state_file.read_bytes()))
        channels = {n["channel"]: n["id"] for n in state["nodes"]}
        selected = {s: channels[ids(result["seed"])[s]] for s in "AB"}
        records = [e["payload"] for e in events if e.get("payload", {}).get("analysis_schema")]
        derived = [analyze_targets(r, node_ids=list(selected.values())) for r in records]
        rows.append(
            {
                "key": result["key"],
                "target_ids": selected,
                "probe_available": result["extra"]["probe_available"],
                "complete_window": result["extra"]["complete_window"],
                "analyses": derived,
            }
        )
    assert len(rows) == 96
    write_gzip(WORK / "calibration/old-target-analysis.json.gz", rows)
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
    new_json(WORK / "calibration/source-checksums.json", hashes)
    measured = [a for r in rows for a in r["analyses"]]
    summary = {
        "conditions": len(rows),
        "windows": len(measured),
        "active_windows": sum(a["process"]["raw_activity_seen"] for a in measured),
        "active_global_unresolved": sum(
            a["process"]["raw_activity_seen"] and a["original_classification"] == "unresolved" for a in measured
        ),
        "local_pattern": sum(a["first_pattern_convergence"] is not None for a in measured),
        "local_steady": sum(a["first_steady_convergence"] is not None for a in measured),
        "source_files_unchanged": len(hashes),
        "simulations": 0,
    }
    new_json(WORK / "calibration/summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    (WORK / "calibration").mkdir(parents=True, exist_ok=True)
    calibrate()
