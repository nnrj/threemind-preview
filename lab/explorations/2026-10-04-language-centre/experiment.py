"""E42 bounded Qwen feasibility first. No changes to Core dynamics or old data."""

import argparse
import gzip
import json
import random
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.language_observation import channel_peaks, project, trace_summary
from lab.tools.service_study import Study, StudyConfig, encoded, new_json, read_json
from threemind_runtime.codec import ArtifactCodec
from threemind_transformer.language_compute import compute
from threemind_transformer.language_protocol import LanguageCompute, LanguageProtocol, LanguageTraining
from threemind_transformer.language_senses import advance_language, embedding_frame
from threemind_transformer.language_session import LanguageSession

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/language-centre-20261004"
WORDS = ["松子", "铃铛", "陶杯", "柳叶"]
NAMES = ["甲", "乙", "丁", "戊"]
SEEDS = [17, 29, 43, 71]
POLICY = LanguageCompute(compute_device="cuda", memory_mib=6144, wall_seconds=1800, threads=2)


def protocol(seed, layout="signed-average"):
    return LanguageProtocol(
        schema_id="threemind.language-adapter/1" if layout == "signed-average" else "threemind.language-adapter/2",
        feature_layout=layout,
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
            "language-centre/1",
            "E42 Qwen 可行性与自发活动语言转译",
            HERE,
            WORK,
            31,
            instance_limit=256,
            wall_seconds=14400,
            storage_soft=3 * 2**30,
            storage_hard=4 * 2**30,
            usage_soft_delta=3,
            usage_hard_delta=5,
        ),
        prepare=prepare,
    )


def compute_once(s, key, operation, payload, *, head=None):
    path = WORK / "computations" / key
    if (path / "result.json").exists():
        return read_json(path / "result.json"), (path / "weights.safetensors").read_bytes() if (
            path / "weights.safetensors"
        ).exists() else None
    recovery = key == "s29-unsigned-peak-80" and (path / "failure.json").exists()
    if recovery and "nonfinite mapping-head loss" not in read_json(path / "failure.json")["error"]:
        raise RuntimeError("recovery requires the recorded nonfinite loss")
    if path.exists() and not recovery:
        raise RuntimeError("partial computation retained; register recovery before retry: " + key)
    s.guard(True)
    used = sum(read_json(p).get("elapsed_seconds", 0) for p in (WORK / "computations").glob("*/result.json"))
    if used + s.completed_wall > 14400:
        raise RuntimeError("aggregate training/simulation budget")
    path.mkdir(parents=True, exist_ok=recovery)
    policy = POLICY.model_copy(update={"compute_device": "cpu"}) if recovery else POLICY
    new_json(
        path / ("cpu-recovery-request.json" if recovery else "request.json"),
        {
            "operation": operation,
            "payload": payload,
            "policy": policy.model_dump(),
            "reason": "Explicit fresh CPU float32 retry after nonfinite FP16 head loss" if recovery else None,
        },
    )
    try:
        result, weights = compute(operation, payload, policy, head=head)
    except Exception as error:
        new_json(
            path / ("cpu-recovery-failure.json" if recovery else "failure.json"),
            {"error": str(error), "evidence": getattr(error, "report", None)},
        )
        raise
    if recovery:
        result["recovery"] = "fresh CPU float32 retry; initial FP16 failure retained separately"
    if weights is not None:
        (path / "weights.safetensors").write_bytes(weights)
    new_json(path / "result.json", result)
    print(json.dumps({"stage": key, "status": "done", "seconds": result.get("elapsed_seconds")}), flush=True)
    return result, weights


def inputs(s):
    texts = WORDS + NAMES + [name + "是" for name in NAMES]
    texts += [name + "是" + word + "。" for name in NAMES for word in WORDS]
    # The first invocation failed before loading a model: Windows sandbox denied
    # access to its own temporary directory. Keep that evidence and retry once
    # in an explicitly approved process, without replacing the failed request.
    key = "encoded-material"
    failed = WORK / "computations" / key / "failure.json"
    if failed.exists() and not (failed.parent / "result.json").exists():
        if "WinError 5" not in read_json(failed)["error"]:
            raise RuntimeError("unreviewed encoding failure")
        key = "encoded-material-approved-retry"
        recovery = WORK / "encoding-recovery.json"
        if not recovery.exists():
            new_json(
                recovery,
                {
                    "original": str(failed.relative_to(WORK)),
                    "retry": key,
                    "reason": "Sandbox temporary-directory permission failure before model execution; approved local retry; no input or protocol change.",
                },
            )
    result, _ = compute_once(s, key, "encode", {"texts": texts, "protocol": protocol(17).model_dump()})
    return dict(zip(texts, result["vectors"]))


