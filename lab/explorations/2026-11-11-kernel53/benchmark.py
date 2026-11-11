"""Bounded engineering fixtures; no scientific subject or learning claim."""

import argparse
import json
import math
from pathlib import Path
import statistics
import time

import psutil
from threemind_core import Stimulus
from threemind_kernels.decay53 import CURVES, decay_value
from threemind_kernels.local53 import KERNEL_ID, Local53Config
from threemind_kernels.registry import resolve_kernel
from threemind_runtime.codec import ArtifactCodec


def trial(backend, curve):
    cfg = Local53Config(decay_curve=curve, quiescence_death_us=10**12)
    measurements = []
    # The passive specimen explicitly silences all nodes. This measures the
    # fixed structural scan, not spontaneous activity or learned retention.
    for passive in (True, False):
        core = resolve_kernel(KERNEL_ID).create(cfg, backend=backend)
        started = time.perf_counter()
        for pair in range(32):
            core.inject(Stimulus(0, ((pair * 2, 0.8), (pair * 2 + 1, 0.8))))
        core.advance_to(0)
        if passive:
            core.intervene(nodes=list(range(64)), action="silence")
        setup_s = time.perf_counter() - started
        started = time.perf_counter()
        core.advance_to(10_000_000)
        advance_s = time.perf_counter() - started
        state = core.capture_state()
        started = time.perf_counter()
        for _ in range(10):
            blob = ArtifactCodec.encode(core.capture_state(), "tmind")
        save_s = (time.perf_counter() - started) / 10
        restored = ArtifactCodec.decode(blob)
        assert restored.digest == state.digest
        assert core.capture_state().digest == state.digest
        doc = state.to_dict()
        measurements.append(
            dict(
                kind="passive-silenced" if passive else "active",
                setup_seconds=setup_s,
                advance_seconds=advance_s,
                save_seconds=save_s,
                internal_seconds=10,
                nodes=len(doc["nodes"]),
                edges=len(doc["edges"]),
                json_bytes=len(state.payload),
                tmind_bytes=len(blob),
                audit=doc["audit"],
                transport=doc["transport"],
            )
        )
    # Repeated inputs represent a small complete input course, not adapter training.
    core = resolve_kernel(KERNEL_ID).create(cfg, backend=backend)
    started = time.perf_counter()
    for t in (0, 0.1, 0.3, 0.7, 1.5, 3.1, 6.3, 12.7):
        us = round(t * 1e6)
        core.advance_to(us)
        core.inject(Stimulus(us, ((71, 0.4), (83, 0.4))))
        core.advance_to(us)
    core.advance_to(13_000_000)
    teaching_s = time.perf_counter() - started
    return dict(
        backend=backend,
        curve=curve,
        measurements=measurements,
        course_seconds=teaching_s,
        course_internal_seconds=13,
        peak_working_set=psutil.Process().memory_info().peak_wset,
        private_bytes=psutil.Process().memory_info().private,
    )


def run(output):
    rows = []
    for backend in ("reference", "native"):
        for curve in CURVES:
            repeats = [trial(backend, curve) for _ in range(3)]
            row = dict(
                backend=backend,
                curve=curve,
                repeats=repeats,
                median_course_seconds=statistics.median(r["course_seconds"] for r in repeats),
            )
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "repeats"}), flush=True)
    scalars = []
    for curve in CURVES:
        cfg = Local53Config(decay_curve=curve)
        started = time.perf_counter()
        value, age, h = 0.8, 0.0, 30.0
        for _ in range(10000):
            value, age, h = decay_value(value, age, h, 0.01, cfg)
        assert math.isfinite(value) and value >= 0
        scalars.append(dict(curve=curve, calls=10000, seconds=time.perf_counter() - started))
    result = dict(
        kind="engineering-only",
        rows=rows,
        scalar_reference=scalars,
        caveats="Small fixtures; no scientific accuracy or large-network throughput inference.",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    run(p.parse_args().output)
