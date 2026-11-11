"""Reproducible external parent selection with independent newborn evaluations."""

import argparse
import gzip
import hashlib
import json
import random

from common import HERE, WORK, Study, load_case, new_json
from world import SEEDS, STARTS, Body, run_world

EVAL_STARTS = (0.0625, 0.5625)
HELD_STARTS = (0.1875, 0.4375, 0.6875, 0.9375)
ARMS = ("region0", "region1", "random")


def freeze(path, value):
    if path.exists():
        if json.loads(path.read_bytes()) != json.loads(json.dumps(value)):
            raise RuntimeError("registered selection differs; do not overwrite decisions")
    else:
        new_json(path, value)


def evaluate(study, candidates, prefix):
    scores = []
    for i, parent in enumerate(candidates):
        copies = [
            run_world(study, f"{prefix}/c{i}/eval{j}", parent["seed"], position, parent=parent)
            for j, position in enumerate(EVAL_STARTS)
        ]
        scores.append(sum(r["extra"]["region1_fraction"] for r in copies) / len(copies))
    return scores


def select(seed, generation, arm, scores):
    if arm == "random":
        return random.Random(seed + generation).sample(range(len(scores)), 2)
    return sorted(range(len(scores)), key=lambda i: (scores[i] if arm == "region0" else -scores[i], i))[:2]


def playback(result):
    return json.loads(gzip.decompress((WORK / "cases" / result["key"] / "world.json.gz").read_bytes()))


def run(study):
    if not json.loads((WORK / "world-preflight.json").read_bytes())["may_proceed"]:
        raise RuntimeError("world integration did not pass")
    freeze(
        WORK / "selection-registration.json",
        {
            "seeds": SEEDS,
            "arms": ARMS,
            "evaluation_starts": EVAL_STARTS,
            "held_out_starts": HELD_STARTS,
            "generations": 3,
            "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("selection.*")},
        },
    )
    champions, decisions, final = [], [], []
    for seed in SEEDS:
        initial = [load_case(study, f"world/s{seed}/g0/c{i}") for i in range(4)]
        initial_scores = evaluate(study, initial, f"selection/s{seed}/g0")
        for arm in ARMS:
            candidates, scores = initial, initial_scores
            for generation in (1, 2):
                chosen = select(seed, generation - 1, arm, scores)
                decision = {
                    "seed": seed,
                    "arm": arm,
                    "generation": generation,
                    "candidates": [r["id"] for r in candidates],
                    "scores": scores,
                    "selected_indices": chosen,
                }
                freeze(WORK / f"decisions/s{seed}/{arm}/g{generation}.json", decision)
                decisions.append(decision)
                parents = [candidates[i] for i in chosen]
                prefix = f"selection/s{seed}/{arm}/g{generation}"
                candidates = [
                    run_world(
                        study, f"{prefix}/c{i}/experience", seed, STARTS[(i + generation) % 4], parent=parents[i // 2]
                    )
                    for i in range(4)
                ]
                scores = evaluate(study, candidates, prefix)
                study.guard(force=True)
                print(json.dumps({"seed": seed, "arm": arm, "generation": generation, "scores": scores}), flush=True)
            index = select(seed, 2, arm, scores)[0]
            parent = candidates[index]
            champ = {
                "seed": seed,
                "arm": arm,
                "index": index,
                "key": parent["key"],
                "id": parent["id"],
                "scores": scores,
            }
            freeze(WORK / f"decisions/s{seed}/{arm}/champion.json", champ)
            champions.append(champ)
            held = {}
            for i, position in enumerate(HELD_STARTS):
                for swapped in (0, 1):
                    r = run_world(
                        study,
                        f"selection/s{seed}/{arm}/final/p{i}/swap{swapped}",
                        seed,
                        position,
                        parent=parent,
                        phase=swapped * 0.5,
                    )
                    held[i, swapped] = r
                    final.append(
                        {
                            "seed": seed,
                            "arm": arm,
                            "i": i,
                            "swapped": swapped,
                            "key": r["key"],
                            "id": r["id"],
                            "extra": r["extra"],
                        }
                    )
            for i in (0, 2):
                recording = playback(held[i, 0])
                for control in ("sensory-replay", "motor-replay", "reversal"):
                    run_world(
                        study,
                        f"selection/s{seed}/{arm}/controls/p{i}/{control}",
                        seed,
                        HELD_STARTS[i],
                        parent=parent,
                        controller="closed" if control == "reversal" else control,
                        playback=recording,
                        phase=0.5 if control == "motor-replay" else 0,
                        reversal_s=30 if control == "reversal" else None,
                    )
    baselines = []
    for i, position in enumerate(HELD_STARTS):
        for phase in (0, 0.5):
            for control in (-0.5, 0, 0.5):
                body = Body(position, phase=phase)
                regions = []
                for _ in range(600):
                    regions.append(body.region)
                    body.move(control, 0.1)
                baselines.append({"i": i, "phase": phase, "control": control, "region1_fraction": sum(regions) / 600})
    freeze(
        WORK / "selection-results.json",
        {"champions": champions, "decisions": decisions, "held_out": final, "physical_baselines": baselines},
    )


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    study = Study()
    try:
        run(study)
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({"budget_stop": True, "error": str(exc)})
        raise
    finally:
        study.db.close()
