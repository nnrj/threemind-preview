"""Seal each segment once, keeping its full inputs and resumable state together."""

import gzip
import hashlib
import io
import json
import os
import shutil
import time
from contextlib import ExitStack
from zipfile import ZipFile, ZIP_STORED

from paths import CONTROL, HORIZON, KERNEL, NAME, SECOND, exclusive_json, pool, sha
from apparatus import StateImage
from execution import checked_metrics, encoded, snapshot
from habitat import ContactLitter63, make_world
from lab.tools.ocean_evolution_cli import RecordWriter
from threemind_lab.storage_files import atomic_json


def state_bytes(context):
    """Use the same sorted string keys for in-memory individual IDs and their JSON copies."""
    return encoded(json.loads(encoded(context)))


def restore(source):
    with ZipFile(source) as z:
        spec = json.loads(z.read("world.json"))
        if spec["kind"] != "ContactLitter63":
            raise ValueError("unexpected experimental world")
        images = {int(n[6:-5]): StateImage(z.read(n)) for n in z.namelist() if n.startswith("cores/")}
    w = ContactLitter63(spec["protocol"], state=spec["context"], images=images)
    if state_bytes(w.capture()) != encoded(spec["context"]) or set(w.engines) != set(images):
        raise ValueError("incomplete restored world")
    for individual, engine in w.engines.items():
        if engine.dynamics != KERNEL or engine.capture_state().payload != images[individual].payload:
            raise ValueError(f"restored Core differs for individual {individual}")
    return w


def restore_end(path):
    with ZipFile(path) as z:
        return restore(io.BytesIO(z.read("end.zip")))


def world_fingerprint(world):
    state = json.loads(encoded(world.capture()))
    current = state
    while "bodies" not in current:
        if "research" in current:
            current["research"].pop("supply_seconds", None)
        current = next(
            current[k] for k in ("carrion", "material", "enclosure", "group", "community", "world") if k in current
        )
    current["protocol"].pop("nutrient_interval_us")
    current.pop("next_food_us")
    return hashlib.sha256(encoded(state)).hexdigest()


def remove_spool(spool, archive):
    if spool.resolve().parent != archive.resolve().parent or spool.name != archive.stem + ".staging":
        raise ValueError("unexpected staging directory")
    with ZipFile(archive) as z:
        members = json.loads(z.read("manifest.json"))
        for name, expected in members.items():
            file = (spool / name).resolve()
            if not file.is_relative_to(spool.resolve()):
                raise ValueError(name)
            if file.exists():
                if sha(file) != expected:
                    raise ValueError("staging differs from verified archive")
                file.unlink()
    if (spool / "inputs").exists():
        (spool / "inputs").rmdir()
    spool.rmdir()


def seal(spool, archive):
    pending = archive.with_suffix(".zipping")
    members = {p.relative_to(spool).as_posix(): sha(p) for p in sorted(spool.rglob("*")) if p.is_file()}
    with ZipFile(pending, "x", ZIP_STORED, allowZip64=True) as z:
        for name in members:
            z.write(spool / name, name)
        z.writestr("manifest.json", encoded(members))
    with ZipFile(pending) as z:
        for name, expected in members.items():
            with z.open(name) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError("segment readback " + name)
    pending.rename(archive)
    remove_spool(spool, archive)


def motion_row(w, row):
    items = []
    for item in row["inputs"]:
        i = item["individual"]
        b = w.bodies[i]
        if not b.physical:
            continue
        raw = item["raw"]
        vx, vy = raw[5] * 0.03, raw[6] * 0.03
        sin, cos = raw[8], raw[9]
        items.append(
            [i, *b.position, cos * vx - sin * vy, sin * vx + cos * vy, b.angle, raw[7], item["action"][2], raw[23]]
        )
    return [row["time_us"], items]


def guard(root, extra=0):
    actual = pool().guard(NAME, "worlds", extra_bytes=extra, check_directory=False)
    if (actual / "evidence").resolve() != root.resolve() or shutil.disk_usage(root).free < 5 * 1024**3 + extra:
        raise RuntimeError("P1 evidence volume or free-space floor")
    if (root / "STOP").exists() or (actual / "STOP").exists() or (CONTROL / "STOP").exists():
        raise RuntimeError("operator STOP")