def read_case(key):
    path = WORK / "cases" / key
    if (path / "result.json").exists():
        return read_json(path / "result.json")
    if path.exists():
        raise RuntimeError("partial case retained: " + key)
    return None


def session(seed, source=None, frozen=False, config=None):
    if source:
        path = WORK / "cases" / source
        image = ArtifactCodec.decode((path / "final.tmind").read_bytes())
        value = LanguageSession(protocol(seed).model_dump(), image=image, context=read_json(path / "context.json"))
    else:
        value = LanguageSession(protocol(seed).model_dump(), seed=seed, config=config)
    if frozen:
        value.engine.reconfigure(replace(value.engine.config, plasticity=False))
    return value


def run_case(
    s,
    vectors,
    key,
    seed,
    *,
    lessons=(),
    source=None,
    probe=None,
    intensity=1.0,
    windows=4,
    frozen=False,
    label=None,
    split=None,
    waiting_windows=0,
    config=None,
    probe_intensity=0.5,
):
    previous = read_case(key)
    if previous:
        return previous
    s.guard(True)
    value = session(seed, source, frozen, config)
    path = WORK / "cases" / key
    path.mkdir(parents=True)
    started = time.monotonic()
    new_json(
        path / "definition.json",
        {
            "seed": seed,
            "source": source,
            "lessons": list(lessons),
            "probe": probe,
            "intensity": intensity,
            "probe_intensity": probe_intensity,
            "windows": windows,
            "frozen": frozen,
            "label": label,
            "split": split,
            "waiting_windows": waiting_windows,
            "protocol": value.protocol.model_dump(),
            "config": value.engine.capture_state().to_dict()["config"],
        },
    )
    (path / "initial.tmind").write_bytes(ArtifactCodec.encode(value.engine.capture_state()))
    compact = []

    def advance(text=None, strength=1.0):
        value.records.clear()
        frames = (
            []
            if text is None
            else [{"stimulus": embedding_frame(vectors[text], value.protocol, strength), "labels": {}}]
        )
        return advance_language(value.engine, frames, value.protocol, value.reader, lambda: s.guard())

    with gzip.open(path / "teaching.jsonl.gz", "wt", encoding="utf-8") as log:
        for index in range(waiting_windows):
            process = advance()
            log.write(
                encoded({"text": None, "waiting_window": index, "process": process, "readouts": value.records}).decode()
                + "\n"
            )
        for text in lessons:
            process = advance(text, intensity)
            log.write(
                encoded(
                    {
                        "text": text,
                        "vector": vectors[text],
                        "intensity": intensity,
                        "process": process,
                        "readouts": value.records,
                    }
                ).decode()
                + "\n"
            )
    with gzip.open(path / "observations.jsonl.gz", "wt", encoding="utf-8") as log:
        for index in range(windows):
            if value.engine.life == "dead":
                break
            pending = value.reader.bus.pending_count()
            process = advance(probe if index == 0 else None, probe_intensity if probe else intensity)
            row = {
                "window": index,
                "new_input": bool(index == 0 and probe),
                "pending_external_before": pending,
                "raw": channel_peaks(process, value.protocol),
                "summary": trace_summary(process),
                "signed-average": process["features"],
                "unsigned-peak": project(process, protocol(seed, "unsigned-peak")),
            }
            compact.append(row)
            log.write(encoded(row | {"process": process, "readouts": value.records}).decode() + "\n")
    image = value.engine.capture_state()
    (path / "final.tmind").write_bytes(ArtifactCodec.encode(image, profile=value.profile))
    new_json(path / "context.json", value.context())
    result = {
        "key": key,
        "seed": seed,
        "label": label,
        "split": split,
        "source": source,
        "probe": probe,
        "windows": compact,
        "life": value.engine.life,
        "time_us": str(value.engine.time_us),
        "wall_seconds": time.monotonic() - started,
        "metrics": value.engine.metrics(),
        "state_hash": image.digest,
    }
    new_json(path / "result.json", result)
    s.completed_count = None
    print(
        json.dumps(
            {
                "case": key,
                "life": value.engine.life,
                "windows": len(compact),
                "seconds": round(result["wall_seconds"], 2),
            }
        ),
        flush=True,
    )
    return result


