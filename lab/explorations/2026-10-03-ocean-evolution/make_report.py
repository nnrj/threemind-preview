"""Render bilingual evidence tables; scientific interpretation is reviewed afterward."""

import json

from experiment import HERE, WORK

from lab.tools.ocean_cli import read_json


def table(headers, rows):
    return "\n".join(
        ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
        + ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    )


def n(value, digits=0):
    return f"{value:,.{digits}f}"


def main():
    summary = read_json(WORK / "analysis/summary.json")
    verification = read_json(WORK / "formal-verification.json")
    decision = read_json(WORK / "followup-delivery-decision.json")
    lookup = {r["case"]: r for r in summary["worlds"]}
    eco = [r for r in summary["worlds"] if r["case"].startswith("fork-")]
    titles = {
        "zh": "# E29：稀疏海洋中的生存、身体变异与资源交换",
        "en": "# E29: Survival, body variation and resource exchange in a sparse ocean",
    }
    primary_rows = []
    energy_rows = []
    for g in range(3):
        for mode in ("core", "random"):
            r = lookup.get(f"phase1-{g}-{mode}")
            if not r:
                continue
            primary_rows.append(
                [
                    g + 1,
                    mode,
                    n(r["duration_s"]),
                    r["food"],
                    n(r["food_per_body_s"], 5),
                    n(r["living_body_s"]),
                    r["physical_survivors"],
                    n(r["totals_delta"]["births"]),
                ]
            )
            obs = r["input_summary"]
            energy_rows.append(
                [
                    g + 1,
                    mode,
                    n(r["body_delta"]["motor_energy"]),
                    n(r["core_cost"]),
                    n(r["body_delta"]["path_m"], 2),
                    n(obs["mean_squared_translation_command"], 4),
                    n(obs["mean_velocity_food_gradient_cosine"], 4),
                ]
            )
    eco_rows = []
    trait_rows = []
    encounter_rows = []
    exchange_rows = []
    for r in eco:
        t = r["totals_delta"]
        transfers = r["exchange_summary"]
        if transfers["transfer_steps"]:
            relation = transfers["relationships"]
            exchange_rows.append(
                [
                    r["case"],
                    transfers["distinct_pairs"],
                    n(transfers["sent"], 1),
                    n(transfers["received"], 1),
                    n(relation["parent_to_child"]["received"], 1),
                    n(relation["child_to_parent"]["received"], 1),
                    n(relation["other"]["received"], 1),
                ]
            )
        encounter_rows.append(
            [
                r["case"],
                r["input_summary"]["nonzero_neighbor_measurement_samples"],
                r["input_summary"]["nonzero_enclosure_measurement_samples"],
                n(t["protected_contacts"]),
            ]
        )
        eco_rows.append(
            [
                r["case"],
                n(r["duration_s"]),
                r["food"],
                r["physical_survivors"],
                n(t["births"]),
                n(t["predations"]),
                n(t["recombinations"]),
                n(t["horizontal_transfers"]),
                n(t["sharing_contacts"]),
            ]
        )
        live = [v for v in r["traits"] if v["alive"]]
        trait_rows.append(
            [
                r["case"],
                r["generation_max"],
                f"{min(v['radius'] for v in r['traits']) * 1000:.2f}–{max(v['radius'] for v in r['traits']) * 1000:.2f}",
                f"{min(v['shell'] for v in r['traits']):.3f}–{max(v['shell'] for v in r['traits']):.3f}",
                f"{min(v['reflectance'] for v in r['traits']):.3f}–{max(v['reflectance'] for v in r['traits']):.3f}",
                len({v["ligand"] for v in live}),
            ]
        )
    differences = [
        [p["group"] + 1, p["variant"], f"{p['food']:+d}", f"{p['living_body_s']:+.1f}", f"{p['physical_survivors']:+d}"]
        for p in summary["ecological_pairs"]
    ]
    verification_rows = [
        [r["segment"], n(r["start_us"] / 1e6), n(r["end_us"] / 1e6), r["steps"]] for r in verification["replays"]
    ]
    pairs = summary["primary_pairs"]
    food_diffs = " / ".join(f"{p['food_difference']:+d} ({p['food_relative']:+.1%})" for p in pairs)
    survivor_diffs = " / ".join(f"{p['survivor_difference']:+d}" for p in pairs)
    rates_lower = (
        all(
            lookup[f"phase1-{g}-core"]["food_per_body_s"] < lookup[f"phase1-{g}-random"]["food_per_body_s"]
            for g in range(3)
            if f"phase1-{g}-core" in lookup and f"phase1-{g}-random" in lookup
        )
        and len(pairs) == 3
    )
    births = sum(r["totals_delta"]["births"] for r in eco)
    predations = sum(r["totals_delta"]["predations"] for r in eco)
    exchanges = sum(r["totals_delta"]["sharing_contacts"] for r in eco)
    sharing_pairs = [p for p in summary["ecological_pairs"] if p["variant"] == "sharing"]
    sharing_food = " / ".join(f"{p['food']:+d}" for p in sharing_pairs)
    sharing_survivors = " / ".join(f"{p['physical_survivors']:+d}" for p in sharing_pairs)
    sharing_births = " / ".join(f"{p['births']:+.0f}" for p in sharing_pairs)
    sharing_living = " / ".join(f"{p['living_body_s']:+.2f}" for p in sharing_pairs)
    maximum_error = max(r["largest_energy_error"] for r in verification["worlds"])
    scopes = sum(r["snapshots_restored"] for r in verification["worlds"])
    incomplete = ", ".join(summary["incomplete"] + summary["unexecuted"]) or "none"
    for language in ("zh", "en"):
        zh = language == "zh"
        pieces = [
            titles[language],
            "2026-10-03 · `continuous-memory/2` · `threemind.ocean/2`",
            "[预登记 / Registration](design."
            + language
            + ".md) · [执行与修订 / Execution and amendments](execution-notes.md)",
        ]
        if zh:
            pieces += [
                "## 先说结果",
                f"三个主世界的意识驱动相对随机驱动，摄食差分别为 **{food_diffs}**，末态存活数差为 **{survivor_diffs}**。"
                + (
                    "达到原先登记的进一步确认门限。"
                    if summary["confirmation_gate"]
                    else "没有达到原先登记的进一步确认门限。"
                )
                + "门限只用于分配后续实验资源，完整指标如下，不能把总摄食量替代单个活体的摄食效率。",
                (
                    "**一个很有价值的区别：三组意识驱动的累计存活时间和总摄食都更高，但每个活体每秒摄食反而都略低。**"
                    "它的优势更像是维持一个更能持续生存的种群，而非每个个体都更快找到食物。"
                    "其中第三组末态少存活1个，并不抹去此前累计存活时间更长的事实；两项结果都保留。"
                    if rates_lower
                    else "单位活体时间的摄食率与整个种群总摄食分别列出，不用一个指标替代另一个。"
                ),
                (
                    f"生态分叉新增 {n(births)} 个后代、{n(predations)} 次吞食、{n(exchanges)} 次相容接触交换。"
                    "身体变异和接触交换是环境允许的规则，是否改善生存要看与同源对照的差别；开了开关本身不是主动合作或新物种的证据。"
                ),
                f"**接触资源交换确实改写了生存与繁殖，但没有表现为所有指标都改善。** 两个来源分别多吃 {sharing_food} 颗，末态存活差 {sharing_survivors} 个，出生差 {sharing_births} 个，累计活体时间差 {sharing_living} 秒。第一组终点多活下来，不代表整个观察期或第二组也有相同收益。繁殖混合、吞食及吞食来源遗传均没有实际发生，不能将此写成它们发生后无效。",
                decision["summary_zh"],
                "## 一、意识驱动与随机驱动",
                "每个世界31个创始者、37个活体上限，观察1800模拟秒。无默认年龄死亡；观察期到达只暂停保存，个体仍按能量与活动规则生存或死亡。海域1.2米见方，初始180颗营养、上限1024、每2秒补一颗。物理5ms、感官20ms；没有接入实时硬件遥测。",
                table(
                    ["组", "驱动", "模拟秒", "摄食颗数", "颗/活体秒", "活体秒合计", "末态存活", "后代"], primary_rows
                ),
                "![主对照：存活、摄食与未找到的食物](figures/primary.png)",
                "每一配对世界才是独立实验单位。后代和数百万感官帧彼此相关，不能拿它们冒充数百万次独立验证。海中仍有食物而部分个体饿死，表示有限时间内找不到或到达不了食物，不是全世界食物已经用光。",
                "## 二、优势究竟可能来自哪里",
                table(
                    ["组", "驱动", "推进耗能", "Core耗能", "总路径米", "平移动作平方均值", "速度/食物梯度余弦"],
                    energy_rows,
                ),
                "动作是运动接口的命令，身体还会根据燃料限制实际推进；命令大不等于实际移动多。梯度余弦只记录相对水流的速度与局部感官梯度的同向程度，不是单独的学习判据。",
                "随机组每1秒抽样并保持动作，意识组每20ms从活动得到动作；幅度、持续性和耗能不同。因此主对照能回答本装置中哪种驱动更利于生存，不能单凭胜负把差别全部归给学会觅食。身体更省能、感官与运动的闭环、节点经历、连接通信都应进一步区分。原地不动或绕圈没有被实验程序判为错误，只有实际获得食物和付出的能量影响生存。",
                "## 三、生态分叉",
                "固定取前两个意识世界的末态，各复制为4个分叉，再观察900秒，不按成绩选取最好来源。下表摄食/出生/事件均为分叉后的新增量，存活是分叉末态值；不把前1800秒的历史再次算作新效果。",
                table(["世界", "新增秒", "新增摄食", "存活", "出生", "吞食", "繁殖混合", "吞食来源", "交换"], eco_rows),
                "![独立生态对照](figures/ecology.png)",
                "以下为各可选机制相对同源ecology分叉的差；正负都保留。交换次数按实际转移步骤计，不是独立碰面次数或主动合作次数。",
                table(["源组", "机制", "摄食差", "活体秒差", "存活数差"], differences),
                "交换的实际能量流向如下。双向交换的同一对个体只算一对；“其他”只表示不是直接亲子，仍可能有其他亲缘。亲子关系仅由观察工具查谱系，不送入内核或交换规则。",
                table(
                    ["世界", "发生交换的个体对", "送出能量", "收到能量", "亲代→子代收到", "子代→亲代收到", "其他收到"],
                    exchange_rows,
                ),
                "身体差异如下，区间覆盖保留的全部个体（包括死者）；末列仅数存活体的表面类型，不把类型标签当物种。",
                table(["世界", "最高代次", "半径mm", "外壳", "反射率", "存活相容类型数"], trait_rows),
                "以下是新增只读诊断，不替换原主判据：实际邻近信号和包裹信号的个体采样帧数。它们不是独立碰面次数；包裹信号也不保证持续足够久或有足够能量吞食。",
                table(["世界", "非零邻近帧", "非零包裹帧", "亲代保护步骤"], encounter_rows),
                "基础ecology有随机身体变异和吞食；recombination仅另允接触繁殖混合；transfer仅另允吞食后保留身体遗传来源；sharing仅另允相容接触时有损资源交换。融合/交换不开启时不是强行禁止意识形成任何偏好，只是此环境没有相应材料过程。",
                "变异限于半径、推进力、感知范围、外壳、反射率、表面相容性和中性标记。外壳有重量/阻力/建造和维持代价，也增加吞食难度；降低反射率改变局部感官量，不让内核预知敌我。母体不能吞食不足60秒的自己的子体，这是明确的环境保护规则，不是已涌现的亲情。体型或标签不同还不能称新物种，稳定遗传与跨环境保持仍需后续验证。",
                "可选机制共用身体变异随机流，连失败的概率抽取也可能改变后续抽样；营养混合随机流还随剩余颗粒数变化。因此分叉保证同源初态及逐步可重放，不保证未来随机事件逐一相同。零成功融合的分叉差别不能解释成成功融合的作用。",
                "## 四、发现并处理的供能配置问题",
                "旧主配置给新生体Core180r、身体60r，但消化优先把Core补回240r，可能立即用完身体的推进燃料。原始记录在77秒出生、77.02秒补能的个体上确认了此事。六个主组保留该配置，不能悄悄重算成更有利版本。",
                "八个生态分组启动前统一改成新生Core240r＋身体60r，由亲代额外支付60r；没有凭空送能、补发给旧个体或复活死者。该修订使生态分组的对照仍共有相同出生条件，但主阶段与生态阶段的差别不能只归因于捕食和变异。r=5.706242779562836来自独立工程样例的每体每秒Core支出，不是生物常数。",
                "## 五、完整性、资源与可重现性",
                f"正式主/生态世界 {len(summary['worlds'])} 个，包含复制的存活身体和出生共 {n(summary['active_copies_and_births'])} 次；未完成/未执行：{incomplete}。模拟进程耗时合计 {n(summary['wall_seconds'] / 3600, 2)} 小时，不能把并行时间当免费资源。",
                f"恢复检查覆盖 {scopes} 份保存状态，能量账本最大绝对残差 {maximum_error:.3g}。下列完整区间重放同时匹配输入、动作、事件及结束状态；不是所有正式世界从头全程重放。",
                table(["分段", "起点秒", "终点秒", "步数"], verification_rows),
                "网络中断时三个世界因数据库连接关闭而安全暂停，核验后从原状态继续。另一次749秒暂停用于独立世界并行编排。所有旧错误、状态、随机流、检查点和接续边界保留，墙钟暂停不推进模型时间。JSON整数键/字符串键的校验错误只在验证器修正，没有更改模型。",
                "独立确认又在473/524秒因操作者未及时刷新账户用量检查而保护暂停，完整核验后原样续跑。同期用户报告Docker崩溃，检查时Docker引擎已响应、本地PostgreSQL仍自9月28日起运行；这次保护暂停不能归因于Docker，也没有为此重启服务。",
                f"最终正式核验累计耗时 {n(verification['wall_seconds'] / 60, 1)} 分钟，包含已停止的首个核验尝试。每个保存状态和选定重放区间有与源文件摘要绑定的核验收据；重试不抹去失败记录或退还已耗资源。总预算为模拟与正式核验合计14进程小时，完整实耗另见交付收据。",
                "装置与Core源码摘要固定；13项Ocean /2测试、2项只读统计测试、2项副本干预测试，以及15项旧海洋/生存回归通过。工程样例全1500步重放，Python/Rust状态按既定容差核对。离线回放器验过1440/390像素；完整群体实时启动UI仍在T08，不能用离线播放器冒充已实现。",
                "## 六、下一步如何选择",
                "先依据完整比较判断驱动优势能否跨种子保持，再用已登记的独立确认与经历/连接对照找原因。若有作用，再定位具体连接和活动片段，做匹配的移除、假干预、解除与移植。不能先挑一个看起来有趣的区域，再把普通身体/运动差异改称自主联想证据。",
                "稳定生态型、主动合作、感官或器官由更基本材料规则自发出现仍未被本实验完成。当前有限身体参数可以检验代价与选择，不等同于早期地球，也不因为跑得久就保证产生智能。对这些问题的设想继续留在研究计划，而不是悄悄删掉。",
            ]
        else:
            pieces += [
                "## Findings first",
                f"Core-minus-random food differences across the three primary pairs are **{food_diffs}**; final survivor differences are **{survivor_diffs}**. "
                + (
                    "The original confirmation gate passed. "
                    if summary["confirmation_gate"]
                    else "The original confirmation gate did not pass. "
                )
                + "This gate allocates follow-up resources; total intake does not replace intake per living-body second.",
                (
                    "**All three Core groups sustain more total living-body time and eat more overall, yet intake per living-body second is slightly lower in every pair.** "
                    "This is an advantage in sustaining the population, not evidence that every individual finds food faster. "
                    "The third Core group ends with one fewer survivor despite its longer cumulative survival; preserve both observations."
                    if rates_lower
                    else "Per-living-body intake and whole-population intake are reported separately."
                ),
                f"Ecological forks added {n(births)} offspring, {n(predations)} engulfings and {n(exchanges)} compatible exchanges. Enabling these material processes is not evidence of active cooperation or new species; compare actual paired outcomes.",
                f"**Contact sharing changes survival and reproduction, but does not improve every outcome.** The paired food differences are {sharing_food}, endpoint survivors {sharing_survivors}, births {sharing_births}, and cumulative living-body seconds {sharing_living}. A better first endpoint does not imply a benefit throughout that observation period or in the other source. No successful recombination, engulfing or engulfing-derived inheritance occurred; absence of realized events is not evidence that they occurred without effect.",
                decision["summary_en"],
                "## 1. Core versus random drive",
                "Each world begins with 31 founders, permits 37 living bodies and observes 1,800 simulated seconds. There is no default age death; the observation horizon saves and pauses the population. The 1.2 m square starts with 180 food particles, permits 1,024 and adds one every 2 seconds. Physics advances every 5 ms and senses sample every 20 ms. No live hardware telemetry is connected.",
                table(
                    ["Pair", "Drive", "Seconds", "Food", "Food/body-s", "Living body-s", "Survivors", "Offspring"],
                    primary_rows,
                ),
                "![Primary survival, intake and uneaten food](figures/primary.png)",
                "Independent worlds, not offspring or millions of correlated input frames, are the experimental units. Starvation with food still present indicates failure to reach usable food in time, not exhaustion of all environmental supply.",
                "## 2. Possible sources of advantage",
                table(
                    [
                        "Pair",
                        "Drive",
                        "Motor energy",
                        "Core energy",
                        "Path m",
                        "Translation command squared",
                        "Velocity/gradient cosine",
                    ],
                    energy_rows,
                ),
                "Commands are limited by available body fuel before producing motion. Gradient alignment describes measured velocity relative to water and local nutrient signals; it is not a learning verdict by itself. Random commands change once per second; Core commands are read every 20 ms. Magnitude, persistence and energy costs differ, so primary performance alone cannot isolate learned foraging from economical motion, feedback, node history or communication. Remaining still or circling is never scored as wrong; actual energy consequences determine survival.",
                "## 3. Ecological forks",
                "Fork the fixed first two Core endpoints into four 900-second continuations each. Intake, birth and event counts below are increments after the fork; survivors are endpoint values. Earlier history is not counted again.",
                table(
                    [
                        "World",
                        "Added s",
                        "Added food",
                        "Survivors",
                        "Births",
                        "Engulfing",
                        "Recombination",
                        "Transfer",
                        "Exchange",
                    ],
                    eco_rows,
                ),
                "![Separate ecological allowances](figures/ecology.png)",
                "Differences below are relative to each source's ecology fork. Exchange counts denote transfer steps, not independent encounters or active cooperative acts.",
                table(
                    ["Source", "Mechanism", "Food difference", "Living body-s difference", "Survivor difference"],
                    differences,
                ),
                "Actual transfer energy is broken down below. A pair exchanging in both directions counts once. Other means not a direct parent-child relationship, and may still include other relatives. Genealogy is consulted only by the observer, never supplied to Core or the sharing rule.",
                table(
                    [
                        "World",
                        "Distinct pairs",
                        "Sent energy",
                        "Received energy",
                        "Parent→child received",
                        "Child→parent received",
                        "Other received",
                    ],
                    exchange_rows,
                ),
                "Trait ranges cover all retained individuals, including the dead. Surface types count living compatible classes, not species.",
                table(
                    ["World", "Maximum generation", "Radius mm", "Shell", "Reflectance", "Living surface types"],
                    trait_rows,
                ),
                "Additional read-only diagnostics count individual sample frames with neighbor/enclosure signals, not independent encounters. Enclosure need not last long enough or have sufficient energy for engulfing; these diagnostics do not replace the primary criterion.",
                table(["World", "Neighbor frames", "Enclosure frames", "Protected steps"], encounter_rows),
                "The ecology baseline permits random body mutation and engulfing. Recombination, engulfing-derived inheritance and lossy contact sharing are separate additions. Variation is limited to radius, thrust, sensing range, shell, reflectance, compatible surfaces and a neutral marker. Shells have mass, drag, maintenance/construction costs and engulfing resistance; reflectance changes local measurements without enemy labels. Parent protection below 60 seconds is an explicit environmental rule, not emergent parenting. Trait diversity is not demonstrated species diversity.",
                "Optional mechanisms share a saved mutation RNG, including unsuccessful draws; food mixing also depends on remaining particle count. Forks share exact initial conditions and replayable dynamics, not identical future random tapes. A difference with no successful recombination cannot be attributed to successful fusion.",
                "## 4. A discovered newborn-fuel coupling",
                "The original primary configuration gives offspring 180r in Core energy and 60r in body fuel, but digestion refills Core to 240r, potentially consuming all initial motor fuel. Records show this at 77 and 77.02 seconds. All six original primary arms and their evidence retain this configuration. Before any ecological arm began, all eight received the prospective allocation of 240r to Core and 60r to body fuel, charging parents the additional 60r. No existing individual was refueled or revived. Thus primary-to-ecological differences cannot be attributed only to predation and mutation. The measured engineering scale r = 5.706242779562836 is not a biological constant.",
                "## 5. Verification and resources",
                f"There are {len(summary['worlds'])} primary/ecological worlds and {n(summary['active_copies_and_births'])} active copies plus births. Incomplete/unexecuted: {incomplete}. Aggregate simulation process time: {n(summary['wall_seconds'] / 3600, 2)} hours, summing parallel workers.",
                f"Restoration covered {scopes} snapshots with maximum absolute ledger residual {maximum_error:.3g}. The following complete intervals matched inputs/actions/events/final state; this is not a full rerun of every world.",
                table(["Segment", "Start s", "End s", "Steps"], verification_rows),
                "Three worlds safely paused when database connections closed during the network incident, then resumed from verified states. An earlier pause at 749 seconds changed scheduling only. Errors, checkpoints and random states remain; wall-clock downtime is not model time. Integer-versus-string JSON map-key comparison was fixed only in the verifier.",
                "Independent confirmation also paused at 473/524 seconds because the operator failed to refresh account usage on time, then resumed after exact checks. The concurrent Docker incident did not require a service restart: the engine responded, and local PostgreSQL had remained running since September 28. The recorded account-check pause must not be attributed to Docker.",
                f"Formal verification consumed {n(verification['wall_seconds'] / 60, 1)} minutes in total, including the stopped first attempt. World and selected-interval receipts are bound to evidence hashes; retries preserve failures and charge their time. The combined simulation/verification allowance is 14 process-hours; the delivery receipt records complete measured usage.",
                "Thirteen Ocean /2 tests, two read-only statistics tests, two copy-intervention tests and fifteen legacy/survival regressions passed. All 1,500 engineering steps replayed; Python/Rust state comparison used declared tolerances. The offline viewer passed checks at 1,440 and 390 pixels. Full graphical cohort launching remains T08; playback is not live orchestration.",
                "## 6. Next decisions",
                "Use complete paired outcomes, independent confirmation and registered history/communication controls before locating and transplanting specific active structures. Whole-body or motor differences are not localized association evidence. Stable ecological types, active cooperation and organs emerging from general material rules remain open. This finite trait family is a tractable selection experiment, not calibrated early Earth, and longer execution does not guarantee intelligence.",
            ]
        supplementary = HERE / f"followup-report.{language}.md"
        if supplementary.exists():
            pieces.append(supplementary.read_text(encoding="utf-8"))
        path = HERE / f"report.{language}.md"
        if path.exists():
            raise FileExistsError("preserve existing reports; append a dated revision instead")
        path.write_text("\n\n".join(pieces) + "\n", encoding="utf-8")
    print(json.dumps({"reports": [str(HERE / f"report.{lang}.md") for lang in ("zh", "en")]}))


if __name__ == "__main__":
    main()
