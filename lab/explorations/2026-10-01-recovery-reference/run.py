"""Registered recovery, timing and exposure-matched experiments; Core unchanged."""

import argparse
import itertools
import random

from common import (
    ROOT,
    SEEDS,
    Study,
    attach_observer,
    checkpoint,
    fresh,
    ids,
    legacy_module,
    new_json,
    observe,
    old_sensory,
    progress,
    read_json,
    run_cli,
    saved,
    settings,
    sources,
    wait,
    write_gzip,
)

from lab.tools.state_exchange_cut import GROUPS, exchange_cut
from threemind_core import Stimulus

SENSORY_SEEDS = (930101, 930102, 930103, 930104)


def sensory_probe(study, key, seed, parent, meta, sign, physical, legacy, receipt=None):
    if saved(study, key):
        return
    c = fresh(study, key, seed, parent=parent, observe=True)
    if receipt is not None:
        write_gzip(c.folder / "exchange.json.gz", receipt)
        c.events.append(
            {
                "key": "persistent-cut",
                "kind": "research_intervention",
                "time_us": str(c.engine.time_us),
                "payload": receipt,
            }
        )
    before = checkpoint(c, "pre-probe")
    start = c.engine.time_us
    points = attach_observer(c, "sensory-state-probe")
    if physical:
        legacy.clip(c, sign, meta["mode"], legacy.dose(), observed=True)
    else:
        legacy.wait(c, start + legacy.EPISODE)
    c.session.begin_observation("sensory-after-input")
    legacy.trajectory(c, c.engine.time_us + legacy.PROBE_US)
    write_gzip(c.folder / "trajectory.json.gz", points)
    row = c.finish(
        meta
        | {
            "stage": "probe",
            "sign": sign,
            "physical": physical,
            "cue": 0.5 if physical else 0,
            "parent": parent["id"],
            "probe_start_us": start,
            "pre_probe_sha256": before.digest,
            "targets": [legacy.identities(seed)[x] for x in "AB"],
        }
    )
    if meta["family"] == "cut" and meta["groups"] == "none":
        original = read_json(
            ROOT
            / f".work/order-mechanisms-20261001/cases/sensory/{seed}/{meta['mode']}/learn{meta['learn']}/test11/sign{sign}/physical{int(physical)}/result.json"
        )
        assert row["state_sha256"] == original["state_sha256"], "sham must reproduce E21"


def sensory(study, args):
    legacy = legacy_module()
    for seed, mode, learn in itertools.product(args.block or SENSORY_SEEDS, ("full", "no_imu"), ("01", "11")):
        parent = old_sensory(study, seed, mode, learn)
        if args.stage == "cut":
            donor = old_sensory(study, seed, mode, "11" if learn == "01" else "01")
            for bits in itertools.product((0, 1), repeat=3):
                groups = tuple(g for g, enabled in zip(GROUPS, bits) if enabled)
                label = "".join(groups) or "none"
                image, receipt = exchange_cut(parent["image"], donor["image"], groups)
                meta = {
                    "family": "cut",
                    "mode": mode,
                    "learn": learn,
                    "groups": label,
                    "delay_s": 1,
                    "donor": donor["id"],
                }
                for sign, physical in itertools.product((1, -1), (False, True)):
                    key = f"cut/{seed}/{mode}/learn{learn}/{label}/sign{sign}/physical{int(physical)}"
                    sensory_probe(study, key, seed, parent | {"image": image}, meta, sign, physical, legacy, receipt)
                progress(study, key)
        else:
            for delay in (10, 30, 60):
                base = f"recovery/{seed}/{mode}/learn{learn}/wait{delay}"
                holding = saved(study, base + "/hold")
                if not holding:
                    c = fresh(study, base + "/hold", seed, parent=parent)
                    checkpoint(c, "initial")
                    legacy.wait(c, c.engine.time_us + (delay - 1) * 1000000)
                    holding = c.finish(
                        {
                            "family": "recovery",
                            "stage": "holding",
                            "mode": mode,
                            "learn": learn,
                            "delay_s": delay,
                            "parent": parent["id"],
                        }
                    )
                for sign, physical in itertools.product((1, -1), (False, True)):
                    key = base + f"/sign{sign}/physical{int(physical)}"
                    sensory_probe(study, key, seed, holding, holding["extra"], sign, physical, legacy)
                progress(study, key)


def schedule(family, order, phase=0, variant="fixed", cadence="dense", layout="shared"):
    frames = []
    if family in ("timing", "jitter"):
        jitter = random.Random(22001)
        offsets = [phase if variant == "fixed" else 40000 + jitter.randint(-40, 40) * 1000 for _ in range(12)]
        period = 2500000 if family == "timing" else 550000
        for i in range(12):
            for j, obj in enumerate(order):
                frames.append({"at": i * period + offsets[i] + j * 50000, "symbols": obj + "X"})
        end = 32200000 if family == "timing" else 7000000
    else:
        period, slots, end = (
            (1100000, (0, 50000, 550000, 600000), 13200000)
            if cadence == "dense"
            else (5000000, (0, 50000, 2500000, 2550000), 60000000)
        )
        refs = (
            {"A": "X", "B": "X", "C": "Z", "D": "Z"} if layout == "shared" else {"A": "X", "B": "Z", "C": "Z", "D": "X"}
        )
        for i in range(12):
            for obj, slot in zip(order + "CD", slots):
                frames.append({"at": i * period + slot, "symbols": obj + refs[obj]})
    return frames, end