def calibrate(s, vectors, seeds):
    for seed in seeds:
        for wi, word in enumerate(WORDS):
            for condition, strength, count, split in (
                ("low", 0.5, 1, "train"),
                ("ordinary", 1.0, 3, "train"),
                ("heldout", 0.8, 2, "heldout"),
            ):
                run_case(
                    s,
                    vectors,
                    f"s{seed}-cal-{wi}-{condition}",
                    seed,
                    lessons=[word] * count,
                    intensity=strength,
                    windows=4,
                    label=word,
                    split=split,
                )
        cases = [read_json(p) for p in (WORK / "cases").glob(f"s{seed}-cal-*/result.json")]
        train = [(c, w) for c in cases if c["split"] == "train" for w in c["windows"] if w["summary"]["has_activity"]]
        heldout = [(c, w) for c in cases if c["split"] == "heldout" for w in c["windows"]]
        selections = []
        for layout in ("signed-average", "unsigned-peak"):
            for steps in (80, 600):
                p = protocol(seed, layout)
                training = LanguageTraining(
                    protocol=p,
                    samples=[{"features": w[layout], "text": c["label"] + "。"} for c, w in train],
                    steps=steps,
                    learning_rate=0.003,
                    compute=POLICY,
                )
                key = f"s{seed}-{layout}-{steps}"
                failure = WORK / "computations" / key / "failure.json"
                if key == "s29-unsigned-peak-600" and failure.exists():
                    if "nonfinite mapping-head loss" not in read_json(failure)["error"]:
                        raise RuntimeError("unreviewed calibration failure")
                    selections.append(
                        {
                            "layout": layout,
                            "steps": steps,
                            "correct": None,
                            "total": len(heldout),
                            "head_key": key,
                            "status": "numerical_failure",
                            "reason": "FP16 failed; CPU 600-step retry deferred. Signed-average held-out accuracy is already maximal.",
                        }
                    )
                    continue
                _, head = compute_once(s, key, "train", training.model_dump())
                decoded, _ = compute_once(
                    s,
                    key + "-validation",
                    "decode_many",
                    {"protocol": p.model_dump(), "windows": [w[layout] for c, w in heldout]},
                    head=head,
                )
                correct = sum(classify(d.get("text")) == c["label"] for (c, w), d in zip(heldout, decoded["windows"]))
                selections.append(
                    {"layout": layout, "steps": steps, "correct": correct, "total": len(heldout), "head_key": key}
                )
        chosen = max(
            (v for v in selections if v["steps"] == 600 and v["correct"] is not None),
            key=lambda v: (v["correct"], v["layout"] == "signed-average"),
        )
        selection = {
            "seed": seed,
            "candidates": selections,
            "chosen": chosen,
            "test_answers_used": False,
            "calibration_passed": chosen["correct"] >= 0.75 * chosen["total"],
        }
        target = WORK / f"selection-{seed}.json"
        if not target.exists():
            new_json(target, selection)
        print(json.dumps({"calibration": selection}, ensure_ascii=False), flush=True)


def classify(text):
    found = [word for word in WORDS if word in (text or "")]
    return found[0] if len(found) == 1 else None


def curriculum(seed, reverse=False):
    labels = WORDS[::-1] if reverse else WORDS
    sentences = [name + "是" + word + "。" for name, word in zip(NAMES, labels)]
    result = []
    order = list(range(4))
    random.Random(seed).shuffle(order)
    for rounds in (12, 6, 3):
        result.extend(sentence for i in order for sentence in [sentences[i]] * rounds)
        order = order[1:] + order[:1]
    return result


def formal(s, vectors, seeds):
    for seed in seeds:
        if not (WORK / f"selection-{seed}.json").exists():
            raise RuntimeError("freeze calibration choice first")
        for condition in ("ordinary", "reversed", "blank", "frozen"):
            key = f"s{seed}-{condition}"
            lessons = [] if condition == "blank" else curriculum(seed, condition == "reversed")
            run_case(
                s,
                vectors,
                key,
                seed,
                lessons=lessons,
                windows=0,
                frozen=condition == "frozen",
                waiting_windows=len(curriculum(seed)) if condition == "blank" else 0,
            )
            for name_index, name in enumerate(NAMES):
                for suffix in ("", "是"):
                    target = WORDS[::-1][name_index] if condition == "reversed" else WORDS[name_index]
                    run_case(
                        s,
                        vectors,
                        key + f"-probe-{name_index}-{len(suffix)}",
                        seed,
                        source=key,
                        probe=name + suffix,
                        windows=4,
                        label=target,
                        split="formal",
                    )
            run_case(s, vectors, key + "-spontaneous", seed, source=key, windows=40, split="unprompted")


