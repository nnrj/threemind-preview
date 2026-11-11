"""Export figures from saved observations, never from a new Core simulation."""

import gzip
import json
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import WORK, read_json

MODES = {
    "full": "Full sensors",
    "no_imu": "Joints only",
    "dose_matched": "Full, matched dose",
    "shuffled_imu": "Shuffled IMU",
}
COLORS = {
    "full": "#167c80",
    "no_imu": "#d38b30",
    "dose_matched": "#7957a3",
    "shuffled_imu": "#758289",
    "delayed_imu": "#7957a3",
    "no_proprioception": "#758289",
}


def save(fig, name):
    fig.savefig(WORK / (name + ".png"), dpi=160, bbox_inches="tight")
    fig.savefig(WORK / (name + ".svg"), bbox_inches="tight")
    plt.close(fig)


def main():
    rows = read_json(WORK / "analysis-final.json")["rows"]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout="constrained")
    for ax, preset in zip(axes, ("ordinary", "facilitation")):
        for mode, name in MODES.items():
            values = []
            for delay in (1, 60, 300):
                rs = [
                    r
                    for r in rows
                    if r["family"] == "memory"
                    and r["stage"] == "probe"
                    and r["preset"] == preset
                    and r["mode"] == mode
                    and r["delay_s"] == delay
                    and r["cue"] != "none"
                ]
                values.append(mean(r["target_delta_integrals"][r["expected"]] for r in rs))
            ax.plot((1, 60, 300), values, "o-", label=name, color=COLORS[mode])
        ax.set(
            title=preset.title(),
            xlabel="Retention interval (simulation seconds)",
            ylabel="Cue minus no-cue activation integral",
        )
        ax.set_xscale("log")
        ax.set_xticks((1, 60, 300), labels=("1", "60", "300"))
        ax.grid(alpha=0.18)
    axes[0].legend(fontsize=9)
    fig.suptitle("Retained associations: transient elicitation, separate from convergence ranking")
    save(fig, "memory-retention")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout="constrained")
    for ax, cue in zip(axes, ("A", "B")):
        selected = [
            r
            for r in rows
            if r["seed"] == 930101
            and r["preset"] == "ordinary"
            and r["mode"] == "full"
            and r.get("cue") == cue
            and r.get("delay_s") == 300
            and r["stage"] == "probe"
        ]
        for r in selected:
            condition = r.get("intervention_condition", "original")
            curve = json.loads(gzip.decompress((WORK / "cases" / r["key"] / "trajectory.json.gz").read_bytes()))
            channel = r["targets"][r["expected"]]
            ys = [next((n["activation"] for n in p["nodes"] if n["channel"] == channel), 0) for p in curve]
            ax.plot(
                [p["relative_us"] / 1e6 for p in curve],
                ys,
                label=condition,
                linestyle="--" if condition == "restore" else "-",
                linewidth=2 if condition == "original" else 1.4,
            )
            if condition == "original" and r["decision_us"]:
                at = (int(r["decision_us"]) - r["extra"]["begin_us"]) / 1e6
                ax.axvline(at, color="#777777", linestyle=":", label="Convergence decision")
        ax.set(title=f"Cue {cue}: expected joint channel", xlabel="Seconds after cue", ylabel="Activation", xlim=(0, 3))
        ax.grid(alpha=0.18)
    axes[1].legend(fontsize=8)
    fig.suptitle("300-second retained memory: silence, restore and matched-edge controls (one declared example)")
    save(fig, "memory-intervention")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
    categories = ("0.5s ordered", "5s ordered", "0.5s shuffled", "5s shuffled")
    for index, preset in enumerate(("ordinary", "facilitation")):
        values = []
        for cat in categories:
            delay = float(cat.split("s")[0])
            assignment = "ordered" if cat.endswith("ordered") else "shuffled_outcomes"
            subset = [
                r
                for r in rows
                if r["family"] == "sequence"
                and r["stage"] == "probe"
                and r["preset"] == preset
                and r["mode"] == "full"
                and r["delay_s"] == delay
                and r["assignment"] == assignment
            ]
            values.append(mean(r["secondary_correct"] for r in subset))
        axes[0].bar([i + (index - 0.5) * 0.35 for i in range(4)], values, width=0.35, label=preset)
    axes[0].set_xticks(range(4), labels=categories, rotation=15)
    axes[0].set(ylim=(0, 1.06), title="Sequence: full sensors", ylabel="Secondary direction correct")
    axes[0].legend(fontsize=8)
    for index, domain in enumerate(("original", "angle", "gravity")):
        values = []
        for mode in MODES:
            subset = [
                r
                for r in rows
                if r["family"] == "transfer"
                and r["preset"] == "ordinary"
                and r["mode"] == mode
                and r["domain"] == domain
            ]
            values.append(
                mean(
                    (
                        r["trajectory_target_integrals"][r["expected"]]
                        - r["trajectory_target_integrals"][1 - r["expected"]]
                    )
                    / sum(r["trajectory_target_integrals"])
                    for r in subset
                )
            )
        axes[1].bar([i + (index - 1) * 0.24 for i in range(4)], values, width=0.24, label=domain)
    axes[1].set_xticks(range(4), labels=("Full", "Joints only", "Matched dose", "Shuffled IMU"), rotation=15)
    axes[1].set(
        ylim=(-1.05, 1.05), title="Transfer: ordinary preset", ylabel="Signed selectivity (+ trained, - reversed)"
    )
    axes[1].axhline(0, color="#777777", linewidth=0.7)
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(axis="y", alpha=0.18)
    fig.suptitle("Trajectory scoring is secondary; primary convergence and all conditions are in the report")
    save(fig, "sequence-transfer")

    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout="constrained")
    for column, mode in enumerate(("full", "no_imu")):
        r = next(
            r
            for r in rows
            if r["family"] == "transfer-trace" and r["seed"] == 930102 and r["mode"] == mode and r["sign"] == 1
        )
        raw = json.loads(gzip.decompress((WORK / "cases" / r["key"] / "input-trajectory.json.gz").read_bytes()))
        by_time = {p["relative_us"]: p for p in raw}
        points = [by_time[t] for t in sorted(by_time)]
        for row, field in enumerate(("activation", "inhibition")):
            ax = axes[row, column]
            for i, channel in enumerate(r["targets"]):
                ax.plot(
                    [p["relative_us"] / 1e6 for p in points],
                    [next((n[field] for n in p["nodes"] if n["channel"] == channel), 0) for p in points],
                    label="A (trained target)" if i == 0 else "B (other marker)",
                )
            ax.axvspan(0, 0.4, color="#167c80", alpha=0.08, label="Physical input")
            ax.axvline(0.6, linestyle=":", color="#555555", label="Original score starts")
            ax.set(
                xlim=(0, 1.3),
                title=MODES[mode] + ": " + field,
                xlabel="Seconds from physical input onset",
                ylabel=field,
            )
            ax.grid(alpha=0.15)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("One declared replay example: seed 930102, positive pose; all eight final Core hashes unchanged")
    save(fig, "transfer-phases")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), layout="constrained")
    for ax, preset in zip(axes, ("ordinary", "facilitation")):
        for mode in ("full", "no_imu", "delayed_imu", "no_proprioception"):
            for learning in (True, False):
                rs = [
                    r
                    for r in rows
                    if r["family"] == "adaptation"
                    and r["stage"] == "training"
                    and r["preset"] == preset
                    and r["mode"] == mode
                    and r["consolidation"] == learning
                ]
                if not rs:
                    continue
                values = [mean(r["episodes"][i]["position_mse"] for r in rs) for i in range(3)]
                ax.plot(
                    (1, 2, 3),
                    values,
                    "o-" if learning else "--",
                    color=COLORS[mode],
                    label=f"{mode}, consolidation {'on' if learning else 'off'}",
                )
        passive = mean(r["position_mse"] for r in read_json(WORK / "passive-cart.json"))
        ax.axhline(passive, color="black", linestyle=":", label="Passive physics")
        ax.set(
            title=preset.title(),
            xlabel="10-second body episode (same Core continues)",
            ylabel="Mean squared distance from track centre",
        )
        ax.set_xticks((1, 2, 3))
        ax.grid(alpha=0.18)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, -0.14), ncol=3)
    fig.suptitle("Closed-loop behaviour: lower error means closer to the external centre objective")
    save(fig, "environment-adaptation")


if __name__ == "__main__":
    main()
