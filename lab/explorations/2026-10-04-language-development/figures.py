"""Publication-friendly summaries; counts are not independent sample sizes."""

from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from experiment import HERE, read_json


def main():
    data = read_json(HERE / "results.json")
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "figure.facecolor": "#f4f8f5", "axes.facecolor": "#ffffff"})
    fig, grid = plt.subplots(3, 2, figsize=(12, 11), constrained_layout=True)
    axes = grid[1:]
    colors = {"text": "#98aa9b", "stream-sparse": "#207961"}
    positions = np.arange(3)
    for offset, route in enumerate(("text", "stream-sparse")):
        values = [sum(max(map(abs, r["response"])) > 1e-8 for r in data["visual_recall_rows"]
                      if r["route"] == route and r["seed"] == seed and r["condition"] in ("normal", "reversed"))
                  for seed in (11, 37, 53)]
        bars = grid[0, 0].bar(positions + (offset - .5) * .32, values, .3, label=route, color=colors[route])
        grid[0, 0].bar_label(bars)
    grid[0, 0].set(xticks=positions, xticklabels=["seed 11", "seed 37", "seed 53"], ylim=(0, 115),
                   title="A  Names can evoke visual-related activity", ylabel="Nonzero cue effect / 96 conditions")
    grid[0, 0].legend(frameon=False, fontsize=8)
    grid[0, 0].text(.02, .87, "No teaching / plasticity off: all zero", transform=grid[0, 0].transAxes, fontsize=8)
    for condition, linestyle in (("normal", "-"), ("reversed", "--")):
        for seed in (11, 37, 53):
            values = [next(r for r in data["graphs"] if r["route"] == "stream-sparse" and r["seed"] == seed
                           and r["condition"] == condition and r["seconds"] == sec)["edges"].get("language/visual", 0)
                      for sec in (266, 326, 566)]
            grid[0, 1].plot([0, 60, 300], values, linestyle=linestyle, marker="o", alpha=.8, label=f"{seed} {condition}")
    grid[0, 1].set(xlabel="Seconds after teaching", ylabel="Language-visual connections",
                   title="B  Learned bridges: persistence is not precise recall")
    grid[0, 1].legend(frameon=False, fontsize=7, ncol=2)
    for offset, route in enumerate(("text", "stream-sparse")):
        rows = [r for r in data["visual_recall_summary"] if r["route"] == route]
        values = [sum(r["correct"] for r in rows if r["seed"] == seed) for seed in (11, 37, 53)]
        bars = axes[0, 0].bar(positions + (offset - .5) * .32, values, .3, label=route, color=colors[route])
        axes[0, 0].bar_label(bars)
    axes[0, 0].set(xticks=positions, xticklabels=["seed 11", "seed 37", "seed 53"],
                   title="C  Correct effect follows reversed teaching", ylabel="Both assignments correct / 48 conditions")
    axes[0, 0].legend(frameon=False)
    expr = [r for r in data["expression"]["summary"] if r["head"] == "final"]
    vision = [sum(v["correct"] for k, v in r["teaching"].items() if k != "untaught") /
              sum(v["total"] for k, v in r["teaching"].items() if k != "untaught") for r in expr]
    recalled = data["expression"]["paired"]
    rates = []
    for head in ("final", "weak"):
        rows = [r for r in recalled if r["head"] == head]
        rates.append(sum(r["same_window_both_correct_and_changed_from_no_cue"] for r in rows) / sum(r["windows"] for r in rows))
    bars = axes[0, 1].bar([0, 1, 2], [np.mean(vision) * 100, *[v * 100 for v in rates]],
                          color=["#207961", "#c07127", "#89949c"])
    axes[0, 1].bar_label(bars, fmt="%.1f%%")
    axes[0, 1].set(xticks=[0, 1, 2], xticklabels=["Teaching\n(current object)", "Cue-specific recall\n(original head)", "Cue-specific recall\n(weak calibration)"],
                   ylim=(0, 113), ylabel="Correct expression (%)", title="D  Perception and remembered answer differ")
    axes[0, 1].text(.42, .80, "Also succeeds with\nCore learning off.", transform=axes[0, 1].transAxes,
                     fontsize=9, color="#54645b")
    counts = defaultdict(lambda: [0, 0])
    for row in data["weak_validation"]:
        key = (row["variant"], row["intensity"])
        counts[key][0] += row["correct"]
        counts[key][1] += row["total"]
    for variant, color in (("base", "#89949c"), ("weak", "#207961")):
        axes[1, 0].plot([.1, .3, 1], [100 * counts[variant, x][0] / counts[variant, x][1] for x in (.1, .3, 1)],
                       marker="o", color=color, label=variant)
    axes[1, 0].set(xscale="log", xticks=[.1, .3, 1], xticklabels=["0.1", "0.3", "1"], ylim=(-4, 104),
                   xlabel="Measured visual input strength", ylabel="Exact object-word expression (%)",
                   title="E  Held-out visual views, no question/answer labels")
    axes[1, 0].legend(frameon=False)
    bridge = [r for r in data["bridge_ablation"]["results"] if "skipped" not in r]
    seeds = sorted({r["seed"] for r in bridge})
    for offset, mask in enumerate(("bridge", "matched")):
        values = [sum(r["correct"] for r in bridge if r["seed"] == s and r["mask"] == mask) for s in seeds]
        bars = axes[1, 1].bar(np.arange(len(seeds)) + (offset - .5) * .32, values, .3,
                              label="Language-visual" if mask == "bridge" else "Other matched edges",
                              color="#c07127" if mask == "bridge" else "#207961")
        axes[1, 1].bar_label(bars)
    axes[1, 1].set(xticks=np.arange(len(seeds)), xticklabels=[f"seed {s}" for s in seeds], yticks=[0, 1, 2], ylim=(0, 2.6),
                   ylabel="Correct assignments after silence / 2", title="F  Local intervention on selected cue effects")
    axes[1, 1].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle("ThreeMind E44 | Scratch language peripherals and plastic Core", fontsize=16)
    fig.supxlabel("Same-source prompts/windows are correlated; these panels are descriptive. Core dynamics unchanged.", fontsize=9)
    fig.savefig(HERE / "findings.png", dpi=170)
    fig.savefig(HERE / "findings.svg")
    plt.close(fig)
    print("E44 figures saved")


if __name__ == "__main__":
    main()
