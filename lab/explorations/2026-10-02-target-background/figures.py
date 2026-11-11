"""Render E24 figures from saved evidence; never advance a model."""

from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from analyze import cases, coordinates, metrics, target_series
from common import HERE, WORK, new_json, read_json


def main():
    summary = read_json(WORK / "summary.json")
    rows = cases()
    colors = {"telemetry": "#167b74", "random": "#b67427", "none": "#607786"}
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.6), constrained_layout=True)
    ax = axes[0, 0]
    for i, kind in enumerate(colors):
        data = [r for r in summary["groups"] if r["background"] == kind]
        x = np.array([0, 1]) + (i - 1) * 0.23
        ax.bar(x, [r["mean_margin"] or 0 for r in data], 0.21, color=colors[kind], label=kind)
        if kind == "none":
            ax.text(x[0], data[0]["mean_margin"] * 1.015, "early only", ha="center", fontsize=8)
            ax.text(x[1], 0.00004, "unavailable\n(dead)", ha="center", fontsize=8)
    ax.set(
        xticks=[0, 1],
        xticklabels=["1 s", "30 s"],
        xlabel="Wait after teaching",
        ylabel="Later - earlier net activation integral",
        title="A. The order effect survives background replacement",
    )
    ax.legend(frameon=False, fontsize=8)
    ax.set_ylim(0, 0.00095)
    ax = axes[0, 1]
    for kind, style in (("telemetry", "-"), ("random", "--"), ("none", ":")):
        trace = target_series(rows[f"matrix/100121/{kind}/AB/wait1/cue1"])
        points = [(t, v) for t, v in sorted(trace.items()) if t <= 9_000_000]
        for symbol, color in (("A", "#9d5378"), ("B", "#256b9d")):
            ax.step(
                [(t - 8_000_000) / 1e6 for t, _ in points],
                [v[symbol] for _, v in points],
                where="post",
                color=color,
                linestyle=style,
                linewidth=1.6,
                label=f"{symbol}: {kind}",
            )
    ax.set(
        xlabel="Seconds after cue",
        ylabel="Raw target activation",
        title="B. Brief responses; all three backgrounds overlap",
    )
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax = axes[1, 0]
    for i, (label, items) in enumerate(
        (
            ("Telemetry vs random", summary["background_trajectory_comparisons"]),
            ("Live minimal vs dense", summary["live_pairs"]),
        )
    ):
        whole = [r["global_max_l1_difference"] for r in items]
        ax.plot([i, i], [min(whole), max(whole)], lw=5, color="#b67427")
        ax.scatter([i], [sum(whole) / len(whole)], marker="D", color="#b67427", s=34)
        ax.scatter([i], [max(r["target_max_l1_difference"] for r in items)], marker="o", color="#167b74", s=45)
    ax.plot([], [], "D", color="#b67427", label="Whole network: range / mean")
    ax.plot([], [], "o", color="#167b74", label="A/B target: maximum = 0")
    ax.set(
        xticks=[0, 1],
        xticklabels=["Telemetry / random", "Live load pair"],
        ylim=(-0.18, 2.35),
        ylabel="Maximum trajectory L1 difference",
        title="C. Global changes, identical target trajectories",
    )
    ax.legend(frameon=False, fontsize=8, loc="upper center")
    ax = axes[1, 1]
    for mode, offset, color in (("minimal", -0.18, "#607786"), ("dense", 0.18, "#167b74")):
        selected = [r for r in summary["live"] if r["mode"] == mode]
        ax.bar(
            np.arange(4) + offset, [100 * r["cpu"]["process:cpu_load"] for r in selected], 0.34, color=color, label=mode
        )
    ax.set(
        xticks=range(4),
        xticklabels=["121", "122", "123", "124"],
        xlabel="Paired block (seed suffix)",
        ylabel="Mean process CPU measurement (%)",
        title="D. Live observer load is physically measurable",
    )
    ax.legend(frameon=False, fontsize=8)
    fig.suptitle("E24: target evidence and matched physical-background controls", fontsize=14, fontweight="bold")
    folder = HERE / "figures"
    folder.mkdir(exist_ok=True)
    for ext in ("png", "svg"):
        path = folder / ("target-background." + ext)
        if path.exists():
            raise FileExistsError(path)
        fig.savefig(path, dpi=170, facecolor="white")
    plt.close(fig)
    matrix = [metrics(r) for k, r in rows.items() if k.startswith("matrix/") and "/cue" in k]
    details = {
        "matrix_windows": sum(r is not None for r in matrix),
        "global_classes": dict(Counter(r["global"] for r in matrix if r)),
        "local_pattern_count": sum(r["local_pattern"] is not None for r in matrix if r),
        "local_steady_count": sum(r["local_steady"] is not None for r in matrix if r),
        "target_end_nonzero": sum(any(v["terminal"] != 0 for v in r["targets"].values()) for r in matrix if r),
        "representative_node_ids": coordinates(rows["matrix/100121/telemetry/AB/wait1/cue1"]),
    }
    new_json(WORK / "descriptive-readout-check.json", details)
    print(details, flush=True)


if __name__ == "__main__":
    main()
