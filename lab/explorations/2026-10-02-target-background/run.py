"""One bounded E24 worker. All model input, snapshots and evidence use existing services."""

import argparse
import gzip
import itertools
import json
import random
import time

from common import (
    KINDS,
    SEEDS,
    WORK,
    Stimulus,
    Study,
    finish,
    freeze_sources,
    fresh,
    historical,
    ids,
    make_materials,
    new_json,
    read_json,
    saved,
    settings,
    wait,
)

from lab.tools.study_lock import worker_lock
from threemind_lab.telemetry import RuntimeTelemetry
from threemind_runtime.event_observation import advance_observed

TELEMETRY = {"enabled": True, "intensity": 0.2, "sample_interval_ms": 500}


def live_advance(c, until, dense):
    """Real sampling, with production advancement-meter boundaries preserved."""
    telemetry = RuntimeTelemetry(c.spec, c.id)
    start, wall0 = c.engine.time_us, time.monotonic()
    tape = [{"queued_at_us": start, "stimulus": dict(f["stimulus"])} for f in c.inputs.changes["frames"]]
    count, spent = 0, 0.0
    stream = gzip.open(c.folder / "dense-states.jsonl.gz", "xb") if dense else None  # noqa: SIM115 -- closed in finally
    try:
        for target in range(start + 20000, until + 1, 20000):
            remaining = wall0 + (target - start) / 1e6 - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            first = True
            while first or c.engine.time_us < target and c.engine.life != "dead":
                first = False
                c.guard()
                boundary = min(target, c.engine.time_us + min(20000, c.engine.config.step_us * 10))
                if c.session.host.next_us is not None:
                    boundary = min(boundary, max(c.engine.time_us, c.session.host.next_us))
                if c.session.bus.next_time_us is not None:
                    boundary = min(boundary, max(c.engine.time_us, c.session.bus.next_time_us))
                t0, p0 = time.monotonic(), time.thread_time()
                advance_observed(c.engine, boundary, c.session.observe_event, record_spikes=True)
                telemetry.measured(
                    time.monotonic() - t0, time.thread_time() - p0, max(0, t0 - (wall0 + (boundary - start) / 1e6))
                )
                c.session.host.observe(c.engine)
                if c.engine.time_us >= target or c.engine.life == "dead":
                    break
            if stream:
                before = time.process_time()
                stream.write(c.engine.capture_state().payload + b"\n")
                stream.flush()
                spent += time.process_time() - before
                count += 1
            previous = len(c.inputs.changes["frames"])
            telemetry.poll(c.inputs, c.events.append, source_enabled=True)
            tape.extend(
                {"queued_at_us": c.engine.time_us, "stimulus": dict(f["stimulus"])}
                for f in c.inputs.changes["frames"][previous:]
            )
            c.sample()
            if c.engine.life == "dead":
                break
    finally:
        if stream:
            stream.close()
    new_json(c.folder / "actual-tape.json", tape)
    return {
        "telemetry": telemetry.capture(),
        "realtime_wall_s": time.monotonic() - wall0,
        "dense_reads": count,
        "dense_process_cpu_s": spent,
        "meter_scope": "advance_observed thread CPU and wall; readout excluded",
    }


def live_case(study, key, seed, *, parent=None, duration=6000000, dense=False, cue=True):
    if row := saved(study, key):
        return row
    runtime = {
        "clock": "realtime",
        **{k: TELEMETRY for k in ("host_telemetry", "process_telemetry", "runtime_telemetry")},
    }
    c = fresh(
        study, key, seed, parent=parent, config=None if parent else historical(seed, "AB")["config"], runtime=runtime
    )
    start = c.engine.time_us
    for at in range(start, start + duration, 500000):
        c.send([ids(seed)["K"]], 0.2, at=at, source="common-live-maintenance")
    if cue:
        c.send([ids(seed)["X"]], 0.5, at=start + 1000000, source="live-probe")
    meta = live_advance(c, start + duration, dense)
    return finish(c, meta | {"stage": "live" if parent else "acquisition", "dense": dense, "start_us": start})


def acquire(study):
    for seed in SEEDS:
        live_case(study, f"acquisition/{seed}", seed, duration=44000000, cue=False)
        if not (WORK / f"materials/{seed}-telemetry.json").exists():
            make_materials(seed)


