"""E29 registration, independent worlds and explicitly declared external forks."""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import psutil

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_evolution import EvolutionOcean, EvolutionProtocol
from lab.tools.ocean_evolution_cli import apparatus, load_population, run
from lab.tools.ocean_view import recorded_segments
from lab.tools.service_study import Study, StudyConfig, digest

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/ocean-evolution-20261003"
ENGINEERING = ROOT / ".work/ocean-evolution-engineering-01"
RATE = 5.706242779562836
VERIFICATION_SECONDS = 4500


def study(prepare=False):
    return Study(
        StudyConfig(
            "ocean-evolution/1",
            "E29 稀疏海洋：身体耗能、变异与合作对照",
            HERE,
            WORK,
            3,
            instance_limit=2048,
            wall_seconds=50400,
            storage_soft=9 * 2**30,
            storage_hard=28 * 2**30,
            usage_soft_delta=8,
            usage_hard_delta=12,
        ),
        prepare=prepare,
    )


def protocol(group, mode):
    r = RATE
    return EvolutionProtocol(
        seed=290100 + 100 * group,
        environment_seed=291101 + group,
        mode=mode,
        initial_energy=240 * r,
        initial_body_energy=120 * r,
        core_capacity=2400 * r,
        storage_capacity=4800 * r,
        nutrient_energy=60 * r,
        child_energy=180 * r,
        child_body_energy=60 * r,
        reproduction_cost=30 * r,
        construction_energy=20 * r,
        parent_retained_food=120 * r,
        body_maintenance_per_s=0.05 * r,
        shell_barrier_energy=10 * r,
        mutation_sigma=0.0,
    ).model_dump(by_alias=True)


def freeze():
    if not read_json(ENGINEERING / "verification.json")["matched"]:
        raise RuntimeError("engineering replay required")
    recovering = (WORK / "platform.json").exists()
    if (WORK / "frozen.json").exists():
        raise RuntimeError("study already frozen")
    s = study(not recovering)
    try:
        if recovering:
            for language in ("zh", "en"):
                source = HERE / f"design.{language}.md"
                s.note(
                    f"design:{language}",
                    f"执行登记 / Study registration {language}",
                    source.read_text(encoding="utf-8"),
                )
                shutil.copy2(source, WORK / f"design-frozen.{language}.md")
            # Preserve the failed registration hash and document the link-only repair.
            write_json(
                WORK / "registration-recovery.json",
                {
                    "original_design_sha256": s.meta["design_sha256"],
                    "registered_design_sha256": hashlib.sha256((HERE / "design.zh.md").read_bytes()).hexdigest(),
                    "reason": "notebook rejected relative link; changed to supported local document URL before formal trials",
                },
            )
            for name in s.implementation["source_files"]:
                destination = WORK / "frozen-sources" / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, destination)
        (WORK / "cases").mkdir()
        shutil.copytree(ENGINEERING, WORK / "engineering")
        write_json(
            WORK / "usage.json",
            {
                "used_percent": 3,
                "actual_account_percent": 3,
                "carry_offset": 0,
                "observed_epoch": time.time(),
                "source": "account tool at registration",
            },
        )
        sources = apparatus()
        for name in sources:
            target = WORK / "apparatus-sources" / name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(ROOT / "lab/tools" / name, target)
        write_json(WORK / "apparatus-sources/manifest.json", sources)
        write_json(
            WORK / "frozen.json",
            {
                "rate": RATE,
                "horizon_us": 1800000000,
                "fork_duration_us": 900000000,
                "groups": [0, 1, 2],
                "fork_groups": [0, 1],
                "forks": ["ecology", "recombination", "transfer", "sharing"],
            },
        )
        (HERE / "protocols").mkdir(exist_ok=True)
        for g in range(3):
            for mode in ("core", "random"):
                write_json(HERE / "protocols" / f"phase1-{g}-{mode}.json", protocol(g, mode))
        print(json.dumps({"project_id": s.project, "registered": True}), flush=True)
    finally:
        s.db.close()


def latest(folder):
    return recorded_segments(folder)[-1]


def guard(s, world):
    # Check resource state at wall-clock intervals, without making database latency
    # a stimulus or rescanning thousands of files at every physical substep.
    if time.monotonic() - getattr(s, "external_check", 0) < 10:
        return
    s.external_check = time.monotonic()
    if getattr(s, "worker_marker", None):
        s.worker_marker["individuals"] = len(world.bodies)
        store_worker(s.worker_path, s.worker_marker)
    check_study(s)
    active = active_workers()
    elapsed = sum(time.time() - v["started_epoch"] for v in active if not (WORK / v["output"] / "result.json").exists())
    if s.completed_wall + elapsed >= s.settings.wall_seconds - VERIFICATION_SECONDS:
        raise RuntimeError("aggregate worker time; retain verification allowance")
    if sum(v["rss"] for v in active) > 4 * 2**30:
        raise RuntimeError("aggregate simulation worker RSS exceeds 4 GiB")
    counts = {}
    for p in (WORK / "cases").glob("*/result.json"):
        for attempt in range(20):
            try:
                counts[p.parent.name] = len(read_json(latest(p.parent) / "result.json")["members"])
                break
            except json.JSONDecodeError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
    counts.update({v["case"]: v["individuals"] for v in active})
    if sum(counts.values()) > 2048:
        raise RuntimeError("registered cumulative individual budget")


