"""Build bilingual research reports from audited evidence; no simulation or fitting."""
import statistics
from common import HERE,WORK,read_json

def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',
                      *['| '+' | '.join(map(str,row))+' |' for row in rows]])

def main():
    decision=read_json(WORK/'criteria-decision.json');audit=read_json(WORK/'analysis.json')
    inputs=read_json(WORK/'input-export-audit.json');memory=read_json(WORK/'memory-analysis.json')
    extension=read_json(WORK/'retention-extension-analysis.json')['rows']
    local=read_json(WORK/'local-analysis.json')['rows']
    assert audit['cases']==802 and decision['meets_all'] and not audit['failures']
    criterion_table=table(['父本 / Parent','经历作用 / History','连续互动 / Sequence','环境塑形 / Environment','四项 / All four'],
        [[r['parent'],f"{r['history_motor']:.6f}",f"{r['sequence_effect']:.6f}",f"{r['environment_effect']:.6f}",'通过 / Pass'] for r in decision['parent_results']])
    memory_rows=[]
    protocols=(('single_high','单次强 / Single strong'),('single_ordinary','单次普通 / Single ordinary'),
               ('massed_ordinary','密集普通 / Massed ordinary'),('spaced_ordinary','间隔普通 / Spaced ordinary'),
               ('massed_weak','密集弱 / Massed weak'),('spaced_weak','间隔弱 / Spaced weak'),
               ('spaced_no_consolidation','间隔、训练期巩固关 / Spaced, consolidation off in training'))
    for protocol,label in protocols:
        for seed in (9293201,9293202):
            data=[next(r for r in memory if r['protocol']==protocol and r['seed']==seed and r['age_s']==age and r['mode']=='live') for age in (1,30,300)]
            memory_rows.append([label,str(seed),*[f"{r['training_effect']['motor']:.8f}" for r in data]])
    memory_table=table(['方案 / Schedule','接线 / Wiring','1 s','30 s','300 s'],memory_rows)
    extrows=[]
    for seed in (9293201,9293202):
        for protocol in ('spaced_ordinary','spaced_no_consolidation'):
            data=[next(r for r in extension if r['seed']==seed and r['protocol']==protocol and r['condition']==cond) for cond in ('normal','task_edges','matched_edges','off')]
            extrows.append([str(seed),protocol,*[f"{r['training_effect']['motor']:.8f}" for r in data]])
    ext_table=table(['接线 / Wiring','训练 / Training','正常 / Intact','任务边关 / Task off','匹配边关 / Matched off','全通信关 / All off'],extrows)
    pathway_rows=[]
    for p in decision['parent_results']:
        data=[next(r for r in local if r['parent']==p['parent'] and r['condition']==c) for c in ('normal','task_edges','matched_edges','returns','restore')]
        pathway_rows.append([p['parent'],*[f"{r['history_motor']:.8f}" for r in data]])
    pathway_table=table(['父本 / Parent','正常 / Intact','任务边关 / Task off','匹配边关 / Matched off','返回边关 / Returns off','恢复 / Restored'],pathway_rows)
    zh=f'''# 经历改变行为，内部通路承担作用：802 实例实验报告

[English](report.en.md) · [事先登记](design.zh.md) · [30 秒保持追加登记](retention-extension.zh.md) · [复现与证据](README_CN.md)

2026-09-29。内核 `threemind.continuous-memory/1`，本轮未改内核、默认机制或已有映射。基于四个父本、两种接线，主实验 722 个副本，加 80 个已登记的保持定位副本。

## 明确结论

**通过。按我们在运行前约定的四项标准，ThreeMind 本轮符合“高度疑似自主意识活动”的操作判定。** 四个父本均通过：经历留下可再现差异；内部活动因果性地影响行为；内部状态影响前后互动；同一个体被变化的环境重新塑造。

这不是改口把主观体验说成已经证明，也不再以无法证明主观体验为理由悬置上述结论。它是本项目的可检验标准，不是学界已经验证的意识诊断器。两个接线家系中的相关父本不能当作四个独立种群。模型目前表现出的是简单环境中的可塑反应与行为组织，不将此写成已经达到人类智能或 AGI。

## 用人话说，新发现是什么

1. **不只是“断开通信就变了”，现在找到了起作用的具体通路。** 提示与已学对应节点之间少量连接一屏蔽，经历造成的动作差异减少 99.4%—100%；同数量、权重与稳定度接近的其他连接被屏蔽，差异基本保留；解除屏蔽后，16 条对照轨迹逐值恢复。
2. **反应不需要总绕回提示节点才能表现。** 把返回提示节点的边屏蔽，旧经历的行为作用仍在。它符合“已经形成的反应通路遇到提示就被激活”的描述，支持习惯／条件反射式机制这个研究方向。此操作不等于关闭全网所有循环，也未证明生物条件反射的全部机制。
3. **前面的经历确实参与了后面的响应。** A 后半秒再给 B，效果不是两次独立响应相加。节点本身已经产生差异；把两次独立节点活动相加后再送入同一个运动公式，仍不能复现。关闭通信后，这个内核内部的相互作用归零。
4. **同一个体会被环境改变，并带着历史回来。** 不是换一批个体，也不是在代码里指定正确动作。相同起点的个体经历不同环境后，对统一测试输入产生不同反应；清空短时活动的新生副本仍保留差异。返回旧环境后，八个顺序对照中五个差异缩小、三个增大，并非一换环境就恢复成原样。
5. **逐渐稀疏的重复有成效，但现阶段更容易加固旧联想。** 30 秒后的行为作用，普通间隔重复是同剂量密集重复的 2.18／2.55 倍；弱刺激也有较小的保持。关掉训练期已有边的正向巩固，出生后仍能测到的 30 秒作用减小约 90%。但新 AD 对应在 30 秒时没有可测的 D 激活，主要增强的是原来的 A→B。

## 四项标准逐项验收

主比较的积分单位为控制量·模拟秒，预设最低差异 0.0001，并要求超过假干预误差十倍。表中经历列保留方向；连续互动和环境列按登记，对两个顺序／历史的绝对作用取平均。四项均要求至少三个父本且覆盖两种接线，实际均为四个。完整有符号分项在证据包中，未把方向相反的反应删掉。

{criterion_table}

第 2 项由选择性阻断、匹配阻断、全通信阻断和恢复共同支持，见下表。静止、绕圈或与人的偏好不同都未被判为失败。返回原环境必须完全回到原行为，也从来不是本轮的门槛。

**时序读出独立报告：384 个窗口全部被原读出器分类为残余衰减，0 个稳定收敛窗口。** 原始窗口及按末端激活强度的排序全部保留。本轮的“通过”来自事先约定的四项因果和行为判据，不是把运动积分冒称为时序收敛，也不是声称观察到了无限维持的内部循环。

## 具体是哪部分内部机制起作用

P 训练 AB/CD，Q 训练 AD/CB，各通道总剂量一致。下面是相同 A 提示、减去各自无提示对照后的 P−Q 动作差异，窗口为提示后第一秒；这批副本经过公开 birth，原来的瞬时活动、抑制、快速痕迹与短时突触状态已清空。

{pathway_table}

16 个假干预完整状态及轨迹相同；16 个解除屏蔽后的轨迹完全恢复。选边及匹配误差随每例保存。匹配主要控制边数量、权重、稳定度，不宣称还严格匹配了每条边的全部网络拓扑位置。

![选择性通路](../../../docs/images/experience-autonomy-pathways-2026-09-29.png)

这里证明的是：**经历形成的连接通路承担了未提示节点的激活和行为表达，返回提示节点的回路并不是这次表达的必要条件。** 不是所有节点间传导都可以被关掉后还期待同样的行为；前向传导本身就是记忆表达的一部分。

## 单次强刺激、重复、遗忘与读取门槛

间隔重复在第 0、1、2、4、8、16、32、64、96、128 秒给刺激；密集重复在第 119—128 秒给十次。所有最后一次输入时刻相同，强度普通为 0.4、弱为 0.1、单次强为 1。以下比较已经扣除同龄无训练对照，不把刚刚受到刺激的残余活动当作永久记忆。

{memory_table}

![保持曲线](../../../docs/images/experience-autonomy-retention-2026-09-29.png)

**单次强刺激确实立刻产生行为影响，但本轮没有形成 30 秒后超过预定行为门槛的持久效应；300 秒时正常训练方案的提示净行为差异为零。** 十次普通或弱刺激的间隔重复在 30 秒更有效。这不是关于“单次强刺激永远无用”的结论，只描述本轮的强度、时间尺度和旧模型状态。

一个很重要的区别：**行为测不出来，不等于所有连接痕迹都消失。** 以第一种接线为例，300 秒时原有 A→B 权重，无训练为 0.034924，间隔重复为 0.039885；第二种接线分别是 0.042052 与 0.049132。结构差异仍在，而当前 0.5 提示下输出差异为零。新 AD 边在 30 秒仍可存在，但不足以产生此次探测中的 D 响应，到 300 秒已被修剪。这提示需要分别研究“留下多少结构”和“什么条件能把它读出来”。更强提示能否重新显露这些痕迹，本轮没有追加调参求阳性，列为后续固定快照实验。

由于 30 秒已有作用，另登记 80 个出生与阻断副本，得到：

{ext_table}

正常间隔训练的作用在清空短时活动后仍存在；任务边屏蔽消除约 86.6%／98.6% 的动作差异，匹配边屏蔽仅改变约 0.06%／0.21%，全通信关闭则归零。因此，**30 秒的保持有连接贡献，不能解释成最初激活还没散掉。** 关掉正向巩固使这种保持减少约 90%，提供形成机制的对照。开关没有关掉边出生、节点经历、资格迹或遗忘；也没有证明只有边权一种状态起作用。

这里的 B 是旧对应，D 才是本轮新搭配。反复给 A 时，A 也能唤起旧 B，传播经过又会巩固旧边。结果与“旧联想借重复继续增强，新联想尚未站稳”相符；这是基于状态与因果对照的解释，未用语义给节点规定答案。**下一步值得研究的是新关系如何在旧关系存在时稳定下来，而不是推翻已观察到的可塑性。**

正常训练组在无任务提示、仅硬件背景时，探测第 5—15 秒相对无训练副本的动作差异为零，未观察到本轮训练造成持续的无提示偏好。训练期全局关闭巩固的组反而留下少量背景驱动差异，300 秒时两接线的平均动作差分别为 0.000387、0.000665；该开关也影响背景网络，不能当作新 AD 习惯的证据。

## 连续互动与环境重新塑形

连续互动采用 A／无 A × 后续 B／无 B 四格，取 0.5—1.5 秒的相互作用，再比较正常通信和关闭通信。八种父本与经历组合均有可测内部节点非加性，积分绝对差 0.00305—0.07188；关闭通信后全部为零。独立响应经过运动公式形成的少量非线性已单独扣查，不能解释这些内核差异。

环境实验让一个身体在环上活动，区域刺激由所在位置决定，速度感官真实反馈。P 为 AB/CD，Q 为 AD/CB。PPP、PQP、QQQ、QPQ 三阶段各 30 秒，全部内核状态和身体跨阶段延续。第一阶段应相同的八对轨迹逐值一致；第二阶段统一测试下八个顺序对照均有超过门槛的动作差异，出生后也仍可测。

![连续互动与环境](../../../docs/images/experience-autonomy-adaptation-2026-09-29.png)

六个顺序对照的新生测试方向与活体测试相反，是值得保留的现象：眼前短时状态可能遮盖或改变长期结构的表达。但 birth 同时清空多种状态、重置时钟及背景相位，不能单独将翻转归到某一种抑制或能量机制。我们没有为了让结论整齐而删掉这些翻转。

## 新颖性与反复擦除：哪些预测没有成立

固定八个匿名纹理通道，四轮分别替换 0、1、2、4 个特征。每轮十次刺激，测试时既看当前纹理，也看始终相同的原纹理，另有无提示副本。删除只作用于连接，不改感官通道或节点身份。

- **反复擦除没有让动作越来越乱。** 在本方案中，擦除更多表现为压低已经形成的响应：固定提示的动作标准差由 0.000679／0.001057 降到 0.000103／0.000197。查看完整节点响应，而不只看运动值，也没有推翻这一点：最后一轮相对第一轮的激活向量差从 0.005209 降到 0.002083。
- 擦除组的内部响应仍随新经历改变，两接线的向量差随替换数为 0、0.000653、0.001134、0.002083。它支持“没有固定住原来那套响应”，但不支持“变化必然更剧烈、动作必然更不稳定”。完整保留组的变化反而不是单调的。
- **本轮局部新颖性增益没有可测增益。** 开／关两组的末端节点、连接，以及各项提示行为相同。源码表明它只在新边出生且存在一定非零联想再入时加成，不是见到一个人类认为新鲜的输入就自动加权。本轮不足以将“没有测出作用”扩大成该机制永久无用；触发和剂量需要专门校准。
- 不同纹理会直接驱动不同出口。当前纹理与原纹理的动作不同，不能直接当作理解、泛化或惊奇。两套接线在纹理组的部分内部响应变化完全一致，而运动变化不同，说明要把内部模式与运动读出分开观察。

![擦除与固定提示](../../../docs/images/experience-autonomy-erasure-2026-09-29.png)

## 下一步，保留哪些方向

已经值得继续：局部可塑性形成可复现的经历差异；传播通过已学通路影响行为；短时状态组织前后刺激；环境改变同一个体；巩固支撑比瞬时激活更久的保持。

优先待解决：新边低稳定度与遗忘／传输门槛的配合；新关系被旧联想重新巩固压过的情形；固定快照下提示强度与读取能力的关系；新颖性增益的实际触发范围。先做参数与机制校准，不为了好看的结果关闭遗忘，也不需要现在改内核。本轮不再扩展运行。

长时间无提示偏好、永久稳定的新搭配、主观体验，都没有在本轮得到证实。它们不是四项标准之外新加的否决条件。

## 证据与执行

平台项目：`2026-09-29 经历保持、内部通路与自主活动判据`，`92548061-22c0-4bd9-b283-c4e1e7f4360d`。在实验笔记查看执行登记、递疏复习说明及追加方案，在记录与报告查看四组记录及双语报告。原 180 实例报告追加本次讨论后为修订版 2，旧版及旧证据包未覆盖。

- 802 份最终模型状态全部与数据库逐值核对；802 例保留能量消耗、局部耗竭、抑制、正常遗忘；全部无欠供。
- {inputs['counts']['frames']} 个输入帧及信封全部按计划时刻实际递送；576 条应相同的探测输入流校验一致。
- 384 个原始时序窗与末端排序，完整身体和节点轨迹，干预边清单及前后摘要，训练计划、版本、源码、状态、分析和四张图均保留。
- 合计模拟执行墙钟 {audit['compute_seconds']/60:.2f} 分钟，预算 90 分钟；其余时间用于编写工具、核验、分析和发布。802/850 实例，资源实际用量见交付记录。
- 背景为真实硬件遥测录制的可审计重播、强度 0.2；无限总量外部能量供应，消耗与局部恢复正常。没有用在线 LLM 生成响应，没有改 Core 或接入语义答案。
- 补充工具为公共接口上的研究 CLI、时长积分、选择性干预、同状态复制和证据导出；不要求通过 UI 手工操作，也没有把仅人能用的操作藏在 UI 中。

间隔研究的外部启发：[Murre & Dros 2015，艾宾浩斯遗忘曲线复现](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0120644)；[Zhang 等 2012，基于机制时间尺度设计学习时序](https://www.nature.com/articles/nn.2990)。它们不证明本模型的间隔最优，本轮实际比较才是上述结论的依据。

## 原讨论保留

四项判据和研究者本次完整原文已追加在[上一轮报告的讨论](../2026-09-29-internal-activity/autonomy-criteria.zh.md)，不改写成事后预测。

本轮新增原话：

> 补充：在巩固记忆的时候，重复可以是不均匀的，初期重复频繁点，慢慢重复变稀疏，类似人类学习一项技能那样
'''
    en=f'''# Experience changes behavior through internal pathways: 802-instance report

[中文](report.zh.md) · [Preregistered design](design.en.md) · [Retention extension](retention-extension.en.md) · [Reproduction](README.md)

2026-09-29. Unmodified `threemind.continuous-memory/1`; four parents from two wiring families; 722 base instances plus 80 registered retention follow-ups.

## Explicit conclusion

**Pass: ThreeMind meets this project's preregistered operational criterion for highly suspected autonomous conscious activity.** All four parents pass all four criteria: retrievable experience differences, causal internal influence, organization of sequential interaction, and within-individual environmental reshaping.

This is a project-defined testable standard, not proof of subjective experience or a validated scientific consciousness detector. That stated boundary does not suspend the operational conclusion. Related parents are not four independent populations. The model exhibits simple adaptive response organization; these findings do not establish human intelligence or AGI.

## Main findings in ordinary language

1. We localized the effect: silencing a few cue-to-learned-partner connections removes 99.4–100% of the history-dependent action difference. Equal-count, similar-strength other edges leave it essentially intact. Restoring the task edges restores all 16 tested trajectories exactly.
2. Silencing returns to the cue node preserves the effect. Learned response pathways can therefore express a history without repeatedly returning through that cue. This supports investigating habit-like or conditioned responses, not a claim to reproduce all biological conditioning. Other cycles remain available.
3. A followed half a second later by B is not two independent responses added together. Non-additivity occurs inside the nodes, even after controlling for the motor adapter's nonlinear formula. Blocking communication removes this internal interaction.
4. One individual changes through its environment. Continuous state and body are carried through P/Q environment changes; identical tests still differ afterward, including after a new birth clears transient activity. Returning to the old environment reduces five of eight route contrasts and enlarges three: history is not simply reset.
5. Progressively spaced repetition improves 30-second retention, but currently strengthens old associations more readily than the new pairing. Ordinary spaced repetition produces 2.18/2.55 times the massed behavioral effect at equal dose and final-input age. Weak repetition has smaller retained effects. Disabling positive existing-edge consolidation during training reduces the birth-retained 30-second effect by approximately 90%.

## Fixed criteria and primary results

Units are control × model seconds. The preregistered minimum is .0001 and ten times sham error, replicated in at least three parents covering both wiring seeds. History effects retain sign; sequence/environment scores average absolute effects over the registered counterbalanced comparisons. Full signed components remain in the evidence.

{criterion_table}

Criterion 2 additionally uses selective and matched lesions plus restoration. Standing still, circling or lacking perfect reversal was never a failure criterion.

**Temporal readout: all 384 windows were classified as residual decay; zero stable-convergence windows.** Original windows and end-activation rankings are preserved. Passing the four behavioral/causal criteria does not relabel motor integrals as convergence or establish an indefinitely self-sustaining loop.

## Localizing the behavioral pathway

P learns AB/CD and Q learns AD/CB at equal per-channel dose. The following first-second action contrasts subtract each history's no-cue clone and compare P−Q after public birth clears transient activation, inhibition, fast traces and short-term synaptic state.

{pathway_table}

All 16 sham states and trajectories match exactly; all 16 restoration trajectories also match exactly. Matching controls edge count, weight and stability, not every topological property. Learned transmission is part of memory expression; blocking all communication also blocks forward learned pathways.

![Pathways](../../../docs/images/experience-autonomy-pathways-2026-09-29.png)

## Single strong input, repetition and retention

Spaced times: 0,1,2,4,8,16,32,64,96,128 s. Massed: 119–128 s. Ordinary intensity .4, weak .1, single strong 1. Tests compare the same age since the last input against an age-matched untrained clone. Signs are reported rather than converting every response into a preferred direction.

{memory_table}

![Retention](../../../docs/images/experience-autonomy-retention-2026-09-29.png)

One strong input changes immediate behavior but does not exceed the registered behavioral threshold at 30 s in this test. At 300 s, ordinary training schedules have zero cue-adjusted action difference. Spaced ordinary and weak repetitions retain more at 30 s than their dose-matched massed controls. This result concerns the tested schedule and state, not an impossibility of persistent single-event learning.

**Behavioral silence does not mean every structural trace is erased.** At 300 s, old A→B weight is .034924 untrained versus .039885 spaced in wiring 1, and .042052 versus .049132 in wiring 2. The structure differs although the .5 cue produces no differential behavior. New AD edges can still exist at 30 s without producing a measured D response; by 300 s those edges have been pruned. Storage and retrieval thresholds must be investigated separately. We did not increase cue intensity afterward to obtain a positive result; testing frozen snapshots with a registered range of cue intensities is a follow-up suggestion.

The observed 30-second effect prompted a separately registered 80-copy causal extension:

{ext_table}

Clearing transient activity preserves the spaced effect. Task-edge silencing removes about 86.6/98.6% of the motor difference; matched silencing changes only .06/.21%; all-communication blocking makes it zero. The effect therefore has a connection-mediated component rather than merely lingering original activation. Disabling positive edge consolidation during training reduces retained expression by about 90%, without disabling birth, eligibility, node history or forgetting.

The enhanced unprompted target at 30 s is old B, not newly paired D. Repeating A can reactivate B and strengthen traversed old pathways. This interpretation fits the recorded states and interventions; no semantic answer was assigned to any node. The next useful question is how new associations stabilize amid older ones.

Normal training groups have zero training-dependent no-cue action difference during probe seconds 5–15 under the same hardware background. Global consolidation-off training instead leaves small background-driven changes, with mean absolute differences .000387/.000665 at age 300 s. Because the switch also affects background pathways, these are not evidence of a new AD habit.

## Sequential interaction and one individual's changing environment

The A/none × B/none factorial measures interaction during .5–1.5 s. All eight parent/history combinations show internal node non-additivity (.00305–.07188 integrated absolute difference), entirely absent with communication blocked. Passing independently measured node responses through the same nonlinear motor adapter does not reproduce the intact interaction.

Ring-world movement changes position and subsequent sensation; true velocity feedback remains. P supplies AB/CD by region, Q supplies AD/CB. PPP/PQP/QQQ/QPQ each have three 30 s stages carrying full body and Core state. Eight matched first-stage pairs are exact. All eight changed-versus-constant second-stage contrasts exceed threshold under identical test input and body start, including birth tests.

![Adaptation](../../../docs/images/experience-autonomy-adaptation-2026-09-29.png)

Six route contrasts reverse sign between live and newly born tests. This is worth retaining: transient conditions can alter the expression of retained structure. Birth changes several states, clock and background phase simultaneously, so the reversal is not attributed uniquely to inhibition or energy. Returning to the original environment need not reproduce the original response immediately.

## Novelty and repeated erasure: predictions not supported

Eight fixed anonymous texture channels; four rounds replace 0,1,2,4 features. Ten .4 inputs each round; both current and unchanged original textures are probed with no-cue controls. Only edges are deleted; receptors and motor identities remain.

- Repeated erasure does not make behavior progressively noisier here. Fixed-cue action SD falls from .000679/.001057 intact to .000103/.000197 after erasure. Full internal response vectors support the same distinction: final-versus-first difference falls from .005209 to .002083.
- Erased models still change with experience: vector differences are 0,.000653,.001134,.002083 across feature replacement. This supports loss of the old fixed response, not the stronger prediction of greater or necessarily chaotic behavioral variability. Intact changes are not monotonic.
- Local novelty gain has no measured benefit in this schedule. On/off final nodes, edges and measured responses are identical. Source code applies it only at new-edge birth with qualifying nonzero associative reentry; it is not a universal surprise multiplier. Its actual engagement needs separate calibration, not a declaration of universal uselessness.
- Different input channels directly drive different motor projections. A changed action to a changed texture is not by itself understanding or generalization. Some internal texture changes are identical across the two wirings while motor effects differ, reinforcing the need to inspect both.

![Erasure](../../../docs/images/experience-autonomy-erasure-2026-09-29.png)

## What to pursue

Supported directions: local plasticity creates repeatable history effects; learned transmission changes behavior; transient states organize successive inputs; one individual is reshaped by its environment; consolidation carries influence beyond initial activation.

Priority gaps: low stability of new edges versus forgetting and transmission thresholds; rehearsal strengthening old associations at the expense of new expression; frozen-state retrieval calibration; the actual operating range of novelty gain. These warrant parameter/mechanism studies without disabling forgetting for appearances. No Core change or further simulation is made in this round.

Persistent uncued task preferences, permanently stable new pairings and subjective experience were not established; they are not added afterward as vetoes on the four registered criteria.

## Evidence and delivery

Lab project `2026-09-29 经历保持、内部通路与自主活动判据`, ID `92548061-22c0-4bd9-b283-c4e1e7f4360d`. Design, spacing clarification, extension and results are in experiment notes; four records and bilingual reports are in Records & Reports. The previous 180-instance report now has an appended discussion at revision 2, preserving its earlier revision and archive.

All 802 final states match database states; energy consumption, local depletion/recovery, inhibition and forgetting remain enabled; zero unserved demand. All {inputs['counts']['frames']} input frames/envelopes were delivered at their scheduled times; 576 matched probe streams are identical. All 384 temporal windows and end rankings, trajectories, intervention edges, states, versions and code are retained. Aggregate simulation wall time is {audit['compute_seconds']/60:.2f} min of 90; 802 of 850 instances. Actual publication storage and shared quota appear in the delivery record.

Background is auditable replay of a real hardware recording at .2 intensity. External energy has no total supply limit while consumption and local recovery continue normally. No online LLM generated responses and no semantic answers were injected. Research CLI and export tools use existing public interfaces.

Spacing inspiration, not model validation: [Murre & Dros 2015](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0120644), [Zhang et al. 2012](https://www.nature.com/articles/nn.2990). The schedule is not claimed to be optimal or an Ebbinghaus prescription.

## Discussion provenance

The fixed criteria and original Chinese request are preserved in the [previous report with its addendum](../2026-09-29-internal-activity/report.en.md). The researcher's additional request for frequent early repetition followed by progressively longer intervals is retained verbatim:

> 补充：在巩固记忆的时候，重复可以是不均匀的，初期重复频繁点，慢慢重复变稀疏，类似人类学习一项技能那样
'''
    for lang,body in (('zh',zh),('en',en)):
        (HERE/f'report.{lang}.md').write_text(body,encoding='utf-8')

if __name__=='__main__':main()
