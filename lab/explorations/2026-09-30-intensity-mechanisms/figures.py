"""Static research figures with explicit units and deterministic block ranges."""

import re
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from experiment import HERE, WORK

from lab.tools.service_study import read_json

EN = {
    "目标 B 累计激活 × 10³\n（提示减去无提示；单位：激活·秒）": "Target B integral x 1000\n(cued minus uncued; activation-seconds)",
    "目标 B 累计激活 × 10³": "Target B integral x 1000",
    "当前提示强度": "Current cue intensity",
    "无额外项\n无易化": "No extra term\nNo facilitation",
    "无额外项\n易化 1 秒": "No extra term\nFacilitation 1 s",
    "保留额外项\n无易化": "Extra term ON\nNo facilitation",
    "保留额外项\n易化 1 秒": "Extra term ON\nFacilitation 1 s",
    "末次强刺激后 1 模拟秒": "1 simulated second after teaching",
    "末次强刺激后 30 模拟秒": "30 simulated seconds after teaching",
    "去掉额外强度公式后，已有机制能保留多少响应？": "Without the extra intensity term: how much response remains?",
    "单次强度 4，提示强度 0.5，既有边巩固开启。误差线：4 个固定材料块的最小值至最大值，非置信区间。": "Single intensity-4 input; cue 0.5; existing-edge consolidation ON.\nError bars: range across 4 fixed blocks, not confidence intervals.",
    "无新经历": "No new experience",
    "单次 1": "Single 1",
    "单次 4": "Single 4",
    "10 次 0.4": "10 inputs at 0.4",
    "易化关闭，等待 1 秒": "Facilitation OFF; wait 1 s",
    "易化关闭，等待 30 秒": "Facilitation OFF; wait 30 s",
    "易化开启，等待 1 秒": "Facilitation ON; wait 1 s",
    "易化开启，等待 30 秒": "Facilitation ON; wait 30 s",
    "相同提示，经历不同；不同提示，反应不一定等比例": "Experience changes responses; cue-response curves are not proportional",
    "额外强刺激项关闭；既有边巩固开启；2 个固定材料块均值；所有值已减去同源无提示对照。": "Extra term OFF; existing-edge consolidation ON; means of 2 fixed blocks.\nEvery value subtracts its matched uncued control.",
    "正常": "Unchanged",
    "无普通\n触达巩固": "Touch gains\nOFF",
    "无出生\n权重项": "Birth term\nOFF",
    "无新颖性": "Novelty OFF",
    "触达与出生\n两项均关": "Both terms\nOFF",
    "形成阶段：30 秒后测试（I0/F0/L0）": "Formation: test after 30 s (I0/F0/L0)",
    "仅取消\n局部耗竭": "Depletion\nOFF",
    "仅取消\n接收抑制": "Reception\ninhibition OFF",
    "仅关闭\n短时权重": "Fast trace\nOFF",
    "仅关闭\n局部竞争": "Competition\nOFF",
    "1 秒后：只改变提示阶段（I0/F0/L1）": "After 1 s: change expression only (I0/F0/L1)",
    "关→关": "OFF to OFF",
    "关→开": "OFF to ON",
    "开→关": "ON to OFF",
    "开→开": "ON to ON",
    "1 秒后易化：训练及等待 → 提示阶段（I0/L1）": "Facilitation: training/wait to cue phase (1 s; I0/L1)",
    "静默\nA→B": "Silence\nA to B",
    "静默后\n解除": "Silence then\nrestore",
    "静默其他\n匹配连接": "Silence matched\nother connection",
    "30 秒后：连接消融与恢复": "After 30 s: connection silencing and restoration",
    "定位作用：当前状态影响表达，学习连接承担关联": "Local states regulate expression; learned connections carry the association",
    "单次强度 4，提示 0.5；误差线为 2 个固定材料块范围。开关沿用已有状态；关闭耗竭不等于外界能量充足。": "Single intensity-4 input; cue 0.5; ranges across 2 fixed blocks.\nSwitches retain existing state. Disabling depletion is not unlimited external supply.",
}


def bar(ax, rows, labels, colors, *, title):
    values = np.array([r["net_B"] * 1000 for r in rows])
    low = np.array([r["B_min"] * 1000 for r in rows])
    high = np.array([r["B_max"] * 1000 for r in rows])
    ax.bar(
        range(len(rows)),
        values,
        color=colors,
        width=0.65,
        yerr=np.maximum(0, np.array([values - low, high - values])),
        capsize=3,
    )
    ax.set_xticks(range(len(labels)), labels)
    ax.set_title(title, loc="left", fontsize=12)
    ax.set_ylabel("目标 B 累计激活 × 10³\n（提示减去无提示；单位：激活·秒）")
    ax.axhline(0, color="#64748b", linewidth=0.6)
    for i, value in enumerate(values):
        ax.annotate(
            f"{value:.3f}",
            (i, value),
            xytext=(0, 6 if value >= 0 else -14),
            textcoords="offset points",
            ha="center",
            fontsize=9,
        )
    ax.margins(y=0.2)


def save(fig, name):
    folder = HERE / "figures"
    folder.mkdir(exist_ok=True)
    path = folder / f"{name}.png"
    # Only derived figures regenerate; experiment states and results remain immutable.
    fig.savefig(path, dpi=160, facecolor="white")
    shutil.copy2(path, WORK / path.name)
    for ax in fig.axes:
        labels = [item.get_text() for item in ax.get_xticklabels()]
        if any(re.search("[\u4e00-\u9fff]", label) for label in labels):
            ax.set_xticks(ax.get_xticks(), [EN.get(label, label) for label in labels])
    from matplotlib.text import Text

    for item in fig.findobj(match=Text):
        old = item.get_text()
        if re.search("[\u4e00-\u9fff]", old):
            if old not in EN:
                raise ValueError(f"missing figure translation: {old}")
            item.set_text(EN[old])
    path = folder / f"{name}.en.png"
    fig.savefig(path, dpi=160, facecolor="white")
    shutil.copy2(path, WORK / path.name)
    plt.close(fig)


