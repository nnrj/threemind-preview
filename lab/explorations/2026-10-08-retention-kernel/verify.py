"""Bounded, preregistered kernel instrumentation; no organism or service changes."""

import gzip
import json
import time
from pathlib import Path

from threemind_core import Stimulus
from threemind_kernels.novelty import NoveltyConfig
from threemind_kernels.novelty_native import NativeNoveltyEngine
from threemind_kernels.retention import RetentionConfig
from threemind_kernels.retention_native import NativeRetentionEngine

ROOT = Path(__file__).resolve().parent


def create(new, **settings):
    settings = {"quiescence_death_us": 10_000_000_000, **settings}
    return NativeRetentionEngine(RetentionConfig(**settings)) if new else NativeNoveltyEngine(NoveltyConfig(**settings))


def observe(engine):
    value = engine.capture_state().to_dict()
    memory = value.get("operator_state", {}).get("retention", {})
    return {
        "time_us": str(engine.time_us),
        "nodes": len(value["nodes"]),
        "edges": len(value["edges"]),
        "mean_weight": sum(e["weight"] for e in value["edges"]) / max(1, len(value["edges"])),
        "max_half_life_s": max((r[2] for r in memory.get("edges", [])), default=None),
        "max_support": max((n["support"] for n in value["nodes"]), default=0),
        "max_node_half_life_s": max((r[1] for r in memory.get("nodes", [])), default=None),
        "max_fatigue": max((r[1] for r in memory.get("fatigue", [])), default=0),
        "dormant": len(memory.get("dormant", [])),
        "revived": memory.get("audit", {}).get("revived", 0),
        "node_rejections": value["resources"]["node_capacity_rejections"],
        "edge_rejections": value["resources"]["edge_capacity_rejections"],
    }


def save(engine, name):
    state = engine.capture_state()
    path = ROOT / "checkpoints" / (name + ".json.gz")
    path.parent.mkdir(exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as output:
        json.dump(state.to_dict(), output, ensure_ascii=False, separators=(",", ":"))
    return state.digest


def main():
    result = {
        "schema": "threemind.retention-verification/1",
        "kind": "kernel instrumentation",
        "exposure": [],
        "background": [],
        "pairing": [],
    }
    for new in (False, True):
        for schedule in ("single", "strong", "repeated"):
            name = f"memory{3 if new else 2}-{schedule}"
            engine = create(new, propagation_rate=0, inhibition=False)
            started = time.perf_counter()
            times = range(0, 120_000_000, 250_000) if schedule == "repeated" else [0]
            for when in times:
                engine.inject(Stimulus(when, ((1, 0.8), (2, 0.8)), 4.0 if schedule == "strong" else 1.0))
                engine.advance_to(when)
            last = engine.time_us
            observations = []
            for delay in (100_000, 30_000_000, 300_000_000, 1_800_000_000):
                engine.advance_to(last + delay)
                observations.append({"delay_s": delay / 1e6, **observe(engine)})
            result["exposure"].append(
                {
                    "name": name,
                    "observations": observations,
                    "state_digest": save(engine, name),
                    "wall_s": time.perf_counter() - started,
                }
            )
            print(name, flush=True)
    modes = [
        ("memory2", False, {}),
        ("automatic", True, {}),
        ("manual", True, {"node_retention_mode": "manual"}),
        ("dormant", True, {"dormant_traces_enabled": True}),
        ("revival", True, {"dormant_traces_enabled": True, "revival_enabled": True}),
    ]
    for alphabet in ("fixed", "expanding"):
        for mode, new, settings in modes:
            name = f"{alphabet}-{mode}"
            engine = create(new, max_nodes=128, max_edges=512, **settings)
            started = time.perf_counter()
            for step in range(60):
                channels = (
                    (1 + (step * 17) % 32, 1 + (step * 17 + 7) % 32)
                    if alphabet == "fixed"
                    else (step * 2 + 1, step * 2 + 2)
                )
                engine.inject(Stimulus(step * 2_000_000, tuple((n, 0.3) for n in channels)))
                engine.advance_to(step * 2_000_000)
            engine.advance_to(120_000_000)
            trained = observe(engine)
            engine.advance_to(420_000_000)
            result["background"].append(
                {
                    "name": name,
                    "at_input_end": trained,
                    "after_300s": observe(engine),
                    "state_digest": save(engine, name),
                    "wall_s": time.perf_counter() - started,
                }
            )
            print(name, flush=True)
    for new in (False, True):
        engine = create(new, propagation_rate=0, inhibition=False)
        for step in range(160):
            when = step * 250_000
            engine.inject(Stimulus(when, ((1, 0.8), (2 if step < 80 else 3, 0.8))))
            engine.advance_to(when)
        observations = []
        for when in (40_000_000, 340_000_000):
            engine.advance_to(when)
            observations.append(
                {
                    **observe(engine),
                    "weights": [
                        [e["source"], e["target"], e["weight"]] for e in engine.capture_state().to_dict()["edges"]
                    ],
                }
            )
        name = f"pairing-memory{3 if new else 2}"
        result["pairing"].append({"name": name, "observations": observations, "state_digest": save(engine, name)})
        print(name, flush=True)
    (ROOT / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
