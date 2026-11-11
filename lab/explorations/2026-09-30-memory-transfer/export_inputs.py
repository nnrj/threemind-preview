"""Portable input evidence through the existing public streaming exporter."""

import copy
import gzip
import hashlib
import itertools
import json
import math
import time
from collections import Counter

from common import WORK, new_json, read_json
from publication_base import Publisher

from threemind_lab.inputs import digest, export_stream

SENSOR_KINDS = {"accelerometer", "gyroscope", "joint_position", "joint_velocity"}


def normalize_zero(value):
    if isinstance(value, float) and value == 0:
        return 0.0
    if isinstance(value, list):
        return [normalize_zero(v) for v in value]
    if isinstance(value, dict):
        return {k: normalize_zero(v) for k, v in value.items()}
    return value


def zero_sign_differences(left, right, path=""):
    """Fail closed on any change other than a floating zero's sign."""
    assert type(left) is type(right), (path, "type changed")
    if isinstance(left, dict):
        assert left.keys() == right.keys(), (path, "keys changed")
        return [p for k in left for p in zero_sign_differences(left[k], right[k], path + "/" + k)]
    if isinstance(left, list):
        assert len(left) == len(right), (path, "length changed")
        return [p for i, (a, b) in enumerate(zip(left, right)) for p in zero_sign_differences(a, b, path + f"/{i}")]
    assert left == right, (path, "numeric or textual value changed")
    if isinstance(left, float) and left == 0 and math.copysign(1, left) != math.copysign(1, right):
        return [path]
    return []


def add_measurements(index, measurements, source):
    key = digest(normalize_zero(measurements))
    original = digest(measurements)
    index.setdefault(key, {}).setdefault(original, {"measurements": measurements, "source": source})


def recover_payload(row, index):
    """Recover only from recorded physical samples, never guess zero signs."""
    payload = row["payload"]
    if digest(payload) == row["payload_hash"]:
        return None
    options = []
    for unit in payload.get("units", []):
        slots = [i for i, m in enumerate(unit.get("measurements", [])) if m.get("kind") in SENSOR_KINDS]
        raw = [unit["measurements"][i] for i in slots]
        candidates = index.get(digest(normalize_zero(raw)), {})
        assert candidates, (row["id"], "original physical measurements unavailable")
        options.append([(slots, value) for value in candidates.values()])
    assert options and math.prod(len(v) for v in options) <= 32, "ambiguous original samples"
    for selection in itertools.product(*options):
        original = copy.deepcopy(payload)
        sources = []
        for unit, (slots, candidate) in zip(original["units"], selection):
            for slot, measurement in zip(slots, candidate["measurements"]):
                unit["measurements"][slot] = measurement
            sources.append(candidate["source"])
        if digest(original) != row["payload_hash"]:
            continue
        paths = zero_sign_differences(payload, original)
        assert paths and all("/measurements/" in p for p in paths), "input changed beyond measurement metadata"
        return {
            "envelope_id": row["id"],
            "original_payload": original,
            "original_payload_hash": row["payload_hash"],
            "database_payload_hash": digest(payload),
            "zero_sign_paths": paths,
            "source_recordings": sources,
            "core_input_unchanged": True,
        }
    raise AssertionError((row["id"], "original hash not recoverable from physical evidence"))


