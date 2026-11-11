"""E44 bounded development stages, via ordinary Runtime and external instruments."""

import argparse
import gzip
import json
import random
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import torch

from lab.tools.language_teaching_world import WORDS, TeachingWorld, co_observed
from lab.tools.recorded_background import RecordedBackground
from lab.tools.service_study import Study, StudyConfig, encoded, new_json, read_json, write_gzip
from threemind_runtime.codec import ArtifactCodec
from threemind_transformer.development import (
    StreamInput,
    TrajectoryBasis,
    activity_changes,
    compile_stream,
    input_summary,
)
from threemind_transformer.development_model import fit
from threemind_transformer.development_model import load as load_decoder
from threemind_transformer.language_protocol import LanguageProtocol, ScratchTraining
from threemind_transformer.language_senses import embedding_frame
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.scratch_language import load as load_input
from threemind_transformer.scratch_language import train as train_input

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/language-development-20261004"
CAL_NAMES, TEST_NAMES = ("壬", "癸", "子", "丑"), ("甲", "乙", "丁", "戊")
ROUTES = ("text", "sentence", "stream-dense", "stream-sparse")
END = 266
READOUTS = {"structural_readout": {"enabled": False}, "temporal_readout": {"enabled": False},
            "activity_readout": {"enabled": False}}


def study(prepare=False):
    return Study(StudyConfig("language-development/1", "E44 从零语言共同发育与内部活动", HERE, WORK, 35,
                            instance_limit=1536, wall_seconds=14400, storage_soft=6 * 2**30,
                            storage_hard=8 * 2**30, usage_soft_delta=8, usage_hard_delta=12), prepare=prepare)


def protocol(seed):
    return LanguageProtocol(seed=seed, input_model="scratch", output_model="scratch", mode="strict",
                            scratch_width=64, scratch_layers=2, scratch_context=256, maximum_tokens=32)


def guard(s, force=False):
    s.guard(force)
    if force or not hasattr(s, "compute_seconds"):
        # Training samples contain no timing metadata; parsing them on every
        # resource check wastes time and memory without adding budget evidence.
        s.compute_seconds = sum(read_json(p).get("wall_seconds", 0) for p in (WORK / "models").glob("*.json")
                                if not p.name.endswith(".training.json"))
        s.compute_seconds += sum(read_json(p).get("wall_seconds", 0) for p in (WORK / "decoded").glob("*.json"))
        s.compute_seconds += sum(read_json(p).get("wall_seconds", 0) for p in (WORK / "language-analysis").glob("*.json"))
        s.compute_seconds += sum(read_json(p).get("wall_seconds", 0) for p in (WORK / "continuous-text").glob("*.json"))
        for name in ("weak-validation.json", "bridge-expression.json"):
            if (WORK / name).exists():
                s.compute_seconds += read_json(WORK / name).get("wall_seconds", 0)
        failures = list((WORK / "interrupted-attempts").glob("*/failure.json"))
        s.compute_seconds += sum(read_json(p).get("wall_seconds", 0) for p in failures)
        if len(failures) + (s.completed_count or 0) >= s.settings.instance_limit:
            raise RuntimeError("aggregate instance budget including interrupted attempts")
    active = time.monotonic() - s.active_case.born_wall if s.active_case else 0
    if s.compute_seconds + s.completed_wall + active > 14400:
        raise RuntimeError("aggregate E44 compute budget")
    if torch.cuda.is_available() and torch.cuda.memory_allocated() > 3 * 2**30:
        raise RuntimeError("GPU memory budget")


def background():
    return RecordedBackground(WORK / "physical-telemetry.jsonl")


def save_state(path, value, cursor):
    path.mkdir(parents=True, exist_ok=True)
    image = value.engine.capture_state()
    with (path / "state.tmind").open("xb") as stream:
        stream.write(ArtifactCodec.encode(image, profile=value.profile))
    write_gzip(path / "context.json.gz", value.context())
    new_json(path / "summary.json", {"time_us": str(value.engine.time_us), "life": value.engine.life,
                                   "metrics": value.engine.metrics(), "cursor": cursor, "hash": image.digest})


