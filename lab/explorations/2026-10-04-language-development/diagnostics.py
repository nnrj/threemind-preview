"""Read completed E44 evidence once; never advance or reconfigure a Core."""

import gzip
import json
from collections import Counter, defaultdict

import numpy as np
from analyze import paired, rows
from experiment import HERE, TEST_NAMES, WORK, Input, background, protocol, read_json

from lab.tools.language_teaching_world import WORDS, TeachingWorld
from lab.tools.service_study import new_json
from threemind_runtime.codec import ArtifactCodec
from threemind_transformer.development import input_summary
from threemind_transformer.scratch_language import load as load_input


def groups(rows, keys):
    result = defaultdict(list)
    for row in rows:
        result[tuple(row[k] for k in keys)].append(row)
    return result


def fraction(rows, key="correct"):
    return {"correct": sum(bool(r[key]) for r in rows), "total": len(rows)}


def expression():
    result, comparisons, details = [], [], []
    for path in sorted((WORK / "language-analysis").glob("*.json")):
        data = read_json(path)
        for checkpoint, value in data["results"].items():
            identity = {"route": data["route"], "seed": data["seed"], "head": checkpoint}
            teaching = value["teaching"]
            probes = value["probes"]
            record = identity | {
                "teaching": {k[0]: fraction(v) for k, v in groups(teaching, ("condition",)).items()},
                "no_cue": dict(Counter(o["text"] for r in probes if r["cue"] is None for o in r["outputs"])),
                "controls": {kind: dict(Counter(o["text"] for r in probes if r["cue"] is None
                                               for o in r["altered"].get(kind, [])))
                             for kind in ("zero", "reverse_time_bins", "permuted_channels")},
            }
            cued = [r for r in probes if r["cue"] is not None]
            no_cue = {(r["condition"], r["seconds"]): r for r in probes
                      if r["cue"] is None and r["intervention"] == "none"}
            record["cued"] = {}
            for key, subset in groups(cued, ("condition",)).items():
                outputs = [o | {"correct": o["text"] == r["target"] + "。"}
                           for r in subset for o in r["outputs"]]
                record["cued"][key[0]] = fraction(outputs) | {
                    "texts": dict(Counter(o["text"] for o in outputs))}
            for key, subset in groups([r for r in cued if r["condition"] in ("normal", "reversed")],
                                      ("seconds", "intensity", "cue")).items():
                items = {r["condition"]: r for r in subset}
                left, right = items["normal"], items["reversed"]
                a = [o["text"] for o in left["outputs"]]
                b = [o["text"] for o in right["outputs"]]
                blank_a = [o["text"] for o in no_cue["normal", key[0]]["outputs"]][:len(a)]
                blank_b = [o["text"] for o in no_cue["reversed", key[0]]["outputs"]][:len(b)]
                target_a, target_b = left["target"] + "。", right["target"] + "。"
                comparisons.append(identity | {"seconds": key[0], "intensity": key[1], "cue": key[2],
                    "same_window_both_correct": sum(x == target_a and y == target_b for x, y in zip(a, b, strict=True)),
                    "same_window_both_correct_and_changed_from_no_cue": sum(
                        x == target_a and y == target_b and x != bx and y != by
                        for x, y, bx, by in zip(a, b, blank_a, blank_b, strict=True)),
                    "windows": len(a), "each_has_target_somewhere": target_a in a and target_b in b})
                details.append(identity | {"key": left["key"], "normal": a, "reversed": b,
                                           "normal_no_cue": blank_a, "reversed_no_cue": blank_b,
                                           "normal_target": target_a, "reversed_target": target_b})
            result.append(record)
    return {"summary": result, "paired": comparisons, "paired_outputs": details,
            "text_analysis_status": "descriptive fixed-window counts; visual recall remains registered primary"}


