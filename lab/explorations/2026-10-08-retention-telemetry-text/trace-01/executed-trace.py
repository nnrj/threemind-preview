"""Post-result instrument replay, with an exact end-state witness."""

import gzip
import hashlib
import json
import time
from pathlib import Path

from threemind_core import Stimulus
from threemind_kernels.retention import RetentionConfig
from threemind_kernels.retention_native import NativeRetentionEngine

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def main():
    original = HERE / "run-02"
    output = HERE / "trace-01"
    output.mkdir(exist_ok=False)
    manifest = read(original / "manifest.json")
    for name, expected in manifest["kernel_sources"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    assert (
        hashlib.sha256((ROOT / ".work/native-repair/_threemind_native.pyd").read_bytes()).hexdigest()
        == manifest["native_sha256"]
    )
    channels = set(manifest["text_channels"])
    lessons = read(original / "curriculum.json")["repeat"]
    times = sorted(set(range(0, 24_000_001, 100_000)) | {t + 100_000 for t, _ in lessons} | {530_000_000})
    events = read(original / "inputs-repeat.json.gz")
    results = []
    for case in ("scheme1-repeat", "scheme2-repeat"):
        start = time.perf_counter()
        e = NativeRetentionEngine(RetentionConfig(**read(original / case / "config.json")))
        for row in events:
            e.inject(Stimulus.from_dict(row["stimulus"]))
        rows = []
        for t in times:
            e.advance_to(t)
            state = e.capture_state().to_dict()
            text_ids = {n["id"] for n in state["nodes"] if n["channel"] in channels}
            anchors = state["operator_state"]["retention"]["edges"]
            hs = [
                max(e.config.memory_half_life_min_s, h - e.config.memory_half_life_decay_rate * (t - int(at)) / 1e6)
                for a, b, h, at in anchors
                if a in text_ids and b in text_ids
            ]
            graph = e.graph()
            edges = [x for x in graph["edges"] if x["source"] in text_ids and x["target"] in text_ids]
            rows.append(
                {
                    "time_us": str(t),
                    "text_edges": len(edges),
                    "text_H_max_s": max(hs, default=None),
                    "text_weight_sum": sum(x["weight"] for x in edges),
                    "transport": state["transport"],
                }
            )
        final_hash = e.capture_state().digest
        assert final_hash == read(original / case / "t530.context.json")["state_hash"]
        result = {
            "case": case,
            "samples": len(rows),
            "sampled_text_H_max_s": max(r["text_H_max_s"] or 0 for r in rows),
            "final_hash": final_hash,
            "exact_original_state": True,
            "rows": rows,
            "wall_seconds": time.perf_counter() - start,
        }
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k != "rows"}), flush=True)
    (output / "registration.md").write_bytes((HERE / "trace-registration.md").read_bytes())
    (output / "executed-trace.py").write_bytes(Path(__file__).read_bytes())
    (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, separators=(",", ":")), "utf-8")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}
    (output / "checksums.json").write_text(json.dumps(hashes, indent=2), "utf-8")


if __name__ == "__main__":
    main()
