"""Bounded engineering witnesses for /2; never loads a research individual or database.

Historical source and full outputs are written only to a new directory under .work.
The tracked fixture contains configuration and hashes, not experiment trajectories.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = (
    "52e18c3e3d9be89aa2569861e612b977c6911f4b",  # earliest /2 identity
    "6a9e68a2b261beb6c2d3424662d3e0c6baad102c",  # before /3
    "f4e7568f29c0f81c9ed2bce022f805279aff4fe7",  # before /4
)
EXTRA_CASES = {
    "strong_non_aligned": {"config": {}, "actions": [
        ["input", 0, [[1, .8], [2, .6]], 1.], ["advance", 70001],
        ["input", 70001, [[1, .5], [3, .7]], 4.], ["advance", 110001],
        ["input", 173771, [[1, .9], [2, .8], [3, .4]], 1.5],
        ["advance", 611337], ["advance", 4000000]]},
    "temporal_links": {"config": {"edge_birth_policy": "temporal-association"}, "actions": [
        ["input", 0, [[1, .7]], 1.], ["advance", 73123],
        ["input", 73123, [[2, .8]], 1.], ["advance", 410000], ["advance", 2000000]]},
    "energy_starvation": {"config": {"energy_simulation_enabled": True,
        "energy_starvation_damage_enabled": True, "energy_initial_reserve": .0001}, "actions": [
        ["input", 0, [[1, .8], [2, .7]], 1.], ["advance", 300000], ["advance", 2000000]]},
    "spatial_neighborhood": {"config": {"spatial_embedding": True, "spatial_radius": 2.5}, "actions": [
        ["input", 0, [[1, .8], [2, .7], [3, .6]], 1.], ["advance", 300000], ["advance", 2000000]]},
    "base_operator_route": {"config": {"stp_enabled": False, "fast_enabled": False,
        "context_enabled": False}, "actions": [
        ["input", 0, [[1, .8], [2, .7]], 1.], ["advance", 73000],
        ["input", 73000, [[1, .5], [3, .6]], 1.], ["advance", 300000], ["advance", 2000000]]},
    "learning_off": {"config": {"plasticity": False}, "actions": [
        ["input", 0, [[1, .8], [2, .7]], 1.], ["advance", 300000], ["advance", 2000000]]},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def cases():
    sys.path.insert(0, str(ROOT / "tests_v2"))
    from kernel_witnesses import CASES
    return {mode + "/" + name: dict(case, config=case["config"] | {"novelty_mode": mode})
            for mode in ("immediate", "arrival-window") for name, case in (CASES | EXTRA_CASES).items()}


def collect(backend="python"):
    # PYTHONPATH is chosen by the caller; do not insert the current source here.
    from dataclasses import asdict

    from threemind_core import Stimulus
    from threemind_kernels.novelty import NoveltyConfig, NoveltyEngine
    if backend == "native":
        from threemind_kernels.novelty_native import NativeNoveltyEngine
        factory = NativeNoveltyEngine
    else:
        factory = NoveltyEngine
    definitions = cases()
    from kernel_witnesses import exercise
    return {"default": asdict(NoveltyConfig()), "cases": {
        name: exercise(case, config_type=NoveltyConfig, stimulus_type=Stimulus, factory=factory)
        for name, case in definitions.items()}}


def close(a, b):
    """Existing cross-backend tolerance; identity, topology and integers stay exact."""
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(close(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
    if isinstance(a, float):
        return isinstance(b, (int, float)) and abs(a - b) <= max(1e-14, abs(a) * 1e-12)
    return a == b


def audit_tool_time():
    """Read-only host checks on fresh cores; physical waiting is mocked, not slept."""
    from unittest.mock import patch

    from threemind_core import Stimulus
    from threemind_kernels.novelty import NoveltyEngine
    from threemind_kernels.novelty_native import NativeNoveltyEngine
    from threemind_runtime.host import Runtime
    from threemind_runtime.readout_session import ReadoutSession
    summary = {}
    for factory in (NoveltyEngine, NativeNoveltyEngine):
        control, observed = factory(), factory()
        rows = []
        session = ReadoutSession(observed, record=rows.append, config={
            "structural_readout": {"enabled": True, "interval_us": 11357},
            "temporal_readout": {"enabled": True, "interval_us": 17311},
            "activity_readout": {"enabled": True, "interval_us": 19877}})
        for engine in (control, observed):
            for t, channels in ((0, ((1, .8), (2, .7))), (73123, ((1, .4), (3, .5))),
                                (311337, ((2, .6), (3, .8)))):
                engine.inject(Stimulus(t, channels))
        control.advance_to(1001337)
        session.advance_to(1001337)
        equal = control.capture_state().to_dict() == observed.capture_state().to_dict()
        before = observed.capture_state().payload
        for _ in range(3):
            observed.metrics()
            observed.graph()
            observed.activations()
            observed.observation_nodes()
            observed.induced_edges([1, 2])
            observed.spatial_geometry()
            session.host.observe(observed, force=True)
            session.capture()
        readonly = before == observed.capture_state().payload
        host_now = [0]
        with patch("threemind_runtime.host.time.monotonic_ns", side_effect=lambda clock=host_now: clock[0]), \
                patch("threemind_runtime.host.time.sleep"):
            runtime = Runtime(observed, clock="realtime")
            runtime.pace(observed.time_us + 20000)
            host_now[0] += 100_000_000_000
            runtime.pace(observed.time_us + 20000)
        summary[factory.__name__] = {
            "uneven_readout_boundaries_equal": equal,
            "queries_and_forced_readout_preserve_bytes": readonly,
            "mock_100s_physical_delay_preserves_bytes": before == observed.capture_state().payload,
            "simulation_us": observed.time_us, "readout_events": len(rows)}
    return summary


def run(output, *, native=False, tool_time=False):
    output = output.resolve()
    if not output.is_relative_to((ROOT / ".work").resolve()) or output == ROOT / ".work":
        raise ValueError("audit output must be a new child of this repository's .work")
    output.mkdir(parents=True, exist_ok=False)
    results, archives = {}, {}
    for reference in (*REFERENCES, "current"):
        source = ROOT / "src"
        if reference != "current":
            archive_bytes = subprocess.check_output(["git", "archive", "--format=tar", reference,
                "--", "src/threemind_core", "src/threemind_kernels"], cwd=ROOT)
            destination = output / reference
            with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
                for member in archive.getmembers():
                    if not member.isfile():
                        continue
                    path = (destination / member.name).resolve()
                    if not path.is_relative_to(destination.resolve()):
                        raise ValueError("unsafe historical source path")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.extractfile(member).read())
            archives[reference] = hashlib.sha256(archive_bytes).hexdigest()
            source = destination / "src"
        env = os.environ | {"PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--emit"],
                              cwd=output, env=env, capture_output=True, text=True, timeout=90, check=True)
        results[reference] = json.loads(proc.stdout)
        (output / f"{reference}.json").write_text(proc.stdout, encoding="utf-8")
    current = results["current"]
    comparisons = {}
    for reference in REFERENCES:
        old = results[reference]
        comparisons[reference] = {
            "case_state_exact_equal": old["cases"] == current["cases"],
            "defaults_changed": {k: [old["default"].get(k), current["default"].get(k)]
                for k in old["default"] | current["default"]
                if old["default"].get(k) != current["default"].get(k)}}
    summary = {"schema": "threemind.memory2-preservation/1", "classification": "engineering audit",
               "source_archives_sha256": archives, "case_count": len(current["cases"]),
               "snapshot_count": sum(map(len, current["cases"].values())), "comparisons": comparisons}
    if native:
        native_result = collect("native")
        (output / "current-native.json").write_text(json.dumps(native_result), encoding="utf-8")
        summary["native_within_tolerance"] = close(current, native_result)
    if tool_time:
        summary["tool_time"] = audit_tool_time()
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if (not all(v["case_state_exact_equal"] for v in comparisons.values())
            or not summary.get("native_within_tolerance", True)
            or any(not value for result in summary.get("tool_time", {}).values()
                   for value in result.values() if isinstance(value, bool))):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--tool-time", action="store_true", help="also check observation and mocked pacing on /2")
    parser.add_argument("--emit", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.emit:
        print(json.dumps(collect(), sort_keys=True, separators=(",", ":")))
    elif args.output:
        run(args.output, native=args.native, tool_time=args.tool_time)
    else:
        parser.error("--output is required")
