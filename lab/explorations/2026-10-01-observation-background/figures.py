"""Export scientific figures from fixed E23 evidence; no simulations."""

from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import HERE, WORK, read_json


def main():
    s = read_json(WORK / "summary-final.json")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5), layout="constrained")
    colors = {"periodic": "#267c6c", "random": "#507eb4", "none": "#a64f3f"}
    a = axes[0, 0]
    for i, kind in enumerate(("periodic", "random")):
        rows = [r for r in s["background"] if r["background"] == kind]
        a.bar(
            [j + (i - 0.5) * 0.30 for j in range(2)],
            [r["mean_margin"] * 1000 for r in rows],
            width=0.28,
            label=kind,
            color=colors[kind],
        )
    a.set(
        xticks=[0, 1],
        xticklabels=["1 s delay", "30 s delay"],
        ylabel="Later-minus-earlier net activity (x 0.001 s)",
        title="A. Order effect survives random background",
    )
    a.legend(frameon=False)
    a.text(
        0.02,
        0.04,
        "No background: truncated early window;\nlate probe unavailable after death.",
        transform=a.transAxes,
        fontsize=9,
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "none"},
    )
    a = axes[0, 1]
    names = ["Minimal /\ndense", "Read / discard\nand dummy load", "Live-input\nreplay"]
    values = [120, 32, 12]
    a.bar(names, values, color=["#267c6c", "#507eb4", "#a78639"])
    for i, v in enumerate(values):
        a.text(i, v + 3, f"{v}/{v}", ha="center")
    a.set(title="B. Exact full-Core-state agreement", ylabel="Matched comparisons", ylim=(0, 145))
    a.text(0.02, 0.97, "52 additional serial confirmations also agreed", transform=a.transAxes, fontsize=9, va="top")
    a = axes[1, 0]
    for i, mode in enumerate(("minimal", "dense", "dummy")):
        rows = [r for r in s["live"] if r["observation"]["mode"] == mode]
        vals = [r["mean_measurements"]["process/cpu_load"] * 100 for r in rows]
        a.scatter([i + (j - 1.5) * 0.05 for j in range(4)], vals, color=["#267c6c", "#507eb4", "#a78639"][i], s=45)
        a.plot([i - 0.2, i + 0.2], [mean(vals)] * 2, color="black", linewidth=1)
    a.set(
        xticks=[0, 1, 2],
        xticklabels=["Minimal", "Dense", "Dummy"],
        ylabel="Recorded process CPU (%)",
        title="C. Live telemetry records observation cost",
    )
    a.set_ylim(0, a.get_ylim()[1] * 1.18)
    a.text(
        0.03, 0.97, "Four sequential sessions each; host load is not fixed", transform=a.transAxes, va="top", fontsize=9
    )
    a = axes[1, 1]
    rows = [read_json(p) for p in (WORK / "cases/later").glob("*/early-commitment.json")]
    for choice, color, label in ((0, "#267c6c", "Later: no extra reader"), (1, "#bd7750", "Later: extra reader")):
        selected = [
            r for r in rows if read_json(WORK / f"cases/later/{r['trial']:03d}/later-choice.json")["choice"] == choice
        ]
        a.scatter(
            [r["dose"] for r in selected],
            [(r["targets"]["A"]["integral"] - r["targets"]["B"]["integral"]) * 1000 for r in selected],
            s=18,
            alpha=0.75,
            color=color,
            label=label,
        )
    a.set(
        xlabel="Preregistered cue strength",
        ylabel="Earlier A-minus-B integral (x 0.001 s)",
        title=f"D. Later choice: no detected association (p={s['later']['two_sided_permutation_p']:.3f})",
    )
    a.legend(frameon=False, fontsize=8)
    for a in axes.flat:
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", alpha=0.15)
    target = HERE / "figures"
    target.mkdir(exist_ok=True)
    fig.savefig(target / "observation-background-final.png", dpi=160)
    fig.savefig(target / "observation-background-final.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