def graphs():
    bg = {int(c) for row in background().rows if row["stimulus"] for c, _ in row["stimulus"]["channels"]}
    output = []
    for source in sorted((WORK / "cases").glob("formal-*/definition.json")):
        definition = read_json(source)
        if "basis" not in definition:
            continue
        world = TeachingWorld(definition["seed"])
        visual = {c for i in range(4) for c, _ in world.frame(world.sample(i)).channels}
        known = set(definition["basis"]["channels"])
        if visual & bg:
            raise RuntimeError("unexpected visual/background channel overlap")

        def kind(channel, visual=visual, known=known):
            return "visual" if channel in visual else "background" if channel in bg else "language" if channel in known else "unknown"

        for seconds in (266, 326, 566):
            snapshot = source.parent / f"checkpoint-{seconds}" / "state.tmind"
            state = ArtifactCodec.decode(snapshot.read_bytes()).to_dict()
            node_kind = {int(n["id"]): kind(int(n["channel"])) for n in state["nodes"]}
            count, weight, active = Counter(), Counter(), Counter()
            for edge in state["edges"]:
                label = "/".join(sorted((node_kind[int(edge["source"])], node_kind[int(edge["target"])])))
                count[label] += 1
                weight[label] += edge["weight"]
            for node in state["nodes"]:
                active[node_kind[int(node["id"])]] += node["activation"]
            output.append({k: definition[k] for k in ("route", "seed", "condition")} | {
                "seconds": seconds, "edges": dict(count), "weights": dict(weight), "activation": dict(active),
                "life": state["life"], "nodes": len(state["nodes"])})
    return output


