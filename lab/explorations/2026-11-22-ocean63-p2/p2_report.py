from p1_report import fmt, remaining_sections, scientific_conclusions


def report(findings, lang):
    def tr(zh, en):
        return zh if lang == "zh" else en

    lines = [
        tr("# OCEAN63-P2　幼体、亲代哺育与环境选择", "# OCEAN63-P2. Juvenile growth, parental care and selection"),
        "",
        tr(
            "两个独立水域各设每 1 秒与每 8 秒补一颗营养的配对条件。个体从小身体开始，生长消耗自身储备，每胎三个。亲缘保护和接触哺育规则适用于四个世界。",
            "Each of two independent habitats had a reference and a sparse food supply, one particle every 1 or 8 seconds. Individuals began small, paid for growth and had litters of three. All worlds used the same kin protection and parental feeding rules.",
        ),
        "",
        tr(
            "| 水域与供给 | 观测秒数 | 最高代次 | 出生数 | 期末存活 | 营养颗粒 | 活体捕食 | 食腐取食次数 |",
            "| World and supply | Seconds | Highest generation | Births | Surviving | Grains | Live kills | Carrion meals |",
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, c in findings["cases"].items():
        lines.append(
            f"| {name} | {c['seconds']:g} | {c['maximum_generation']} | {c['births']} | {c['alive']} | {c['grains']} | {c['predations']} | {c['carrion_meals']} |"
        )
    lines += [
        "",
        tr(
            "| 世界 | 第 1–2／3–5 代捕食率¹ | 早期捕食者人数／存活子代 | 其他个体人数／存活子代 | 分层后差值 |",
            "| World | Kill rate¹ in G1–2 / G3–5 | Early hunters / surviving children | Other individuals / surviving children | Adjusted difference |",
        ),
        "|---|---:|---:|---:|---:|",
    ]
    for name, c in findings["cases"].items():
        r = c["reproduction"]
        h, o = (r["groups"][role] for role in ("hunter", "other"))
        lines.append(
            f"| {name} | {fmt(c['early_rate'])} / {fmt(c['late_rate'])} | {h['eligible']} / {h['surviving_children']} | {o['eligible']} / {o['surviving_children']} | {fmt(r['adjusted_difference'])} |"
        )
    lines += [
        "",
        tr(
            "¹ 出生后前 180 秒每 100 个体存活分钟内活体捕食次数。",
            "¹ Live kills per 100 living-body minutes over the first 180 seconds of life.",
        ),
        "",
    ]
    lines.extend(scientific_conclusions(findings["outcomes"], lang))
    lines += [
        "",
        tr(
            "| 世界 | 接触亲代的幼体 | 得到哺育的幼体 | 接触总秒数 | 转入能量 | 生长耗能 | 平均每胎支出 |",
            "| World | Young contacting parent | Young receiving energy | Contact seconds | Energy transferred | Growth cost | Mean litter bill |",
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, c in findings["cases"].items():
        care = list(c["nursing_by_child"].values())
        bills = c["birth_bills"]
        lines.append(
            f"| {name} | {len(care)} | {sum(r['received'] > 0 for r in care)} | {sum(r['contact_seconds'] for r in care):.2f} | {sum(r['received'] for r in care):.3f} | {c['paid_growth']:.3f} | {fmt(sum(bills) / len(bills) if bills else None)} |"
        )
    return remaining_sections(findings, lang, lines)
