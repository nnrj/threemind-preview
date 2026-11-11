"""Report all registered encounters, with measured effects and scope kept separate."""
from experiment import HERE,WORK,ARMS
from lab.tools.ocean_cli import read_json


def build():
    sources=read_json(WORK/'findings.json')['sources']
    if len(sources)!=4 or any(set(s['arms'])!=set(ARMS) for s in sources.values()):
        raise RuntimeError('all registered encounter arms must finish')
    rows=[];grafts=[];events=[]
    for key,s in sources.items():
        c=s['comparisons']
        decreases=[]
        for op in ('target','matched'):
            x=c['uncued intact vs '+op]
            decreases.append(100*(1-x['other_activation_seconds']/x['intact_activation_seconds']))
        rows.append(f"| {key}, body {s['focal']} | {decreases[0]:.2f}% | {decreases[1]:.2f}% | "
            f"{c['intact vs target']['20']['mae']:.6f} | {c['intact vs matched']['20']['mae']:.6f} | "
            + ' / '.join(str(s['arms'][op]['captured']) for op in ('intact','target','matched','random'))+' |')
        base=c['experienced vs blank']['20']['mae']
        graft=c['experienced vs graft']['20']['mae'];matched=c['experienced vs graft-matched']['20']['mae']
        grafts.append(f"| {key}, body {s['focal']} | {base:.6f} | {graft:.6f} | {matched:.6f} | {100*(1-graft/base):.1f}% | "
            + ' / '.join(str(s['arms'][op]['captured']) for op in ('experienced','blank','graft','graft-matched'))+' |')
        for op,a in s['arms'].items():
            for e in a['events']:
                if e['kind']=='body_engulfed' and e['predator']==s['focal']:
                    events.append(f"| {key} | {op} | {e['predator']} → {e['individual']} | {(e['time_us']-s['time_us'])/1e6:.3f} | {e['method']} |")
    table='\n'.join(rows);graft_table='\n'.join(grafts);event_table='\n'.join(events)
    better=sum(s['comparisons']['experienced vs graft']['20']['mae']<min(s['comparisons']['experienced vs blank']['20']['mae'],s['comparisons']['experienced vs graft-matched']['20']['mae']) for s in sources.values())
    minutes=sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('*/result.json'))/60
    zh=f'''# E34：内部活动改变了动作；持久连接也改变了实际捕获结果

[English](report.en.md) · [事前设计](design.zh.md) · [完整实测表](measured-tables.md) · [执行更正](execution-notes.md) · [命令](README.md)

2026-10-04完成。2个完整海洋、4个事前规则选中的遭遇来源，各8个20秒对照；32项分叉全部完成。目录日期是起草日，不是完成日。

## 先说清楚这次发现了什么

**连接不是一份对行为无用的记录。**屏蔽与未直接提示活动有关的连接，四个来源中的相关活动都下降，动作随后改变。把这些连接移植到同受体空白副本后，{better}/4个来源的动作比空白和匹配移植都更接近经历者。这里转移的是可测的动作模式，不能仅凭“更像原个体”就称为生存收益。

**其中一次，连接改变了“是否真的捕获到对方”。**12号的空白副本在分叉后3.08秒捕获57号，匹配连接移植在3.04秒捕获；保留经历和目标连接移植均未接触、更未捕获57号。目标移植让动作差距相对空白缩小约49.4%，同时恢复了经历者的“不发生这次捕获”结果。这个方向是减少捕获，不能改口说成增强捕食，也不推断它具有善恶意图。其他个体、营养和水域始终存在。

**也有明确的未归因结果。**36号原样捕获了9号和40号；随机控制没有捕获。目标通路静默使所选区域无直接提示的活动下降约97.1%，仍捕获这两只，只是时刻改变；匹配静默也仍捕获。由此不能把这两次捕获的必要原因归给这128条连接。它们影响了过程，但该局部通路不是当前条件下完成捕获的必要条件。

所以，本轮已经加强“内部活动与经历能因果地改变完整生态里的行为”的证据；**尚未把E32整组捕获优势充分归因于所选联想通路，更没有证明全部捕获都是主动追猎。**这不撤销已经测到的整体优势和局部因果作用，两者现在还缺一段定量连接。

## 内部活动与动作

目标区域在干预前按最近活动选择，不看之后的捕获结果。每源最多128条入向连接，匹配组使用同数量、权重/稳定度相近的其他连接。静默改变传导，不改身体或移除其他生物。

下面的活动下降只比较分叉后1–10秒、两分支对应通道此前1秒均无直接输入的共同样本；因此不是把所有感官都关闭。动作差距为20秒共同存活期间各动作分量绝对差的平均值。四个来源均保留足够共同存活观察。活动下降与动作差距是不同量，不能把前者很大写成行为差距同样巨大。

| 来源 | 目标静默：活动下降 | 匹配静默：活动下降 | 目标：动作差距 | 匹配：动作差距 | 新捕获：原样/目标/匹配/随机 |
| --- | ---: | ---: | ---: | ---: | --- |
{table}

![实测距离与运动命令](figures/encounters.png)

图中的方向针对事前选中的邻近个体，不是追踪后来“最有利”的对象。48→47、14→6以及36→8均没有接触该指定对象。36号后来捕获的是另外两只，不能把“对8号没有靠近”写成“没有捕获活动”。负方向表示当前动作背离该对象，不自动定义为异常或错误。

## 经历及连接移植

四项出生式对照统一清除即时激活和排队事件，保留相同身体位置、速度、年龄及当前有限储备。经历者继承持久状态，空白副本保留同一受体框架，移植组分别转入目标或匹配持久连接及其规定的相关局部状态。分叉后继续正常学习。它们比较持久经历，不等于活跃状态的直接移植。

| 来源 | 经历者与空白动作差距 | 经历者与目标移植 | 经历者与匹配移植 | 目标移植相对空白缩小 | 新捕获：经历/空白/目标移植/匹配移植 |
| --- | ---: | ---: | ---: | ---: | --- |
{graft_table}

![模式转移和捕获结局分开比较](figures/graft-effects.png)

12号说明：持久经历的影响不只停留在数值上，可以经动作和接触链条改变真实事件。它也提醒我们，不能把“有经历”“更像供体”预设成“吃得更多”。48号和14号未发生指定捕获，但目标移植的动作接近仍是正面可测现象。

## 每次焦点捕获发生在何时

| 来源 | 操作 | 捕获者 → 被捕者 | 分叉后秒 | 方式 |
| --- | --- | --- | ---: | --- |
{event_table}

这些是原始事件记录中的捕获，不由读出器根据运动轨迹猜测。外壳及接触保持条件继续生效；亲子成熟前使用已批准的双向保护。

## 能回答什么，还不能回答什么

本项从E32第60秒开始选样，不覆盖早期全部捕获。E32补充核查表明，g0的捕获优势集中在前60秒；g1前后均有差异。[捕获构成补充](../2026-10-03-ocean-community/capture-composition-addendum.md)因此不能用本轮晚期局部阴性消融，否定早期其他连接、其他个体的作用；同样不能用12号的一次变化声称已经解释全部优势。

各分支保留相同来源的整个世界、随机营养刷新、其他意识、物理反馈和变异。只有注册干预及未来双向亲子规则不同，Core公式不变。两环境种子不是32个独立生态重复。目标区域最大128条，未覆盖的联想通路仍可参与行为。

接下来已批准的E35比较同一整组副本的控制能力和停用内核成本，E36比较两组在同一海洋中的竞争。若再追究捕食优势的神经来源，最有针对性的待办是在早期真实接触前保存完整世界，定位**实际后来捕获的对象**相关过程；选样与评价仍须分开，不删掉未捕获来源。这是下一轮建议，本轮不临时加样追逐阳性。

## 影片、资源与留存

影片包含12号的四种经历/移植对照，以及36号原样/两种静默的实际捕获。每段均为完整海洋加辅助近景，20模拟秒、1倍速；100毫秒真实记录，不补造活动。影片按说明价值挑选，所有来源和阴性结果仍列在上表，不增加样本。

本批合计{minutes:.2f}模拟进程分钟，单worker。完整状态、输入、过程及事件独立保存于`.work/ocean-hunting-20261003`；本机研究项目`315c50a4-0a3a-4b07-b760-0fc053730a39`保存设计、报告和影片。原始大包只留本地。档案收据另列，不反复重算旧证据。
'''
    en=f'''# E34: internal activity changes action; persistent connections change a capture outcome

[中文](report.zh.md) · [Preregistration](design.en.md) · [All measured tables](measured-tables.md) · [Execution corrections](execution-notes.md) · [Commands](README.md)

Completed 2026-10-04: two complete oceans, four prospectively selected encounters, eight 20-second arms each. All 32 forks completed. The directory retains the drafting date.

## Findings

Connections were not behaviorally inert records. Silencing pathways associated with activity lacking recent direct input reduced that activity in all four sources and changed action. Target grafts made actions closer to the experienced donor than both blank and matched grafts in **{better}/4 sources**. Transferring a pattern is distinct from improving survival or capture.

**One persistent-state intervention changed whether a capture actually occurred.** Body 12's blank copy captured body 57 at 3.08 seconds; its matched graft did so at 3.04 seconds. The experienced copy and target graft did not contact or capture body 57. Target grafting reduced action distance from the experienced copy by about 49.4% relative to blank and restored its no-capture outcome. The direction reduces capture; it is not evidence of better hunting or a moral choice. All neighbors, food and water remained present.

**A separate capture advantage was not localized to the selected pathways.** Body 36 captured bodies 9 and 40 when intact, but none under random control. Target silencing reduced selected uncued activity by about 97.1%, yet both captures still happened with changed timing. Matched silencing also retained both captures. These 128 connections affected the process but were not necessary for those captures under these conditions.

This strengthens causal evidence that internal activity and persistent experience affect behavior in a complete habitat. It **does not yet fully attribute E32's population-level capture advantage to the selected association pathways**, nor establish that every capture is active pursuit. Neither the group advantage nor the local causal effects are withdrawn; their quantitative connection remains incomplete.

## Activity and action

Regions were chosen from preceding activity without looking at later capture success. Up to 128 inbound edges per source were silenced; matched controls had the same count and similar weight/stability. Activity reduction uses shared samples during seconds 1–10 whose corresponding channels received no direct input in the preceding second in either branch. Other sensory inputs continue. Action distance is mean absolute component difference over common living periods during 20 seconds. These two scales must not be conflated.

| Source | Target activity reduction | Matched reduction | Target action distance | Matched action distance | Captures: intact/target/matched/random |
| --- | ---: | ---: | ---: | ---: | --- |
{table}

![Measured separation and motor commands](figures/encounters.png)

Direction is relative to the prospectively selected counterpart, not a retrospectively convenient victim. Sources 48→47, 14→6 and 36→8 never contacted that designated body. Body 36 captured two others. Moving away is not classified as abnormal or wrong.

## Persistent experience and grafting

The four birth-style arms uniformly reset immediate activity and queues while preserving physical age, position, velocity and current finite reserves. Experienced copies inherit persistent state; blank copies preserve the receptor framework; grafts transfer the selected persistent connections and their specified associated local state. Learning then continues. These are persistent-state tests, not transfers of live activation.

| Source | Experienced vs blank | vs target graft | vs matched graft | Reduction relative to blank | Captures: experienced/blank/target graft/matched graft |
| --- | ---: | ---: | ---: | ---: | --- |
{graft_table}

![Pattern transfer versus actual captures](figures/graft-effects.png)

Body 12 demonstrates an effect beyond numerical similarity: persistent state can alter a physical encounter and its outcome. Experience or donor resemblance must not automatically be interpreted as better performance. Sources 48 and 14 showed measurable pattern transfer without a designated capture.

## Every focal capture

| Source | Arm | Hunter → victim | Seconds after fork | Method |
| --- | --- | --- | ---: | --- |
{event_table}

These are recorded physical events, not captures inferred by a readout. Shell and contact-duration rules remained operative. Immature parent–child protection was bilateral as approved.

## Scope and next questions

Selection starts after E32's 60-second snapshots. Its [capture-composition addendum](../2026-10-03-ocean-community/capture-composition-addendum.md) shows g0's advantage concentrated earlier, whereas g1 differed in both periods. Late local negative ablations cannot rule out early pathways or other organisms; body 12's changed outcome cannot explain all population benefit either.

Every fork retains the source world, random nutrient replenishment, other brains, physical sensing and mutation. Only registered focal interventions and the explicit future protection rule differ; Core equations are unchanged. Two world seeds do not become 32 independent ecological replicates. Unselected pathways can remain active after a 128-edge intervention.

Approved E35 examines whole copied populations and operating costs; E36 examines shared-ocean competition. A focused future capture-attribution study should save complete worlds before early actual contact and analyze pathways associated with the subsequently captured body, separating discovery from evaluation and retaining failed encounters. This is a recommendation, not a post hoc extension of this batch.

## Media and evidence

Footage includes body 12's four persistent-state arms and body 36's intact/target/matched captures. Each preserves the full habitat with a supplementary inset: 20 simulated seconds at real replay speed, recorded every 100 ms without invented intermediate activity. Illustration selection adds no statistical samples.

Total {minutes:.2f} simulation-process minutes, one worker. Complete states, inputs, trajectories and events remain in `.work/ocean-hunting-20261003`. Local project `315c50a4-0a3a-4b07-b760-0fc053730a39` holds designs, reports and clips; the full raw archive remains local. See the separate delivery receipt.
'''
    for lang,body in (('zh',zh),('en',en)):
        with (HERE/f'report.{lang}.md').open('x',encoding='utf-8') as out:out.write(body)


if __name__=='__main__':build()
