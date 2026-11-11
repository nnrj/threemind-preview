"""Explicit controls on new Ocean /2 copies; never edit their source population.

Birth controls test persistent history in a new common environment. Saved-world
controls silence existing edges once, not all future communication or a located
autonomous region. Core dynamics and ordinary birth rules remain unchanged.
"""

import argparse
import hashlib

from lab.tools.ocean_cli import write_json
from lab.tools.ocean_controls import naive_same_receptors
from lab.tools.ocean_evolution import EvolutionOcean
from lab.tools.ocean_evolution_cli import load_population, save_population


def make_control(source, operation, *, environment_seed=None):
    before = source.capture()
    ids = sorted(i for i, b in source.bodies.items() if b.physical and source.engines[i].life != "dead")
    if not ids:
        raise ValueError("no living physical donors; do not revive the dead")
    receipt = {"schema": "threemind.ocean-control/1", "operation": operation, "source_ids": ids}
    if operation in ("inherited", "naive"):
        if environment_seed is None:
            raise ValueError("common-garden controls need an explicit new environment seed")
        protocol = source.p.model_dump(by_alias=True) | {"founders": len(ids), "environment_seed": environment_seed}
        images = [source.engines[i].capture_state() for i in ids]
        if operation == "naive":
            images = [naive_same_receptors(image) for image in images]
        world = EvolutionOcean(protocol, founder_images=images, backend=source.backend)
        receipt.update(
            new_environment_seed=environment_seed,
            donor_by_founder={j: i for j, i in enumerate(ids)},
            meaning="new births; persistent history retained or erased, both reset activity/time/energy by birth/1",
        )
    elif operation in ("sham", "silence"):
        if environment_seed is not None:
            raise ValueError("saved-world controls preserve their physical environment")
        images = {i: e.capture_state() for i, e in source.engines.items()}
        world = EvolutionOcean(before["protocol"], state=before, images=images, backend=source.backend)
        targets, differences = {}, {}
        for i in ids:
            e = world.engines[i]
            old = e.capture_state().to_dict()
            edges = sorted((row["source"], row["target"]) for row in old["edges"]) if operation == "silence" else []
            e.intervene(edges=edges, action="silence")
            after = e.capture_state().to_dict()
            changed = sorted(k for k in old if old[k] != after[k])
            if set(changed) - {"sequence", "silenced_edges"}:
                raise ValueError(f"unexpected concurrent state change during intervention: {changed}")
            targets[i], differences[i] = edges, changed
        receipt.update(
            edges=targets,
            changed_fields=differences,
            meaning="one-time existing-edge intervention; in-flight signals, future edges and births remain possible",
        )
        after_world = world.capture()
        assert {k: v for k, v in before.items() if k != "core_hashes"} == {
            k: v for k, v in after_world.items() if k != "core_hashes"
        }
    else:
        raise ValueError("unknown ocean control")
    assert source.capture() == before, "control changed source population"
    receipt["source_core_hashes"] = before["core_hashes"]
    receipt["result_core_hashes"] = world.capture()["core_hashes"]
    receipt["energy_balance_error"] = world.metrics()["energy_balance_error"]
    return world, receipt


def main():
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="saved population directory")
    parser.add_argument("output", type=Path, help="new directory; source is never overwritten")
    parser.add_argument("--operation", required=True, choices=("inherited", "naive", "sham", "silence"))
    parser.add_argument("--environment-seed", type=int)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    source = load_population(args.source)
    world, receipt = make_control(source, args.operation, environment_seed=args.environment_seed)
    receipt["source_manifest_sha256"] = hashlib.sha256((args.source / "manifest.json").read_bytes()).hexdigest()
    save_population(world, args.output / "state")
    write_json(args.output / "control-receipt.json", receipt)
    print(f"Saved {args.operation} control to {args.output}; source unchanged.")


if __name__ == "__main__":
    main()
