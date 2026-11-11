"""Read all preregistered worlds; no selection of favorable times or individuals."""

import gzip
import json
import re
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from experiment import HERE, WORK

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_exchange_summary import summarize as exchange_summary
from lab.tools.ocean_input_summary import summarize as input_summary
from lab.tools.ocean_view import recorded_segments


def core_spent(m):
    return sum(
        m["core_energy"][k]
        for k in ("consumed_direct", "consumed_associative", "consumed_inhibition", "consumed_maintenance")
    )


def analyze_case(root):
    parts = recorded_segments(root)
    result = read_json(parts[-1] / "result.json")
    initial = read_json(root / "initial/manifest.json")["context"]
    start, end = initial["time_us"], result["time_us"]
    prior = {x["id"]: x for x in initial["bodies"]}
    events = [e for part in parts for e in read_json(part / "events.json")]
    lost = {}
    for e in events:
        if e["kind"] in ("body_engulfed", "body_age_limit", "consciousness_dead"):
            lost.setdefault(e["individual"], e["time_us"])
    living_seconds = 0.0
    for m in result["members"]:
        if m["id"] in prior and not prior[m["id"]]["physical"]:
            continue
        living_seconds += max(0, min(end, lost.get(m["id"], end)) - max(start, m["birth_us"])) / 1e6
    food = sum(x["grains"] - prior.get(x["id"], {}).get("grains", 0) for x in result["members"])
    delta = {k: result["totals"][k] - initial["totals"].get(k, 0) for k in result["totals"]}
    body_delta = {
        k: sum(m[k] - prior.get(m["id"], {}).get(k, 0) for m in result["members"])
        for k in (
            "path_m",
            "motor_energy",
            "body_maintenance",
            "body_unserved",
            "exhausted_motor_steps",
            "share_sent",
            "share_received",
            "mechanical_work_j",
        )
    }
    timeline = []
    for part in parts:
        with gzip.open(part / "trajectory.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                timeline.append(
                    {
                        "seconds": (r["time_us"] - start) / 1e6,
                        "living": sum(m["physical"] for m in r["members"]),
                        "food": sum(m["grains"] - prior.get(m["id"], {}).get("grains", 0) for m in r["members"]),
                        "available_food": r["nutrient_count"],
                        "energy": sum(
                            m["core_energy"]["reserve"] + m["storage"] for m in r["members"] if m["physical"]
                        ),
                        "body_cost": r["totals"]["body_heat"] - initial["totals"]["body_heat"],
                    }
                )
    timeline.append(
        {
            "seconds": (end - start) / 1e6,
            "living": sum(m["physical"] for m in result["members"]),
            "food": food,
            "available_food": result["nutrient_count"],
            "energy": sum(m["core_energy"]["reserve"] + m["storage"] for m in result["members"] if m["physical"]),
            "body_cost": delta["body_heat"],
        }
    )
    # Initial Core accounting is read from its saved images, not inferred from final reserves.
    from lab.tools.ocean_evolution_cli import load_population

    old = load_population(root / "initial")
    old_cost = sum(core_spent({"core_energy": e.metrics()["energy"]}) for e in old.engines.values())
    row = {
        "case": root.name,
        "status": result["status"],
        "error": result["error"],
        "duration_s": (end - start) / 1e6,
        "initial_s": start / 1e6,
        "wall_seconds": sum(read_json(p / "result.json")["wall_seconds"] for p in parts),
        "retained_states": len(result["members"]),
        "active_copies_and_births": sum(b["physical"] for b in initial["bodies"]) + delta["births"],
        "food": food,
        "food_per_body_s": food / living_seconds if living_seconds else 0,
        "living_body_s": living_seconds,
        "physical_survivors": sum(m["physical"] for m in result["members"]),
        "core_survivors": sum(m["life"] != "dead" for m in result["members"]),
        "living_energy": timeline[-1]["energy"],
        "core_cost": sum(core_spent(m) for m in result["members"]) - old_cost,
        "totals_delta": delta,
        "body_delta": body_delta,
        "input_summary": input_summary(root),
        "exchange_summary": exchange_summary(root),
        "energy_balance_error": result["energy_balance_error"],
        "generation_max": max(m["generation"] for m in result["members"]),
        "food_left": result["nutrient_count"],
        "traits": [
            {
                "id": m["id"],
                "parent": m["parent"],
                "alive": m["physical"],
                "generation": m["generation"],
                "radius": m["radius"],
                "thrust": m["thrust"],
                "sensor_range": m["sensor_range"],
                "shell": m["shell"],
                "reflectance": m["reflectance"],
                "grains": m["grains"],
                "ligand": m["ligand"],
                "neutral_allele": m["neutral_allele"],
            }
            for m in result["members"]
        ],
    }
    return row, timeline