def decode_formal(s, seeds):
    for seed in seeds:
        selection = read_json(WORK / f"selection-{seed}.json")["chosen"]
        layout = selection["layout"]
        p = protocol(seed, layout)
        cases = [
            read_json(f)
            for f in sorted((WORK / "cases").glob(f"s{seed}-*/result.json"))
            if "-probe-" in f.parent.name or f.parent.name.endswith("-spontaneous")
        ]
        rows = [
            {
                "key": c["key"],
                "label": c["label"],
                "probe": c["probe"],
                "window": w["window"],
                "features": w[layout],
                "raw": w["raw"],
                "summary": w["summary"],
            }
            for c in cases
            for w in c["windows"]
        ]
        for start in range(0, len(rows), 128):
            batch = rows[start : start + 128]
            key = f"s{seed}-formal-{start}"
            index = WORK / "computations" / (key + "-index.json")
            if not index.exists():
                new_json(index, batch)
            head = (WORK / "computations" / selection["head_key"] / "weights.safetensors").read_bytes()
            compute_once(
                s,
                key,
                "decode_many",
                {"protocol": p.model_dump(), "windows": [r["features"] for r in batch]},
                head=head,
            )
        # Counterfactual output controls use exactly the preregistered 0.5-1s window.
        tested = [r for r in rows if r["probe"] and r["window"] == 1]
        changed = []
        for r in tested:
            shuffled = r["features"].copy()
            random.Random(f"shuffle:{seed}:{r['key']}").shuffle(shuffled)
            for kind, features in (("zero", [0.0] * len(shuffled)), ("shuffled", shuffled)):
                changed.append({"key": r["key"], "label": r["label"], "control": kind, "features": features})
            other_key = (
                r["key"].replace("-ordinary-", "-reversed-")
                if "-ordinary-" in r["key"]
                else r["key"].replace("-reversed-", "-ordinary-")
            )
            if other_key != r["key"]:
                other = next(v for v in tested if v["key"] == other_key)
                changed.append(
                    {
                        "key": r["key"],
                        "label": r["label"],
                        "control": "swapped_experience",
                        "features": other["features"],
                    }
                )
        for start in range(0, len(changed), 128):
            batch = changed[start : start + 128]
            key = f"s{seed}-controls-{start}"
            if not (WORK / "computations" / (key + "-index.json")).exists():
                new_json(WORK / "computations" / (key + "-index.json"), batch)
            compute_once(
                s,
                key,
                "decode_many",
                {"protocol": p.model_dump(), "windows": [r["features"] for r in batch]},
                head=(WORK / "computations" / selection["head_key"] / "weights.safetensors").read_bytes(),
            )
        # Same spontaneous activity through early calibration; no Core re-execution.
        spontaneous = [r for r in rows if "-spontaneous" in r["key"]]
        for start in range(0, len(spontaneous), 128):
            batch = spontaneous[start : start + 128]
            key = f"s{seed}-early-stream-{start}"
            if not (WORK / "computations" / (key + "-index.json")).exists():
                new_json(WORK / "computations" / (key + "-index.json"), batch)
            compute_once(
                s,
                key,
                "decode_many",
                {"protocol": p.model_dump(), "windows": [r["features"] for r in batch]},
                head=(WORK / "computations" / f"s{seed}-{layout}-80" / "weights.safetensors").read_bytes(),
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "calibrate", "formal", "decode"))
    parser.add_argument("--seeds", default="17,29,43,71")
    args = parser.parse_args()
    seeds = [int(v) for v in args.seeds.split(",")]
    if set(seeds) - set(SEEDS):
        raise ValueError("unregistered seed")
    s = study(args.stage == "prepare")
    try:
        if args.stage == "prepare":
            new_json(WORK / "usage.json", {"used_percent": 31})
            new_json(
                WORK / "protocol.json",
                {
                    "seeds": SEEDS,
                    "words": WORDS,
                    "names": NAMES,
                    "phase": "Qwen feasibility first",
                    "core": "continuous-memory/2",
                    "windows_us": 500000,
                    "primary_response_window": [500000, 1000000],
                    "reviews": [12, 6, 3],
                    "background": "none; explicitly no live telemetry",
                    "calibration_steps": [80, 600],
                    "gate": "heldout>=75%; new pairings > blank and reverse in >=3/4 seeds with activity dependence",
                },
            )
            print(json.dumps({"project": s.project, "work": str(WORK)}))
        else:
            vectors = inputs(s)
            if args.stage == "calibrate":
                calibrate(s, vectors, seeds)
            elif args.stage == "formal":
                formal(s, vectors, seeds)
            else:
                decode_formal(s, seeds)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
