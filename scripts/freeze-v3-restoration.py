"""Freeze tiny V3 witnesses from verified Git source, never from data/.

Run before changing the causal/8 implementation. The fixture is an oracle for
local mechanisms, not a claim that the two schedulers are equivalent.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import types
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def freeze():
    sources = []
    for revision, path in (
        ("97d8592", "core/threemind/runtime.py"),
        ("97d8592", "core/threemind/model.py"),
        ("97d8592", "core/threemind/frames.py"),
        ("97d8592", "core/threemind/attention.py"),
        ("0c5e64a", "legacy/ui/src/Lab.tsx"),
        ("0c5e64a", "legacy/ui/src/MediaControls.tsx"),
    ):
        raw = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)
        sources.append({"revision": revision, "path": path, "sha256": hashlib.sha256(raw).hexdigest()})

    package = types.ModuleType("frozen_v3")
    package.__path__ = []
    sys.modules[package.__name__] = package
    for name in ("model", "frames", "attention", "runtime"):
        path = f"core/threemind/{name}.py"
        raw = subprocess.check_output(["git", "show", f"97d8592:{path}"], cwd=ROOT)
        module = types.ModuleType(f"frozen_v3.{name}")
        module.__file__ = str(ROOT / path)
        sys.modules[module.__name__] = module
        exec(compile(raw, f"git:97d8592:{path}", "exec"), module.__dict__)  # noqa: S102 -- fixed Git revision, local oracle only
    from frozen_v3.frames import SensoryFrame
    from frozen_v3.model import ModelManifest, ModelPackage
    from frozen_v3.runtime import ConsciousnessRuntime, RuntimeConfig

    def runtime(**config):
        return ConsciousnessRuntime(
            ModelPackage(ModelManifest(), consciousness_id="v3-restoration-fixture"),
            config=replace(RuntimeConfig(), **config),
        )

    def state(r):
        return {"nodes": list(r.nodes.values()), "edges": list(r.edges.values())}

    samples = {}
    # Isolate the old local operators from its frame scheduler. This lets the
    # causal kernel retain timestamp delivery without pretending whole-tick
    # snapshots should match at birth (old ticks immediately forget new edges).
    r = runtime(topology_inhibition_enabled=False, propagation_gain=0)

    def local_contact(channels):
        delta = {
            key: set()
            for key in (
                "created_nodes",
                "created_edges",
                "strengthened_edges",
                "weakened_edges",
                "removed_edges",
                "removed_nodes",
            )
        }
        accepted = [(0, channel, drive, drive, 1.0) for channel, drive in channels]
        direct, impulses, groups = r._apply_direct(accepted, delta)
        r._adapt_edges(direct, set(), groups, set(), impulses, delta)
        r._update_nodes(direct)
        return json.loads(json.dumps(state(r)))

    samples["local_birth"] = local_contact([(11, 0.7), (22, 0.5)])
    samples["local_repeat"] = local_contact([(11, 0.7), (22, 0.5)])
    # Set controlled local history, then call the actual old operator.
    for n in r.nodes.values():
        n["associative_touch"] = 0.05
    samples["local_novelty"] = local_contact([(11, 0.3), (33, 0.6)])
    r._forget_and_prune(set(), {key: set() for key in ("weakened_edges", "removed_edges", "removed_nodes")})
    samples["local_forget"] = json.loads(json.dumps(state(r)))
    r = runtime(topology_inhibition_enabled=False, propagation_gain=0)
    r.receive_frame(SensoryFrame("manual", {11: 0.7, 22: 0.5}))
    samples["first_pair"] = state(r)
    # Detach snapshots before subsequent transitions.
    samples = json.loads(json.dumps(samples))
    r.receive_frame(SensoryFrame("manual", {11: 0.7, 22: 0.5}))
    samples["repeat_pair"] = state(r)
    r = runtime(topology_inhibition_enabled=False)
    r.receive_frame(SensoryFrame("manual", {99: 0.7}))
    samples["isolated_without_energy"] = state(r)
    r = runtime(
        topology_inhibition_enabled=False,
        energy_simulation_enabled=True,
        energy_direct_cost=0.1,
        energy_initial_reserve=10,
        energy_capacity=10,
    )
    r.receive_frame(SensoryFrame("manual", {99: 1.0}))
    n = next(iter(r.nodes.values()))
    n["activation"] = 1.0
    before = r.energy_reserve
    _direct, impulses, _groups = r._apply_direct([(0, 99, 1.0, 1.0, 1.0)], {"created_nodes": set()})
    samples["saturated_direct"] = {
        "energy_consumed": before - r.energy_reserve,
        "activation": n["activation"],
        "direct_touch": n["direct_touch"],
        "impulses": impulses,
    }
    r = runtime()
    samples["soft_inhibition"] = [{"input": q, "output": r._saturate_inhibition(q)} for q in (0, 0.1, 0.5, 1, 2)]
    r = runtime(propagation_gain=0)
    local_contact([(11, 0.7), (22, 0.5)])
    baseline = {}
    for n, q in zip(r.nodes.values(), (0.5, 0.7)):
        n["inhibition"], n["pending_inhibition"] = q, 0.0
        baseline[n["id"]] = n["activation"] - 0.1
    r._prepare_inhibition()
    delta = {}
    r._update_local_inhibition(baseline, delta)
    samples["inhibition_two_phases"] = json.loads(json.dumps({"state": state(r), "delta": delta}))
    return {
        "schema": "threemind-v3-restoration-oracle/1",
        "sources": sources,
        "samples": samples,
        "history_limit": "Old runtime first appears in root commit 97d8592; earlier author intent is unavailable.",
    }


if __name__ == "__main__":
    target = ROOT / "tests_v2/fixtures/v3-restoration.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(freeze(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(target.relative_to(ROOT))
