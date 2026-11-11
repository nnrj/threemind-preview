"""E28 registration and bounded ocean cohorts; no Core implementation changes."""

import argparse
import gzip
import hashlib
import json
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from cases import complete

from lab.tools.ocean import Ocean, OceanProtocol
from lab.tools.ocean_cli import load_population, read_json, run, write_json
from lab.tools.ocean_controls import naive_same_receptors
from lab.tools.service_study import Study, StudyConfig

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/primitive-ocean-20261003"
ENGINEERING = ROOT / ".work/ocean-engineering-20261003-02"


def study(prepare=False):
    instance = Study(
        StudyConfig(
            "primitive-ocean/1",
            "E28 原始海洋：摄食、繁殖与有限能量选择",
            HERE,
            WORK,
            15,
            instance_limit=512,
            wall_seconds=7200,
            storage_soft=3 * 2**30,
            storage_hard=4 * 2**30,
            usage_soft_delta=6,
            usage_hard_delta=10,
        ),
        prepare=prepare,
    )
    amendment = WORK / "budget-amendment.json"
    if amendment.exists():
        change = read_json(amendment)
        instance.settings = replace(
            instance.settings, storage_soft=change["storage_soft"], storage_hard=change["storage_hard"]
        )
    for name in ("wall-budget-amendment.json", "wall-budget-amendment-02.json"):
        wall_amendment = WORK / name
        if wall_amendment.exists():
            instance.settings = replace(instance.settings, wall_seconds=read_json(wall_amendment)["wall_seconds"])
    return instance


def spent(energy):
    return sum(
        energy[k] for k in ("consumed_direct", "consumed_associative", "consumed_inhibition", "consumed_maintenance")
    )


def calibrate():
    p = OceanProtocol(seed=289001, environment_seed=289101, founders=1, reproduction=False).model_dump(by_alias=True)
    w = Ocean(p)
    result = run(w, ENGINEERING, 30000000, wall_seconds=60)
    if not result["horizon_reached"]:
        raise RuntimeError("engineering calibration did not complete")
    with gzip.open(ENGINEERING / "trajectory.jsonl.gz", "rt", encoding="utf-8") as stream:
        at20 = next(json.loads(line) for line in stream if json.loads(line)["time_us"] == 20000000)
    rate = (spent(result["members"][0]["core_energy"]) - spent(at20["members"][0]["core_energy"])) / 10
    write_json(
        ENGINEERING / "calibration.json", {"rate": rate, "explanation": "last ten of thirty seconds, separate seed"}
    )
    print(json.dumps({"calibration_rate": rate, "status": result["status"]}), flush=True)


def freeze():
    c = read_json(ENGINEERING / "calibration.json")
    r = c["rate"]
    s = study(True)
    try:
        (WORK / "cases").mkdir()
        write_json(WORK / "usage.json", {"used_percent": 15, "source": "account tool before registration"})
        frozen = {
            "rate": r,
            "horizon_us": 900000000,
            "evaluation_us": 300000000,
            "groups": [0, 1, 2],
            "modes": ["core", "passive", "random"],
            "formal_started": False,
        }
        write_json(WORK / "frozen.json", frozen)
        shutil.copytree(ENGINEERING, WORK / "engineering")
        (WORK / "apparatus-sources").mkdir()
        for name in ("ocean.py", "ocean_cli.py"):
            shutil.copy2(ROOT / "lab/tools" / name, WORK / "apparatus-sources" / name)
        write_json(
            WORK / "apparatus-sources/manifest.json",
            {
                name: hashlib.sha256((ROOT / "lab/tools" / name).read_bytes()).hexdigest()
                for name in ("ocean.py", "ocean_cli.py")
            },
        )
        print(json.dumps({"project": s.project, "frozen": frozen}), flush=True)
    finally:
        s.db.close()


def protocol(group, mode="core", *, phase2=False):
    r = read_json(WORK / "frozen.json")["rate"]
    return OceanProtocol(
        seed=280100 + 100 * group,
        environment_seed=281100 + group,
        founders=8,
        population_limit=16,
        total_birth_limit=32,
        mode=mode,
        initial_energy=240 * r,
        core_capacity=960 * r,
        storage_capacity=960 * r,
        nutrient_energy=30 * r,
        child_energy=180 * r,
        reproduction_cost=30 * r,
        parent_retained_food=180 * r,
        predation=phase2,
        mutation_sigma=0.15 if phase2 else 0.0,
    ).model_dump(by_alias=True)


