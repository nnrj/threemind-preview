"""Run preregistered E23 phases. No Core writes or dynamics changes."""

import argparse
import hashlib
import itertools
import os
import time

from common import (
    SEEDS,
    WORK,
    Study,
    background,
    checkpoint,
    encoded,
    fresh,
    ids,
    load_case,
    new_json,
    old_folder,
    prepare_sources,
    progress,
    read_json,
    saved,
    settings,
    targets,
    wait,
    write_gzip,
)

from lab.tools.study_lock import worker_lock
from threemind_core import Stimulus
from threemind_lab.telemetry import RuntimeTelemetry
from threemind_runtime.event_observation import advance_observed


class Observation:
    def __init__(self, case, mode):
        self.c, self.mode, self.points = case, mode, []
        self.calls, self.cpu, self.wall, self.bytes = 0, 0.0, 0.0, 0
        original = case.session.host.observe
        self.stream = (case.folder / "observer-output.bin").open("xb") if mode in ("dense", "dummy") else None

        def observe(engine, *args, **kwargs):
            w, p = time.perf_counter(), time.process_time()
            result = original(engine, *args, **kwargs)
            if self.mode in ("dense", "discard"):
                state = engine.capture_state().to_dict()
                point = {k: state[k] for k in ("time_us", "nodes", "edges", "operator_state", "transport")}
                raw = encoded(point)
                if self.mode == "dense":
                    self.points.append(point)
                    self.stream.write(raw + b"\n")
                    self.stream.flush()
                    self.bytes += len(raw) + 1
            elif self.mode == "dummy":
                value = b"E23 independent load" * 256
                deadline = time.perf_counter() + 0.002
                while time.perf_counter() < deadline:
                    value = hashlib.sha256(value).digest() * 128
                self.stream.write(b"0" * 8192)
                self.stream.flush()
                self.bytes += 8192
            self.calls += 1
            self.cpu += time.process_time() - p
            self.wall += time.perf_counter() - w
            return result

        case.session.host.observe = observe

    def close(self):
        if self.stream:
            self.stream.close()
        return {
            "mode": self.mode,
            "calls": self.calls,
            "cpu_seconds": self.cpu,
            "wall_seconds": self.wall,
            "bytes_written": self.bytes,
        }


def finish(c, obs, meta):
    if obs.points:
        write_gzip(c.folder / "trajectory.json.gz", obs.points)
    meta = meta | {"observation": obs.close()}
    return c.finish(meta)


def train(study, seed, kind, order, mode, namespace="replication-v2"):
    key = f"{namespace}/{seed}/{kind}/{order}/{mode}/train"
    if row := saved(study, key):
        return row
    original = read_json(old_folder(seed, order) / "result.json")
    c = fresh(study, key, seed, config=original["config"], observe=mode == "dense")
    obs = Observation(c, mode)
    if mode == "dense":
        c.session.begin_observation("E23-training")
    background(c, kind, 1)
    c.session.advance_to(0, guard=c.guard)
    for i in range(12):
        for j, symbol in enumerate(order):
            at = i * 550000 + 40000 + j * 50000
            wait(c, kind, at)
            if c.engine.life == "dead":
                raise RuntimeError("death before teaching finished")
            c.send([ids(seed)[symbol], ids(seed)["X"]], 0.4, source="registered-course")
            c.session.advance_to(at, guard=c.guard)
    wait(c, kind, 7000000)
    if c.engine.life != "dead":
        c.send([ids(seed)["Y"]], 0.2, source="common-final-input")
        c.session.advance_to(7000000, guard=c.guard)
    row = finish(c, obs, {"stage": "training", "background": kind, "order": order, "reference_time_us": 7000000})
    if kind == "periodic":
        assert row["state_sha256"] == original["state_sha256"], "E22 teaching mismatch"
    return row


