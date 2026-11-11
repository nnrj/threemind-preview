"""Registered Core-only probes. Does not load or modify an existing individual."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import platform
import subprocess
import time
from pathlib import Path

from threemind_core import Stimulus
from threemind_kernels.novelty import NoveltyConfig, NoveltyEngine
from threemind_kernels.novelty_native import NativeNoveltyEngine
from threemind_kernels.retention import RetentionConfig, RetentionEngine
from threemind_kernels.retention_native import NativeRetentionEngine


def schedule(case):
    if case in ("single", "strong"):
        return [(0, ((1, 0.8), (2, 0.8)), 4.0 if case == "strong" else 1.0)], 1_000_000
    if case in ("repeat", "reversal"):
        return [
            (i * 100_000, ((1, 0.8), (3 if case == "reversal" and i >= 600 else 2, 0.8)), 1.0) for i in range(1200)
        ], 120_000_000
    return [
        (i * 100_000, ((10 + (i % 8 if case == "fixed-background" else i), 0.05),), 1.0) for i in range(80)
    ], 8_000_000


def close(a, b, path="state"):
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for k in a:
            close(a[k], b[k], path + "/" + k)
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{path}/{i}")
    elif isinstance(a, float):
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14), (path, a, b)
    else:
        assert a == b, (path, a, b)


def run(out, variant, case, backend):
    kwargs = {"quiescence_death_us": 10**12}
    if variant == "memory2":
        config = NoveltyConfig(**kwargs)
        cls = NoveltyEngine if backend == "reference" else NativeNoveltyEngine
    else:
        kwargs.update(consolidation_mode="legacy-stability" if variant == "legacy" else "adaptive-half-life")
        if variant == "linear":
            kwargs["memory_growth_formula"] = "linear-saturating"
        if variant.startswith("gain-"):
            kwargs["memory_learning_gain"] = float(variant.split("-")[1])
        config = RetentionConfig(**kwargs)
        cls = RetentionEngine if backend == "reference" else NativeRetentionEngine
    e = cls(config)
    inputs, end = schedule(case)
    result = {
        "variant": variant,
        "case": case,
        "backend": backend,
        "config": config.to_dict(),
        "kernel_id": e.dynamics,
        "inputs": inputs,
        "stages": [],
    }
    compute = readout = capture = compress = 0.0
    states = []

    def stage(label):
        nonlocal readout, capture, compress
        start = time.perf_counter()
        m = e.metrics()
        graph = e.graph()
        row = {k: m[k] for k in ("time_us", "nodes", "edges", "mean_weight", "transport")}
        row.update(
            label=label,
            retention=m.get("retention"),
            support_sum=sum(n["support"] for n in graph["nodes"]),
            target_edges=[x for x in graph["edges"] if x["source"] in (1, 2, 3) and x["target"] in (1, 2, 3)],
        )
        readout += time.perf_counter() - start
        start = time.perf_counter()
        s = e.capture_state()
        row["state_hash"] = s.digest
        states.append(s.to_dict())
        capture += time.perf_counter() - start
        start = time.perf_counter()
        name = f"{variant}-{case}-{backend}-{label}.json.gz"
        (out / name).write_bytes(gzip.compress(s.payload, mtime=0))
        compress += time.perf_counter() - start
        row["checkpoint"] = name
        result["stages"].append(row)

    start = time.perf_counter()
    for t, channels, intensity in inputs:
        e.inject(Stimulus(t, channels, intensity))
        e.advance_to(t)
    e.advance_to(end)
    compute += time.perf_counter() - start
    stage("exposure")
    for seconds in (30, 120, 300):
        start = time.perf_counter()
        e.advance_to(end + seconds * 1_000_000)
        compute += time.perf_counter() - start
        stage(f"delay-{seconds}")
    start = time.perf_counter()
    for i in range(10):
        t = end + 300_000_000 + i * 100_000
        e.inject(Stimulus(t, ((1, 0.8), (2, 0.8))))
        e.advance_to(t)
    compute += time.perf_counter() - start
    stage("reminders")
    # Same-backend continuation must preserve complete state, not just graph values.
    resumed = cls(state=e.capture_state())
    e.advance_to(end + 302_000_000)
    resumed.advance_to(end + 302_000_000)
    assert e.capture_state().digest == resumed.capture_state().digest
    result["seconds"] = {"core": compute, "readout": readout, "capture_hash": capture, "gzip_write": compress}
    result["resume_exact"] = True
    return result, states


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    records = []
    metadata = {
        "registered_protocol": "../protocol.md",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "cases": ["single", "strong", "repeat", "reversal", "fixed-background", "growing-background"],
    }

    def pair(variant, case):
        a, x = run(args.out, variant, case, "reference")
        b, y = run(args.out, variant, case, "native")
        close(x, y)
        a["backend_parity"] = b["backend_parity"] = True
        records.extend((a, b))
        with (args.out / f"result-{variant}-{case}.json").open("x", encoding="utf-8") as stream:
            json.dump({"metadata": metadata, "records": [a, b]}, stream, ensure_ascii=False, indent=2)
        print(variant, case, "parity passed; final delay edges", a["stages"][3]["edges"], flush=True)

    for variant in ("adaptive", "legacy", "linear", "memory2"):
        for case in metadata["cases"]:
            pair(variant, case)
    repeated = next(
        r for r in records if r["variant"] == "adaptive" and r["case"] == "repeat" and r["backend"] == "reference"
    )
    if repeated["stages"][3]["edges"] == 0 or repeated["stages"][0]["retention"]["half_life_max_s"] <= 30.1:
        for variant in ("gain-2", "gain-4"):
            pair(variant, "repeat")
    with (args.out / "results.json").open("x", encoding="utf-8") as stream:
        json.dump({"metadata": metadata, "records": records}, stream, ensure_ascii=False, indent=2)
    print("complete", len(records), "records", flush=True)


if __name__ == "__main__":
    main()
