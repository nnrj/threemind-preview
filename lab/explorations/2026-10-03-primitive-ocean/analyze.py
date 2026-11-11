"""Read-only E28 summaries and figures; independent unit is a shared world."""

import gzip
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cases import complete, segments
from experiment import HERE, WORK

from lab.tools.ocean_cli import read_json, write_json


def main():
    rows = []
    trajectories = {}
    populations = {}
    for path in sorted((WORK / "cases").glob("*/result.json")):
        root = path.parent
        parts = segments(root)
        result = read_json(complete(root) / "result.json")
        key = path.parent.name
        populations[key] = result["members"]
        row = {
            "case": key,
            "status": result["status"],
            "sim_seconds": result["time_us"] / 1e6,
            "wall_seconds": sum(read_json(part / "result.json")["wall_seconds"] for part in parts),
            "segments": len(parts),
            "individuals": len(result["members"]),
            "births": result["totals"]["births"],
            "predations": result["totals"]["predations"],
            "deferred_births": result["totals"]["deferred_births"],
            "alive": sum(m["life"] != "dead" for m in result["members"]),
            "physical": sum(m["physical"] for m in result["members"]),
            "grains": sum(m["grains"] for m in result["members"]),
            "energy_remaining": sum(
                m["storage"] + m["core_energy"]["reserve"] for m in result["members"] if m["life"] != "dead"
            ),
            "deaths": sum(m["life"] == "dead" for m in result["members"]),
            "starvation_deaths": sum(
                m["life"] == "dead" and m["core_energy"]["reserve"] == 0 and m["consumed_by"] is None
                for m in result["members"]
            ),
            "max_generation": max(m["generation"] for m in result["members"]),
            "energy_balance_error": result["energy_balance_error"],
            "radius_min": min(m["radius"] for m in result["members"]),
            "radius_max": max(m["radius"] for m in result["members"]),
            "surviving_radii": [m["radius"] for m in result["members"] if m["physical"]],
            "parents_with_offspring": sum(m["children"] > 0 for m in result["members"]),
            "energy_unserved": sum(m["core_energy"]["unserved_total"] for m in result["members"]),
            "storage_overflow": result["totals"]["storage_overflow"],
            "core_energy_spent": sum(
                m["core_energy"][k]
                for m in result["members"]
                for k in ("consumed_direct", "consumed_associative", "consumed_inhibition", "consumed_maintenance")
            ),
            "food_utilization": result["totals"]["food_consumed"] / result["totals"]["environment_food"]
            if result["totals"]["environment_food"]
            else 0,
        }
        rows.append(row)
        trajectories[key] = []
        for part in parts:
            with gzip.open(part / "trajectory.jsonl.gz", "rt", encoding="utf-8") as stream:
                trajectories[key].extend(json.loads(line) for line in stream)
    comparisons = []
    for group in range(3):
        by_key = {r["case"]: r for r in rows}
        learned, blank = (by_key.get(f"evaluation-{group}-{v}") for v in ("inherited", "blank"))
        if learned and blank:
            curves = [
                {v["time_us"]: v for v in trajectories[f"evaluation-{group}-{kind}"]} for kind in ("inherited", "blank")
            ]
            timecourse = []
            for t in sorted(curves[0].keys() & curves[1].keys()):
                members = [curve[t]["members"] for curve in curves]
                food = [sum(m["grains"] for m in group_members) for group_members in members]
                energy = [
                    sum(m["storage"] + m["core_energy"]["reserve"] for m in group_members if m["life"] != "dead")
                    for group_members in members
                ]
                timecourse.append(
                    {
                        "seconds": t / 1e6,
                        "grains_difference": food[0] - food[1],
                        "energy_difference": energy[0] - energy[1],
                    }
                )
            comparisons.append(
                {
                    "group": group,
                    "grains_difference": learned["grains"] - blank["grains"],
                    "energy_difference": learned["energy_remaining"] - blank["energy_remaining"],
                    "alive_difference": learned["alive"] - blank["alive"],
                    "inherited_food_utilization": learned["food_utilization"],
                    "blank_food_utilization": blank["food_utilization"],
                    "core_energy_spent_difference": learned["core_energy_spent"] - blank["core_energy_spent"],
                    "overflow_difference": learned["storage_overflow"] - blank["storage_overflow"],
                    "timecourse": timecourse,
                }
            )
    summary = {
        "worlds": rows,
        "evaluation_pairs": comparisons,
        "individuals": sum(r["individuals"] for r in rows),
        "wall_seconds": sum(r["wall_seconds"] for r in rows),
        "new_local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
    }
    output = WORK / "analysis/summary.json"
    write_json(output, summary)
    figures = HERE / "figures"
    figures.mkdir(exist_ok=True)
    fig, axes = plt.subplots(2, 3, figsize=(12, 6), sharex=True)
    colors = {"core": "#087f75", "passive": "#84938c", "random": "#b8752e"}
    for group in range(3):
        for mode, color in colors.items():
            key = f"phase1-{group}-{mode}"
            if key not in trajectories:
                continue
            values = trajectories[key]
            t = [v["time_us"] / 1e6 for v in values]
            axes[0, group].plot(t, [sum(m["physical"] for m in v["members"]) for v in values], color=color, label=mode)
            axes[1, group].plot(t, [sum(m["grains"] for m in v["members"]) for v in values], color=color)
        axes[0, group].set_title(f"Independent world {group + 1}")
        axes[1, group].set_xlabel("Simulated seconds")
    axes[0, 0].set_ylabel("Living bodies")
    axes[1, 0].set_ylabel("Nutrients consumed")
    axes[0, 0].legend()
    fig.suptitle("E28 | Contact feeding and bounded population dynamics")
    fig.tight_layout()
    fig.savefig(figures / "population.png", dpi=155)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(12, 6))
    by_key = {r["case"]: r for r in rows}
    for group in range(3):
        values = populations.get(f"phase2-{group}", [])
        for living, color, marker in ((True, "#087f75", "o"), (False, "#88918d", "x")):
            members = [m for m in values if m["physical"] == living]
            axes[0, group].scatter(
                [m["radius"] * 1000 for m in members],
                [m["grains"] for m in members],
                color=color,
                marker=marker,
                label="living body" if living else "lost body",
            )
        axes[0, group].set_title(f"Mutation world {group + 1}")
        axes[0, group].set_xlabel("Body radius (mm)")
        pair = [by_key.get(f"evaluation-{group}-{v}") for v in ("inherited", "blank")]
        if all(pair):
            axes[1, group].bar(
                ["inherited", "experience erased"], [r["grains"] for r in pair], color=["#087f75", "#b8752e"]
            )
        axes[1, group].set_title(f"Common environment {group + 1}")
    axes[0, 0].set_ylabel("Lifetime nutrients consumed")
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].set_ylabel("Nutrients consumed in 300 seconds")
    fig.suptitle("E28 | Body differences and inherited-network controls")
    fig.tight_layout()
    fig.savefig(figures / "selection.png", dpi=155)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(12, 6), sharex=True)
    for pair in comparisons:
        group, series = pair["group"], pair["timecourse"]
        for row, key in enumerate(("grains_difference", "energy_difference")):
            axes[row, group].plot([v["seconds"] for v in series], [v[key] for v in series], color="#087f75")
            axes[row, group].axhline(0, color="#8b9691", linewidth=0.8)
        axes[0, group].set_title(f"Paired environment {group + 1}")
        axes[1, group].set_xlabel("Simulated seconds")
    axes[0, 0].set_ylabel("Nutrients: inherited minus erased")
    axes[1, 0].set_ylabel("Energy: inherited minus erased")
    fig.suptitle("E28 | Full response course (secondary analysis)")
    fig.tight_layout()
    fig.savefig(figures / "comparison.png", dpi=155)
    plt.close(fig)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
