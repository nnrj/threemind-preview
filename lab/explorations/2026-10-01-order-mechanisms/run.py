"""Three registered batches; no strong-input replacement and no Core edits."""

import argparse
import itertools

from common import (
    ROOT,
    SEEDS,
    Study,
    attach_observer,
    checkpoint,
    fresh,
    ids,
    legacy_module,
    observe,
    old_state,
    progress,
    read_json,
    run_cli,
    saved,
    settings,
    sources,
    wait,
    write_gzip,
)

from lab.tools.state_exchange import GROUPS, exchange


def swaps(study, args):
    for seed, tau, order in itertools.product(args.block or SEEDS, (0, 1), ("AB", "BA")):
        parent = old_state(study, seed, tau, order)
        donor = old_state(study, seed, tau, order[::-1])
        for bits in itertools.product((0, 1), repeat=4):
            groups = tuple(g for g, on in zip(GROUPS, bits) if on)
            label = "".join(groups) or "none"
            image, receipt = exchange(parent["image"], donor["image"], groups)
            for cue in (0, 0.5):
                key = f"swap/{seed}/f{tau}/{order}/{label}/cue{cue:g}"
                if saved(study, key):
                    continue
                c = fresh(study, key, seed, parent=parent | {"image": image}, observe=True)
                write_gzip(
                    c.folder / "exchange.json.gz", receipt | {"recipient_case": parent["id"], "donor_case": donor["id"]}
                )
                c.events.append(
                    {
                        "key": "state-exchange",
                        "kind": "research_intervention",
                        "time_us": str(c.engine.time_us),
                        "payload": receipt,
                    }
                )
                row = observe(
                    c,
                    {
                        "family": "swap",
                        "tau": tau,
                        "order": order,
                        "groups": label,
                        "parent": parent["id"],
                        "donor": donor["id"],
                        "delay_s": 30,
                    },
                    cue,
                )
                if not groups:
                    original = old_state(study, seed, tau, order, cue)
                    if row["state_sha256"] != original["state_sha256"]:
                        raise RuntimeError("sham exchange differs from exact old probe: " + key)
            progress(study, key)


def training(study, seed, tau, gap, phase, order, separate=False, cadence=False):
    prefix = "cadence" if cadence else "reference" if separate else "phase"
    key = f"{prefix}/{seed}/f{tau}/g{gap}/p{phase}/{order}/train"
    if row := saved(study, key):
        return row
    c = fresh(study, key, seed, config={"stp_facilitation_tau_s": float(tau)})
    channels = ids(seed)
    c.send([channels["K"]], 0.2, at=0, source="maintenance-control")
    c.session.advance_to(0, guard=c.guard)
    c.next_keep = 500000
    for i in range(12):
        for j, letter in enumerate(order):
            at = phase + i * (550000 if cadence else 2500000) + j * gap
            wait(c, at)
            reference = "Z" if separate and letter == "B" else "X"
            c.send([channels[letter], channels[reference]], 0.4, source="controlled-order-course")
            c.session.advance_to(at, guard=c.guard)
    wait(c, 7000000 if cadence else 32200000)
    c.send([channels["Y"]], 0.2, source="common-final-input")
    c.session.advance_to(c.engine.time_us, guard=c.guard)
    return c.finish(
        {
            "stage": "training",
            "family": prefix,
            "tau": tau,
            "gap_us": gap,
            "phase_us": phase,
            "order": order,
            "reference_time_us": c.engine.time_us,
            "separate": separate,
        }
    )


def phase(study, args):
    separate = args.stage == "reference"
    cadence = args.stage == "cadence"
    phases = (0, 40000) if separate else (0, 20000, 40000, 60000, 80000)
    gaps = (50000,) if separate or cadence else (50000, 500000, 2000000)
    for seed, tau, gap, offset, order in itertools.product(args.block or SEEDS, (0, 1), gaps, phases, ("AB", "BA")):
        parent = training(study, seed, tau, gap, offset, order, separate, cadence)
        for delay, cue in itertools.product((1, 30), ("none", "X", "Z") if separate else ("none", "X")):
            key = parent["key"].removesuffix("/train") + f"/wait{delay}/cue{cue}"
            if saved(study, key):
                continue
            c = fresh(study, key, seed, parent=parent, observe=True)
            wait(c, parent["extra"]["reference_time_us"] + delay * 1000000)
            observe(
                c,
                parent["extra"] | {"delay_s": delay, "parent": parent["id"], "cue_symbol": cue},
                0 if cue == "none" else 0.5,
                channel=ids(seed).get(cue),
            )
        progress(study, parent["key"])


