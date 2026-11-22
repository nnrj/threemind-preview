"""Generate bilingual reports from the independent event and exposure audit."""
from ocean_results import analyze
from registration import directory, TITLES
from map_view import from_case

EN={"28":"Feeding and reproduction with finite energy","30":"Neural propagation and feeding",
    "38":"Food supply, predation and descent","39C":"Scavenging and natural selection across generations"}

HISTORICAL={"28":"2026-10-03-primitive-ocean","30":"2026-10-03-ocean-causality","38":"2026-10-04-ocean-species"}


def f(x):
    return "—" if x is None else f"{x:.3f}"


def historical_comparison(code,data,english):
    if code not in HISTORICAL:
        return []
    cases=data["cases"]
    def tr(zh,en):
        return en if english else zh
    result=[tr("## 与历史实验的同口径比较","## Comparison with the historical observations")]
    if code=="30":
        table=[tr("| 水域 | 控制方式 | 旧版颗粒数 | 6.3 颗粒数 | 旧版颗粒/身体分钟 | 6.3 颗粒/身体分钟 |",
                  "| World | Controller | Historical grains | 6.3 grains | Historical grains/body-min | 6.3 grains/body-min |"),
               "|---|---|---:|---:|---:|---:|"]
        for g,mode,n,rate in ((0,"core",401,3.497),(0,"random",268,2.537),(0,"random-fast",46,.297),
                              (1,"core",355,3.459),(1,"random",324,2.477),(1,"random-fast",35,.252)):
            r=cases[f"world-{g}-{mode}"]
            table.append(f'| {g+1} | {mode} | {n} | {r["grains"]} | {f(rate)} | {f(r["grain_rate"])} |')
        result.append("\n".join(table))
    if code=="28":
        table=[tr("| 控制方式 | 旧版颗粒数 | 6.3 颗粒数 | 旧版出生 | 6.3 出生 | 旧版期末存活 | 6.3 期末存活 |",
                  "| Controller | Historical grains | 6.3 grains | Historical births | 6.3 births | Historical survivors | 6.3 survivors |"),
               "|---|---:|---:|---:|---:|---:|---:|"]
        for mode,food,births,alive in (("core",1006,24,48),("passive",137,0,0),("random",1005,24,47)):
            rows=[cases[f"ecology-{g}-{mode}"] for g in range(3)]
            table.append(f'| {mode} | {food} | {sum(r["grains"] for r in rows)} | {births} | {sum(r["births"] for r in rows)} | {alive} | {sum(r["alive"] for r in rows)} |')
        result.append("\n".join(table))
    if code=="38":
        result.append(tr("旧 E38 选取本人已捕食的 59 号，以保存于 300 内部秒的状态建立候选谱系。6.3 保存新亲代自身首次符合条件的捕食事件当步状态。比较到两个旧分支都实际运行过的 600 内部秒。",
            "Historical E38 used the saved state of individual 59 at 300 internal seconds, after its own predation event. The 6.3 study saves the new parent's state at its first qualifying event. Both historical branches were observed through 600 internal seconds."))
        common=cases["common"]
        obs=data["targets"]["supply"].get(600) or data["targets"]["supply"].get("600")
        if obs:
            table=[tr("| 供给 | 旧版累计颗粒 | 6.3 累计颗粒 | 旧版累计出生 | 6.3 累计出生 | 旧版减粮时点后捕食 | 6.3 同期捕食 |",
                      "| Supply | Historical total grains | 6.3 total grains | Historical total births | 6.3 total births | Historical post-fork predations | 6.3 post-fork predations |"),
                   "|---|---:|---:|---:|---:|---:|---:|"]
            for key,n,b in (("original",858,24),("reduced",740,21)):
                r=obs[key]
                table.append(f'| {key} | {n} | {common["grains"]+r["grains"]} | {b} | {common["births"]+r["births"]} | 0 | {r["predations"]} |')
            result.append("\n".join(table))
    lang="en" if english else "zh"
    result.append(tr("历史数据取自仓库中的 ","Historical source in the repository: ")+
                  f'`lab/explorations/{HISTORICAL[code]}/report.r2.{lang}.md`.')
    return result


