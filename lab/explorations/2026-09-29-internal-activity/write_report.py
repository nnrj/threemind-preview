"""Render bilingual reports from audited result tables."""
from common import HERE, WORK, read_json

def main():
    audit=read_json(WORK/'analysis.json')
    birth=read_json(WORK/'birth-analysis.json')
    expression=read_json(WORK/'expression-analysis.json')
    rows=[r for r in birth if r['communication']=='on']
    table='|父本 / Parent|未提示节点的经历差异 / Activity contrast|运动输出的经历差异 / Motor contrast|关闭通信后两项 / Both with communication off|\n|---|---:|---:|---:|\n'
    for r in rows:
        off=next(x for x in birth if x['parent']==r['parent'] and x['communication']=='off')
        assert off['association_contrast'][0]==off['P_minus_Q_net_control'][0]==0
        table+=f"|{r['parent']}|{r['association_contrast'][0]:.6f}|{r['P_minus_Q_net_control'][0]:.6f}|0 / 0|\n"
    e=next(r for r in expression if r['parent']=='s9293201/region0' and r['condition']=='temporary_off')
    recovery=[p['control_mae'] for p in e['phases']]
    minutes=audit['compute_seconds']/60
    zh=f'''# 内部活动确实改变了行为：180 个实例的因果对照

[English](report.en.md) · [执行前登记](design.zh.md) · [出生验证追加登记](validation.zh.md)

**本轮确认了：相同先天模型经历不同的共现刺激后，面对同一个提示，会激活不同的未提示内容，并产生不同运动输出。清空即时活动、作为新个体出生后，这种差异仍然保留；关闭内部通信，出生副本的这两项差异均归零。**

这使“内部活动影响行为”从观察图像变成了有匹配干预支持的结果。上一轮的停留比例没有充分显示它；本轮记录完整动作和节点活动后看到了。方向值得继续研究：经历能够留下改变，保留的改变能够通过内部联想影响身体。

这里的影响主要持续几百毫秒到数秒，尚未显示在相同当前输入下长期维持不同策略的内部状态。**本轮能确认经历依赖的联想和行为影响，尚不足以把模型认定为高度疑似具有主观意识。** 这一区分限定结论，不取消已经观察到的能力。

## 1. 讨论已经追加，旧结果保持可追溯

上一轮[中英文报告补记](../2026-09-29-input-rate-and-autonomy/discussion-addendum.zh.md)已写到报告末尾，数据库报告均为第 2 版，原第 1 版和原始归档保留。明确撤回两种过宽解释：不能把完全断输入后不能无限维持当成失败；不能把测试时停留分数相近说成内部通信对全部行为或形成过程都无用。静止、绕圈与其他行为平等记录，不额外惩罚。

## 2. 第一组：同一个模型，临时切断内部联络再接回

沿用上一轮两种身体接线、各两个选择方向的四个父本。每个出生并在原环形世界暖机 20 秒，从同一完整状态复制。正常分支继续闭环 20 秒；另外七个分支接收其完全相同的感官输入和录制宿主背景。

假干预的 **4/4** 副本完整动作、轨迹和最终 Core 状态与正常分支完全相同。共 **32 个表现分支**的逐帧刺激核对一致。因此干预后的差异不是输入换了或复制错了。

全程关闭通信、分别关闭激活传导/抑制扩散、5–10 秒临时关闭通信、5–10 秒静默两组互补连接，均记录。两组连接按预先固定哈希分配，不按结果挑选，不称作预先识别出的脑区。保留感官节点和运动出口，已经发出的信号仍到达。

**内部联络确实改变动作。** 第一接线的绕圈个体，关闭通信后 0–5 秒平均控制差约 0.019，15–20 秒约 0.025；第二接线的停留个体，全关通信的差异小得多，但只阻断部分连接也能引起更明显的瞬时变化。总体行为类型不变不代表动作完全不变；部分阻断不必比全部阻断影响更小，平衡抵消是值得进一步核查的解释。

在第一接线、目标 0 的临时阻断分支，四段 5 秒的平均动作差依次为 **{recovery[0]:.6f}、{recovery[1]:.6f}、{recovery[2]:.6f}、{recovery[3]:.6f}**。阻断前一致，阻断期间改变，恢复后逐渐接近；实际传输也重新发生。不能要求解除阻断消除已经积累的经历和身体位置差异。

![内部干预与恢复](../../../docs/images/internal-activity-intervention-2026-09-29.png)

这些图显示匹配输入下的反事实动作差。干预副本身体仍按自身动作运动，但感官按正常副本回放，所以不能把它们当成各自自由闭环产生的成功率或新适应策略。

## 3. 第二组：同样的起点，不同的经历

每个暖机状态分别接受 P：AB/CD、Q：AD/CB。A/B/C/D 是原来已经存在的感官通道，名称只是观察标签。两套经历各 80 帧，先每对连续 20 次，再各 10 次、各 10 次；1 秒间隔，强度 0.8。每个通道都出现 40 次。改变的是共现对象，未改变通道编号、总剂量、总训练时长、运动接线或内核机制。

训练期通信开/关各一组，得到 16 份训练结果。末次输入后等 1 秒，独立复制 A、C、无提示副本，再交叉测试期通信开/关，得到 96 个测试。提示强度 0.5，背景持续 0.2。所有匹配提示的后续外部输入完全一致。

**正常训练、正常测试的四父本×两提示，八个经历对比均出现符合共现关系变化的未提示节点响应差异。** 例如第二接线、目标 1 父本，提示 A：P 经历后的 B 响应积分为 0.016531、D 为 0；Q 经历后的 B 为 0、D 为 0.016798。这里 B/D 没有被当前提示直接输入。数值先扣除了同一训练状态的无提示副本，统计提示后首秒；不是把训练残留整体变亮当作记忆。

其他父本也有经历差异，但并非都彻底交换主导对象：有的在 Q 后仍同时唤起 B 和 D。原有经历与新经历叠加，这些结果完整保留，不只挑“答对”的副本。

**训练时关闭通信，并没有阻止共同输入形成这种差异；恢复测试期通信后仍能表达出来。** 这与当前共同输入可直接改变连接的实现一致。部分训练关闭分支的差异甚至更大，说明形成过程和表现过程需要分别研究；不能笼统说通信越多越好，也不能据此默认关闭通信。是否存在传播带来的竞争或干扰，本轮尚未拆分。

## 4. 追加验证：不是只剩刚才的一点激活

在上述结果出现后，追加登记并纳入全部八个正常训练的 P/Q 父本。通过原有公开出生接口生成新个体，清空即时激活、抑制、在途信号、短时突触状态和快痕迹，继承结构和长期节点历史。每份再做 A/无提示×测试通信开/关，共 **32 个副本**，不复活或重置原个体。

结果如下，均为提示后首秒的积分；运动输出本身范围为 −1 到 1。正负代表 P 与 Q 的方向差，不表示好坏。

{table}

未提示节点差异的定义为 `(B−D)在P下 − (B−D)在Q下`，每一项先减对应无提示副本；运动差异为 P 的净控制量减 Q 的净控制量。积分按实际采样间隔加权，不能让早期 10 ms 采样因点数多而占额外权重。

**四个父本的经历差异均在出生后保留，且需要测试期内部通信才能表达为这些未提示活动和运动差异。** 这排除了“只因刚才还亮着”和“只有固定接线、当前直接输入就足以解释全部差异”这两种解释。出生同时保留连接结构和节点长期历史，尚不能把全部保持都归给某一条边或某一个变量。

![出生后仍保留的经历差异](../../../docs/images/internal-activity-retention-2026-09-29.png)

![四个父本的真实未提示节点响应](../../../docs/images/internal-activity-recall-2026-09-29.png)

影响幅度不大但可复核：首秒平均运动差异绝对值约 0.0055–0.0159，主要在提示后短时间出现。1–5 秒部分分支仍有小量影响，5–15 秒本次统计的提示净差异均为 0。保持的是能被再唤起的改变，不是本次已经证明了一段持续 15 秒的独立联想循环。

## 5. 时序读出与结论边界

80 个有提示测试均保留原始时序窗口、完整窗内统计，以及按窗口结束激活强度排序的列表。既有读出器将 **80/80** 判为 `residual_decay`，没有合格收敛窗口。48 个无提示副本没有任务提示窗口；连续世界背景未偷偷改成手动提示来触发窗口。

本轮的因果结论来自相同状态/输入下的动作和节点差异，以及出生和通信干预；不将峰值或积分冒充时序收敛成功。后台输入始终保留，未以停止全部刺激作为自主性门槛。

四个父本来自两种接线及其相关家系，不是四个独立种群；同一父本的多个副本是匹配干预，不是独立样本。这里报告逐父本结果和完全复现，不用大量时间点制造虚假的统计显著性。

本轮没有移植区域，没有共同生态竞争/协作，没有验证长期自主目标或主观体验。它确认了一个更具体、也更扎实的能力：**经历在模型中留下可保留的改变，内部传导会把它重新唤起，并改变身体动作。** 下一步应在同一模型的真实闭环环境中检验这种差异是否影响之后的感知、选择和再学习，并用目标连接与匹配连接干预定位来源；不急于改核、扩规模或赋予“意识分数”。

## 6. 实施与复核

- 新建项目：`2026-09-29 内部活动与行为的因果验证`。双语实验设计、追加登记、实验记录、结果报告和原始证据均通过 Lab 服务落库。
- 共 180 实例：4 暖机、32 同状态表现干预、16 经历训练、96 原状态提示、32 出生验证。原生 CPU 累计实例墙钟 **{minutes:.2f} 分钟**。无 GPU、云、付费 AI。
- 180 份本地完整状态与数据库规范化哈希及解码内容一致；5928 输入载体、5928 实际帧均按计划时刻递送；32 表现分支、128 提示分支的匹配输入一致性已核对。
- 没有修改 Core、感官映射、默认参数，也没有清理旧数据。记录内的 `config` 是实例创建配置，后续显式干预见事件，最终实际配置见完整模型状态。局部耗竭/恢复、易化、遗忘、抑制仍在；外部供应充足，全部实例账本未满足需求为 0。
- 三项工具测试通过。一次测试最初把静默/解除后的事件序号也要求原样，核查确认只有合法操作序号增加 2；修正测试预期，未改动力学。四个假干预的最终模型逐值一致仍通过。
- 新增总预算 2 GiB，已放置 STOP，不再新增模拟。最终空间、共享账户额度和附件读回验证见 [交付记录](delivery.zh.md)。执行前冻结工具与追加阶段工具分别封存；后期分析脚本单独保留，不伪称事前全部固定。
'''
    en=f'''# Internal activity changes behavior: 180 matched causal tests

[中文](report.zh.md) · [Registered design](design.en.md) · [Birth extension](validation.en.md)

**Different co-occurrence histories in the same inherited model produced different unprompted-node responses and motor outputs to identical cues. The differences survived birth, which cleared current activity and short-term states. Blocking communication eliminated both measured birth-history contrasts.** Retained experience can therefore affect behavior through internal transmission in these conditions.

This is stronger than observing an activity image or comparing occupancy alone. Effects were brief and modest, not a demonstrated long-lived autonomous strategy or subjective consciousness. The concrete causal finding remains valuable.

## Interpretation corrections

The prior bilingual reports now have a versioned discussion addendum (database revision 2); original revision 1 and the sealed archive remain. Input-free indefinite persistence is not an autonomy requirement. Standing still and circling receive no separate penalty. Disabling test-time communication while preserving occupancy never established its irrelevance to formation or every aspect of behavior.

## Matched intervention and recovery

Four inherited parents from two wiring families and two selection goals were born, warmed for 20 s, then copied in complete live state. A normal 20 s closed loop provided the identical sensory replay for seven counterfactual branches. All 4 sham copies reproduced exact motor trajectories and final Core states; all 32 branches had identical external stimulus streams.

Compare full communication blockade, excitation-only and inhibition-only blockade, temporary blockade during 5–10 s, and temporary silencing of two complementary hash-defined edge groups. Sensory and motor nodes stayed available and in-flight signals were retained. Groups were defined before outcomes, not identified associative regions.

Circling models showed motor differences around 0.019 early and 0.025 late under full blockade. In the second wiring, full blockade had smaller effects; partial edge blockade could produce larger transient changes. Cancellation between pathways is a hypothesis, not yet isolated. Temporary blockade in wiring 1/goal 0 yielded four successive 5 s mean absolute control differences of {', '.join(f'{v:.6f}' for v in recovery)}: effects appeared during blockade and declined after restoration. Restored communication resumed actual transmission but cannot erase accumulated history or body displacement.

![Intervention](../../../docs/images/internal-activity-intervention-2026-09-29.png)

The counterfactual bodies moved under their own outputs but received the normal copy's replayed input. These are causal action comparisons, not independently closed-loop adaptation scores.

## Different experience under equal exposure

P learned AB/CD; Q learned AD/CB. All channels already existed, keeping receptor identity and body wiring fixed. Each pair repeated 20, then 10, then 10 times: 80 frames 1 s apart, intensity 0.8, 40 exposures/channel. Cross histories with training communication on/off, yielding 16 trained states. After a 1 s wait, fork A/C/no-cue tests with expression communication on/off, yielding 96 copies, cue intensity 0.5 and continuing recorded host background 0.2.

All eight normal-training, normal-expression parent/cue contrasts showed experience-related changes in unprompted activity. In wiring 2/goal 1, cue A produced first-second no-cue-adjusted B/D integrals 0.016531/0 after P versus 0/0.016798 after Q. B and D were not directly prompted. Other Q copies retained mixtures of old B and newly associated D responses rather than cleanly reversing the leading node; all were kept.

Communication was unnecessary during training to form all such contrasts: restoring it during expression still revealed them. Current co-input learning can alter edges without transmitted activation. Some blocked-training contrasts were larger. Formation and expression should be studied separately; competition or interference during transmission is not yet an established explanation, and default communication remains unchanged.

## Retention after birth

After these observations, a disclosed extension included every normally trained P/Q parent. Public birth inherited structure and long-term node history, clearing current activation, inhibition, queued events and short-term operator states. A/no-cue by test communication on/off gave 32 new individuals, not revivals.

{table}

Numbers integrate the first second. Activity contrast is `[(B−D) under P] − [(B−D) under Q]`, with each response adjusted by its matched no-cue copy. Motor contrast is P's adjusted control minus Q's. Motor range is −1 to 1. Integration uses actual sample durations, not sample counts. Signs express direction, not quality.

**All four retained history contrasts survived birth and required test-time communication for these measured effects.** This excludes current residual activation and fixed wiring plus direct input as sufficient explanations of the entire difference. Birth preserves both structure and long-term node history, so it does not isolate one edge or memory variable.

![Retention](../../../docs/images/internal-activity-retention-2026-09-29.png)

![Recall in all four parents](../../../docs/images/internal-activity-recall-2026-09-29.png)

Absolute first-second mean motor contrasts were about 0.0055–0.0159. Some small effects remained during 1–5 s; all measured cue-adjusted history contrasts were zero during 5–15 s. What persisted was the capacity for a later cue-dependent response, not a demonstrated continuously active 15 s internal loop.

## Temporal readouts and scope

All 80 cued copies retained existing temporal windows and end-activation rankings: 80 residual-decay classifications, no qualifying convergence. The 48 no-cue copies had no task-triggered window. Ambient world input was not relabeled to force task windows. Matched behavior/state interventions establish this round's causal finding; peaks and integrals are not called convergence.

Four parents from two related wiring families are not four independent populations, and time points are not independent replications. No region transplantation, shared ecology, long-term autonomous goal or subjective experience was demonstrated. The next question is whether history-driven internal effects alter subsequent sensing, selection and relearning in a genuine closed loop, with pathway-specific and matched controls.

## Delivery and checks

New Lab project: `2026-09-29 内部活动与行为的因果验证`. Bilingual registrations, reports, records and evidence are stored through Lab services. The 180 instances comprise 4 warmups, 32 expression branches, 16 training, 96 original-state probes and 32 birth probes. Native CPU aggregate case wall time: {minutes:.2f} min; no GPU/cloud/paid AI.

All 180 complete local/database states matched canonical hashes and decoded content. All 5928 envelopes/frames were delivered exactly on schedule. Identical-input checks covered 32 expression and 128 probe branches. Core, mapping and defaults were unchanged; no old data were deleted. Result `config` records creation settings; explicit later interventions are in events and the actual final configuration is in the full model. Consumption, recovery, facilitation, forgetting and inhibition remained; unmet energy demand was zero.

Three tool tests passed. An initial test incorrectly expected intervention sequence counters to remain unchanged; inspection found only the legitimate +2 operation count, so the expectation was corrected without changing dynamics. Sham final-state equality still passed.

New storage budget 2 GiB; STOP prevents new simulations. Final storage, shared usage and archive readback are in [delivery](delivery.en.md). Initial execution and extension code are separately frozen; later analysis sources are not misrepresented as initial preregistration.
'''
    for lang,text in [('zh',zh),('en',en)]:
        (HERE/f'report.{lang}.md').write_text(text,encoding='utf-8')

if __name__=='__main__':main()
