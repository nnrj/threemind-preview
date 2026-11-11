"""Prospectively registered, bounded follow-up; no Core dynamics edits."""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.service_study import GIB, Case, Study, StudyConfig, load_case, write_gzip
from threemind_kernels.novelty import NoveltyConfig
from threemind_runtime.adapters import channel_id

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/priority-memory-20261001"
KERNEL = "threemind.continuous-memory/2"
BLOCKS = {100101: (0.3, 0.5), 100102: (0.4, 1.0), 100111: (0.3, 1.0), 100112: (0.4, 0.5)}
TAUS = (0.0, 0.3, 1.0, 3.0)
END_US = 25_600_000
HISTORIES = {
    "none": [],
    "single1": [(END_US, 1.0)],
    "single4": [(END_US, 4.0)],
    "massed": [(END_US - 4_500_000 + k * 500_000, 0.4) for k in range(10)],
    "spaced": [(round(t * 1e6), 0.4) for t in (0, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8, 25.6)],
}
BASE = NoveltyConfig()
PROFILES = {
    "ordinary2": {"first_gain": 2 * BASE.first_gain, "repeat_gain": 2 * BASE.repeat_gain},
    "stability2": {"stability_gain": 2 * BASE.stability_gain},
}


def settings():
    return StudyConfig(
        "priority-memory/1",
        "2026-10-01 优先验证：强刺激保持与从出生易化",
        HERE,
        WORK,
        80,
        instance_limit=4096,
        wall_seconds=14400,
        storage_soft=10 * GIB,
        storage_hard=12 * GIB,
    )


def identities(seed):
    return {name: channel_id(seed, "priority-memory/1", i) for i, name in enumerate("ABCDEFGHK")}


def saved(study, key):
    path = study.work / "cases" / key / "result.json"
    if not path.exists():
        return None
    row = load_case(study, key)
    if row["extra"].get("failure"):
        raise RuntimeError(f"preserved failure: {key}; use a separately registered retry")
    return row


def fresh(study, key, seed, **kwargs):
    study.guard(force=True)
    return Case(study, key, KERNEL, seed, **kwargs)


