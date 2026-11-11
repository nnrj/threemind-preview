"""Express local-intervention trajectories with both frozen output heads."""

import json
import time
from types import SimpleNamespace

import torch
from experiment import WORK, guard, read_json, study

from lab.tools.service_study import new_json
from threemind_transformer.development_model import load


def main():
    target = WORK / "bridge-expression.json"
    if target.exists():
        return
    s = study()
    try:
        started = time.monotonic()
        s.active_case = SimpleNamespace(born_wall=started)
        results = []
        for seed in (11, 37, 53):
            cases = [read_json(p) for p in (WORK / "cases").glob(f"bridge-*-s{seed}-*/result.json")]
            if not cases:
                continue
            for variant in ("base", "weak"):
                suffix = "" if variant == "base" else "-weak"
                model, _ = load(WORK / "models" / f"output-stream-sparse-{seed}{suffix}.safetensors",
                                "cuda" if torch.cuda.is_available() else "cpu")
                for case in cases:
                    outputs = model.decode([w["projection"]["values"] for w in case["windows"]])
                    results.append({k: case[k] for k in ("key", "seed", "condition", "cue", "mask", "target")} |
                                   {"variant": variant, "outputs": outputs})
                    guard(s)
                del model
        new_json(target, {"results": results, "wall_seconds": time.monotonic() - started})
        s.active_case = None
        print(json.dumps({"bridge_expression_cases": len(results)}), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    torch.set_num_threads(2)
    main()