def main():
    plt.rcParams.update(
        {
            "font.family": "Microsoft YaHei",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.unicode_minus": False,
            "axes.titlepad": 12,
        }
    )
    data = read_json(WORK / "summary-final.json")
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5), layout="constrained")
    labels = ["无额外项\n无易化", "无额外项\n易化 1 秒", "保留额外项\n无易化", "保留额外项\n易化 1 秒"]
    colors = ["#a8bfc4", "#167d8d", "#d19a44", "#8066ac"]
    for ax, delay in zip(axes, (1, 30)):
        rows = [
            next(
                r
                for r in data["primary_matrix"]
                if (r["i"], r["f"], r["l"], r["history"], r["delay"]) == (i, f, 1, "single4", delay)
            )
            for i, f in ((0, 0), (0, 1), (1, 0), (1, 1))
        ]
        bar(ax, rows, labels, colors, title=f"末次强刺激后 {delay} 模拟秒")
    fig.suptitle("去掉额外强度公式后，已有机制能保留多少响应？", fontsize=15)
    fig.supxlabel(
        "单次强度 4，提示强度 0.5，既有边巩固开启。误差线：4 个固定材料块的最小值至最大值，非置信区间。", fontsize=9
    )
    save(fig, "factorial")
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8), layout="constrained")
    names = {"none": "无新经历", "single1": "单次 1", "single4": "单次 4", "repeat": "10 次 0.4"}
    palette = {"none": "#94a3b8", "single1": "#167d8d", "single4": "#d17d35", "repeat": "#8066ac"}
    for ax, (f, delay) in zip(axes.flat, ((0, 1), (0, 30), (1, 1), (1, 30))):
        for history, label in names.items():
            rows = sorted(
                (r for r in data["sensitivity"] if (r["f"], r["delay"], r["history"]) == (f, delay, history)),
                key=lambda r: r["cue"],
            )
            ax.plot(
                [r["cue"] for r in rows],
                [r["net_B"] * 1000 for r in rows],
                marker="o",
                label=label,
                color=palette[history],
            )
        ax.set_title(f"易化{'开启' if f else '关闭'}，等待 {delay} 秒", loc="left")
        ax.set_xlabel("当前提示强度")
        ax.set_ylabel("目标 B 累计激活 × 10³")
        ax.legend(fontsize=9)
    fig.suptitle("相同提示，经历不同；不同提示，反应不一定等比例", fontsize=15)
    fig.supxlabel("额外强刺激项关闭；既有边巩固开启；2 个固定材料块均值；所有值已减去同源无提示对照。", fontsize=9)
    save(fig, "sensitivity")
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), layout="constrained")
    axes = axes.ravel()
    conditions = ("unchanged", "ordinary-off", "birth-weight-off", "novelty-off", "ordinary-and-birth-off")
    rows = [
        next(
            r
            for r in data["formation"]
            if r["condition"] == name and r["f"] == 0 and r["l"] == 0 and r["history"] == "single4"
        )
        for name in conditions
    ]
    bar(
        axes[0],
        rows,
        ["正常", "无普通\n触达巩固", "无出生\n权重项", "无新颖性", "触达与出生\n两项均关"],
        ["#167d8d", "#94a3b8", "#72935a", "#d17d35", "#8066ac"],
        title="形成阶段：30 秒后测试（I0/F0/L0）",
    )
    labels, rows = [], []
    for condition, label in (
        ("unchanged", "正常"),
        ("depletion-off", "仅取消\n局部耗竭"),
        ("inhibition-response-off", "仅取消\n接收抑制"),
        ("fast-off", "仅关闭\n短时权重"),
        ("context-off", "仅关闭\n局部竞争"),
    ):
        rows.append(next(r for r in data["expression"] if r["condition"] == condition and r["delay"] == 1))
        labels.append(label)
    bar(
        axes[1],
        rows,
        labels,
        ["#94a3b8", "#d17d35", "#167d8d", "#8066ac", "#72935a"],
        title="1 秒后：只改变提示阶段（I0/F0/L1）",
    )
    rows = [
        next(
            r
            for r in data["phases"]
            if r["f"] == before and r["expression_f"] == after and r["history"] == "single4" and r["delay"] == 1
        )
        for before, after in ((0, 0), (0, 1), (1, 0), (1, 1))
    ]
    bar(
        axes[2],
        rows,
        ["关→关", "关→开", "开→关", "开→开"],
        ["#94a3b8", "#167d8d", "#d17d35", "#8066ac"],
        title="1 秒后易化：训练及等待 → 提示阶段（I0/L1）",
    )
    rows = [
        next(r for r in data["connections"] if r["condition"] == c)
        for c in ("unchanged", "silence", "restore", "matched")
    ]
    bar(
        axes[3],
        rows,
        ["正常", "静默\nA→B", "静默后\n解除", "静默其他\n匹配连接"],
        ["#167d8d", "#94a3b8", "#5da695", "#d19a44"],
        title="30 秒后：连接消融与恢复",
    )
    fig.suptitle("定位作用：当前状态影响表达，学习连接承担关联", fontsize=15)
    fig.supxlabel(
        "单次强度 4，提示 0.5；误差线为 2 个固定材料块范围。开关沿用已有状态；关闭耗竭不等于外界能量充足。", fontsize=9
    )
    save(fig, "mechanism-location")


if __name__ == "__main__":
    main()
