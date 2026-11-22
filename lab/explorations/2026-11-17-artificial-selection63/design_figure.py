"""Draw the registered study flow; this schematic contains no measured results."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

import figures


def draw(lang):
    zh = lang == "zh"
    figures.config(lang)
    fig, ax = plt.subplots(figsize=(13.0, 8.2))
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    labels = {
        "title": "AS63-01：先测亲代，再检验后代" if zh else "AS63-01: Assess the parent, then test the descendants",
        "subtitle": ("16个独立群体 · 每群体4名G0候选 · G0→G1→G2 · 主实验区域布局固定"
                     if zh else "16 independent populations · 4 G0 candidates each · G0 → G1 → G2 · Fixed primary layout"),
        "candidate": ("每代4名候选原体\n各连续培养60内部秒\n保存完整当前状态"
                      if zh else "4 original candidates per generation\n60 internal seconds of development\nSave complete current state"),
        "selection": ("选择评估：2个起点\n从完整状态复制，不调用出生\n计算平均区域1停留比例"
                      if zh else "Selection assessment: 2 starts\nComplete-state copies; no birth\nMean region 1 occupancy"),
        "held": ("保留测试：另4个起点\n从同一完整状态复制\n成绩不用于选择亲代"
                 if zh else "Held-out assessment: 4 other starts\nCopies of the same complete state\nScores excluded from selection"),
        "parents": ("每条件选2名候选原体\n区域0：最低分；区域1：最高分\n随机：不读取成绩"
                    if zh else "Select 2 original candidates per arm\nRegion 0: lowest; region 1: highest\nRandom: independent of scores"),
        "measure": ("比较各代全部候选\n每名先平均4个起点\n再平均群体内4名候选"
                    if zh else "Compare every candidate in each generation\nAverage 4 starts within candidates\nThen 4 candidates within populations"),
        "birth": ("每名亲代产生2名子代\n每条件4名组成下一代\nthreemind.birth/2 · preserve"
                  if zh else "2 offspring per selected parent\n4 offspring per arm in the next generation\nthreemind.birth/2 · preserve"),
        "blank": ("每个子代配1名空白内核对照\n不继承亲代内核状态\n外设、起点及培养相同"
                  if zh else "1 uninherited control per offspring\nBlank Core; no parental Core state\nSame peripherals, starts, development"),
        "outcome": ("分别检验四个问题\n倾向保留 · 选择收益\n逐代增强 · 继承收益"
                    if zh else "Four separate questions\nRetention · Selection advantage\nAccumulation · Inheritance benefit"),
    }
    ax.text(.5, .965, labels["title"], ha="center", va="top", weight="bold", fontsize=17)
    ax.text(.5, .905, labels["subtitle"], ha="center", va="top", fontsize=10.5, color="#465665")

    def box(x, y, name, *, face="#f2f6f8"):
        width, height = .27, .15
        ax.add_patch(FancyBboxPatch((x,y), width, height, boxstyle="round,pad=0.008,rounding_size=0.008",
                                   facecolor=face, edgecolor="#526676", linewidth=1.1))
        ax.text(x+width/2, y+height/2, labels[name], ha="center", va="center", fontsize=9.3, linespacing=1.55)

    def arrow(points, color="#526676", dashed=False):
        for a,b in zip(points[:-2], points[1:-1]):
            ax.plot([a[0],b[0]], [a[1],b[1]], color=color, lw=1.2, ls="--" if dashed else "-")
        ax.annotate("", xy=points[-1], xytext=points[-2],
                    arrowprops={"arrowstyle":"-|>", "color":color, "lw":1.2,
                                "linestyle":"--" if dashed else "-", "mutation_scale":12})

    for x, y, name in ((.035,.68,"candidate"),(.365,.68,"selection"),(.695,.68,"held"),
                       (.035,.405,"parents"),(.695,.405,"measure"),
                       (.035,.13,"birth"),(.365,.13,"blank"),(.695,.13,"outcome")):
        box(x,y,name,face="#eaf4f9" if name in ("candidate","parents","birth") else "#f5f7f8")
    arrow([(.313,.755),(.357,.755)])
    arrow([(.17,.838),(.17,.865),(.83,.865),(.83,.838)])
    ax.text(.51,.851,"完整状态复制" if zh else "Complete-state copies",ha="center",va="center",fontsize=8.5,
            bbox={"facecolor":"white","edgecolor":"none","pad":1})
    arrow([(.17,.672),(.17,.563)])
    ax.text(.178,.62,"原体保持不变" if zh else "Original stays unchanged",ha="left",va="center",fontsize=8.5)
    arrow([(.50,.672),(.50,.48),(.313,.48)])
    ax.text(.51,.565,"评分用于选择原体" if zh else "Scores select original candidates",ha="left",va="center",fontsize=8.5)
    arrow([(.83,.672),(.83,.563)])
    arrow([(.83,.397),(.83,.288)])
    arrow([(.17,.397),(.17,.288)])
    ax.text(.178,.343,"仅此处调用出生" if zh else "Birth only here",ha="left",va="center",fontsize=8.5)
    arrow([(.313,.205),(.357,.205)],dashed=True)
    arrow([(.643,.205),(.687,.205)],dashed=True)
    ax.text(.5,.075,("所有评估副本连续运行60内部秒；评估经历不写回原体。G2不再繁殖。独立N=16个群体。"
                    if zh else "Each assessment runs continuously for 60 internal seconds; experience is not written back. G2 does not reproduce. Independent N = 16."),
            ha="center",va="center",fontsize=9.1)
    fig.tight_layout(pad=.5)
    figures.save(fig,"06-study-design",lang)


if __name__ == "__main__":
    for lang in ("zh","en"):
        draw(lang)
    print("Bilingual registered-design schematic saved")
