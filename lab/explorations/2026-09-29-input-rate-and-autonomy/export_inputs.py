"""Export only this project's saved sensory evidence using the public Lab service."""

import gzip
import hashlib
import json
from collections import Counter

from common import ROOT, WORK, Study, encoded

from threemind_lab.inputs import export_stream


def export(study):
    destination = WORK / "external-evidence"
    destination.mkdir(exist_ok=True)
    source = ROOT / ".work/candidates-20260929/host-0.jsonl"
    expected = json.loads((WORK / "rate-manifest.json").read_bytes())["background_sha256"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    for path in (source, source.with_suffix(".complete.json")):
        out = destination / path.name
        if out.exists():
            assert out.read_bytes() == path.read_bytes()
        else:
            out.write_bytes(path.read_bytes())
    counts = Counter()
    for path in sorted((WORK / "cases").rglob("result.json")):
        item = json.loads(path.read_bytes())
        for records in ("envelopes", "frames"):
            output = path.parent / f"input-{records}.jsonl.gz"
            if not output.exists():
                with gzip.open(output, "wt", encoding="utf-8") as f:
                    for line in export_stream(study.db, study.project, item["id"], records=records, format="jsonl"):
                        f.write(line)
            with gzip.open(output, "rt", encoding="utf-8") as f:
                next(f)
                for line in f:
                    row = json.loads(line)
                    counts[records] += 1
                    if records == "frames":
                        counts["frame_status:" + row["status"]] += 1
                        if row["status"] == "delivered":
                            assert int(row["scheduled_time_us"]) == int(row["delivered_time_us"])
    result = {"counts": dict(counts), "background_sha256": expected,
              "scope": "new study only; no old project export or mutation", "all_delivered_at_scheduled_time": True}
    (WORK / "input-export-audit.json").write_bytes(encoded(result))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    study = Study()
    try:
        export(study)
    finally:
        study.db.close()
