"""Registered intensity study through public Runtime and Lab services."""

from __future__ import annotations

import argparse
import gzip
import itertools
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.service_study import Case, Study, StudyConfig, load_case, new_json, write_gzip
from threemind_core import Stimulus
from threemind_runtime.adapters import channel_id

HERE = Path(__file__).resolve().parent
WORK = ROOT / os.environ.get("THREEMIND_INTENSITY_STUDY_DIR", ".work/intensity-mechanisms-20260930")
KERNEL = "threemind.continuous-memory/2"
BLOCKS = {930401: (0.3, 0.5), 930402: (0.4, 1.0), 930411: (0.3, 1.0), 930412: (0.4, 0.5)}
HISTORIES = {
    "none": [],
    "single1": [(4.5, 1.0)],
    "single4": [(4.5, 4.0)],
    "repeat": [(i * 0.5, 0.4) for i in range(10)],
}


def settings():
    return StudyConfig(
        "intensity-mechanisms/1",
        "2026-09-30 强刺激机制替代与经历敏感性",
        HERE,
        WORK,
        int(os.environ.get("THREEMIND_INTENSITY_USAGE_START", "73")),
    )


def identities(seed):
    return {name: channel_id(seed, "intensity-mechanisms/1", i) for i, name in enumerate("ABCDK")}


def factor_config(i, f, learning):
    return {
        "intensity_gain": 0.075 if i else 0.0,
        "stp_facilitation_tau_s": float(f),
        "edge_consolidation_enabled": bool(learning),
    }


def saved(study, key):
    if not (study.work / "cases" / key / "result.json").exists():
        return None
    row = load_case(study, key)
    if row["extra"].get("failure"):
        raise RuntimeError(f"preserved failure at {key}; explicitly register a separately named retry")
    return row


def fresh(study, key, seed, **kwargs):
    study.guard(force=True)
    return Case(study, key, KERNEL, seed, **kwargs)


def wait(c, until):
    # A separate, disclosed carrier. Never merge it with task input.
    at = getattr(c, "next_keep", ((c.engine.time_us + 499999) // 500000) * 500000)
    while at < until:
        c.send([identities(c.seed)["K"]], 0.2, at=at, source="maintenance-control")
        at += 500000
    c.next_keep = at
    c.advance(until)
    c.session.advance_to(until, guard=c.guard)
    if c.engine.time_us != until or c.engine.life == "dead":
        raise RuntimeError("maintenance did not keep this instance active through its registered deadline")


def checkpoint(c, name):
    state = c.engine.capture_state()
    with gzip.open(c.folder / f"{name}.json.gz", "xb") as stream:
        stream.write(state.payload)
    return state


def parent(study, seed):
    key = f"parents/{seed}"
    if result := saved(study, key):
        return result
    c = fresh(study, key, seed)
    amplitude, interval = BLOCKS[seed]
    ids = identities(seed)
    for pair in ("AC", "BD"):
        for _ in range(12):
            c.send([ids[x] for x in pair], amplitude, source="prior-experience")
            wait(c, c.engine.time_us + round(interval * 1e6))
    wait(c, c.engine.time_us + 5_000_000)
    return c.finish({"stage": "parent", "prior_amplitude": amplitude, "prior_interval_s": interval})


def training(study, p, factors, history, *, prefix="matrix", patch=None):
    i, f, learning = factors
    key = f"{prefix}/{p['seed']}/i{i}f{f}l{learning}/{history}/train"
    if row := saved(study, key):
        return row
    cfg = factor_config(i, f, learning) | (patch or {})
    c = fresh(study, key, p["seed"], parent=p, config=cfg)
    ids = identities(c.seed)
    start = c.engine.time_us
    receipts = []
    for offset, dose in HISTORIES[history]:
        at = start + round(offset * 1e6)
        wait(c, at)
        before = c.engine.capture_state().to_dict()
        c.send([ids["A"], ids["B"]], dose, source="controlled-experience")
        c.session.advance_to(at, guard=c.guard)
        receipts.append(
            {"time_us": at, "intensity": dose, "before": before, "after": c.engine.capture_state().to_dict()}
        )
    wait(c, start + 4_500_000)
    write_gzip(c.folder / "teaching-effects.json.gz", receipts)
    return c.finish(
        {
            "stage": "train",
            "history": history,
            "factors": list(factors),
            "teaching_end_us": c.engine.time_us,
            "parent": p["id"],
            "patch": patch or {},
        }
    )


def probe(study, p, delay, cue, *, suffix="", patch=None, interventions=(), expression_patch=None):
    key = p["key"].removesuffix("/train") + f"/wait{delay}/cue{cue}{suffix}"
    if row := saved(study, key):
        return row
    c = fresh(study, key, p["seed"], parent=p, observe=True, config=patch)
    wait(c, c.engine.time_us + round(delay * 1e6))
    before = checkpoint(c, "pre-probe")
    audit = []
    if expression_patch:
        c.engine.reconfigure(replace(c.engine.config, **expression_patch))
        audit.append(
            {
                "configuration": expression_patch,
                "before": before.digest,
                "after": c.engine.capture_state().digest,
                "time_us": c.engine.time_us,
            }
        )
    for intervention in interventions:
        old = c.engine.capture_state().digest
        c.engine.intervene(**intervention)
        audit.append({"operation": intervention, "before": old, "after": c.engine.capture_state().digest})
    if audit:
        checkpoint(c, "after-intervention")
        c.events.append(
            {
                "key": "research:expression",
                "kind": "research_intervention",
                "time_us": str(c.engine.time_us),
                "payload": {"changes": audit},
            }
        )
    points = []
    original = c.session.host.observe

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
    c.session.begin_observation("matched-history-probe")
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
            "interventions": audit,
            "probe_patch": patch or {},
        }
    )