def guard(s):
    s.completed_count = None
    s.guard()
    count = 1  # calibration individual
    for path in (WORK / "cases").glob("*/result.json"):
        count += len(read_json(path)["members"])
    if count >= 512:
        raise RuntimeError("registered population budget")


def execute(key, ocean, seconds):
    s = study()
    try:
        expected = read_json(WORK / "apparatus-sources/manifest.json")
        for name, sha in expected.items():
            if hashlib.sha256((ROOT / "lab/tools" / name).read_bytes()).hexdigest() != sha:
                raise RuntimeError("apparatus changed after registration")
        s.completed_count = None
        s.guard(True)
        s.active_case = SimpleNamespace(born_wall=time.monotonic())
        result = run(ocean, WORK / "cases" / key, round(seconds * 1e6), wall_seconds=1800, guard=lambda: guard(s))
        print(
            json.dumps(
                {
                    "case": key,
                    "status": result["status"],
                    "sim_seconds": result["time_us"] / 1e6,
                    "alive": sum(m["life"] != "dead" for m in result["members"]),
                    "population": len(result["members"]),
                    "totals": result["totals"],
                    "wall_seconds": result["wall_seconds"],
                    "error": result["error"],
                }
            ),
            flush=True,
        )
    finally:
        s.db.close()


def phase1(group, mode):
    execute(f"phase1-{group}-{mode}", Ocean(protocol(group, mode)), 900)


def phase1_all():
    for group in range(3):
        modes = ["core", "passive", "random"]
        modes = modes[group:] + modes[:group]
        for mode in modes:
            result = complete(WORK / "cases" / f"phase1-{group}-{mode}") / "result.json"
            if result.exists():
                if read_json(result)["status"] not in ("horizon_paused", "extinct"):
                    raise RuntimeError("unfinished case requires explicit continuation")
                continue
            phase1(group, mode)


def stage_gate():
    results = [read_json(complete(WORK / "cases" / f"phase1-{g}-core") / "result.json") for g in range(3)]
    qualified = [
        g
        for g, r in enumerate(results)
        if r["horizon_reached"] and r["totals"]["food_consumed"] > 0 and r["totals"]["births"] > 0
    ]
    shortage = any(
        m["core_energy"]["unserved_total"] > 0 or m["core_energy"]["reserve"] < 0.5 * protocol(g)["initial_energy"]
        for g, r in enumerate(results)
        for m in r["members"]
    )
    answer = {
        "qualified": qualified,
        "shortage_observed": shortage,
        "passed": len(qualified) >= 2 and shortage,
        "criterion": "preregistered ecological feasibility, not adaptation",
    }
    write_json(WORK / "stage-gate.json", answer)
    print(json.dumps(answer), flush=True)


def phase2(group):
    if not read_json(WORK / "stage-gate.json")["passed"]:
        raise ValueError("phase one gate not passed")
    s = study()
    try:
        s.allow_extension()
    finally:
        s.db.close()
    source = load_population(complete(WORK / "cases" / f"phase1-{group}-core") / "final")
    alive = [i for i, b in source.bodies.items() if b.physical and source.engines[i].life == "active"]
    if not alive:
        raise ValueError("no surviving source in this world; do not revive the dead")
    parents = sorted(alive, key=lambda i: (-source.bodies[i].generation, i))
    chosen = [parents[i % len(parents)] for i in range(8)]
    images = [source.engines[i].capture_state() for i in chosen]
    p = protocol(group, phase2=True)
    p["environment_seed"] += 1000
    write_json(
        WORK / f"phase2-{group}-sources.json",
        {
            "source": f"phase1-{group}-core",
            "parents": chosen,
            "source_hashes": [image.digest for image in images],
            "endowment": "new experimental ocean; founder energy counted as external initial supply",
            "generation": "generation zero in the new ocean; source lineage recorded separately",
        },
    )
    execute(f"phase2-{group}", Ocean(p, founder_images=images), 900)