def restore(path, seed):
    state = ArtifactCodec.decode((path / "state.tmind").read_bytes())
    with gzip.open(path / "context.json.gz", "rt", encoding="utf-8") as file:
        context = json.load(file)
    return LanguageSession(protocol(seed).model_dump(), image=state, context=context)


def observe(value, until, s):
    start = value.engine.time_us
    rows = []
    before = value.engine.metrics()["transport"]
    while True:
        rows.append({"time_us": str(value.engine.time_us), "nodes": [
            {"id": str(n["id"]), "channel": int(n["channel"]), "activation": float(n["activation"])}
            for n in value.engine.observation_nodes() if n["activation"] > 0]})
        if value.engine.time_us >= until or value.engine.life == "dead":
            break
        value.reader.advance_to(min(until, value.engine.time_us + 20000), guard=lambda: guard(s))
    after = value.engine.metrics()["transport"]
    return {"start_us": str(start), "planned_end_us": str(until), "end_us": str(value.engine.time_us),
            "trajectory": rows, "transport_delta": {k: after[k] - before[k] for k in before},
            "pending_external": value.reader.bus.pending_count(), "life": value.engine.life}


def input_model(s, seed):
    path = WORK / "models" / f"input-{seed}.safetensors"
    p = protocol(seed)
    if not path.exists():
        corpus = [*WORDS, *CAL_NAMES, *TEST_NAMES, "是", "我", "你", "谁", "。", "？"]
        corpus += [prefix + word + end for word in WORDS for prefix in ("", "我看见", "这是") for end in ("。", "？")]
        spec = ScratchTraining(protocol=p, texts=corpus, steps=1200, learning_rate=0.001)
        started = time.monotonic()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        s.active_case = SimpleNamespace(born_wall=started)
        result = train_input(spec, path, device, lambda: guard(s))
        new_json(path.with_suffix(".json"), result | {"wall_seconds": time.monotonic() - started, "device": device,
                                                     "corpus": corpus, "formal_assignments_exposed": False})
        s.active_case = None
        print(json.dumps({"input_trained": seed, "device": device, "seconds": time.monotonic() - started}), flush=True)
    p = p.model_copy(update={"input_checkpoint_sha256": read_json(path.with_suffix(".json"))["checkpoint_sha256"]})
    model = load_input(p, "input", "cpu", path)[1]
    return model


class Input:
    def __init__(self, route, seed, model):
        self.route, self.seed, self.model = route, seed, model
        self.value = LanguageSession(protocol(seed).model_dump(), seed=seed, readouts=READOUTS)
        self.world = TeachingWorld(seed)
        self.cache = {}

    def frames(self, text, intensity=1.0):
        if text not in self.cache:
            if self.route == "text":
                frames = list(self.value.sensor.frames(text))
            elif self.route == "sentence":
                from threemind_transformer.scratch_language import BOS
                ids = torch.tensor([[BOS, *text.encode("utf-8")]])
                with torch.no_grad():
                    vec = self.model(input_ids=ids).last_hidden_state[:, -1, :64]
                    vector = torch.nn.functional.normalize(vec, dim=1)[0].tolist()
                frames = [{"stimulus": embedding_frame(vector, protocol(self.seed)), "labels": {}}]
            else:
                frames = compile_stream(text, self.model, StreamInput(seed=self.seed, top_k=4 if self.route.endswith("sparse") else 0))
            self.cache[text] = frames
        return [{"stimulus": replace(row["stimulus"], intensity=intensity), "labels": {}} for row in self.cache[text]]

    def basis(self, tape):
        known = set()
        for text in (*WORDS, *CAL_NAMES, *TEST_NAMES, *[n + "是" + w + "。" for n in (*CAL_NAMES, *TEST_NAMES) for w in WORDS]):
            known.update(c for row in self.frames(text) for c, _ in row["stimulus"].channels)
        for item in range(4):
            known.update(c for c, _ in self.world.frame(self.world.sample(item)).channels)
        for row in tape.rows:
            if row["stimulus"]:
                known.update(int(c) for c, _ in row["stimulus"]["channels"])
        return TrajectoryBasis(tuple(sorted(known)))


