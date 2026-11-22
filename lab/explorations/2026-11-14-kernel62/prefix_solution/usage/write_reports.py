"""Build bilingual reports from the completed, independently audited batch."""
import argparse
import json
from pathlib import Path


def write(work, folder):
    read = lambda p: json.loads(p.read_text(encoding="utf8"))
    a = read(work / "analysis-final.json")
    z = read(folder / "summary.json")
    assert a["passed"] and read(work / "audit-final.json")["passed"]
    groups = {(g["phase"], g["variant"], g["task"]): g for g in z["groups"]}
    def rows(phase):
        return [g for g in z["groups"] if g["phase"] == phase]
    def margins(g):
        return "; ".join(f"{r['block']}/{r['cue']}: {r['margin']:.12g}" for r in g["observations"])
    usage = a["usage_selection"]["chosen"]
    e_table = "\n".join(f"| {g['variant']} | {g['passed_blocks']}/2 | {margins(g)} |" for g in rows("E"))
    f_table = "\n".join(f"| {g['variant']} | {g['passed_blocks']}/2 | {margins(g)} |" for g in rows("F"))
    c_table = "\n".join(f"| {g['name']} | {2 if g['prefix_pass'] else 0}/2 | {2 if g['persistence_pass'] else 0}/2 |" for g in z["shared_profiles"])
    d = groups[("D", "fresh-codes", "prefix")]
    if usage:
        name = usage["name"]
        g = groups[("G", name, "persistent")]
        h = groups[("H", name, "prefix")]
        extra_zh = (f"追加对照中，{name}恢复了两套教材的前缀区分。该条件与其A阶段参照只相差抑制使用记录，"
                    "因此这一对照确认：抑制通过使用记录影响保持，能够决定该配置是否保留正确前缀关系。"
                    f"同配置300秒持续活动为{g['passed_blocks']}/2，另两套新编码复验为{h['passed_blocks']}/2。"
                    "这项结果补充了F阶段的完整恢复方案。")
        extra_en = (f"The {name} condition restored prefix discrimination in both blocks. Its matched phase-A control differs only in inhibitory usage marking. "
                    "This comparison establishes a causal contribution of that marking to the prefix outcome under the specified configuration. "
                    f"The identical full configuration passed persistence in {g['passed_blocks']}/2 blocks and the additional recoding check in {h['passed_blocks']}/2 blocks. "
                    "This supplies a second, more narrowly isolated recovery result alongside phase F.")
        recovery_zh = (f"**已找到在6.2固定函数寻址下恢复前缀区分的具体方案，并完成了直接因果对照。** "
                       "在抑制按有效权重归一分配、不消耗激活连接的突触资源、不参与显式连接学习、抑制连接信号门槛为零的条件下，"
                       "原方案仍为0/2。只增加一项改变——抑制传导不再更新连接的使用时间——两套交换教材即全部恢复正确区分。"
                       f"更换匿名编码和出生种子后的检验为{h['passed_blocks']}/2。节点发送门槛与抑制对节点的竞争作用保留。")
        recovery_en = ("**A concrete solution restores prefix discrimination with 6.2 fixed-function addressing, supported by a direct causal comparison.** "
                       "The reference normalizes inhibition by effective connection weights, bypasses excitatory synaptic resources, disables explicit inhibitory learning, "
                       "and sets the inhibitory connection-signal threshold to zero, yet passes 0/2 blocks. Changing only whether inhibitory transmission writes "
                       "the connection usage time restores both exchanged curricula. "
                       f"The new-code and birth-seed check passes {h['passed_blocks']}/2 blocks. Node sending thresholds and inhibitory competition remain active.")
        recipe_zh = """### 推荐方案

E阶段给出的方案保留当前发送函数的执行顺序，完整设置如下：

- 保留稳定度保持、即时新颖性、资源释放前检查及活动到期修复。
- 激活连接信号门槛为0.004；资源耗竭开启，易化关闭。
- 抑制总量按输出连接的有效权重与距离系数归一分配，抑制连接信号门槛为0。
- 抑制不释放或消耗激活连接的突触资源，显式抑制学习关闭。
- 仅抑制传导不更新连接使用时间；激活传导仍更新该记录。
- 节点发送门槛保留，抑制消退时间常数保留0.2321354823秒。

本次定位了连接使用记录对保持的具体作用：此前虽然关掉显式抑制学习，抑制仍能通过该记录影响衰减和后续强化。E对照将这项作用与节点竞争分开后，恢复了正确的前缀关系。干预对象是这项记录及其两处后续用途，归因按这个实际机制单元表述。该方案已在独立研究实现中完成，正式Python/Rust内核及默认尚未调整。
"""
        recipe_en = """### Recommended configuration

The phase-E solution retains the current emission order. Its full settings are stability-based retention, immediate novelty, a 0.004 excitatory connection-signal threshold, pre-release checking and activity expiry; inhibitory output normalized by outgoing effective weights and distance factors; no inhibitory release or consumption of excitatory synaptic resources; explicit inhibitory learning disabled; inhibitory connection-signal threshold zero; and no inhibitory-only update of connection usage time. Node sending thresholds remain. Depletion is enabled, facilitation disabled, and the inhibition decay constant remains 0.2321354823 seconds.

The causal result concerns a specific connection-usage record. Even with explicit inhibitory learning disabled, inhibition previously influenced decay and later reinforcement through that record. Separating this effect from competition restored the correct prefix relations. The intervention acts on the record and both of its downstream uses; attribution is to that measured mechanism unit. The research implementation is complete. Production Python/Rust and defaults have not been changed.
"""
    else:
        extra_zh = ("两个追加条件均未恢复前缀区分。因此，代码中确实存在抑制传导对保持的隐含作用，"
                    "但只取消这项作用，不能恢复所测两个配置的前缀区分。原预期在本批被否定；"
                    "最终保留F阶段已经通过新编码检验的完整抑制传导方案，不继续追加参数搜索。")
        extra_en = ("Neither added condition restored prefix discrimination. Inhibitory transmission does have the retention effect identified in the source, "
                    "but removing that effect alone did not recover either tested configuration. The added recovery prediction failed. "
                    "Phase F therefore remains the supported solution, including its successful recoding test; no further parameter search was added.")
        recovery_zh = ("**已找到在6.2固定函数寻址下恢复前缀区分的具体方案。** 方案保留稳定度保持、即时新颖性和资源释放前检查，"
                       "将激活连接信号门槛设为0.004；抑制沿有向输出连接传导，把节点发出的抑制总量按各连接的有效权重分配，"
                       "并独立于激活的资源释放及连接学习过程。两套交换教材均恢复正确的AB、DB区分；"
                       f"更换匿名编码和出生种子后，仍为{d['passed_blocks']}/2通过。")
        recovery_en = ("**A concrete configuration restores prefix discrimination with 6.2 fixed-function addressing.** It retains stability-based retention, "
                       "immediate novelty and pre-release resource checking, sets the excitatory connection-signal threshold to 0.004, and distributes a node's "
                       "total inhibitory output over outgoing connections in proportion to their effective weights. Inhibition is handled separately from excitatory "
                       "resource release and connection learning. Both exchanged curricula recover the correct AB and DB responses. Both also pass after anonymous "
                       f"codes and birth seeds are changed ({d['passed_blocks']}/2).")
        recipe_zh = ""
        recipe_en = ""
    cost = f"{z['science_stage_wall_seconds']/60:.2f}"
    host = f"{z['phase_host_wall_seconds']/60:.2f}"
    raw = f"{z['raw_bytes_at_final_audit']/2**20:.2f}"
    peak = f"{z['peak_private_bytes']/2**20:.2f}"
    reserves = "/".join(f"{z['minimum_available_bytes'][k]/2**30:.2f}" for k in ("commit", "ram", "system_disk", "data_disk"))
    e_result = ", ".join(f"{x['variant']} {x['passed_blocks']}/2" for x in rows("E"))
    e_verdict_zh = "归一抑制条件达标；该使用记录的保持作用具有因果贡献" if usage else "未达标；取消该记录没有恢复所测两条件"
    e_verdict_en = "Passed under normalized inhibition; the usage record has a causal contribution" if usage else "Failed; removing marking did not recover either condition"
    more_targets_zh = (f"| 最终E候选的新编码复验 | H为{h['passed_blocks']}/2，达标 | 恢复结果在新的编码与出生种子下复现 |\n"
                       f"| 最终E候选的同配置持续活动 | G为{g['passed_blocks']}/2，未达标 | 该前缀配置没有维持300秒后的任务活动 |") if usage else ""
    more_targets_en = (f"| Recoding of the final E candidate | H: {h['passed_blocks']}/2; passed | Recovery is reproduced with new codes and birth seeds |\n"
                       f"| Same-configuration persistence of the final E candidate | G: {g['passed_blocks']}/2; failed | This prefix configuration does not maintain task activity after 300 seconds |") if usage else ""
    contrast_zh = ("在两套教材中，归一抑制参照保留使用记录时，AB的正确结尾优势约为0.001050893，DB却为−0.001051378；"
                   "取消该记录后，AB与DB分别为0.000974493和0.002693423。网络由偏向同一个结尾，恢复为按前缀选择对应结尾。") if usage else ""
    contrast_en = ("In both blocks, retaining the usage record in the normalized control gives a correct-ending advantage of approximately 0.001050893 for AB but −0.001051378 for DB. "
                   "Removing the record gives 0.000974493 and 0.002693423, respectively. A preference for one ending becomes the appropriate response to each prefix.") if usage else ""
    zh = f"""# R51t11：恢复前缀区分——抑制传导与连接保持的对照实验

2026-11-15。科研记录：`{z['record']}`。本报告为本批首个完成版本；先前报告、原始数据及判据保持原样。

## 结论

{recovery_zh}

这意味着：面对相同的B提示，网络能根据此前是A还是D，产生指向不同已学结尾的响应。改变教学中的结尾对应关系后，正确响应也随之交换。该恢复来自网络规则和经历，不依赖可训练读出器或评分答案。

{extra_zh}

持续活动与前缀区分的联合目标则没有在F候选的四套完整配置中实现：能正确区分前缀的配置未维持300秒后的任务活动；维持了任务活动的配置没有正确区分两种前缀。**本批解决了前缀恢复问题，也明确了当前候选在两项能力上的配置取舍。** 正式6.2及默认值没有修改。

## 目的、材料与判定方法

本批承接作者“找到解决的办法”的要求，主要目标是找到可实施的前缀恢复方案，拆分抑制传播的作用，并在同一完整配置下检验持续活动。原方案和两项事前增补见[初始协议](protocol.zh.md)、[同配置比较补注](shared-config-amendment.zh.md)和[连接使用记录补注](usage-amendment.zh.md)。

实验使用两套交换教材。一套教授A—B—C与D—B—E，另一套交换结尾的对应关系。每个条件从出生开始连续教学212.2内部秒。教学结束后，保存完整父体，另立AB、DB两个明确登记的诊断副本；先给前缀，再于1秒后给相同B提示，观察15秒的激活、抑制、直接和联想活动，每10毫秒记录一次，并保存刺激前后同刻记录，共1502点。本批使用Python参考实现的独立研究派生版本，各派生版本保存自己的身份和完整定义。

评分沿用历史标准：B到达后，正确结尾节点的激活峰值减去另一结尾节点的激活峰值，须大于10⁻⁶；AB、DB均满足才算该教材通过。两套教材全部通过才称为前缀恢复。本批是两个交换教材区组的机制实验，条件、副本和记录点不另算独立样本。新编码检验更换匿名编码及出生种子，沿用同一教学关系，检验编码替换后的结果。

持续活动使用另一套既有材料：连续教学81.2秒，随后保留300帧固定背景刺激、等待300内部秒，再观察15秒。每个记录点至少有一个任务节点激活大于10⁻⁶，且两套教材均满足，才通过。另报告激活达到0.95的记录比例。这里测量实际节点活动，不以`active`标签计分。两种任务分别出生，但比较时使用完全相同的内核配置。

## 前缀恢复方案及对照

A阶段比较抑制总量分配、是否使用突触资源、是否参与连接学习及是否设置抑制连接门槛四个因素，共16种组合。所有组合均为0/2。参照已经启用稳定度保持、即时新颖性及0.004激活连接门槛，因此它代表“采用当前发送路径的参照”，不是所有参数均为生产默认的个体。

F阶段按事前分支检验完整的独立抑制路径，并分别采用相邻连接或有向输出连接、基础权重或有效权重。四种组合均通过：

| 连接与权重选择 | 通过教材 | 各教材/提示的正确结尾峰值优势 |
| --- | --- | --- |
{f_table}

有向输出连接＋有效权重保留了当前的连接方向和权重使用方式，按事前规则成为选中方案。其AB优势约0.000976199，DB优势约0.002737817；两套教材均通过。新编码检验的优势相同，全部超过10⁻⁶门槛。因此，恢复前缀不要求回到相邻连接路由，也不要求改回基础权重读取。

F阶段选中方案的具体发送过程如下：

1. 激活仍按6.2的节点规则、资源释放前检查、突触资源及学习规则处理。激活连接信号门槛为0.004。
2. 激活发送处理结束后，计算节点当前可发出的抑制总量，沿用节点抑制发送量门槛0.002。
3. 将这份总量按有向输出连接有效权重所占比例分配给目标节点。公式为`目标所得抑制量 = 节点抑制发送总量 × 该连接有效权重 / 可用输出连接有效权重之和`。
4. 这一路抑制保留对目标节点的竞争作用；它不使用激活连接的突触资源，不直接强化连接，也不更新连接的使用时间。激活处理与抑制分配的顺序是该方案的一部分。

这是一个经过验证的组合方案。四因素比较已经表明，不能把其成功简单归于“减少抑制”或“关闭抑制学习”某一个开关。完整配置、独立研究身份和源码均已冻结，见原件中的`phase-F-selection.json`、`phase-D-selection.json`及对应源码副本。

## 抑制传导对连接保持的隐含作用

本批源码核查发现：当前发送路径即使关闭`inhibitory_learning_enabled`，只有抑制成功传导时仍会更新`last_pass_us`。在稳定度保持模式下，这个字段会让连接跳过同一时刻的权重衰减，也会参与下一次共同刺激强化系数的选择。因此，该字段具有实际动力学作用。

这项发现先登记为新假设，再开展E阶段。E使用两个A阶段条件作完整参照，只取消“仅抑制传导更新使用记录”，保留激活对该记录的更新。`current-path`保留当前分配与资源方式；`normalized-path`已将抑制归一分配、绕过突触资源、关闭显式抑制学习及抑制连接门槛。结果如下：

| 条件 | 通过教材 | 各教材/提示的正确结尾峰值优势 |
| --- | --- | --- |
{e_table}

{contrast_zh}

{extra_zh}

{recipe_zh}

## 同一配置下的持续活动与前缀判断

原前缀材料启用资源耗竭、关闭易化；原持续活动材料关闭耗竭、采用1秒易化时间常数。本批在执行C阶段前补齐交叉比较，避免将不同配置的两项成功合并。101表示耗竭开启、易化关闭；011表示耗竭关闭、易化时间常数1秒；两者均开启连接巩固。原抑制消退时间常数为0.2321354823秒，四分之一为0.05803387058秒。

| 完整配置 | 前缀区分 | 300秒后任务活动 |
| --- | --- | --- |
{c_table}

011原时间常数下，观察窗内逐点最大任务激活为0.0171540—0.0230551；四分之一时间常数下为0.0554378—0.0745087。两者均无达到0.95的记录。101两种时间常数下，300秒后任务节点激活均为零。

结论是：所测范围内，持续活动可以增强而前缀区分仍失败；前缀区分也可以恢复而不形成300秒任务活动。持续时长不能代替关系判断成绩。这个结果支持分别检验活动维持与信息区分，并把两者的兼顾列为明确的配置选择问题。

## 目标结项与对ThreeMind的意义

| 目标 | 结果与判定 | 科学结论 |
| --- | --- | --- |
| 找到可实施的前缀恢复方案 | F四配置各2/2，达标 | 在6.2固定函数寻址下，正确前缀关系可以恢复 |
| 在更换匿名编码后复验 | D为{d['passed_blocks']}/2，达标 | 选中方案的结果不依赖原来的匿名编码 |
| 四因素拆分直接给出恢复条件 | A的16组合全0/2，未达标 | 原四因素组合没有涵盖成功路径的全部必要差异 |
| 同一F候选配置兼具前缀与300秒活动 | 四套完整配置无联合通过，未达标 | 当前配置存在明确取舍，不据单项成绩更改全局默认 |
| 只取消抑制使用记录恢复所测路径 | {e_result} | {e_verdict_zh} |
{more_targets_zh}

对ThreeMind而言，前缀恢复是有利结果：它给出了规则层面的可行修复，而不是通过换答案、重新训练外设或退回旧刺激寻址得到成绩。A与E的失败同样约束了原因解释，防止把已有开关误当作完整机制。两套任务的交叉结果则反对仅以活动持续更久来选默认参数。

建议把已经验证的抑制传导方案整理为6.2的独立可选机制，保留现有模式及旧存档身份；默认取舍根据前缀与持续活动的实际用途决定。本批没有把这一建议自动实施为正式内核变更。此前全面复验和论文修订仍暂停。

## 原件、完整性与成本

共完成{z['stages']}个教学、等待或诊断阶段，独立核验{z['verified_states']}份完整状态和{z['verified_processes']}段过程。评分复算最大差为{z['max_arithmetic_error']}。观察、保存恢复、分段推进与宿主暂停的装置检查均保持完整状态一致。原168阶段分析和核验保留，追加结果另存`analysis-final.json`、`audit-final.json`。

科学阶段累计墙钟{cost}分钟，含阶段管理的宿主累计{host}分钟；最大私有内存{peak}MiB。最终核验时目录文件总量{raw}MiB，归档和读回另计；这里是文件字节统计，不是NTFS实际分配或因果性能基准。提交内存/RAM/C盘/E盘的最低观测余量依次为{reserves}GiB，保留门槛仍为5/4/5/25GiB。未触发资源停止，没有新增不完整阶段。

独立抑制研究路径没有累计通用的抑制传导计数；本报告依据保存的节点抑制过程与干预结果判断其作用，不把该计数零解释为没有抑制，也不据它比较抑制传导总量。

原件目录：`{work.as_posix()}`。科研API登记、完整归档读回和待同步为零的完成状态以[交付回执](delivery.json)为准。所有正式内核源码、默认值、历史原件和论文保持不变。
"""
    en = f"""# R51t11: Restoring prefix discrimination by separating inhibition transmission and connection retention

15 November 2026. Research record: `{z['record']}`. This is the first completed report for this batch. Earlier reports, originals and criteria are preserved.

## Conclusion

{recovery_en}

The same B cue therefore elicits different learned endings according to whether A or D preceded it. Exchanging the taught endings exchanges the correct responses. This recovery uses network dynamics and experience, without a trainable readout or access to scoring answers.

{extra_en}

None of the four complete configurations tested with the phase-F candidate jointly passed prefix discrimination and task activity after 300 seconds. The configuration that recovered prefixes failed persistence; those that maintained task activity failed prefix discrimination. **The batch resolves prefix recovery and identifies the candidate's present configuration trade-off.** Production 6.2 and its defaults were not changed.

## Purpose, material and criteria

The author requested a solution. The registered targets were an implementable recovery, a decomposition of inhibitory propagation, and a persistence check under identical full configurations. See the [initial protocol](protocol.en.md), [shared-configuration amendment](shared-config-amendment.en.md) and [usage-record amendment](usage-amendment.en.md).

Two curriculum blocks teach A–B–C and D–B–E, with the ending assignments exchanged in the second block. Each condition develops continuously for 212.2 internal seconds. Its complete teaching state is retained; separately registered diagnostic copies receive AB or DB, with B one second after the prefix. Activation, inhibition, direct and associative activity are recorded over 15 seconds at 10-ms intervals, including same-time pre/post-stimulus observations: 1,502 points in total. Execution uses isolated derivatives of the Python reference implementation, each with its own saved identity and complete definition.

The historical criterion is unchanged: after B, peak activation of the correct ending minus that of the alternative must exceed 10⁻⁶. Both AB and DB must pass within each block, and both blocks must pass for recovery. The units are two exchanged curriculum blocks. Conditions, copies and observation points are not additional independent samples. The recoding test changes anonymous codes and birth seeds while retaining the taught relations.

Persistence uses existing material: 81.2 seconds of teaching, a 300-second wait containing 300 fixed background frames, and a 15-second observation window. At every observation, at least one task node must have activation above 10⁻⁶; both blocks must pass. Records at or above 0.95 are also counted. Actual node activity, not the life label, determines the outcome. Prefix and persistence subjects are born separately, with identical full configurations in each matched comparison.

## Recovery and controls

Phase A crossed four binary factors: inhibitory allocation, use of synaptic resources, inhibitory learning, and the inhibitory connection threshold. All sixteen combinations passed 0/2 blocks. This reference already used stability-based retention, immediate novelty and the 0.004 excitatory threshold. It represents the current sending pathway under those settings, not an individual with every production default.

The preregistered fallback compared incident versus outgoing connections and base versus effective weights within a separate inhibitory pathway. All four conditions passed:

| Routing and weight | Blocks passed | Block/cue: correct-ending peak advantage |
| --- | --- | --- |
{f_table}

Outgoing connections with effective weights were selected by the registered preference, preserving the current direction and weight representation. AB and DB advantages were approximately 0.000976199 and 0.002737817. The recoding test produced the same advantages, above the 10⁻⁶ criterion. Recovery therefore does not require incident-edge routing or a return to base-weight readout.

The selected phase-F procedure is explicit:

1. Process excitation using 6.2 node rules, pre-release checking, synaptic resources and learning; use an excitatory connection-signal threshold of 0.004.
2. After excitatory processing, calculate the node's inhibitory output budget and retain the node-level inhibitory output threshold of 0.002.
3. Allocate that budget proportionately over available outgoing effective weights: `inhibition delivered to a target = node inhibitory output × connection effective weight / total available outgoing effective weight`.
4. Inhibition continues to affect competing target nodes. It does not use excitatory synaptic resources, directly reinforce connections or update their usage time. The ordering of excitatory processing and inhibitory allocation is part of the tested procedure.

This is a validated combination. Phase A shows that its success cannot simply be assigned to a single switch such as less inhibition or disabled inhibitory learning. Complete configurations, distinct research identities and source copies are frozen in the phase-F and phase-D selection artifacts.

## Inhibitory usage records and retention

Source inspection found that the current sending pathway updates `last_pass_us` after inhibitory-only transmission even with `inhibitory_learning_enabled=False`. Under stability-based retention, this can exempt the connection from weight decay at the same time and affects the coefficient used for a later co-stimulation update. It is a dynamics-relevant field.

This observation became a prospectively registered phase-E hypothesis. Two completed A conditions serve as intact controls. E changes only whether inhibitory-only transmission writes the usage record; excitation continues to write it. The current-path condition keeps existing allocation and resources. The normalized-path condition already normalizes inhibition, bypasses its synaptic resources, and disables explicit inhibitory learning and its connection threshold.

| Condition | Blocks passed | Block/cue: correct-ending peak advantage |
| --- | --- | --- |
{e_table}

{contrast_en}

{extra_en}

{recipe_en}

## Prefix discrimination and persistence under the same configuration

Historical prefix material enabled depletion and disabled facilitation; historical persistence material disabled depletion and used a one-second facilitation time constant. A prospective amendment crossed both resource settings with both inhibition time constants in both tasks. Code 101 denotes depletion on and facilitation off; 011 denotes depletion off and a one-second facilitation time constant. Connection consolidation is enabled in both. The original inhibition decay constant is 0.2321354823 seconds; its quarter value is 0.05803387058 seconds.

| Complete configuration | Prefix discrimination | Task activity after 300 seconds |
| --- | --- | --- |
{c_table}

With resource setting 011, pointwise maximum task activation was 0.0171540–0.0230551 at the original time constant and 0.0554378–0.0745087 at the quarter value. Neither reached 0.95. With setting 101, task activation after 300 seconds was zero at both time constants.

Within these comparisons, stronger persistence coexists with failed prefix discrimination, and successful prefix discrimination coexists with failed 300-second persistence. Activity duration is therefore not a substitute for relational performance. The results support measuring activity maintenance and discrimination separately when choosing a configuration.

## Target closure and implications

| Target | Result and judgment | Scientific conclusion |
| --- | --- | --- |
| Implementable prefix recovery | Four F conditions each 2/2; passed | Correct prefix relations can be recovered with 6.2 fixed-function addressing |
| Check changed anonymous codes | D: {d['passed_blocks']}/2; passed | Recovery is preserved under the tested recoding |
| Recover through the original four-factor decomposition | Sixteen A conditions all 0/2; failed | Those factors did not capture all consequential differences in the successful pathway |
| Joint prefix and 300-second persistence with the F candidate | No joint pass among four complete configurations; failed | The measured trade-off argues against selecting a global default from one task alone |
| Recover by removing inhibitory usage marking alone | {e_result} | {e_verdict_en} |
{more_targets_en}

Prefix recovery is a favorable result for ThreeMind: it supplies a rule-level solution without changing answers, fitting a peripheral or reverting stimulus addressing. The negative controls constrain its explanation and prevent an existing switch from being mistaken for a complete mechanism. The crossed-task results argue against choosing defaults solely for longer activity.

The supported inhibitory pathway is a candidate optional 6.2 mechanism, with the current pathway and historical saved identities retained. Default selection should reflect the actual prefix and persistence requirements. This recommendation has not been applied to production. Comprehensive replication and manuscript revision remain paused.

## Evidence, integrity and cost

The batch completed {z['stages']} teaching, waiting or diagnostic stages. Independent verification covered {z['verified_states']} complete states and {z['verified_processes']} processes; maximum scoring discrepancy was {z['max_arithmetic_error']}. Apparatus checks preserved identical full states under observation, save/restore, partitioned advancement and host pauses. The original 168-stage analysis and audit remain intact; additions appear in `analysis-final.json` and `audit-final.json`.

Scientific stages took {cost} wall-clock minutes; phase hosts including management took {host} minutes. Peak private memory was {peak} MiB. Files occupied {raw} MiB at final audit, before archive and readback copies. This is a file-byte total, not NTFS allocation or a controlled performance benchmark. Minimum observed commit/RAM/C/E availability was {reserves} GiB; reserve thresholds remained 5/4/5/25 GiB. No resource stop or new incomplete stage occurred.

The separate inhibitory research pathway does not increment the general inhibitory-transmission counter. Conclusions use saved node inhibition processes and controlled outcomes. A zero value of that counter is not interpreted as absent inhibition or used to compare total inhibitory transmission.

Originals: `{work.as_posix()}`. The [delivery receipt](delivery.json) records completion of scientific-API registration, full archive readback and pending=0. Production kernel sources, defaults, historical originals and manuscripts are unchanged.
"""
    (folder / "report.zh.md").write_text(zh, encoding="utf8")
    (folder / "report.en.md").write_text(en, encoding="utf8")
    print("Bilingual reports written from final audited results.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--tools", type=Path, required=True)
    args = p.parse_args()
    write(args.work, args.tools)
