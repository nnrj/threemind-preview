"""Publication figures from fixed, audited analysis tables; no model execution."""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from runner import HERE, WORK

from lab.tools.service_study import read_json

COLORS = ("#278176", "#ca7945", "#546ca6", "#ad5886")


def choose(lang, zh, en):
    return zh if lang == "zh" else en


def save(fig, name, lang):
    # YaHei supplies Chinese, while mathtext supplies complete exponent glyphs.
    from matplotlib.text import Text

    for artist in fig.findobj(Text):
        artist.set_text(artist.get_text().replace("10⁻³", r"$10^{-3}$").replace("10⁻⁶", r"$10^{-6}$"))
    folder = HERE / "figures"
    folder.mkdir(exist_ok=True)
    suffix = "" if lang == "zh" else ".en"
    fig.savefig(folder / f"{name}{suffix}.png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def retention(data, lang):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), layout="constrained", sharey=True)
    taus = [0, 0.3, 1, 3]
    for ax, delay in zip(axes, (1, 30, 300)):
        for i in (0, 1):
            for j, tau in enumerate(taus):
                rows = [
                    r
                    for r in data["rows"]
                    if r["cue"]
                    and r["profile"] == "default"
                    and r["interference"] == "none"
                    and r["history"] == "single4"
                    and r["delay"] == delay
                    and r["i"] == i
                    and r["tau"] == tau
                ]
                values = [r["net_B"] * 1000 for r in rows]
                x = j + (i - 0.5) * 0.32
                label = (
                    choose(lang, "额外项关" if i == 0 else "额外项开", "Extra term off" if i == 0 else "Extra term on")
                    if j == 0
                    else None
                )
                ax.bar(x, mean(values), width=0.3, color=COLORS[i], alpha=0.75, label=label)
                ax.scatter(
                    [x - 0.065 + k * 0.043 for k in range(len(values))],
                    values,
                    s=18,
                    color=COLORS[i],
                    edgecolors="white",
                    linewidths=0.4,
                    zorder=3,
                )
        ax.set_title(f"{delay} " + choose(lang, "模拟秒后", "simulated seconds later"))
        ax.set_xticks(range(4), ["0", "0.3", "1", "3"])
        ax.set_xlabel(choose(lang, "从创建时设置的易化时间常数（秒）", "Facilitation tau from creation (s)"))
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
    axes[0].set_ylabel(choose(lang, "B 净累计激活（×10⁻³ 激活·秒）", "Net B integral (×10⁻³ activation·s)"))
    axes[0].legend(fontsize=9)
    fig.suptitle(
        choose(
            lang,
            "易化与额外强刺激项：短时唤起、较长保持分别看",
            "Facilitation and the extra term: expression and retention separately",
        ),
        fontsize=14,
    )
    fig.supxlabel(
        choose(
            lang,
            "单次强度 4；提示 0.5。柱为四个固定材料块均值，点为每块结果；非独立随机样本。",
            "Single intensity 4; cue 0.5. Bars: means of four fixed blocks; dots: each block, not independent random samples.",
        ),
        fontsize=9,
    )
    save(fig, "retention", lang)


def interference(data, lang):
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout="constrained", sharey=True)
    conditions = ("none", "AC", "EF")
    for ax, (i, tau) in zip(axes.flat, ((0, 0), (1, 0), (0, 1), (1, 1))):
        for symbol, color in zip("BC", COLORS):
            series = []
            for condition in conditions:
                values = [
                    r[f"net_{symbol}"] * 1000
                    for r in data["rows"]
                    if r["cue"]
                    and r["profile"] == "default"
                    and r["history"] == "single4"
                    and r["delay"] == 30
                    and r["i"] == i
                    and r["tau"] == tau
                    and r["interference"] == condition
                ]
                series.append(mean(values))
            ax.plot(range(3), series, "o-", color=color, label=symbol)
        ax.set_title(
            choose(
                lang,
                f"额外项 {'开' if i else '关'}；易化 {tau} 秒",
                f"Extra term {'on' if i else 'off'}; facilitation {tau} s",
            )
        )
        ax.set_xticks(range(3), [choose(lang, "无后续教学", "No teaching"), "AC × 10", "EF × 10"])
        ax.set_ylabel(choose(lang, "净累计激活（×10⁻³）", "Net integral (×10⁻³)"))
        ax.grid(axis="y", alpha=0.2)
        ax.legend()
    fig.suptitle(
        choose(
            lang,
            "相同 A 提示，之后的经历能怎样改变 B 与 C 的响应？",
            "Same A cue: how does intervening experience change B and C?",
        ),
        fontsize=14,
    )
    fig.supxlabel(
        choose(
            lang,
            "AB 单次强度 4 后，分别重复 AC 或 EF；原教学后第 30 秒探测。四个材料块均值。",
            "After a single AB input of 4, repeat AC or EF; probe at 30 s after original teaching. Four-block means.",
        ),
        fontsize=9,
    )
    save(fig, "interference", lang)


