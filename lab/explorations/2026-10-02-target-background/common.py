"""E24 frozen identity, matched background material and existing-service persistence."""

import gzip
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.service_study import (
    GIB,
    Case,
    Study,
    StudyConfig,
    encoded,
    load_case,
    new_json,
    read_json,
    write_gzip,
)
from threemind_core import StateImage, Stimulus
from threemind_runtime.adapters import channel_id
from threemind_runtime.observation_tools import analyze_targets

__all__ = ["Case", "Stimulus", "Study", "encoded", "load_case", "new_json", "read_json", "write_gzip"]
HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/target-background-20261002"
OLD = ROOT / ".work/observation-background-20261001"
SEEDS = (100121, 100122, 100123, 100124)
KINDS = ("telemetry", "random", "none")
KERNEL = "threemind.continuous-memory/2"


def settings():
    return StudyConfig(
        "target-background/1",
        "E24 目标响应与遥测背景对照",
        HERE,
        WORK,
        93,
        instance_limit=160,
        wall_seconds=3600,
        storage_soft=int(1.5 * GIB),
        storage_hard=2 * GIB,
        usage_soft_delta=3,
        usage_hard_delta=5,
    )


def ids(seed):
    return {s: channel_id(seed, "priority-memory/1", i) for i, s in enumerate("ABCDEFGHK")} | {
        s: channel_id(seed, "priority-sequence/1", i) for i, s in enumerate("XYZ")
    }


def historical(seed, order):
    folder = OLD / f"cases/replication-v2/{seed}/periodic/{order}/minimal/train"
    row = read_json(folder / "result.json")
    image = StateImage.from_dict(json.loads(gzip.decompress((folder / "parent-state.json.gz").read_bytes())))
    assert image.digest == row["state_sha256"]
    return row | {"image": image, "external_project": True}


def saved(study, key):
    if (study.work / "cases" / key / "result.json").exists():
        row = load_case(study, key)
        if row["extra"].get("failure"):
            raise RuntimeError("preserved failed case: " + key)
        return row


def fresh(study, key, seed, **kwargs):
    study.guard(force=True)
    return Case(study, key, KERNEL, seed, **kwargs)


def pulse_background(c, kind, until):
    if kind == "none":
        return
    if not hasattr(c, "background_tape"):
        c.background_tape = read_json(WORK / f"materials/{c.seed}-{kind}.json")
        c.background_index = 0
        while (
            c.background_index < len(c.background_tape)
            and int(c.background_tape[c.background_index]["stimulus"]["time_us"]) <= c.engine.time_us
        ):
            c.background_index += 1
    while c.background_index < len(c.background_tape):
        frame = c.background_tape[c.background_index]
        stim = Stimulus.from_dict(frame["stimulus"])
        if stim.time_us > until:
            break
        # Keep the public anonymous carrier replayable. Origin and the research
        # randomization remain in the frozen material, joined by scope/time.
        c.send_stimulus(stim, source=kind + "-background:" + frame["scope"])
        c.background_index += 1


def wait(c, kind, until):
    if c.engine.life == "dead":
        return
    pulse_background(c, kind, until)
    c.advance(until)
    if c.engine.life != "dead":
        c.session.advance_to(until, guard=c.guard)


def finish(c, extra):
    row = c.finish(extra)
    channels = {n["channel"]: n["id"] for n in row["image"].to_dict()["nodes"]}
    targets = [channels[ids(c.seed)[s]] for s in "AB" if ids(c.seed)[s] in channels]
    reports = []
    for event in c.events:
        r = event.get("payload", {})
        if r.get("analysis_schema") and targets:
            reports.append(analyze_targets(r, node_ids=targets))
    write_gzip(c.folder / "target-analysis.json.gz", reports)
    print(
        json.dumps({"finished": c.key, "cases": c.study.completed_count, "wall_s": round(c.study.completed_wall, 2)}),
        flush=True,
    )
    return row


def make_materials(seed):
    folder = WORK / f"cases/acquisition/{seed}"
    inputs = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
    envelopes = {e["id"]: e for e in inputs["envelopes"]}
    frames = [
        {
            "scope": envelopes[f["envelope_id"]]["source"].removesuffix("-telemetry"),
            "stimulus": f["stimulus"],
            "origin_envelope": f["envelope_id"],
        }
        for f in inputs["frames"]
        if envelopes[f["envelope_id"]]["adapter_id"].endswith("-telemetry")
    ]
    frames.sort(key=lambda f: (int(f["stimulus"]["time_us"]), f["scope"]))
    pools = {
        s: sorted({int(c) for f in frames if f["scope"] == s for c, _ in f["stimulus"]["channels"]})
        for s in ("host", "process", "runtime")
    }
    assert not set(ids(seed).values()) & {c for pool in pools.values() for c in pool}
    rng = random.Random(f"E24-matched-assignment/{seed}")
    randomized = []
    for frame in frames:
        stim = frame["stimulus"]
        values = [float(v) for _, v in stim["channels"]]
        channels = rng.sample(pools[frame["scope"]], len(values))
        randomized.append(frame | {"stimulus": stim | {"channels": sorted(zip(channels, values))}})
    new_json(WORK / f"materials/{seed}-telemetry.json", frames)
    new_json(WORK / f"materials/{seed}-random.json", randomized)
    new_json(WORK / f"materials/{seed}-pools.json", pools)


def freeze_sources():
    paths = []
    for seed in SEEDS:
        for order in ("AB", "BA"):
            root = OLD / f"cases/replication-v2/{seed}/periodic/{order}/minimal/train"
            paths += [root / name for name in ("result.json", "parent-state.json.gz")]
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    new_json(WORK / "historical-sources.json", manifest)
