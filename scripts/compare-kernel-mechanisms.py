"""Bounded nonsemantic mechanism check; not a memory/AGI benchmark."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from threemind_core import Stimulus
from threemind_kernels.definition import KernelDefinition
from threemind_runtime import create_engine
from threemind_runtime.event_observation import advance_observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("reference", "native"), default="native")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("existing evidence is never overwritten")
    cases = [
        ("baseline", "threemind.causal/9", {}),
        (
            "continuous_all_off",
            "threemind.continuous/1",
            {"stp_enabled": False, "fast_enabled": False, "context_enabled": False},
        ),
        ("continuous", "threemind.continuous/1", {}),
        ("continuous_no_stp", "threemind.continuous/1", {"stp_enabled": False}),
        ("continuous_no_fast", "threemind.continuous/1", {"fast_enabled": False}),
        ("continuous_no_context", "threemind.continuous/1", {"context_enabled": False}),
        ("lif", "threemind.lif/1", {}),
        ("lif_no_stp", "threemind.lif/1", {"stp_enabled": False}),
        ("lif_no_stdp", "threemind.lif/1", {"stdp_enabled": False}),
    ]
    inputs = [Stimulus(i * 100000, ((101, 0.7), (202, 0.5)), 0.9) for i in range(6)]
    inputs.append(Stimulus(650000, ((101, 0.5),), 0.5))
    started = time.monotonic()
    process = psutil.Process()
    rows = []
    for name, kernel, config in cases:
        engine = create_engine(config, kernel_id=kernel, backend=args.backend)
        for stimulus in inputs:
            engine.inject(stimulus)
        observations = []
        spikes = []
        for when in range(0, 900001, 25000):
            if time.monotonic() - started > 60 or process.memory_info().rss > 1024**3:
                raise RuntimeError("comparison stopped at 60 seconds or 1 GiB; no wider exploration")
            advance_observed(
                engine, when, lambda event, spikes=spikes: spikes.append(event) if event["kind"] == "spikes" else None
            )
            observations.append(engine.metrics())
        image = engine.capture_state()
        restored = create_engine(state=image, backend=args.backend)
        if restored.capture_state().digest != image.digest:
            raise AssertionError("exact recovery mismatch")
        rows.append(
            {
                "case": name,
                "kernel_id": kernel,
                "definition": KernelDefinition.default(kernel, config).to_dict(),
                "final_state_hash": image.digest,
                "observations": observations,
                "spikes": spikes,
                "exact_restore": True,
                "final_state": image.to_dict(),
            }
        )
    protocol = [s.to_dict() for s in inputs]
    payload = {
        "schema": "threemind.mechanism-check/1",
        "scope": "nonsemantic engineering check; no learning or AGI claim",
        "backend": args.backend,
        "inputs": protocol,
        "protocol_sha256": hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest(),
        "budgets": {"wall_seconds": 60, "memory_bytes": 1024**3, "output_bytes": 2 * 1024**2},
        "wall_seconds": time.monotonic() - started,
        "rss_bytes": process.memory_info().rss,
        "cases": rows,
    }
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2).encode()
    if len(raw) > 2 * 1024**2:
        raise RuntimeError("evidence exceeds 2 MiB; refusing output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(raw)
    print(
        json.dumps(
            {
                "cases": len(rows),
                "bytes": len(raw),
                "wall_seconds": payload["wall_seconds"],
                "rss_bytes": payload["rss_bytes"],
            }
        )
    )


if __name__ == "__main__":
    main()