def reversal(data, lang):
    selected = ("1111", "1110", "1101", "1011", "0111", "0000", "silence")
    zh = ("原配置", "关抑制响应", "关局部竞争", "关短时连接变化", "关局部耗竭", "四项全关", "静默原有连接")
    en = (
        "Original",
        "Inhibitory response off",
        "Local competition off",
        "Fast trace off",
        "Depletion off",
        "All four off",
        "Existing edges silent",
    )
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), layout="constrained")
    for ax, mode in zip(axes, ("full", "no_imu")):
        rows = {r["variant"]: r for r in data["summary"] if r["mode"] == mode}
        values = [rows[v]["whole_mean"] for v in selected]
        bars = ax.barh(
            range(len(selected)), values, color=[COLORS[0] if v >= 0 else COLORS[1] for v in values], alpha=0.72
        )
        ax.bar_label(bars, labels=[f"{v:.4g}" if v >= 0 else "" for v in values], padding=12, fontsize=8)
        for index, value in enumerate(values):
            if value < 0:
                ax.annotate(
                    f"{value:.4g}", (0, index), xytext=(14, 0), textcoords="offset points", va="center", fontsize=8
                )
        for index, variant in enumerate(selected):
            cases = [
                r["margin_whole"]
                for r in data["rows"]
                if r["mode"] == mode and r["variant"] == variant and r["physical"]
            ]
            ax.scatter(cases, [index - 0.2 + k * 0.055 for k in range(len(cases))], s=11, color="#333333", zorder=3)
        ax.margins(x=0.18)
        ax.axvline(0, color="#555", linewidth=0.8)
        ax.set_yticks(range(len(selected)), zh if lang == "zh" else en)
        ax.invert_yaxis()
        ax.set_title(
            choose(
                lang, "完整感官" if mode == "full" else "无惯性感官", "Full senses" if mode == "full" else "Without IMU"
            )
        )
        ax.set_xlabel(choose(lang, "全程方向差（激活·秒）", "Whole-window directional margin (activation·s)"))
        ax.grid(axis="x", alpha=0.2)
        ax.set_axisbelow(True)
    fig.suptitle(
        choose(
            lang,
            "反向响应定位：正数为原对应方向，负数为反向",
            "Locating reversal: positive = original correspondence, negative = reversed",
        ),
        fontsize=14,
    )
    fig.supxlabel(
        choose(
            lang,
            "同父本、测试时切换；减去无物理输入。点为 4 块 × 2 方向，柱为均值；左右横轴独立。全部 16 组合见表。",
            "Switch at test; matched no-input subtraction. Dots: 4 blocks × 2 directions; bars: means. Separate x-scales. All 16 combinations in tables.",
        ),
        fontsize=9,
    )
    save(fig, "reversal", lang)


def sequence(data, lang):
    groups = defaultdict(list)
    for r in data["pairs"]:
        if r["shared"]:
            groups[(r["tau"], r["gap_s"], r["delay_s"])].append(r)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), layout="constrained", sharey=True)
    for ax, tau in zip(axes, (0, 1)):
        for j, gap in enumerate((0.05, 0.5, 2)):
            counts = [sum(r["bidirectional_1e6"] for r in groups[(tau, gap, d)]) for d in (1, 30, 300)]
            bars = ax.bar([x + (j - 1) * 0.25 for x in range(3)], counts, width=0.23, color=COLORS[j], label=f"{gap} s")
            ax.bar_label(bars, fmt="%d", padding=3, fontsize=9)
        ax.set_ylim(-0.15, 5.2)
        ax.set_yticks(range(5))
        ax.set_xticks(range(3), ["1", "30", "300"])
        ax.set_title(choose(lang, f"易化 {tau} 秒", f"Facilitation {tau} s"))
        ax.set_xlabel(choose(lang, "等待时间（模拟秒）", "Delay (simulated seconds)"))
        ax.grid(alpha=0.2)
        ax.legend(title=choose(lang, "刺激间隔", "Input interval"), loc="upper right", fontsize=8)
        ax.set_axisbelow(True)
    axes[0].set_ylabel(choose(lang, "双向顺序表达的材料块数 / 4", "Blocks with bidirectional order expression / 4"))
    fig.suptitle(
        choose(
            lang,
            "相同末次输入、相同 X 提示，能否读出不同次序？",
            "Same last input and X cue: can the two orders be distinguished?",
        ),
        fontsize=14,
    )
    fig.supxlabel(
        choose(
            lang,
            "含共同参照 AX/BX；两个次序必须产生异号的 A−B 差异，门槛 10⁻⁶。既不假定近因优势，也不假定首因优势。",
            "Shared-reference AX/BX; A−B must reverse sign between orders, threshold 10⁻⁶. Neither recency nor primacy is prescribed.",
        ),
        fontsize=9,
    )
    save(fig, "sequence", lang)