def main():
    rows = []
    courses = {}
    for p in sorted((WORK / "cases").glob("*/result.json")):
        if not re.fullmatch(
            r"phase1-[012]-(core|random)|fork-[01]-(ecology|recombination|transfer|sharing)", p.parent.name
        ):
            continue  # Independently registered follow-ups are analyzed separately.
        row, courses[p.parent.name] = analyze_case(p.parent)
        rows.append(row)
    lookup = {r["case"]: r for r in rows}
    pairs = []
    for g in range(3):
        a, b = lookup.get(f"phase1-{g}-core"), lookup.get(f"phase1-{g}-random")
        if not (a and b):
            continue
        pairs.append(
            {
                "group": g,
                "both_complete": all(
                    r["status"] == "extinct" or (r["status"] == "horizon_paused" and r["duration_s"] == 1800)
                    for r in (a, b)
                ),
                "food_difference": a["food"] - b["food"],
                "food_relative": (a["food"] - b["food"]) / b["food"] if b["food"] else None,
                "living_body_s_difference": a["living_body_s"] - b["living_body_s"],
                "survivor_difference": a["physical_survivors"] - b["physical_survivors"],
                "birth_difference": a["totals_delta"]["births"] - b["totals_delta"]["births"],
                "core_cost_difference": a["core_cost"] - b["core_cost"],
                "body_cost_difference": a["totals_delta"]["body_heat"] - b["totals_delta"]["body_heat"],
            }
        )
    gate = (
        len(pairs) == 3
        and all(
            p["both_complete"]
            and p["food_relative"] is not None
            and p["food_difference"] > 0
            and p["living_body_s_difference"] >= 0
            for p in pairs
        )
        and statistics.median(p["food_relative"] for p in pairs) >= 0.1
    )
    ecological = []
    for g in (0, 1):
        base = lookup.get(f"fork-{g}-ecology")
        if not base:
            continue
        for variant in ("recombination", "transfer", "sharing"):
            other = lookup.get(f"fork-{g}-{variant}")
            if not other:
                continue
            left = read_json(recorded_segments(WORK / "cases" / base["case"])[-1] / "final/manifest.json")["context"]
            right = read_json(recorded_segments(WORK / "cases" / other["case"])[-1] / "final/manifest.json")["context"]
            ecological.append(
                {
                    "group": g,
                    "variant": variant,
                    "different_final_fields_except_protocol": [
                        k for k in left if k != "protocol" and left[k] != right[k]
                    ],
                    **{k: other[k] - base[k] for k in ("food", "living_body_s", "physical_survivors", "living_energy")},
                    "births": other["totals_delta"]["births"] - base["totals_delta"]["births"],
                    "events": {
                        k: other["totals_delta"][k]
                        for k in ("recombinations", "horizontal_transfers", "sharing_contacts", "predations")
                    },
                }
            )
    planned = [f"phase1-{g}-{m}" for g in range(3) for m in ("core", "random")] + [
        f"fork-{g}-{m}" for g in (0, 1) for m in ("ecology", "recombination", "transfer", "sharing")
    ]
    summary = {
        "worlds": rows,
        "primary_pairs": pairs,
        "confirmation_gate": bool(gate),
        "ecological_pairs": ecological,
        "unexecuted": [k for k in planned if k not in lookup],
        "incomplete": [
            r["case"]
            for r in rows
            if r["status"] != "extinct"
            and (
                r["status"] != "horizon_paused" or r["duration_s"] != (1800 if r["case"].startswith("phase1-") else 900)
            )
        ],
        "wall_seconds": sum(r["wall_seconds"] for r in rows),
        "active_copies_and_births": sum(r["active_copies_and_births"] for r in rows),
        "unit": "three independent primary world pairs; two paired ecological source worlds, not independent offspring",
    }
    write_json(WORK / "analysis/summary.json", summary)
    write_json(WORK / "analysis/courses.json", courses)
    figdir = HERE / "figures"
    figdir.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(3, 3, figsize=(14, 10), layout="constrained")
    for g in range(3):
        for mode, color in [("core", "#147f70"), ("random", "#bb782f")]:
            c = courses.get(f"phase1-{g}-{mode}", [])
            for j, key in enumerate(("living", "food", "available_food")):
                axes[j, g].plot([x["seconds"] for x in c], [x[key] for x in c], label=mode, color=color)
        axes[0, g].set_title(f"Independent world pair {g + 1}")
        axes[0, g].legend()
        axes[2, g].set_xlabel("Simulated seconds")
    for ax, label in zip(axes[:, 0], ("Living bodies", "Nutrients eaten", "Nutrients left"), strict=True):
        ax.set_ylabel(label)
    fig.suptitle("E29 | Sparse ocean with charged body energy")
    fig.savefig(figdir / "primary.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained")
    for g in (0, 1):
        for variant in ("ecology", "recombination", "transfer", "sharing"):
            c = courses.get(f"fork-{g}-{variant}", [])
            axes[0, g].plot([x["seconds"] for x in c], [x["living"] for x in c], label=variant)
            axes[1, g].plot([x["seconds"] for x in c], [x["food"] for x in c], label=variant)
        axes[0, g].set_title(f"Paired source world {g + 1}")
        axes[0, g].legend()
        axes[1, g].set_xlabel("Seconds since saved fork")
    axes[0, 0].set_ylabel("Living bodies")
    axes[1, 0].set_ylabel("Additional food eaten")
    fig.suptitle("E29 | Separate ecological allowances")
    fig.savefig(figdir / "ecology.png", dpi=150)
    plt.close(fig)
    print(
        json.dumps(
            {"worlds": len(rows), "pairs": pairs, "confirmation_gate": bool(gate), "unexecuted": summary["unexecuted"]},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
