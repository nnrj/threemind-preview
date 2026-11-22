"""Generate both editions from the same world-level denominators and decisions."""


def fmt(x):
    return "—" if x is None else f"{x:.3f}"


def scientific_report(data, lang):
    zh = lang == "zh"
    text = lambda a, b: a if zh else b
    lines = [
        text("# OCEAN63-P1　营养供应如何影响捕食与繁殖", "# OCEAN63-P1. Food supply, predation and reproduction"),
        "",
        text(
            "我们从两个独立水域初态分别建立两个世界。每个世界最初有53个个体和53颗营养。正常供给每秒补充一颗，低供给每八秒补充一颗。大个体首次接触小个体即可吞食，亲代为每胎的两个子代支付全部费用。我们检验后几代的捕食是否更常见，以及捕食亲代留下的存活子代是否更多。",
            "We created a pair of worlds from each of two independent initial habitats, each with 53 founders and 53 grains. The reference worlds received one grain per simulated second and the sparse worlds one every eight seconds. A larger individual consumed a smaller one upon contact. Parents paid for both offspring in each litter. We asked whether predation became more frequent over generations and whether early hunters left more surviving offspring.",
        ),
        "",
        text(
            "| 水域－供给 | 终点（内部秒） | 最高代次 | 出生／期末存活 | 颗粒／食腐／活体捕食 | 颗粒／遗体／活体转入能量 |",
            "| World and supply | Endpoint (simulated s) | Highest generation | Births / survivors | Grains / scavenging / live kills | Energy from grains / carcasses / prey |",
        ),
        "|---|---:|---:|---:|---:|---:|",
    ]
    for k, c in data["cases"].items():
        lines.append(
            f"| {k} | {c['seconds']:.2f} | {c['maximum_generation']} | {c['births']} / {c['alive']} | {c['grains']} / {c['carrion_meals']} / {c['predations']} | {c['grain_energy']:.1f} / {c['carrion_energy']:.1f} / {c['live_energy']:.1f} |"
        )
    lines += [
        "",
        text("## 捕食的代际变化与存活子代", "## Predation across generations and surviving offspring"),
        "",
        text(
            "捕食率以个体出生后前180秒的实际存活时间为分母，单位为每100存活身体分钟。早期合并第1、2代，后期合并第3至5代。亲代按本人前60秒是否捕食分组，统计此后120秒内出生且活到60秒的子代，包括留下零个存活子代的个体。校正差值在同代、相近出生体型的个体间比较。",
            "Rates count live kills per 100 living-body minutes during the first 180 seconds of life. The early cohort pools generations 1 and 2, and the late cohort generations 3 to 5. We classified individuals by predation during their own first 60 seconds and counted offspring born during the next 120 seconds that survived to age 60. Individuals with no surviving offspring were included. The adjusted difference compares individuals of the same generation and similar size at birth.",
        ),
        "",
        text(
            "| 水域－供给 | 早期／后期捕食率 | 早期捕食者人数／其存活子代数 | 其余个体人数／其存活子代数 | 每亲代校正差值 |",
            "| World and supply | Early / late predation rate | Early hunters / surviving offspring | Other individuals / surviving offspring | Adjusted difference per individual |",
        ),
        "|---|---:|---:|---:|---:|",
    ]
    for k, c in data["cases"].items():
        r = c["reproduction"]
        h = r["groups"]["hunter"]
        o = r["groups"]["other"]
        lines.append(
            f"| {k} | {fmt(c['early_rate'])} / {fmt(c['late_rate'])} | {h['eligible']} / {h['surviving_children']} | {o['eligible']} / {o['surviving_children']} | {fmt(r['adjusted_difference'])} |"
        )
    outcomes = data["outcomes"]
    lines.append("")
    lines.extend(scientific_conclusions(outcomes, lang))
    return remaining_sections(data, lang, lines)


