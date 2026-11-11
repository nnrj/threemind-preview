"""Static research figures from frozen observations; no simulation or smoothing."""

import gzip
import json
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from common import ROOT, WORK


def read(name):
    return json.loads((WORK / name).read_bytes())


def save(fig, name):
    fig.savefig(WORK / f"{name}.png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    directory = ROOT / "docs/images"
    directory.mkdir(exist_ok=True)
    shutil.copy2(WORK / f"{name}.png", directory / f"input-rate-autonomy-{name}-2026-09-29.png")


def figures():
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    rate = read("rate-analysis.json")
    intervals = [1000, 5000, 20000, 100000, 1000000]
    attribution = read("attribution-results.json")
    selection = read("selection-results.json")
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
    for mode, marker in (("single", "o"), ("burst", "s")):
        ys = [rate["groups"]["continuous"][str(i)]["9293001"][mode]["mean"] for i in intervals]
        axes[0].plot([i / 1000 for i in intervals], ys, marker=marker, label=mode + " cue")
    axes[0].set(
        xscale="log",
        xlabel="Input interval (ms)",
        ylabel="Cue-specific target peak difference",
        title="Faster input was not better",
    )
    axes[0].legend()
    names = ["Goal: region 0", "Goal: region 1", "Random"]
    for block, shift, color in ((9293201, -0.18, "#7999b2"), (9293202, 0.18, "#168475")):
        vals = [
            sum(r["extra"]["region1_fraction"] for r in selection["held_out"] if r["seed"] == block and r["arm"] == arm)
            / 8
            for arm in ("region0", "region1", "random")
        ]
        axes[1].bar([i + shift for i in range(3)], vals, width=0.34, color=color, label=f"Wiring {block % 10}")
    axes[1].axhline(0.5, color="#aaa", lw=1, ls="--")
    axes[1].set(
        xticks=range(3),
        xticklabels=names,
        ylim=(0, 1.08),
        ylabel="Time in region 1",
        title="Inherited behavior in held-out worlds",
    )
    axes[1].legend()
    for arm, color in (("region0", "#537aaf"), ("region1", "#dc9751")):
        vals = []
        normal = [
            r["extra"]["region1_fraction"] for r in selection["held_out"] if r["seed"] == 9293202 and r["arm"] == arm
        ]
        vals.append(sum(normal) / len(normal))
        for condition in ("communication_off", "consolidation_off"):
            xs = [
                r["extra"]["region1_fraction"] for r in attribution if r["arm"] == arm and r["condition"] == condition
            ]
            vals.append(sum(xs) / len(xs))
        axes[2].plot(range(3), vals, marker="o", color=color, label=arm.replace("region", "Goal "))
    axes[2].set(
        xticks=range(3),
        xticklabels=["Ordinary", "No inter-node\ncommunication", "No further edge\nconsolidation"],
        ylim=(0, 1.08),
        ylabel="Time in region 1",
        title="The preference survives disconnection",
    )
    axes[2].legend()
    fig.tight_layout(w_pad=2)
    save(fig, "overview")

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    key = "selection/s9293202/region0/final/p2/swap0"
    data = json.loads(gzip.decompress((WORK / "cases" / key / "world.json.gz").read_bytes()))
    rows = data["rows"]
    time = [r["relative_us"] / 1e6 for r in rows]
    axes[0].plot(time, [r["body"]["x"] for r in rows], color="#168475", label="Body position")
    axes[0].axhspan(0, 0.5, color="#168475", alpha=0.08, label="Selected region 0")
    axes[0].set(ylabel="Position", title="An unseen starting position in the other region")
    axes[0].legend(loc="upper right")
    axes[1].plot(
        time, [sum(n["activation"] for n in r["nodes"]) for r in rows], color="#537aaf", label="All-node activation"
    )
    axes[1].plot(
        time, [sum(n["inhibition"] for n in r["nodes"]) for r in rows], color="#dc9751", label="All-node inhibition"
    )
    axes[1].set(ylabel="Model units")
    axes[1].legend()
    axes[2].plot(time, [r["applied_control"] for r in rows], color="#7c569a")
    axes[2].set(xlabel="Simulated seconds", ylabel="Motor control")
    fig.tight_layout()
    save(fig, "activity")

    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    for teaching, color in (("paired", "#168475"), ("balanced", "#dc9751")):
        for tau, style in ((0.8, "--"), (0.02, "-")):
            path = WORK / "cases" / f"recovery/{teaching}/tau{tau}/recovery.jsonl.gz"
            with gzip.open(path, "rt", encoding="utf-8") as f:
                rs = [json.loads(line) for line in f]
            ax.plot(
                [r["relative_us"] / 1e6 for r in rs],
                [sum(n["activation"] for n in r["nodes"]) for r in rs],
                color=color,
                ls=style,
                label=f"{teaching}, recovery {tau} s",
            )
    ax.set(
        xlabel="Seconds after all sensory input stops",
        ylabel="All-node activation",
        title="Continuous external energy supply does not prevent silence",
    )
    ax.legend()
    fig.tight_layout()
    save(fig, "recovery")


if __name__ == "__main__":
    figures()
