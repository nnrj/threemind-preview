"""AS63-01: registration, frozen parent-based selection, serial complete populations."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time
from uuid import uuid5

import ring as r
from lab.tools.study_lock import worker_lock

PROJECT = "d0a04159-ee0f-4200-ada9-13d5ce7197b7"
DEFAULT_WORK = r.ROOT / ".work/artificial-selection63-20261117"
ARMS = ("region0", "region1", "random")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def guard(work):
    import psutil
    if (work / "STOP").exists():
        raise RuntimeError("explicit STOP: preserve current state")
    if shutil.disk_usage(work).free < 25 * 2**30 or shutil.disk_usage("C:/").free < 5 * 2**30:
        raise RuntimeError("disk reserve reached")
    memory = psutil.virtual_memory()
    if memory.available < 4 * 2**30:
        raise RuntimeError("RAM reserve reached")
    info = psutil.Process().memory_info()
    if getattr(info, "private", info.rss) > 2**30:
        raise RuntimeError("1 GiB scientific host memory cap")
    # Existing Windows guard also checks commit reserve; no simulation effects.
    sys.path.insert(0, str(r.ROOT / "lab/explorations/2026-10-16-mechanism-discovery"))
    import pilot_m2
    pilot_m2.resource_check(work)


def select(candidates, arm, seed, generation):
    if arm == "random":
        return random.Random(seed + generation).sample(range(4), 2)
    return sorted(range(4), key=lambda i: (
        candidates[i]["selection_region1"] if arm == "region0" else -candidates[i]["selection_region1"], i))[:2]


def check_selection():
    candidates = [{"selection_region1": x, "test_region1": 1-x} for x in (.2, .8, .3, .7)]
    assert select(candidates, "region0", 7, 0) == [0, 2]
    assert select(candidates, "region1", 7, 0) == [1, 3]
    expected = select(candidates, "random", 7, 0)
    assert len(set(expected)) == 2
    for c in candidates:
        c["test_region1"] = 999
    assert select(candidates, "region0", 7, 0) == [0, 2]
    assert select(candidates, "random", 7, 0) == expected


def native_path():
    from _threemind_native import _threemind_native as native
    return Path(native.__file__)


def register(work):
    assert (work / "apparatus.json").exists() and r.read(work / "apparatus.json")["passed"]
    assert not (work / "registration.json").exists()
    assert not (work / "populations").exists()
    check_selection()
    guard(work)
    sources = [p for p in r.HERE.iterdir() if p.suffix in (".py", ".md")]
    production = [p for name in ("threemind_core", "threemind_kernels", "threemind_runtime")
                  for p in (r.ROOT / "src" / name).rglob("*.py")]
    frozen = {"kernel": r.KERNEL, "populations": list(r.SEEDS), "native_path": str(native_path()),
              "native_sha256": sha(native_path()), "registered_before_formal_subjects": True,
              "sources": {p.relative_to(r.ROOT).as_posix(): sha(p) for p in sources if p.name != "HANDOFF.md"},
              "production": {p.relative_to(r.ROOT).as_posix(): sha(p) for p in production}}
    r.save(work / "frozen.json", frozen)
    for p in sources + production:
        dest = work / "frozen-source" / p.relative_to(r.ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copyfile(p, dest)
        assert sha(dest) == sha(p)
    import httpx
    from threemind_lab.config import load_env
    from threemind_lab.operations_client import OperationsClient
    from threemind_lab.research_recorder import ResearchRecorder
    load_env()
    with OperationsClient(url="http://127.0.0.1:8877", username=os.environ.get("THREEMIND_API_USERNAME"),
                          password=os.environ.get("THREEMIND_API_PASSWORD"), token=os.environ.get("THREEMIND_API_TOKEN"),
                          transport=httpx.HTTPTransport(trust_env=False), reuse_session=False,
                          require_auth=True, source="ai") as client:
        rec = ResearchRecorder(work, PROJECT, client=client)
        rec.register({"source_key": "as63-01:artificial-selection:20261117:v1",
                      "title": "AS63-01：固定环形环境中的人工选择与代际保留",
                      "classification": "formal", "execution_status": "running", "executor": "ai",
                      "kernels": [r.KERNEL], "protocol": (r.HERE / "protocol.zh.md").read_text("utf8"),
                      "protocol_version": sha(r.HERE / "protocol.zh.md"),
                      "required_roles": ["protocol", "report", "note", "original"],
                      "metadata": {"independent_populations": 16, "generations": 3, "arms": 3,
                                   "planned_stages": 5056, "assessment_uses_birth": False,
                                   "fixed_regions": True, "instrument_seed": r.INSTRUMENT_SEED}},
                     request_id=uuid5(r.NS, "register"))
        for lang in ("zh", "en"):
            rec.text({"identity": str(uuid5(r.NS, "protocol-document-" + lang)),
                      "request_id": str(uuid5(r.NS, "protocol-" + lang)), "expected_revision": 0,
                      "kind": "protocol", "title": "AS63-01 protocol " + lang,
                      "markdown": (r.HERE / f"protocol.{lang}.md").read_text("utf8")})
        rec.synchronize(strict=True)
        r.save(work / "registration.json", {"project": PROJECT, "record": rec.experiment,
               "pending": rec.status["pending"], "registered_before_run": True})
    print(json.dumps(r.read(work / "registration.json")), flush=True)


def frozen_check(work):
    frozen = r.read(work / "frozen.json")
    for relative, expected in (frozen["sources"] | frozen["production"]).items():
        assert sha(r.ROOT / relative) == expected, relative
    assert sha(native_path()) == frozen["native_sha256"]
    assert r.read(work / "registration.json")["pending"] == 0


def population(work, seed):
    import psutil
    frozen_check(work)
    folder = work / "populations" / str(seed)
    if (folder / "complete.json").exists():
        return r.read(folder / "complete.json")
    if (work / "in-flight.json").exists():
        raise RuntimeError("prior in-flight evidence: inspect actual host before any continuation")
    start = time.monotonic()
    raw_at_start = sum(p.stat().st_size for p in work.rglob("*") if p.is_file())
    added_bytes = 0
    prior_wall = sum(r.read(p)["wall_seconds"] for p in (work / "populations").glob("*/complete.json"))
    r.save(work / "in-flight.json", {"seed": seed, "pid": os.getpid(),
           "created": psutil.Process().create_time(), "phase": "population"})
    last_check = 0.
    completed = 0
    def bounded():
        nonlocal last_check
        now = time.monotonic()
        if now - last_check >= 1:
            guard(work)
            last_check = now
        if prior_wall + now - start > 6 * 3600:
            raise RuntimeError("six-hour total scientific budget")
        if raw_at_start + added_bytes > 3 * 2**30:
            raise RuntimeError("3 GiB original evidence budget")

    def life(key, **kwargs):
        nonlocal completed, added_bytes
        result, state = r.execute(folder / key, key, seed, guard=bounded, **kwargs)
        added_bytes += sum(p.stat().st_size for p in (folder / key).iterdir() if p.is_file())
        completed += 1
        if completed % 8 == 0:
            gc.collect()
            progress = {"seed": seed, "stages_complete": completed, "planned": 316,
                        "latest": key, "wall_seconds": time.monotonic() - start,
                        "private_bytes": getattr(psutil.Process().memory_info(), "private", 0)}
            (work / "progress.json").write_text(json.dumps(progress), encoding="utf8")
            print(json.dumps(progress), flush=True)
        return result, state

    def candidate(key, generation, index, *, parent=None, parent_id=None, blank=False):
        result, state = life(key + "/development", parent=parent, position=r.STARTS[(index + generation) % 4],
                             blank_control=blank)
        source_hash = r.digest(state)
        if result["life"] == "dead":
            raise RuntimeError("candidate died; preserve before selecting or birthing from a dead candidate")
        scores, tests = [], []
        if not blank:
            for j, position in enumerate(r.SELECT_STARTS):
                score, _ = life(key + f"/selection-{j}", whole=state, position=position)
                assert score["ancestry"]["birth_called"] is False
                assert score["initial_core_hash"] == result["final_core_hash"]
                scores.append(score["region1"])
        for j, position in enumerate(r.TEST_STARTS):
            test, _ = life(key + f"/held-{j}", whole=state, position=position)
            assert test["ancestry"]["birth_called"] is False
            assert test["initial_core_hash"] == result["final_core_hash"]
            tests.append(test["region1"])
        assert r.digest(state) == source_hash
        row = {"key": key, "generation": generation, "index": index, "seed": seed,
               "parent_id": parent_id, "blank_control": blank, "development": result,
               "selection_scores": scores, "selection_region1": sum(scores) / len(scores) if scores else None,
               "test_scores": tests, "test_region1": sum(tests) / len(tests),
               "candidate_whole_hash": source_hash}
        r.save(folder / key / "candidate.json", row)
        return row

    g0 = [candidate(f"g0/c{i}", 0, i) for i in range(4)]
    decisions, groups, controls = [], {}, {}
    for arm in ARMS:
        previous = g0
        groups[arm], controls[arm] = {"0": g0}, {}
        for generation in (1, 2):
            chosen = select(previous, arm, seed, generation - 1)
            decision = {"arm": arm, "offspring_generation": generation,
                        "candidate_ids": [c["key"] for c in previous],
                        "selection_region1": [c["selection_region1"] for c in previous],
                        "selected_indices": chosen, "selected_ids": [previous[i]["key"] for i in chosen],
                        "rule": "candidate-own-complete-state-assessment", "held_out_scores_used": False,
                        "rng_seed": seed + generation - 1 if arm == "random" else None}
            r.save(folder / arm / f"g{generation}/decision.json", decision)
            decisions.append(decision)
            children, blanks = [], []
            for index in range(4):
                selected = previous[chosen[index // 2]]
                parent = r.read(folder / selected["key"] / "development/final.json.gz")
                key = f"{arm}/g{generation}/c{index}"
                children.append(candidate(key, generation, index, parent=parent, parent_id=selected["key"]))
                blanks.append(candidate(key + "-uninherited", generation, index, parent=parent,
                                        parent_id=selected["key"], blank=True))
            groups[arm][str(generation)] = children
            controls[arm][str(generation)] = blanks
            previous = children
    assert completed == 316
    report = {"seed": seed, "groups": groups, "uninherited": controls,
              "decisions": decisions, "stages": completed, "wall_seconds": time.monotonic() - start}
    r.save(folder / "complete.json", report)
    # Only the transient running marker is removed; scientific originals are immutable.
    (work / "in-flight.json").unlink()
    print(json.dumps({"population_complete": seed, "stages": completed,
                      "wall_seconds": report["wall_seconds"]}), flush=True)
    return report


def run(work, only_seed=None):
    frozen_check(work)
    lock = worker_lock(work)
    try:
        selected = [only_seed] if only_seed is not None else r.SEEDS
        for seed in selected:
            assert seed in r.SEEDS
            guard(work)
            if (work / "in-flight.json").exists():
                raise RuntimeError("in-flight marker must not be bypassed")
            existing = list((work / "populations").glob("*/complete.json")) if (work / "populations").exists() else []
            if sum(r.read(p)["wall_seconds"] for p in existing) >= 6 * 3600:
                raise RuntimeError("six-hour scientific budget")
            population(work, seed)
        completed = list((work / "populations").glob("*/complete.json"))
        if len(completed) == 16:
            r.save(work / "science-complete.json", {"populations": 16, "stages": 5056,
                   "wall_seconds": sum(r.read(p)["wall_seconds"] for p in completed)})
    finally:
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("register", "run", "check-selection"))
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if args.command == "register": register(args.work.resolve())
    elif args.command == "run": run(args.work.resolve(), args.seed)
    else: check_selection(); print("selection checks passed")
