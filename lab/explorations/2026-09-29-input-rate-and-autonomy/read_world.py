"""Apply the existing temporal reader to saved world samples without running a Core."""

import gzip
import hashlib
import json
from collections import Counter
from uuid import UUID, uuid5

from common import TEMPORAL, WORK, encoded, new_json

from threemind_runtime.readout_config import TemporalReadoutConfig
from threemind_runtime.readouts import TemporalReader


def run():
    # Default live observers exclude ambient-triggered windows. Do not rename
    # the source to 'manual' to evade that setting. This separately named,
    # post-hoc observational product opens actual ring frames explicitly.
    config = dict(TEMPORAL, trigger_ambient=True)
    registration = {
        "schema": "ring-observation-reanalysis/1",
        "configuration": config,
        "scope": "all 48 held-out normal world trials",
        "sampling_us": 100000,
        "observed_until_relative_us": 59900000,
        "notes": "Post-hoc reader on saved 100 ms samples. Background remains in node states; only ring frames open windows. Observer sequence is sample index, not Core event sequence. No interpolation or rerun.",
        "runner_sha256": hashlib.sha256(__import__("pathlib").Path(__file__).read_bytes()).hexdigest(),
    }
    path = WORK / "world-readout-registration.json"
    if not path.exists():
        new_json(path, registration)
    elif json.loads(path.read_bytes()) != registration:
        raise RuntimeError("readout reanalysis registration differs")
    summary = []
    selection = json.loads((WORK / "selection-results.json").read_bytes())
    for item in selection["held_out"]:
        folder = WORK / "cases" / item["key"]
        evidence = folder / "world.json.gz"
        data = json.loads(gzip.decompress(evidence.read_bytes()))
        reader = TemporalReader(TemporalReadoutConfig(**config))
        output = []
        for i, row in enumerate(data["rows"]):
            at = row["relative_us"]
            deliveries = [
                {
                    "envelope_id": str(uuid5(UUID(item["id"]), f"ring:{at}")),
                    "delivered_time_us": str(at),
                    "frame_index": 0,
                    "frame_count": 1,
                    "last_scheduled_index": 0,
                    "source": "ring-study",
                    "adapter_id": "ring-study",
                }
            ]
            if at % 1000000:
                deliveries = []
            output.extend(reader.consume(at, i + 1, row["nodes"], deliveries))
        output.extend(reader.close(data["rows"][-1]["relative_us"], "saved_samples_end"))
        target = WORK / "derived-readouts" / (item["id"] + ".jsonl.gz")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with gzip.open(target, "xb") as f:
                for window in output:
                    window["end_activation_ranking"] = sorted(
                        window["nodes"], key=lambda n: (-n["last_activation"], n["node_id"])
                    )
                    f.write(encoded(window) + b"\n")
        summary.append(
            {
                "run": item["id"],
                "key": item["key"],
                "source_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                "classifications": dict(Counter(w["classification"] for w in output)),
                "windows": len(output),
                "path": target.relative_to(WORK).as_posix(),
            }
        )
    (WORK / "world-readout-analysis.json").write_bytes(encoded(summary))
    counts = Counter()
    for r in summary:
        counts.update(r["classifications"])
    print(json.dumps({"cases": len(summary), "windows": dict(counts)}), flush=True)


if __name__ == "__main__":
    run()