def train(study, seed, meta, base):
    if row := saved(study, base + "/train"):
        return row
    c = fresh(study, base + "/train", seed, config={"stp_facilitation_tau_s": float(meta["tau"])})
    channels = ids(seed)
    c.send([channels["K"]], 0.2, at=0, source="maintenance-control")
    c.session.advance_to(0, guard=c.guard)
    c.next_keep = 500000 + meta.get("maintenance_phase_us", 0)
    frames, end = schedule(
        meta["family"],
        meta["order"],
        meta.get("phase_us", 0),
        meta.get("variant", "fixed"),
        meta.get("cadence", "dense"),
        meta.get("layout", "shared"),
    )
    snapshots = []
    for frame in frames:
        wait(c, frame["at"])
        before = c.engine.capture_state().to_dict()
        c.send([channels[x] for x in frame["symbols"]], 0.4, source="registered-course")
        c.session.advance_to(frame["at"], guard=c.guard)
        snapshots.append({"frame": frame, "before": before, "after": c.engine.capture_state().to_dict()})
    wait(c, end)
    c.send([channels["Y"]], 0.2, source="common-final-input")
    c.session.advance_to(end, guard=c.guard)
    write_gzip(c.folder / "teaching-states.json.gz", snapshots)
    row = c.finish(meta | {"stage": "training", "reference_time_us": end, "schedule": frames})
    if meta["family"] == "timing" and meta["maintenance_phase_us"] == 0:
        original = read_json(
            ROOT
            / f".work/order-mechanisms-20261001/cases/phase/{seed}/f{meta['tau']}/g50000/p{meta['phase_us']}/{meta['order']}/train/result.json"
        )
        assert row["state_sha256"] == original["state_sha256"], "timing teaching must reproduce E21"
    return row


def order_probe(study, parent, delay, cue):
    base = parent["key"].removesuffix("/train")
    key = base + f"/wait{delay}/cue{cue}"
    if saved(study, key):
        return
    c = fresh(study, key, parent["seed"], parent=parent, observe=True)
    wait(c, parent["extra"]["reference_time_us"] + delay * 1000000)
    meta = {k: v for k, v in parent["extra"].items() if k != "schedule"} | {
        "delay_s": delay,
        "parent": parent["id"],
        "cue_symbol": cue,
    }
    if cue != "XZ":
        row = observe(c, meta, 0 if cue == "none" else 0.5, channel=ids(c.seed).get(cue))
    else:
        before = checkpoint(c, "pre-probe")
        points = attach_observer(c, "joint-reference-probe")
        start = c.engine.time_us
        ch = ids(c.seed)
        c.send_stimulus(Stimulus(start, ((ch["X"], 0.5), (ch["Z"], 0.5)), 0.5), source="manual-research-probe")
        wait(c, start + 5000000)
        write_gzip(c.folder / "trajectory.json.gz", points)
        row = c.finish(
            meta
            | {
                "stage": "probe",
                "cue": 0.5,
                "probe_start_us": start,
                "pre_probe_sha256": before.digest,
                "targets": [ch["A"], ch["B"]],
            }
        )
    m = parent["extra"]
    if m["family"] == "timing" and m["maintenance_phase_us"] == 0:
        old = read_json(
            ROOT
            / f".work/order-mechanisms-20261001/cases/phase/{c.seed}/f{m['tau']}/g50000/p{m['phase_us']}/{m['order']}/wait30/cue{cue}/result.json"
        )
        assert row["state_sha256"] == old["state_sha256"], "timing expression must reproduce E21"


def courses(study, args):
    family = args.stage
    seeds = args.block or SEEDS
    if family == "timing":
        conditions = (
            {"family": family, "tau": tau, "phase_us": phase, "maintenance_phase_us": k, "order": order}
            for tau, phase, k, order in itertools.product((0, 1), (0, 40000, 60000), (0, 40000, 60000), ("AB", "BA"))
        )
    elif family == "jitter":
        conditions = (
            {"family": family, "tau": 0, "phase_us": 40000, "variant": variant, "order": order}
            for variant, order in itertools.product(("fixed", "jitter"), ("AB", "BA"))
        )
    else:
        conditions = (
            {"family": family, "tau": 0, "cadence": cadence, "layout": layout, "order": order}
            for cadence, layout, order in itertools.product(("dense", "sparse"), ("shared", "separate"), ("AB", "BA"))
        )
    for meta in conditions:
        for seed in seeds:
            suffix = (
                f"f{meta['tau']}/p{meta['phase_us']}/k{meta['maintenance_phase_us']}"
                if family == "timing"
                else meta["variant"]
                if family == "jitter"
                else f"{meta['cadence']}/{meta['layout']}"
            )
            base = f"{family}/{seed}/{suffix}/{meta['order']}"
            parent = train(study, seed, meta, base)
            for delay, cue in itertools.product(
                (1, 30) if family == "reference" else (30,),
                ("none", "X", "Z", "XZ") if family == "reference" else ("none", "X"),
            ):
                order_probe(study, parent, delay, cue)
            progress(study, base)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=("prepare", "cut", "recovery", "timing", "jitter", "reference", "status"))
    p.add_argument("--block", type=int, action="append")
    args = p.parse_args()
    if args.stage in ("prepare", "status"):
        study = Study(settings(), prepare=args.stage == "prepare")
        try:
            if args.stage == "prepare":
                sources(study)
                new_json(study.work / "jitter-plan.json", schedule("jitter", "AB", variant="jitter")[0])
                print(study.project, flush=True)
            else:
                rows = [read_json(p) for p in (study.work / "cases").rglob("result.json")]
                print(
                    {
                        "cases": len(rows),
                        "wall_seconds": sum(r["wall_seconds"] for r in rows),
                        "closed": (study.work / "STOP").exists(),
                    },
                    flush=True,
                )
        finally:
            study.db.close()
    else:
        run_cli(sensory if args.stage in ("cut", "recovery") else courses, args)