def probe(study, parent, kind, order, mode, delay, cue, key=None):
    key = key or parent["key"].removesuffix("/train") + f"/wait{delay}/cue{cue}"
    if row := saved(study, key):
        return row
    c = fresh(study, key, parent["seed"], parent=parent, observe=mode in ("dense", "discard"))
    obs = Observation(c, mode)
    wait(c, kind, 7000000 + delay * 1000000)
    before = checkpoint(c, "pre-probe")
    start, alive = c.engine.time_us, c.engine.life != "dead"
    obs.points.clear()  # Full probe trajectory excludes the waiting period.
    if alive:
        if mode in ("dense", "discard"):
            c.session.begin_observation("E23-probe")
        if cue == "X":
            c.send([ids(c.seed)["X"]], 0.5, source="manual-research-probe")
        wait(c, kind, start + 5000000)
    row = finish(
        c,
        obs,
        {
            "stage": "probe",
            "background": kind,
            "order": order,
            "delay_s": delay,
            "cue": cue,
            "probe_available": alive,
            "probe_start_us": start,
            "planned_probe_us": 7000000 + delay * 1000000,
            "pre_probe_sha256": before.digest,
            "complete_window": alive and c.engine.time_us == start + 5000000,
            "target_values": targets(obs.points, c.seed) if alive and mode == "dense" else None,
        },
    )
    if kind == "periodic" and delay == 30:
        old = read_json(old_folder(c.seed, order, f"wait30/cue{cue}") / "result.json")
        assert old["state_sha256"] == row["state_sha256"], "E22 probe mismatch"
    return row


def replication(study):
    for kind, seed, order in itertools.product(("periodic", "none", "random"), SEEDS, ("AB", "BA")):
        rows = {}
        for mode in ("minimal", "dense"):
            parent = train(study, seed, kind, order, mode)
            rows[(mode, "train")] = parent
            for delay, cue in itertools.product((1, 30), ("none", "X")):
                rows[(mode, delay, cue)] = probe(study, parent, kind, order, mode, delay, cue)
        for condition in ("train", (1, "none"), (1, "X"), (30, "none"), (30, "X")):
            suffix = (condition,) if isinstance(condition, str) else condition
            a, b = rows[("minimal", *suffix)], rows[("dense", *suffix)]
            assert a["state_sha256"] == b["state_sha256"], "same-input observation divergence"
            if condition != "train":
                assert a["extra"]["pre_probe_sha256"] == b["extra"]["pre_probe_sha256"]
        progress(study, f"{seed}/{kind}/{order}")


def loads(study, namespace="load"):
    for seed, order, mode, rep in itertools.product(SEEDS, ("AB", "BA"), ("discard", "dummy"), (0, 1)):
        parent = load_case(study, f"replication-v2/{seed}/periodic/{order}/minimal/train")
        row = probe(study, parent, "periodic", order, mode, 1, "X", f"{namespace}/{seed}/{order}/{mode}/{rep}")
        ref = read_json(WORK / f"cases/replication-v2/{seed}/periodic/{order}/minimal/wait1/cueX/result.json")
        assert row["state_sha256"] == ref["state_sha256"], "same-input load divergence"
        progress(study, row["key"])


def serial_check(study):
    for order, mode in itertools.product(("AB", "BA"), ("minimal", "dense")):
        parent = train(study, 100124, "random", order, mode, "replication-serial-check")
        original = load_case(study, parent["key"].replace("replication-serial-check", "replication-v2"))
        assert parent["state_sha256"] == original["state_sha256"]
        for delay, cue in itertools.product((1, 30), ("none", "X")):
            row = probe(study, parent, "random", order, mode, delay, cue)
            reference = load_case(study, row["key"].replace("replication-serial-check", "replication-v2"))
            assert row["state_sha256"] == reference["state_sha256"]
        progress(study, parent["key"])
    loads(study, "load-serial-check")


