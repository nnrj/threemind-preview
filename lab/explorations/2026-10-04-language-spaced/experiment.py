"""E43: expanding reviews, ordinary stimuli, immutable physical background."""

import argparse
import gzip
import json
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.language_observation import embedding_basis_peaks, trace_summary
from lab.tools.recorded_background import RecordedBackground
from lab.tools.service_study import Study, StudyConfig, encoded, new_json, read_json, write_gzip
from lab.tools.spaced_reviews import PHASE_ENDS, schedule
from threemind_runtime.codec import ArtifactCodec
from threemind_transformer.language_compute import compute
from threemind_transformer.language_protocol import LanguageCompute, LanguageProtocol
from threemind_transformer.language_senses import advance_language, embedding_frame
from threemind_transformer.language_session import LanguageSession

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/language-spaced-20261004"
PREVIOUS = ROOT / ".work/language-centre-20261004"
WORDS, NAMES = ["松子", "铃铛", "陶杯", "柳叶"], ["甲", "乙", "丁", "戊"]
CONDITIONS = ("spaced", "reversed", "massed", "frozen", "untaught")
CHECKPOINTS = (*PHASE_ENDS, 530, 590, 830)
PROBES = (24, 144, 530, 590, 830)


def protocol(seed):
    return LanguageProtocol(
        input_model="qwen",
        output_model="qwen",
        mode="strict",
        seed=seed,
        response_us=500000,
        feature_bins=4,
        feature_buckets=64,
        embedding_dimensions=64,
        maximum_tokens=24,
    )


def study(prepare=False):
    return Study(
        StudyConfig(
            "language-spaced/1",
            "E43 普通强度间隔复习与真实遥测背景",
            HERE,
            WORK,
            34,
            instance_limit=512,
            wall_seconds=7200,
            storage_soft=3 * 2**30,
            storage_hard=4 * 2**30,
            usage_soft_delta=3,
            usage_hard_delta=5,
        ),
        prepare=prepare,
    )


def prepare_assets():
    if (WORK / "assets.json").exists():
        return
    source = PREVIOUS / "computations/encoded-material-approved-retry"
    result, request = read_json(source / "result.json"), read_json(source / "request.json")
    vectors = dict(zip(request["payload"]["texts"], result["vectors"]))
    selections, calibration = {}, {}
    for seed in (17, 29):
        chosen = read_json(PREVIOUS / f"selection-{seed}.json")["chosen"]
        if chosen["layout"] != "signed-average":
            raise ValueError("registered main projection changed")
        selections[str(seed)] = chosen
        shutil.copy2(
            PREVIOUS / "computations" / chosen["head_key"] / "weights.safetensors", WORK / f"head-{seed}.safetensors"
        )
        calibration[str(seed)] = [
            {"label": c["label"], "values": w["raw"]}
            for p in sorted((PREVIOUS / "cases").glob(f"s{seed}-cal-*/result.json"))
            for c in [read_json(p)]
            if c["split"] == "train"
            for w in c["windows"]
            if w["summary"]["has_activity"]
        ]
    new_json(
        WORK / "assets.json",
        {
            "vectors": vectors,
            "selection": selections,
            "calibration": calibration,
            "source_study": "E42",
            "source_project": "2f6dc868-4ee2-4131-af36-36f4935a9844",
            "mapping_unchanged": True,
            "test_answers_used_to_fit_head": False,
        },
    )
    sources = WORK / "runner-tools"
    sources.mkdir(exist_ok=True)
    for name in ("spaced_reviews.py", "recorded_background.py", "telemetry_recording.py", "language_observation.py"):
        shutil.copy2(ROOT / "lab/tools" / name, sources / name)


def restore(path, seed):
    image = ArtifactCodec.decode((path / "state.tmind").read_bytes())
    with gzip.open(path / "context.json.gz", "rt", encoding="utf-8") as stream:
        context = json.load(stream)
    return LanguageSession(protocol(seed).model_dump(), image=image, context=context)


