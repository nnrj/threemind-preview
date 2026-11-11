"""Generate plain-language bilingual results and figures from audited evidence."""

import shutil
from statistics import mean

from common import HERE, ROOT, WORK, new_json, read_json


def select(rows, **conditions):
    return [r for r in rows if all(r.get(k) == v for k, v in conditions.items())]


def average(rows, field, **conditions):
    selected = select(rows, **conditions)
    assert selected, conditions
    return mean(r[field] for r in selected)


def write():
    audit = read_json(WORK / "audit.json")
    analysis = read_json(WORK / "analysis-current.json")
    assert audit["verified_cases"] == analysis["cases"] == 786
    new_json(WORK / "analysis-final.json", analysis)
    rows = analysis["rows"]
    cued = select(rows, stage="probe", cue_intensity=0.5)
    strong = "|强度 / Intensity|增益关闭：30 秒权重 / Gain off|增益开启：30 秒权重 / Gain on|关闭：目标响应 / Off response|开启：目标响应 / On response|\n|---|---:|---:|---:|---:|\n"
    for intensity in (0.4, 1, 1.5, 2, 4):
        args = {"family": "intensity", "protocol": f"single_{intensity:g}", "age_s": 30}
        vals = [
            average(cued, field, **args, gain=gain)
            for field in ("initial_AD_weight", "D_cue_integral")
            for gain in (0.0, 0.075)
        ]
        strong += f"|{intensity:g}|" + "|".join(f"{v:.6f}" for v in vals) + "|\n"
    novelty = "|训练强度 / Training dose|立即计算 / Immediate|延迟触达结算 / Arrival window|相对增加 / Increase|\n|---|---:|---:|---:|\n"
    for dose in (0.2, 0.4, 0.8):
        a, b = [
            average(cued, "D_cue_integral", family="novelty", dose=dose, gain=0.018, mode=mode)
            for mode in ("immediate", "arrival-window")
        ]
        gain = f"{(b / a - 1) * 100:.2f}%" if a else "两者为零 / Both zero"
        novelty += f"|{dose:g}|{a:.8f}|{b:.8f}|{gain}|\n"
    retention = "|遗忘条件 / Condition|300 秒时权重 / Weight at 300 s|提示 0.5：目标响应 / Cue 0.5|提示 1：目标响应 / Cue 1|\n|---|---:|---:|---:|\n"
    for condition in ("normal", "weight_off", "slow_off"):
        args = {
            "family": "forgetting",
            "condition": condition,
            "protocol": "spaced_ordinary",
            "age_s": 300,
            "stage": "probe",
        }
        weight = average(rows, "initial_AD_weight", **args, cue_intensity=0.5)
        vals = [average(rows, "D_cue_integral", **args, cue_intensity=cue) for cue in (0.5, 1)]
        retention += f"|{condition}|{weight:.6f}|{vals[0]:.8f}|{vals[1]:.8f}|\n"
    adapted = "|条件 / Condition|新提示引起的旧 B 响应 / Old B|新 D 响应 / New D|\n|---|---:|---:|\n"
    for condition in ("normal", "weight_off", "slow_off"):
        vals = [
            average(cued, field, family="adaptation", condition=condition, phase=2)
            for field in ("B_cue_integral", "D_cue_integral")
        ]
        adapted += f"|{condition}|{vals[0]:.8f}|{vals[1]:.8f}|\n"
    fig = "../../../docs/images/mechanism-calibration-2026-09-29.png"
    zh = f"""# 强刺激、新颖性与 300 秒遗忘：校准结果

[English](report.en.md) · 2026-09-29 · 独立项目：`2026-09-29 强刺激、新颖性与遗忘校准`

## 先说结果

**强刺激机制没有丢失，而且确实能让新连接更强、保持更久。** 以前把强度 1 当作“强刺激”，没有触发额外增益项；该项计算的是超过 1 的部分。本轮单次强度 4 在 30 秒后仍能让提示引起目标的短暂激活，额外增益关闭时明显较弱。

**新颖性公式也没有丢失，但立即连边会错过稍后才到达的联想。** 新版本给刚出生的连接一个局部等待窗口，用真实到达的联想量结算原有增益。在训练强度 0.4 下，目标短暂响应比立即计算增加 **40.66%**；0.8 下增加 **2.26%**，0.2 下两者都没有可测目标响应。没有给内核添加“内容重要”“答案正确”这样的判断。

**300 秒的问题已经拆开：正常遗忘确实删掉了弱连接；关闭权重遗忘能留住它，但弱提示仍可能激不活它。** 提示从 0.5 增到 1 后，保存下来的连接又有短暂目标响应。因此，“读不出来”不能一概当成“结构里什么都没了”。

本轮这些目标响应都发生得较早，**目标未进入后续响应模式收敛窗口的主要排名**。这是主要读出与次要轨迹观察的区别。新读出器现在会把模式是否稳定、幅度是否下降、是否周期活动、是否结束分别报告；不能把整网比例趋稳直接当成目标配对长期保持。

![校准图](../../../docs/images/mechanism-calibration-2026-09-29.png)

## 怎样比较

共 **786 个有效平台实例**：强刺激 288、新颖性 216（含补齐的 72 个无提示副本）、遗忘 240、适应 42；另有 12 个旧源码小型见证。两个种子为 9293201、9293202，三种新颖性相位为 70、110、170 ms。匿名通道有明确的外部实验标记，标记不进入动力学。每个测试副本从同一父状态独立分出，测试不回写父本。

遗忘与强刺激试验用原先的 `continuous-memory/1` 及原始父状态。新颖性用新 `continuous-memory/2`，分别选择立即计算和延迟触达模式；旧内核没有被升级覆盖。背景是先前记录的真实宿主机遥测，强度 0.2、原映射不变，重放周期和哈希入证据。没有调用 AI 决定行为。

保留抑制、自身短时反应减弱、局部耗竭与恢复、易化、持续可塑性；只改变本组登记的量。外部供应器每模拟秒最多提供 10 单位、总量不限，连接仍消耗能量。全部实例未满足能量需求为 **0**；这不是关闭耗能或强行补满局部资源。既有维护费用仍与缺能损伤选项相连，本轮不把该账本称为完整生物代谢模型。

主要指标是响应模式收敛判定窗口末尾的实际节点激活排序。另保存原活动稳态判定。次要的“目标响应”为 5 秒轨迹中每 100 ms 采样的激活积分，减去同源无提示副本；它包含先升后降的短暂响应。下面的连接权重取**提示之前**，避免把探测本身引起的巩固算成保持。所有条件都报告，不挑正结果。

两个编码／接线种子用于复核方向；不把它们当成大样本生物实验，不报告由这种小样本制造的显著性。新颖性每格是两个种子 × 三个相位的描述均值。

## 强刺激：原公式有效，不需要再编一个增益

额外项是 `intensity_gain × max(0, intensity − 1)`，默认系数 0.075；直接激活仍经过接收响应和软饱和，并不无限增长。输入强度 0.4、1 的增益开关对照完全一致；1.5、2、4 随强度显示额外结构巩固。下表均为训练后 30 秒、同样 0.5 提示。

{strong}

单次强度 4 与 0.4×10 的总名义输入相同，但时间分布不同，不能要求效果相同。集中重复在 119～128 秒每秒一次；稀疏重复在 0、1、2、4、8、16、32、64、96、128 秒。所有组最后一次输入均为 128 秒，单次组也在这一时刻输入。当前遗忘速度下，集中重复的近期目标响应强于这一组越来越稀疏的重复；它**没有支持“越稀疏越好”**。单次强刺激的 30 秒保持最好，但正常遗忘下到 300 秒这些新连接仍已被修剪。训练间隔应与连接能保持多久一起校准。

本轮不修改强刺激公式或默认遗忘速度；修正参数说明，让研究者知道强度 1 不触发额外项。普通 UI 刺激的数值和映射不被悄悄放大。

## 新颖性：保留旧模式，新增局部触达窗口

先输入 AB，再输入共享 A 的 AC。新模式只看出生前是否已有邻域以及端点真正收到的非零联想。窗口截至出生时已排定的下一传播时刻加传播延迟，结算同刻已到达的信号；只结算一次。无邻域、无联想、增益为零均不会获得奖励。断连撤销该出生记录，重建连接有新身份；快照保存未结算窗口。

首个观察窗口内，增益开启组的立即计算是 **72 次生边中 8 次获得增益**；延迟触达是 **72 次中 24 次**。相同增益关闭时两种模式的目标轨迹一致，排除了“仅仅多了一次调度就凭空增强”的解释。

{novelty}

0.8 组立即模式本来就能触发部分增益，所以新模式相对旧模式仅增加 2.26%；相对两者共同的无增益对照则增加约 8.18%。不能把两个比较混写。

冻结 Git `97d8592` 的旧操作顺序也进行了 3 个同幅度、9 个交叉幅度见证：这组最简单的 AB→AC 样例**同样没有触发旧新颖性奖励**。传播可能到达 B，但新连接端点是 A、C；旧传播还受目标响应与饱和影响。所以不是“旧源码只要传播在前就一定有效”，也不能把所有零结果都归于迁移遗漏。代码恢复见证与自然输入触发是两项不同验证。

结论：采用 `continuous-memory/2` 的延迟触达模式作为**新建意识的默认方案**，因为它保留原有局部条件，并在不改变感官映射的情况下得到可重复的触发与响应增益。已有意识／协议保持原内核，`continuous-memory/1` 和立即模式均可选择。该决定针对当前校准任务，并不声称它已解决持久收敛、语言理解或所有新颖性问题。界面标明研究版本，下一轮应观察真实新经验而非语义评分。

## 300 秒：结构遗忘和提示门槛同时存在

直接使用上一轮“无训练／逐渐稀疏重复”的原状态，分别经过 1、10、30、100、300 秒。`normal` 原参数；`weight_off` 仅 `forgetting_rate=0`；`slow_off` 再关闭稳定度和支持度衰减。激活、抑制、痕迹及资格迹仍正常变化，学习仍开启。

{retention}

正常组 300 秒时新 A→D 连接确实不在了。两种关闭遗忘组都保留约 0.041 的连接；0.5 提示依然没有 D 响应，1 提示能引起约 0.000416 的短暂净响应。只关权重遗忘已足以保留本例的弱记忆；不需要为了这个结果把所有衰减都关掉。旧 B 的响应与新 D 分开保存，不能把旧反射当成新记忆成功。

**300 模拟秒不能诚实地换算成人的几小时或几天。** 模型有多种时间尺度，没有经过人类行为数据标定。作为内部参照：激活时间常数约 0.304 秒、抑制约 0.232 秒、局部恢复 0.8 秒、易化 1 秒、快痕迹 2 秒；稳定度与支持度的名义尺度约 667 秒。弱连接还受经过历史、资格迹和修剪阈值 0.008 共同作用。这次实际观察到正常弱连接消失，而关闭权重遗忘后保留，已把因果来源缩小到遗忘路径，不能仅凭“300”这个数字断言它符合或违背人类记忆。

## 关闭遗忘会不会失去适应能力

在 300 秒后的独立副本中先训练 AB，再训练 AD，各 10 次 0.4、间隔 1 秒，分别测试。新 AD 仍能建立；没有看到关闭遗忘让它完全学不会。第二阶段结果：

{adapted}

关闭遗忘后旧 B 与新 D 都响应；正常组此时旧 B 响应为零。这说明较强的旧响应得以保留，**还不能仅凭并存就判定“压过新经验”或适应变差**，需要明确的相冲突任务和行为目标再评估。本轮测试窗口结束时各组饱和比例均为 0；所有采样的最大比例为 {audit["max_observed_saturated_fraction"]:.4f}，没有观察到持续全网饱和。短时、两个种子的反转试验不等于长期不会饱和。

## 新读出与科学结论的边界

300 个有提示副本分别留下旧、新读出各一份。新工具都检测到一个比例趋稳的窗口；这批目标 D 在该主要排名中的激活为零，目标短暂变化在完整轨迹里。240 个无提示副本没有伪造输入信封来触发“提示响应”，但保存了同样的 5 秒全节点轨迹用于控制。旧算法的分类原样保留。

“模式收敛”回答的是观测节点比例是否稳定；“幅度变化”另答总体是否下降。开启真实遥测时，稳定背景也可能主导排名。读出器如实报告该状态，研究分析再用无提示对照分辨任务相关部分，不能删掉不符合期待的原始激活。新读出不是在本轮后重新设定自主意识标准。

先前 `autonomy-criteria/1` 四项操作标准的通过结论不改写，本轮没有重跑它，也没有宣称检测到了主观体验。以前完成的是消融、恢复、出生副本对照；区域移植仍待做。学术指标收集与相关独立实验属于下一阶段。

## 完整性、限制与下一步

- {audit["verified_cases"]} 份最终快照逐一从数据库解码，与本地规范化模型哈希和内容一致；六份历史父状态核对未变。有效实验没有预算中断、没有供能缺口。
- 累计模拟墙钟 {audit["compute_seconds"] / 60:.2f} 分钟，上限 120 分钟；最大网络 {audit["max_nodes"]} 节点、{audit["max_edges"]} 连接。归档前新增本地＋数据库约 {(audit["local_bytes"] + audit["database_growth_bytes"]) / 2**30:.3f} GiB；最终含归档用量见交付验证，上限 4 GiB。
- 共享账户用量由 {audit["usage_start_percent"]}% 到 {audit["usage_end_percent"]}%；不能把全部变化归因于本任务。已停止扩展实验。
- 两个工具错误透明保留：首个空实例因配置对象类型错误在输入前中断，记为 blocked，不计有效样本；随后一个探测调用参数重复在创建探测前失败，修正后复用已完成训练。都没有修改 Core 或删除失败记录。72 个无提示补充在独立登记后执行。
- 现阶段更值得做的是匹配刺激间隔与保持时间、检验有因果干预的反转任务、判断哪些短暂联想能转成稳定行为；不靠强行降低读出标准获得好看的回答，也不因为目标未留到末尾就抹掉已测到的短暂增益。

完整案例表、快照、输入信封、全节点探测轨迹、两个读出、旧源码见证、执行修订和本报告生成脚本均归档到该项目；报告与四项实验记录可以从“记录与报告”查看。
"""
    en = f"""# Intensity, novelty and 300-second retention: calibration results

[中文](report.zh.md) · 2026-09-29 · Project: `2026-09-29 强刺激、新颖性与遗忘校准`

## Findings

**The strong-input mechanism exists and works.** Its extra term is `intensity_gain × max(0, intensity − 1)`, so earlier intensity-1 input never activated it. A single intensity-4 exposure leaves stronger connections and an observable transient target response at 30 seconds, especially with the extra gain enabled.

**Local novelty exists, but immediate edge formation can precede delayed associative arrival.** A versioned local arrival window retains the old eligibility/formula while waiting for actual signals. At training dose 0.4, target response is **40.66%** greater than immediate settlement; at 0.8 the increase over immediate settlement is **2.26%**; at 0.2 both are zero. No content-importance or correctness score is introduced.

**Failure to retrieve at 300 seconds has two causes.** Ordinary forgetting removes weak new connections; disabling weight forgetting preserves them, yet a 0.5 cue still fails to evoke the target. A cue of 1 evokes a small transient response. Missing output is not always missing structure.

Targets are absent from the later pattern-convergence decision ranks in these tests. The positive effects are early, transient responses in complete trajectories. The main endpoint and secondary measurements are reported separately, without hiding either.

![Calibration]({fig})

## Design and measurements

There are **786 completed platform instances**: 288 intensity, 216 novelty (including 72 separately registered no-cue controls), 240 forgetting and 42 adaptation cases, plus 12 tiny frozen-source legacy witnesses. Seeds are 9293201/9293202; novelty onset phases are 70/110/170 ms. These are small descriptive checks, not a population study or grounds for significance claims.

Intensity/retention use original `continuous-memory/1` parent states. Novelty uses `continuous-memory/2` with explicit immediate/arrival-window modes and gain 0/0.018. Each test is an independent clone and never updates its parent. Anonymous channel labels exist only in external analysis. Recorded real host telemetry is replayed at intensity 0.2 under its original encoder, with hashes and cycles retained. No AI directs behavior.

Inhibition, short-lived self-suppression, depletion/recovery, facilitation and plasticity stay enabled; only registered variables change. External energy supply offers up to 10 units/s without a total cap. Consumption remains active and all unmet demand is zero; local resources are not forcibly replenished. Existing maintenance accounting remains coupled to the disabled starvation-damage option, so this is not a complete metabolic model.

The primary endpoint ranks actual activation at the end of a pattern-convergence decision window. Original steady-state judgments are retained. Secondary target response integrates full-node samples every 100 ms over 5 s and subtracts the matched no-cue clone. Weights below are measured **before the cue**, excluding probe-induced learning. Novelty means cover two seeds × three phases; other tables average two seeds.

## Strong input

The extra gain is identical on/off at doses 0.4 and 1, and effective above 1. Reception still uses response and soft saturation. At age 30 s with a common 0.5 cue:

{strong}

A single dose of 4 and ten doses of 0.4 have equal nominal totals, but different timing. Massed input occurs at seconds 119–128; spaced input at 0,1,2,4,8,16,32,64,96,128. Single exposures also occur at 128, so last-exposure time is matched. Under current forgetting, massed repetition yields more recent target response than this widening schedule. Spacing is not automatically beneficial. Strong single input retains best at 30 s, but new edges in these ordinary-forgetting groups are pruned by 300 s.

No replacement intensity formula or arbitrary forgetting retuning is justified by this audit. Parameter help now explicitly states the greater-than-one threshold. Ordinary UI input and sensory mapping are not silently amplified.

## Novelty

After AB, an overlapping AC pattern creates new edges. Eligible new edges wait until the next propagation time scheduled at birth plus transmission delay. Same-time arrivals are included before one settlement. Eligibility requires a pre-existing local neighborhood and nonzero actual associative touch; gain zero, no neighborhood or no reentry produces no bonus. Deleting an edge cancels its pending birth; a later birth has a new identity. Exact snapshots preserve pending windows.

Within the first observation window, immediate mode awards **8 of 72 births**, versus **24 of 72** with arrival-window mode, among gain-enabled runs. With gain disabled the two modes produce identical target trajectories, guarding against extra scheduling steps creating the effect.

{novelty}

At dose 0.8, the new mode gains about 8.18% over gain-off, but only 2.26% over immediate gain-on. These are different comparisons. The unchanged Git `97d8592` ordering also yields zero bonuses in 3 same-dose and 9 crossed-dose AB→AC witnesses: association can reach B rather than the new A/C endpoints; old propagation also depends on receiver response/saturation. Earlier ordering alone is not sufficient. Formula-preservation tests and natural triggering are distinct evidence.

Select arrival-window `continuous-memory/2` for **new-consciousness defaults after acceptance**. Existing models retain their identities/configuration; memory/1 and immediate mode remain available. This follows improved causal timing and measured local effects, not a claim of solved language, persistent target convergence or universal superiority. The kernel remains labeled as a research version.

## Retention and cue threshold

Read-only historical no-training/spaced-training states are probed at ages 1/10/30/100/300 s. `normal` preserves all defaults; `weight_off` sets only forgetting_rate=0; `slow_off` additionally disables stability/support decay. Activation, inhibition, traces, eligibility and learning remain active.

{retention}

At 300 s, ordinary new A→D edges are absent. Weight-off and slow-off retain approximately 0.041 weight, but only the stronger cue recovers a tiny transient response. Keeping weight alone suffices for this case; disabling every decay process is unnecessary. Old B responses are stored separately from the new target D.

**There is no defensible conversion from 300 model seconds to human hours/days.** Timescales have not been fitted to human behavior. Internal reference scales are activation 0.304 s, inhibition 0.232 s, local recovery 0.8 s, facilitation 1 s, fast traces 2 s and nominal stability/support 667 s. History, eligibility and the 0.008 pruning threshold also affect retention. The controlled weight-forgetting comparison establishes a model-specific cause rather than a human-time analogy.

## Adaptation without forgetting

Independent age-300 clones learn AB then AD, ten 0.4 exposures each at 1-s spacing. After the second phase:

{adapted}

Weight-off/slow-off still acquire the new D response while retaining B. Coexistence is not, by itself, evidence that old experience overwhelms new experience; a task with explicit incompatible demands is needed. Final-window saturation fractions are zero, and the largest sampled fraction anywhere is {audit["max_observed_saturated_fraction"]:.4f}. No sustained whole-network saturation is observed in this bounded study, which is not a long-term guarantee.

## Readout interpretation and integrity

All 300 cued clones have one original and one new readout. The new observer detects a stable proportion window in each; the target has zero activation in the primary ranks, while early target activity remains available in the full curves. The 240 no-cue clones preserve complete 5-s trajectories without fabricating a cue envelope. Real background activity can dominate stable proportions; matched controls distinguish task effects without deleting raw activation.

The previous passed `autonomy-criteria/1` conclusion is retained, not rerun or replaced here. It is an operational research standard, not a validated subjective-experience test. Earlier work used ablation, restoration and birth clones, not regional transplantation. Academic-indicator collection and independent experiments remain a subsequent phase.

All {audit["verified_cases"]} final states were decoded from the DB and checked against local canonical hashes/content; six historical parents are unchanged. No effective case stopped for budget or unmet energy. Simulation wall time is {audit["compute_seconds"] / 60:.2f}/120 min; maximum network {audit["max_nodes"]} nodes/{audit["max_edges"]} edges. Pre-archive local+DB growth is {(audit["local_bytes"] + audit["database_growth_bytes"]) / 2**30:.3f} GiB; final delivery records include archive overhead within 4 GiB. Shared account usage moved {audit["usage_start_percent"]}%→{audit["usage_end_percent"]}%, not attributable exclusively to this study.

Two runner errors are preserved: an empty startup case failed on a configuration-object type before input, and one probe call failed on a duplicate keyword before probe creation. Both were fixed without changing Core or erasing records; completed training was reused. A registered supplement supplied the 72 missing no-cue controls.

Next priorities are matching repetition intervals to measured retention, task-defined reversal tests with interventions, and determining when transient association becomes stable behavior. Full cases, snapshots, inputs, trajectories, both observers, frozen legacy witnesses, execution amendments and report-generation sources are archived in the new project. Two reports and four experiment records are available in the platform.
"""
    for lang, body in (("zh", zh), ("en", en)):
        (HERE / f"report.{lang}.md").write_text(body, encoding="utf-8")
        shutil.copy2(HERE / f"report.{lang}.md", WORK / f"report.{lang}.md")
    figures(rows)


