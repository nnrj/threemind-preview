"""Separate amplitude-calibrated expression head; no formal labels or Core edits."""

import gzip
import json
import time
from dataclasses import replace
from types import SimpleNamespace

import torch
from experiment import WORK, background, finish_case, guard, observe, read_json, restore, save_state, study

from lab.tools.language_teaching_world import WORDS, TeachingWorld
from lab.tools.service_study import new_json, write_gzip
from threemind_transformer.development import TrajectoryBasis
from threemind_transformer.development_model import fit


def calibration(s, seed):
    base = WORK / "cases" / f"formal-stream-sparse-s{seed}-untaught" / "checkpoint-266"
    if not base.exists():
        raise RuntimeError("complete registered formal sources first")
    tape, world = background(), TeachingWorld(seed)
    cases = []
    for item in range(4):
        for intensity in (0.1, 0.3, 1.0):
            for variant in (8, 9):
                key = f"weak-visual-s{seed}-o{item}-i{intensity}-v{variant}"
                path = WORK / "cases" / key
                if (path / "result.json").exists():
                    cases.append(path)
                    continue
                if path.exists():
                    raise RuntimeError("partial weak calibration retained: " + key)
                guard(s, True)
                path.mkdir(parents=True)
                started = time.monotonic()
                s.active_case = SimpleNamespace(born_wall=started)
                value = restore(base, seed)
                cursor = read_json(base / "summary.json")["cursor"]
                visual = world.sample(item, variant)
                stimulus = replace(world.frame(visual), intensity=intensity)
                new_json(path / "definition.json", {"kind": "weak-visual-calibration", "seed": seed,
                                                     "item": item, "view": variant, "intensity": intensity,
                                                     "measurement": visual, "source": str(base.relative_to(WORK)),
                                                     "name_delivered_to_core": False})
                for index in range(20):
                    value.reader.schedule([{"stimulus": stimulus, "labels": {}}],
                                          source="E44-weak-visual-calibration", adapter_id="visual-teaching-world/1",
                                          at=value.engine.time_us + index * 100000)
                processes = []
                for _ in range(4):
                    until = value.engine.time_us + 500000
                    cursor = tape.queue_before(value.reader, cursor, until)
                    processes.append(observe(value, until, s))
                write_gzip(path / "process.json.gz", {"processes": processes, "teacher_text": WORDS[item] + "。"})
                save_state(path / "final", value, cursor)
                finish_case(s, path, {"key": key, "kind": "weak-visual-calibration", "seed": seed,
                                      "item": item, "intensity": intensity, "view": variant}, started)
                cases.append(path)
    return cases


def main():
    torch.set_num_threads(2)
    s = study()
    try:
        s.allow_extension()
        routes = read_json(WORK / "selection.json")["routes"]
        for seed in (11, 37, 53):
            cases = calibration(s, seed)
            for route in routes:
                target = WORK / "models" / f"output-{route}-{seed}-weak.safetensors"
                if target.exists():
                    continue
                original = WORK / "models" / f"output-{route}-{seed}.safetensors"
                old = read_json(original.with_suffix(".training.json"))
                basis, samples = TrajectoryBasis(**old["basis"]), old["samples"]
                for path in cases:
                    if read_json(path / "definition.json")["view"] != 8:
                        continue
                    with gzip.open(path / "process.json.gz", "rt", encoding="utf-8") as stream:
                        row = json.load(stream)
                    for process in row["processes"]:
                        samples.append({"values": basis.project(process)["values"], "text": row["teacher_text"],
                                        "source": path.name, "start_us": process["start_us"]})
                new_json(target.with_suffix(".training.json"), {"basis": basis.to_dict(), "samples": samples})
                started = time.monotonic()
                s.active_case = SimpleNamespace(born_wall=started)
                result = fit(samples, basis, target, seed=seed, steps=1200, initial=original, checkpoints=(),
                             device="cuda" if torch.cuda.is_available() else "cpu", check=lambda: guard(s))
                new_json(target.with_suffix(".json"), result)
                s.active_case = None
                print(json.dumps({"weak_expression_trained": [route, seed], "samples": len(samples)}), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
