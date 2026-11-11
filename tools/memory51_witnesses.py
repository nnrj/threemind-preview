"""Bounded synthetic /5-to-/5.1 transition witnesses, never formal individuals.

Freeze writes originals only to a new ignored .work directory. The harness uses
public input/advance/intervention/configuration operations, captures each boundary,
and restores only its own complete *current* engineering fixture.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import replace
from pathlib import Path

from threemind_core import Stimulus
from threemind_core.engine import canonical_bytes

ROOT = Path(__file__).resolve().parents[1]


def cases():
    result = {}
    for mode, source, arrival, phase in itertools.product(
        ("adaptive-half-life", "legacy-stability"),
        ("legacy-source", "unified"),
        ("sequential", "coincident"),
        ("aligned", "asynchronous"),
    ):
        result[f"{mode}/{source}/{arrival}/{phase}"] = {
            "consolidation_mode": mode, "reception_mode": source,
            "arrival_mode": arrival, "propagation_phase": phase,
        }
    result.update({
        "learning-off": {"plasticity": False},
        "eligibility-decay-off": {"eligibility_decay_enabled": False},
        "stability-decay-off": {"stability_decay_enabled": False},
        "node-retention-manual": {"node_retention_mode": "manual"},
        "linear-growth": {"memory_growth_formula": "linear-saturating"},
        "strong-fatigue-off": {"strong_fatigue_enabled": False},
        "context-off": {"context_enabled": False},
        "stp-fast-off": {"stp_enabled": False, "fast_enabled": False},
        "scan-control": {"propagation_mode": "scan-control"},
        "global-energy": {"energy_simulation_enabled": True, "energy_model": "global-ledger",
                          "energy_initial_reserve": 0.04},
        "local-counter-energy": {"energy_simulation_enabled": True, "energy_region_count": 1,
                                 "energy_initial_reserve": 0.04},
        "local-stream-energy": {"energy_simulation_enabled": True, "energy_region_count": 1,
                                "energy_distribution": "stream-random", "energy_initial_reserve": 0.04},
        "dormancy-wake": {"dormant_traces_enabled": True, "revival_enabled": True,
                          "node_wake_threshold": 0.05, "edge_wake_threshold": 0.1},
        "spatial": {"spatial_embedding": True, "neighborhood_enabled": True},
    })
    return result


def factories(version, backend):
    if version == "5":
        from threemind_kernels.local5 import Local5Config, Local5Engine

        if backend == "native":
            from threemind_kernels.local5_native import NativeLocal5Engine

            return Local5Config, NativeLocal5Engine
        return Local5Config, Local5Engine
    if version != "5.1":
        raise ValueError("witnesses only cover memory/5 and memory/5.1")
    from threemind_kernels.local51 import Local51Config, Local51Engine

    if backend == "native":
        from threemind_kernels.local51_native import NativeLocal51Engine

        return Local51Config, NativeLocal51Engine
    return Local51Config, Local51Engine


def trace(version, backend, options):
    config_type, factory = factories(version, backend)
    config = config_type(**options, quiescence_death_us=10**12)
    engine, snapshots = factory(config), []

    def capture(label):
        before = engine.capture_state().payload
        snapshots.append({"label": label, "state": engine.capture_state().to_dict(),
                          "metrics": engine.metrics(), "graph": engine.graph(),
                          "activations": engine.activations()})
        assert engine.capture_state().payload == before, "observation changed the fixture"

    capture("blank")
    for index, (when, channels, intensity) in enumerate((
        (0, ((1, 0.8), (2, 0.7)), 1.0),
        (70000, ((1, 0.5), (3, 0.5)), 1.0),
        (80000, ((1, 0.1),), 1.0),
        (100000, ((1, 0.6), (4, 0.7)), 1.0),
        (100000, ((1, 0.2), (3, 0.4)), 1.0),
        (100000, ((4, 0.002),), 1.0),
        (611337, ((1, 0.6), (3, 0.7)), 3.0),
    )):
        engine.advance_to(when)
        engine.inject(Stimulus(when, channels, intensity=intensity))
        engine.advance_to(when)
        capture(f"input-{index}")
    if config.energy_simulation_enabled:
        engine.supply_energy(0.2, time_us=711337)
    engine.advance_to(811337)
    capture("energy-event")
    engine = factory(state=engine.capture_state())
    capture("current-boundary-restored")
    engine.inject(Stimulus(811337, ((1, 0.3), (4, 0.5))))
    engine.advance_to(811337)
    capture("next-same-time-input")
    engine.intervene(nodes=(1,), action="silence")
    engine.advance_to(900000)
    capture("silence")
    engine.intervene(nodes=(1,), action="restore")
    engine.intervene(edges=((0, 1),), action="disconnect_edges")
    engine.advance_to(1000000)
    capture("disconnect")
    engine.reconfigure(replace(config, eligibility_tau=0.73, eligibility_decay_enabled=False))
    engine.advance_to(1100000)
    capture("changed-config-decay-off")
    engine.reconfigure(replace(config, eligibility_tau=0.73, eligibility_decay_enabled=True))
    engine.advance_to(1200000)
    capture("changed-config-decay-on")
    engine.reconfigure(replace(config, plasticity=False))
    engine.advance_to(1500000)
    capture("learning-off-after-use")
    engine.reconfigure(config)
    engine.intervene(nodes=(2,), action="delete_nodes")
    engine.inject(Stimulus(1500000, ((3, 0.7), (5, 0.8))))
    engine.advance_to(1500000)
    capture("delete-then-new-birth")
    engine.advance_to(2300000)
    capture("final")
    return snapshots


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def normalize(value):
    """Normalize only declared identity fields; never remove scientific state.

    Both original definition hashes are checked first. The normalized hash is
    regenerated because its input includes the explicitly changed birth identity.
    """
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: normalize(item) for key, item in value.items()}
    for key, old, new in (
        ("dynamics", "threemind.continuous-memory/5.1", "threemind.continuous-memory/5"),
        ("kernel_id", "threemind.continuous-memory/5.1", "threemind.continuous-memory/5"),
        ("schema", "threemind.continuous-memory-state/5.1", "threemind.continuous-memory-state/5"),
        ("state_schema", "threemind.continuous-memory-state/5.1", "threemind.continuous-memory-state/5"),
        ("hypothesis_id", "threemind.hypotheses/continuous-memory51", "threemind.hypotheses/continuous-memory5"),
    ):
        if result.get(key) == old:
            result[key] = new
    if "definition_hash" in result:
        assert value["definition_hash"] == digest(value["definition"])
        result["definition_hash"] = digest(result["definition"])
    return result


def freeze(output):
    output = output.resolve()
    if not output.is_relative_to(ROOT / ".work"):
        raise ValueError("witness originals must use a fresh ignored .work directory")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"kind": "synthetic-engineering-witness", "version": "5", "cases": {}}
    for backend in ("python", "native"):
        manifest["cases"][backend] = {}
        for index, (name, options) in enumerate(cases().items()):
            snapshots = trace("5", backend, options)
            path = output / f"{backend}-{index:02d}.json"
            path.write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest["cases"][backend][name] = {"file": path.name, "sha256": digest(snapshots),
                                                "boundaries": len(snapshots)}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "cases": len(cases()), "boundaries": len(snapshots)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    freeze(parser.parse_args().output)