def schedule(names, seed):
    order = list(range(4))
    random.Random(seed).shuffle(order)
    rows = []
    for slot, item in enumerate(order):
        rows.extend({"seconds": slot * 6 + i * 0.5, "item": item, "repetition": i} for i in range(12))
    for phase, (start, interval) in enumerate(((24, 2), (40, 4), (72, 8), (136, 16))):
        for repeat in range(8):
            for slot, item in enumerate(order):
                rows.append({"seconds": start + repeat * interval + slot * interval / 4,
                             "item": item, "repetition": 12 + phase * 8 + repeat})
    rows.extend({"seconds": 264 + slot * 0.5, "item": item, "repetition": 44} for slot, item in enumerate(order))
    return sorted(rows, key=lambda r: r["seconds"])


def finish_case(s, path, result, start):
    elapsed = time.monotonic() - start
    new_json(path / "result.json", result | {"wall_seconds": elapsed, "runner_signature": s.runner_signature})
    s.active_case = None
    s.completed_count = (s.completed_count or 0) + 1
    s.completed_wall += elapsed


def source(s, inp, tape, condition, names, stage):
    key = f"{stage}-{inp.route}-s{inp.seed}-{condition}"
    path = WORK / "cases" / key
    if (path / "result.json").exists():
        return path
    if path.exists():
        raise RuntimeError("partial source retained for review: " + key)
    guard(s, True)
    path.mkdir(parents=True)
    start = time.monotonic()
    s.active_case = SimpleNamespace(born_wall=start)
    value = LanguageSession(protocol(inp.seed).model_dump(), seed=inp.seed, readouts=READOUTS)
    if condition == "frozen":
        value.engine.reconfigure(replace(value.engine.config, plasticity=False))
    lessons = schedule(names, inp.seed) if condition != "untaught" else []
    assignment = list(range(4))[::-1] if condition == "reversed" else list(range(4))
    for row in lessons:
        row.update(text=names[row["item"]] + "是" + WORDS[assignment[row["item"]]] + "。",
                   object=assignment[row["item"]])
    new_json(path / "definition.json", {"route": inp.route, "seed": inp.seed, "condition": condition,
                                        "stage": stage, "names": names, "assignment": assignment,
                                        "lessons": lessons, "config": value.engine.capture_state().to_dict()["config"],
                                        "basis": inp.basis(tape).to_dict(), "visual_amount_per_frame": 2.0,
                                        "readouts": READOUTS, "input_intensity": 1.0})
    save_state(path / "initial", value, 0)
    cursor, lesson_cursor = 0, 0
    windows = []
    checkpoints = (END,) if stage == "cal" else (END, END + 60, END + 300)
    basis = inp.basis(tape)
    for end in checkpoints:
        with gzip.open(path / f"process-{end}.jsonl.gz", "xt", encoding="utf-8") as log:
            while value.engine.time_us < end * 1000000 and value.engine.life != "dead":
                until = min(end * 1000000, value.engine.time_us + 500000)
                cursor = tape.queue_before(value.reader, cursor, until)
                labels = []
                acquisition = []
                while lesson_cursor < len(lessons) and round(lessons[lesson_cursor]["seconds"] * 1e6) < until:
                    row = lessons[lesson_cursor]
                    visual = inp.world.sample(row["object"], row["repetition"] % 8)
                    frames = co_observed(inp.frames(row["text"]), inp.world.frame(visual))
                    value.reader.schedule(frames, at=round(row["seconds"] * 1e6), source="E44-shared-teaching-observation",
                                          adapter_id="language-development/1")
                    acquisition.append({"text": row["text"], "visual": visual, "input": input_summary(frames)})
                    labels.append(WORDS[row["object"]])
                    lesson_cursor += 1
                value.records.clear()
                process = observe(value, until, s)
                projection = basis.project(process)
                row = {"process": process, "projection": projection, "changes": activity_changes(process),
                       "teacher_labels": labels, "acquisition": acquisition}
                log.write(encoded(row).decode() + "\n")
                if stage == "cal" and (labels or condition == "untaught" and int(process["start_us"]) % 4000000 == 0):
                    windows.append({"values": projection["values"], "text": labels[-1] + "。" if labels else "",
                                    "source": key, "start_us": process["start_us"]})
        save_state(path / f"checkpoint-{end}", value, cursor)
        print(json.dumps({"checkpoint": key, "sim_s": end, "life": value.engine.life,
                          "edges": value.engine.metrics()["edges"], "wall_s": round(time.monotonic() - start, 1)}), flush=True)
    if stage == "cal":
        new_json(path / "calibration.json", windows)
    finish_case(s, path, {"key": key, "stage": stage, "route": inp.route, "seed": inp.seed,
                         "condition": condition, "life": value.engine.life, "metrics": value.engine.metrics()}, start)
    return path


