"""Scientific plots from fixed analysis only; no Core execution."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from common import HERE, WORK, read_json


def choose(lang, zh, en):
    return zh if lang == "zh" else en


def save(fig, name, lang):
    folder = HERE / "figures"
    folder.mkdir(exist_ok=True)
    path = folder / (name + ("" if lang == "zh" else ".en") + ".png")
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def swaps(data, lang):
    labels = ["none", "N", "S", "D", "W", "WSND"]
    names = choose(
        lang,
        ["不交换", "节点历史", "边历史", "快速状态", "边权", "全部四组"],
        ["Sham", "Node history", "Edge history", "Fast states", "Weights", "All four"],
    )
    fig, ax = plt.subplots(figsize=(10.5, 4.8), layout="constrained")
    for j, tau in enumerate((0, 1)):
        values = [
            next(s["mean_margin"] for s in data["summary"] if s["group"] == ["swap", tau, g]) * 1000 for g in labels
        ]
        xs = np.arange(len(labels)) + (j - 0.5) * 0.34
        ax.bar(
            xs,
            values,
            width=0.32,
            label=choose(
                lang, "易化关闭" if not tau else "易化 1 秒", "Facilitation off" if not tau else "Facilitation 1 s"
            ),
            color=("#2b8276", "#c87b47")[j],
        )
    ax.axhline(0, color="#555", lw=0.8)
    ax.set_xticks(range(len(labels)), names)
    ax.set_ylabel(
        choose(
            lang,
            "后教者减先教者的净累计激活（×0.001 激活·秒）",
            "Net later-minus-earlier integral (×0.001 activation·s)",
        )
    )
    ax.set_title(
        choose(
            lang,
            "只交换连接权重，顺序响应优势跟着交换",
            "Exchanging weights exchanges the order-dependent response advantage",
        )
    )
    ax.legend()
    ax.grid(axis="y", alpha=0.18)
    ax.set_axisbelow(True)
    fig.supxlabel(
        choose(
            lang,
            "30 秒后相同提示；供体接受相反教学。四个材料块、两个方向；全部 16 组合见表。",
            "Same cue after 30 s; opposite-order donor. Four blocks, two orders; all 16 combinations are in the tables.",
        ),
        fontsize=9,
    )
    save(fig, "state-exchange", lang)


def timing(data, lang):
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout="constrained")
    rows = [("cadence", 50000), ("phase", 50000), ("phase", 500000), ("phase", 2000000)]
    names = choose(
        lang,
        ["快重复 / 50 ms", "慢重复 / 50 ms", "慢重复 / 500 ms", "慢重复 / 2000 ms"],
        ["Dense / 50 ms", "Sparse / 50 ms", "Sparse / 500 ms", "Sparse / 2000 ms"],
    )
    for ax, (tau, delay) in zip(axes.flat, ((0, 1), (0, 30), (1, 1), (1, 30))):
        matrix = np.array(
            [
                [
                    next(
                        s["mean_margin"] for s in data["summary"] if s["group"] == [family, tau, gap, phase, delay, "X"]
                    )
                    * 1000
                    for phase in (0, 20000, 40000, 60000, 80000)
                ]
                for family, gap in rows
            ]
        )
        vmax = max(float(np.max(np.abs(matrix))), 1e-6)
        img = ax.imshow(matrix, cmap="BrBG", vmin=-vmax, vmax=vmax, aspect="auto")
        ax.set_xticks(range(5), ["0", "20", "40", "60", "80"])
        ax.set_yticks(range(4), names)
        ax.set_title(choose(lang, f"易化 {tau} 秒，等待 {delay} 秒", f"Facilitation {tau} s, wait {delay} s"))
        ax.set_xlabel(choose(lang, "教学相位（毫秒）", "Teaching phase (ms)"))
        for (y, x), value in np.ndenumerate(matrix):
            ax.text(
                x,
                y,
                f"{value:.3g}",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if abs(value) > 0.6 * vmax else "#222",
            )
        fig.colorbar(img, ax=ax, shrink=0.8)
    fig.suptitle(
        choose(lang, "课程节奏、间隔和时间位置分别比较", "Separating cadence, within-pair gap and timing phase"),
        fontsize=14,
    )
    fig.supxlabel(
        choose(
            lang,
            "格内为后教者优势 ×0.001 激活·秒；负数是先教者优势。每面板独立色标，所有格保留实际数值。",
            "Cells: later-minus-earlier ×0.001 activation·s; negative means primacy. Each panel has its own color scale.",
        ),
        fontsize=9,
    )
    save(fig, "timing", lang)


def sensory(data, lang):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    codes = ["00", "01", "10", "11"]
    names = choose(lang, ["两者关", "仅竞争", "仅耗竭", "两者开"], ["Both off", "Competition", "Depletion", "Both on"])
    for ax, mode in zip(axes, ("full", "no_imu")):
        matrix = np.array(
            [
                [
                    next(s["mean_margin"] for s in data["summary"] if s["group"] == ["sensory", mode, learn, test])
                    for test in codes
                ]
                for learn in codes
            ]
        )
        vmax = max(float(np.max(np.abs(matrix))), 1e-6)
        image = ax.imshow(matrix, cmap="BrBG", vmin=-vmax, vmax=vmax, aspect="auto")
        ax.set_xticks(range(4), names, rotation=15)
        ax.set_yticks(range(4), names)
        ax.set_xlabel(choose(lang, "表达阶段", "During expression"))
        ax.set_ylabel(choose(lang, "教学及等待阶段", "During teaching and retention"))
        ax.set_title(
            choose(
                lang,
                "完整感官" if mode == "full" else "无惯性感官",
                "Full senses" if mode == "full" else "Without inertial senses",
            )
        )
        for (y, x), value in np.ndenumerate(matrix):
            ax.text(
                x,
                y,
                f"{value:.4g}",
                ha="center",
                va="center",
                fontsize=10,
                color="white" if abs(value) > 0.6 * vmax else "#222",
            )
        fig.colorbar(image, ax=ax, shrink=0.8)
    fig.suptitle(
        choose(
            lang,
            "教学经历与表达时的局部机制共同决定响应",
            "Learning history and expression mechanisms jointly determine responses",
        ),
        fontsize=14,
    )
    fig.supxlabel(
        choose(
            lang,
            "原教学目标减另一目标的净累计激活（激活·秒）；正负均为观察结果，非好坏评分。两面板独立色标。",
            "Net trained-target-minus-other integral (activation·s). Sign is an outcome, not a quality score. Separate color scales.",
        ),
        fontsize=9,
    )
    save(fig, "sensory-formation", lang)


if __name__ == "__main__":
    data = read_json(WORK / "final.json")
    plt.rcParams.update({"font.family": "Microsoft YaHei", "axes.unicode_minus": False, "font.size": 10})
    for lang in ("zh", "en"):
        swaps(data, lang)
        timing(data, lang)
        sensory(data, lang)
