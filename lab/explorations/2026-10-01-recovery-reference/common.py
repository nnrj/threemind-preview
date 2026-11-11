"""Shared registration and recording for the bounded localization experiment."""

from __future__ import annotations

import gzip
import hashlib
import importlib
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.service_study import GIB, Case, StudyConfig, load_case, new_json, read_json, write_gzip
from lab.tools.service_study import Study as BaseStudy
from threemind_core import StateImage
from threemind_runtime.adapters import channel_id

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/recovery-reference-20261001"
OLD = ROOT / ".work/priority-memory-20261001"
KERNEL = "threemind.continuous-memory/2"
SEEDS = (100121, 100122, 100123, 100124)


def note_text(body):
    return re.sub(
        r"\[([^\]]+)\]\(([A-Za-z0-9_./-]+\.md)\)",
        lambda m: f"[{m[1]}](/docs?doc={quote((HERE / m[2]).resolve().relative_to(ROOT).as_posix(), safe='')})",
        body,
    )


class Study(BaseStudy):
    def note(self, key, title, text):
        return super().note(key, title, note_text(text))


def settings():
    return StudyConfig(
        "recovery-reference/1",
        "2026-10-01 感官恢复、维护时机与共同参照",
        HERE,
        WORK,
        88,
        instance_limit=2048,
        wall_seconds=14400,
        storage_soft=6 * GIB,
        storage_hard=8 * GIB,
        usage_soft_delta=3,
        usage_hard_delta=5,
    )


def ids(seed):
    base = {s: channel_id(seed, "priority-memory/1", i) for i, s in enumerate("ABCDEFGHK")}
    return base | {s: channel_id(seed, "priority-sequence/1", i) for i, s in enumerate("XYZ")}


def saved(study, key):
    path = study.work / "cases" / key / "result.json"
    if not path.exists():
        return None
    row = load_case(study, key)
    if row["extra"].get("failure"):
        raise RuntimeError("preserved failure requires separately registered retry: " + key)
    return row


def fresh(study, key, seed, **kwargs):
    study.guard(force=True)
    return Case(study, key, KERNEL, seed, **kwargs)


def wait(c, until):
    if until < c.engine.time_us:
        raise ValueError("time cannot reverse")
    at = getattr(c, "next_keep", ((c.engine.time_us + 499999) // 500000) * 500000)
    while at < until:
        c.send([ids(c.seed)["K"]], 0.2, at=at, source="maintenance-control")
        at += 500000
    c.next_keep = at
    c.advance(until)
    c.session.advance_to(until, guard=c.guard)
    if c.engine.time_us != until or c.engine.life == "dead":
        raise RuntimeError("registered maintenance failed")


def checkpoint(c, name):
    image = c.engine.capture_state()
    with gzip.open(c.folder / (name + ".json.gz"), "xb") as out:
        out.write(image.payload)
    return image


def attach_observer(c, name):
    points, original = [], c.session.host.observe

    def passive(engine, *args, **kwargs):
        result = original(engine, *args, **kwargs)
        state = engine.capture_state().to_dict()
        points.append({k: state[k] for k in ("time_us", "nodes", "edges", "operator_state", "transport")})
        return result

    c.session.host.observe = passive
    c.session.begin_observation(name)
    return points


def observe(c, meta, cue, *, channel=None):
    before = checkpoint(c, "pre-probe")
    points = attach_observer(c, "order-mechanism-probe")
    start = c.engine.time_us
    if cue:
        c.send([channel if channel is not None else ids(c.seed)["X"]], 0.5, source="manual-research-probe")
    wait(c, start + 5_000_000)
    write_gzip(c.folder / "trajectory.json.gz", points)
    return c.finish(
        meta
        | {
            "stage": "probe",
            "cue": cue,
            "probe_start_us": start,
            "pre_probe_sha256": before.digest,
            "targets": [ids(c.seed)["A"], ids(c.seed)["B"]],
        }
    )


def progress(study, key):
    print(
        json.dumps(
            {"finished": key, "cases": study.completed_count, "wall_seconds": round(study.completed_wall, 2)},
            ensure_ascii=False,
        ),
        flush=True,
    )


def sources(study):
    """Freeze only explicitly selected historic states/materials and reusable tools."""
    path = WORK / "sources.json"
    if path.exists():
        manifest = read_json(path)
        for name, sha in manifest.items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha:
                raise RuntimeError("registered source changed: " + name)
        return manifest
    selected = [
        ROOT / "lab/tools/state_exchange_cut.py",
        ROOT / "lab/tools/state_exchange.py",
        ROOT / "lab/tools/study_input_audit.py",
    ]
    previous = ROOT / ".work/order-mechanisms-20261001"
    for seed in (930101, 930102, 930103, 930104):
        for mode in ("full", "no_imu"):
            for learn in ("01", "11"):
                base = previous / f"cases/sensory/{seed}/{mode}/learn{learn}/test11"
                selected.append(base / "sign1/physical1/pre-probe.json.gz")
                for sign in (1, -1):
                    for physical in (0, 1):
                        selected.append(base / f"sign{sign}/physical{physical}/result.json")
    legacy_work = ROOT / ".work/memory-transfer-20260930"
    selected += list((ROOT / "lab/explorations/2026-09-30-memory-transfer").glob("*.py"))
    selected += list((ROOT / "lab/explorations/2026-10-01-order-mechanisms").glob("*.py"))
    selected.append(legacy_work / "calibration.json")
    for seed in (930101, 930102, 930103, 930104):
        for sign in (1, -1):
            selected.append(legacy_work / "materials" / f"pendulum-{seed}-{sign}-original.json")
    for seed in SEEDS:
        for tau in (0, 1):
            for offset in (0, 40000, 60000):
                for order in ("AB", "BA"):
                    base = previous / f"cases/phase/{seed}/f{tau}/g50000/p{offset}/{order}"
                    for tail in ("train", "wait30/cueX", "wait30/cuenone"):
                        selected.append(base / tail / "result.json")
    manifest = {}
    for source in selected:
        name = source.relative_to(ROOT).as_posix()
        manifest[name] = hashlib.sha256(source.read_bytes()).hexdigest()
        target = WORK / "selected-sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    new_json(path, manifest)
    return manifest


def old_sensory(study, seed, mode, learn):
    folder = ROOT / f".work/order-mechanisms-20261001/cases/sensory/{seed}/{mode}/learn{learn}/test11/sign1/physical1"
    row = read_json(folder / "result.json")
    image = StateImage(gzip.decompress((folder / "pre-probe.json.gz").read_bytes()))
    assert image.digest == row["extra"]["pre_probe_sha256"]
    project = read_json(ROOT / ".work/order-mechanisms-20261001/platform.json")["project_id"]
    _, end = study.db.load_checkpoint(project, row["id"])
    assert end.digest == row["state_sha256"]
    return row | {"image": image, "external_project": True}


def legacy_module():
    names = ("common", "materials", "experiment")
    prior = {n: sys.modules.pop(n, None) for n in names}
    original = list(sys.path)
    sys.path.insert(0, str(ROOT / "lab/explorations/2026-09-30-memory-transfer"))
    try:
        return importlib.import_module("experiment")
    finally:
        sys.path[:] = original
        for n in names:
            sys.modules.pop(n, None)
            if prior[n] is not None:
                sys.modules[n] = prior[n]


def run_cli(fn, args):
    study = Study(settings())
    try:
        sources(study)
        study.allow_extension()
        fn(study, args)
    except Exception as exc:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"failure": repr(exc), "budget_stop": True})
        raise
    finally:
        study.db.close()