def main():
    study = Publisher()
    try:
        entries = []
        totals = Counter()
        original_index = {}
        for path in sorted((WORK / "materials").glob("*.json")):
            for i, unit in enumerate(read_json(path)["units"]):
                add_measurements(
                    original_index, unit["measurements"], f"{path.relative_to(WORK).as_posix()}#/units/{i}"
                )
        for result in sorted((WORK / "cases").rglob("result.json")):
            case = read_json(result)
            index = {k: dict(v) for k, v in original_index.items()}
            physics = result.parent / "physics.json.gz"
            if physics.exists():
                episodes = json.loads(gzip.decompress(physics.read_bytes()))
                for i, episode in enumerate(episodes):
                    for j, sample in enumerate(episode["rows"]):
                        add_measurements(
                            index, sample["measurements"], f"{physics.relative_to(WORK).as_posix()}#/{i}/rows/{j}"
                        )
            recoveries = []
            expected_frames = 0
            for kind in ("envelopes", "frames"):
                path = result.parent / f"inputs-{kind}.jsonl.gz"
                if not path.exists():
                    staging = path.with_suffix(f".partial-{time.time_ns()}")
                    with gzip.open(staging, "xb", compresslevel=6) as out:
                        for i, line in enumerate(
                            export_stream(study.db, study.project, case["id"], records=kind, format="jsonl")
                        ):
                            if i % 1000 == 0:
                                study.guard()
                            out.write(line.encode("utf-8"))
                    staging.rename(path)
                count = 0
                statuses = Counter()
                with gzip.open(path, "rt", encoding="utf-8") as source:
                    header = json.loads(next(source))
                    assert header["run_id"] == case["id"] and header["records"] == kind
                    for line in source:
                        row = json.loads(line)
                        assert row["run_id"] == case["id"]
                        if kind == "envelopes":
                            recovery = recover_payload(row, index)
                            if recovery is not None:
                                recoveries.append(recovery)
                            assert digest(row["configuration"]) == row["configuration_hash"]
                            expected_frames += row["frame_count"]
                        statuses[row["status"]] += 1
                        count += 1
                assert not statuses["accepted"] and not statuses["scheduled"], "unfinished input audit"
                if kind == "frames":
                    assert count == expected_frames, (case["id"], "envelope/frame count differs")
                with path.open("rb") as f:
                    sha = hashlib.file_digest(f, "sha256").hexdigest()
                entries.append(
                    {
                        "run_id": case["id"],
                        "records": kind,
                        "count": count,
                        "statuses": dict(statuses),
                        "path": path.relative_to(WORK).as_posix(),
                        "sha256": sha,
                        "bytes": path.stat().st_size,
                    }
                )
                totals[kind] += count
            if recoveries:
                path = result.parent / "inputs-original-payloads.jsonl.gz"
                if not path.exists():
                    staging = path.with_suffix(f".partial-{time.time_ns()}")
                    with gzip.open(staging, "xt", encoding="utf-8", compresslevel=6) as out:
                        for recovery in recoveries:
                            out.write(json.dumps(recovery, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
                    staging.rename(path)
                with gzip.open(path, "rt", encoding="utf-8") as source:
                    saved = [json.loads(line) for line in source]
                    assert len(saved) == len(recoveries)
                    for a, b in zip(saved, recoveries):
                        assert digest(a) == digest(b)
                        assert digest(a["original_payload"]) == a["original_payload_hash"]
                with path.open("rb") as f:
                    sha = hashlib.file_digest(f, "sha256").hexdigest()
                entries.append(
                    {
                        "run_id": case["id"],
                        "records": "original-payloads",
                        "count": len(recoveries),
                        "path": path.relative_to(WORK).as_posix(),
                        "sha256": sha,
                        "bytes": path.stat().st_size,
                    }
                )
                totals["signed_zero_recoveries"] += len(recoveries)
            totals["cases"] += 1
            if totals["cases"] % 128 == 0:
                print(json.dumps(dict(totals)), flush=True)
        with study.db.tx(study.project) as db:
            envelopes = db.execute(
                "SELECT count(*) AS n FROM input_envelopes WHERE project_id=%s", (study.project,)
            ).fetchone()["n"]
            frames = db.execute(
                "SELECT count(*) AS n FROM input_frames WHERE project_id=%s", (study.project,)
            ).fetchone()["n"]
        assert totals["envelopes"] == envelopes and totals["frames"] == frames
        value = {
            "project_id": study.project,
            "files": entries,
            "totals": dict(totals),
            "verified_payload_and_configuration_hashes": envelopes,
            "signed_zero_policy": "Database exports retained byte-for-byte as emitted by public export; original payload sidecars recovered exclusively from recorded physical samples and verified against pre-storage hashes. Every difference is a floating zero sign in measurement metadata; encoded Core inputs are unchanged. No database rows were modified.",
            "compressed_bytes": sum(e["bytes"] for e in entries),
            "unfinished_inputs": 0,
        }
        new_json(WORK / "inputs-export.json", value)
        print(
            json.dumps({"totals": dict(totals), "compressed_MiB": value["compressed_bytes"] / 2**20, "verified": True})
        )
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
