"""Bounded read-only calibration of new response extraction on archived evidence."""

import csv
import gzip
import hashlib
import json
import shutil
import time
from collections import Counter
from pathlib import Path

import psutil

from threemind_runtime.adapters import channel_id
from threemind_runtime.observation_tools import analyze_responses, analyze_targets

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/response-readout-20261002/verified"
GIB = 1024**3


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    if (WORK / "summary.json").exists():
        raise RuntimeError("analysis already completed; preserve its evidence")
    WORK.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    sources, rows, details = {}, [], []
    paths = [
        ("E23", p)
        for p in sorted(
            (ROOT / ".work/observation-background-20261001/cases/replication-v2").glob(
                "*/*/*/dense/wait*/cue*/result.json"
            )
        )
    ]
    for group in ("matrix", "expression", "live"):
        paths.extend(
            ("E24-" + group, p)
            for p in sorted((ROOT / f".work/target-background-20261002/cases/{group}").rglob("result.json"))
            if p.parent.name != "train"
        )
    assert len(paths) <= 400
    peak_rss = 0
    for study, path in paths:
        peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
        if time.monotonic() - started > 600 or peak_rss > 2 * GIB or psutil.virtual_memory().available < 2 * GIB:
            raise RuntimeError("offline time or memory budget")
        if shutil.disk_usage("C:/").free < 5 * GIB or shutil.disk_usage("E:/").free < 15 * GIB:
            raise RuntimeError("disk reserve")
        source_files = [path, path.with_name("events.jsonl.gz"), path.with_name("parent-state.json.gz")]
        for source in source_files:
            sources[source.relative_to(ROOT).as_posix()] = digest(source)
        result = json.loads(path.read_bytes())
        state = json.loads(gzip.decompress(source_files[2].read_bytes()))
        channels = {n["channel"]: n["id"] for n in state["nodes"]}
        targets = {s: channels[channel_id(result["seed"], "priority-memory/1", i)] for i, s in enumerate("AB")}
        events = [json.loads(l) for l in gzip.decompress(source_files[1].read_bytes()).splitlines()]
        records = [e["payload"] for e in events if e.get("payload", {}).get("analysis_schema")]
        assert len(records) <= 1, (study, result["key"], len(records))
        cue = result["extra"].get("cue")
        if isinstance(cue, str):
            assert cue in ("X", "none"), cue
            cue = cue == "X"
        assert not records or type(cue) is bool, (study, result["key"], cue)
        row = {"study": study, "key": result["key"], "available": bool(records), "cue": cue, "window": None}
        if records:
            record = records[0]
            new = analyze_responses(record, node_ids=list(targets.values()))
            old = analyze_targets(record, node_ids=list(targets.values()))
            selected = new["events"][new["strongest_event_index"]] if new["events"] else None
            # Every output must be an actual simultaneous source state.
            for event in new["events"]:
                vector = record["series"][event["sample_index"]]["activation_vector"]
                expected = sorted(
                    (
                        {"node_id": i, "activation": vector.get(str(i), 0)}
                        for i in targets.values()
                        if vector.get(str(i), 0) > 0
                    ),
                    key=lambda n: (-n["activation"], n["node_id"]),
                )
                assert event["ranking"] == expected
            assert new["raw_activity_seen"] == old["process"]["raw_activity_seen"]
            row |= {
                "window": record["window_id"],
                "source_sha256": new["source_sha256"],
                "original_global": record["classification"],
                "response": new["status"] == "response_observed",
                "old_pattern_stable": old["first_pattern_convergence"] is not None,
                "old_amplitude_stable": old["first_steady_convergence"] is not None,
                "response_count": new["event_count"],
                "episode_count": new["episode_count"],
                "single_point_episodes": sum(e["sample_count"] == 1 for e in new["episodes"]),
                "observed_peaks": sum("observed_peak" in e["reasons"] for e in new["events"]),
                "maximum_time_us": selected["time_us"] if selected else None,
                "A_at_maximum": next((n["activation"] for n in selected["ranking"] if n["node_id"] == targets["A"]), 0)
                if selected
                else None,
                "B_at_maximum": next((n["activation"] for n in selected["ranking"] if n["node_id"] == targets["B"]), 0)
                if selected
                else None,
            }
            details.append({"study": study, "key": result["key"], "target_ids": targets, "analysis": new})
        rows.append(row)
    assert all(digest(ROOT / name) == sha for name, sha in sources.items())
    observed = [r for r in rows if r["available"]]
    summary = {
        "cases": len(rows),
        "windows": len(observed),
        "unavailable": len(rows) - len(observed),
        "responses": sum(r["response"] for r in observed),
        "old_pattern_stable": sum(r["old_pattern_stable"] for r in observed),
        "old_amplitude_stable": sum(r["old_amplitude_stable"] for r in observed),
        "response_global_unresolved": sum(r["response"] and r["original_global"] == "unresolved" for r in observed),
        "uncued_windows": sum(not r["cue"] for r in observed),
        "uncued_target_responses": sum(not r["cue"] and r["response"] for r in observed),
        "single_point_episodes": sum(r["single_point_episodes"] for r in observed),
        "observed_peaks": sum(r["observed_peaks"] for r in observed),
        "groups": {
            s: {
                "cases": sum(r["study"] == s for r in rows),
                "windows": sum(r["study"] == s for r in observed),
                "responses": sum(r["study"] == s and r["response"] for r in observed),
            }
            for s in sorted({r["study"] for r in rows})
        },
        "classifications": dict(Counter(r["original_global"] for r in observed)),
        "verified_original_files": len(sources),
        "simulations": 0,
        "wall_seconds": time.monotonic() - started,
        "peak_rss_bytes": peak_rss,
    }
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (WORK / "windows.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    data = json.dumps(details, ensure_ascii=False, allow_nan=False).encode()
    if len(data) > 256 * 1024**2:
        raise RuntimeError("derived evidence size budget")
    (WORK / "responses.json.gz").write_bytes(gzip.compress(data, mtime=0))
    (WORK / "source-checksums.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    summary["new_evidence_bytes"] = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
    assert summary["new_evidence_bytes"] < 512 * 1024**2
    (WORK / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