def scientific_conclusions(outcomes, lang):
    options = {
        "predation_over_generations": {
            "supported": (
                "两座低供给水域中，后几代的捕食率都高于前两代。",
                "In both sparse worlds, later generations had a higher predation rate.",
            ),
            "not_met": (
                "低供给水域的代际变化没有一致达到预期。",
                "The generational changes in the sparse worlds did not consistently meet the prediction.",
            ),
            "insufficient": (
                "至少一座低供给水域缺少可比较的早期或后期世代，代际变化无法作双水域判断。",
                "At least one sparse habitat lacked an observable early or late cohort, preventing a two-habitat conclusion.",
            ),
        },
        "extra_change_under_lower_supply": {
            "supported": (
                "两座水域中，减粮后的代际增幅均大于正常供给。",
                "In both habitat pairs, the generational change was larger under sparse supply.",
            ),
            "not_met": (
                "两组供给对照未显示减粮一致增大代际增幅。",
                "The paired comparisons did not show a consistently greater generational increase under sparse supply.",
            ),
            "insufficient": (
                "至少一条供给分支缺少可比世代，无法在两个水域比较减粮的作用。",
                "At least one supply branch lacked comparable generations, preventing a two-habitat comparison of the supply effect.",
            ),
        },
        "surviving_offspring": {
            "supported": (
                "控制代次和出生体型后，两座低供给水域中有早期捕食记录的个体都留下了更多存活子代。",
                "After accounting for generation and size at birth, early hunters left more surviving offspring in both sparse habitats.",
            ),
            "not_met": (
                "控制代次和出生体型后，早期捕食者没有在两座低供给水域中都留下更多存活子代。",
                "After accounting for generation and size at birth, early hunters did not leave more surviving offspring in both sparse habitats.",
            ),
            "insufficient": (
                "至少一座低供给水域没有同代且体型相近、早期捕食经历又不同的两类个体，无法完成两座水域的亲代比较。",
                "At least one sparse world lacked both early hunters and comparison individuals of the same generation and size class, preventing a two-habitat comparison of reproductive output.",
            ),
        },
    }
    return [messages[outcomes[key]][0 if lang == "zh" else 1] for key, messages in options.items()]


def remaining_sections(data, lang, lines):
    zh = lang == "zh"
    text = lambda a, b: a if zh else b
    outcomes = data["outcomes"]
    lines += [
        "",
        text(
            "亲代在年龄240内部秒时的家系存活数也逐家统计。下表列出两类亲代当时的全部存活后代数（包括孙代），以及近亲在活体捕食中所占的次数。同一只后代可能同时属于不同世代祖先的家系。",
            "We also counted all living descendants, including grandchildren, at each eligible individual's age of 240 simulated seconds. Descendants can belong to the lineages of ancestors in more than one generation. The table includes the number of live kills involving immediate relatives.",
        ),
        "",
        text(
            "| 水域－供给 | 早期捕食者／其余个体的存活后代 | 亲子间捕食 | 同胞间捕食 | 其余活体捕食 |",
            "| World and supply | Living descendants of early hunters / others | Parent–offspring kills | Sibling kills | Other live kills |",
        ),
        "|---|---:|---:|---:|---:|",
    ]
    for k, c in data["cases"].items():
        groups = c["reproduction"]["groups"]
        kin = c["predation_kin"]
        lines.append(
            f"| {k} | {groups['hunter']['living_descendants_at_240']} / {groups['other']['living_descendants_at_240']} | {kin.get('parent_child', 0)} | {kin.get('siblings', 0)} | {kin.get('other', 0)} |"
        )
    lines += [
        "",
        text("## 个体如何转弯", "## Observed turns"),
        "",
        text(
            "| 水域－供给 | 转弯摄入颗粒／个体 | 转弯捕食活体／个体 | 转弯躲避／个体 | 接近机会／双方均完整观察5秒 |",
            "| World and supply | Turns to grains / individuals | Turns to live prey / individuals | Evasive turns / individuals | Closing encounters / both observed for 5 s |",
        ),
        "|---|---:|---:|---:|---:|",
    ]
    for k, c in data["cases"].items():
        f = c["food_turns"]
        p = c["pursuit"]
        e = c["escape"]
        lines.append(
            f"| {k} | {f['turns']} / {f['individuals']} | {len(p)} / {len({v['predator'] for v in p})} | {len(e)} / {len({v['small'] for v in e})} | {c['eligible_approaches']} / {c['observed_pairs_5s']} |"
        )
    lines.append("")
    for k, cn, en in (
        ("food_turns", "转弯摄入营养颗粒", "Turning to a grain and ingesting it"),
        ("pursuit", "转向活体并捕食", "Turning towards and consuming live prey"),
        ("escape", "转弯躲避较大个体", "Turning away from a larger individual on a collision course"),
    ):
        n = outcomes[k]["worlds_with_observations"]
        if n:
            lines.append(
                text(
                    f"{n} 座独立水域中观察到了{cn}。",
                    f"{en} was observed in {n} independent habitat{'s' if n != 1 else ''}.",
                )
            )
        else:
            lines.append(
                text(
                    f"按预定的运动判据，本批未观察到{cn}。",
                    f"No recorded event met the prespecified criteria for {en.lower()}.",
                )
            )
    lines += [
        "",
        text(
            "按个体、世代、亲缘和实际时刻的结果在 analysis/findings.json 中。表中横线表示缺少分母或可配对个体。水域配对和全体事件的取样单位见冻结方案。",
            "The file analysis/findings.json provides measurements by individual, generation, kinship and event time. A dash marks a missing denominator or comparison group. The frozen protocol defines the habitat pairs and observation units.",
        ),
    ]
    return "\n".join(lines) + "\n"
