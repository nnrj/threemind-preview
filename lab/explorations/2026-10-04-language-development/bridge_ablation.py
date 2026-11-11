"""Local, weight-matched interventions on existing sensory bridge connections."""

import gzip
import json
import time
from types import SimpleNamespace

import numpy as np
import torch
from analyze import paired, prediction, rows, templates
from experiment import (
    WORK,
    Input,
    background,
    finish_case,
    guard,
    input_model,
    observe,
    read_json,
    restore,
    save_state,
    study,
)

from lab.tools.service_study import encoded, new_json
from threemind_transformer.development import TrajectoryBasis, activity_changes


def masks(state, cue_channels, visual_channels):
    node_channels = {int(n["id"]): int(n["channel"]) for n in state["nodes"]}

    def is_bridge(edge):
        a, b = node_channels[int(edge["source"])], node_channels[int(edge["target"])]
        return a in cue_channels and b in visual_channels or b in cue_channels and a in visual_channels

    target = [e for e in state["edges"] if is_bridge(e)]
    candidates = [e for e in state["edges"] if not is_bridge(e)]
    control, errors = [], []
    if len(candidates) < len(target) or not target:
        raise ValueError("insufficient bridge/control edges")
    for edge in sorted(target, key=lambda e: -e["weight"]):
        selected = min(range(len(candidates)), key=lambda i: abs(candidates[i]["weight"] - edge["weight"]))
        match = candidates.pop(selected)
        control.append(match)
        errors.append(abs(match["weight"] - edge["weight"]))
    return {"bridge": target, "matched": control}, errors


def branch(s, inp, tape, source, seconds, cue_index, intensity, mask, edges):
    key = f"bridge-{source.name}-t{seconds}-q{cue_index}-i{intensity}-{mask}"
    path = WORK / "cases" / key
    if (path / "result.json").exists():
        return read_json(path / "result.json")
    if path.exists():
        raise RuntimeError("partial bridge case retained")
    guard(s, True)
    path.mkdir(parents=True)
    started = time.monotonic()
    s.active_case = SimpleNamespace(born_wall=started)
    checkpoint = source / f"checkpoint-{seconds}"
    value = restore(checkpoint, inp.seed)
    definition = read_json(source / "definition.json")
    cursor = read_json(checkpoint / "summary.json")["cursor"]
    pairs = [(int(e["source"]), int(e["target"])) for e in edges]
    value.engine.intervene(edges=pairs, action="silence")
    cue = None if cue_index < 0 else definition["names"][cue_index // 2] + ("是" if cue_index % 2 else "")
    if cue:
        value.reader.schedule(inp.frames(cue, intensity), source="E44-bridge-cue", adapter_id="language-development/1")
    new_json(path / "definition.json", {"source": source.name, "seconds": seconds, "cue": cue,
                                         "mask": mask, "edges": edges, "action": "silence"})
    basis, windows = TrajectoryBasis(**definition["basis"]), []
    with gzip.open(path / "process.jsonl.gz", "xt", encoding="utf-8") as out:
        for _ in range(4):
            until = value.engine.time_us + 500000
            cursor = tape.queue_before(value.reader, cursor, until)
            process = observe(value, until, s)
            projected = basis.project(process)
            changes = activity_changes(process)
            out.write(encoded({"process": process, "projection": projected, "changes": changes}).decode() + "\n")
            windows.append({"projection": projected, "changes": changes, "transport": process["transport_delta"]})
    save_state(path / "final", value, cursor)
    result = {"key": key, "kind": "bridge-ablation", "seed": inp.seed, "condition": definition["condition"],
              "seconds": seconds, "cue": cue, "cue_index": cue_index, "mask": mask, "windows": windows,
              "target": definition["assignment"][cue_index // 2] if cue_index >= 0 else None}
    finish_case(s, path, result, started)
    return result


def main():
    torch.set_num_threads(2)
    s = study()
    try:
        selection_path = WORK / "bridge-selection.json"
        if selection_path.exists():
            selected = read_json(selection_path)["selected"]
        else:
            _raw, observations = rows("formal")
            candidates = paired(observations)
            selected = []
            for seed in (11, 37, 53):
                success = sorted([p for p in candidates if p["seed"] == seed and p["route"] == "stream-sparse" and p["joint_correct"]],
                                 key=lambda p: (p["seconds"], p["intensity"], p["cue_index"]))
                if success:
                    selected.append(success[0])
            new_json(selection_path, {"criterion": "first registered joint success per seed", "selected": selected})
        result = []
        tape = background()
        for selected_case in selected:
            seed = selected_case["seed"]
            inp = Input("stream-sparse", seed, input_model(s, seed))
            visual_channels = {c for c, _ in inp.world.frame(inp.world.sample(0)).channels}
            for condition in ("normal", "reversed"):
                source = WORK / "cases" / f"formal-stream-sparse-s{seed}-{condition}"
                seconds, q, intensity = (selected_case[k] for k in ("seconds", "cue_index", "intensity"))
                definition = read_json(source / "definition.json")
                value = restore(source / f"checkpoint-{seconds}", seed)
                cue = definition["names"][q // 2] + ("是" if q % 2 else "")
                cue_channels = {c for f in inp.frames(cue) for c, _ in f["stimulus"].channels}
                try:
                    variants, errors = masks(value.engine.capture_state().to_dict(), cue_channels, visual_channels)
                except ValueError as error:
                    result.append({"seed": seed, "condition": condition, "skipped": str(error)})
                    continue
                for kind, edges in variants.items():
                    cued = branch(s, inp, tape, source, seconds, q, intensity, kind, edges)
                    blank = branch(s, inp, tape, source, seconds, -1, intensity, kind, edges)
                    template = templates(definition)
                    scored = []
                    for left, right in zip(cued["windows"], blank["windows"], strict=True):
                        scored.append((np.asarray(left["projection"]["values"]).mean(axis=0) -
                                       np.asarray(right["projection"]["values"]).mean(axis=0)) @ template.T)
                    score = np.asarray(scored).mean(axis=0)
                    result.append({"seed": seed, "condition": condition, "mask": kind, "edges": len(edges),
                                   "weight_match_max_error": max(errors), "seconds": seconds, "cue_index": q,
                                   "intensity": intensity, "target": cued["target"], "prediction": prediction(score),
                                   "response": score.tolist(), "correct": prediction(score) == cued["target"],
                                   "cases": [cued["key"], blank["key"]]})
        new_json(WORK / "bridge-results.json", {"selected": selected, "results": result})
        print(json.dumps({"selected": selected, "results": [{k: v for k, v in r.items() if k not in ("cases", "response")} for r in result]}), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
