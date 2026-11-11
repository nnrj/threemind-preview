"""New-project-only calibration and validation, with immutable per-case evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import time
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

import psutil
from psycopg.types.json import Jsonb

from threemind_core import Config
from threemind_lab import calibration, notebooks
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.inputs import envelope_record
from threemind_lab.protocols import RunSpec
from threemind_lab.provenance import capture_implementation
from threemind_runtime import create_engine
from threemind_runtime.calibration import CalibrationProtocol
from threemind_runtime.sensory import TEXT_VERSION, TextSensor, TextSensorConfig

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / ".work" / "calibrated-generalization-20260909"
META = HERE / "platform.json"
OLD = "900840b0-d00d-450c-9669-72600cea7c40"
WORKER = "calibrated-generalization-owned-jobs"
VOCAB = [
    ("甲", "松子", "乙", "铃铛"),
    ("丙", "陶杯", "丁", "柳叶"),
    ("戊", "星河", "己", "木舟"),
    ("庚", "雨滴", "辛", "沙丘"),
    ("壬", "海螺", "癸", "铜镜"),
]
CAL = [("岚", "竹笛", "汀", "橡果"), ("岑", "绒球", "洵", "纸鹤")]
FAMILIES = [
    "青岳 白川 赤岩 玄舟 苍木 紫原",
    "冬岚 春汀 夏岑 秋洵 雪澄 露屿",
    "北辰 南烛 东翎 西漠 远帆 近溪",
    "晨石 午桐 暮竹 夜泉 晓榆 夕禾",
]


def encoded(v):
    return json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False, default=str).encode()


def heads(db, project):
    with db.tx(project) as c:
        rows = c.execute(
            "SELECT id,revision,state_hash,status FROM runs WHERE project_id=%s ORDER BY id", (project,)
        ).fetchall()
    return {"count": len(rows), "sha256": hashlib.sha256(encoded(rows)).hexdigest()}


def init():
    if META.exists():
        raise RuntimeError("new project already initialized; never overwrite")
    db = Database(Settings.from_env().database_url)
    try:
        project = db.create_project({"id": LOCAL_USER}, "校准验证：扩大词表与未见家系 · 2026-09-09")
        notebook = notebooks.ensure_default(db, project["id"], LOCAL_USER)
        note = uuid4()
        notebooks.save_note(
            db,
            project["id"],
            LOCAL_USER,
            note,
            {
                "operation_id": str(uuid4()),
                "expected_revision": 0,
                "title": "预先固定方案：校准、配对泛化与关系组合",
                "kind": "note",
                "collection_id": str(notebook["id"]),
                "body": {"format": "markdown", "text": (HERE / "protocol.md").read_text(encoding="utf-8")},
            },
        )
        with db.tx() as c:
            physical = c.execute("SELECT pg_database_size(current_database()) n").fetchone()["n"]
        meta = {
            "project_id": str(project["id"]),
            "notebook_id": str(notebook["id"]),
            "protocol_note_id": str(note),
            "protocol_sha256": hashlib.sha256((HERE / "protocol.md").read_bytes()).hexdigest(),
            "old_heads_before": heads(db, OLD),
            "database_bytes_before": physical,
            "quota_baseline_percent": 49,
        }
        META.write_bytes(encoded(meta) + b"\n")
        print(encoded(meta).decode())
    finally:
        db.close()


class Study:
    def __init__(self, phase, attempt=1):
        WORK.mkdir(parents=True, exist_ok=True)
        self.phase, self.started, self.peak = phase, time.monotonic(), 0
        self.meta = json.loads(META.read_bytes())
        self.project = self.meta["project_id"]
        assert hashlib.sha256((HERE / "protocol.md").read_bytes()).hexdigest() == self.meta["protocol_sha256"]
        self.db = Database(Settings.from_env().database_url)
        self.impl = capture_implementation("native")
        self.impl["harness_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.cap = {
            "executor": str(Path(__file__).relative_to(ROOT)),
            "scope": self.project,
            "features": {"worker.core": {"state": "available"}, "worker.probe_calibration_v1": {"state": "available"}},
        }
        self.db.announce_worker(WORKER, self.cap)
        self.path = WORK / f"{phase}-attempt{attempt}-results.json"
        if self.path.exists():
            raise RuntimeError("phase exists; evidence cannot be overwritten")
        self.previous = sum(json.loads(p.read_bytes())["elapsed_s"] for p in WORK.glob("*-results.json"))
        self.rows = []
        self.estimated = 0
        self.refresh_budget()
        self.dose = (
            json.loads((HERE / "calibration-decision.json").read_bytes())["selected_dose"]
            if phase != "calibration"
            else None
        )

    def refresh_budget(self):
        with self.db.tx(self.project) as c:
            counts = c.execute(
                "SELECT coalesce(sum((metrics->>'nodes')::bigint+(metrics->>'edges')::bigint),0) n FROM runs WHERE project_id=%s",
                (self.project,),
            ).fetchone()
            payload = c.execute(
                "SELECT (SELECT coalesce(sum(byte_count),0) FROM checkpoints WHERE project_id=%s)+(SELECT coalesce(sum(bytes),0) FROM artifacts WHERE project_id=%s) n",
                (self.project, self.project),
            ).fetchone()
            physical = c.execute("SELECT pg_database_size(current_database()) n").fetchone()["n"]
        self.estimated = max(int(counts["n"]) * 320 + int(payload["n"]), physical - self.meta["database_bytes_before"])

    def guard(self, engine=None):
        self.peak = max(self.peak, psutil.Process().memory_info().rss)
        if self.peak > 2 * 1024**3 or psutil.virtual_memory().available < 3 * 1024**3:
            raise RuntimeError("memory limit")
        if min(shutil.disk_usage("D:/").free, shutil.disk_usage(WORK).free) < 15 * 1024**3:
            raise RuntimeError("disk reserve")
        if self.estimated + sum(p.stat().st_size for p in WORK.glob("*.json")) > 4 * 1024**3:
            raise RuntimeError("4 GiB storage budget")
        if time.monotonic() - self.started + self.previous > 900:
            raise RuntimeError("15 minute experiment limit")
        if engine and (engine.metrics()["nodes"] > 2000 or engine.metrics()["edges"] > 100000):
            raise RuntimeError("network limit")

    def claim(self, job_id):
        self.db.announce_worker(WORKER, self.cap)
        with self.db.tx(self.project) as c:
            job = c.execute(
                "UPDATE jobs SET status='leased',worker_id=%s,generation=generation+1,attempts=attempts+1,lease_until=clock_timestamp()+interval '5 minutes' WHERE id=%s AND project_id=%s AND status='pending' RETURNING *",
                (WORKER, job_id, self.project),
            ).fetchone()
            if not job:
                raise RuntimeError("owned job is not pending")
            c.execute(
                "INSERT INTO job_assignments(project_id,job_id,generation,worker_id,required_features,capabilities) VALUES(%s,%s,%s,%s,%s,%s)",
                (self.project, job_id, job["generation"], WORKER, job["required_features"], Jsonb(self.cap)),
            )
        return job

    def train(self, seed, mode, sentences, gap, tag, learn=True):
        self.guard()
        e = create_engine(Config(plasticity=learn))
        spec = RunSpec(
            environment="manual",
            clock="unbounded",
            duration_s=None,
            seed=seed,
            config=e.config.to_dict(),
            text_sensor=TextSensorConfig(encoding=mode),
            structural_readout={"enabled": False},
            temporal_readout={"enabled": False},
        )
        run = self.db.create_run(self.project, tag, spec.model_dump())
        inputs = RuntimeInputs(self.db, self.project, run["id"], e, spec, {"initialized": True, "start_us": "0"}, 0)
        sensor = TextSensor(seed, spec.text_sensor)
        for i, text in enumerate(sentences):
            if e.life == "dead":
                raise RuntimeError("training died; no resurrection")
            frames = [
                dict(f, stimulus=replace(f["stimulus"], time_us=i * gap + f["stimulus"].time_us))
                for f in sensor.frames(text)
            ]
            env = envelope_record(
                uuid4(),
                "text-sensor",
                "manual-cli-text",
                {"text": text, "intensity": 1},
                {"seed": seed, "adapter": asdict(spec.text_sensor), "transduction": sensor.describe(text)},
                len(frames),
                sum(len(f["stimulus"].channels) for f in frames),
                version=TEXT_VERSION,
            )
            inputs.changes["envelopes"].append(env)
            inputs.schedule(env, frames)
            e.advance_to((i + 1) * gap, inputs.observe, inputs_only=True)
            self.guard(e)
        image = e.capture_state()
        cp = self.db.save_checkpoint(
            self.project,
            run["id"],
            image,
            expected_revision=0,
            status="completed",
            observations=[e.metrics()],
            input_changes=inputs.take_changes(),
            context={
                "initialized": True,
                "protocol": spec.model_dump(),
                "start_us": "0",
                "end_us": str(e.time_us),
                "input_bus": inputs.bus.capture(),
                "input_bus_run_id": str(run["id"]),
                "implementation": self.impl,
                "source_enabled": True,
                "exploration": {"tag": tag, "sentences": sentences, "gap_us": gap},
            },
        )
        self.estimated += cp["byte_count"] + 320 * (e.metrics()["nodes"] + e.metrics()["edges"])
        return run, cp

    def probe(self, run, cp, protocol):
        self.guard()
        requested = calibration.request(
            self.db,
            self.project,
            run["id"],
            LOCAL_USER,
            operation_id=uuid4(),
            protocol=protocol.model_dump(),
            checkpoint_id=cp["id"],
        )
        job = self.claim(requested["job_id"])
        try:
            completion = calibration.execute(self.db, job, implementation=self.impl)
            self.db.finish(job, result=completion)
        except Exception as e:
            self.db.finish(job, error=str(e))
            raise
        result = calibration.result(self.db, self.project, requested["id"])
        with self.db.tx(self.project) as c:
            self.estimated += int(c.execute(
                "SELECT coalesce(sum(bytes),0) n FROM artifacts WHERE job_id=%s", (job["id"],)
            ).fetchone()["n"])
        compact = {
            k: result[k] for k in ("source_hash", "source_unchanged", "mapping", "protocol", "seed", "sensor_config")
        }
        compact["id"] = str(requested["id"])
        compact["run_id"] = str(run["id"])
        compact["checkpoint_id"] = str(cp["id"])
        compact["artifacts"] = completion
        compact["rows"] = [
            {
                k: r.get(k)
                for k in (
                    "cue",
                    "intensity",
                    "available",
                    "endpoint",
                    "net_endpoint",
                    "transport",
                    "delivered_signal_amount",
                    "life",
                )
            }
            | {"max_saturated_fraction": max(p["saturated_fraction"] for p in r["curve"])}
            for r in result["rows"]
        ]
        return compact

    def memory(self):
        phase = self.phase
        vocab, seeds = (CAL, range(41221, 41225)) if phase == "calibration" else (VOCAB, range(41301, 41313))
        cases = [
            ("anonymous-distributed", s, v, g, 12, a)
            for s in seeds
            for v in range(len(vocab))
            for g in ([800000] if phase == "calibration" else [400000, 800000, 1600000])
            for a in (["paired"] if phase == "calibration" else ["paired", "mixed", "swapped", "learning_off"])
        ]
        if phase == "memory":
            cases += [
                ("anonymous-distributed", s, v, g, 4, a)
                for s in list(seeds)[:4]
                for v in range(2)
                for g in [400000, 800000, 1600000]
                for a in ["paired", "mixed", "swapped"]
            ]
            cases += [
                ("literal-character", s, v, 800000, 12, a)
                for s in list(seeds)[:4]
                for v in range(2)
                for a in ["paired", "mixed", "swapped", "learning_off"]
            ]
        for mode, seed, v, gap, n, arm in cases:
            a, b, c, d = vocab[v]
            rng = random.Random(seed)
            sentences = []
            for cycle in range(n):
                swap = arm == "swapped" or arm == "mixed" and cycle % 2 == 1
                pair = [f"{a}是{d}", f"{c}是{b}"] if swap else [f"{a}是{b}", f"{c}是{d}"]
                rng.shuffle(pair)
                sentences += pair
            tag = f"{phase}/{mode}/{seed}/v{v}/g{gap}/n{n}/{arm}"
            run, cp = self.train(seed, mode, sentences, gap, tag, arm != "learning_off")
            data = self.probe(
                run,
                cp,
                CalibrationProtocol(
                    cues=[a, c], terms=[b, d], intensities=[1.0, 2.0, 4.0] if phase == "calibration" else [self.dose]
                ),
            )
            self.rows.append(
                {
                    "seed": seed,
                    "vocab": v,
                    "gap_us": gap,
                    "n": n,
                    "mode": mode,
                    "arm": arm,
                    "pairs": [[a, b], [c, d]],
                    "measurement": data,
                }
            )
            self.progress(len(cases))

    def relations(self):
        for seed in range(41401, 41413):
            for f, names in enumerate(FAMILIES):
                a, b, c, d, e, z = names.split()
                for arm in ["correct", "wrong_template", "reversed_chain"]:
                    rng = random.Random(seed)
                    examples = ["A是B的父亲", "B是C的父亲", "D是E的父亲", "E是F的父亲"] + (
                        ["D是C的爷爷", "A是F的爷爷"] if arm == "wrong_template" else ["A是C的爷爷", "D是F的爷爷"]
                    )
                    held = (
                        [f"{b}是{a}的父亲", f"{c}是{b}的父亲", f"{e}是{d}的父亲", f"{z}是{e}的父亲"]
                        if arm == "reversed_chain"
                        else [f"{a}是{b}的父亲", f"{b}是{c}的父亲", f"{d}是{e}的父亲", f"{e}是{z}的父亲"]
                    )
                    sentences = []
                    for source, count in [(examples, 8), (held, 4)]:
                        for _ in range(count):
                            cycle = source.copy()
                            rng.shuffle(cycle)
                            sentences += cycle
                    run, cp = self.train(
                        seed, "anonymous-distributed", sentences, 800000, f"relations/{seed}/f{f}/{arm}"
                    )
                    cues = [name + suffix for name in [c, z] for suffix in ["的爷爷", "的父亲", ""]]
                    data = self.probe(
                        run, cp, CalibrationProtocol(cues=cues, terms=[a, b, d, e], intensities=[self.dose])
                    )
                    self.rows.append(
                        {"seed": seed, "family": f, "names": [a, b, c, d, e, z], "arm": arm, "measurement": data}
                    )
                    self.progress(144)

    def progress(self, total):
        if len(self.rows) % 20 == 0 or self.phase == "calibration":
            self.refresh_budget()
            print(
                f"{self.phase}: {len(self.rows)}/{total}; elapsed {time.monotonic() - self.started:.1f}s; storage {self.estimated / 1024**2:.1f}MiB",
                flush=True,
            )

    def close(self, error=None):
        self.refresh_budget()
        result = {
            "phase": self.phase,
            "rows": self.rows,
            "elapsed_s": time.monotonic() - self.started,
            "peak_rss": self.peak,
            "estimated_total_bytes": self.estimated,
            "implementation": self.impl,
            "error": error,
            "old_heads_after": heads(self.db, OLD),
        }
        with self.path.open("xb") as f:
            f.write(encoded(result))
        if not error:
            self.meta.setdefault("completed_phases", {})[self.phase] = self.path.name
            META.write_bytes(encoded(self.meta)+b"\n")
        self.db.close()
        assert result["old_heads_after"] == self.meta["old_heads_before"], "old project heads changed"


def decide():
    path = WORK / json.loads(META.read_bytes())["completed_phases"]["calibration"]
    data = json.loads(path.read_bytes())
    summary = []
    for dose in [1, 2, 4]:
        checks = []
        for case in data["rows"]:
            m = case["measurement"]
            cover = all(v["scorable"] for v in m["mapping"]["coverage"].values())
            for r in m["rows"]:
                if r["cue"] and r["intensity"] == dose:
                    checks.append(
                        cover
                        and r["available"]
                        and r["transport"]["sent"] > 0
                        and r["delivered_signal_amount"] > 0
                        and r["max_saturated_fraction"] < 0.2
                    )
        summary.append(
            {"dose": dose, "eligible": sum(checks), "total": len(checks), "fraction": sum(checks) / len(checks)}
        )
    choices = [r["dose"] for r in summary if r["fraction"] >= 0.8]
    decision = {
        "rule": "lowest dose with >=80% physical observability; no target-hit criterion",
        "summary": summary,
        "selected_dose": choices[0] if choices else 4,
        "calibration_passed": bool(choices),
        "calibration_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    with (HERE / "calibration-decision.json").open("xb") as f:
        f.write(encoded(decision) + b"\n")
    print(encoded(decision).decode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["init", "calibration", "decide", "memory", "relations"])
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    if args.phase == "init":
        init()
    elif args.phase == "decide":
        decide()
    else:
        study = Study(args.phase, args.attempt)
        error = None
        try:
            study.relations() if args.phase == "relations" else study.memory()
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            raise
        finally:
            study.close(error)
