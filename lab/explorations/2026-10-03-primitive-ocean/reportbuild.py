"""Bilingual measured report, preserving previously published experiments."""

from experiment import HERE, WORK

from lab.tools.ocean_cli import read_json


def table(rows, english=False):
    out = [
        "| World | Seconds | Born total | Offspring | Living Core / bodies | Dead | Food particles | Last generation |"
        if english
        else "| 世界 | 模拟秒 | 累计个体 | 后代 | 存活意识 / 躯体 | 意识死亡 | 摄入颗粒 | 最高代次 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        out.append(
            f"| {r['case']} | {r['sim_seconds']:.2f} | {r['individuals']} | {r['births']} | {r['alive']} / {r['physical']} | {r['deaths']} | {r['grains']} | {r['max_generation']} |"
        )
    return "\n".join(out)


def main():
    s = read_json(WORK / "analysis/summary.json")
    phase1 = [r for r in s["worlds"] if r["case"].startswith("phase1-")]
    phase2 = [r for r in s["worlds"] if r["case"].startswith("phase2-")]
    evaluations = [r for r in s["worlds"] if r["case"].startswith("evaluation-")]
    pairs = s["evaluation_pairs"]
    if len(phase1) != 9 or any(r["status"] not in ("horizon_paused", "extinct") for r in phase1):
        raise RuntimeError("do not silently report incomplete first-stage worlds as completed")
    totals = {
        mode: {
            k: sum(r[k] for r in phase1 if r["case"].endswith(mode))
            for k in ("individuals", "births", "alive", "deaths", "grains")
        }
        for mode in ("core", "passive", "random")
    }
    c, p, r = (totals[x] for x in ("core", "passive", "random"))
    positive = len(pairs) == 3 and all(v["grains_difference"] > 0 and v["energy_difference"] > 0 for v in pairs)
    learned_zh = (
        "三组共同环境比较均出现继承网络摄入更多且剩余能量更高，说明本批存在可保留的经历优势。优势大小见表；尚未定位是哪些内部机制共同产生它。"
        if positive
        else "共同环境比较尚未给出三组一致的继承优势。不能把本轮会游动、会摄食、能繁殖直接升级为已经学会更好的觅食策略。"
    )
    learned_en = (
        "All three common-garden pairs favor inherited networks in both intake and remaining energy. This batch therefore shows retained experiential benefit; its magnitude is tabulated, and the contributing internal mechanisms have not been isolated."
        if positive
        else "The common-garden comparisons do not show inherited benefit in both intake and energy across all three pairs. Movement, feeding and reproduction alone therefore do not establish a learned superior foraging policy."
    )
    if not positive and len(pairs) == 3 and all(v["grains_difference"] > 0 for v in pairs):
        learned_zh = (
            "三组继承网络都摄入了更多营养，出现同方向的摄食增益；但剩余能量并非三组都更高。"
            "这是值得继续检验的经历效应，不能把不一致的储能结果抹掉，也不能把小幅摄食差异扩大为稳定的整体生存优势。"
        )
        learned_en = (
            "All three inherited groups consumed more nutrients, a consistent direction of feeding benefit, "
            "but remaining energy did not improve in all pairs. This experiential effect warrants further testing; "
            "mixed storage outcomes remain relevant, and small intake differences do not establish a stable overall survival advantage."
        )
    pairtable = "| World | Inherited minus blank: food | Energy | Living |\n|---|---:|---:|---:|\n" + "\n".join(
        f"| {v['group']} | {v['grains_difference']:+d} | {v['energy_difference']:+.3f} | {v['alive_difference']:+d} |"
        for v in pairs
    )
    pairtable_zh = pairtable.replace(
        "| World | Inherited minus blank: food | Energy | Living |",
        "| 环境 | 继承减去无经历：摄入颗粒 | 剩余能量 | 存活数 |",
    )
    ceilings = "；".join(
        f"{v['group'] + 1}: {v['inherited_food_utilization']:.1%} / {v['blank_food_utilization']:.1%}" for v in pairs
    )
    energy_table = (
        "| Environment | Core expenditure difference | Storage overflow difference |\n|---|---:|---:|\n"
        + "\n".join(
            f"| {v['group']} | {v['core_energy_spent_difference']:+.3f} | {v['overflow_difference']:+.3f} |"
            for v in pairs
        )
    )
    energy_table_zh = energy_table.replace(
        "| Environment | Core expenditure difference | Storage overflow difference |",
        "| 环境 | 内核耗能差 | 储存溢出损失差 |",
    )
    predations = sum(x["predations"] for x in phase2)
    maximum_generation = max((x["max_generation"] for x in phase2), default=0)
    radius_range = (
        f"{1000 * min(x['radius_min'] for x in phase2):.2f}–{1000 * max(x['radius_max'] for x in phase2):.2f} mm"
        if phase2
        else "not observed"
    )
    rate = read_json(WORK / "frozen.json")["rate"]
    gate = read_json(WORK / "stage-gate.json")
    maxerror = max(abs(x["energy_balance_error"]) for x in s["worlds"])
    continuations = sum(x["segments"] - 1 for x in s["worlds"])
    incomplete = [x["case"] for x in s["worlds"] if x["status"] not in ("horizon_paused", "extinct")]
    if incomplete:
        raise RuntimeError(f"report incomplete worlds explicitly before publication: {incomplete}")
    common = f"{s['individuals']} individuals; {len(s['worlds'])} worlds; {s['wall_seconds'] / 3600:.3f} simulation wall hours"
    zh = f"""# E28：营养海洋让生存与繁殖发生了，学习优势要单独看

日期：2026-10-03。独立项目 `e53a833e-6566-463c-90c2-a94a8fe2a8ef`。Core 没有修改，旧 E27 及所有旧实验保持原样。

## 先说结果

- 意识驱动三世界共 {c["individuals"]} 个体，其中后代 {c["births"]} 个，末态存活 {c["alive"]}、死亡 {c["deaths"]}，摄入 {c["grains"]} 颗营养。
- 停止驱动对照末态存活 {p["alive"]}，后代 {p["births"]}，摄入 {p["grains"]} 颗；随机驱动末态存活 {r["alive"]}，后代 {r["births"]}，摄入 {r["grains"]} 颗。
- **这次已经打通真实的“动作→接触营养→补给内核→存活与繁殖”过程。** 用户提出把起点放简单，是有效的实验调整。此前机械臂没有第一次成功供能的障碍，在此环境中消失了。
- **{learned_zh}**
- 第二阶段完成 {len(phase2)} 个世界，观察到 {predations} 次几何吞食；身体半径出现 {radius_range} 的变体，各世界最高后代代次为 {maximum_generation}。出现了不同体型，但本轮没有建立稳定物种分化的证据。

![浮游群体与摄入](figures/population.png)

## 第一阶段：控制动作是否有用

{table(phase1)}

每世界8个创始个体，观察上限900模拟秒。这个上限只是暂停保存，不是死亡时限。不同驱动组仍运行同一 Core 和感官；停止驱动只令外设推力归零，随机驱动每秒重新抽取动作。三组环境是独立重复；相关个体、后代和恢复分段不是额外独立样本。对照共享初始环境种子和生成规则；动作、摄食及随机数调用随后会改变环境轨迹，并非固定不变的同一场营养录像。

意识驱动与随机驱动的差别用于判断是否已超越一般运动带来的扫食机会。即便两者同样有效，前者仍证明 ThreeMind 能通过外设作用于环境并维持自身；但该事实不能代替“经历改善行为”的对照。

## 第二阶段：身体变异与包裹吞食

预定生态链条件通过状态：`{gate["passed"]}`。条件是至少两个意识驱动世界有真实摄食和繁殖，同时观察到供给不足下的储备下降/缺能。该条件不是意识或适应性标准。

{table(phase2)}

表中代次以各新海洋创始者为0代。第二阶段创始者来自第一阶段活着的父本，跨阶段来源及脑状态摘要另存；这里的局部代次不能冒充完整跨实验谱系的代数。

![身体差异与继承对照](figures/selection.png)

上排每点是一个体，展示大小、累计摄入和身体存活；出生早晚和同世界内亲缘关系不同，不能将这些点当成独立重复来推断体型因果。下排按独立环境比较继承与无经历网络。

随机变异作用于身体半径、推力及局部化学感官范围；不随机更改脑连接，也不写入“追逐猎物”的偏好。较大软包膜完全容纳另一包膜并持续200ms才计吞食；可回收的身体食物储备按60%转换，其余损失。被吞食者关闭感官后，其 Core 仍自然演化，身体失效不直接伪装成意识死亡。

本装置只有局部营养浓度、接触和本体测量，没有向内核提供其他个体的身份或位置，因而本轮也不测试识别特定猎物的追逐策略。吞食的几何规则能运行，与已经演化出主动捕猎是不同问题。

“有利、有害”由摄入、生存与繁殖后果衡量，不由内核里的价值标签衡量。计算人口上限16多次造成繁殖暂缓，所以停在16不是已找到环境自然承载量。最高代次及短观察长度也不足以判断物种。若继续，优先提高这一计算上限并预先安排更长观察，随后做相同新环境中的稳定遗传比较，不先改内核。

## 经历是否改善后代

{pairtable_zh}

各组已生成营养的摄入比例（继承/无经历）：{ceilings}。接近100%时，总摄入已受供给上限限制；优势不明显不能直接解释为没有学习，也不能凭少数颗粒差异就认定稳定适应。

进一步核对能量去向（均为继承减去无经历；耗能/损失为负表示更少）：

{energy_table_zh}

这一分解是在首组结果显示明显储存溢出后增加的解释性分析，不替换主判据。吃到但装不下的食物已明确计为损失，不能把它等同于内核耗能。耗能减少可来自有效适应，也可来自整体响应减弱，需匹配输入进一步区分。

比较采用存活亲代的出生副本、同一新环境、同样普通身体/能量。无经历对照保留同一受体通道与节点身份，按 Core 的空白节点初值清除经历与边，防止意外更换运动接线；两组都关闭繁殖，先比较同样4个体的300秒表现。**无经历只在出生前清除一次，两组测试期间都继续学习。** 这是迁入新环境及普通身体后的网络比较，不代表保留原变异躯体的整体版本优劣；以后可增加保留原躯体的配对比较。原父本不修改。三组中若只完成部分，则只解释已完成部分，不能宣称计划全过。

{table(evaluations)}

![完整评估过程](figures/comparison.png)

这是辅助过程分析：曲线大于0表示当时继承副本更多，小于0则相反。完整展示0～300秒，不挑最好看的时刻替代主判据；某个时间段的优势不自动代表长期稳定优势。

## 装置、证据和真实边界

二维中性浮力水层使用惯性与线性黏性阻力，不是完整流体仿真。感官每20ms、物理每5ms；Core 传播、遗忘、抑制和能量机制保持普通默认。初始160颗营养、全局每5秒最多补1颗、容量160；不因个体繁殖增加供给。校准耗能 {rate:.6f} 单位/秒，正式起始能量 {240 * rate:.6f}、每颗营养 {30 * rate:.6f}。这些是外部资源数值，不是生物常数。

子代的启动能量从亲代身体储备扣除，免费 Core 初始量为0；未靠复制生成能量。本批各世界末态总账最大绝对差 {maxerror:.6g}，相对于约十万单位的总供给属于浮点累加误差。机械做功仍单独记录，未虚称其焦耳已与 Core 实验能量等价。**当前没有把推进器的机械功或更大躯体的制造成本另行折算为食物消耗**；大小已经通过惯性和黏性阻力影响运动，但尚不是完整的生物能量经济，不能把“大体型吞食更多”独自当成高级控制能力。死亡、资源暂停与观察结束分别保存。

已完成：10项新工具测试及5项既有供能工具测试；1500步独立校准完整重放；Python/Rust状态在声明数值容差内一致；同后端保存继续一致；1440/390宽度回放页操作验收。正式群体重放的范围由交付记录单列，不能拿校准代替全部正式复算。

科学模拟成本：{common}。初始账户15%，最终账户和实际新增存储见交付记录；本批只占用一个模拟worker。共{continuations}次保护暂停采用原状态接续，原证据不覆盖。账户读数下降后仍保留旧窗口已观察的消耗继续计数。最终明确追加的资源预算为累计4.5小时、存储软限6GiB/硬限8GiB，原2/4小时登记保留；内存4GiB、可用内存2GiB、C盘5GiB/E盘15GiB余量、账户+6/+10个百分点边界不变。

## 下一步最有用的工作

先比较同样营养供给下提高人口上限、延长观察带来的结果，判断当前群体是否真的会受到资源限制；再扩大共同环境评估的独立谱系与环境数量。若观察到稳定继承优势，再定位连接与节点历史贡献。是否增加能感受同类的物理感官，以及如何让不同躯体的运动/制造耗能影响生存，作为独立外设版本决定。没有理由凭本批就改能量、遗忘或强刺激公式，也没有证据把全部个体差异叫新物种。

[预登记](design.zh.md) · [执行与预算修订](execution-notes.md) · [操作与用户原话](../../../docs/zh/plans/primitive-ocean.md)
"""
    en = f"""# E28: contact feeding supports survival and reproduction; learning needs its own comparison

2026-10-03. Project `e53a833e-6566-463c-90c2-a94a8fe2a8ef`. Core and previous evidence remain unchanged.

## Findings

Core-driven worlds contained {c["individuals"]} individuals including {c["births"]} offspring; {c["alive"]} remained alive and {c["deaths"]} died, with {c["grains"]} particles consumed. Passive controls had {p["alive"]} survivors, {p["births"]} offspring and {p["grains"]} particles. Random-action controls had {r["alive"]} survivors, {r["births"]} offspring and {r["grains"]} particles.

**The action–nutrient-contact–Core-feeding–survival/reproduction loop now operates.** The easier starting environment removes E27's failure to obtain a first meal. **{learned_en}**

![Population and food](figures/population.png)

## First-stage worlds

{table(phase1, True)}

Each begins with 8 founders and is observed for 900 simulated seconds or actual extinction. The horizon pauses living individuals; it does not kill them. All drive variants retain the same Core/sensing/accounting. Passive sets external forces to zero; random samples actions once per second. Three independently seeded worlds are repetitions, not every related descendant or resumed segment. Controls share initial seeds and generation rules; subsequent actions, feeding and random-number calls change the environment trajectory. They are not a fixed replay of identical nutrient positions. Useful movement is distinct from experience improving control.

## Mutation and engulfing

The preregistered ecological gate passed=`{gate["passed"]}`. It requires feeding/reproduction in at least two Core worlds and shortage/reserve decline, not a consciousness or learning conclusion. {len(phase2)} second-stage worlds recorded {predations} geometric engulfings, body radii {radius_range}, and maximum local generation {maximum_generation}.

{table(phase2, True)}

Generation is counted from zero for each new ocean. Phase-two founders inherit from living phase-one parents, whose identities and state hashes are separately recorded. Local generation counts do not describe the full cross-experiment ancestry.

![Body differences and common-environment comparisons](figures/selection.png)

Top: individual size, lifetime intake and body survival. Individuals differ in age and are related within worlds, so these points are not independent evidence of a size effect. Bottom: inherited versus experience-erased networks by independent environment.

Body radius, thrust and sensing range mutate; brain wiring is not randomly rewritten. Full geometric enclosure for 200 ms is required. Recover 60% of prey's bodily food stores and discard the rest; its Core closes inputs and continues naturally. Body destruction is not fabricated immediate consciousness death. The apparatus has local nutrient/contact/proprioceptive sensing but no direct other-body identity/position input; this batch does not test targeted pursuit.

The 16-body computing cap repeatedly deferred births. A plateau at 16 is not a measured natural carrying capacity. Short-lived morphological differences and the limited generations do not establish species. Further work should raise that computing boundary under the same food budget and test stable inheritance in common environments before making such claims.

## Inherited versus experience-erased networks

{pairtable}

Fraction of generated nutrients consumed, inherited / experience-erased: {ceilings}. Near100%, total intake is capped by supply. Small differences alone neither establish stable adaptation nor prove an absence of learning.

Energy accounting, inherited minus erased (negative means lower expenditure/loss):

{energy_table}

This explanatory decomposition was added after the first pair showed substantial storage overflow. It does not replace the primary endpoint. Food that cannot be stored is a recorded loss, distinct from Core expenditure. Reduced expenditure may reflect useful adaptation or generally weaker responses; matched-input controls would distinguish these explanations.

Same new environments, ordinary body and energy; four individuals for 300 seconds, reproduction disabled equally. The naive control preserves receptor/node identities to preserve external motor wiring, replaces histories with actual blank-node defaults and removes edges. **Erasure happens once before birth; both arms continue learning during evaluation.** This tests network transfer into a new environment and ordinary body, not the full inherited organism retaining its mutated body. Matched comparisons retaining each original body are a further question. Original parents are unchanged. Results are limited to completed pairs.

{table(evaluations, True)}

![Full evaluation course](figures/comparison.png)

Secondary process analysis: positive values favor inherited copies at that time, negative values favor erased copies. The entire0–300second course is shown; selected peaks do not replace the primary endpoint or demonstrate lasting advantage by themselves.

## Evidence and limits

This is a planar neutral-buoyancy approximation, not full fluid dynamics. Physics 5 ms, sensing 20 ms, original Core timing/forgetting/inhibition unchanged. Initial 160 particles, capacity 160, globally at most one addition every 5 seconds regardless of population. Calibration expenditure {rate:.6f}/s sets initial reserve {240 * rate:.6f} and nutrient value {30 * rate:.6f}. Offspring are funded from parental stored nutrients and receive zero free initial Core energy. Maximum final population-ledger error is {maxerror:.6g}; mechanical joules remain separate from Core energy units. **Propulsion work and the manufacturing cost of a larger body are not additionally charged as food consumption.** Size already affects motion through inertia and viscous drag, but these tradeoffs are not a complete biological energy economy; greater engulfing capacity alone does not demonstrate advanced control.

Ten new tests plus five existing survival-tool tests passed; full 1500-step calibration replay passed, Python/Rust agreed within stated tolerance, same-backend continuation matched, and the offline viewer passed 1440/390-pixel interactions. Formal-population replay coverage is listed separately in delivery. {continuations} protected pauses were continued with immutable original evidence. After an account-usage reading dropped, previous observed consumption was carried forward for budgeting.

{common}. Final storage/account figures are in delivery. Prospective resource amendments increased wall budget to 4.5 hours and storage to 6/8 GiB; original 2/4-hour registrations were retained and scientific endpoints unchanged. One simulation worker; memory 4 GiB, free RAM 2 GiB, C 5 GiB, E 15 GiB, account +6/+10-point limits retained.

Next: increase the computing population boundary under the same food budget, extend observation, and replicate common-garden effects across independent lineages/environments. Isolate internal mechanisms only after a reproducible inherited advantage. Other-body sensing and explicit movement/body-production food costs would be separate peripheral changes. This batch does not justify changing forgetting/energy/strong-input equations or claiming new species.

[Preregistration](design.en.md) · [Execution](execution-notes.md) · [Operation and proposal](../../../docs/en/plans/primitive-ocean.md)
"""
    for lang, body in (("zh", zh), ("en", en)):
        with (HERE / f"report.{lang}.md").open("x", encoding="utf-8") as stream:
            stream.write(body)


if __name__ == "__main__":
    main()
