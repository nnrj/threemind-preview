"""Small reproducible research figures; no smoothing or invented samples."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from experiment import HERE, read_json


def main():
    data = read_json(HERE / "results.json")
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    colors = ("#19796d", "#b07035")
    conditions = ("ordinary", "reversed", "blank", "frozen")
    for i, seed in enumerate(data["primary"]["seeds"]):
        values = [seed["conditions"][c]["primary_text"]["correct"] for c in conditions]
        bars = axes[0].bar(
            np.arange(4) + (i - 0.5) * 0.35, values, 0.35, color=colors[i], label=f"Wiring/order {seed['seed']}"
        )
        axes[0].bar_label(bars)
    axes[0].set(
        xticks=range(4),
        xticklabels=["Ordinary", "Reversed", "Untaught", "Learning off"],
        ylim=(0, 8.8),
        ylabel="Correct answers / 8 cues",
        title="Fixed 0.5–1.0 s test window",
    )
    axes[0].legend(frameon=False, fontsize=9)
    groups = data["diagnostic"]["groups"]
    for i, condition in enumerate(("ordinary", "reversed")):
        values = [g["conditions"][condition]["teaching_transmission"]["passed_fraction"] * 100 for g in groups]
        bars = axes[1].bar(np.arange(4) + (i - 0.5) * 0.35, values, 0.35, color=colors[i], label=condition)
        axes[1].bar_label(bars, fmt="%.2f", fontsize=8)
    axes[1].set(
        xticks=range(4),
        xticklabels=["1 / off", "4 / off", "1 / 1s", "4 / 1s"],
        ylim=(0, 90),
        xlabel="Teaching intensity / facilitation time",
        ylabel="Passed per-edge emission floor (%)",
        title="Registered single-wiring diagnostic",
    )
    axes[1].legend(frameon=False, fontsize=9)
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    figure.savefig(HERE / "findings.png", dpi=160)
    figure.savefig(HERE / "findings.svg")
    plt.close(figure)


if __name__ == "__main__":
    main()