def save_state(path, value):
    path.mkdir(parents=True, exist_ok=True)
    image = value.engine.capture_state()
    with (path / "state.tmind").open("xb") as stream:
        stream.write(ArtifactCodec.encode(image, profile=value.profile))
    write_gzip(path / "context.json.gz", value.context())
    return image.digest


def guard(s, force=False):
    s.guard(force)
    if force or not hasattr(s, "compute_wall"):
        s.compute_wall = sum(
            read_json(p).get("elapsed_seconds", 0) for p in (WORK / "computations").glob("*/result.json")
        )
    active = time.monotonic() - s.active_case.born_wall if s.active_case else 0
    if s.completed_wall + s.compute_wall + active >= 7200:
        raise RuntimeError("aggregate simulation and decoder budget")


def source(s, tape, assets, seed, condition):
    key = f"s{seed}-{condition}"
    path = WORK / "cases" / key
    if (path / "result.json").exists():
        return
    guard(s, True)
    previous = (
        sorted(path.glob("checkpoints/*/summary.json"), key=lambda p: int(p.parent.name)) if path.exists() else []
    )
    if previous:
        last = read_json(previous[-1])
        value = restore(previous[-1].parent, seed)
        cursor, lesson_index, elapsed = last["tape_cursor"], last["lesson_cursor"], last["wall_seconds"]
    elif path.exists():
        raise RuntimeError("source interrupted before a checkpoint; inspect before resuming")
    else:
        value = LanguageSession(protocol(seed).model_dump(), seed=seed, readouts=s.readers)
        if condition == "frozen":
            value.engine.reconfigure(replace(value.engine.config, plasticity=False))
        cursor, lesson_index, elapsed = 0, 0, 0.0
        path.mkdir(parents=True)
        save_state(path / "initial", value)
    labels = WORDS[::-1] if condition == "reversed" else WORDS
    texts = [name + "是" + word + "。" for name, word in zip(NAMES, labels)]
    lessons = schedule(
        texts, seed, "none" if condition == "untaught" else "massed" if condition == "massed" else "spaced"
    )
    if not (path / "definition.json").exists():
        new_json(
            path / "definition.json",
            {
                "key": key,
                "seed": seed,
                "condition": condition,
                "lessons": lessons,
                "protocol": value.protocol.model_dump(),
                "kernel": value.kernel_id,
                "config": value.engine.capture_state().to_dict()["config"],
                "readouts": value.readout_config,
                "background": "../../physical-telemetry.jsonl",
                "intensity": 1.0,
            },
        )
    started = time.monotonic() - elapsed
    s.active_case = SimpleNamespace(born_wall=started)
    last_message = time.monotonic()
    for end in CHECKPOINTS:
        if value.engine.time_us >= end * 1000000 or value.engine.life == "dead":
            continue
        segment = path / f"training-{end}.jsonl.gz"
        if segment.exists():
            raise RuntimeError("partial training segment retained; register recovery before rerun")
        with gzip.open(segment, "xt", encoding="utf-8") as log:
            while value.engine.time_us < end * 1000000 and value.engine.life != "dead":
                until = min(end * 1000000, value.engine.time_us + 1000000)
                value.records.clear()
                cursor = tape.queue_before(value.reader, cursor, until)
                while lesson_index < len(lessons) and lessons[lesson_index]["time_us"] < until:
                    item = lessons[lesson_index]
                    value.reader.schedule(
                        [
                            {
                                "stimulus": embedding_frame(assets["vectors"][item["text"]], value.protocol, 1.0),
                                "labels": {},
                            }
                        ],
                        at=item["time_us"],
                        source="ordinary-spaced-language",
                        adapter_id="language-transformer",
                    )
                    lesson_index += 1
                value.reader.advance_to(until, guard=lambda: guard(s))
                log.write(
                    encoded(
                        {
                            "time_us": str(value.engine.time_us),
                            "metrics": value.engine.metrics(),
                            "tape_cursor": cursor,
                            "lesson_cursor": lesson_index,
                            "readouts": value.records,
                        }
                    ).decode()
                    + "\n"
                )
                if time.monotonic() - last_message > 30:
                    print(
                        json.dumps(
                            {
                                "source": key,
                                "sim_seconds": value.engine.time_us / 1e6,
                                "wall_seconds": round(time.monotonic() - started),
                                "life": value.engine.life,
                            }
                        ),
                        flush=True,
                    )
                    last_message = time.monotonic()
        cp = path / "checkpoints" / str(end)
        state_hash = save_state(cp, value)
        summary = {
            "seed": seed,
            "condition": condition,
            "requested_seconds": end,
            "time_us": str(value.engine.time_us),
            "life": value.engine.life,
            "metrics": value.engine.metrics(),
            "state_hash": state_hash,
            "tape_cursor": cursor,
            "lesson_cursor": lesson_index,
            "wall_seconds": time.monotonic() - started,
        }
        new_json(cp / "summary.json", summary)
        print(
            json.dumps(
                {
                    "checkpoint": key,
                    "seconds": end,
                    "life": value.engine.life,
                    "wall_seconds": round(summary["wall_seconds"], 1),
                }
            ),
            flush=True,
        )
    new_json(
        path / "result.json",
        {
            "key": key,
            "seed": seed,
            "condition": condition,
            "kind": "source",
            "time_us": str(value.engine.time_us),
            "life": value.engine.life,
            "wall_seconds": time.monotonic() - started,
        },
    )
    s.active_case, s.completed_count = None, None


