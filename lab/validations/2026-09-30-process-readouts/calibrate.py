"""Re-analyze existing complete evidence. Never create/train a consciousness or edit old results."""

import gzip
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from threemind_runtime.observation_tools import analyze_record

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / ".work/memory-transfer-20260930/cases"
DEST = ROOT / ".work/process-readout-calibration-20260930"


def main():
    start = time.monotonic()
    DEST.mkdir(exist_ok=True)
    rows, evidence = [], {}

    def read(path, zipped=False):
        raw = path.read_bytes()
        evidence[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
        return gzip.decompress(raw) if zipped else raw

    for path in sorted(SOURCE.rglob("trajectory.json.gz")):
        if time.monotonic() - start > 120:
            raise RuntimeError("calibration wall budget reached; no new simulations were started")
        if len(rows) >= 2000:
            raise RuntimeError("calibration case budget reached")
        meta = json.loads(read(path.parent / "result.json"))
        event_raw = read(path.parent / "events.jsonl.gz", True)
        windows = [
            r["payload"]
            for r in map(json.loads, event_raw.splitlines())
            if r["kind"] == "temporal_readout" and r["payload"].get("analysis_schema")
        ]
        if not windows:
            continue
        trajectory = json.loads(read(path, True))
        channels = {n["channel"]: n["id"] for p in trajectory for n in p["nodes"]}
        for window in windows:
            before = json.dumps(window, sort_keys=True)
            derived = analyze_record(window)
            assert json.dumps(window, sort_keys=True) == before
            nodes = {n["node_id"]: n for n in derived["nodes"]}
            targets = [channels.get(ch) for ch in meta["extra"].get("targets", [])]
            decisions = {n["node_id"]: n["activation"] for n in (window.get("primary_result") or {}).get("nodes", [])}
            timeline = derived["process"].pop("timeline", [])
            rows.append(
                {
                    "case": meta["key"],
                    "family": meta["extra"].get("family"),
                    "stage": meta["extra"].get("stage"),
                    "cue": meta["extra"].get("cue"),
                    "window_id": window["window_id"],
                    "source_sha256": derived["source_sha256"],
                    "classification": window["classification"],
                    "process": derived["process"],
                    "targets": [
                        {"node_id": ident, "decision_activation": decisions.get(ident, 0), **nodes.get(ident, {})}
                        for ident in targets
                    ],
                    "changed_sample_count": sum(
                        (p["step_increase"] or 0) + (p["step_decrease"] or 0) > 1e-12 for p in timeline
                    ),
                }
            )
    # A checksum is independently re-read, not only assumed from read-only code.
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in evidence.items())
    summaries = {}
    for family in sorted({r["family"] for r in rows}):
        group = [r for r in rows if r["family"] == family]
        summaries[family] = {
            "windows": len(group),
            "classifications": dict(Counter(r["classification"] for r in group)),
            "with_activity": sum(r["process"]["raw_activity_seen"] for r in group),
            "with_dynamic_change": sum(r["changed_sample_count"] > 0 for r in group),
            "with_target_process_activity": sum(
                any(n.get("process_peak_activation", 0) > 1e-12 for n in r["targets"]) for r in group
            ),
            "with_target_at_decision": sum(any(n["decision_activation"] > 1e-12 for n in r["targets"]) for r in group),
        }
    result = {
        "schema": "threemind.process-calibration/1",
        "windows": len(rows),
        "summaries": summaries,
        "source_files": evidence,
        "all_source_hashes_unchanged": True,
        "new_simulations": 0,
        "wall_seconds": time.monotonic() - start,
        "rows": rows,
    }
    body = json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2).encode()
    if len(body) > 256 * 1024**2:
        raise RuntimeError("calibration evidence budget reached")
    with (DEST / "calibration.json").open("xb") as out:
        out.write(body)
    print(
        json.dumps(
            {"windows": len(rows), "summaries": summaries, "wall_seconds": result["wall_seconds"], "bytes": len(body)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
