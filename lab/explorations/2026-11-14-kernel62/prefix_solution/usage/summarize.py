"""Create a small report summary from audited artifacts; no simulation."""
import argparse
import json
from pathlib import Path


def summarize(work, destination):
    read = lambda p: json.loads(p.read_text(encoding="utf8"))
    a = read(work / "analysis-final.json")
    assert a["passed"] and read(work / "audit-final.json")["passed"]
    groups = []
    for g in a["groups"]:
        groups.append({
            "phase": g["phase"], "variant": g["variant"], "task": g["group"],
            "passed_blocks": g["passed_blocks"],
            "observations": [{
                "block": r["block"], "cue": r["cue"], "passed": r["passed"],
                **{k: r["process"][k] for k in
                   ("margin", "minimum", "maximum", "end", "complete", "saturation_fraction")},
            } for r in g["rows"]],
        })
    profiles = [{
        "name": g["name"], "prefix_pass": g["prefix_pass"],
        "persistence_pass": g["persistence_pass"], "patch": g["patch"],
    } for g in a["decision"]["groups"]]
    resources = a["resources"].values()
    usage = a["usage_selection"]["chosen"]
    summary = {
        "experiment": "R51t11", "date": "2026-11-15",
        "record": read(work / "registration.json")["record"],
        "material_blocks": 2, "production_core_changed": False,
        "stages": a["stages"], "verified_states": a["states"],
        "verified_processes": a["processes"],
        "max_arithmetic_error": a["max_arithmetic_error"],
        "science_stage_wall_seconds": a["wall_seconds"],
        "phase_host_wall_seconds": sum(read(p)["wall_seconds"] for p in work.glob("phase-*-summary.json")),
        "raw_bytes_at_final_audit": a["raw_bytes"],
        "peak_private_bytes": max(r["peak_private_bytes"] for r in resources),
        "minimum_available_bytes": {
            k: min(r["minimum_available_bytes"][k] for r in resources)
            for k in ("commit", "ram", "system_disk", "data_disk")
        },
        "prefix_candidate": usage or a["decision"]["selected"],
        "shared_profiles": profiles, "groups": groups,
        "inhibition_counter_note": "Separate inhibition routing omits the general inhibition-transmission counter; conclusions use node-process observations, not that counter.",
    }
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("groups", "prefix_candidate")}, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    summarize(args.work, args.output)
