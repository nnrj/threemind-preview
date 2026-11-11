"""Registered, bounded external-device pilot. Core rules are never edited."""

import argparse
import gzip
import json
import random
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


from lab.tools.service_study import Study, StudyConfig, encoded, new_json, read_json
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.inheritance import birth
from threemind_runtime.robot_session import RobotSession
from threemind_runtime.robot_templates import custom_arm
from threemind_runtime.store import SQLiteStore
from threemind_transformer.language_bundle import pack
from threemind_transformer.language_compute import compute
from threemind_transformer.language_protocol import LanguageCompute, LanguageProtocol, LanguageTraining
from threemind_transformer.language_senses import advance_language, embedding_frame
from threemind_transformer.language_session import LanguageSession

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/robot-language-20261002"
NOUNS = ["松子", "铃铛", "陶杯", "柳叶"]
NAMES = ["甲", "乙", "丁", "戊"]


class DeviceStudy(Study):
    def guard(self, force=False):
        super().guard(force)
        if time.time() - self.meta["started_at_epoch"] > 14400:
            raise RuntimeError("four-hour study elapsed budget")
        if shutil.disk_usage("C:/").free < 8 * 2**30 or shutil.disk_usage("E:/").free < 30 * 2**30:
            raise RuntimeError("device study disk reserve")


def study(prepare=False):
    return DeviceStudy(
        StudyConfig(
            "robot-language-pilot/1",
            "E26 机械臂实用性与语言外设归因",
            HERE,
            WORK,
            5,
            instance_limit=256,
            wall_seconds=14400,
            storage_soft=8 * 2**30,
            storage_hard=10 * 2**30,
            usage_soft_delta=5,
            usage_hard_delta=8,
        ),
        prepare=prepare,
    )


def folder(key):
    path = WORK / "cases" / key
    path.mkdir(parents=True, exist_ok=True)
    if (path / "result.json").exists():
        return path, read_json(path / "result.json")
    if any(path.iterdir()):
        raise RuntimeError("partial evidence retained; register an explicit recovery before retry: " + key)
    return path, None


def save_state(path, session, kind):
    image = session.engine.capture_state()
    (path / "final.tmind").write_bytes(ArtifactCodec.encode(image, profile=session.profile))
    new_json(path / "context.json", session.context())
    SQLiteStore(path / "device.sqlite").save(
        kind, image, expected_revision=0, profile=session.profile, context=session.context()
    )
    return image


def robot_case(s, key, seed, environment_seed, *, image=None, condition="trained", seconds=4):
    path, previous = folder(key)
    if previous:
        return previous, ArtifactCodec.decode((path / "final.tmind").read_bytes())
    s.guard(True)
    start = time.monotonic()
    task = custom_arm()
    if condition in ("position", "skill"):
        task = task.model_copy(update={"control": task.control.model_copy(update={"mode": condition})})
    rng = random.Random(f"random-action:{seed}:{environment_seed}")
    with RobotSession(
        task.model_dump(mode="json"), seed=seed, environment_seed=environment_seed, image=image
    ) as session:
        if condition == "frozen":
            session.engine.reconfigure(replace(session.engine.config, plasticity=False))
        before = session.engine.capture_state()
        (path / "initial.tmind").write_bytes(ArtifactCodec.encode(before))
        new_json(
            path / "protocol.json",
            {
                "robot": task.model_dump(mode="json"),
                "seed": seed,
                "environment_seed": environment_seed,
                "condition": condition,
                "seconds": seconds,
            },
        )
        end = session.engine.time_us + int(seconds * 1e6)
        with gzip.open(path / "events.jsonl.gz", "xb") as stream:

            def record(row):
                row["before_delivery_core"] = {
                    "time_us": str(session.engine.time_us),
                    "activations": session.engine.activations(),
                }
                stream.write(encoded(row) + b"\n")

            while session.engine.time_us < end and session.engine.life != "dead":
                s.guard()
                if time.monotonic() - start > 180:
                    raise RuntimeError("single robot episode exceeded 180 wall seconds")
                action = [rng.uniform(-1, 1) for _ in task.world.motors] if condition == "random" else None
                if condition == "skill":
                    action = [0.4] * len(task.world.motors)
                session.advance(min(end, session.engine.time_us + 10000), record=record, action=action)
        final = save_state(path, session, "robot")
        result = {
            "key": key,
            "condition": condition,
            "seed": seed,
            "environment_seed": environment_seed,
            "initial_hash": before.digest,
            "final_hash": final.digest,
            "metrics": session.engine.metrics() | session.world.task_metrics(),
            "wall_seconds": time.monotonic() - start,
            "completed": session.engine.time_us == end,
        }
        new_json(path / "result.json", result)
    print(
        json.dumps(
            {
                "case": key,
                "distance": result["metrics"]["task_distance"],
                "success": result["metrics"]["task_success"],
                "seconds": result["wall_seconds"],
            }
        ),
        flush=True,
    )
    return result, final