def figures(rows):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.5), constrained_layout=True)
    q = select(rows, stage="probe", cue_intensity=0.5)
    for gain, label in ((0.0, "Extra intensity gain off"), (0.075, "Extra intensity gain on")):
        dose = (0.4, 1, 1.5, 2, 4)
        values = [
            average(q, "initial_AD_weight", family="intensity", protocol=f"single_{d:g}", gain=gain, age_s=30)
            for d in dose
        ]
        axes[0, 0].plot(dose, values, "o-", label=label)
    axes[0, 0].set(
        xlabel="Single input intensity", ylabel="Weight before cue", title="A. Strong input: retained edge at 30 s"
    )
    axes[0, 0].legend()
    for mode, label in (("immediate", "Immediate"), ("arrival-window", "Arrival window")):
        dose = (0.2, 0.4, 0.8)
        values = [average(q, "D_cue_integral", family="novelty", mode=mode, dose=d, gain=0.018) for d in dose]
        axes[0, 1].plot(dose, values, "o-", label=label)
    axes[0, 1].set(
        xlabel="Training intensity",
        ylabel="Cue minus no-cue integral (a.u. s)",
        title="B. Novelty: transient target response",
    )
    axes[0, 1].legend()
    for condition, label in (
        ("normal", "Normal"),
        ("weight_off", "Weight forgetting off"),
        ("slow_off", "Slow structural decay off"),
    ):
        ages = (1, 10, 30, 100, 300)
        values = [
            average(
                q, "initial_AD_weight", family="forgetting", protocol="spaced_ordinary", condition=condition, age_s=age
            )
            for age in ages
        ]
        axes[1, 0].plot(ages, values, "o--" if condition == "slow_off" else "o-", label=label)
    axes[1, 0].set(
        xlabel="Age after last exposure (simulation s)",
        ylabel="Weight before cue",
        title="C. Weight can persist below retrieval threshold",
        xscale="log",
    )
    axes[1, 0].legend()
    names = ("normal", "weight_off", "slow_off")
    for offset, field, label in (
        (-0.17, "B_cue_integral", "Previously trained B"),
        (0.17, "D_cue_integral", "Newly trained D"),
    ):
        values = [average(q, field, family="adaptation", condition=c, phase=2) for c in names]
        axes[1, 1].bar([i + offset for i in range(3)], values, width=0.32, label=label)
    axes[1, 1].set_xticks(range(3), ("Normal", "Weight off", "Slow off"))
    axes[1, 1].set(ylabel="Cue minus no-cue integral (a.u. s)", title="D. After reversal: old and new responses")
    axes[1, 1].legend()
    fig.suptitle(
        "Mechanism calibration | Complete groups, descriptive means | Late target decision activation = 0", fontsize=12
    )
    path = WORK / "overview.png"
    fig.savefig(path, dpi=160)
    fig.savefig(WORK / "overview.pdf")
    plt.close(fig)
    shutil.copy2(path, ROOT / "docs/images/mechanism-calibration-2026-09-29.png")


if __name__ == "__main__":
    write()
