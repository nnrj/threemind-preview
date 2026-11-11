"""Read E67/E68 originals to audit kernel costs; never instantiate a model.

Only standard-library JSON/gzip decoding is used. The sole output must be
inside this checkout's ignored .work directory. No original is rewritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import statistics


REPO = Path(__file__).resolve().parents[1]
ARMS = ("2", "3.1", "4-adaptive", "4-legacy")
E67 = "2026-10-11-shape-color-kernels"
E68 = "2026-10-13-continuous-shape-color"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def document(path: Path):
    raw = path.read_bytes()
    decoded = gzip.decompress(raw) if path.suffix == ".gz" else raw
    return json.loads(decoded), {"path": str(path), "sha256": digest(raw), "bytes": len(raw)}


def audit_of(core: dict) -> dict:
    return core.get("audit", core.get("operator_state", {}).get("retention", {}).get("audit", {}))


def queue_summary(core: dict) -> dict:
    queue = core["queue"]
    signals = [event for event in queue if event["kind"] == "signal"]
    sizes = [len({message[1] for message in event["payload"]["messages"]}) for event in signals]
    return {
        "queue_events": len(queue),
        "timer_items": len(core["timers"]),
        "queue_kinds": dict(Counter(event["kind"] for event in queue)),
        "signal_arrival_times_us": dict(Counter(event["time_us"] for event in signals)),
        "signal_messages": sum(len(event["payload"]["messages"]) for event in signals),
        "distinct_recipients_per_packet": {
            "min": min(sizes) if sizes else None,
            "max": max(sizes) if sizes else None,
            "median": statistics.median(sizes) if sizes else None,
            "distribution": dict(sorted(Counter(sizes).items())),
        },
        "candidate_ordered_pairs_before_receive_gates": sum(k * (k - 1) for k in sizes),
        "interpretation": "Pending packets only; receive gates can shrink the cohort. This is not a count of executed learning pairs. Metrics pending_events includes timers as well as queued packets.",
    }


def stage_input(folder: Path, start_us: int, end_us: int) -> dict:
    inputs = hashlib.sha256()
    times = hashlib.sha256()
    files = hashlib.sha256()
    count = 0
    first = last = None
    uniform_50ms = True
    paths = sorted((folder / "clips").glob("*.json.gz"))
    if not paths:
        raise ValueError(f"No clips: {folder}")
    for path in paths:
        clip, source = document(path)
        files.update(f"{path.name}\t{source['sha256']}\n".encode())
        for frame in clip["process"]:
            payload = json.dumps(frame["stimulus"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            inputs.update(payload.encode("utf-8") + b"\n")
            time_us = int(frame["activity"]["time_us"])
            times.update(f"{time_us}\n".encode())
            count += 1
            uniform_50ms &= time_us == start_us + count * 50_000
            if first is None:
                first = time_us
            last = time_us
    return {
        "source_directory": str(folder / "clips"),
        "clips": len(paths),
        "frames": count,
        "stimulus_sha256": inputs.hexdigest(),
        "stimulus_hash_encoding": "Per-frame stimulus JSON, sort_keys=True, separators=(',', ':'), ensure_ascii=False, UTF-8, then newline; ordered by clip filename and process order.",
        "activity_times_sha256": times.hexdigest(),
        "clip_bytes_manifest_sha256": files.hexdigest(),
        "clip_manifest_encoding": "For each sorted filename: name, tab, compressed-file SHA256, newline, UTF-8.",
        "first_activity_time_us": first,
        "last_activity_time_us": last,
        "uniform_50ms_from_stage_start": uniform_50ms,
        "ends_at_stage_end": last == end_us,
        "time_note": "stimulus.time_us is relative zero in these originals; activity.time_us is the actual model time and is hashed separately.",
    }


def stage_costs(root: Path, arm: str) -> dict:
    folder = root / "arms" / arm / "correction-1"
    result, result_source = document(folder / "result.json")
    initial, initial_source = document(root / "arms" / arm / "initial-teaching" / "result.json")
    saved, saved_source = document(folder / "system" / "system.json.gz")
    core = saved["session"]["core"]
    if int(core["time_us"]) != result["end_us"]:
        raise ValueError(f"Saved state and stage endpoint disagree: {arm}")
    initial_audit = initial["metrics"].get("local_audit", initial["metrics"].get("retention", {}))
    final_audit = audit_of(core)
    counters = {key: value - initial_audit[key] for key, value in final_audit.items()
                if key in initial_audit and isinstance(value, (int, float))}
    # Audit dictionaries include counters only; never subtract derived maxima.
    timing = result["timing"]
    out = {
        "sources": {"result": result_source, "initial_result": initial_source, "checkpoint": saved_source},
        "identity": result["identity"],
        "kernel": result["kernel"],
        "start_us": result["start_us"],
        "end_us": result["end_us"],
        "sim_seconds": result["sim_s"],
        "lessons": result["lessons"],
        "nodes": len(core["nodes"]),
        "edges": len(core["edges"]),
        "timing_raw": timing,
        "timing_seconds": {key.removesuffix("_ns"): value / 1e9 for key, value in timing.items() if key.endswith("_ns")},
        "wall_seconds": result["wall_seconds"],
        "audit_end": final_audit,
        "audit_stage_delta": counters,
        "inputs": stage_input(folder, result["start_us"], result["end_us"]),
    }
    if arm.startswith("4-"):
        out["pending"] = queue_summary(core)
    print(f"Audited E67 {arm}: {out['inputs']['frames']} recorded input frames", flush=True)
    return out


def final_costs(root: Path) -> dict:
    verified, source = document(root / "analysis" / "verified-results.json")
    rows = {}
    for arm in ("2", "3.1"):
        item = verified["arms"][arm]
        boundary = (root / item["final_checkpoint"]).resolve()
        if not boundary.is_relative_to(root.resolve()):
            raise ValueError(f"Final checkpoint is outside the experiment: {arm}")
        saved, saved_source = document(boundary / "system.json.gz")
        core = saved["session"]["core"]
        rows[arm] = {
            "checkpoint": saved_source,
            "time_us": core["time_us"],
            "identity": item["identity"],
            "nodes": len(core["nodes"]),
            "edges": len(core["edges"]),
            "audit": audit_of(core),
            "surviving_node_touches_sum": sum(node.get("touches", 0) for node in core["nodes"]),
            "surviving_edge_touches_sum": sum(edge.get("touches", 0) for edge in core["edges"]),
            "touches_note": "Sum over surviving objects only. Deleted objects' histories are absent; this is not a total count of all lifetime learning or settlement calls.",
            "timing": item["timing"],
            "frames": item["frames"],
            "sim_seconds": item["sim_seconds"],
        }
    return {"source": source, "arms": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path(r"E:\ThreeMindData"))
    parser.add_argument("--output", type=Path, default=REPO / ".work/kernel-performance-20261013/formal-evidence.json")
    args = parser.parse_args()
    output = args.output.resolve()
    work = (REPO / ".work").resolve()
    data_root = args.data_root.resolve()
    if not output.is_relative_to(work) or output.is_relative_to(data_root):
        parser.error("Output must be inside this repository's .work, outside the original data root.")
    if not output.parent.is_dir():
        parser.error("Create the ignored output directory before running this audit.")
    if output.exists():
        parser.error("Output already exists; choose another ignored filename to preserve prior audit evidence.")
    experiments = data_root / "experiments"
    binaries = {}
    for name in (E67, E68):
        platform, source = document(experiments / name / "platform.json")
        binaries[name] = {"source": source, "native_binary_sha256": platform["implementation"]["native_binary_sha256"]}
    for name, path in {
        "installed_pyd": REPO / ".work/kernel-venv/Lib/site-packages/_threemind_native/_threemind_native.pyd",
        "release_dll": REPO / "target/release/_threemind_native.dll",
    }.items():
        binaries[name] = {"path": str(path), "exists": path.exists()}
        if path.exists():
            raw = path.read_bytes()
            binaries[name].update(sha256=digest(raw), bytes=len(raw))
    rows = {arm: stage_costs(experiments / E67, arm) for arm in ARMS}
    matches = {
        "identical_stimulus_payloads": len({row["inputs"]["stimulus_sha256"] for row in rows.values()}) == 1,
        "identical_actual_activity_times": len({row["inputs"]["activity_times_sha256"] for row in rows.values()}) == 1,
        "all_regular_50ms": all(row["inputs"]["uniform_50ms_from_stage_start"] for row in rows.values()),
        "all_endpoints_match": all(row["inputs"]["ends_at_stage_end"] for row in rows.values()),
    }
    if not all(matches.values()):
        raise ValueError(f"Input/time matching failed: {matches}")
    result = {
        "schema": "threemind.kernel-stage-cost-audit/1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_loaded": False,
        "model_restored": False,
        "model_advanced": False,
        "originals_modified": False,
        "data_root": str(data_root),
        "e67_correction_1": rows,
        "matching": matches,
        "e68_final": final_costs(experiments / E68),
        "native_binaries": binaries,
        "limitations": [
            "Read-only documentary audit, not a new timing experiment or function-level CPU profile.",
            "Native advance timers include call and returned encoding overhead. Observations, saves and restoration are reported separately; nested timers must not be added.",
            "The E67 correction-1 teaching segment is continuous; this audit does not validate E67's separate per-question restored evaluations as continuous consciousness tests.",
            "E67 adaptive initial-teaching wall_seconds starts at its resumed invocation, while Meter counters include prior saved work. Do not compare that wall timer with cumulative counters.",
            "Audit visit counters have implementation-specific semantics; compare measured work without treating counts as CPU fractions.",
            "The older deferred-4-performance review precedes later E67 progress. Both /4 lines eventually stopped at 472.5 seconds; neither completed the full study.",
        ],
    }
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": str(output), "matching": matches}, ensure_ascii=False))


if __name__ == "__main__":
    main()