def sensory(study, args):
    legacy = legacy_module()
    blocks = args.block or (930101, 930102, 930103, 930104)
    for seed, mode, d, c_on in itertools.product(blocks, ("full", "no_imu"), (0, 1), (0, 1)):
        key = f"sensory/{seed}/{mode}/learn{d}{c_on}/train"
        parent = saved(study, key)
        if not parent:
            c = fresh(study, key, seed, config={"depletion_enabled": bool(d), "context_enabled": bool(c_on)})
            order = (1, -1) if seed % 2 else (-1, 1)
            schedule = [order[0]] * 12 + [order[1]] * 12 + list(order) * 4
            for sign in schedule:
                legacy.clip(c, sign, mode, legacy.dose(), marker=legacy.identities(seed)["A" if sign > 0 else "B"])
            legacy.wait(c, c.engine.time_us + 1000000)
            parent = c.finish(
                {"family": "sensory", "stage": "training", "mode": mode, "learn": f"{d}{c_on}", "schedule": schedule}
            )
        for test_d, test_c, sign, physical in itertools.product((0, 1), (0, 1), (1, -1), (False, True)):
            key = parent["key"].removesuffix("/train") + f"/test{test_d}{test_c}/sign{sign}/physical{int(physical)}"
            if saved(study, key):
                continue
            c = fresh(
                study,
                key,
                seed,
                parent=parent,
                observe=True,
                config={"depletion_enabled": bool(test_d), "context_enabled": bool(test_c)},
            )
            before = checkpoint(c, "pre-probe")
            start = c.engine.time_us
            points = attach_observer(c, "sensory-formation-probe")
            if physical:
                legacy.clip(c, sign, mode, legacy.dose(), observed=True)
            else:
                legacy.wait(c, start + legacy.EPISODE)
            c.session.begin_observation("sensory-after-input")
            legacy.trajectory(c, c.engine.time_us + legacy.PROBE_US)
            write_gzip(c.folder / "trajectory.json.gz", points)
            row = c.finish(
                {
                    "family": "sensory",
                    "stage": "probe",
                    "mode": mode,
                    "learn": f"{d}{c_on}",
                    "test": f"{test_d}{test_c}",
                    "sign": sign,
                    "physical": physical,
                    "cue": 0.5 if physical else 0,
                    "parent": parent["id"],
                    "probe_start_us": start,
                    "pre_probe_sha256": before.digest,
                    "targets": [legacy.identities(seed)[x] for x in "AB"],
                }
            )
            if physical and (d, c_on, test_d, test_c) == (1, 1, 1, 1):
                old = read_json(
                    ROOT
                    / f".work/memory-transfer-20260930/cases/transfer/{seed}/ordinary/{mode}/original/{sign}/result.json"
                )
                if row["state_sha256"] != old["state_sha256"]:
                    raise RuntimeError("all-on sensory replay differs from E18: " + key)
        progress(study, parent["key"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=("prepare", "swap", "phase", "cadence", "reference", "sensory", "status"))
    p.add_argument("--block", type=int, action="append")
    args = p.parse_args()
    if args.stage == "prepare":
        study = Study(settings(), prepare=True)
        try:
            sources(study)
            print(study.project, flush=True)
        finally:
            study.db.close()
    elif args.stage == "status":
        study = Study(settings())
        try:
            if (study.work / "STOP").exists():
                # Closing simulation must not make the read-only status command unusable.
                rows = [read_json(path) for path in (study.work / "cases").rglob("result.json")]
                print(
                    {
                        "status": "closed",
                        "cases": len(rows),
                        "wall_seconds": round(sum(row["wall_seconds"] for row in rows), 2),
                        "audit_available": (study.work / "audit.json").exists(),
                        "delivery_available": (study.work / "delivery.json").exists(),
                    },
                    flush=True,
                )
            else:
                study.guard(force=True)
                progress(study, "status")
                print({"storage_gib": study.storage_bytes / 2**30}, flush=True)
        finally:
            study.db.close()
    else:
        run_cli(swaps if args.stage == "swap" else sensory if args.stage == "sensory" else phase, args)