def segment(w, run, root, ordinal, horizon):
    pool().guard(NAME, "worlds", extra_bytes=192 * 1024**2)
    archive = run / f"seg-{ordinal:04d}.zip"
    spool = archive.with_suffix(".staging")
    spool.mkdir()
    writer = RecordWriter(spool / "inputs", chunk_steps=100)
    start = w.time_us
    start_hash = hashlib.sha256(state_bytes(w.capture())).hexdigest()
    wall = time.monotonic()
    last = wall - 31
    pause = None
    with ExitStack() as stack:
        events = stack.enter_context(gzip.open(spool / "events.jsonl.gz", "wb", compresslevel=2))
        motion = stack.enter_context(gzip.open(spool / "motion.jsonl.gz", "wb", compresslevel=2))

        def record(row):
            writer.record(row)
            for e in row["events"]:
                events.write(encoded(e) + b"\n")
            if row["time_us"] % 200_000 == 0:
                motion.write(encoded(motion_row(w, row)) + b"\n")

        while w.time_us < horizon and any(b.physical for b in w.bodies.values()):
            if time.monotonic() - last >= 30:
                try:
                    guard(root, 128 * 1024**2)
                except (OSError, ValueError, RuntimeError) as error:
                    pause = str(error)
                    break
                atomic_json(
                    root / "progress.json",
                    dict(
                        case=run.name,
                        time_us=w.time_us,
                        pid=os.getpid(),
                        alive=sum(b.physical for b in w.bodies.values()),
                        predations=int(w.totals["predations"]),
                        births=int(w.totals["births"]),
                        generation=max(b.generation for b in w.bodies.values()),
                        epoch=time.time(),
                    ),
                )
                last = time.monotonic()
            w.step(record)
        writer.flush()
    m = checked_metrics(w)
    snapshot(w, spool / "end.zip")
    meta = dict(
        start_us=start,
        end_us=w.time_us,
        start_hash=start_hash,
        end_hash=hashlib.sha256(state_bytes(w.capture())).hexdigest(),
        energy_balance_error=m["energy_balance_error"],
        wall_s=time.monotonic() - wall,
        pause=pause,
    )
    exclusive_json(spool / "segment.json", meta)
    seal(spool, archive)
    if pause:
        raise RuntimeError(pause)


def run_case(root, block, arm, interval):
    run = root / "cases" / f"world-{block}-{arm}"
    run.mkdir(parents=True, exist_ok=True)
    if (run / "result.json").exists():
        return
    guard(root, 128 * 1024**2)
    initial = run / "initial.zip"
    if not initial.exists():
        w = make_world(block, interval)
        exclusive_json(run.parent / f"pair-{block}.json", dict(initial_state_sha256=world_fingerprint(w)))
        snapshot(w, initial)
    previous = sorted(run.glob("seg-*.zip"))
    for unfinished in run.glob("seg-*.staging"):
        archive = unfinished.with_suffix(".zip")
        if not archive.exists():
            raise RuntimeError(f"interrupted segment kept for inspection: {unfinished}")
        remove_spool(unfinished, archive)
    w = restore_end(previous[-1]) if previous else restore(initial)
    ordinal = len(previous)
    while w.time_us < HORIZON * SECOND and any(b.physical for b in w.bodies.values()):
        next_boundary = min((w.time_us // (60 * SECOND) + 1) * 60 * SECOND, HORIZON * SECOND)
        segment(w, run, root, ordinal, next_boundary)
        ordinal += 1
    saved = restore_end(run / f"seg-{ordinal - 1:04d}.zip") if ordinal else restore(initial)
    if state_bytes(saved.capture()) != state_bytes(w.capture()):
        raise ValueError("final complete state")
    m = checked_metrics(w)
    exclusive_json(
        run / "result.json",
        dict(
            rule=w.research["environment_rules"],
            kernel=KERNEL,
            case=run.name,
            time_us=w.time_us,
            horizon_s=HORIZON,
            extinct=not any(b.physical for b in w.bodies.values()),
            energy_balance_error=m["energy_balance_error"],
            totals=m["totals"],
            members=m["members"],
        ),
    )