def robots(s, count):
    for seed in (100201, 100202, 100203, 100204)[:count]:
        parents = []
        scores = []
        for candidate, env in enumerate((1101, 1102)):
            _, state = robot_case(s, f"robot/{seed}/train{candidate}", seed, env, seconds=6)
            parent = birth(state)
            parents.append(parent)
            distances = []
            for block in (2101, 2102):
                row, _ = robot_case(s, f"robot/{seed}/select{candidate}-{block}", seed, block, image=parent)
                distances.append(row["metrics"]["task_distance"])
            scores.append(sum(distances) / len(distances))
        winner = min(range(2), key=lambda index: (scores[index], index))
        selection = WORK / f"selection-{seed}.json"
        if not selection.exists():
            new_json(selection, {"seed": seed, "scores": scores, "winner": winner})
        for env in (3101, 3102, 3103):
            for kind in ("blank", "trained", "selected", "frozen", "random", "position", "skill"):
                image = None if kind in ("blank", "random", "skill") else parents[0 if kind == "trained" else winner]
                robot_case(s, f"robot/{seed}/test-{env}-{kind}", seed, env, image=image, condition=kind)


def protocol(route):
    return LanguageProtocol(
        input_model=route,
        output_model="scratch",
        mode="strict",
        scratch_width=64,
        scratch_layers=2,
        embedding_dimensions=64,
        maximum_tokens=16,
    )


def pulse(session, text, intensity, cache):
    session.records.clear()
    frames = (
        list(session.sensor.frames(text, intensity))
        if session.protocol.input_model == "text"
        else [{"stimulus": embedding_frame(cache[text], session.protocol, intensity), "labels": {}}]
    )
    process = advance_language(session.engine, frames, session.protocol, session.reader)
    return {
        "text": text,
        "intensity": intensity,
        "stimuli": [f["stimulus"].to_dict() for f in frames],
        "process": process,
        "readouts": list(session.records),
        "after_hash": session.engine.capture_state().digest,
    }


def decode(s, p, features, head, *, assistance=None):
    s.guard(True)
    payload = {"protocol": p.model_dump(), "features": features}
    if assistance is not None:
        payload["protocol"]["mode"] = "assisted"
        payload["assistance"] = assistance
    return compute("decode", payload, LanguageCompute(wall_seconds=180), head=head)[0]


