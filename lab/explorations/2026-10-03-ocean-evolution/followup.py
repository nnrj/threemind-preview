"""Conditional independent confirmation and source-preserving attribution.

No supplementary simulation can run before its prospective registration and the
original primary gate. All results, including unfavorable ones, are retained.
"""

import argparse
import hashlib
import json

from experiment import HERE, WORK, execute, latest, protocol, study

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_evolution import EvolutionOcean
from lab.tools.ocean_evolution_cli import load_population
from lab.tools.ocean_interventions import make_control

CASES = ["confirm-3-core", "confirm-3-random"] + [
    f"control-0-{operation}" for operation in ("inherited", "naive", "sham", "silence")
]


def register():
    s = study()
    try:
        s.allow_extension()
        summary = read_json(WORK / "analysis/summary.json")
        if not summary["confirmation_gate"] or summary["incomplete"] or summary["unexecuted"]:
            raise ValueError("complete registered primary/ecological batch and original confirmation gate first")
        source = latest(WORK / "cases/phase1-0-core") / "final"
        registration = {
            "schema": "e29-followup/1",
            "source": source.relative_to(WORK).as_posix(),
            "source_manifest_sha256": hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest(),
            "confirmation_group": 3,
            "confirmation_duration_us": 1800000000,
            "control_duration_us": 300000000,
            "common_environment_seed": 294101,
            "cases": CASES,
            "primary_gate_passed": True,
            "control_tool_sha256": hashlib.sha256(
                (HERE.parents[1] / "tools/ocean_interventions.py").read_bytes()
            ).hexdigest(),
        }
        for lang in ("zh", "en"):
            p = HERE / f"followup-design.{lang}.md"
            s.note(
                "followup:design:" + lang,
                "E29 条件性确认与归因 / Conditional confirmation " + lang,
                p.read_text(encoding="utf-8"),
            )
        write_json(WORK / "followup-registration.json", registration)
        print(json.dumps(registration))
    finally:
        s.db.close()


def case(key):
    reg = read_json(WORK / "followup-registration.json")
    if key not in reg["cases"]:
        raise ValueError("unregistered supplementary case")
    tool = HERE.parents[1] / "tools/ocean_interventions.py"
    if hashlib.sha256(tool.read_bytes()).hexdigest() != reg["control_tool_sha256"]:
        raise ValueError("registered control implementation changed")
    source = WORK / reg["source"]
    if hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest() != reg["source_manifest_sha256"]:
        raise ValueError("source snapshot changed")
    s = study()
    try:
        s.allow_extension()
    finally:
        s.db.close()
    is_confirm = key.startswith("confirm-")
    if not is_confirm:
        decision = read_json(WORK / "followup-confirmation-decision.json")
        if not decision["passed"]:
            raise ValueError("independent confirmation did not pass; attribution was conditional")
    root = WORK / "cases" / key
    duration = reg["confirmation_duration_us"] if is_confirm else reg["control_duration_us"]
    if root.exists():
        old = latest(root)
        r = read_json(old / "result.json")
        target = read_json(root / "initial/manifest.json")["context"]["time_us"] + duration
        if r["status"] == "extinct" or (r["status"] == "horizon_paused" and r["time_us"] == target):
            return
        world = load_population(old / "final")
        output = old / "continuations/01"
        if output.exists():
            raise RuntimeError("unlinked continuation exists; inspect rather than overwrite")
        execute(key, world, target - world.time_us, output=output)
        write_json(
            old / "completion.json", {"segment": "continuations/01", "reason": "saved supplementary continuation"}
        )
        return
    receipt = {"schema": "e29-independent-confirmation/1"}
    if is_confirm:
        world = EvolutionOcean(protocol(reg["confirmation_group"], key.rsplit("-", 1)[1]))
    else:
        operation = key.rsplit("-", 1)[1]
        world, receipt = make_control(
            load_population(source),
            operation,
            environment_seed=reg["common_environment_seed"] if operation in ("inherited", "naive") else None,
        )
        receipt |= {"source": reg["source"], "source_manifest_sha256": reg["source_manifest_sha256"]}
    answer = execute(key, world, duration)
    write_json(root / "control-receipt.json", receipt)
    if answer["status"] not in ("horizon_paused", "extinct"):
        raise RuntimeError("supplementary world paused; resume its saved state")


def decision():
    from analyze import analyze_case

    rows = [analyze_case(WORK / "cases" / f"confirm-3-{mode}")[0] for mode in ("core", "random")]
    complete = all(
        row["status"] == "extinct" or (row["status"] == "horizon_paused" and row["duration_s"] == 1800) for row in rows
    )
    if not complete:
        raise RuntimeError("independent confirmation unfinished")
    a, b = rows
    result = {
        "passed": a["food"] > b["food"] and a["living_body_s"] >= b["living_body_s"],
        "food_difference": a["food"] - b["food"],
        "living_body_s_difference": a["living_body_s"] - b["living_body_s"],
        "worlds": rows,
        "meaning": "one additional independent 1800-second pair; not a new statistical significance threshold",
    }
    write_json(WORK / "followup-confirmation-decision.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "worlds"}))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("register", "case", "decision"))
    p.add_argument("--case", choices=CASES)
    args = p.parse_args()
    if args.command == "case":
        if not args.case:
            p.error("--case is required")
        case(args.case)
    elif args.command == "register":
        register()
    else:
        decision()
