"""Plots from audited E22 values; no simulation and no inferred missing values."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from common import HERE, WORK, read_json

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def text(lang, zh, en):
    return zh if lang == "zh" else en


def save(fig, name, lang):
    folder = HERE / "figures"
    folder.mkdir(exist_ok=True)
    fig.savefig(
        folder / (name + ("" if lang == "zh" else ".en") + ".png"), dpi=150, bbox_inches="tight", facecolor="white"
    )
    plt.close(fig)


def value(data, group):
    return next((x["mean_margin"] for x in data["summary"] if x["group"] == group), np.nan)


def cuts(data, lang):
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.5), layout="constrained")
    groups = ["none", "N", "S", "SN", "W", "WN", "WS", "WSN"]
    for ax, (mode, learn) in zip(axes.flat, [(m, l) for m in ("full", "no_imu") for l in ("01", "11")]):
        vals = [value(data, ["cut", mode, learn, g]) for g in groups]
        ax.bar(groups, vals, color="#2d8276")
        for last, marker, color in ((False, "o", "#b74b43"), (True, "x", "#32476b")):
            points = []
            for g in groups:
                rows = [
                    r
                    for r in data["rows"]
                    if r["family"] == "cut"
                    and r["mode"] == mode
                    and r["learn"] == learn
                    and r["groups"] == g
                    and (r["sign"] == (-1 if r["seed"] % 2 else 1)) == last
                    and r["cue"]
                ]
                points.append(float(np.mean([r["margin"] for r in rows])) if rows else np.nan)
            ax.plot(
                groups,
                points,
                marker=marker,
                linestyle="none",
                color=color,
                markersize=6,
                label=text(
                    lang,
                    "教学最后方向" if last else "另一方向",
                    "Last taught direction" if last else "Other direction",
                ),
            )
        ax.axhline(0, color="#555", lw=0.8)
        ax.set_title(
            text(
                lang,
                f"{'完整感官' if mode == 'full' else '无惯性感官'} · 教学耗竭{'开' if learn == '11' else '关'}",
                f"{mode} · learning depletion {'on' if learn == '11' else 'off'}",
            )
        )
        ax.set_ylabel(text(lang, "对应目标减另一目标（激活·秒）", "Matched minus other target (activation·s)"))
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        ax.legend(fontsize=8, loc="upper left" if mode == "full" and learn == "11" else "lower left")
    fig.suptitle(
        text(
            lang,
            "只交换持久字段；接收方活动和在途信号完整保留",
            "Persistent-field exchange with receiver activity and signals retained",
        )
    )
    fig.supxlabel(
        text(
            lang,
            "柱为两方向均值，符号分列方向。W：边权；S：连接历史；N：节点历史；供体教学耗竭相反。",
            "Bars average directions; markers separate them. W: weights; S: edge history; N: node history; opposite donor depletion.",
        ),
        fontsize=9,
    )
    save(fig, "persistent-cut", lang)


def recovery(data, lang):
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), layout="constrained")
    for ax, mode in zip(axes, ("full", "no_imu")):
        for learn, color in (("01", "#bd7b3c"), ("11", "#2d8276")):
            vals = [value(data, ["cut", mode, learn, "none"])] + [
                value(data, ["recovery", mode, learn, d]) for d in (10, 30, 60)
            ]
            ax.plot(
                [1, 10, 30, 60],
                vals,
                "o-",
                color=color,
                label=text(
                    lang,
                    "教学耗竭" + ("开" if learn == "11" else "关"),
                    "Learning depletion " + ("on" if learn == "11" else "off"),
                ),
            )
        ax.axhline(0, color="#555", lw=0.8)
        ax.set_title(text(lang, "完整感官" if mode == "full" else "无惯性感官", mode))
        ax.set_xlabel(text(lang, "教学后等待（模拟秒）", "Wait after teaching (simulated s)"))
        ax.set_ylabel(text(lang, "对应目标减另一目标（激活·秒）", "Matched minus other target (activation·s)"))
        ax.grid(alpha=0.2)
        ax.legend()
    fig.suptitle(
        text(
            lang,
            "自然恢复：保留维护刺激、遗忘及正常传播",
            "Natural recovery with maintenance, forgetting and propagation",
        )
    )
    save(fig, "sensory-recovery", lang)


def timing(data, lang):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), layout="constrained")
    phases = [0, 40000, 60000]
    arrays = [
        np.array([[value(data, ["timing", tau, p, k, 30]) * 1000 for k in phases] for p in phases]) for tau in (0, 1)
    ]
    limit = max(float(np.nanmax(np.abs(a))) for a in arrays)
    for ax, tau, vals in zip(axes, (0, 1), arrays):
        im = ax.imshow(vals, cmap="BrBG", vmin=-limit, vmax=limit)
        for y in range(3):
            for x in range(3):
                ax.text(
                    x,
                    y,
                    f"{vals[y, x]:.4f}",
                    ha="center",
                    va="center",
                    color="white" if abs(vals[y, x]) > limit * 0.55 else "#222",
                )
        ax.set_xticks(range(3), [0, 40, 60])
        ax.set_yticks(range(3), [0, 40, 60])
        ax.set_xlabel(text(lang, "教学期维护偏移（ms）", "Maintenance offset during teaching (ms)"))
        ax.set_ylabel(text(lang, "教学偏移（ms）", "Teaching offset (ms)"))
        ax.set_title(
            text(lang, "易化关闭" if tau == 0 else "易化 1 秒", "Facilitation off" if tau == 0 else "Facilitation 1 s")
        )
    fig.colorbar(
        im,
        ax=axes,
        label=text(lang, "后教者减先教者（×0.001 激活·秒）", "Later minus earlier (×0.001 activation·s)"),
        shrink=0.8,
    )
    fig.suptitle(
        text(
            lang,
            "独立改变两种输入时机，保持测试条件一致",
            "Independent input timing shifts with matched test conditions",
        )
    )
    save(fig, "maintenance-timing", lang)


def references(data, lang):
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.2), layout="constrained")
    for ax, (cadence, delay) in zip(axes.flat, [(c, d) for c in ("dense", "sparse") for d in (1, 30)]):
        for i, layout in enumerate(("shared", "separate")):
            counts = []
            for cue in ("X", "Z", "XZ"):
                rs = [p for p in data["pairs"] if p["group"] == ["reference", cadence, layout, delay, cue]]
                counts.append(sum(p["bidirectional_1e6"] for p in rs) if len(rs) == 4 else np.nan)
            ax.bar(
                np.arange(3) + (i - 0.5) * 0.35,
                counts,
                width=0.35,
                color=("#2d8276", "#bd7b3c")[i],
                label=text(lang, "共享" if i == 0 else "独立", layout),
            )
        ax.set_xticks(range(3), ["X", "Z", "X+Z"])
        ax.set_ylim(0, 4.6)
        ax.set_yticks(range(5))
        ax.set_title(
            text(lang, f"{'密集' if cadence == 'dense' else '稀疏'} · 等待 {delay} 秒", f"{cadence} · wait {delay} s")
        )
        ax.set_ylabel(text(lang, "双向顺序表达材料块数 / 4", "Blocks with bidirectional expression / 4"))
        ax.legend()
    fig.suptitle(
        text(lang, "每通道曝光量匹配后的共同参照对照", "Shared-reference controls with per-channel exposures matched")
    )
    fig.supxlabel(
        text(
            lang,
            "联合提示总量与单参照相同；四块主要改变匿名身份，不是独立生态样本。",
            "Joint and single cues have equal total dose; four identity blocks are not independent ecologies.",
        ),
        fontsize=9,
    )
    save(fig, "balanced-references", lang)


if __name__ == "__main__":
    data = read_json(WORK / "final.json")
    for lang in ("zh", "en"):
        for plot in (cuts, recovery, timing, references):
            family = {cuts: "cut", recovery: "recovery", timing: "timing", references: "reference"}[plot]
            if any(r["family"] == family for r in data["rows"]):
                plot(data, lang)
