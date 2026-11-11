"""Bounded, preregistered Core calibration; complete declared subjects, no learned reader."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from threemind_core import Stimulus
from threemind_kernels.local import LocalConfig, LocalEngine
from threemind_kernels.local_native import NativeLocalEngine
from threemind_kernels.retention import RetentionConfig, RetentionEngine
from threemind_kernels.retention_native import NativeRetentionEngine
from threemind_runtime.sensory import TextSensor, TextSensorConfig

ROOT = Path(__file__).resolve().parents[3]
SEED = 20261004
SENTENCES = ("苹果是红色的。", "树叶是绿色的。")
SENSOR = TextSensorConfig(encoding="literal-character", frame_characters=2, frame_interval_us=50000)


def encoded(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(x):
    return hashlib.sha256(x).hexdigest()


def close(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a:
            close(a[k], b[k])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            close(x, y)
    elif isinstance(a, float):
        import math

        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14), (a, b)
    else:
        assert a == b, (a, b)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    begin = time.perf_counter()
    bytes_written = 0

    def write(name, obj, zipped=False):
        nonlocal bytes_written
        assert time.perf_counter() - begin < 1200, "explicit host experiment bound reached"
        data = encoded(obj)
        data = gzip.compress(data, mtime=0) if zipped else data
        if bytes_written + len(data) > 256 * 1024**2:
            raise RuntimeError("explicit evidence-size bound reached; preceding checkpoints retained")
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as f:
            f.write(data)
        bytes_written += len(data)

    source = ROOT / ".work/language-spaced-20261004/physical-telemetry.jsonl"
    physical = [
        row
        for line in source.read_bytes().splitlines()
        if (row := json.loads(line))["scope"] == "host" and int(row["time_us"]) < 44000000 and row["stimulus"]
    ]
    sensor = TextSensor(SEED, SENSOR)
    text_channels = {c for s in SENTENCES for frame in sensor.frames(s) for c, _ in frame["stimulus"].channels}
    conditions = [
        ("v3-h", 3, {}),
        ("v3-stability", 3, {"consolidation_mode": "legacy-stability"}),
        ("v4-h", 4, {}),
        ("v4-stability", 4, {"consolidation_mode": "legacy-stability"}),
    ]
    controls = [
        ("v4-scan", 4, {"propagation_mode": "scan-control"}),
        ("v4-async", 4, {"propagation_phase": "asynchronous"}),
        ("v4-sequential", 4, {"arrival_mode": "sequential"}),
        ("v4-source", 4, {"reception_mode": "legacy-source"}),
    ]
    write(
        "manifest.json",
        {
            "design_sha256": digest(Path(__file__).with_name("design.zh.md").read_bytes()),
            "source_sha256": digest(source.read_bytes()),
            "background_frames": len(physical),
            "text_sensor": asdict(SENSOR),
            "sensory_seed": SEED,
            "source_commit": __import__("subprocess").check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "native_sha256": digest(
                (ROOT / ".work/local-v4-native/_threemind_native/_threemind_native.pyd").read_bytes()
            ),
            "source_hashes": {
                str(f.relative_to(ROOT)): digest(f.read_bytes())
                for f in (
                    ROOT / "src/threemind_kernels/local.py",
                    ROOT / "crates/threemind-core/src/local.rs",
                    ROOT / "crates/threemind-core/src/local-defaults.json",
                    ROOT / "src/threemind_kernels/retention.py",
                    ROOT / "crates/threemind-core/src/retention.rs",
                    Path(__file__),
                )
            },
        },
    )
    result = []
    for name, version, options in conditions + controls:
        for repeat in [False, True] if name in {r[0] for r in conditions} else [True]:
            label = name + ("-repeat" if repeat else "-single")
            cfg = (LocalConfig if version == 4 else RetentionConfig)(quiescence_death_us=10**12, **options)
            ref = (LocalEngine if version == 4 else RetentionEngine)(cfg)
            engine = (NativeLocalEngine if version == 4 else NativeRetentionEngine)(cfg)
            events = [Stimulus.from_dict(row["stimulus"]) for row in physical]
            for second in range(12) if repeat else [11]:
                for i, text in enumerate(SENTENCES):
                    for frame in sensor.frames(text):
                        s = frame["stimulus"]
                        events.append(Stimulus(second * 1000000 + i * 350000 + s.time_us, s.channels, s.intensity))
            events.sort(key=lambda s: s.time_us)
            write(label + "/inputs.json.gz", [s.to_dict() for s in events], True)
            for s in events:
                engine.inject(s)
                ref.inject(s)
            engine.advance_to(2000000)
            ref.advance_to(2000000)
            close(engine.capture_state().to_dict(), ref.capture_state().to_dict())
            baseline = {}
            cost = {"advance_s": 0.0, "observation_s": 0.0, "save_s": 0.0}
            for seconds in (12, 42, 132, 312):
                start = time.perf_counter()
                engine.advance_to(seconds * 1000000)
                cost["advance_s"] += time.perf_counter() - start
                start = time.perf_counter()
                g = engine.graph()
                metrics = engine.metrics()
                cost["observation_s"] += time.perf_counter() - start
                nodes = {n["id"]: n for n in g["nodes"]}
                edges = {(e["source"], e["target"]): e for e in g["edges"]}
                current = {
                    k: e
                    for k, e in edges.items()
                    if nodes[k[0]]["channel"] in text_channels and nodes[k[1]]["channel"] in text_channels
                }
                if seconds == 12:
                    baseline = current.copy()
                kept = {k: e for k, e in current.items() if k in baseline}
                original = sum(e["weight"] for e in baseline.values())
                cross = sum(
                    (nodes[a]["channel"] in text_channels) != (nodes[b]["channel"] in text_channels) for a, b in edges
                )
                image = engine.capture_state()
                h_values = (
                    [e["half_life"] for e in current.values()]
                    if version == 4
                    else [
                        max(cfg.memory_half_life_min_s, h - cfg.memory_half_life_decay_rate * (seconds - int(t) / 1e6))
                        for a, b, h, t in image.to_dict()["operator_state"]["retention"]["edges"]
                        if (a, b) in current
                    ]
                )
                restore = type(engine)(state=image)
                engine.advance_to(seconds * 1000000 + 12345)
                restore.advance_to(seconds * 1000000 + 12345)
                assert (
                    image.to_dict()["dynamics"] == engine.dynamics
                    and engine.capture_state().digest == restore.capture_state().digest
                )
                row = {
                    "condition": label,
                    "time_s": seconds,
                    "nodes": len(nodes),
                    "edges": len(edges),
                    "text_edges": len(current),
                    "baseline_text_edges": len(baseline),
                    "baseline_survivors": len(kept),
                    "baseline_weight_fraction": sum(e["weight"] for e in kept.values()) / original
                    if original
                    else None,
                    "cross_edges": cross,
                    "edge_H_min": min(h_values, default=None)
                    if cfg.consolidation_mode == "adaptive-half-life"
                    else None,
                    "edge_H_max": max(h_values, default=None)
                    if cfg.consolidation_mode == "adaptive-half-life"
                    else None,
                    "local_audit": metrics.get("local_audit"),
                }
                result.append(row)
                start = time.perf_counter()
                write(
                    label + f"/system-{seconds}.json.gz",
                    {
                        "core": image.to_dict(),
                        "text_sensor": asdict(SENSOR),
                        "sensory_seed": SEED,
                        "physical_cursor": sum(int(r["time_us"]) <= seconds * 1000000 for r in physical),
                        "input_sha256": digest(encoded([s.to_dict() for s in events])),
                    },
                    True,
                )
                cost["save_s"] += time.perf_counter() - start
            write(label + "/cost.json", cost)
            print(json.dumps({"condition": label, "finished": True, "cost": cost}), flush=True)
    write("retention.json", result)
    performance = []
    for size in (2, 1002, 10002):
        graphs = []
        for mode in ("local-events", "scan-control"):
            cfg = LocalConfig(
                propagation_mode=mode,
                retain_nodes=True,
                inhibition=False,
                context_enabled=False,
                quiescence_death_us=10**12,
            )
            parent = LocalEngine(cfg)
            for i in range(size):
                parent._birth(1000 + i)
            image = parent.capture_state()
            e = NativeLocalEngine(state=image)
            e.inject(Stimulus(0, ((1000, 0.8), (1001, 0.8))))
            start = time.perf_counter()
            e.advance_to(1000000)
            elapsed = time.perf_counter() - start
            start = time.perf_counter()
            e.metrics()
            observe = time.perf_counter() - start
            start = time.perf_counter()
            gzip.compress(e.capture_state().payload, mtime=0)
            save = time.perf_counter() - start
            performance.append(
                {
                    "nodes": size,
                    "mode": mode,
                    "advance_s": elapsed,
                    "observation_s": observe,
                    "save_compress_s": save,
                    "audit": e.capture_state().to_dict()["audit"],
                }
            )
            graphs.append(e.graph())
        assert graphs[0] == graphs[1], "execution-only control changed the graph"
    for mode in ("local-events", "scan-control"):
        rows = [r["audit"].copy() for r in performance if r["mode"] == mode]
        for r in rows:
            r.pop("scan_visits")
        assert rows[0] == rows[1] == rows[2], "unrelated nodes changed local work"
    write("performance.json", performance)
    energy_results = []
    for model in ("local-field", "global-ledger"):
        cfg = LocalConfig(
            energy_simulation_enabled=True,
            energy_model=model,
            energy_region_count=1,
            energy_initial_reserve=0.0,
            energy_direct_cost=0.0,
            energy_capacity=1.0,
            quiescence_death_us=10**12,
        )
        e = NativeLocalEngine(cfg)
        e.inject(Stimulus(0, ((1, 0.1), (2, 0.1))))
        e.supply_energy(0.8, time_us=0)
        e.supply_energy(0.5, time_us=200000)
        for t in (0, 1000000):
            e.advance_to(t)
            energy_results.append(
                {
                    "model": model,
                    "time_us": t,
                    "energy": e.metrics()["energy"],
                    "nodes": [
                        {"id": n["id"], "reserve": n["reserve"], "activation": n["activation"]}
                        for n in e.observation_nodes()
                    ],
                }
            )
        write("energy-" + model + "/system.json.gz", {"core": e.capture_state().to_dict()}, True)
    write("energy.json", energy_results)
    write(
        "complete.json",
        {
            "complete": True,
            "conditions": 12,
            "wall_s": time.perf_counter() - begin,
            "evidence_bytes_before_final_record": bytes_written,
            "scope": "Core mechanism calibration; no answer scoring",
        },
    )


if __name__ == "__main__":
    main()
