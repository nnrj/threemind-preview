"""Portable input audits for bounded studies, without changing stored evidence.

Keep original carrier bytes alongside JSONB exports: JSONB may normalize -0.0
in observational metadata. A normalization is reported, never silently repaired.
Decoded stimuli and delivery timing must still match exactly.
"""

from __future__ import annotations

import gzip
import json
import time

from threemind_lab.inputs import digest, export_stream
from threemind_runtime.sensory import carrier_frames


def jsonb_value_equal(a, b):
    """Permit numeric representation changes, not bool/number substitution."""
    if type(a) is not type(b):
        return type(a) in (int, float) and type(b) in (int, float) and a == b
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(jsonb_value_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(jsonb_value_equal(x, y) for x, y in zip(a, b))
    return a == b


def verify_input_bundle(study, folder, result, *, require_complete=True):
    """Audit Study's self-contained anonymous and stimulus-unit carriers.

    Text/media and other stateful adapters need their own recorded mapping
    configuration; this helper must not accidentally decode them with defaults.
    """
    if not folder.resolve().is_relative_to((study.work / "cases").resolve()):
        raise ValueError("input exports must remain in this study's case directory")
    tables = {}
    for kind in ("envelopes", "frames"):
        path = folder / f"inputs-{kind}.jsonl.gz"
        if not path.exists():
            staging = path.with_suffix(f".partial-{time.time_ns()}")
            with gzip.open(staging, "xb") as out:
                for line in export_stream(study.db, study.project, result["id"], records=kind, format="jsonl"):
                    out.write(line.encode("utf-8"))
            staging.rename(path)
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            header = json.loads(next(stream))
            assert header["run_id"] == result["id"] and header["records"] == kind
            tables[kind] = [json.loads(line) for line in stream]
        assert all(r["run_id"] == result["id"] for r in tables[kind])
    raw = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
    original_envelopes = {r["id"]: r for r in raw["envelopes"]}
    delivered = {(r["envelope_id"], r["frame_index"]): r for r in raw["delivered"]}
    scheduled = {(r["envelope_id"], r["frame_index"]): r for r in raw["frames"]}
    envelopes = {r["id"]: r for r in tables["envelopes"]}
    assert envelopes.keys() == original_envelopes.keys()
    assert len(scheduled) == len(tables["frames"]) == sum(r["frame_count"] for r in envelopes.values())
    if require_complete:
        assert len(delivered) == len(scheduled)
    assert not raw["rejected"]
    normalized = []
    decoded = {}
    for env_id, env in envelopes.items():
        original = original_envelopes[env_id]
        if original["adapter_id"] not in ("anonymous-frames", "stimulus-units"):
            raise ValueError("audit requires a supported self-contained carrier")
        for field in ("adapter_id", "adapter_version", "source", "frame_count", "channel_count"):
            assert env[field] == original[field]
        assert env["filtered_count"] == 0
        if require_complete:
            assert env["status"] == "completed"
        assert digest(original["payload"]) == original["payload_hash"] == env["payload_hash"]
        assert digest(original["configuration"]) == original["configuration_hash"] == env["configuration_hash"]
        # Value equality is not byte equality: retain both and report the distinction.
        assert jsonb_value_equal(original["payload"], env["payload"])
        assert jsonb_value_equal(original["configuration"], env["configuration"])
        for field in ("payload", "configuration"):
            if digest(env[field]) != env[field + "_hash"]:
                normalized.append({"envelope_id": env_id, "field": field})
        decoded[env_id] = list(carrier_frames(original["adapter_id"], original["payload"], result["seed"], {}))
        persisted = list(carrier_frames(env["adapter_id"], env["payload"], result["seed"], {}))
        assert len(decoded[env_id]) == env["frame_count"]
        assert [digest(f["stimulus"].to_dict()) for f in decoded[env_id]] == [
            digest(f["stimulus"].to_dict()) for f in persisted
        ]
    for row in tables["frames"]:
        original = scheduled[(row["envelope_id"], row["frame_index"])]
        assert row["input_gate"] is None
        stimulus = decoded[row["envelope_id"]][row["frame_index"]]["stimulus"].to_dict()
        assert digest(stimulus) == digest(row["stimulus"]) == digest(original["stimulus"])
        assert row["scheduled_time_us"] == row["stimulus"]["time_us"]
        if row["status"] == "delivered":
            assert (row["envelope_id"], row["frame_index"]) in delivered
            assert row["delivered_time_us"] == row["scheduled_time_us"]
        else:
            assert not require_complete and row["status"] == "scheduled" and row["delivered_time_us"] is None
    return {
        "envelopes": len(envelopes),
        "frames": len(tables["frames"]),
        "pending_frames": len(scheduled) - len(delivered),
        "metadata_normalizations": normalized,
    }
