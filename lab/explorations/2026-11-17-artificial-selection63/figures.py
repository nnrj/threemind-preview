"""Publication figures drawn from audited numbers, with editable SVG labels."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

import layout
import ring as r
import study


def save(fig, name, lang):
    folder = r.HERE / "figures"
    folder.mkdir(exist_ok=True)
    for ext in ("svg", "png", "pdf"):
        fig.savefig(folder / f"{name}.{lang}.{ext}", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def config(lang):
    font = Path("C:/Windows/Fonts/msyh.ttc")
    if font.exists():
        font_manager.fontManager.addfont(str(font))
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Microsoft YaHei", "DejaVu Sans"],
        "font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10,
        "svg.fonttype": "none", "pdf.fonttype": 42, "axes.spines.top": False,
        "axes.spines.right": False, "axes.unicode_minus": False})


def csv_rows(path):
    with path.open(encoding="utf8", newline="") as stream:
        return list(csv.DictReader(stream))


def main(main_only=False):
    evidence = study.DEFAULT_WORK / "analysis-v1"
    assert r.read(evidence / "audit.json")["passed"]
    result = r.read(evidence / "analysis.json")
    rows = csv_rows(evidence / "population-scores.csv")
    paired = csv_rows(evidence / "parent-child.csv")
    retention = csv_rows(evidence / "retention.csv")
    motion = csv_rows(evidence / "stages.csv")
    extra = None
    if not main_only:
        extra = r.read(layout.WORK / "analysis-v1/analysis.json")
        assert r.read(layout.WORK / "analysis-v1/audit.json")["passed"]
    for lang in ("zh", "en"):
        zh = lang == "zh"
        config(lang)
        fig, axes = plt.subplots(1, 2, figsize=(10.1, 4.2), sharey=True)
        for direction, ax in zip(("region0", "region1"), axes):
            for seed in r.SEEDS:
                values = [float(next(x for x in rows if int(x["seed"]) == seed and x["arm"] == direction
                                     and int(x["generation"]) == g)[direction])*100 for g in range(3)]
                ax.plot(range(3), values, color="#b1bac4", alpha=.55, lw=.7, marker="o", ms=2)
            for arm, color, label, offset in ((direction, "#126b93", "定向选择" if zh else "Directional selection", -.04),
                                             ("random", "#cd6e24", "随机选择" if zh else "Random selection", .04)):
                stats = [next(x for x in result["trajectories"] if x["arm"] == arm and x["direction"] == direction
                              and x["generation"] == g) for g in range(3)]
                mean = np.array([x["mean"] for x in stats])*100
                low = np.array([x["ci95"][0] for x in stats])*100
                high = np.array([x["ci95"][1] for x in stats])*100
                ax.errorbar(np.arange(3)+offset, mean, yerr=[mean-low, high-mean],
                            fmt="o-", color=color, capsize=3, lw=2, label=label)
            ax.set(title=("选择目标：区域" if zh else "Selection target: region ")+direction[-1],
                   xlabel="世代" if zh else "Generation", xticks=[0,1,2], xticklabels=["G0","G1","G2"],
                   ylim=(-2,102))
            ax.axhline(50, color="#999999", ls=":", lw=.8)
            ax.grid(axis="y", alpha=.14)
        axes[0].set_ylabel("目标区域停留比例（%）" if zh else "Target-region occupancy (%)")
        axes[0].legend(frameon=False, loc="lower left", fontsize=9)
        fig.text(.5, -.015, ("16个独立群体；每群体每代计入全部4名候选。灰线：定向组各群体；误差线：群体bootstrap 95%区间。"
                            if zh else "16 independent populations; all four candidates per generation. Gray lines: directional populations; bars: population bootstrap 95% CIs."),
                 ha="center", fontsize=8.1)
        fig.tight_layout()
        save(fig, "01-generations", lang)

        fig, axes = plt.subplots(1, 2, figsize=(10.1, 4.3), sharex=True, sharey=True)
        for direction, ax in zip(("region0", "region1"), axes):
            group = [x for x in paired if x["arm"] == direction]
            for generation, color, marker in ((1, "#126b93", "o"), (2, "#cd6e24", "^")):
                subset = [x for x in group if int(x["generation"]) == generation]
                ax.scatter([float(x["parent_target"])*100 for x in subset],
                           [float(x["child_target"])*100 for x in subset], c=color, marker=marker,
                           s=17, alpha=.6, label=f"G{generation-1} → G{generation}")
            ax.axvline(55, color="#555555", ls=":", lw=.8)
            ax.axhline(55, color="#555555", ls=":", lw=.8)
            ax.plot([0,100],[0,100], color="#bbbbbb", ls="--", lw=.6)
            ax.set(title=("选择目标：区域" if zh else "Selection target: region ")+direction[-1], xlim=(-2,102), ylim=(-2,102),
                   xlabel="亲代目标区域停留比例（%）" if zh else "Parent target occupancy (%)")
        axes[0].set_ylabel("子代目标区域停留比例（%）" if zh else "Offspring target occupancy (%)")
        axes[0].legend(frameon=False)
        fig.text(.5, -.01, ("全部256组亲子对应；虚线门槛为55%。同群体亲子并非独立样本；统计单位仍为16个群体。"
                           if zh else "All 256 parent–offspring pairs. Dotted thresholds: 55%. Related pairs are not independent; N = 16 populations."),
                 ha="center", fontsize=8.3)
        fig.tight_layout()
        save(fig, "02-parent-offspring", lang)

        fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.1), sharey=True)
        for direction, ax in zip(("region0", "region1"), axes):
            group = [x for x in rows if x["arm"] == direction and int(x["generation"]) == 2]
            for x in group:
                normal = float(x[direction])*100
                blank = float(x["blank_region1"])
                blank = (1-blank if direction == "region0" else blank)*100
                ax.plot([0,1], [normal, blank], color="#b1bac4", marker="o", ms=3, lw=.8, alpha=.65)
            normal = np.mean([float(x[direction]) for x in group])*100
            blank = np.mean([float(x["blank_region1"]) for x in group])
            blank = (1-blank if direction == "region0" else blank)*100
            ax.plot([0,1], [normal, blank], color="#126b93", marker="D", lw=2.2, ms=7)
            ax.set(xticks=[0,1], xticklabels=(["正常继承","不继承内核状态"] if zh else ["Inherited","Uninherited Core"]),
                   title=("选择目标：区域" if zh else "Selection target: region ")+direction[-1], xlim=(-.25,1.25), ylim=(-2,102))
            ax.axhline(50, color="#999999", ls=":", lw=.8)
        axes[0].set_ylabel("G2目标区域停留比例（%）" if zh else "G2 target-region occupancy (%)")
        fig.text(.5, -.01, ("灰线连接同一群体中的匹配条件；蓝线为16群体均值。两条件外设、培养起点和后续过程相同。"
                           if zh else "Gray lines pair conditions within populations; blue: mean of 16 populations. Peripherals, starts, and subsequent procedures match."),
                 ha="center", fontsize=8.2)
        fig.tight_layout()
        save(fig, "03-inheritance-control", lang)

        if extra is not None:
            fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.4), sharey=True)
            for direction, ax in zip(("region0", "region1"), axes):
                group = [x for x in extra["population_scores"] if x["arm"] == direction]
                matrix = np.array([[x["baseline_region1"],x["closed_region1"],x["replay_region1"]] for x in group])
                if direction == "region0":
                    matrix = 1-matrix
                matrix *= 100
                for line in matrix:
                    ax.plot(range(3), line, color="#b1bac4", lw=.7, marker="o", ms=2, alpha=.6)
                ax.plot(range(3), matrix.mean(axis=0), color="#126b93", lw=2.2, marker="D", ms=6)
                ax.set(xticks=range(3), xticklabels=(["原布局\n实时控制","交换布局\n实时控制","交换布局\n重放旧动作"] if zh else
                       ["Original layout\nClosed loop","Swapped layout\nClosed loop","Swapped layout\nOld-action replay"]),
                       title=("选择目标：区域" if zh else "Selection target: region ")+direction[-1], ylim=(-2,102))
                ax.axhline(50, color="#999999", ls=":", lw=.8)
            axes[0].set_ylabel("目标区域停留比例（%）" if zh else "Target-region occupancy (%)")
            fig.text(.5, -.025, ("全部G2候选；每群体4名、每名2起点。灰线为群体，蓝线为均值。此对照独立于主代际检验。"
                                if zh else "Every G2 candidate; 4 candidates × 2 starts per population. Gray: populations; blue: mean. Separate supplementary comparison."),
                     ha="center", fontsize=8.2)
            fig.tight_layout()
            save(fig, "04-layout-controls", lang)
        fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.3))
        for label, prefix, color, marker in (
            ("G0", "g0/", "#6b7280", "o"),
            ("G2 · " + ("选择区域0" if zh else "Region 0 selection"), "region0/g2/", "#126b93", "s"),
            ("G2 · " + ("选择区域1" if zh else "Region 1 selection"), "region1/g2/", "#cd6e24", "^"),
            ("G2 · " + ("随机选择" if zh else "Random selection"), "random/g2/", "#16857a", "D")):
            data = []
            for seed in r.SEEDS:
                group = [x for x in motion if int(x["seed"]) == seed and x["key"].startswith(prefix)
                         and "/held-" in x["key"] and "-uninherited/" not in x["key"]]
                assert len(group) == 16
                data.append([np.mean([float(x[field]) for x in group])
                             for field in ("region1", "travel_distance", "net_displacement")])
            data = np.array(data)
            for ax, column in zip(axes, (1, 2)):
                ax.scatter(data[:, 0]*100, data[:, column], label=label, c=color,
                           marker=marker, alpha=.65, s=27, edgecolors="none")
        for ax in axes:
            ax.set(xlabel="区域1停留比例（%）" if zh else "Region 1 occupancy (%)", xlim=(-2,102))
            ax.axvline(50, color="#999999", ls=":", lw=.8)
            ax.grid(alpha=.14)
        axes[0].set_ylabel("平均行程（环周长）" if zh else "Mean travel (ring circumferences)")
        axes[0].set_ylim(bottom=0)
        axes[1].set_ylabel("平均有符号净位移（环周长）" if zh else "Mean signed displacement (ring circumferences)")
        axes[1].axhline(0, color="#999999", ls=":", lw=.8)
        axes[0].legend(frameon=False, fontsize=8, loc="best")
        fig.text(.5, -.01, ("每点为一个群体的4名候选、每名4个起点的平均值。此图描述运动过程，不增加达标要求。"
                           if zh else "Each point averages 4 candidates × 4 starts within one population. Descriptive movement measures add no success criterion."),
                 ha="center", fontsize=8.2)
        fig.tight_layout()
        save(fig, "05-movement", lang)
    print("Result figures saved as SVG, PNG, PDF; main_only="+str(main_only))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-only", action="store_true")
    main(parser.parse_args().main_only)
