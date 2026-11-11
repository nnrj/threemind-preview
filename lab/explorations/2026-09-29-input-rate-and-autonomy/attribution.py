"""Separate inherited closed-loop preference from inter-node communication."""

import hashlib
import json

from common import HERE, WORK, Study, load_case, new_json
from selection import HELD_STARTS
from world import run_world

CONDITIONS = {
    "communication_off": {"propagation_rate": 0, "inhibition_diffusion_rate": 0},
    "consolidation_off": {"edge_consolidation_enabled": False},
}


def run(study):
    if not (WORK / "attribution-registration.json").exists():
        new_json(
            WORK / "attribution-registration.json",
            {
                "seed": 9293202,
                "conditions": CONDITIONS,
                "files": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [
                        HERE / "attribution.py",
                        HERE / "attribution.zh.md",
                        HERE / "attribution.en.md",
                        HERE / "world.py",
                    ]
                },
            },
        )
    original = json.loads((WORK / "selection-results.json").read_bytes())
    rows = []
    for champ in original["champions"]:
        if champ["seed"] != 9293202 or champ["arm"] == "random":
            continue
        parent = load_case(study, champ["key"])
        for condition, config in CONDITIONS.items():
            for i, position in enumerate(HELD_STARTS):
                for swapped in (0, 1):
                    result = run_world(
                        study,
                        f"attribution/{champ['arm']}/{condition}/p{i}/swap{swapped}",
                        champ["seed"],
                        position,
                        parent=parent,
                        phase=swapped * 0.5,
                        config_override=config,
                    )
                    rows.append(
                        {
                            "id": result["id"],
                            "key": result["key"],
                            "arm": champ["arm"],
                            "condition": condition,
                            "i": i,
                            "swapped": swapped,
                            "extra": result["extra"],
                        }
                    )
            print(json.dumps({"arm": champ["arm"], "condition": condition, "complete": True}), flush=True)
    new_json(WORK / "attribution-results.json", rows)


if __name__ == "__main__":
    study = Study()
    try:
        run(study)
    except Exception as exc:
        if study.active_case:
            study.active_case.finish({"budget_stop": True, "error": str(exc)})
        raise
    finally:
        study.db.close()
