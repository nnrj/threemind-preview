"""Bounded graph-cost measurements, isolated from scientific individuals."""

import argparse
import json
import statistics
import time
from pathlib import Path

import psutil
from threemind_core import Stimulus
from threemind_kernels.local53 import KERNEL_ID, Local53Config
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec

CURVES = ("exponential", "power-law", "inverse-logarithmic", "power-exponential")


def trial(backend, curve, pairs, passive):
    e = resolve_kernel(KERNEL_ID).create(Local53Config(decay_curve=curve, quiescence_death_us=10**12), backend=backend)
    t = time.perf_counter()
    for i in range(pairs):
        e.inject(Stimulus(0, ((2 * i, 0.8), (2 * i + 1, 0.8))))
    e.advance_to(0)
    if passive:
        e.intervene(nodes=list(range(2 * pairs)), action="silence")
    setup = time.perf_counter() - t
    t = time.perf_counter()
    e.advance_to(1_000_000)
    advance = time.perf_counter() - t
    t = time.perf_counter()
    state = e.capture_state()
    blob = ArtifactCodec.encode(state, "tmind")
    save = time.perf_counter() - t
    assert ArtifactCodec.decode(blob).digest == state.digest == e.capture_state().digest
    doc = state.to_dict()
    return dict(
        setup_seconds=setup,
        advance_seconds=advance,
        save_seconds=save,
        nodes=len(doc["nodes"]),
        directed_edges=len(doc["edges"]),
        json_bytes=len(state.payload),
        tmind_bytes=len(blob),
        audit=doc["audit"],
        transport=doc["transport"],
        process_private_bytes=psutil.Process().memory_info().private,
    )


def run(path):
    rows = []
    for backend in ("reference", "native"):
        for curve in CURVES:
            for pairs in (32, 512) if backend == "reference" else (32, 512, 4096):
                for passive in (True, False):
                    repeats = [trial(backend, curve, pairs, passive) for _ in range(3)]
                    row = dict(
                        backend=backend,
                        curve=curve,
                        initial_nodes=2 * pairs,
                        initial_directed_edges=2 * pairs,
                        silenced=passive,
                        internal_seconds=1,
                        repeats=repeats,
                        median_advance_seconds=statistics.median(r["advance_seconds"] for r in repeats),
                        median_save_seconds=statistics.median(r["save_seconds"] for r in repeats),
                    )
                    rows.append(row)
                    print(json.dumps({k: v for k, v in row.items() if k != "repeats"}), flush=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(
            dict(
                schema="threemind.kernel53-scale-benchmark/1",
                engineering_only=True,
                topology="disjoint reciprocal pairs, not a densely connected graph",
                rows=rows,
                scope="Setup, internal advancement and serialization separated; three repeats; no trained subject or adapter.",
            ),
            f,
            indent=2,
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    run(p.parse_args().output)
