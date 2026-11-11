"""E23 source-preserving registration and explicit background schedules."""

from __future__ import annotations

import gzip
import hashlib
import json
import random
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.service_study import GIB, Case, StudyConfig, encoded, load_case, new_json, read_json, write_gzip
from lab.tools.service_study import Study as BaseStudy
from threemind_runtime.adapters import channel_id

__all__ = ["encoded", "write_gzip"]

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/observation-background-20261001"
OLD = ROOT / ".work/recovery-reference-20261001"
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

    def prepare(self):
        if not (self.work / "platform.json").exists():
            return super().prepare()
        # Resume only a registration interrupted before any simulation, without
        # replacing its project, timestamps, design or source identity.
        if (self.work / "cases").exists() or (self.work / "sources.json").exists():
            raise RuntimeError("registration already completed")
        self.meta = read_json(self.work / "platform.json")
        assert self.meta["implementation"] == self.implementation
        assert self.meta["design_sha256"] == hashlib.sha256((HERE / "design.zh.md").read_bytes()).hexdigest()
        self.project = self.meta["project_id"]
        for lang in ("zh", "en"):
            source = HERE / f"design.{lang}.md"
            self.note(f"design:{lang}", f"执行登记 / Study registration {lang}", source.read_text(encoding="utf-8"))
            shutil.copy2(source, self.work / f"design-frozen.{lang}.md")
        for name in self.implementation["source_files"]:
            destination = self.work / "frozen-sources" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
        new_json(
            self.work / "registration-resume.json",
            {
                "reason": "Relative Markdown link rejected by notebook URL validation; converted to the existing local docs route before simulation.",
                "no_cases_executed": True,
            },
        )


def settings():
    return StudyConfig(
        "observation-background/1",
        "E23 背景刺激、观察影响与延后选择",
        HERE,
        WORK,
        92,
        instance_limit=512,
        wall_seconds=7200,
        storage_soft=3 * GIB,
        storage_hard=4 * GIB,
        usage_soft_delta=3,
        usage_hard_delta=5,
    )


def ids(seed):
    return {s: channel_id(seed, "priority-memory/1", i) for i, s in enumerate("ABCDEFGHK")} | {
        s: channel_id(seed, "priority-sequence/1", i) for i, s in enumerate("XYZ")
    }


def old_folder(seed, order, suffix="train"):
    return OLD / f"cases/jitter/{seed}/fixed/{order}/{suffix}"


def prepare_sources(study):
    paths = []
    historic = []
    project = read_json(OLD / "platform.json")["project_id"]
    for seed in SEEDS:
        for order in ("AB", "BA"):
            for suffix in ("train", "wait30/cueX", "wait30/cuenone"):
                folder = old_folder(seed, order, suffix)
                for name in ("result.json", "parent-state.json.gz", "inputs.json.gz"):
                    paths.append(folder / name)
                row = read_json(folder / "result.json")
                spec = study.db.get_run(project, row["id"])["spec"]
                assert all(
                    not spec[root]["enabled"] for root in ("host_telemetry", "process_telemetry", "runtime_telemetry")
                )
                bundle = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
                assert not any("telemetry" in x["adapter_id"] for x in bundle["envelopes"])
                historic.append(
                    {
                        "id": row["id"],
                        "project": project,
                        "live_telemetry": False,
                        "sources": sorted({e["source"] for e in bundle["envelopes"]}),
                    }
                )
    paths += list((ROOT / "lab/explorations/2026-10-01-recovery-reference").glob("*.py"))
    manifest = {}
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        manifest[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        target = WORK / "selected-sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    new_json(WORK / "sources.json", manifest)
    new_json(WORK / "historical-telemetry-audit.json", historic)
    materials = {}
    for seed in SEEDS:
        rng = random.Random(f"E23/identity-background/{seed}")
        channels = rng.sample(range(2**32), 100)
        assert not set(channels) & set(ids(seed).values())
        materials[str(seed)] = channels
    rng = random.Random(23001)
    new_json(
        WORK / "materials.json",
        {
            "random_channels": materials,
            "later_choice_cues": [rng.uniform(0.3, 0.7) for _ in range(128)],
            "live_order": [rng.sample(["minimal", "dense", "dummy"], 3) for _ in range(4)],
        },
    )


def saved(study, key):
    if (WORK / "cases" / key / "result.json").exists():
        row = load_case(study, key)
        if row["extra"].get("failure"):
            raise RuntimeError("preserved failure: " + key)
        return row


def fresh(study, key, seed, **kwargs):
    study.guard(force=True)
    return Case(study, key, KERNEL, seed, **kwargs)


def checkpoint(c, name):
    image = c.engine.capture_state()
    with gzip.open(c.folder / (name + ".json.gz"), "xb") as out:
        out.write(image.payload)
    return image


def background(c, kind, until):
    at = getattr(c, "next_background", ((c.engine.time_us + 499999) // 500000) * 500000)
    channels = read_json(WORK / "materials.json")["random_channels"][str(c.seed)] if kind == "random" else None
    while at < until:
        if kind != "none":
            channel = ids(c.seed)["K"] if kind == "periodic" else channels[at // 500000]
            c.send(
                [channel], 0.2, at=at, source="maintenance-control" if kind == "periodic" else "random-identity-control"
            )
        at += 500000
    c.next_background = at


def wait(c, kind, until):
    if c.engine.life == "dead":
        return
    background(c, kind, until)
    c.advance(until)
    if c.engine.life != "dead":
        c.session.advance_to(until, guard=c.guard)


def targets(points, seed):
    import itertools
    import math

    result = {}
    for symbol in ("A", "B"):
        channel = ids(seed)[symbol]
        pairs = sorted(
            {
                int(p["time_us"]): next((n["activation"] for n in p["nodes"] if n["channel"] == channel), 0.0)
                for p in points
            }.items()
        )
        result[symbol] = {
            "integral": math.fsum((a[1] + b[1]) * (b[0] - a[0]) / 2e6 for a, b in itertools.pairwise(pairs)),
            "peak": max((x[1] for x in pairs), default=0.0),
            "terminal": pairs[-1][1] if pairs else None,
        }
    return result


def progress(study, key):
    print(
        json.dumps(
            {"finished": key, "cases": study.completed_count, "wall_seconds": round(study.completed_wall, 2)},
            ensure_ascii=False,
        ),
        flush=True,
    )
