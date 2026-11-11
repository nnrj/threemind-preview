"""Held-out measured visual views test calibration independently of formal answers."""

import gzip
import json
import time
from types import SimpleNamespace

import torch
from experiment import WORK, guard, read_json, study

from lab.tools.service_study import new_json
from threemind_transformer.development_model import load


def main():
    torch.set_num_threads(2)
    s = study()
    target = WORK / "weak-validation.json"
    try:
        if target.exists():
            return
        results = []
        started = time.monotonic()
        s.active_case = SimpleNamespace(born_wall=started)
        for seed in (11, 37, 53):
            for route in read_json(WORK / "selection.json")["routes"]:
                for variant in ("base", "weak"):
                    suffix = "" if variant == "base" else "-weak"
                    model, _ = load(WORK / "models" / f"output-{route}-{seed}{suffix}.safetensors",
                                    "cuda" if torch.cuda.is_available() else "cpu")
                    data, cases = [], []
                    for path in sorted((WORK / "cases").glob(f"weak-visual-s{seed}-*-v9")):
                        definition = read_json(path / "definition.json")
                        with gzip.open(path / "process.json.gz", "rt", encoding="utf-8") as stream:
                            row = json.load(stream)
                        for process in row["processes"]:
                            data.append(model.basis.project(process)["values"])
                            cases.append({"source": path.name, "intensity": definition["intensity"],
                                          "target": row["teacher_text"]})
                    for offset in range(0, len(data), 24):
                        words = model.decode(data[offset:offset + 24])
                        for case, output in zip(cases[offset:offset + 24], words, strict=True):
                            results.append(case | {"route": route, "seed": seed, "variant": variant,
                                                   "text": output["text"], "correct": output["text"] == case["target"]})
                        guard(s)
                    del model
        new_json(target, {"results": results, "wall_seconds": time.monotonic() - started,
                          "held_out": "view9 sources not used in amplitude calibration"})
        s.active_case = None
        print(json.dumps({"weak_validation_rows": len(results)}), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