def language(s, route):
    p = protocol(route)
    dest = WORK / "language" / route
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / "summary.json").exists():
        print("already completed language " + route, flush=True)
        return
    cache = {}
    texts = sorted(set(NOUNS + NAMES + [a + "是" + b for a in NAMES for b in NOUNS]))
    cache_path = dest / "encodings.json"
    if route == "scratch":
        if cache_path.exists():
            cache = read_json(cache_path)
        else:
            result, _ = compute("encode", {"protocol": p.model_dump(), "texts": texts}, LanguageCompute())
            single, _ = compute("encode", {"protocol": p.model_dump(), "texts": [texts[0]]}, LanguageCompute())
            assert result["vectors"][0] == single["vectors"][0]
            cache = dict(zip(texts, result["vectors"]))
            new_json(cache_path, cache)
    samples, calibration_inputs = [], []
    for noun in NOUNS:
        for intensity in (0.5, 1):
            session = LanguageSession(p.model_dump())
            row = pulse(session, noun, intensity, cache)
            samples.append({"features": row["process"]["features"], "text": noun})
            calibration_inputs.append(row)
    if not (dest / "calibration-inputs.json").exists():
        new_json(dest / "calibration-inputs.json", calibration_inputs)
    if not (dest / "head.safetensors").exists():
        train = LanguageTraining(
            protocol=p,
            samples=samples,
            steps=300,
            learning_rate=0.003,
            train_decoder=True,
            compute=LanguageCompute(wall_seconds=300),
        )
        meta, head = compute("train", train.model_dump(), train.compute)
        (dest / "head.safetensors").write_bytes(head)
        new_json(dest / "training.json", meta)
    head = (dest / "head.safetensors").read_bytes()
    calibration = []
    for noun in NOUNS:
        session = LanguageSession(p.model_dump())
        raw = pulse(session, noun, 0.8, cache)
        output = decode(s, p, raw["process"]["features"], head)
        calibration.append({"expected": noun, "output": output, "raw": raw})
    new_json(dest / "calibration.json", calibration)
    calibrated = sum(row["output"].get("text") == row["expected"] for row in calibration) >= 3
    # Continue raw Core controls even when language output is not a valid instrument.
    trained = {}
    for mapping in ("ordinary", "reversed"):
        path, old = folder(f"language/{route}/{mapping}")
        if old:
            trained[mapping] = (
                ArtifactCodec.decode((path / "final.tmind").read_bytes()),
                read_json(path / "context.json"),
            )
            continue
        start = time.monotonic()
        session = LanguageSession(p.model_dump())
        nouns = NOUNS if mapping == "ordinary" else list(reversed(NOUNS))
        sentences = [name + "是" + noun for name, noun in zip(NAMES, nouns)]
        sequence = [text for text in sentences for _ in range(12)]
        rng = random.Random(100217)
        for _ in range(2):
            review = list(sentences)
            rng.shuffle(review)
            sequence.extend(review)
        with gzip.open(path / "events.jsonl.gz", "xb") as stream:
            for text in sequence:
                s.guard(True)
                stream.write(encoded(pulse(session, text, 1, cache)) + b"\n")
        state = save_state(path, session, "language")
        (path / "language.tmlanguage").write_bytes(pack(state, session.context(), {"head": head}))
        new_json(
            path / "result.json",
            {
                "key": f"language/{route}/{mapping}",
                "wall_seconds": time.monotonic() - start,
                "sentences": sequence,
                "hash": state.digest,
                "metrics": session.engine.metrics(),
            },
        )
        trained[mapping] = (state, session.context())
    probes = []
    for condition in ("ordinary", "reversed", "blank"):
        for index, name in enumerate(NAMES):
            session = (
                LanguageSession(p.model_dump(), image=trained[condition][0], context=trained[condition][1])
                if condition in trained
                else LanguageSession(p.model_dump())
            )
            raw = pulse(session, name, 0.5, cache)
            output = decode(s, p, raw["process"]["features"], head)
            expected = (NOUNS if condition != "reversed" else list(reversed(NOUNS)))[index]
            probes.append({"condition": condition, "cue": name, "expected": expected, "output": output, "raw": raw})
            print(
                json.dumps(
                    {"language": route, "condition": condition, "cue": name, "decoded": output.get("text")},
                    ensure_ascii=False,
                ),
                flush=True,
            )
    constant = [sum(row["features"][i] for row in samples) / len(samples) for i in range(len(samples[0]["features"]))]
    for index, name in enumerate(NAMES):
        actual = probes[index]["raw"]["process"]["features"]
        shuffled = list(actual)
        random.Random(200 + index).shuffle(shuffled)
        for kind, feature in (
            ("exchanged", probes[(index + 1) % 4]["raw"]["process"]["features"]),
            ("shuffled", shuffled),
            ("constant", constant),
            ("transformer_only", [0.0] * len(actual)),
        ):
            probes.append(
                {
                    "condition": kind,
                    "cue": name,
                    "expected": NOUNS[index],
                    "features": feature,
                    "output": decode(s, p, feature, head, assistance=name if kind == "transformer_only" else None),
                }
            )
    new_json(dest / "probes.json", probes)
    new_json(
        dest / "summary.json",
        {
            "route": route,
            "calibration_correct": sum(r["output"].get("text") == r["expected"] for r in calibration),
            "language_instrument_valid": calibrated,
            "scores": {
                kind: sum(r["output"].get("text") == r["expected"] for r in probes if r["condition"] == kind)
                for kind in ("ordinary", "reversed", "blank", "exchanged", "shuffled", "constant", "transformer_only")
            },
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "robot", "language"))
    parser.add_argument("--seeds", type=int, choices=(2, 4), default=2)
    parser.add_argument("--route", choices=("text", "scratch"), default="text")
    args = parser.parse_args()
    s = study(prepare=args.phase == "prepare")
    try:
        if args.phase == "robot":
            robots(s, args.seeds)
        elif args.phase == "language":
            language(s, args.route)
        else:
            print(json.dumps({"project": s.project, "work": str(WORK)}))
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