def run(study, seeds):
    for seed in seeds:
        p = parent(study, seed)
        for factors in itertools.product((0, 1), repeat=3):
            for history in HISTORIES:
                row = training(study, p, factors, history)
                for delay in (1, 30, 300):
                    for cue in (0.0, 0.5):
                        probe(study, row, delay, cue)
                print(
                    json.dumps(
                        {
                            "finished": row["key"],
                            "cases": study.completed_count,
                            "wall_seconds": round(study.completed_wall, 1),
                        }
                    ),
                    flush=True,
                )


def representations(study):
    rows = []
    for i in (0, 1):
        for value, strength in ((1.0, 1.0), (0.25, 4.0)):
            key = f"representations/i{i}/value{value}intensity{strength}"
            row = saved(study, key)
            if row is None:
                c = fresh(study, key, 930490, config=factor_config(i, 0, 1))
                ids = identities(c.seed)
                c.send_stimulus(
                    Stimulus(0, ((ids["A"], value), (ids["B"], value)), strength),
                    source="equal-incident",
                    adapter="anonymous-frames",
                )
                c.session.advance_to(0, guard=c.guard)
                checkpoint(c, "immediate")
                wait(c, 500000)
                row = c.finish({"stage": "representation", "i": i, "value": value, "intensity": strength})
            rows.append({"key": row["key"], "state_sha256": row["state_sha256"]})
    assert rows[0]["state_sha256"] == rows[1]["state_sha256"]
    new_json(study.work / "representation-check.json", rows)
    print(json.dumps(rows), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run", "representations", "status"))
    parser.add_argument("--block", type=int, choices=tuple(BLOCKS), action="append")
    args = parser.parse_args()
    study = Study(settings(), prepare=args.stage == "prepare")
    try:
        if args.stage == "run":
            run(study, args.block or list(BLOCKS))
        elif args.stage == "representations":
            representations(study)
        else:
            print(json.dumps({"project": study.project, "work": str(study.work)}), flush=True)
    except Exception as error:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            c = study.active_case
            try:
                c.finish({"failure": repr(error), "budget_stop": True})
            except Exception as save_error:  # noqa: BLE001 -- preserve both failures, then re-raise the original
                new_json(
                    c.folder / f"failure-{time.time_ns()}.json", {"error": repr(error), "save_error": repr(save_error)}
                )
        raise
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