def probe(s, inp, tape, source_path, seconds, cue_index, intensity=0.5, intervention="none", duration=2):
    definition = read_json(source_path / "definition.json")
    key = f"{source_path.name}-t{seconds}-q{cue_index}-i{intensity}-{intervention}-d{duration}"
    path = WORK / "cases" / key
    if (path / "result.json").exists():
        return read_json(path / "result.json")
    checkpoint = source_path / f"checkpoint-{seconds}"
    if read_json(checkpoint / "summary.json")["life"] == "dead":
        return None
    if path.exists():
        raise RuntimeError("partial probe retained: " + key)
    guard(s, True)
    path.mkdir(parents=True)
    start = time.monotonic()
    s.active_case = SimpleNamespace(born_wall=start)
    value = restore(checkpoint, inp.seed)
    cursor = read_json(checkpoint / "summary.json")["cursor"]
    if intervention == "transmission-off":
        value.engine.reconfigure(replace(value.engine.config, propagation_rate=0))
    elif intervention not in ("none", "no-external"):
        raise ValueError("unknown intervention")
    cue = None if cue_index < 0 else definition["names"][cue_index // 2] + ("是" if cue_index % 2 else "")
    if cue:
        value.reader.schedule(inp.frames(cue, intensity), source="E44-cue", adapter_id="language-development/1")
    target = None if cue is None else WORDS[definition["assignment"][cue_index // 2]]
    basis, windows = TrajectoryBasis(**definition["basis"]), []
    with gzip.open(path / "process.jsonl.gz", "xt", encoding="utf-8") as log:
        for window in range(duration * 2):
            if value.engine.life == "dead":
                break
            until = value.engine.time_us + 500000
            if intervention != "no-external":
                cursor = tape.queue_before(value.reader, cursor, until)
            process = observe(value, until, s)
            row = {"window": window, "process": process, "projection": basis.project(process),
                   "changes": activity_changes(process)}
            log.write(encoded(row).decode() + "\n")
            windows.append({"window": window, "projection": row["projection"], "changes": row["changes"],
                            "start_us": process["start_us"], "end_us": process["end_us"],
                            "transport": process["transport_delta"]})
    result = {"key": key, "kind": "probe", "source": source_path.name, "stage": definition["stage"],
              "route": inp.route, "seed": inp.seed, "condition": definition["condition"], "seconds": seconds,
              "cue": cue, "cue_index": cue_index, "intensity": intensity, "intervention": intervention,
              "duration": duration, "target": target, "windows": windows, "life": value.engine.life}
    save_state(path / "final", value, cursor)
    finish_case(s, path, result, start)
    return result


def calibrate(s):
    tape = background()
    model = input_model(s, 17)
    for route in ROUTES:
        inp = Input(route, 17, model)
        for condition in ("normal", "reversed", "untaught"):
            path = source(s, inp, tape, condition, CAL_NAMES, "cal")
            for index in range(8):
                probe(s, inp, tape, path, END, index)
            probe(s, inp, tape, path, END, -1, duration=12)


def train_outputs(s, route, seed):
    tape, model = background(), input_model(s, seed)
    inp = Input(route, seed, model)
    basis = inp.basis(tape)
    samples = []
    for condition in ("normal", "reversed", "untaught"):
        path = source(s, inp, tape, condition, CAL_NAMES, "cal")
        samples += read_json(path / "calibration.json")
    target = WORK / "models" / f"output-{route}-{seed}.safetensors"
    if not target.exists():
        new_json(target.with_suffix(".training.json"), {"basis": basis.to_dict(), "samples": samples})
        started = time.monotonic()
        s.active_case = SimpleNamespace(born_wall=started)
        result = fit(samples, basis, target, seed=seed, steps=1600, device="cuda" if torch.cuda.is_available() else "cpu",
                     check=lambda: guard(s), checkpoints=(200,))
        new_json(target.with_suffix(".json"), result)
        s.active_case = None
        print(json.dumps({"decoder_trained": route, "seed": seed, "seconds": time.monotonic() - started}), flush=True)
    return inp


def formal(s, route, seed):
    selection = read_json(WORK / "selection.json")
    if route not in selection["routes"] or seed not in (11, 37, 53):
        raise ValueError("formal route/seed differs from frozen calibration selection")
    inp = train_outputs(s, route, seed)
    tape = background()
    for condition in ("normal", "reversed", "frozen", "untaught"):
        path = source(s, inp, tape, condition, TEST_NAMES, "formal")
        for seconds in (END, END + 60, END + 300):
            for intensity in (0.5, 1.0):
                for index in range(8):
                    probe(s, inp, tape, path, seconds, index, intensity)
            probe(s, inp, tape, path, seconds, -1, duration=12)
            if seconds == END:
                probe(s, inp, tape, path, seconds, -1, intervention="transmission-off", duration=12)
                probe(s, inp, tape, path, seconds, -1, intervention="no-external", duration=12)


def decode(s, route, seed):
    path = WORK / "models" / f"output-{route}-{seed}.safetensors"
    model, _ = load_decoder(path, "cuda" if torch.cuda.is_available() else "cpu")
    dest = WORK / "decoded"
    dest.mkdir(exist_ok=True)
    for result_path in sorted((WORK / "cases").glob(f"formal-{route}-s{seed}-*/result.json")):
        case = read_json(result_path)
        if case.get("kind") != "probe" or (dest / (case["key"] + ".json")).exists():
            continue
        windows = case["windows"]
        started = time.monotonic()
        rows = model.decode([w["projection"]["values"] for w in windows]) if windows else []
        new_json(dest / (case["key"] + ".json"), {"key": case["key"], "outputs": rows,
                                                  "model": str(path.relative_to(WORK)),
                                                  "wall_seconds": time.monotonic() - started})
        guard(s)
    print(json.dumps({"decoded": route, "seed": seed}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["prepare", "calibrate", "formal", "decode"])
    parser.add_argument("--route", choices=ROUTES, default="stream-sparse")
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    torch.set_num_threads(2)
    s = study(prepare=args.operation == "prepare")
    try:
        if args.operation == "prepare":
            (WORK / "models").mkdir(exist_ok=True)
            new_json(WORK / "usage.json", {"used_percent": 35})
            shutil.copy2(ROOT / ".work/language-spaced-20261004/physical-telemetry.jsonl", WORK / "physical-telemetry.jsonl")
            new_json(WORK / "background-source.json", {"study": "E43", "scope": "host and recorder process",
                                                       "timestamps": "unchanged", "looped": False})
            print(json.dumps({"project": s.project, "work": str(WORK)}), flush=True)
        elif args.operation == "calibrate":
            calibrate(s)
        elif args.operation == "formal":
            formal(s, args.route, args.seed)
        elif args.operation == "decode":
            decode(s, args.route, args.seed)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
