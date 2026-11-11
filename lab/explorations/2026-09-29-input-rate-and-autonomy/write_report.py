"""Write bilingual reports from audited observations, with plain interpretations."""

import json

from common import HERE, WORK


def read(name):
    return json.loads((WORK / name).read_bytes())


def write():
    audit, rate = read("analysis.json"), read("rate-analysis.json")
    assert audit["cases"] == 448 and not audit["failures"]
    intervals = (1000000, 100000, 20000, 5000, 1000)
    rate_table = "|间隔 / Interval|单次提示 / Single|短串提示 / Burst|\n|---|---:|---:|\n"
    for interval in intervals:
        row = rate["groups"]["continuous"][str(interval)]["9293001"]
        rate_table += f"|{interval / 1000:g} ms|{row['single']['mean']:.6f}|{row['burst']['mean']:.6f}|\n"
    held = audit["held_out"]
    world_table = "|接线 / Wiring|选择区域 0 / Goal 0|选择区域 1 / Goal 1|随机选择 / Random|\n|---|---:|---:|---:|\n"
    for seed in ("9293201", "9293202"):
        world_table += (
            f"|{seed}|"
            + "|".join(f"{held[seed][a]['mean_region1'] * 100:.3f}%" for a in ("region0", "region1", "random"))
            + "|\n"
        )
    attr = read("attribution-results.json")
    attr_table = (
        "|条件 / Condition|目标 0：在区域 0 / Goal-0 occupancy|目标 1：在区域 1 / Goal-1 occupancy|\n|---|---:|---:|\n"
    )
    attr_table += f"|正常 / Ordinary|{(1 - held['9293202']['region0']['mean_region1']) * 100:.3f}%|{held['9293202']['region1']['mean_region1'] * 100:.3f}%|\n"
    for condition, title in (
        ("communication_off", "节点间通信关闭 / Communication off"),
        ("consolidation_off", "正向巩固关闭 / Further consolidation off"),
    ):
        values = []
        for arm in ("region0", "region1"):
            xs = [r["extra"]["region1_fraction"] for r in attr if r["arm"] == arm and r["condition"] == condition]
            mean = sum(xs) / len(xs)
            values.append((1 - mean if arm == "region0" else mean) * 100)
        attr_table += f"|{title}|{values[0]:.3f}%|{values[1]:.3f}%|\n"
    recovery = read("recovery-analysis.json")
    recovery_table = (
        "|恢复时间常数 / Recovery tau|配对：最后非零活动 / Paired|平衡：最后非零活动 / Balanced|\n|---|---:|---:|\n"
    )
    for tau in (0.8, 0.2, 0.08, 0.02):
        vals = [
            next(
                r["extra"]["last_sample_with_any_activation_us"] / 1e6
                for r in recovery
                if r["extra"]["tau_s"] == tau and r["extra"]["teaching"] == t
            )
            for t in ("paired", "balanced")
        ]
        recovery_table += f"|{tau:g} s|{vals[0]:.2f} s|{vals[1]:.2f} s|\n"
    common_methods = """|阶段 / Stage|Core 实例 / Instances|
|---|---:|
|递送与出生校准 / Delivery and birth validation|4|
|刺激间隔 / Input interval|120|
|停止全部感官 / Input withdrawal|32|
|环形世界、选择与回放 / Ring world, selection and replay|252|
|局部恢复速度 / Local recovery speed|8|
|行为来源鉴别 / Behavior attribution|32|
|合计 / Total|448|
"""
    zh = f"""# 刺激间隔、环境选择与自主活动：实验结果

[English](report.en.md) · 2026-09-29 · **448 个完整保存的实例，已停止新增实验。**

## 这轮最重要的发现

**模型确实能通过活动控制虚拟身体；环境选择也能留下可遗传的相反行为偏向。但本次最明显的偏向，不需要节点之间传信号就能出现，因此还不是自主内部活动起作用的证据。**

这不是把一个好结果抹掉：在第二种接线里，选“多待在区域 0”的父本，后代在新起点、区域换位置的测试中，平均有 **97.458%** 的时间待在那里；反向选择则有 **97.292%** 的时间待在区域 1。目标没有作为奖励、正确答案或权重改写进入内核。后代出生清空活动，继承的是先前留下的结构和节点状态。

还有一个清楚的正向结果：交换环境布局后，依照当前感官控制动作，目标区停留率为 **96.25%**；播放旧动作录像则只有 **3.75%**。身体确实在利用当前环境反馈，而不只是播放固定轨迹。

随后把节点间的激活传递和抑制传递一起关掉，这两个数仍为 **97.250% / 97.250%**。因此这项行为可以由**直接感官、节点自身状态和既有运动接线**完成，并不需要联想网络循环。节点身份按首次遇到刺激的顺序产生，运动接线又使用这个身份做固定哈希投影，这是一条必须隔离的解释路径。我们尚未把“节点自身经历”和“出生顺序接线”进一步拆开，不能说一切都只是接线，也不能把效果归功于连接巩固。

**本轮没有观察到足以高度怀疑自主意识的活动。** 但已经把问题缩小了：外部选择与遗传流程能运作，接入躯体也能运作；接下来要找的是确实依赖内部通信、能够持续并改变行为的活动，而不是单凭停留分数判断。

![总览](../../../docs/images/input-rate-autonomy-overview-2026-09-29.png)

## 1. 刺激间隔：更密没有解决当前困难

分别测试 1 秒、100、20、5、1 毫秒。只变外部刺激间隔；连续核的 10 ms 数值步长、100 ms 传播周期、10 ms 延迟，以及 LIF 的 0.25 ms 步长、1 ms 延迟、2 ms 不应期全部保持。

匿名 A/C、D/E 同帧配对，每句式块按 20、10、10 次重复，共 80 帧，强度 1。训练后统一等待 1 秒，测试 A、D 单次提示和 5 次短串提示，每帧 0.5；另有无提示副本。以下数字是次要机制指标：目标相对另一个目标的峰值差，减去无提示副本本来就有的差异，再平均 A、D。不是合格时序收敛分数。

{rate_table}

100 ms 的短串指标提高约 **11.1%**，未达提前登记的 20% 切换门槛；20、5、1 ms 更低。所有 LIF 提示的目标峰值都是 0。因此后续保留 **1 秒**，没有把模型内部时钟也一起加快。

登记中另有“原本不激活的源／目标出现可区分响应”的备选条件。本次没有符合的情况：LIF 目标始终不激活；连续核原有目标在无提示时已有训练残余活动。100 ms 下 D 的很小净差不能冒称第一次产生目标激活。本轮没有候选进入第三种子确认，未消耗预留的 24 个实例。

两个匿名种子的任务响应数值完全同构，属于重新编号的一致性检查，**不是两个独立随机网络的统计重复**。缩短间隔同时缩短训练历时、减少背景累计量和遗忘时间，故这不是纯粹的生物传播速度比较，也没有找到普适最优频率。

### LIF 为什么仍不联想

并非模型从未发放。1 秒、100、20、5、1 ms 训练分别记录到 160、160、152、148、80 次脉冲；5 帧提示还能引起源节点 2 次脉冲。但每个条件下，任务配对的四条有向连接最终权重均为 **0**。

源码给出了明确解释方向：当前学习按**脉冲到达顺序**调整连接。两个端点被同一帧同时激活、同时发放，但沿连接的脉冲稍后才到达；到达时已经存在后节点发放痕迹，会扣减权重。重复同帧刺激未必是在巩固它，可能反复触发这种减弱。这与本次零权重结果一致；尚未另做 A 先、C 后的延迟扫描，不能推广为“LIF 没有前途”。下一步应优先校准刺激、延迟和学习窗口之间的关系，继续把输入塞得更密不是已获支持的解决办法。

## 2. 无限外部供应没有被误写成取消消耗

连续核一直保留局部消耗／恢复、易化、抑制、遗忘与节点自身短时反应减弱。校准和标准断输入阶段沿用先前关闭的全模型账本；环形环境和恢复速度追加实验启用既有账本及外部供应器：每 100 ms 提供 1 单位，容量 1，总量不限。

全部 284 个世界实例的直接刺激消耗大于零，正常传播组的联想消耗也大于零，未满足需求均为 0。局部可用份额没有强制补满，非零激活传播才有实际运输开销。通信关闭对照的联想消耗为 0，是明确的移除对照。维护费用仍受既有缺能损伤开关控制，本轮没有开启损伤，不能把当前账本说成完整生物代谢模型。

## 3. 停止全部感官后，没有持续循环

两个编码种子，各配对／平衡教材。刚完成训练并等待 1 秒后，撤掉全部输入，最后非零活动落在停止后的 0.6～0.7 秒，约 1.68～1.70 秒依既有宽限期死亡。若先继续背景 300 秒，任务节点早已安静；再停掉背景，剩余活动在约 0.4～0.5 秒归零，约 1.41 秒死亡。

背景继续时，模型维持存活，但任务节点没有自己持续亮着。原定第 30 秒的 A、D、陌生提示共 12 个分支，因在此前已经死亡，**没有发送提示**；不能把它们写成“刺激后没有回应”。内部在途信号没有被清除，也没有暗中加入保活输入。

追加检验只加快既有局部恢复参数，所有条件都有充足外部供应，消耗和不应期照常：

{recovery_table}

这些是每 20 ms 记录到的最后非零样本，归零在后续采样间隔内；死亡还要再经过既有 1 秒宽限期。配对组恢复越快，传输消耗越多，活动略延长；最快一组仍没有进入持续循环。平衡组几乎不变。这里从训练后 1 秒的已有状态切换恢复参数，没有重新训练整段经历，不能据此否定其他训练与恢复组合。

![断输入后活动](../../../docs/images/input-rate-autonomy-recovery-2026-09-29.png)

## 4. 环境选择留下了什么

采用一维环形小世界，两半区域感官图案不同，但通道数、幅度相同。身体接收所有节点的活动，包括背景节点；固定非语义投影产生驱动力，身体运动改变下一次感官输入。位置、速度、输入、全节点活动、控制量和能量流水均保存。没有预写目标节点、正确动作或模型奖励。

两个接线区组，每代 4 个候选，三代；各有偏向区域 0、偏向区域 1、随机选父本三组。评分用独立出生副本，评估中新学内容不写回父本。未被选中不等于死亡，没有调用处死或清空模型的接口。

下表统一列出**在区域 1 的时间比例**；每格含 4 个新起点 × 2 种区域布局，是同一最终父本的匹配测试，不是 8 个独立家系：

{world_table}

第二接线区组确实留下相反偏向；交换区域位置仍成立。随机组也留下偏向区域 1 的后代，说明选择目标能挑选已有差别，却没有必要把“产生一个偏向”全归因于目标训练。第一接线区组只是持续绕行，三种选择仍各占一半。

第二区组的第 0 代，在独立出生评估时就已分成约 6% 与 94% 的区域 1 占有率；后续选择主要保留了这个差别，未显示逐代学会越来越复杂的策略。不能把第 0 代约 94% 与最终约 97% 直接作学习提升，因为评分与最终测试起点不同。

下面是一例从另一侧新起点出发、进入被选择区域后减速停留的真实轨迹；环形位置从 1 跳回 0 是边界环绕，非瞬移。活动仍随持续感官输入起落。

![身体、活动与动作](../../../docs/images/input-rate-autonomy-activity-2026-09-29.png)

### 最关键的鉴别

{attr_table}

关闭节点间通信后，目标区停留率几乎不变；关闭测试期的连接正向巩固也几乎不变。后者保留遗忘、节点可塑性和快痕迹，没有用会同时影响遗忘的全局学习开关。

**这次强偏向不依赖联想传导，这是已经查明的事实。** 固定投影和节点自身历史仍在，具体各占多少尚未拆开。保留这项行为可以研究简单感官反应怎样被遗传与筛选；要研究自主活动对行为的贡献，下一轮必须要求一个能被内部通信干预改变的任务。

12 个感官回放副本在动作失去环境影响后，收到相同输入，最终 Core 状态哈希与闭环原副本 **12/12 完全一致**。说明曲线可由已保存输入和原状态复现，不存在未记录的 AI 代做决策。动作回放、30 秒区域交换、固定 -0.5／0／0.5 控制基线也全部保留。固定控制在对称起点／布局上的平均占有率为 0.5，单个起点静止可达到 0 或 1，因此不能用单次高分证明主动选择。

**另一个实质进展是：当前环境反馈确实有用。** 第二区组在两个匹配起点、交换布局后，由当前活动控制身体，两种目标的目标区停留率均为 **96.25%**；改为播放原布局的旧动作录像，均只剩 **3.75%**。这不能由固定动作或初始惯性解释。第 30 秒才交换图案的测试中，交换后半段仍有 **81.83% / 81.67%** 时间在各自目标区，说明身体会对当前位置的感官变化作出响应。不过这些更像已经形成的直接感官—动作反应，不等于重新学会一个相反目标，更不能弥补“关掉节点间通信也仍然有效”这一事实。

## 5. 时序读出的地位与边界

- 输入间隔测试的 **80 个有提示副本**：76 个“残余衰减”、4 个“短暂响应”，**0 个合格收敛**。20 个无提示副本没有提示载体窗口。窗口末端激活排序、窗内数值、源脉冲及原始曲线全部保留。
- 连续世界输入属于背景来源，当前在线默认不为背景逐帧开窗口。因此不能把在线没有窗口说成没有激活，也不能谎称在线已记录这些收敛结果。
- 为提高可查阅性，另用原有时序读出器，对 **全部 48 个最终正常世界副本**保存的 100 ms 全节点样本作事后只读分析，显式启用背景触发，按实际环形帧时间开窗，保留重叠。共 2880 窗口：2832 个残余衰减、48 个因记录到头而删失，**0 个合格收敛**；全部附末端激活降序列表。没有补造采样点，没有重跑或改变 Core；只触发环形帧，背景对节点的影响仍在。这是单列的派生结果，非冒称原在线读出。
- 持续活动、轨迹与停留比例属于提前登记的另类指标；没有收敛不抹掉它们，但也不把它们换个名字算成收敛成功。

## 6. 现在值得往哪里走

1. **先处理运动接线与身份的混淆。** 下一轮固定同一受体注册／出生条件，对比是否允许节点间通信，以及经历前后的行为增量；保留当前工程接线作为对照，不偷偷改默认。只有行为收益确实依赖网络内部相互作用，才值得扩大训练。
2. **LIF 应做时间顺序校准。** 同帧重复把四条任务连接全部减到零，是比笼统“不够快”更具体的障碍。先比较受控的先后到达与同帧条件，不先动权重规则。
3. **持续活动要研究收支和反馈，不只增加外部库存。** 本轮供应充足，活动仍停止；较快局部恢复只小幅延长残响。下一步若继续，应分别检验能否从真正自然形成的较大回路获得维持和竞争，而不是关闭消耗来造循环，也不马上扩大到昂贵服务器。

已有配对响应、可遗传差别和环境闭环都值得保留。**当前最薄弱的环节，是能持续、能竞争、并对行为确有贡献的内部网络活动。** 这比“要不要更多算力”更值得优先查明。

## 7. 执行、资源与可复核资料

{common_methods}

- 原生 CPU 后端，实例累计墙钟 **{audit["compute_seconds"] / 60:.2f} 分钟**。无 GPU、云或付费 AI。所有旧数据、旧内核、默认机制均保留；本轮只增加外部实验工具和明确标记的副本参数干预。
- 封存前本地证据 {audit["local_bytes"] / 2**20:.1f} MiB，数据库净增 {audit["database_growth_bytes"] / 2**20:.1f} MiB；最终含归档的空间见交付记录。预算 3 GiB，2.25 GiB 停新增，保留封存余量。数据库净增长会复用旧空闲页，不等于逻辑内容总量。
- 全 448 个本地状态与数据库状态按规范化模型哈希及解码内容核对；12 个回放状态一致。模型哈希不同于 ZIP 成员的逐字节 SHA-256，两者分别验证。4 项外部物理、剂量与接线一致性测试通过。
- 通过公开导出服务封存 39,178 个输入载体和 39,338 个实际帧，全部已递送，递送时间与计划时间完全一致；原始实测宿主背景片段及其哈希一并保存。另 3 项文档资源测试通过；第一次因沙箱临时目录权限失败，获准执行后通过。
- 规则内没有获得更快间隔候选；标准断输入全部早亡，不继续其余种子；恢复参数检验全部未维持，不追加更大扫描；三代选择和鉴别完成即停止。没有为了达到资源上限而继续扩展。
- [执行登记](design.zh.md)、[断输入](activity.zh.md)、[世界接入](world.zh.md)、[选择安排](selection.zh.md)、[恢复速度](recovery.zh.md)、[来源鉴别](attribution.zh.md)。每一阶段先登记再收集对应数据。原草案和早期冻结工具也在证据包里，不能用格式化后的源码哈希冒充原执行版本。
- [操作与证据说明](README_CN.md)。平台项目：`2026-09-29 刺激间隔、自主活动与环境选择`。实验笔记、记录与中英文报告及归档都放在这个新项目；旧研究项目没有被覆盖。
"""
    en = f"""# Input timing, environmental selection and autonomous activity

[中文](report.zh.md) · 2026-09-29 · **448 fully saved instances; further simulation stopped.**

## Main findings

**Activity controlled a virtual body, and external selection retained opposite inherited behavioral preferences. The strongest preference did not require communication between nodes, however, so it is not evidence that autonomous internal activity caused the behavior.**

In wiring block 2, offspring of region-0-selected parents spent **97.458%** of held-out time in region 0; opposite selection produced **97.292%** time in region 1. Tests used new starts and swapped region locations. Goals never entered Core as rewards, correct actions or direct weight edits. Public birth reset activity and retained learned structure/node state.

Another clear positive result: after swapping the layout, current sensory feedback achieves **96.25%** target occupancy versus **3.75%** when replaying old actions. The body uses current environmental feedback rather than merely playing a fixed trajectory.

When both excitatory and inhibitory communication between nodes were disabled, target occupancies remained **97.250% / 97.250%**. Direct sensory responses, node-local state and fixed motor wiring can therefore produce this behavior without associative network communication. Node identities follow first encounter order, while motor signs are fixed hashes of those identities: a concrete competing explanation. Node-local experience and identity-based wiring have not been independently separated; neither claim that all effects are wiring artifacts nor credit consolidation without further evidence.

**No activity strongly suggestive of autonomous consciousness was observed in this study.** The constructive result is that embodiment, inheritance and selection operate, while the missing contribution can now be stated more precisely: sustained internal interaction that demonstrably changes behavior.

![Overview](../../../docs/images/input-rate-autonomy-overview-2026-09-29.png)

## Input spacing

Compare 1000/100/20/5/1 ms while retaining all internal clocks: continuous 10 ms integration, 100 ms propagation, 10 ms delay; LIF 0.25 ms integration, 1 ms delay and 2 ms refractoriness. Anonymous A/C and D/E co-frame pairs receive 20/10/10 repetitions (80 frames, intensity 1). Wait 1 s after training. Separate single and five-frame burst cues use intensity 0.5 per frame, plus no-cue copies.

The secondary measure below is target-versus-other-target peak difference, adjusted by the no-cue copy and averaged over A and D. It is not a successful temporal-convergence score.

{rate_table}

The 100 ms burst value rises about **11.1%**, below the preregistered 20% switching criterion. Shorter intervals reduce it. LIF target peaks are zero throughout. Retain **1 s** for the environmental stage. The alternative criterion of a previously inactive source/target becoming selectively active was not met: LIF targets remained inactive, while continuous targets already had residual training activation without a cue. The tiny net D improvement at 100 ms is not first target activation. No candidate advanced to the reserved third-seed stage.

Two channel seeds yielded identical task dynamics under relabeling; they are encoding-consistency checks, not independent random-network replications. Shorter training also changes elapsed forgetting and total background exposure. This study does not establish a universal best frequency or isolate biological transmission speed.

### LIF obstacle

Training spike counts at 1000/100/20/5/1 ms were 160/160/152/148/80; burst cues still produced two source spikes. Yet all four directed task-pair connections ended at **zero weight** in every condition. Current arrival-based learning supplies a specific explanation: co-stimulated endpoints spike together, but their transmitted spikes arrive later, encountering a postsynaptic trace and subtracting weight. Repeating synchronous frames can thus weaken rather than consolidate those connections. Source code and results are consistent with this explanation; an independent input-order/delay experiment is still needed. This is not evidence against LIF in general.

## Plentiful supply and withdrawal

Local consumption/recovery, facilitation, inhibition, forgetting and self-inhibition remain enabled. Calibration/ordinary withdrawal preserve the previous disabled whole-model ledger. Ring and recovery experiments enable the existing ledger with one-unit offers every 100 ms, capacity 1 and unlimited total external stock. All 284 world instances have positive direct consumption and no unmet demand. Ordinary communication also consumes energy. The explicit communication-off control has zero associative expenditure. Local resources are never clamped to full. Maintenance charges remain coupled to the existing disabled starvation-damage path; this is not a complete biological metabolism model.

In four paired/balanced trained parents across two channel labels, withdrawing all inputs at 1 s after training leaves activation for about 0.6–0.7 s, then death at about 1.68–1.70 s including the existing grace. After 300 s of background, task activity is already absent; removing background leaves 0.4–0.5 s of activity and death at about 1.41 s. Twelve planned cues at 30 s were **not administered because the copies had died**. They are not failed responses to received cues. Internal in-flight events were retained.

With continuous external energy supply, vary only the existing local recovery constant on those saved post-training states:

{recovery_table}

Times denote the last nonzero 20 ms sample; zero follows within a sampling interval, then the one-second death grace. Faster recovery modestly increases paired-state transmission and lifetime, but none sustains a loop. The balanced condition barely changes. This is an acute post-training intervention, not retraining at each recovery rate.

![Withdrawal and energy](../../../docs/images/input-rate-autonomy-recovery-2026-09-29.png)

## Environmental selection

A body moves around a ring with two equally sized, equally intense four-channel sensory regions, plus signed velocity sensing. A fixed nonsemantic projection of **all** node activities, including background, drives physical motion and changes subsequent input. Record positions, velocities, raw stimuli, every node, proposed/applied controls and energy flows. Fixed projection is an engineering baseline, not emergent motor anatomy.

Two wiring blocks, four candidates per generation, three generations, region-0/region-1/random parent selection. Independent newborns provide scores; evaluation learning never alters candidate parents. Nonselection does not kill or clear a model. Each following table cell is **region-1 occupancy**, averaged over four held-out starts crossed with normal/swapped layouts for the same champion, not eight independent lineages.

{world_table}

Block 2 retains opposite selected preferences even after spatial swaps. Random selection also retains a strong region-1 preference: an arbitrary preference does not by itself demonstrate target learning. Block 1 keeps circling and remains balanced. Generation-zero newborn evaluations already split into about 6% versus 94% region-1 occupancy; later selection mainly retains existing differences. Comparing initial 94% with final 97% as learning gain would be invalid because evaluation starting positions differ.

![Body, activation and action](../../../docs/images/input-rate-autonomy-activity-2026-09-29.png)

The plotted body starts in the other region, enters the selected one and slows down. A position jump from 1 to 0 is ring wrapping. Ongoing sensory input drives the activity oscillations.

### Attribution

{attr_table}

Zero inter-node communication barely changes behavior. Disabling only evaluation-time positive edge consolidation also barely changes it, while retaining forgetting, node plasticity and fast traces. Thus **associative transmission is not required for this strong preference**. Direct contact, node-local history and identity-based motor projection remain. Quantifying their separate contributions is a next experiment, not a result already obtained.

All **12/12 sensory-replay copies have exactly the same final canonical Core state** as their source closed-loop run when supplied identical inputs and ineffective actions. This verifies reproducibility and excludes unrecorded AI decision-making. Recorded-action controls, region reversal at 30 s and fixed -0.5/0/0.5 physical controls are retained. Fixed controls average 0.5 across symmetric starts/layouts; remaining still can score 0 or 1 at one start. A high single score is insufficient evidence of agency.

**Current environmental feedback nevertheless makes a real difference.** In block 2, across the two matched starting positions under swapped layouts, current activity achieves **96.25%** target occupancy for either selected goal; replaying the old normal-layout actions achieves only **3.75%**. Fixed actions or initial inertia do not explain that contrast. Swapping patterns at 30 s leaves **81.83% / 81.67%** target occupancy in the second half. The body responds to current sensory conditions, but this can be an established direct sensory-motor response rather than learning a reversed goal, and it does not overturn the communication-off result.

## Temporal readouts

- 80 cued interval-test copies: 76 residual-decay, four transient, **zero qualifying convergence**. Twenty no-cue copies have no cue envelope. Complete window measurements, final-activation descending ranks and source spike evidence are saved.
- The live default excludes ambient-triggered windows, including ring inputs. Their absence is not absent activation. A separately registered **post-hoc** pass applies the unchanged temporal reader with ambient triggering to all 48 normal held-out world's saved 100 ms node samples, opening actual ring frames. It yields 2,880 windows: 2,832 residual decay, 48 censored at the saved-data endpoint, **zero qualifying convergence**. Final-activation ranks are included. No interpolation, Core rerun or threshold change; only ring frames open windows, while background effects remain in node states.
- Persistence and behavioral occupancy are separately registered endpoints, not renamed convergence successes.

## Practical next directions

1. Isolate motor wiring and receptor identity, then measure behavior added by internal communication and experience under matched receptor registration. Keep current wiring as a declared baseline. Do this before scaling training.
2. For LIF, calibrate controlled input order against transmission delays and learning windows before changing learning equations. More synchronous input is not a demonstrated solution.
3. For sustained activity, examine local recovery, losses and naturally acquired feedback structures. Plentiful external stock did not sustain activity here; faster local recovery only extended it modestly. Do not manufacture a loop by removing consumption or immediately rent larger machines.

Preserve genuine paired responses, inherited differences and working environmental feedback. The weakest demonstrated link is sustained, competing internal activity with a causal contribution to behavior.

## Execution and evidence

{common_methods}

Native CPU backend; aggregate instance wall time **{audit["compute_seconds"] / 60:.2f} minutes**. No GPU, cloud or paid AI. Existing kernels, defaults and old research data preserved. Only external tools and explicitly labeled copy-level parameter interventions were added.

Before publication: local evidence {audit["local_bytes"] / 2**20:.1f} MiB; database net growth {audit["database_growth_bytes"] / 2**20:.1f} MiB. Final archive-inclusive figures appear in the delivery record. Total budget 3 GiB, simulation admission cutoff 2.25 GiB. Net database growth can reuse old free pages and is not logical content size.

All 448 model checkpoints match local versus database canonical hashes and decoded contents; 12 replay matches. Canonical model hashes are distinct from archive-member byte SHA-256 checks. Four external-physics, dose and wiring tests pass. Stop conditions applied: no interval candidate, no extra seeds after early withdrawal deaths, no expanded recovery sweep without persistence, and completion of three generations and attribution. No experiment was expanded merely to exhaust the budget.

The public input-export service preserves 39,178 envelopes and 39,338 frames, all delivered at exactly their scheduled times. The original recorded host-telemetry clip and hash are included. Three documentation-resource tests also pass after an authorized retry resolved a sandbox temporary-directory denial.

[Overall registration](design.en.md), [withdrawal](activity.en.md), [world integration](world.en.md), [selection](selection.en.md), [recovery](recovery.en.md), [attribution](attribution.en.md), [execution guide](README.md). Each simulation stage was registered before its own data. Frozen execution tools and earlier drafts remain in the evidence archive. New Lab project: `2026-09-29 刺激间隔、自主活动与环境选择`; plans, records, bilingual reports and archive are published there without overwriting old projects.
"""
    for lang, text in (("zh", zh), ("en", en)):
        (HERE / f"report.{lang}.md").write_text(text, encoding="utf-8")
    records = {
        "rate": "# 输入间隔校准\n\n"
        + rate_table
        + "\n120 实例，另 4 个工程校准。LIF 各间隔任务边全为零。80 个提示窗口 0 合格收敛。原始末值排序见每例 result.json。保持 1 s，未改变内核时钟。",
        "activity": "# 全部输入停止后的活动\n\n32 实例。早期训练末态在断输入后约 0.6–0.7 s 归零，晚期背景末态约 0.4–0.5 s。12 个延后提示因死亡未执行，不能算刺激失败。背景继续时存活。未观察到自主持续循环。",
        "selection": "# 环境选择与行为归因\n\n下表为区域 1 占有率，包含未见起点和区域交换。\n\n"
        + world_table
        + "\n第二区组追加来源鉴别：\n\n"
        + attr_table
        + "\n252 个世界与选择实例，32 个归因实例。强偏向不依赖节点间通信；直接感官、节点自身历史与固定投影尚未拆分。随机选择也留下强偏向。12/12 感官回放末态一致。",
        "recovery": "# 局部恢复速度\n\n"
        + recovery_table
        + "\n8 个副本。无限外部库存、有限储量与供应速率、真实消耗、自身抑制均保留。配对组略延长，全部归零；没有继续扩大扫描。以 20 ms 保存全活动及局部可用份额。",
    }
    for key, text in records.items():
        (HERE / f"record-{key}.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    write()
