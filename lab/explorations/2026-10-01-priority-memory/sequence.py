"""Registered common-reference order experiment, using public runtime operations."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import shutil

from runner import HERE, WORK, checkpoint, fresh, identities, progress, saved, settings, wait

from lab.tools.service_study import Study, new_json, write_gzip
from threemind_runtime.adapters import channel_id

SEEDS = (100121, 100122, 100123, 100124)


def ids(seed):
    return identities(seed) | {s: channel_id(seed, "priority-sequence/1", i) for i, s in enumerate("XY")}


def register(study):
    path = WORK / "sequence-registration.json"
    if path.exists():
        return
    for lang in ("zh", "en"):
        source = HERE / f"sequence-design.{lang}.md"
        study.note(
            f"sequence-design:{lang}", f"顺序形成、保持与表达：事前登记 {lang}", source.read_text(encoding="utf-8")
        )
        shutil.copy2(source, WORK / source.name)
    new_json(path, {"design_sha256": hashlib.sha256((HERE / "sequence-design.zh.md").read_bytes()).hexdigest()})


def train(study, seed, tau, shared, gap, order):
    key = f"sequence/{seed}/f{tau:g}/shared{int(shared)}/gap{gap:g}/{order}/train"
    if row := saved(study, key):
        return row
    c = fresh(study, key, seed, config={"stp_facilitation_tau_s": tau})
    channels, receipts = ids(seed), []
    for _ in range(12):
        for i, letter in enumerate(order):
            before = c.engine.capture_state().to_dict()
            group = [channels[letter]] + ([channels["X"]] if shared else [])
            c.send(group, 0.4, source="controlled-order-course")
            c.session.advance_to(c.engine.time_us, guard=c.guard)
            receipts.append({"letter": letter, "before": before, "after": c.engine.capture_state().to_dict()})
            wait(c, c.engine.time_us + (round(gap * 1e6) if i == 0 else 500000))
    wait(c, c.engine.time_us + 200000)
    c.send([channels["Y"]], 0.2, source="common-final-input")
    c.session.advance_to(c.engine.time_us, guard=c.guard)
    write_gzip(c.folder / "teaching-effects.json.gz", receipts)
    return c.finish(
        {
            "stage": "sequence-train",
            "tau": tau,
            "shared": shared,
            "gap_s": gap,
            "order": order,
            "reference_time_us": c.engine.time_us,
        }
    )


def probe(study, parent, delay, cue):
    key = parent["key"].removesuffix("/train") + f"/wait{delay}/cue{cue:g}"
    if row := saved(study, key):
        return row
    c = fresh(study, key, parent["seed"], parent=parent, observe=True)
    wait(c, parent["extra"]["reference_time_us"] + delay * 1_000_000)
    before = checkpoint(c, "pre-probe")
    points, old = [], c.session.host.observe

    def passive(engine, *args, **kwargs):
        result = old(engine, *args, **kwargs)
        state = engine.capture_state().to_dict()
        points.append(
            {
                "time_us": engine.time_us,
                "nodes": state["nodes"],
                "edges": state["edges"],
                "operator_state": state["operator_state"],
                "transport": state["transport"],
            }
        )
        return result

    c.session.host.observe = passive
    c.session.begin_observation("common-reference-order-probe")
    start = c.engine.time_us
    if cue:
        c.send([ids(c.seed)["X"]], cue, source="manual-research-probe")
    wait(c, start + 5_000_000)
    write_gzip(c.folder / "trajectory.json.gz", points)
    return c.finish(
        parent["extra"]
        | {
            "stage": "sequence-probe",
            "delay_s": delay,
            "cue": cue,
            "parent": parent["id"],
            "probe_start_us": start,
            "pre_probe_sha256": before.digest,
        }
    )


def run(study, seeds):
    register(study)
    study.allow_extension()
    for seed, tau, shared, gap, order in itertools.product(
        seeds, (0.0, 1.0), (False, True), (0.05, 0.5, 2.0), ("AB", "BA")
    ):
        parent = train(study, seed, tau, shared, gap, order)
        for delay, cue in itertools.product((1, 30, 300), (0.0, 0.5)):
            probe(study, parent, delay, cue)
        progress(study, parent["key"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register-only", action="store_true")
    parser.add_argument("--block", type=int, choices=SEEDS, action="append")
    args = parser.parse_args()
    study = Study(settings())
    try:
        if args.register_only:
            register(study)
        else:
            run(study, args.block or SEEDS)
    except Exception as exc:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"failure": repr(exc), "budget_stop": True})
        raise
    finally:
        study.db.close()
