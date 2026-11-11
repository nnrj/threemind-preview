"""Translate every recorded source window, including gaps, without feedback to Core."""

import argparse
import gzip
import json
import time
from types import SimpleNamespace

import torch
from experiment import WORK, guard, study

from lab.tools.service_study import encoded, new_json
from threemind_transformer.development_model import load


def translate(route, seed, variant="base"):
    s = study()
    try:
        destination = WORK / "continuous-text"
        destination.mkdir(exist_ok=True)
        for condition in ("normal", "reversed", "untaught"):
            source_key = f"formal-{route}-s{seed}-{condition}"
            suffix = "" if variant == "base" else "-weak"
            key = source_key + suffix
            final = destination / f"{key}.json"
            if final.exists():
                continue
            source = WORK / "cases" / source_key
            if not (source / "result.json").exists():
                raise RuntimeError("source incomplete")
            model, _ = load(WORK / "models" / f"output-{route}-{seed}{suffix}.safetensors",
                            "cuda" if torch.cuda.is_available() else "cpu")
            started = time.monotonic()
            s.active_case = SimpleNamespace(born_wall=started)
            pending, count = [], 0
            with gzip.open(destination / f"{key}.jsonl.gz", "xt", encoding="utf-8") as out:
                for end in (266, 326, 566):
                    with gzip.open(source / f"process-{end}.jsonl.gz", "rt", encoding="utf-8") as stream:
                        for line in stream:
                            row = json.loads(line)
                            pending.append(row)
                            if len(pending) == 32:
                                count += flush(model, pending, out, s)
                count += flush(model, pending, out, s)
            new_json(final, {"key": key, "source": source_key, "variant": variant, "rows": count, "route": route, "seed": seed,
                             "condition": condition, "wall_seconds": time.monotonic() - started,
                             "continuous_source": True, "offline_frozen_decoder": True,
                             "background": "recorded physical telemetry", "text_fed_back": False})
            s.active_case = None
            del model
            print(json.dumps({"continuous_translation": key, "windows": count}), flush=True)
    finally:
        s.db.close()


def flush(model, pending, out, s):
    if not pending:
        return 0
    words = model.decode([r["projection"]["values"] for r in pending])
    for row, word in zip(pending, words, strict=True):
        process = row["process"]
        out.write(encoded({"start_us": process["start_us"], "end_us": process["end_us"],
                           "teacher_labels": row["teacher_labels"], "acquisition": row["acquisition"],
                           "output": word, "changes": row["changes"],
                           "transport": process["transport_delta"], "life": process["life"],
                           "pending_external": process["pending_external"],
                           "activity": [[int(f["time_us"]), sum(n["activation"] for n in f["nodes"])]
                                        for f in process["trajectory"]]}).decode() + "\n")
    count = len(pending)
    pending.clear()
    guard(s)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--variant", choices=("base", "weak"), default="base")
    args = parser.parse_args()
    torch.set_num_threads(2)
    translate(args.route, args.seed, args.variant)
