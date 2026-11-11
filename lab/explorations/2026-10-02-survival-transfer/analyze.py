"""Read-only E27 analysis; no simulation, threshold tuning or data replacement."""

import argparse
import collections
import gzip
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / ".work/survival-transfer-20261002"


def read(path):
    return json.loads(path.read_bytes())


def case(folder):
    result = read(folder / "result.json")
    trajectory = read(folder / "trajectory.json")
    m, events = result["metrics"], collections.Counter(e["kind"] for e in result["events"])
    energy = m["core"]["energy"]
    spent = {
        k: energy[k] for k in ("consumed_direct", "consumed_associative", "consumed_inhibition", "consumed_maintenance")
    }
    ledger_error = energy["initial_total"] + energy["supplied_total"] - energy["reserve"] - sum(spent.values())
    assert abs(ledger_error) < 0.001, (folder.name, ledger_error)
    assert energy["offered_total"] == m["offered"]
    assert events["qualified_transfer"] == m["transferred"]
    assert m["offered"] + m["pending_food"] == m["transferred"] * 10100
    if result["status"] == "starved":
        assert m["core"]["life"] == "dead" and energy["reserve"] == 0
        assert energy["starved_since_us"] is not None and energy["death_us"] is not None
    late, actions, action_count, clipping, frame_count, max_channels = [], np.zeros(8), 0, 0, 0, 0
    last_time, food_count = 0, 0
    with gzip.open(folder / "events.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            assert row["time_us"] == last_time + 20000
            last_time = row["time_us"]
            values = np.asarray(row["action"])
            assert len(values) == 8 and np.isfinite(values).all() and np.max(np.abs(values)) <= 1
            actions += np.abs(values)
            action_count += 8
            clipping += int((np.abs(values) > 0.95).sum())
            frame_count += 1
            max_channels = max(max_channels, len(row["stimulus"]["channels"]))
            food_count += row["food"] is not None
            if row["time_us"] >= m["time_us"] - 30000000:
                late.append(row["physical"]["physical"][:9])
    assert last_time == m["time_us"]
    assert food_count == 0 or m["offered"] > 0
    live = [r for r in trajectory if r["core"]["life"] == "active"]
    return {
        "key": result["key"],
        "attached": result["attached"],
        "status": result["status"],
        "life_seconds": m["time_us"] / 1e6,
        "death_core_seconds": int(energy["death_us"]) / 1e6 if energy["death_us"] else None,
        "empty_seconds": int(energy["starved_since_us"]) / 1e6 if energy["starved_since_us"] else None,
        "transferred": m["transferred"],
        "physical_grasps": events["physical_grasp"],
        "physical_lifts": events["physical_lift"],
        "spilled": m["spilled"],
        "energy_supplied": energy["supplied_total"],
        "energy_offered": m["offered"],
        "remaining_energy": energy["reserve"],
        "spent": spent,
        "ledger_error": ledger_error,
        "density_at_1s": trajectory[0]["core"]["edge_density"],
        "nodes_at_1s": trajectory[0]["core"]["nodes"],
        "edges_at_1s": trajectory[0]["core"]["edges"],
        "density_live_mean": float(np.mean([r["core"]["edge_density"] for r in live])),
        "late_joint_std": np.std(late, axis=0).tolist(),
        "mean_abs_action": (actions / frame_count).tolist(),
        "action_abs_above_095_fraction": clipping / action_count,
        "peak_contact_n": m["peak_contact_n"],
        "mechanical_work_j": m["mechanical_work_j"],
        "frames": frame_count,
        "maximum_channels_per_frame": max_channels,
        "wall_seconds": result["wall_seconds"],
        "error": result["error"],
        "initial_hash": result["initial_hash"],
        "final_hash": result["final_hash"],
        "runner_signature": result["runner_signature"],
    }, trajectory


def describe(rows):
    durations = [r["life_seconds"] for r in rows]
    return {
        "count": len(rows),
        "statuses": dict(collections.Counter(r["status"] for r in rows)),
        "duration_seconds_min_mean_max": [min(durations), float(np.mean(durations)), max(durations)],
        "transferred": sum(r["transferred"] for r in rows),
        "individuals_with_transfer": sum(r["transferred"] > 0 for r in rows),
        "physical_grasps": sum(r["physical_grasps"] for r in rows),
        "physical_lifts": sum(r["physical_lifts"] for r in rows),
        "energy_supplied": sum(r["energy_supplied"] for r in rows),
        "spilled": sum(r["spilled"] for r in rows),
        "wall_seconds": sum(r["wall_seconds"] for r in rows),
        "simulated_seconds": sum(durations),
        "density_at_1s_min_mean_max": [
            min(r["density_at_1s"] for r in rows),
            float(np.mean([r["density_at_1s"] for r in rows])),
            max(r["density_at_1s"] for r in rows),
        ],
        "nodes_at_1s_range": [min(r["nodes_at_1s"] for r in rows), max(r["nodes_at_1s"] for r in rows)],
        "spent": {k: sum(r["spent"][k] for r in rows) for k in rows[0]["spent"]},
        "max_abs_ledger_error": max(abs(r["ledger_error"]) for r in rows),
    }


def main(output):
    folders = sorted((WORK / "cases").glob("*/result.json"))
    assert len(folders) == 24, "registered 16 free-cup and 8 attached-cup cases must finish first"
    output.mkdir(parents=True, exist_ok=False)
    rows, trajectories = [], {}
    for p in folders:
        row, trajectory = case(p.parent)
        rows.append(row)
        trajectories[row["key"]] = trajectory
        print(json.dumps({"analyzed": row["key"], "frames": row["frames"]}), flush=True)
    groups = {
        name: [r for r in rows if r["attached"] == attached] for name, attached in (("free", False), ("attached", True))
    }
    summary = {
        "schema": "threemind.survival-analysis/1",
        "groups": {k: describe(v) for k, v in groups.items()},
        "cases": rows,
        "primary_success": "physical grasp, lift and qualified grain transfer",
        "attached_is_a_different_task": True,
        "analysis_changes_core": False,
        "partial_or_failed_count": sum(r["status"] not in ("survived", "starved") for r in rows),
        "formal_count": len(rows),
        "formal_wall_seconds": sum(r["wall_seconds"] for r in rows),
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    colors = {"free": "#187965", "attached": "#c17925"}
    labels = {"free": "Free cup (n=16)", "attached": "Attached cup (n=8)"}
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for name, group in groups.items():
        times = sorted(r["life_seconds"] for r in group)
        axes[0, 0].step(
            [0] + times + [600],
            [1] + [1 - (i + 1) / len(times) for i in range(len(times))] + [0],
            where="post",
            color=colors[name],
            label=labels[name],
        )
        for i, row in enumerate(group):
            ts = trajectories[row["key"]]
            x = [r["time_us"] / 1e6 for r in ts]
            axes[0, 1].plot(x, [r["core"]["energy"]["reserve"] for r in ts], color=colors[name], alpha=0.45, lw=1)
            axes[1, 0].plot(x, [r["core"]["edge_density"] for r in ts], color=colors[name], alpha=0.4, lw=1)
    axes[0, 0].set(
        title="Survival: no task-derived food", xlabel="Simulated seconds", ylabel="Fraction alive", ylim=(-0.03, 1.03)
    )
    axes[0, 0].legend()
    axes[0, 1].set(
        title="Energy reserve of each individual", xlabel="Simulated seconds", ylabel="Core experimental units"
    )
    axes[1, 0].set(
        title="Connection density (directed graph)",
        xlabel="Simulated seconds",
        ylabel="Edges / possible directed edges",
        ylim=(0, 1.03),
    )
    keys = list(rows[0]["spent"])
    base = np.zeros(2)
    for k, color in zip(keys, ("#4f8c7d", "#235b85", "#d5a540", "#999fa5")):
        amounts = np.array(
            [summary["groups"][n]["spent"][k] / sum(summary["groups"][n]["spent"].values()) for n in groups]
        )
        axes[1, 1].bar([0, 1], amounts, bottom=base, label=k.removeprefix("consumed_"), color=color)
        base += amounts
    axes[1, 1].set(
        title="Where Core energy was spent",
        xticks=[0, 1],
        xticklabels=["Free cup", "Attached cup"],
        ylabel="Share of consumed energy",
        ylim=(0, 1.04),
    )
    axes[1, 1].legend(fontsize=8, loc="center left", bbox_to_anchor=(1, 0.5))
    fig.suptitle("E27 | Survival selection with physical grain transfer", fontsize=15)
    fig.savefig(output / "survival.png", dpi=160)
    plt.close(fig)
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=WORK / "analysis")
    main(parser.parse_args().output)
