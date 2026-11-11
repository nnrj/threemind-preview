"""Bounded, reproducible research harness. Never changes Core or existing runs.

Run with the project's Python: run.py --phase pilot|memory|relations.
All stimuli use the existing TextSensor and InputBus; actual model states and
input audit are committed to the selected, explicitly owned Lab project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import time
import zipfile
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

import psutil

from threemind_core import Config
from threemind_lab.config import Settings
from threemind_lab.database import Database
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.inputs import envelope_record
from threemind_lab.protocols import RunSpec
from threemind_lab.provenance import capture_implementation
from threemind_runtime import create_engine
from threemind_runtime.inheritance import birth
from threemind_runtime.sensory import TEXT_VERSION, TextSensor, TextSensorConfig

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2] / ".work" / "memory-relations-20260909"
WORK.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(41203, 41211))
DT = 20_000
WINDOW = list(range(200_000, 1_000_001, DT))


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


class LimitReached(RuntimeError):
    pass


class Study:
    def __init__(self, phase, attempt="", project_id=None):
        self.phase, self.started = phase, time.monotonic()
        self.db = Database(Settings.from_env().database_url)
        self.meta = json.loads((HERE / "platform.json").read_text(encoding="utf-8"))
        self.project = project_id or self.meta["project_id"]
        self.impl = capture_implementation("native")
        self.impl["harness_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.rows, self.runs, self.peak_rss = [], [], 0
        self.stem = phase + (f"-{attempt}" if attempt else "")
        self.file = WORK / f"{self.stem}-raw.zip"
        if self.file.exists():
            raise RuntimeError(f"Evidence already exists: {self.file}; do not overwrite an experiment")
        self.raw = zipfile.ZipFile(self.file, "w", zipfile.ZIP_DEFLATED, compresslevel=3)
        self.raw.writestr("protocol.md", (HERE / "protocol.md").read_bytes())
        self.raw.writestr("implementation.json", encode(self.impl))
        self.bytes_db = 0
        self.unfinished = set()
        with self.db.tx(self.project) as db:
            totals = db.execute(
                "SELECT coalesce(sum((metrics->>'nodes')::bigint),0) n, coalesce(sum((metrics->>'edges')::bigint),0) e FROM runs"
            ).fetchone()
            checkpoints = db.execute("SELECT coalesce(sum(byte_count),0) n FROM checkpoints").fetchone()
        # Include the queryable SQL projection and index allowance, not just the
        # compressed model bytes. This is a conservative per-project estimate.
        self.estimated_db = 320 * (int(totals["n"]) + int(totals["e"])) + int(checkpoints["n"])
        self.previous_elapsed = sum(
            json.loads(p.read_text(encoding="utf-8"))["elapsed_s"] for p in WORK.glob("*-results.json")
        )
        self.raw.writestr("harness.py", Path(__file__).read_bytes())

    def guard(self, engine=None):
        rss = psutil.Process().memory_info().rss
        self.peak_rss = max(self.peak_rss, rss)
        reason = None
        if rss > 2 * 1024**3 or psutil.virtual_memory().available < 3 * 1024**3:
            reason = "memory budget"
        if shutil.disk_usage(WORK).free < 15 * 1024**3 or self.file.stat().st_size > 200 * 1024**2:
            reason = "disk/evidence budget"
        if self.estimated_db + sum(p.stat().st_size for p in WORK.glob("*-raw.zip")) > 500 * 1024**2:
            reason = "checkpoint byte budget"
        if time.monotonic() - self.started + self.previous_elapsed > 15 * 60:
            reason = "wall time budget"
        if engine:
            m = engine.metrics()
            if m["nodes"] > 2000 or m["edges"] > 100000:
                reason = "network size budget"
        if reason:
            raise LimitReached(reason)

    def model(self, seed, mode, name, config=None, initial=None, parent=None):
        self.guard()
        engine = create_engine(config or Config(), state=initial)
        spec = RunSpec(
            environment="manual",
            clock="unbounded",
            duration_s=60,
            seed=seed,
            config=engine.config.to_dict(),
            text_sensor=TextSensorConfig(encoding=mode),
            structural_readout={"enabled": False},
            temporal_readout={"enabled": False},
        )
        run = self.db.create_run(
            self.project,
            f"{self.phase} · {name}",
            spec.model_dump(),
            parent_id=parent,
            origin_hash=initial.digest if initial else None,
            origin_kind="fork" if parent else None,
        )
        self.unfinished.add(str(run["id"]))
        context = {"initialized": True, "start_us": str(engine.time_us), "end_us": str(engine.time_us + 60_000_000)}
        inputs = RuntimeInputs(self.db, self.project, run["id"], engine, spec, context, engine.time_us)
        return engine, run, spec, inputs, []

    def send(self, model, text, at, intensity=1):
        _engine, _run, spec, inputs, _ = model
        sensor = TextSensor(spec.seed, spec.text_sensor)
        frames = [
            dict(frame, stimulus=replace(frame["stimulus"], time_us=at + frame["stimulus"].time_us))
            for frame in sensor.frames(text, intensity)
        ]
        envelope = envelope_record(
            uuid4(),
            "text-sensor",
            "manual-cli-text",
            {"text": text, "intensity": intensity},
            {"seed": spec.seed, "adapter": asdict(spec.text_sensor), "transduction": sensor.describe(text)},
            len(frames),
            sum(len(f["stimulus"].channels) for f in frames),
            version=TEXT_VERSION,
        )
        inputs.changes["envelopes"].append(envelope)
        inputs.schedule(envelope, frames)

    def advance(self, model, at):
        engine, _, _, inputs, _ = model
        engine.advance_to(at, inputs.observe, inputs_only=True)

    def save(self, model, descriptor):
        engine, run, spec, inputs, observations = model
        self.guard(engine)
        state = engine.capture_state()
        observations = observations or [engine.metrics()]
        cp = self.db.save_checkpoint(
            self.project,
            run["id"],
            state,
            expected_revision=0,
            status="completed",
            observations=observations,
            input_changes=inputs.take_changes(),
            context={
                "initialized": True,
                "protocol": spec.model_dump(),
                "start_us": "0",
                "end_us": str(engine.time_us),
                "input_bus": inputs.bus.capture(),
                "input_bus_run_id": str(run["id"]),
                "implementation": self.impl,
                "exploration": descriptor,
                "source_enabled": True,
            },
        )
        self.bytes_db += cp["byte_count"]
        self.estimated_db += cp["byte_count"] + 320 * (engine.metrics()["nodes"] + engine.metrics()["edges"])
        self.unfinished.discard(str(run["id"]))
        evidence = {
            "run_id": str(run["id"]),
            "checkpoint_id": str(cp["id"]),
            "state_hash": state.digest,
            "time_us": engine.time_us,
            "life": engine.life,
            "nodes": engine.metrics()["nodes"],
            "edges": engine.metrics()["edges"],
            **descriptor,
        }
        self.runs.append(evidence)
        return state, evidence

    @staticmethod
    def template(seed, mode, word):
        return dict(next(TextSensor(seed, TextSensorConfig(encoding=mode)).frames(word))["stimulus"].channels)

    def probe(self, parent, seed, mode, cue, route, templates, masks, *, tag, intensity=1):
        image, parent_info = parent
        model = self.model(
            seed,
            mode,
            f"{tag} · {route} · {cue or '无探针'}",
            initial=birth(image) if route == "birth" else image,
            parent=parent_info["run_id"],
        )
        engine = model[0]
        engine.reconfigure(Config(**(engine.config.to_dict() | {"plasticity": False})))
        model = (engine, model[1], model[2].model_copy(update={"config": engine.config.to_dict()}), model[3], model[4])
        start = engine.time_us
        if route == "live":
            self.advance(model, start + 800_000)
        start = engine.time_us
        if engine.life == "dead":
            _, info = self.save(model, {"stage": "probe", "tag": tag, "route": route, "cue": cue, "unavailable": True})
            return {"scores": None, "info": info}
        if cue:
            self.send(model, cue, start, intensity)
        samples, scored = [], []
        for delta in range(0, 1_000_001, DT):
            self.advance(model, start + delta)
            activity = engine.activations()
            # Keep every node value, including zero; no semantic selection in raw evidence.
            samples.append([str(start + delta), activity])
            identities = {n["id"]: n["channel"] for n in engine.observation_nodes()}
            by_channel = {identities[n]: value for n, value in activity}
            scored.append(
                {
                    word: sum(by_channel.get(c, 0) * weight for c, weight in mask.items()) / sum(mask.values())
                    if mask
                    else None
                    for word, mask in masks.items()
                }
            )
            if delta % 100_000 == 0:
                model[4].append(engine.metrics())
        result = {}
        for word in templates:
            values = [scored[d // DT][word] for d in WINDOW]
            result[word] = (
                (sum(values) - (values[0] + values[-1]) / 2) / (len(values) - 1)
                if all(v is not None for v in values)
                else None
            )
        _state, info = self.save(
            model, {"stage": "probe", "tag": tag, "route": route, "cue": cue, "intensity": intensity}
        )
        self.raw.writestr(
            f"probes/{info['run_id']}.json",
            encode(
                {
                    "info": info,
                    "node_channels": identities,
                    "all_node_activations": samples,
                    "score_by_time": scored,
                    "masks": masks,
                    "endpoint": result,
                }
            ),
        )
        return {"scores": result, "info": info}

    def train(self, seed, mode, sentences, tag, *, plasticity=True):
        model = self.model(seed, mode, tag, Config(plasticity=plasticity))
        for index, sentence in enumerate(sentences):
            if model[0].life == "dead":
                raise LimitReached("training consciousness died; no automatic resurrection")
            self.send(model, sentence, index * 800_000)
            self.advance(model, (index + 1) * 800_000)
            self.guard(model[0])
        result = self.save(model, {"stage": "train", "tag": tag, "seed": seed, "mode": mode, "sentences": sentences})
        return result

    def memory(self, pilot=False):
        for mode in ("anonymous-distributed", "literal-character"):
            seeds = SEEDS[:1] if pilot else SEEDS if mode == "anonymous-distributed" else SEEDS[:2]
            for seed in seeds:
                templates = {word: self.template(seed, mode, word) for word in ("松子", "铃铛")}
                excluded = set(self.template(seed, mode, "甲")) | set(self.template(seed, mode, "乙"))
                shared = set(templates["松子"]) & set(templates["铃铛"])
                masks = {
                    word: {c: v for c, v in values.items() if c not in excluded | shared}
                    for word, values in templates.items()
                }
                cases = [(n, arm) for n in ([4] if pilot else [1, 4, 12]) for arm in ("paired", "mixed", "swapped")]
                if not pilot:
                    cases += [(12, "learning_off"), (0, "paired")]
                for repetitions, arm in cases:
                    rng, sentences = random.Random(seed), []
                    for cycle in range(repetitions):
                        swap = arm == "swapped" or arm == "mixed" and cycle % 2 == 1
                        pair = ["甲是铃铛", "乙是松子"] if swap else ["甲是松子", "乙是铃铛"]
                        rng.shuffle(pair)
                        sentences.extend(pair)
                    tag = f"{mode}/{seed}/{repetitions}/{arm}"
                    parent = self.train(seed, mode, sentences, tag, plasticity=arm != "learning_off")
                    for route in ("birth", "live"):
                        sham = self.probe(parent, seed, mode, "", route, templates, masks, tag=tag)
                        for cue, target, foil in [("甲", "松子", "铃铛"), ("乙", "铃铛", "松子")]:
                            result = self.probe(parent, seed, mode, cue, route, templates, masks, tag=tag)
                            valid = (
                                result["scores"] is not None
                                and sham["scores"] is not None
                                and all(
                                    result["scores"][w] is not None and sham["scores"][w] is not None for w in templates
                                )
                            )
                            contrast = (
                                (
                                    result["scores"][target]
                                    - result["scores"][foil]
                                    - sham["scores"][target]
                                    + sham["scores"][foil]
                                )
                                if valid
                                else None
                            )
                            self.rows.append(
                                {
                                    "family": "memory",
                                    "mode": mode,
                                    "seed": seed,
                                    "repetitions": repetitions,
                                    "arm": arm,
                                    "route": route,
                                    "cue": cue,
                                    "target": target,
                                    "foil": foil,
                                    "contrast": contrast,
                                    "probe": result,
                                    "sham": sham,
                                    "parent": parent[1],
                                    "mask_sizes": {k: len(v) for k, v in masks.items()},
                                }
                            )
                    print(
                        f"completed {tag}; rows={len(self.rows)}; wall={time.monotonic() - self.started:.1f}s",
                        flush=True,
                    )

    def relations(self):
        mode = "anonymous-distributed"
        chains = ["A是B的父亲", "B是C的父亲", "D是E的父亲", "E是F的父亲"]
        for seed in SEEDS[:2]:
            templates = {word: self.template(seed, mode, word) for word in ("X", "Y", "U", "V")}
            questions = [f"{end}{suffix}" for end in ("Z", "W") for suffix in ("的爷爷", "的父亲", "")]
            excluded = set().union(*(set(self.template(seed, mode, q)) for q in questions))
            # Remove overlap with other measured names and any question's direct input.
            masks = {
                w: {
                    c: v
                    for c, v in features.items()
                    if c not in excluded and all(c not in other for ow, other in templates.items() if ow != w)
                }
                for w, features in templates.items()
            }
            for arm in ("correct", "wrong_template", "reversed_chain"):
                examples = chains + (
                    ["D是C的爷爷", "A是F的爷爷"] if arm == "wrong_template" else ["A是C的爷爷", "D是F的爷爷"]
                )
                rng, sentences = random.Random(seed), []
                for _ in range(8):
                    cycle = examples.copy()
                    rng.shuffle(cycle)
                    sentences.extend(cycle)
                heldout = (
                    ["Y是X的父亲", "Z是Y的父亲", "V是U的父亲", "W是V的父亲"]
                    if arm == "reversed_chain"
                    else ["X是Y的父亲", "Y是Z的父亲", "U是V的父亲", "V是W的父亲"]
                )
                for _ in range(4):
                    cycle = heldout.copy()
                    rng.shuffle(cycle)
                    sentences.extend(cycle)
                tag = f"relations/{seed}/{arm}"
                parent = self.train(seed, mode, sentences, tag)
                # Structural transfer is primary; continuing-state recall is covered
                # by Experiment 1. A blank child controls for spontaneous activity.
                sham = self.probe(parent, seed, mode, "", "birth", templates, masks, tag=tag)
                for query in questions:
                    result = self.probe(parent, seed, mode, query, "birth", templates, masks, tag=tag)
                    self.rows.append(
                        {
                            "family": "relations",
                            "seed": seed,
                            "arm": arm,
                            "query": query,
                            "probe": result,
                            "sham": sham,
                            "parent": parent[1],
                            "mask_sizes": {k: len(v) for k, v in masks.items()},
                        }
                    )
                print(f"completed {tag}; wall={time.monotonic() - self.started:.1f}s", flush=True)

    def sensitivity(self):
        previous = json.loads((WORK / "memory-results.json").read_text(encoding="utf-8"))
        mode = "anonymous-distributed"
        for seed in SEEDS[:2]:
            templates = {w: self.template(seed, mode, w) for w in ("松子", "铃铛")}
            excluded = set(self.template(seed, mode, "甲")) | set(self.template(seed, mode, "乙"))
            shared = set(templates["松子"]) & set(templates["铃铛"])
            masks = {w: {c: v for c, v in fs.items() if c not in excluded | shared} for w, fs in templates.items()}
            for arm in ("paired", "mixed", "swapped", "learning_off"):
                info = next(
                    r
                    for r in previous["runs"]
                    if r.get("stage") == "train" and r.get("tag") == f"{mode}/{seed}/12/{arm}"
                )
                _, image = self.db.load_checkpoint(self.project, info["run_id"])
                parent = (image, info)
                tag = f"sensitivity/{seed}/{arm}"
                sham = self.probe(parent, seed, mode, "", "birth", templates, masks, tag=tag)
                for intensity in (2, 4):
                    for cue, target, foil in [("甲", "松子", "铃铛"), ("乙", "铃铛", "松子")]:
                        result = self.probe(
                            parent, seed, mode, cue, "birth", templates, masks, tag=tag, intensity=intensity
                        )
                        contrast = (
                            result["scores"][target]
                            - result["scores"][foil]
                            - sham["scores"][target]
                            + sham["scores"][foil]
                        )
                        self.rows.append(
                            {
                                "family": "sensitivity",
                                "seed": seed,
                                "arm": arm,
                                "intensity": intensity,
                                "cue": cue,
                                "target": target,
                                "foil": foil,
                                "contrast": contrast,
                                "probe": result,
                                "sham": sham,
                                "parent": info,
                            }
                        )
                print(f"completed {tag}", flush=True)

    def close(self, reason):
        if self.unfinished:
            with self.db.tx(self.project) as db:
                db.execute(
                    "UPDATE runs SET status='cancelled',error=%s WHERE id=ANY(%s::uuid[]) AND status='queued'",
                    (reason, list(self.unfinished)),
                )
        result = {
            "phase": self.phase,
            "stop_reason": reason,
            "elapsed_s": time.monotonic() - self.started,
            "peak_rss_bytes": self.peak_rss,
            "checkpoint_bytes": self.bytes_db,
            "implementation": self.impl,
            "project": self.project,
            "rows": self.rows,
            "runs": self.runs,
        }
        result["estimated_project_db_bytes"] = self.estimated_db
        self.raw.writestr("results.json", encode(result))
        self.raw.close()
        (WORK / f"{self.stem}-results.json").write_bytes(encode(result))
        self.db.close()
        print(
            json.dumps(
                {k: result[k] for k in ("phase", "stop_reason", "elapsed_s", "peak_rss_bytes", "checkpoint_bytes")}
            ),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("pilot", "memory", "relations", "sensitivity"), required=True)
    parser.add_argument(
        "--attempt", default="", help="Distinct evidence name after a stopped attempt; never overwrites"
    )
    parser.add_argument("--project-id", help="Explicit new Lab project for an independent reproduction")
    parser.add_argument(
        "--output-dir", type=Path, help="New raw evidence directory; existing phase files are never overwritten"
    )
    args = parser.parse_args()
    if args.output_dir:
        WORK = args.output_dir.resolve()
        WORK.mkdir(parents=True, exist_ok=True)
    study = Study(args.phase, args.attempt, args.project_id)
    reason = "planned cases completed"
    try:
        # Labels are annotations only: verify identical stimuli before the experiments.
        for seed in SEEDS:
            for text in ("甲是松子", "乙是铃铛", "Z的爷爷"):
                anonymous = TextSensor(seed).frames(text)
                labeled = TextSensor(seed, TextSensorConfig(encoding="labeled-observation")).frames(text)
                assert [f["stimulus"] for f in anonymous] == [f["stimulus"] for f in labeled]
        if args.phase == "relations":
            study.relations()
        elif args.phase == "sensitivity":
            study.sensitivity()
        else:
            study.memory(args.phase == "pilot")
    except BaseException as exc:
        reason = f"stopped: {type(exc).__name__}: {exc}"
        raise
    finally:
        study.close(reason)