def continuous():
    output = []
    for meta in sorted((WORK / "continuous-text").glob("*.json")):
        value = read_json(meta)
        counts = defaultdict(Counter)
        active = defaultdict(lambda: Counter())
        with gzip.open(meta.with_suffix(".jsonl.gz"), "rt", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                start = int(row["start_us"]) / 1e6
                phase = "teaching" if row["acquisition"] else "interleaved_background" if start < 266 else "retention"
                counts[phase][row["output"]["text"]] += 1
                active[phase]["transmitted"] += row["transport"].get("sent", 0)
                active[phase]["positive_change"] += row["changes"]["positive_change"]
                active[phase]["reentries"] += row["changes"]["reentries"]
        output.append(value | {"texts": {k: dict(v) for k, v in counts.items()},
                               "activity": {k: dict(v) for k, v in active.items()}})
    return output


def sensory_dose():
    """Descriptive input-dose audit, not another fitted selection criterion."""
    result = []
    for seed in (11, 37, 53):
        path = WORK / "models" / f"input-{seed}.safetensors"
        spec = protocol(seed).model_copy(update={"input_checkpoint_sha256": read_json(path.with_suffix(".json"))["checkpoint_sha256"]})
        model = load_input(spec, "input", "cpu", path)[1]
        for route in ("text", "stream-sparse"):
            inp = Input(route, seed, model)
            for i, name in enumerate(TEST_NAMES):
                full = inp.frames(name + "是" + WORDS[i] + "。")
                lesson_channels = {c for f in full for c, _ in f["stimulus"].channels}
                for suffix in ("", "是"):
                    cue = inp.frames(name + suffix, .5)
                    cue_channels = {c for f in cue for c, _ in f["stimulus"].channels}
                    vector = Counter()
                    for frame in cue:
                        for channel, amount in frame["stimulus"].channels:
                            vector[channel] += amount * frame["stimulus"].intensity
                    similarities = {}
                    for other in TEST_NAMES:
                        if other == name:
                            continue
                        comparison = Counter()
                        for frame in inp.frames(other + suffix, .5):
                            for channel, amount in frame["stimulus"].channels:
                                comparison[channel] += amount * frame["stimulus"].intensity
                        denominator = np.linalg.norm(list(vector.values())) * np.linalg.norm(list(comparison.values()))
                        similarities[other + suffix] = sum(amount * comparison[channel] for channel, amount in vector.items()) / denominator
                    result.append({"route": route, "seed": seed, "cue": name + suffix,
                                   "lesson_language": input_summary(full), "cue_language": input_summary(cue),
                                   "lesson_visual_amount": 2.0 * len(full),
                                   "integrated_cue_cosines": similarities,
                                   "cue_channel_fraction_seen_in_lesson": len(cue_channels & lesson_channels) / len(cue_channels)})
    return result


def main():
    import torch
    torch.set_num_threads(2)
    target = HERE / "results.json"
    if target.exists():
        raise RuntimeError("keep published analyses immutable; choose an addendum filename")
    cache = WORK / "formal-visual-analysis.json"
    if cache.exists():
        measured = read_json(cache)
        observations, pairs, formal_count = measured["observations"], measured["pairs"], measured["formal_cases"]
        raw = [read_json(p) for p in (WORK / "cases").glob("formal-*-q-1-*/result.json")]
    else:
        raw, observations = rows("formal")
        pairs, formal_count = paired(observations), len(raw)
    visual = []
    for key, subset in sorted(groups(pairs, ("route", "seed", "seconds", "intensity")).items()):
        visual.append(dict(zip(("route", "seed", "seconds", "intensity"), key, strict=True)) |
                      fraction(subset, "joint_correct") | {"mean_margin": float(np.mean([r["mean_margin"] for r in subset]))})
    no_cue = []
    for row in raw:
        if row.get("kind") != "probe" or row["cue"] is not None:
            continue
        windows = row["windows"]
        no_cue.append({k: row[k] for k in ("key", "route", "seed", "seconds", "condition", "intervention", "life")} | {
            "observed_seconds": (int(windows[-1]["end_us"]) - int(windows[0]["start_us"])) / 1e6,
            "windows": len(windows),
            "transport": {key: sum(w["transport"].get(key, 0) for w in windows) for key in ("sent", "received", "activated", "discarded")},
            "positive_change": sum(w["changes"]["positive_change"] for w in windows),
            "reentries": sum(w["changes"]["reentries"] for w in windows),
        })
    weak = read_json(WORK / "weak-validation.json")
    validation = [dict(zip(("route", "seed", "variant", "intensity"), key, strict=True)) | fraction(values)
                  for key, values in sorted(groups(weak["results"], ("route", "seed", "variant", "intensity")).items())]
    all_cases = list((WORK / "cases").glob("*/result.json"))
    failures = [read_json(p) for p in (WORK / "interrupted-attempts").glob("*/failure.json")]
    compute = sum(read_json(path)["wall_seconds"] for path in all_cases) + sum(row["wall_seconds"] for row in failures)
    for folder in ("models", "decoded", "language-analysis", "continuous-text"):
        compute += sum(read_json(p).get("wall_seconds", 0) for p in (WORK / folder).glob("*.json")
                       if not p.name.endswith(".training.json"))
    compute += weak["wall_seconds"]
    compute += read_json(WORK / "bridge-expression.json")["wall_seconds"]
    data = {"schema": "E44-results/1", "completed_cases": len(all_cases), "interrupted_attempts": failures,
            "recorded_compute_seconds": compute, "formal_cases": formal_count,
            "visual_recall_summary": visual, "visual_recall_rows": observations, "visual_recall_pairs": pairs,
            "expression": expression(), "weak_validation": validation,
            "bridge_ablation": read_json(WORK / "bridge-results.json"),
            "bridge_expression": read_json(WORK / "bridge-expression.json"),
            "no_cue": no_cue, "graphs": graphs(), "continuous": continuous(),
            "sensory_dose": sensory_dose(),
            "limits": "Case/prompt/window counts are correlated, not independent participants. No Core dynamics changed."}
    new_json(target, data)
    print(json.dumps({"completed_cases": len(all_cases), "compute_minutes": round(compute / 60, 2),
                      "visual_joint": {str(key): fraction(value, "joint_correct") for key, value in groups(pairs, ("route", "seed")).items()},
                      "no_cue_branches": len(no_cue)}))


if __name__ == "__main__":
    main()
