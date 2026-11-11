"""Post-result, read-only replay; never writes back to a mainline subject."""

import gzip
import hashlib
import json
from pathlib import Path

from threemind_core import StateImage, Stimulus
from threemind_kernels.local import LocalConfig
from threemind_kernels.local_native import NativeLocalEngine
from threemind_runtime import create_engine
from threemind_runtime.sensory import TextSensor, TextSensorConfig


def main():
    root = Path(__file__).resolve().parents[3]
    folder = root / ".work/local-v4-validation-20261009"
    sensor = TextSensor(
        20261004, TextSensorConfig(encoding="literal-character", frame_characters=2, frame_interval_us=50000)
    )
    labels = {
        int(k): "".join(v)
        for text in ("苹果是红色的。", "树叶是绿色的。")
        for f in sensor.frames(text)
        for k, v in f["labels"].items()
    }

    def image(label, seconds):
        return StateImage.from_dict(
            json.loads(gzip.decompress((folder / label / f"system-{seconds}.json.gz").read_bytes()))["core"]
        )

    rows = []
    for label in ("v3-h-repeat", "v3-stability-repeat", "v4-h-repeat", "v4-stability-repeat"):
        for seconds in (12, 132):
            engine = create_engine(state=image(label, seconds))
            graph = engine.graph()
            names = {n["id"]: labels[n["channel"]] for n in graph["nodes"] if n["channel"] in labels}
            edges = [
                {
                    "pair": names[e["source"]] + names[e["target"]],
                    "weight": e["weight"],
                    "stability": e["stability"],
                    "touches": e["touches"],
                    "half_life": e.get("half_life"),
                }
                for e in graph["edges"]
                if e["source"] in names and e["target"] in names
            ]
            rows.append({"condition": label, "time_s": seconds, "edges": edges})
    saved = image("v4-h-repeat", 12)
    ids = [n["id"] for n in saved.to_dict()["nodes"] if n["channel"] in labels]
    engine = NativeLocalEngine(LocalConfig(**saved.to_dict()["config"]))
    for s in json.loads(gzip.decompress((folder / "v4-h-repeat/inputs.json.gz").read_bytes())):
        engine.inject(Stimulus.from_dict(s))
    peak, times = 30.0, {}
    for t in range(0, 12000001, 10000):
        engine.advance_to(t)
        for edge in engine.induced_edges(ids):
            peak = max(peak, edge["half_life"])
            if int(edge["last_pass_us"]) > 0:
                times.setdefault((edge["source"], edge["target"]), set()).add(edge["last_pass_us"])
    assert engine.capture_state().digest == saved.digest
    result = {
        "design_sha256": hashlib.sha256(Path(__file__).with_name("diagnostic-design.zh.md").read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "replay_final_hash_matches": True,
        "sample_interval_us": 10000,
        "sampled_text_edge_H_max_s": peak,
        "observed_text_emission_times": sum(map(len, times.values())),
        "snapshot_comparisons": rows,
    }
    with (folder / "diagnostics.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "snapshot_comparisons"}))


if __name__ == "__main__":
    main()