def train(study, seed, kind, order):
    key = f"matrix/{seed}/{kind}/{order}/train"
    if row := saved(study, key):
        return row
    c = fresh(study, key, seed, config=historical(seed, order)["config"])
    for i in range(12):
        for j, symbol in enumerate(order):
            at = i * 550000 + 40000 + j * 50000
            wait(c, kind, at)
            if c.engine.life == "dead":
                return finish(c, {"stage": "training", "background": kind, "order": order, "early_death": True})
            c.send([ids(seed)[symbol], ids(seed)["X"]], 0.4, source="registered-course")
            c.session.advance_to(at, guard=c.guard)
    wait(c, kind, 7000000)
    if c.engine.life != "dead":
        c.send([ids(seed)["Y"]], 0.2, source="common-final-input")
        c.session.advance_to(7000000, guard=c.guard)
    return finish(c, {"stage": "training", "background": kind, "order": order})


def probe(study, parent, kind, order, delay, cue, key):
    if row := saved(study, key):
        return row
    c = fresh(study, key, parent["seed"], parent=parent, observe=True)
    wait(c, kind, 7000000 + delay * 1000000)
    alive, start = c.engine.life != "dead", c.engine.time_us
    image = c.engine.capture_state()
    with gzip.open(c.folder / "pre-probe.json.gz", "xb") as out:
        out.write(image.payload)
    if alive:
        c.session.begin_observation("registered-target-window")
        if cue:
            c.send([ids(c.seed)["X"]], 0.5, source="registered-probe")
        wait(c, kind, start + 5000000)
    return finish(
        c,
        {
            "stage": "probe",
            "background": kind,
            "order": order,
            "delay_s": delay,
            "cue": cue,
            "probe_available": alive,
            "probe_start_us": start,
            "pre_probe_sha256": image.digest,
            "complete_window": alive and c.engine.time_us == start + 5000000,
        },
    )


def matrix(study):
    for seed, kind, order in itertools.product(SEEDS, KINDS, ("AB", "BA")):
        parent = train(study, seed, kind, order)
        for delay, cue in itertools.product((1, 30), (False, True)):
            probe(
                study,
                parent,
                kind,
                order,
                delay,
                cue,
                parent["key"].removesuffix("/train") + f"/wait{delay}/cue{int(cue)}",
            )


def expression(study):
    for kind, order, cue in itertools.product(KINDS, ("AB", "BA"), (False, True)):
        parent = historical(SEEDS[0], order)
        probe(study, parent, kind, order, 1, cue, f"expression/{kind}/{order}/cue{int(cue)}")


def replay(study, original, parent, cue):
    key = original["key"] + ("/replay" if cue else "/no-cue")
    if row := saved(study, key):
        return row
    c = fresh(study, key, parent["seed"], parent=parent, observe=True)
    tape = read_json(WORK / "cases" / original["key"] / "actual-tape.json")
    if not cue:
        tape = [f for f in tape if ids(c.seed)["X"] not in {int(n) for n, _ in f["stimulus"]["channels"]}]
    position = 0

    def enqueue():
        nonlocal position
        while position < len(tape) and tape[position]["queued_at_us"] == c.engine.time_us:
            c.send_stimulus(Stimulus.from_dict(tape[position]["stimulus"]), source="actual-live-tape")
            position += 1

    enqueue()
    start = c.engine.time_us
    for at in range(start + 20000, int(original["time_us"]) + 1, 20000):
        c.session.advance_to(at, guard=c.guard)
        enqueue()
        if at == start + 1000000:
            c.session.begin_observation("live-target-probe")
        c.sample()
    row = finish(
        c,
        {
            "stage": "live-replay",
            "original": original["key"],
            "cue": cue,
            "order": parent["extra"]["order"],
            "probe_start_us": start + 1000000,
        },
    )
    assert position == len(tape)
    if cue:
        assert row["state_sha256"] == original["state_sha256"], "actual-input replay mismatch"
    return row


def live(study):
    modes = read_json(WORK / "live-order.json")
    for block, seed in enumerate(SEEDS):
        parent = historical(seed, "AB" if block % 2 == 0 else "BA")
        for mode in modes[str(seed)]:
            row = live_case(study, f"live/{seed}/{mode}", seed, parent=parent, dense=mode == "dense")
            replay(study, row, parent, True)
            replay(study, row, parent, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "acquire", "matrix", "expression", "live"))
    args = parser.parse_args()
    lock = worker_lock(WORK)
    study = Study(settings(), prepare=args.stage == "prepare")
    try:
        if args.stage == "prepare":
            freeze_sources()
            rng = random.Random(24001)
            new_json(WORK / "live-order.json", {str(s): rng.sample(["minimal", "dense"], 2) for s in SEEDS})
            new_json(WORK / "usage.json", {"used_percent": 93})
            print(json.dumps({"project": study.project}), flush=True)
        else:
            study.allow_extension()
            globals()[args.stage](study)
    except Exception as error:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"failure": repr(error), "budget_stop": True})
        raise
    finally:
        study.db.close()
        lock.close()
