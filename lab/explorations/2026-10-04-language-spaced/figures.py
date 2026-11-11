"""Static E43 scientific figure from measured result tables only."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from experiment import HERE, read_json


def main():
    results = read_json(HERE / "results.json")
    colors = {
        "spaced": "#146d64",
        "reversed": "#8066a1",
        "massed": "#dd943b",
        "frozen": "#bb535d",
        "untaught": "#687783",
    }
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    structural = results["structural_diagnostic"]["rows"]
    for position, seed in enumerate((17, 29)):
        for offset, condition in ((-0.18, "spaced"), (0.18, "massed")):
            row = next(
                r
                for r in results["checkpoints"]
                if r["seed"] == seed and r["condition"] == condition and r["requested_seconds"] == 530
            )
            retained = next(r for r in structural if r["source"] == f"s{seed}-{condition}" and r["seconds"] == 830)
            for ax, value in (
                (axes[0, 0], row["passed_emission_floor"]),
                (axes[0, 1], retained["edges"].get("language-to-language", {}).get("count", 0)),
            ):
                ax.bar(
                    position + offset,
                    value,
                    width=0.33,
                    color=colors[condition],
                    label=condition if position == 0 else None,
                )
                ax.annotate(
                    f"{value:.1f}" if ax is axes[0, 0] else str(value),
                    (position + offset, value),
                    ha="center",
                    xytext=(0, 5),
                    textcoords="offset points",
                    fontsize=10,
                )
    for ax, title, ylabel in (
        (axes[0, 0], "Signal passing the emission threshold during teaching", "Total amount (includes background)"),
        (axes[0, 1], "Language connections retained 300s after teaching", "Connections"),
    ):
        ax.set_title(title, fontsize=11)
        ax.set_ylabel(ylabel)
        ax.set_xticks([0, 1], ["Wiring / order 17", "Wiring / order 29"])
        ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
        ax.legend(loc="upper right", fontsize=9)
    for column, seed in enumerate((17, 29)):
        ax = axes[1, column]
        for condition, color in colors.items():
            scores = sorted(
                [r for r in results["table"] if r["seed"] == seed and r["condition"] == condition],
                key=lambda r: r["checkpoint"],
            )
            ax.plot(
                [r["checkpoint"] for r in scores],
                [r["text_correct"] for r in scores],
                "o-",
                label=condition,
                color=color,
                linewidth=1.5,
            )
        ax.set_title(f"Wiring / order {seed}: frozen Qwen correct answers", fontsize=11)
        ax.set_xlabel("Simulation seconds (teaching ends at 530)")
        ax.set_ylabel("Correct / 8 related cues")
        ax.axvline(530, color="#555555", linestyle=":", linewidth=1)
        ax.set_ylim(-0.3, 8.3)
        ax.set_yticks(range(9))
        ax.legend(fontsize=8, ncol=2, loc="upper right")
    for ax in axes.flat:
        ax.spines[["right", "top"]].set_visible(False)
        ax.grid(axis="y", alpha=0.15)
    fig.suptitle("ThreeMind E43 | Ordinary-strength expanding reviews + identical physical telemetry", fontsize=15)
    fig.savefig(HERE / "findings.png", dpi=160)
    fig.savefig(HERE / "findings.svg")
    svg = HERE / "findings.svg"
    svg.write_text(
        "\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8"
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