def live(study):
    parent = load_case(study, "replication-v2/100121/periodic/AB/minimal/train")
    order = read_json(WORK / "materials.json")["live_order"]
    cfg = {"enabled": True, "intensity": 0.2, "sample_interval_ms": 500}
    for block, modes in enumerate(order):
        for mode in modes:
            key = f"live-kernel-meter/{block}/{mode}"
            row = saved(study, key)
            if not row:
                runtime = {
                    "clock": "realtime",
                    **{root: cfg for root in ("host_telemetry", "process_telemetry", "runtime_telemetry")},
                }
                c = fresh(study, key, 100121, parent=parent, observe=mode == "dense", runtime=runtime)
                obs = Observation(c, mode)
                if mode == "dense":
                    c.session.begin_observation("E23-live")
                background(c, "periodic", 13000000)
                c.send([ids(c.seed)["X"]], 0.5, at=8000000, source="manual-research-probe")
                tape = [
                    {"queued_at_us": c.engine.time_us, "stimulus": dict(x["stimulus"])}
                    for x in c.inputs.changes["frames"]
                ]
                telemetry = RuntimeTelemetry(c.spec, c.id)
                wall0 = time.monotonic()
                for target in range(7020000, 13000001, 20000):
                    due = wall0 + (target - 7000000) / 1e6
                    remaining = due - time.monotonic()
                    if remaining > 0:
                        time.sleep(remaining)
                    # Match the production meter boundary: only advancement and
                    # input-event bookkeeping, before the readout callback;
                    # thread CPU is distinct from total process CPU.
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
                            time.monotonic() - t0,
                            time.thread_time() - p0,
                            max(0, t0 - (wall0 + (boundary - 7000000) / 1e6)),
                        )
                        c.session.host.observe(c.engine)
                        if c.engine.time_us >= target or c.engine.life == "dead":
                            break
                    previous = len(c.inputs.changes["frames"])
                    telemetry.poll(c.inputs, c.events.append, source_enabled=True)
                    tape.extend(
                        {"queued_at_us": c.engine.time_us, "stimulus": dict(x["stimulus"])}
                        for x in c.inputs.changes["frames"][previous:]
                    )
                    c.sample()
                    if c.engine.life == "dead":
                        break
                new_json(c.folder / "actual-tape.json", tape)
                row = finish(
                    c,
                    obs,
                    {
                        "stage": "live",
                        "block": block,
                        "meter_scope": "thread CPU and advance_observed, readout excluded",
                        "telemetry": telemetry.capture(),
                        "realtime_elapsed": time.monotonic() - wall0,
                        "tape_sha256": hashlib.sha256(encoded(tape)).hexdigest(),
                    },
                )
            replaykey = key + "/replay"
            replay = saved(study, replaykey)
            if not replay:
                c = fresh(study, replaykey, 100121, parent=parent)
                tape = read_json(WORK / "cases" / key / "actual-tape.json")

                def enqueue_due(tape=tape, c=c):
                    for frame in tape:
                        if frame["queued_at_us"] == c.engine.time_us:
                            c.send_stimulus(Stimulus.from_dict(frame["stimulus"]), source="frozen-live-input")

                enqueue_due()
                for target in range(7020000, int(row["time_us"]) + 1, 20000):
                    c.session.advance_to(target, guard=c.guard)
                    enqueue_due()
                    c.sample()
                replay = c.finish({"stage": "live_replay", "original_id": row["id"], "original": key})
            assert replay["state_sha256"] == row["state_sha256"], "live tape replay divergence"
            progress(study, replaykey)


def later(study):
    strengths = read_json(WORK / "materials.json")["later_choice_cues"]
    for i, dose in enumerate(strengths):
        key = f"later/{i:03d}"
        if saved(study, key):
            continue
        order = "AB" if i % 2 == 0 else "BA"
        parent = load_case(study, f"replication-v2/100121/periodic/{order}/minimal/train")
        c = fresh(study, key, 100121, parent=parent)  # common early recording, no reader-specific trigger changes
        wait(c, "periodic", 8000000)
        obs = Observation(c, "dense")
        c.send([ids(c.seed)["X"]], dose, source="registered-later-choice-cue")
        wait(c, "periodic", 13000000)
        image = checkpoint(c, "early-state")
        write_gzip(c.folder / "early-trajectory.json.gz", obs.points)
        early = {
            "trial": i,
            "order": order,
            "dose": dose,
            "targets": targets(obs.points, c.seed),
            "state_sha256": image.digest,
            "trajectory_sha256": hashlib.sha256((c.folder / "early-trajectory.json.gz").read_bytes()).hexdigest(),
        }
        raw = encoded(early)
        with (c.folder / "early-commitment.json").open("xb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        committed_ns = time.perf_counter_ns()
        byte = os.urandom(1)[0]
        choice = byte & 1
        new_json(
            c.folder / "later-choice.json",
            {
                "byte": byte,
                "choice": choice,
                "early_sha256": hashlib.sha256(raw).hexdigest(),
                "commit_ns": committed_ns,
                "choice_ns": time.perf_counter_ns(),
                "wall_time_ns": time.time_ns(),
            },
        )
        obs.points.clear()
        obs.mode = "dense" if choice else "minimal"
        wait(c, "periodic", 14000000)
        finish(
            c,
            obs,
            {"stage": "later_choice", "trial": i, "order": order, "dose": dose, "early": early, "choice": choice},
        )
        if i % 16 == 15:
            progress(study, key)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=("prepare", "replication", "loads", "serial_check", "live", "later"))
    args = p.parse_args()
    lock = worker_lock(WORK)
    study = Study(settings(), prepare=args.stage == "prepare")
    try:
        if args.stage == "prepare":
            prepare_sources(study)
            new_json(WORK / "usage.json", {"used_percent": 92})
            print(study.project, flush=True)
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