def sequence_example(lang):
    """Fixed first registered block, with the whole observed response window."""
    from sequence import ids

    channels = ids(100121)
    root = WORK / "cases/sequence/100121/f0/shared1/gap0.05"
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.6), layout="constrained", sharey="row")
    for column, order in enumerate(("AB", "BA")):
        folder = root / order / "wait30"
        before = json.loads(gzip.decompress((folder / "cue0.5/pre-probe.json.gz").read_bytes()))
        identities = {n["channel"]: n["id"] for n in before["nodes"]}
        weights = [
            next(
                (
                    e["weight"]
                    for e in before["edges"]
                    if (e["source"], e["target"]) == (identities[channels["X"]], identities[channels[letter]])
                ),
                0.0,
            )
            for letter in "AB"
        ]
        bars = axes[0, column].bar(["X → A", "X → B"], weights, color=COLORS[:2], alpha=0.8)
        axes[0, column].bar_label(bars, fmt="%.5f", padding=4, fontsize=9)
        axes[0, column].set_ylim(0, max(weights) * 1.25)
        axes[0, column].set_title(choose(lang, f"教学顺序 {order}", f"Teaching order {order}"))
        cued, uncued = [
            json.loads(gzip.decompress((folder / cue / "trajectory.json.gz").read_bytes()))
            for cue in ("cue0.5", "cue0")
        ]
        start = int(cued[0]["time_us"])
        baseline = {int(p["time_us"]): {n["channel"]: n["activation"] for n in p["nodes"]} for p in uncued}
        for letter, color in zip("AB", COLORS):
            values = []
            for point in cued:
                at = int(point["time_us"])
                value = next((n["activation"] for n in point["nodes"] if n["channel"] == channels[letter]), 0.0)
                values.append(value - baseline[at].get(channels[letter], 0.0))
            axes[1, column].plot([(int(p["time_us"]) - start) / 1e6 for p in cued], values, label=letter, color=color)
        axes[1, column].set_xlim(0, 5)
        axes[1, column].legend()
        axes[1, column].set_xlabel(choose(lang, "同样 X 提示后的模拟秒", "Simulated seconds after identical X cue"))
        for ax in axes[:, column]:
            ax.grid(axis="y", alpha=0.2)
            ax.set_axisbelow(True)
    axes[0, 0].set_ylabel(choose(lang, "提示前连接权重", "Edge weight before cue"))
    axes[1, 0].set_ylabel(choose(lang, "净激活：有提示 − 无提示", "Net activation: cued − uncued"))
    fig.suptitle(
        choose(lang, "顺序改变留下的连接，也改变后来的响应", "Order changes retained connections and later responses"),
        fontsize=14,
    )
    fig.supxlabel(
        choose(
            lang,
            "固定示例 100121：50 ms 间隔、易化关、等待 30 秒；末次输入均为 Y。图示 A/B，原数据保留全部通道。",
            "Fixed block 100121: 50 ms interval, facilitation off, 30 s delay; identical final Y input. A/B shown; all channels retained.",
        ),
        fontsize=9,
    )
    save(fig, "sequence-example", lang)


if __name__ == "__main__":
    plt.rcParams.update(
        {
            "font.family": "Microsoft YaHei",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.unicode_minus": False,
        }
    )
    main = read_json(WORK / "analysis-final.json")
    reverse = read_json(WORK / "reversal-final.json")
    order = read_json(WORK / "sequence-final.json")
    for lang in ("zh", "en"):
        retention(main, lang)
        interference(main, lang)
        reversal(reverse, lang)
        sequence(order, lang)
        sequence_example(lang)