def probe(s, tape, assets, seed, condition, seconds, cue_index, *, intensity=0.5, prefix="", kind="probe"):
    source_key = f"s{seed}-{condition}"
    key = f"{prefix}{source_key}-t{seconds}-p{cue_index}"
    path = WORK / "cases" / key
    if (path / "result.json").exists():
        return
    cp = WORK / "cases" / source_key / "checkpoints" / str(seconds)
    if not (cp / "summary.json").exists() or read_json(cp / "summary.json")["life"] == "dead":
        return
    if path.exists():
        raise RuntimeError("partial probe retained: " + key)
    guard(s, True)
    value = restore(cp, seed)
    before = read_json(cp / "summary.json")
    cursor = before["tape_cursor"]
    cue = None if cue_index == 8 else NAMES[cue_index // 2] + ("是" if cue_index % 2 else "")
    label = None if cue is None else (WORDS[::-1] if condition == "reversed" else WORDS)[cue_index // 2]
    path.mkdir(parents=True)
    new_json(
        path / "definition.json",
        {
            "source": str(cp.relative_to(WORK)),
            "source_state_hash": before["state_hash"],
            "probe": cue,
            "probe_intensity": intensity,
            "background_cursor": cursor,
        },
    )
    started = time.monotonic()
    s.active_case = SimpleNamespace(born_wall=started)
    windows = []
    with gzip.open(path / "observations.jsonl.gz", "xt", encoding="utf-8") as log:
        for index in range(4):
            if value.engine.life == "dead":
                break
            value.records.clear()
            cursor = tape.queue_before(value.reader, cursor, value.engine.time_us + 500000)
            frames = (
                [{"stimulus": embedding_frame(assets["vectors"][cue], value.protocol, intensity), "labels": {}}]
                if cue and index == 0
                else []
            )
            process = advance_language(value.engine, frames, value.protocol, value.reader, lambda: guard(s))
            row = {
                "window": index,
                "features": process["features"],
                "basis": embedding_basis_peaks(process, value.protocol),
                "summary": trace_summary(process),
            }
            windows.append(row)
            log.write(encoded(row | {"process": process, "readouts": value.records}).decode() + "\n")
    result = {
        "key": key,
        "kind": kind,
        "probe_intensity": intensity,
        "source": source_key,
        "seed": seed,
        "condition": condition,
        "checkpoint": seconds,
        "probe": cue,
        "cue_index": cue_index,
        "label": label,
        "windows": windows,
        "time_us": str(value.engine.time_us),
        "life": value.engine.life,
        "metrics": value.engine.metrics(),
        "wall_seconds": time.monotonic() - started,
        "final_state_hash": value.engine.capture_state().digest,
    }
    new_json(path / "result.json", result)
    s.active_case, s.completed_count = None, None


def simulate(s, seeds, conditions):
    if not (WORK / "physical-telemetry.complete.json").exists():
        raise RuntimeError("finish real telemetry recording first")
    tape = RecordedBackground(WORK / "physical-telemetry.jsonl")
    if int(tape.rows[-1]["time_us"]) < 833000000:
        raise ValueError("background does not cover retention probes")
    assets = read_json(WORK / "assets.json")
    for seed in seeds:
        for condition in conditions:
            source(s, tape, assets, seed, condition)
            for seconds in PROBES:
                for cue in range(9):
                    probe(s, tape, assets, seed, condition, seconds, cue)
                print(
                    json.dumps({"probes": f"s{seed}-{condition}", "checkpoint": seconds, "status": "done"}), flush=True
                )


def decode(s, seeds):
    for seed in seeds:
        rows = []
        for path in sorted((WORK / "cases").glob(f"s{seed}-*-p*/result.json")):
            case = read_json(path)
            rows.extend(
                {
                    "key": case["key"],
                    "checkpoint": case["checkpoint"],
                    "condition": case["condition"],
                    "probe": case["probe"],
                    "label": case["label"],
                    "window": w["window"],
                    "features": w["features"],
                }
                for w in case["windows"]
                if w["window"] == 1 or case["probe"] is None
            )
        for begin in range(0, len(rows), 96):
            batch = rows[begin : begin + 96]
            path = WORK / "computations" / f"s{seed}-{begin}"
            if (path / "result.json").exists():
                if read_json(path / "index.json") != batch:
                    raise RuntimeError("decoding index changed; keep batches immutable")
                continue
            if path.exists():
                raise RuntimeError("failed/partial decoder retained; register recovery first")
            guard(s, True)
            used = s.completed_wall + sum(
                read_json(p).get("elapsed_seconds", 0) for p in (WORK / "computations").glob("*/result.json")
            )
            policy = LanguageCompute(
                compute_device="cuda", memory_mib=6144, wall_seconds=min(1800, max(1, int(7200 - used))), threads=2
            )
            new_json(path / "index.json", batch)
            payload = {"protocol": protocol(seed).model_dump(), "windows": [r["features"] for r in batch]}
            new_json(
                path / "request.json", {"operation": "decode_many", "policy": policy.model_dump(), "payload": payload}
            )
            try:
                result, _ = compute(
                    "decode_many", payload, policy, head=(WORK / f"head-{seed}.safetensors").read_bytes()
                )
            except Exception as error:
                new_json(path / "failure.json", {"error": str(error), "evidence": getattr(error, "report", None)})
                raise
            new_json(path / "result.json", result)
            print(
                json.dumps(
                    {"decoded": f"s{seed}-{begin}", "windows": len(batch), "seconds": result.get("elapsed_seconds")}
                ),
                flush=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "simulate", "decode"))
    parser.add_argument("--seeds", type=int, nargs="+", default=[17, 29])
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    args = parser.parse_args()
    s = study(prepare=args.action == "prepare")
    try:
        if args.action == "prepare":
            prepare_assets()
            print(json.dumps({"project": s.project, "work": str(WORK)}), flush=True)
        elif args.action == "simulate":
            simulate(s, args.seeds, args.conditions)
        else:
            decode(s, args.seeds)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
