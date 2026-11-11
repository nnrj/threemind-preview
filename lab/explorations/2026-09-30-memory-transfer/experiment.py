"""Bounded staged CLI; all writes go through public runtime and Lab services."""

import argparse
import copy
import gzip
import json
import math
import random
import time
from collections import deque

from common import WORK, Case, Study, encoded, load_case, new_json, prepare, read_json
from materials import (
    EPISODE,
    KERNEL,
    MODES,
    PERIOD,
    SEEDS,
    cart_spec,
    config,
    cue_unit,
    frame,
    identities,
    imu_channels,
    physical_clip,
    transform,
)

from threemind_runtime.world import PhysicalWorld

PRESETS = ("ordinary", "facilitation")
DELAYS = (1, 60, 300)
PROBE_US = 5_000_000


def saved(study, key):
    return load_case(study, key) if (WORK / "cases" / key / "result.json").exists() else None


def fresh(study, key, seed, preset, parent=None, observe=False, patch=None):
    study.guard(force=True)
    return Case(
        study,
        key,
        KERNEL,
        seed,
        parent=parent,
        config=patch if parent else (config(preset) | (patch or {})),
        observe=observe,
    )


def keep(c, until):
    # No future maintenance input remains queued after this interval.
    now = c.engine.time_us
    next_at = getattr(c, "next_keep", ((now + 499999) // 500000) * 500000)
    while next_at < until:
        c.send([identities(c.seed)["keep"]], 0.2, at=next_at, source="maintenance-control")
        next_at += 500000
    c.next_keep = next_at


def wait(c, until):
    keep(c, until)
    c.advance(until)


def push(c, unit, *, source="physical-replay"):
    c.send_stimulus(frame(unit), source=source, adapter="stimulus-units", payload={"units": [unit]})


def clip(c, sign, mode, intensity, *, marker=None, domain="original", interval=EPISODE, observed=False):
    start = c.engine.time_us
    units = transform(physical_clip(c.seed, sign, domain)["units"], mode, c.seed)
    for index, original in enumerate(units):
        u = copy.deepcopy(original)
        u["time_us"] = str(start + int(u["time_us"]))
        u["intensity"] = intensity
        if marker is not None:
            u["elements"].append({"channel": marker, "value": 0.5})
            u["measurements"].append({"controlled_marker": marker, "value": 0.5, "physical_measurement": False})
            u["grouping_basis"] = "declared experimental pairing of a physical sample and anonymous marker"
        push(c, u, source="manual-registered-probe" if observed and index == len(units) - 1 else "physical-replay")
    wait(c, start + interval)


def trajectory(c, until):
    keep(c, until)
    points = []
    start = c.engine.time_us
    c.session.advance_to(start, guard=c.guard)
    while True:
        points.append(
            {
                "relative_us": c.engine.time_us - start,
                "time_us": str(c.engine.time_us),
                "nodes": c.engine.observation_nodes(),
                "metrics": c.engine.metrics(),
            }
        )
        if c.engine.time_us >= until or c.engine.life == "dead":
            break
        c.advance(min(until, c.engine.time_us + 100000))
    return points


def finish(c, meta, points=None, physics=None):
    if points is not None:
        with gzip.open(c.folder / "trajectory.json.gz", "xb") as f:
            f.write(encoded(points))
    if physics is not None:
        with gzip.open(c.folder / "physics.json.gz", "xb") as f:
            f.write(encoded(physics))
    return c.finish(meta)


def observe(c, meta, channel, intensity=0.45):
    begin = c.engine.time_us
    before = c.engine.capture_state().digest
    envelope = None
    if channel is not None:
        unit = cue_unit(begin, channel, intensity)
        envelope = c.send_stimulus(
            frame(unit), source="manual-registered-probe", adapter="stimulus-units", payload={"units": [unit]}
        )
    points = trajectory(c, begin + PROBE_US)
    c.session.host.close(c.engine.time_us, "run_ended")
    if envelope is not None:
        assert any(e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema") for e in c.events), (
            "registered readout missing"
        )
    return finish(
        c,
        meta
        | {
            "stage": "probe",
            "before_probe": before,
            "begin_us": begin,
            "cue_channel": channel,
            "probe_intensity": intensity if channel is not None else 0,
            "probe_intensity_scope": "additional anonymous cue only; physical intensity is in the recorded stimulus units",
            "probe_envelope": envelope,
        },
        points,
    )


def calibrate(study):
    if (WORK / "calibration.json").exists():
        return
    rows = []
    for intensity in (0.03, 0.1, 0.3, 1.0):
        for preset in PRESETS:
            for mode in ("full", "no_imu"):
                key = f"calibration/{intensity}/{preset}/{mode}"
                r = saved(study, key)
                if not r:
                    c = fresh(study, key, 930199, preset)
                    values = []
                    for _ in range(12):
                        clip(c, 1, mode, intensity, marker=identities(c.seed)["A"])
                        nodes = c.engine.observation_nodes()
                        values.append(
                            next(
                                (
                                    n["activation"]
                                    for n in nodes
                                    if n["channel"] == identities(c.seed)["position_positive"]
                                ),
                                0,
                            )
                        )
                    r = finish(
                        c,
                        {
                            "family": "calibration",
                            "stage": "training",
                            "intensity": intensity,
                            "preset": preset,
                            "mode": mode,
                            "joint_responses": values,
                        },
                    )
                rows.append(r)
    scores = []
    for intensity in (0.03, 0.1, 0.3, 1.0):
        rs = [r for r in rows if r["extra"]["intensity"] == intensity]
        values = [v for r in rs for v in r["extra"]["joint_responses"][-6:]]
        valid = all(r["life"] == "active" for r in rs) and min(values) > 0.02
        saturation = sum(v >= 0.98 for v in values) / len(values)
        score = abs(sum(values) / len(values) - 0.45) + 2 * saturation
        scores.append(
            {
                "intensity": intensity,
                "valid": valid,
                "score": score,
                "mean": sum(values) / len(values),
                "saturation": saturation,
            }
        )
    valid = [s for s in scores if s["valid"] and s["saturation"] < 0.5]
    if not valid:
        new_json(WORK / "calibration-failed.json", scores)
        raise RuntimeError("no nonsaturated measurable common dose; stop before main experiment")
    selected = min(valid, key=lambda r: (r["score"], r["intensity"]))
    new_json(
        WORK / "calibration.json",
        {
            "selection_rule": "measurability and saturation, no answer scoring",
            "scores": scores,
            "selected": selected,
            "confirmatory_seeds_unseen": True,
        },
    )
    print(json.dumps({"stage": "calibration", "selected": selected}), flush=True)


def dose():
    return read_json(WORK / "calibration.json")["selected"]["intensity"]


def memory_parent(study, seed, preset, mode):
    key = f"memory/{seed}/{preset}/{mode}/train"
    if r := saved(study, key):
        return r
    c = fresh(study, key, seed, preset)
    order = (1, -1) if seed % 2 else (-1, 1)
    schedule = [order[0]] * 12 + [order[1]] * 12 + list(order) * 4
    for sign in schedule:
        if mode == "untrained":
            wait(c, c.engine.time_us + EPISODE)
        else:
            clip(c, sign, mode, dose(), marker=identities(seed)["A" if sign > 0 else "B"])
    return finish(
        c,
        {
            "family": "memory",
            "stage": "training",
            "preset": preset,
            "mode": mode,
            "schedule": schedule,
            "intensity": dose(),
        },
    )


def memory(study, seeds):
    for seed in seeds:
        for preset in PRESETS:
            for mode in (*MODES, "untrained"):
                p = memory_parent(study, seed, preset, mode)
                train_end = int(p["time_us"])
                for delay in DELAYS:
                    key = f"memory/{seed}/{preset}/{mode}/wait-{delay}"
                    hold = saved(study, key)
                    if not hold:
                        c = fresh(study, key, seed, preset, parent=p)
                        wait(c, train_end + delay * 1000000)
                        hold = finish(
                            c,
                            {
                                "family": "memory",
                                "stage": "retention",
                                "preset": preset,
                                "mode": mode,
                                "delay_s": delay,
                                "training_parent": p["id"],
                            },
                        )
                    for cue in ("none", "A", "B"):
                        key = f"memory/{seed}/{preset}/{mode}/wait-{delay}/{cue}"
                        if saved(study, key):
                            continue
                        c = fresh(study, key, seed, preset, parent=hold, observe=True)
                        observe(
                            c,
                            {
                                "family": "memory",
                                "preset": preset,
                                "mode": mode,
                                "delay_s": delay,
                                "cue": cue,
                                "parent": hold["id"],
                                "targets": [
                                    identities(seed)["position_positive"],
                                    identities(seed)["position_negative"],
                                ],
                                "expected": None if cue == "none" else int(cue == "B"),
                            },
                            None if cue == "none" else identities(seed)[cue],
                        )
            print(json.dumps({"stage": "memory", "seed": seed, "preset": preset}), flush=True)


def sequence_training(study, seed, preset, mode, assignment):
    key = f"sequence/{seed}/{preset}/{mode}/{assignment}/train"
    if r := saved(study, key):
        return r
    c = fresh(study, key, seed, preset)
    first = 1 if seed % 2 else -1
    schedule = [first] * 12 + [-first] * 12 + [first, -first] * 4
    labels = {sign: (["X", "Y"] * 8) for sign in (1, -1)}
    for sign, values in labels.items():
        random.Random(f"balanced-outcomes:{seed}:{sign}").shuffle(values)
    used = {1: 0, -1: 0}
    registered = []
    for sign in schedule:
        clip(c, sign, mode, dose(), marker=identities(seed)["C"])
        clip(c, -sign, mode, dose(), marker=identities(seed)["C"])
        # Exactly the same neutral ending and gap precede both anonymous outcomes.
        wait(c, c.engine.time_us + 500000)
        label = ("X" if sign > 0 else "Y") if assignment == "ordered" else labels[sign][used[sign]]
        used[sign] += 1
        c.send([identities(seed)["C"], identities(seed)[label]], 0.5, source="controlled-common-ending")
        wait(c, c.engine.time_us + 500000)
        registered.append({"first_sign": sign, "outcome": label})
    wait(c, c.engine.time_us + 1000000)
    return finish(
        c,
        {
            "family": "sequence",
            "stage": "training",
            "preset": preset,
            "mode": mode,
            "assignment": assignment,
            "schedule": registered,
        },
    )


def sequence(study, seeds):
    for seed in seeds:
        for preset in PRESETS:
            for mode in MODES:
                for assignment in ("ordered", "shuffled_outcomes"):
                    parent = sequence_training(study, seed, preset, mode, assignment)
                    for sign in (1, -1):
                        for delay in (0.5, 5):
                            key = f"sequence/{seed}/{preset}/{mode}/{assignment}/{sign}/delay-{delay}"
                            if saved(study, key):
                                continue
                            c = fresh(study, key, seed, preset, parent=parent, observe=True)
                            clip(c, sign, mode, dose(), marker=identities(seed)["C"])
                            clip(c, -sign, mode, dose(), marker=identities(seed)["C"])
                            wait(c, c.engine.time_us + round(delay * 1000000))
                            observe(
                                c,
                                {
                                    "family": "sequence",
                                    "preset": preset,
                                    "mode": mode,
                                    "assignment": assignment,
                                    "delay_s": delay,
                                    "order": "AB" if sign > 0 else "BA",
                                    "parent": parent["id"],
                                    "targets": [identities(seed)["X"], identities(seed)["Y"]],
                                    "expected": int(sign < 0),
                                },
                                identities(seed)["C"],
                            )
            print(json.dumps({"stage": "sequence", "seed": seed, "preset": preset}), flush=True)


def transfer(study, seeds):
    for seed in seeds:
        for preset in PRESETS:
            for mode in (*MODES, "untrained"):
                parent = load_case(study, f"memory/{seed}/{preset}/{mode}/wait-1")
                for domain in ("original", "angle", "gravity"):
                    for sign in (1, -1):
                        key = f"transfer/{seed}/{preset}/{mode}/{domain}/{sign}"
                        if saved(study, key):
                            continue
                        c = fresh(study, key, seed, preset, parent=parent, observe=True)
                        clip(c, sign, "full" if mode == "untrained" else mode, dose(), domain=domain, observed=True)
                        # Register the actual final physical input; add no observation-only stimulus.
                        observe(
                            c,
                            {
                                "family": "transfer",
                                "preset": preset,
                                "mode": mode,
                                "domain": domain,
                                "sign": sign,
                                "parent": parent["id"],
                                "targets": [identities(seed)["A"], identities(seed)["B"]],
                                "expected": int(sign < 0),
                            },
                            None,
                        )
            print(json.dumps({"stage": "transfer", "seed": seed, "preset": preset}), flush=True)


def cart_episode(c, force, mode, *, seconds=10, passive=False):
    spec = cart_spec(force)
    start = c.engine.time_us
    rows, delayed = [], deque()
    with PhysicalWorld(spec, c.seed) as world:
        initial = world.capture()
        for offset in range(0, seconds * 1000000, PERIOD):
            c.guard()
            now = start + offset
            if c.engine.life == "dead":
                break
            stimulus = world.sample(
                now, [] if passive else [(n["id"], n["activation"]) for n in c.engine.observation_nodes()]
            )
            u = world.stimulus_unit(stimulus, capture_us=world.elapsed_us)
            ids = imu_channels(u)
            inertial = [e for e in u["elements"] if e["channel"] in ids]
            if mode == "no_imu":
                u["elements"] = [e for e in u["elements"] if e["channel"] not in ids]
            elif mode == "no_proprioception":
                # This cart has only inertial and joint sensors; retain external maintenance input.
                assert all(
                    s.kind in ("accelerometer", "gyroscope", "joint_position", "joint_velocity") for s in spec.sensors
                )
                u["elements"] = []
            elif mode == "delayed_imu":
                delayed.append(copy.deepcopy(inertial))
                u["elements"] = [e for e in u["elements"] if e["channel"] not in ids] + (
                    delayed.popleft() if len(delayed) > 10 else []
                )
            u["intensity"] = dose()
            u["measurements"].append(
                {"research_intervention": mode, "delay_us": 200000 if mode == "delayed_imu" else 0}
            )
            if u["elements"]:
                push(c, u, source="closed-physical-world")
            wait(c, now + PERIOD)
            joint = world.data.joint("j_slide")
            x, v = float(joint.qpos[0]), float(joint.qvel[0])
            control = world.last_controls[0]["control"]
            rows.append(
                {
                    "relative_us": offset + PERIOD,
                    "x": x,
                    "v": v,
                    "control": control,
                    "nodes": c.engine.observation_nodes() if offset % 100000 == 0 else [],
                    "measurements": world.last_measurements,
                    "input_elements": u["elements"],
                }
            )
        end = world.capture()
    if not rows:
        return {"initial": initial, "final": end, "rows": [], "metrics": {"observed": False}}
    metrics = {
        "observed": True,
        "position_mse": math.fsum(r["x"] ** 2 for r in rows) / len(rows),
        "centre_fraction": sum(abs(r["x"]) <= 0.5 for r in rows) / len(rows),
        "limit_fraction": sum(abs(r["x"]) >= 1.95 for r in rows) / len(rows),
        "motor_work": math.fsum(abs(r["control"] * r["v"]) * PERIOD / 1e6 for r in rows),
        "mean_control": math.fsum(r["control"] for r in rows) / len(rows),
    }
    return {
        "spec": spec.model_dump(mode="json"),
        "initial": initial,
        "final": end,
        "rows": rows,
        "metrics": metrics,
        "force": force,
        "mode": mode,
        "passive": passive,
    }


def adaptation(study, seeds, *, presets=PRESETS, modes=("full", "no_imu", "delayed_imu")):
    for seed in seeds:
        for preset in presets:
            for mode in modes:
                for force in (0.06, -0.06):
                    for learning in (True, False):
                        base = f"adaptation/{seed}/{preset}/{mode}/{force}/{learning}"
                        parent = saved(study, base + "/train")
                        if not parent:
                            c = fresh(
                                study, base + "/train", seed, preset, patch={"edge_consolidation_enabled": learning}
                            )
                            episodes = [cart_episode(c, force, mode) for _ in range(3)]
                            parent = finish(
                                c,
                                {
                                    "family": "adaptation",
                                    "stage": "training",
                                    "preset": preset,
                                    "mode": mode,
                                    "force": force,
                                    "consolidation": learning,
                                    "episodes": [e["metrics"] for e in episodes],
                                },
                                physics=episodes,
                            )
                        for test_force in (force, -force):
                            key = base + f"/test-{test_force}"
                            if saved(study, key):
                                continue
                            c = fresh(study, key, seed, preset, parent=parent)
                            episode = cart_episode(c, test_force, mode)
                            finish(
                                c,
                                {
                                    "family": "adaptation",
                                    "stage": "evaluation",
                                    "preset": preset,
                                    "mode": mode,
                                    "force": force,
                                    "test_force": test_force,
                                    "consolidation": learning,
                                    "parent": parent["id"],
                                    "behavior": episode["metrics"],
                                },
                                physics=[episode],
                            )
            print(json.dumps({"stage": "adaptation", "seed": seed, "preset": preset}), flush=True)


def without_body(study, seeds):
    adaptation(study, seeds, presets=("ordinary",), modes=("no_proprioception",))


def passive():
    path = WORK / "passive-cart.json"
    if path.exists():
        return
    rows = []
    for force in (0.06, -0.06):
        with PhysicalWorld(cart_spec(force), SEEDS[0]) as w:
            initial, points = w.capture(), []
            for t in range(0, 10000000, PERIOD):
                w.sample(t, [])
                x = float(w.data.joint("j_slide").qpos[0])
                points.append({"time_us": t + PERIOD, "x": x})
            rows.append(
                {
                    "force": force,
                    "initial": initial,
                    "final": w.capture(),
                    "points": points,
                    "position_mse": sum(r["x"] ** 2 for r in points) / len(points),
                    "centre_fraction": sum(abs(r["x"]) <= 0.5 for r in points) / len(points),
                }
            )
    new_json(path, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage", choices=("prepare", "calibrate", "memory", "sequence", "transfer", "adaptation", "without_body")
    )
    parser.add_argument("--seed", action="append", type=int, choices=SEEDS)
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare()
        return
    study = Study()
    try:
        if args.stage == "calibrate":
            calibrate(study)
        else:
            if args.stage == "adaptation":
                passive()
            globals()[args.stage](study, args.seed or SEEDS)
        new_json(
            WORK / f"completed-{args.stage}-{'-'.join(map(str, args.seed or SEEDS))}.json", {"finished_at": time.time()}
        )
    except Exception as exc:
        stamp = str(time.time_ns())
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"budget_stop": True, "error": str(exc), "stage": "interrupted"})
        new_json(WORK / f"failure-{stamp}.json", {"type": type(exc).__name__, "error": str(exc), "stage": args.stage})
        raise
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