def wait(c, until):
    if until < c.engine.time_us:
        raise ValueError("cannot go back to an earlier observation time")
    at = getattr(c, "next_keep", ((c.engine.time_us + 499999) // 500000) * 500000)
    while at < until:
        c.send([identities(c.seed)["K"]], 0.2, at=at, source="maintenance-control")
        at += 500000
    c.next_keep = at
    c.advance(until)
    c.session.advance_to(until, guard=c.guard)
    if c.engine.time_us != until or c.engine.life == "dead":
        raise RuntimeError("maintenance did not preserve active lifetime through registered deadline")


def checkpoint(c, name):
    image = c.engine.capture_state()
    with gzip.open(c.folder / f"{name}.json.gz", "xb") as out:
        out.write(image.payload)
    return image


def parent(study, seed, tau):
    key = f"parents/{seed}/f{tau:g}"
    if row := saved(study, key):
        return row
    c = fresh(study, key, seed, config={"stp_facilitation_tau_s": tau})
    ids, (amplitude, gap) = identities(seed), BLOCKS[seed]
    for pair in ("AC", "BD"):
        for _ in range(12):
            c.send([ids[x] for x in pair], amplitude, source="prior-experience")
            wait(c, c.engine.time_us + round(gap * 1e6))
    wait(c, c.engine.time_us + 5_000_000)
    return c.finish({"stage": "parent", "lifelong_tau_s": tau, "prior_amplitude": amplitude, "prior_gap_s": gap})


def training(study, p, intensity, history, profile="default"):
    tau = p["extra"]["lifelong_tau_s"]
    key = f"{profile}/{p['seed']}/i{intensity}f{tau:g}/{history}/train"
    if row := saved(study, key):
        return row
    patch = {"intensity_gain": 0.075 if intensity else 0.0} | PROFILES.get(profile, {})
    c = fresh(study, key, p["seed"], parent=p, config=patch)
    ids, start = identities(c.seed), c.engine.time_us
    receipts = []
    for offset, dose in HISTORIES[history]:
        at = start + offset
        wait(c, at)
        before = c.engine.capture_state().to_dict()
        c.send([ids["A"], ids["B"]], dose, source="controlled-experience")
        c.session.advance_to(at, guard=c.guard)
        receipts.append(
            {"time_us": at, "intensity": dose, "before": before, "after": c.engine.capture_state().to_dict()}
        )
    wait(c, start + END_US)
    write_gzip(c.folder / "teaching-effects.json.gz", receipts)
    return c.finish(
        {
            "stage": "train",
            "i": intensity,
            "lifelong_tau_s": tau,
            "history": history,
            "profile": profile,
            "parent": p["id"],
            "reference_time_us": c.engine.time_us,
            "patch": patch,
        }
    )


def probe(study, p, delay, cue):
    key = p["key"].removesuffix("/train") + f"/wait{delay:g}/cue{cue:g}"
    if row := saved(study, key):
        return row
    c = fresh(study, key, p["seed"], parent=p, observe=True)
    wait(c, p["extra"]["reference_time_us"] + round(delay * 1e6))
    before = checkpoint(c, "pre-probe")
    points, original = [], c.session.host.observe

    def passive(engine, *args, **kwargs):
        result = original(engine, *args, **kwargs)
        value = engine.capture_state().to_dict()
        points.append(
            {
                "time_us": engine.time_us,
                "nodes": value["nodes"],
                "edges": value["edges"],
                "operator_state": value.get("operator_state"),
                "transport": value["transport"],
            }
        )
        return result

    c.session.host.observe = passive
    c.session.begin_observation("matched-retention-probe")
    start = c.engine.time_us
    if cue:
        c.send([identities(c.seed)["A"]], cue, source="manual-research-probe")
    wait(c, start + 5_000_000)
    write_gzip(c.folder / "trajectory.json.gz", points)
    return c.finish(
        p["extra"]
        | {
            "stage": "probe",
            "delay_s": delay,
            "cue": cue,
            "parent": p["id"],
            "probe_start_us": start,
            "pre_probe_sha256": before.digest,
        }
    )


def interference(study, p, kind):
    key = "interference/" + p["key"].removesuffix("/train") + f"/{kind}/train"
    if row := saved(study, key):
        return row
    c = fresh(study, key, p["seed"], parent=p)
    ids, start = identities(c.seed), p["extra"]["reference_time_us"]
    for k in range(10):
        wait(c, start + 1_000_000 + k * 500000)
        c.send([ids[x] for x in kind], 0.4, source="interfering-experience")
        c.session.advance_to(c.engine.time_us, guard=c.guard)
    return c.finish(p["extra"] | {"stage": "interference", "interference": kind, "parent": p["id"]})


def progress(study, key):
    print(
        json.dumps(
            {"finished": key, "cases": study.completed_count, "wall_seconds": round(study.completed_wall, 2)},
            ensure_ascii=False,
        ),
        flush=True,
    )


def run(study, stage, seeds):
    for seed in seeds:
        if stage == "matrix":
            for tau in TAUS:
                p = parent(study, seed, tau)
                for i, history in itertools.product((0, 1), HISTORIES):
                    row = training(study, p, i, history)
                    for delay, cue in itertools.product((1, 30, 300), (0.0, 0.5)):
                        probe(study, row, delay, cue)
                    progress(study, row["key"])
        elif stage == "profiles":
            p = parent(study, seed, 1.0)
            for profile, history in itertools.product(PROFILES, ("single4", "massed", "spaced")):
                row = training(study, p, 0, history, profile)
                for delay, cue in itertools.product((1, 30, 300), (0.0, 0.5)):
                    probe(study, row, delay, cue)
                progress(study, row["key"])
        elif stage == "interference":
            for tau, i, history in itertools.product((0.0, 1.0), (0, 1), ("single4", "massed", "spaced")):
                p = parent(study, seed, tau)
                row = training(study, p, i, history)
                for kind in ("AC", "EF"):
                    changed = interference(study, row, kind)
                    for cue in (0.0, 0.5):
                        probe(study, changed, 30, cue)
                    progress(study, changed["key"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "matrix", "profiles", "interference", "status"))
    parser.add_argument("--block", type=int, choices=tuple(BLOCKS), action="append")
    args = parser.parse_args()
    study = Study(settings(), prepare=args.stage == "prepare")
    try:
        if args.stage in ("prepare", "status"):
            print(json.dumps({"project_id": study.project, "work": str(WORK)}, ensure_ascii=False), flush=True)
        else:
            study.allow_extension()
            run(study, args.stage, args.block or list(BLOCKS))
    except Exception as error:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"failure": repr(error), "budget_stop": True})
        raise
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
