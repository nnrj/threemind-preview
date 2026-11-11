"""Separately registered, bounded mechanism localization."""

import argparse
import itertools
import json

from experiment import HERE, identities, parent, probe, settings, training

from lab.tools.service_study import Study, load_case, new_json

SEEDS = (930401, 930411)


def registered(study):
    for language in ("zh", "en"):
        text = (HERE / f"extension.{language}.md").read_text(encoding="utf-8")
        study.note(f"extension:{language}", f"追加机制定位 / Mechanism extension {language}", text)


def register_phase(study):
    for language in ("zh", "en"):
        text = (HERE / f"phase-extension.{language}.md").read_text(encoding="utf-8")
        study.note(f"phase-extension:{language}", f"易化形成与表达 / Facilitation phases {language}", text)


def phases(study, seeds):
    for seed, f, history, delay, cue in itertools.product(seeds, (0, 1), ("single4", "repeat"), (1, 30), (0.0, 0.5)):
        p = main_parent(study, seed, f, history)
        probe(
            study,
            p,
            delay,
            cue,
            suffix=f"-facilitation-switch-{1 - f}",
            expression_patch={"stp_facilitation_tau_s": float(1 - f)},
        )
    print(json.dumps({"phases": list(seeds), "cases": study.completed_count}), flush=True)


def main_parent(study, seed, f, history):
    return load_case(study, f"matrix/{seed}/i0f{f}l1/{history}/train")


def formation(study, seeds):
    patches = {
        "ordinary-off": {"first_gain": 0.0, "repeat_gain": 0.0},
        "novelty-off": {"local_novelty_gain": 0.0},
        "birth-weight-off": {"birth_weight": 0.0},
        "ordinary-and-birth-off": {"first_gain": 0.0, "repeat_gain": 0.0, "birth_weight": 0.0},
    }
    for seed in seeds:
        p = parent(study, seed)
        for name, patch in patches.items():
            factors = [(0, 0, 0)] + ([(0, 1, 1)] if name in ("ordinary-off", "birth-weight-off") else [])
            for factor, history in itertools.product(factors, ("single1", "single4")):
                row = training(study, p, factor, history, prefix=f"formation/{name}", patch=patch)
                for cue in (0.0, 0.5):
                    probe(study, row, 30, cue)
        print(json.dumps({"formation": seed, "cases": study.completed_count}), flush=True)


def facilitation(study, seeds):
    for seed in seeds:
        p = parent(study, seed)
        for tau, history in itertools.product((0.1, 0.3, 3.0), ("single1", "single4", "repeat")):
            row = training(
                study, p, (0, 1, 1), history, prefix=f"facilitation/tau{tau}", patch={"stp_facilitation_tau_s": tau}
            )
            for delay, cue in itertools.product((1, 30), (0.0, 0.5)):
                probe(study, row, delay, cue)
        print(json.dumps({"facilitation": seed, "cases": study.completed_count}), flush=True)


def sensitivity(study, seeds):
    for seed in seeds:
        for f, history in itertools.product((0, 1), ("none", "single1", "single4", "repeat")):
            p = main_parent(study, seed, f, history)
            for delay, cue in itertools.product((1, 30), (0.2, 1.0, 2.0)):
                probe(study, p, delay, cue)
        print(json.dumps({"sensitivity": seed, "cases": study.completed_count}), flush=True)


def expression(study, seeds):
    patches = {
        "depletion-off": {"depletion_enabled": False},
        "inhibition-response-off": {"inhibition_response_gain": 0.0},
        "fast-off": {"fast_enabled": False},
        "context-off": {"context_enabled": False},
        "consolidation-off": {"edge_consolidation_enabled": False},
    }
    for seed in seeds:
        p = main_parent(study, seed, 0, "single4")
        for (name, patch), delay, cue in itertools.product(patches.items(), (1, 30), (0.0, 0.5)):
            probe(study, p, delay, cue, suffix=f"-expression-{name}", expression_patch=patch)
        state = p["image"].to_dict()
        nodes = {n["channel"]: n["id"] for n in state["nodes"]}
        ids = identities(seed)
        chosen = (nodes[ids["A"]], nodes[ids["B"]])
        edges = {(e["source"], e["target"]): e for e in state["edges"]}
        target = edges[chosen]
        other = min(
            (key for key in edges if key != chosen and key[0] != chosen[0]),
            key=lambda key: (
                abs(edges[key]["weight"] - target["weight"]) + abs(edges[key]["stability"] - target["stability"])
            ),
        )
        for name in ("silence", "restore", "matched"):
            applied = other if name == "matched" else chosen
            interventions = [{"edges": [applied], "action": "silence"}]
            if name == "restore":
                interventions.append({"edges": [applied], "action": "unsilence"})
            for cue in (0.0, 0.5):
                probe(study, p, 30, cue, suffix=f"-connection-{name}", interventions=interventions)
        new_json(
            study.work / f"matching-{seed}.json",
            {
                "target": chosen,
                "other": other,
                "target_at_training": target,
                "other_at_training": edges[other],
                "selection_time": "training end, before waiting/probe results",
            },
        )
        print(json.dumps({"expression": seed, "cases": study.completed_count}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        choices=("register", "register-phase", "formation", "facilitation", "sensitivity", "expression", "phases"),
    )
    parser.add_argument("--block", type=int, choices=SEEDS, action="append")
    args = parser.parse_args()
    study = Study(settings())
    try:
        if args.stage == "register":
            registered(study)
        elif args.stage == "register-phase":
            register_phase(study)
        else:
            study.allow_extension()
            {
                "formation": formation,
                "facilitation": facilitation,
                "sensitivity": sensitivity,
                "expression": expression,
                "phases": phases,
            }[args.stage](study, args.block or SEEDS)
    except Exception as error:
        if study.active_case and not (study.active_case.folder / "result.json").exists():
            study.active_case.finish({"failure": repr(error), "budget_stop": True})
        raise
    finally:
        study.db.close()