def write_report(code,data,english):
    t,c=data["targets"],data["cases"]
    def tr(zh,en):
        return en if english else zh
    def verdict(v):
        if v is None:
            return tr("缺少完成比较的个体或观察","insufficient observations")
        return tr("达到预定标准","met the criterion") if v else tr("未达到预定标准","did not meet the criterion")
    s=[f"# OCEAN63-{code}　"+(EN[code] if english else TITLES[code])]
    if code=="30":
        s+=[tr("我们用两个独立环境初态分别比较了四种控制方式。四组都接收身体运动带来的后续感知，创始个体每组 31 个。",
               "Starting from each of two independent environments, we compared four controllers. Each group began with 31 individuals and received the sensory consequences of its own movements."),
            tr("内核控制与两种随机控制的摄食比较","Feeding with Core control versus both random controls")+" — "+verdict(t["full_exceeds_random"])+".",
            tr("完整内核相对直接感官响应的摄食率差值，两个环境各为 ","The differences in feeding rate between full propagation and direct sensory responses were ")+
            ", ".join(map(f,t["differences_direct"]))+tr(" 颗/存活身体分钟。两个环境一致增益的检验"," grains per living body-minute in the two environments. Consistent gain")+" — "+verdict(t["internal_gain"])+".",
            tr("直接响应组仍使用本个体的内核和外设。两种传导在新生时关闭，个体此后的运动、感知和能量消耗共同参与了比较。",
               "The direct-response control retained its own Core and peripherals. Propagation and inhibitory diffusion were disabled from birth, so subsequent action, sensation and energy use contributed to the observed difference.")]
    elif code=="28":
        s+=[tr("我们在三个独立水域比较内核、被动和随机控制，考察个体能否通过摄食补给能量并产生后代。",
               "We compared Core, passive and random control in three independent environments to test whether feeding could sustain reproduction."),
            tr("摄食、繁殖及能量短缺的联合检验","Joint feeding, reproduction and energy-shortage test")+" — "+verdict(t["ecological_cycle"])+
            tr("。达到摄食和繁殖标准的完整世界为 ",". Worlds meeting the feeding and reproduction criterion were ")+str(t["eligible_worlds"])+".",
            tr("共同环境下，继承内核相对空白内核的摄食率差值按三个世界依次为 ","In the common garden, feeding-rate differences for inherited versus blank Cores were ")+
            ", ".join(map(f,t["common_garden_differences"]))+tr(" 颗/存活身体分钟。一致的继承收益"," grains per living body-minute. Consistent benefit from inheritance")+" — "+verdict(t["consistent_inherited_gain"])+"."]
    elif code=="38":
        s+=[tr("我们先按亲代本人表现选取曾完整吞食活体的个体。入选记录","We selected a parent on its own observed complete enclosure and consumption of live prey. Parent found")+" — "+str(t["parent_selected"])+".",
            tr("供给分支已建立","Matched supply branches established")+" — "+str(t["fork_applied"])+".",
            tr("下列数字从供给分支建立时起计算。一个世界的两个副本共享分支前全部经历。",
               "The comparisons below start at the supply change. Both branches shared the entire preceding history of a single world.")]
        for when,v in t["supply"].items():
            fields=["grains","predations","births"]
            s+=[f"{when} "+tr("内部秒时，原供给与减半供给下，新增颗粒摄取、捕食及出生分别为 ",
                               "internal seconds. New grain intakes, predations and births under original and halved supply were ")+
                str([v["original"][k] for k in fields])+" / "+str([v["reduced"][k] for k in fields])+
                tr("。减粮增加捕食"," . Increased predation with lower supply")+" — "+verdict(v["increased_predation"])+"."]
        for label,v in t["lineage"].items():
            s+=[f"{label} — "+tr("候选谱系实际捕食者编号 ","IDs of hunters from the candidate lineage ")+str(v["hunters"])+
                tr("，吞食次数 ",", predations ")+str(v["predations"])+tr("，自然出生的捕食者编号 ",", naturally born hunters ")+str(v["natural_offspring_hunters"])+"."]
        s+=[tr("候选谱系至少两个成员合计完成至少三次捕食","At least two lineage members account for three or more predations")+" — "+verdict(t["qualifying_lineage"])+"."]
    else:
        s+=[tr("两个独立水域各从同一快照比较原供给和减半供给。个体死亡后遗体继续漂移，身体材料、剩余储备与实际吸收量分别记账。第 0 代为创始者。",
               "Within each of two independent environments, the original and halved food supplies were compared from a common snapshot. Naturally dead bodies drifted in the habitat. We recorded recoverable material, remaining reserves and actual absorption separately. Founders are generation zero.")]
        for key,title in (("predation_rate",tr("活体捕食","Live predation")),("carrion_rate",tr("食腐","Scavenging"))):
            v=t["supply_effects"][key]
            s+=[title+tr("每存活身体分钟的发生率，减半供给减去原供给，两世界的差值为 ",
                        " per living body-minute, halved minus original supply, differed across the two worlds by ")+
                ", ".join(map(f,v["differences"]))+tr("。两世界一致促进",". Increase in both worlds")+" — "+verdict(v["increased_in_both"])+"."]
        for mode,v in t["energy_loss_predictions"].items():
            s+=[mode+" — "+tr("前 60 内部秒取食所得不足以覆盖运动和外壳处理开销的行为倾向，是否随代际选择减少","Selection against food income below movement and shell-handling expenditure in the first 60 seconds")+" — "+verdict(v)+"."]
        for key,r in c.items():
            s+=[key+" — "+tr("最高实际代数 ","highest observed generation ")+str(r["maximum_generation"])+
                tr("，推迟繁殖次数 ",", deferred births ")+str(int(r["deferred_births"]))+
                tr("，处理外壳后净亏的食腐次数 ",", scavenging meals with a net loss after shell processing ")+str(r["losing_carrion_meals"])+"."]
            if "offspring" in r:
                o=r["offspring"]
                s+=[tr("负收支和非负收支两组完成随访的个体数及平均子代数 ",
                       "First-60-second deficit and non-deficit groups, eligible individuals and mean offspring at ages (60,180] ")+
                    " / ".join(str(o["reproduction"][n]["observed"])+", "+f(o["reproduction"][n]["mean_children"])
                               for n in ("negative","nonnegative"))+
                    tr("。第 1–2 代和第 3–5 代亏损个体数/可观察个体数 ",". Individuals with a deficit / observed individuals in generations 1–2 and 3–5 ")+
                    " / ".join(f'{o[k]["negative"]}:{o[k]["observed"]}' for k in ("generations_1_2","generations_3_5"))+"."]
    s+=[tr("## 各世界的观测","## Observations by world"),
        tr("摄食次数、捕食、食腐、出生和身体分钟从各行的起点开始累计。存活数取终点。破折号表示分母为零或没有合适的比较。",
           "Counts and living body-minutes start at the beginning of each row. Survivors are counted at its endpoint. A dash denotes a zero denominator or unavailable comparison."),
        tr("| 世界 | 终点（内部秒） | 期末存活 | 新出生 | 颗粒 | 存活身体分钟 | 颗粒/身体分钟 | 捕食 | 食腐 |",
           "| World | End (internal s) | Survivors | Births | Grains | Living body-min | Grains/body-min | Predations | Carrion meals |")+
        "\n|---|---:|---:|---:|---:|---:|---:|---:|---:|"+
        "".join(f'\n| {k} | {f(v["time_us"]/1e6)} | {v["alive"]} | {v["births"]} | {v["grains"]} | {f(v["living_body_minutes"])} | {f(v["grain_rate"])} | {v["predations"]} | {v["carrion_meals"]} |' for k,v in c.items()),
        tr("各项分母以独立环境或配对世界为单位。逐事件复核使用每个 20 内部毫秒的原始记录，重新累计存活身体时间，并核对摄食、出生和捕食事件、完整快照及其时间。精确数值、谱系和各时点结果见同目录 findings.json。",
           "Independent environments and paired world branches define the experimental units. We independently counted events and living-body time from every 20-millisecond tick and checked checkpoint identity, timestamps, feedings, births and predations. Exact outcomes and lineage and time-point details are in findings.json.")]
    s.extend(historical_comparison(code,data,english))
    return "\n\n".join(s)+"\n"


def prepare(code):
    data=analyze(code)
    work=directory(code)
    out=work/"analysis"
    for lang in ("zh","en"):
        text=write_report(code,data,lang=="en")
        path=out/("report."+lang+".md")
        if path.exists() and path.read_text(encoding="utf8")!=text:
            raise ValueError("a new report edition is required")
        if not path.exists():
            path.write_text(text,encoding="utf8")
    if code=="39C":
        for key in data["cases"]:
            target=out/(key+"-map.html")
            if not target.exists():
                from_case(work/"cases"/key,target)
    return data