def store_worker(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def check_study(s, force=False):
    # Existing evidence writers expose an immutable file while finishing its JSON.
    # Retry only this short read race; never ignore a persistent malformed result.
    for attempt in range(20):
        try:
            s.guard(force=force or attempt > 0)
            return
        except json.JSONDecodeError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def active_workers():
    active = []
    for path in (WORK / "worker-status").glob("*.json"):
        value = read_json(path)
        if value["status"] != "running":
            continue
        try:
            process = psutil.Process(value["pid"])
            if process.create_time() != value["process_created"]:
                continue
            active.append(value | {"rss": process.memory_info().rss})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return active


def execute(key, world, duration_us, *, output=None, receipt=None):
    s = study()
    try:
        if apparatus() != read_json(WORK / "apparatus-sources/manifest.json"):
            raise RuntimeError("frozen apparatus changed")
        check_study(s, True)
        if key.startswith("fork-"):
            s.allow_extension()
        s.active_case = SimpleNamespace(born_wall=time.monotonic())
        destination = output or WORK / "cases" / key
        s.worker_path = WORK / "worker-status" / f"{key}.json"
        s.worker_marker = {
            "pid": os.getpid(),
            "process_created": psutil.Process().create_time(),
            "started_epoch": time.time(),
            "status": "running",
            "case": key,
            "output": destination.relative_to(WORK).as_posix(),
            "individuals": len(world.bodies),
        }
        store_worker(s.worker_path, s.worker_marker)
        answer = run(world, destination, duration_us, wall_seconds=7200, guard=lambda: guard(s, world))
        if receipt is not None:
            write_json(destination / "fork-receipt.json", receipt)
        print(
            json.dumps(
                {
                    "case": key,
                    "status": answer["status"],
                    "sim_seconds": answer["time_us"] / 1e6,
                    "observed_seconds": answer["observed_us"] / 1e6,
                    "wall_seconds": answer["wall_seconds"],
                    "alive": sum(m["life"] != "dead" for m in answer["members"]),
                    "individuals": len(answer["members"]),
                    "totals": answer["totals"],
                    "error": answer["error"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return answer
    finally:
        if getattr(s, "worker_marker", None):
            s.worker_marker.update(status="finished", ended_epoch=time.time())
            store_worker(s.worker_path, s.worker_marker)
        s.db.close()


def phase1_all():
    for group in range(3):
        modes = ("random", "core") if group == 1 else ("core", "random")
        for mode in modes:
            key = f"phase1-{group}-{mode}"
            folder = WORK / "cases" / key
            if folder.exists():
                r = read_json(latest(folder) / "result.json")
                if r["status"] in ("extinct", "horizon_paused") and (
                    r["status"] == "extinct" or r["time_us"] == 1800000000
                ):
                    continue
                raise RuntimeError(f"{key} requires explicit saved continuation")
            r = execute(key, EvolutionOcean(protocol(group, mode)), 1800000000)
            if r["status"] not in ("extinct", "horizon_paused"):
                return


def fork_all():
    for group in (0, 1):
        source = latest(WORK / "cases" / f"phase1-{group}-core") / "final"
        original = load_population(source)
        if not any(b.physical for b in original.bodies.values()):
            marker = WORK / f"fork-group-{group}-unavailable.json"
            if not marker.exists():
                write_json(marker, {"reason": "source has no physical survivors; no resurrection"})
            continue
        variants = ("ecology", "recombination", "transfer", "sharing")
        variants = variants[group:] + variants[:group]
        for variant in variants:
            key = f"fork-{group}-{variant}"
            folder = WORK / "cases" / key
            if folder.exists():
                r = read_json(latest(folder) / "result.json")
                if r["status"] in ("extinct", "horizon_paused") and (
                    r["status"] == "extinct" or r["time_us"] == original.time_us + 900000000
                ):
                    continue
                raise RuntimeError(f"{key} requires explicit saved continuation")
            before = original.capture()
            state = json.loads(json.dumps(before))
            updates = ecological_updates(original.p, variant)
            state["protocol"].update(updates)
            images = {i: e.capture_state() for i, e in original.engines.items()}
            world = EvolutionOcean(state["protocol"], state=state, images=images)
            after = world.capture()
            assert {k: v for k, v in before.items() if k != "protocol"} == {
                k: v for k, v in after.items() if k != "protocol"
            }
            receipt = {
                "schema": "ocean-external-fork/1",
                "source": str(source.relative_to(WORK)),
                "source_sha256": digest(before),
                "fork_sha256": digest(after),
                "protocol_changes": updates,
                "core_and_physical_state_unchanged": True,
                "source_manifest_sha256": hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest(),
            }
            r = execute(key, world, 900000000, receipt=receipt)
            if r["status"] not in ("extinct", "horizon_paused"):
                return


def continuation(key):
    root = WORK / "cases" / key
    old = latest(root)
    source = load_population(old / "final")
    target = (
        1800000000
        if key.startswith("phase1-")
        else read_json(root / "initial/manifest.json")["context"]["time_us"] + 900000000
    )
    duration = target - source.time_us
    if duration <= 0:
        raise ValueError("case already complete")
    parent = old / "continuations"
    index = 1
    while (parent / f"{index:02d}").exists():
        index += 1
    output = parent / f"{index:02d}"
    execute(key, source, duration, output=output)
    write_json(
        old / "completion.json",
        {
            "segment": str(output.relative_to(old)).replace("\\", "/"),
            "reason": "explicit saved continuation; original evidence unchanged",
        },
    )


def ecological_updates(p, variant):
    # Prospective amendment, shared by all four ecological arms. The parent
    # pays the extra reserve, so newborn motor fuel is not immediately digested.
    if not (WORK / "ecology-birth-budget-amendment.json").exists():
        raise RuntimeError("record the birth-budget amendment before ecological forks")
    updates = {"mutation_sigma": 0.12, "predation": True, "child_energy": p.initial_energy}
    if variant == "recombination":
        updates["recombination_probability"] = 0.25
    if variant == "transfer":
        updates["horizontal_transfer_probability"] = 0.25
    if variant == "sharing":
        updates["sharing_rate_per_s"] = 0.5
    return updates


def one_case(key):
    """One externally scheduled independent world; no shared simulation state."""
    if not re.fullmatch(r"(?:phase1-[012]-(?:core|random)|fork-[01]-(?:ecology|recombination|transfer|sharing))", key):
        raise ValueError("unregistered case key")
    folder = WORK / "cases" / key
    if folder.exists():
        r = read_json(latest(folder) / "result.json")
        target = (
            1800000000
            if key.startswith("phase1-")
            else read_json(folder / "initial/manifest.json")["context"]["time_us"] + 900000000
        )
        if r["status"] == "extinct" or (r["status"] == "horizon_paused" and r["time_us"] == target):
            print(json.dumps({"case": key, "status": "already_complete"}), flush=True)
            return
        continuation(key)
        return
    match = re.fullmatch(r"phase1-([012])-(core|random)", key)
    if match:
        execute(key, EvolutionOcean(protocol(int(match[1]), match[2])), 1800000000)
        return
    match = re.fullmatch(r"fork-([01])-(ecology|recombination|transfer|sharing)", key)
    if not match:
        raise ValueError("unregistered case key")
    group, variant = int(match[1]), match[2]
    source = latest(WORK / "cases" / f"phase1-{group}-core") / "final"
    original = load_population(source)
    if not any(b.physical for b in original.bodies.values()):
        marker = WORK / f"fork-group-{group}-unavailable.json"
        if not marker.exists():
            write_json(marker, {"reason": "source has no physical survivors; no resurrection"})
        print(json.dumps({"case": key, "status": "source_extinct"}), flush=True)
        return
    before = original.capture()
    state = json.loads(json.dumps(before))
    updates = ecological_updates(original.p, variant)
    state["protocol"].update(updates)
    images = {i: e.capture_state() for i, e in original.engines.items()}
    world = EvolutionOcean(state["protocol"], state=state, images=images)
    after = world.capture()
    assert {k: v for k, v in before.items() if k != "protocol"} == {k: v for k, v in after.items() if k != "protocol"}
    receipt = {
        "schema": "ocean-external-fork/1",
        "source": str(source.relative_to(WORK)),
        "source_sha256": digest(before),
        "fork_sha256": digest(after),
        "protocol_changes": updates,
        "core_and_physical_state_unchanged": True,
        "source_manifest_sha256": hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest(),
    }
    execute(key, world, 900000000, receipt=receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "phase1-all", "fork-all", "continue", "case"])
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.command == "freeze":
        freeze()
    elif args.command == "phase1-all":
        phase1_all()
    elif args.command == "fork-all":
        fork_all()
    elif args.command == "case":
        one_case(args.case)
    else:
        continuation(args.case)
