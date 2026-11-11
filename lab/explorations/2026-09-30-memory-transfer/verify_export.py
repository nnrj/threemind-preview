"""Read-only check of exported payloads against actual delivered Core inputs."""

import gzip
import hashlib
import json
from collections import Counter

from common import WORK, new_json, read_json
from export_inputs import digest, zero_sign_differences

from threemind_runtime.sensory import carrier_frames


def records(path, header=True):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        if header:
            next(source)
        for line in source:
            yield json.loads(line)


def main():
    manifest = read_json(WORK / "inputs-export.json")
    totals = Counter()
    for entry in manifest["files"]:
        path = WORK / entry["path"]
        with path.open("rb") as source:
            assert hashlib.file_digest(source, "sha256").hexdigest() == entry["sha256"]
        if entry["records"] != "envelopes":
            continue
        recovered_path = path.with_name("inputs-original-payloads.jsonl.gz")
        recovered = (
            {r["envelope_id"]: r for r in records(recovered_path, header=False)} if recovered_path.exists() else {}
        )
        frames = records(path.with_name("inputs-frames.jsonl.gz"))
        for envelope in records(path):
            payload = envelope["payload"]
            if envelope["id"] in recovered:
                restored = recovered.pop(envelope["id"])
                original = restored["original_payload"]
                assert digest(payload) == restored["database_payload_hash"]
                assert digest(original) == restored["original_payload_hash"] == envelope["payload_hash"]
                assert zero_sign_differences(payload, original) == restored["zero_sign_paths"]
                assert all("/measurements/" in p for p in restored["zero_sign_paths"])
                totals["verified_original_sidecars"] += 1
            else:
                assert digest(payload) == envelope["payload_hash"]
            assert envelope["adapter_id"] in ("stimulus-units", "anonymous-frames")
            assert envelope["status"] == "completed"
            assert int(envelope["delay_us"]) == 0
            # These two already-encoded protocols do not consult seed/config.
            for i, converted in enumerate(carrier_frames(envelope["adapter_id"], payload, 0, {})):
                frame = next(frames)
                assert frame["envelope_id"] == envelope["id"] and frame["frame_index"] == i
                assert digest(converted["stimulus"].to_dict()) == digest(frame["stimulus"])
                assert frame["status"] == "delivered" and frame["input_gate"] is None
                assert frame["scheduled_time_us"] == frame["delivered_time_us"] == frame["stimulus"]["time_us"]
                totals["exact_core_inputs"] += 1
            totals["envelopes"] += 1
        assert next(frames, None) is None and not recovered
        totals["cases"] += 1
    assert totals["cases"] == manifest["totals"]["cases"]
    assert totals["exact_core_inputs"] == manifest["totals"]["frames"]
    assert totals["verified_original_sidecars"] == manifest["totals"]["signed_zero_recoveries"]
    result = dict(totals) | {"core_execution": False, "database_writes": False, "unresolved_mismatches": 0}
    new_json(WORK / "inputs-delivery-verification.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