def evaluation(group, variant):
    """Common-garden comparison; donor selection is independent of intake score."""
    s = study()
    try:
        s.allow_extension()
    finally:
        s.db.close()
    source_path = complete(WORK / "cases" / f"phase2-{group}") / "final"
    if not source_path.exists():
        source_path = complete(WORK / "cases" / f"phase1-{group}-core") / "final"
    source = load_population(source_path)
    alive = [i for i, b in source.bodies.items() if b.physical and source.engines[i].life == "active"]
    roots = {}
    for i in alive:
        root = i
        while source.bodies[root].parent is not None:
            root = source.bodies[root].parent
        roots.setdefault(root, []).append(i)
    parents = [min(roots[k], key=lambda i: (-source.bodies[i].generation, i)) for k in sorted(roots)]
    if not parents:
        raise ValueError("no living donor for common-garden evaluation")
    chosen = [parents[i % len(parents)] for i in range(4)]
    images = [source.engines[i].capture_state() for i in chosen]
    if variant == "blank":
        images = [naive_same_receptors(image) for image in images]
    p = protocol(group)
    p.update(founders=4, reproduction=False, environment_seed=283100 + group)
    key = f"evaluation-{group}-{variant}"
    write_json(
        WORK / (key + "-sources.json"),
        {
            "source": str(source_path.relative_to(WORK)),
            "parents": chosen,
            "parent_hashes": [source.engines[i].capture_state().digest for i in chosen],
            "variant": variant,
            "traits": "identical ordinary bodies; brain inheritance only",
            "reproduction": "disabled equally in both evaluation arms",
        },
    )
    execute(key, Ocean(p, founder_images=images), 300)


def continuation(key):
    root = WORK / "cases" / key
    previous = complete(root)
    result = read_json(previous / "result.json")
    if result["status"] not in ("paused_error", "paused_resource_limit"):
        raise ValueError("only incomplete live segments need continuation")
    ocean = load_population(previous / "final")
    initial_hashes = ocean.capture()["core_hashes"]
    target = previous / "continuations/01"
    horizon = 300000000 if key.startswith("evaluation-") else 900000000
    execute(target.relative_to(WORK / "cases").as_posix(), ocean, (horizon - ocean.time_us) / 1e6)
    write_json(
        previous / "completion.json",
        {
            "segment": "continuations/01",
            "reason": result["error"],
            "initial_checkpoint_hashes": initial_hashes,
            "old_evidence": "preserved without changes",
        },
    )


def evaluate_all():
    for group in range(3):
        variants = ["inherited", "blank"] if group % 2 == 0 else ["blank", "inherited"]
        for variant in variants:
            folder = WORK / "cases" / f"evaluation-{group}-{variant}"
            result = complete(folder) / "result.json"
            if not result.exists():
                evaluation(group, variant)
            if read_json(complete(folder) / "result.json")["status"] not in ("horizon_paused", "extinct"):
                raise RuntimeError("unfinished evaluation needs explicit checkpoint continuation")


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "command",
        choices=[
            "calibrate",
            "freeze",
            "phase1",
            "phase1-all",
            "gate",
            "phase2",
            "evaluate",
            "evaluate-all",
            "continue",
        ],
    )
    p.add_argument("--group", type=int, choices=[0, 1, 2], default=0)
    p.add_argument("--mode", choices=["core", "passive", "random"], default="core")
    p.add_argument("--variant", choices=["inherited", "blank"], default="inherited")
    p.add_argument("--case")
    args = p.parse_args()
    if args.command == "calibrate":
        calibrate()
    elif args.command == "freeze":
        freeze()
    elif args.command == "phase1":
        phase1(args.group, args.mode)
    elif args.command == "phase1-all":
        phase1_all()
    elif args.command == "phase2":
        phase2(args.group)
    elif args.command == "evaluate":
        evaluation(args.group, args.variant)
    elif args.command == "evaluate-all":
        evaluate_all()
    elif args.command == "continue":
        continuation(args.case)
    else:
        stage_gate()


if __name__ == "__main__":
    main()
