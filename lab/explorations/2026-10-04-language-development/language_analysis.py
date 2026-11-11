"""Evaluate frozen expression on held-out experiences and unprompted trajectories."""

import argparse
import gzip
import json
import random
import time
from collections import Counter
from types import SimpleNamespace

import numpy as np
import torch
from experiment import WORK, guard, read_json, study

from lab.tools.service_study import new_json
from threemind_transformer.development_model import load


def evaluate(route, seed, variant="base"):
    s = study()
    try:
        suffix = "" if variant == "base" else "-weak"
        target = WORK / "language-analysis" / f"{route}-{seed}{suffix}.json"
        if target.exists():
            return
        target.parent.mkdir(exist_ok=True)
        final = WORK / "models" / f"output-{route}-{seed}{suffix}.safetensors"
        outputs = {}
        started = time.monotonic()
        s.active_case = SimpleNamespace(born_wall=started)
        for checkpoint in (("step200", "final") if variant == "base" else ("weak",)):
            path = final if checkpoint in ("final", "weak") else final.with_name(final.stem + "-step200.safetensors")
            model, _ = load(path, "cuda" if torch.cuda.is_available() else "cpu")
            teaching = []
            for condition in ("normal", "reversed", "frozen", "untaught"):
                source = WORK / "cases" / f"formal-{route}-s{seed}-{condition}"
                if not (source / "result.json").exists():
                    raise RuntimeError("formal source incomplete")
                pending = []

                def flush(batch=pending, decoder=model, collected=teaching):
                    if not batch:
                        return
                    decoded = decoder.decode([row["values"] for row in batch])
                    for row, result in zip(batch, decoded, strict=True):
                        collected.append({k: row[k] for k in ("condition", "start_us", "target")} | {
                            "text": result["text"], "correct": result["text"] == row["target"]})
                    batch.clear()
                    guard(s)

                with gzip.open(source / "process-266.jsonl.gz", "rt", encoding="utf-8") as stream:
                    for line in stream:
                        row = json.loads(line)
                        labels = row["teacher_labels"]
                        if labels or condition == "untaught" and int(row["process"]["start_us"]) % 4000000 == 0:
                            pending.append({"values": row["projection"]["values"], "condition": condition,
                                            "start_us": row["process"]["start_us"], "target": labels[-1] + "。" if labels else ""})
                        if len(pending) >= 32:
                            flush()
                flush()
            probes = []
            for result_file in sorted((WORK / "cases").glob(f"formal-{route}-s{seed}-*/result.json")):
                case = read_json(result_file)
                if case.get("kind") != "probe":
                    continue
                values = [row["projection"]["values"] for row in case["windows"]]
                # Pairing and transformations affect only the readout, never Core.
                modified = {}
                if case["cue"] is None:
                    modified["zero"] = np.zeros_like(values).tolist()
                    modified["reverse_time_bins"] = [list(reversed(v)) for v in values]
                    shuffled = np.asarray(values).copy()
                    order = list(range(shuffled.shape[2]))
                    random.Random(903).shuffle(order)
                    modified["permuted_channels"] = shuffled[:, :, order].tolist()
                decoded = model.decode(values) if values else []
                alterations = {key: model.decode(v) for key, v in modified.items()}
                probes.append({"key": case["key"], "cue": case["cue"], "target": case["target"],
                               "seconds": case["seconds"], "intensity": case["intensity"],
                               "intervention": case["intervention"], "condition": case["condition"],
                               "outputs": decoded, "altered": alterations})
                guard(s)
            outputs[checkpoint] = {"teaching": teaching, "probes": probes,
                                   "teaching_correct": sum(r["correct"] for r in teaching),
                                   "teaching_total": len(teaching),
                                   "unprompted_words": dict(Counter(o["text"] for r in probes if r["cue"] is None for o in r["outputs"]))}
            del model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        value = {"route": route, "seed": seed, "results": outputs, "wall_seconds": time.monotonic() - started,
                 "held_out": "formal names/relations and Core histories absent from decoder training"}
        new_json(target, value)
        s.active_case = None
        print(json.dumps({"language_evaluated": [route, seed], "seconds": value["wall_seconds"],
                          "teaching": {k: [v["teaching_correct"], v["teaching_total"]] for k, v in outputs.items()}}, ensure_ascii=False), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--variant", choices=("base", "weak"), default="base")
    args = parser.parse_args()
    torch.set_num_threads(2)
    evaluate(args.route, args.seed, args.variant)
