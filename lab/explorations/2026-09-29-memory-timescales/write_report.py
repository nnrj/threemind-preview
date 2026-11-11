"""Build bilingual human-readable reports from audited, saved experiment results."""

import json
import shutil
import statistics

from common import HERE, ROOT, WORK


def write():
    a = json.loads((WORK / "analysis.json").read_bytes())
    audit = json.loads((WORK / "audit.json").read_bytes())
    assert a["cases"] == audit["cases"] == 598 and not a["failures"] and not audit["failures"]
    retention = "|D/F/L|1 s|30 s|300 s|\n|---|---:|---:|---:|\n"
    short = "|D/F/L|0.1 s|1 s|3 s|\n|---|---:|---:|---:|\n"
    for b in a["short"]:
        retention += (
            "|" + b + "|" + "|".join(f"{a['retention'][b][str(d)]['specificity']:.8f}" for d in (1, 30, 300)) + "|\n"
        )
        short += "|" + b + "|" + "|".join(f"{a['short'][b][str(d)]['mean']:.9f}" for d in (0.1, 1, 3)) + "|\n"
    readout = "|D/F/L|30 s: L on → off|300 s: L on → off|\n|---|---:|---:|\n"
    for b in ("001", "011", "101", "111"):
        values = []
        for d in (30, 300):
            rows = [
                v
                for v in a["test_time_consolidation"].values()
                if v["bits"] == b and v["delay"] == d and not v["balanced"]
            ]
            values.append(
                f"{statistics.mean(v['signed_peak_L_on'] for v in rows):.8f} → {statistics.mean(v['signed_peak_L_off'] for v in rows):.8f}"
            )
        readout += "|" + b + "|" + "|".join(values) + "|\n"
    min_ratio = min(
        v["signed_peak_L_off"] / v["signed_peak_L_on"]
        for v in a["test_time_consolidation"].values()
        if not v["balanced"] and v["signed_peak_L_on"] > 0
    )
    improvement = a["retention"]["111"]["300"]["specificity"] / a["retention"]["101"]["300"]["specificity"] - 1
    resources = (
        f"{audit['compute_seconds'] / 60:.2f}",
        f"{audit['local_bytes'] / 2**20:.1f}",
        f"{audit['database_growth_bytes'] / 2**20:.1f}",
    )
    zh = f"""# 耗竭、易化与连接巩固：实验结果

[English](report.en.md)

2026-09-29。**已完成 598 个整网实例；旧数据和旧内核保留。** [原设计](design.zh.md)按实施前状态冻结；本报告追加实际结果和执行修订。

## 先说发现

1. **连接巩固确实把重复经历变成了能再次唤起的配对。** 四个 L 开启组，在两个交换教材的区组里，等待 30、300 模拟秒后，只给提示，都能让对应目标比另一个目标激活得更强。四个 L 关闭组在这两个时点的目标响应都是 0。遗忘一直开启。这里确认的是当前训练和强度下的可用差别；L 关闭仍有初次生边、节点学习等机制。
2. **易化有实际增益，而且会与资源约束共同改变活动形态。** 保留耗竭和巩固时，加入易化让 300 秒处的配对特异响应提高约 **{improvement * 100:.1f}%**。关闭耗竭后，易化与巩固一起作用，形成了另一种持续低幅内部活动。
3. **那种持续活动的维持条件已经查明。** 训练结束后 300 秒仍有约 0.01715—0.02306 的任务节点激活；恢复耗竭，约 0.65 秒归零；关闭易化，约 0.55 秒归零；只关闭后续巩固，额外观察 15 秒仍持续。两套交换教材都如此。巩固形成的结构可以支持循环，循环的即时维持依靠足够的释放和易化。
4. **上一轮的短时前缀效果是真的，但有效条件比“学会序列”窄。** 训练末态等待 1 秒时，A→B 和 D→B 分别偏向各自结尾；等待 3 秒便都偏向同一结尾，20 秒后也没有恢复。它依赖当时的历史状态，不能直接当作已经形成稳健序列规则。
5. **约定的合格时序收敛输出仍未出现。** 452 个有任务提示的正式及扩展测试都被既有读出器归为“残余衰减”，0 个为合格收敛。上面描述的是完整活动曲线中的事实，峰值是单独登记的机制指标。58 个无任务提示对照没有载体窗口，属于预定设计。

## 八组比较了什么

D 为资源耗竭，F 为短时易化，L 为既有连接的正向权重／稳定度巩固。1 开、0 关。F 不是此前报告中的 fast 快痕迹。

新增独立研究内核 `threemind.continuous-memory/1`，状态 `threemind.continuous-memory-state/1`，假说标识 `threemind.hypotheses/continuous-memory1`。`continuous/1` 与 `causal/9` 保留；新版本默认 D/F/L=101 精确复现原连续版，不替换原默认内核。

- D 关是**无限补给的研究对照**：每次释放使用 x=1，保留基础利用率 U=0.5 和 u 的历史。它不是更高生物真实性的默认方案。
- F 开使用既有易化公式，恢复时间常数 1 秒；关时利用率固定为 U。资源恢复仍为 0.8 秒，活跃态 0.003 秒。
- L 关只拦截既有边的正向权重和稳定度增加；初次生边、资格迹、触达历史、节点支持与可塑性、快痕迹、遗忘、修剪均继续。
- 抑制、自身抑制、激活和痕迹衰减、上下文、门槛、映射等均未随意关闭。完整配置只出现已登记的差异。独立控制经 Python／Rust 八组合和保存恢复验证。

训练采用匿名通道，用 A/B/C/D/E 表示，标签未进入内核。短时任务为 `[A]→[A,B]→[B,C]` 与另一对应，分 20、10、5 次重复；保持任务为 `[A,C]`、`[D,E]`，分 20、10、10 次重复。另有四种交叉配对各 10、5、5 次的平衡教材，总帧数与各通道剂量相等。两个区组交换 C/E；不是独立随机种子的大样本。

每帧间隔 1 模拟秒、强度 1；提示强度 0.5。保持时间从最后训练帧实际递送时刻计起。所有正式条件回放相同宿主机记录，强度 0.2，周期 **300.413474 秒**，保留原始采样抖动。记录哈希见审计文件。映射后背景与任务通道无重叠；全部保存末态没有两者之间的交叉边。背景维持整体存活，不自动把任务子网一直激活。

## 较长时间的配对保持

表中数值为“匹配目标峰值−另一目标峰值”，再减去平衡教材的相同指标；每格含两个交换区组的 A、D 提示，共 4 个副本。绝对量不做百分制包装。目标没有直接获得测试刺激。

{retention}

30 和 300 秒处，001、101、111 的任务节点在提示前激活为零，收到提示后才重新激活；011 则保持内部活动，属于另一种状态。011 的较大数值不能直接当作比其他组更好的同类静默记忆。

在 300 秒处，001、101、111 的配对边权重优势分别约为 0.1818、0.1311、0.1314；011 为 1。L 关闭的四组在 30 秒还剩约 0.0137—0.0197 的权重优势，但不足以在本次提示下触发目标；到 300 秒该优势为零。**结构残留、可唤起响应、持续活动是三个不同结果。**

1 秒条件仍有上一条训练输入留下的活动。追加的 32 个无提示对照及 64 次对应比较保留在 `residual_controls`，不能把训练残留当作新提示的回答。更干净的安静后唤起证据来自 30、300 秒的 001、101、111。

![八组合跨时间尺度比较](../../../docs/images/memory-timescales-2026-09-29.png)

## 是已有记忆，还是测试时重新学出来的

先保留 L 开启完成训练和等待，在提示之前才用公开配置接口关掉 L。其他参数不变，平衡教材也做同样对照。表中为配对教材的匹配峰值差均值：

{readout}

全部配对副本关闭测试时巩固后仍保持正确目标优势；最少保留原差值的 **{min_ratio * 100:.3f}%**。因此，当前响应主要由已有结构产生，测试过程中新增的正向巩固只贡献很小变化。该结论不依赖把整个学习或遗忘关掉。

## 持续内部活动的来源

011 组完成训练后，两个配对子网都在没有新任务刺激的情况下继续循环激活。300 秒时，在同一状态上分支：

|只在观察开始时改变|结果|
|---|---|
|不改参数|继续在约 0.01715—0.02306 之间波动，15 秒观察结束仍活跃|
|恢复资源耗竭|最后非零样本为 0.64 秒，0.65 秒归零|
|关闭易化|最后非零样本为 0.54 秒，0.55 秒归零|
|同时恢复耗竭、关闭易化|0.55 秒归零|
|只关闭后续正向巩固|与不改参数的活动轨迹一致，继续循环|

两套交换教材结果一致。这说明当前模型已经具有**安静结构中的可唤起记忆**和**由局部反馈维持的持续活动**两种状态。耗竭在这里既能携带近期历史，也能限制正反馈；易化既能放大短时响应，也能帮助强连接进入持续活动。三机制不是简单相加。

这里的 D=0 仍是无限补给干预，不能据此推荐删除耗竭。波动遵循现有 100 ms 传播节律；本轮没有新增自主时钟。没有加入内容评分、指定答案或目标偏好。

![安静后唤起与持续活动的开关核查](../../../docs/images/memory-timescales-activity-2026-09-29.png)

## 短时前缀效果的适用范围

共同等待 20 秒后，16 个准备状态的资源、易化和快痕迹残余均低于 1e−6。八组的平均匹配峰值差如下；平均为零可能是两次都偏向同一结尾，并非完全没有激活：

{short}

010 在 3 秒间隔下出现 0.0003185 的平均幅度差，但每个教材内 A→B、D→B 仍偏向同一结尾；开启 L 后这项幅度差消失。它是值得保留的非线性组合现象，尚不能叫正确序列选择。

从训练末态另取副本，保持 F 关、L 开，只比较 D：

|D|训练后等待|A→B 匹配差|D→B 匹配差|
|---:|---:|---:|---:|
|开|1 s|+0.000977870|+0.002735633|
|开|3 s|+0.000970302|−0.000970324|
|关|1 s|+0.002353496|−0.002354272|
|关|3 s|+0.002315407|−0.002316217|

交换教材复现同样模式。资源耗竭参与了 1 秒条件的路径区别；3 秒与 20 秒条件没有保持这种区别。等待也会改变抑制、快痕迹、稳定度等状态，不能把所有时间变化归给单一资源常数。完整两两及三阶交互、不同固定背景下的效应均存于 `analysis.json/interactions`，不只报告一个总均值。

## 读出与下一步判断

主要标准始终是**合格收敛窗口结束时的激活强度排序**。完整窗口、末值排序、终止原因与原始曲线全部保存。本轮有提示的 452 个窗口都是 residual_decay；58 个无提示对照为 no_window。所有正式提示完整递送，正式意识均存活；4 个死亡实例来自无背景的旧结果复现。

读出器保留原有 0.055 激活筛选阈值等设置，仅按设计将共同序列上限设为 15 秒；原结果复现仍用 12 秒。300 秒处 101/111 的目标峰值约 0.009—0.011，低于该筛选值；011 的响应更大，但仍被归为衰减。因此，约定主指标尚未通过，同时存在可直接核查的配对响应和持续活动。后续可独立审查“残余衰减／自然竞争结束”的读出定义；本轮没有为过关改变分类或替换主指标。

**建议继续保留 L；优先研究有资源约束的 D+F+L。** 本轮已经确认巩固保留可用结构、易化增益，以及耗竭限制循环的具体作用。011 适合当作持续活动的机制对照。下一步若研究跨时关联，应保持这轮基线，并另测未同时触达的输入如何形成连接；本轮同帧配对不能替它作答。

没有继续扩大词表、寻找“最好”参数或训练规模；未做新的独立种子、AB/BA 泛化或低 U 层。结论范围是本次匿名通道、两个交换区组和指定强度。相关生物机制及七篇原始文献已追加在[前轮报告末尾](../2026-09-29-continuous-mechanisms/report.zh.md)，本轮的价值是把各机制在 ThreeMind 中的作用进一步分开。

## 证据、实现与预算

- 6 个复现实例、210 个短时阶段实例、224 个保持阶段实例；另有 158 个预先登记的有限核查，总计 598，低于 650。正式及扩展测试副本共 510，其中 58 个为无任务提示对照。
- 原连续版训练末态哈希精确复现；新研究内核的默认配置与其行为一致。四个额外公开观察器副本与原对应副本的最终内核哈希相同。598 个数据库检查点均实际解码并与本地哈希核对，无失败。
- Python 检查 95 通过、1 跳过；Rust 核心测试 5 通过；前端构建通过。此次未运行浏览器端到端测试，不把构建当作交互验收。
- 单 CPU worker，合计模拟实例计算 **{resources[0]} 分钟**。发布前本地证据约 **{resources[1]} MiB**，数据库净增长约 **{resources[2]} MiB**。总新增预算 2 GiB；压缩包在内存生成、逐成员校验后存入数据库，避免额外落地一份大包。最终账目另见交付记录。
- 账户用量从设计基线 41% 到实验结束核查 43%，是共享账户的粗粒度读数，不能精确归因；44% 软停止线保留。未调用付费模型、云算力或 GPU。
- `execution-manifest.json` 冻结八配置与输入；三份扩展登记说明理由和全组合范围。保持阶段仅减少背景节点的重复高频存储，任务曲线、完整时序读出和首尾状态保留；变更记录在 `execution-amendment-1.json`，没有更改输入或内核。
- 原证据包 SHA-256 仍为 `{audit["previous_archive_sha256"]}`。旧数据未迁移、清理或覆盖。原设计笔记及报告历史版本保留。

入口与复现方式见 [README](README_CN.md)。数据中包含完整配置、输入信封、检查点、10 ms 任务轨迹、读出器状态、局部诊断和所有交互效应。原始证据包通过平台项目中的报告附件下载。
"""
    en = f"""# Depletion, facilitation and consolidation: experiment results

[中文](report.zh.md)

2026-09-29. **598 whole-network instances completed; existing kernels and evidence preserved.** The [original design](design.en.md) is retained as preregistration. This report adds execution results and amendments.

## Findings in plain language

1. **Consolidation preserved associations that could be recalled.** All four L-on configurations showed target-specific responses after 30 and 300 simulated seconds in both swapped curricula. All four L-off configurations had zero target response at these delays under the chosen cue. Forgetting remained enabled. L-off still permits edge birth and node learning.
2. **Facilitation contributed measurable gain and changed the activity regime.** With depletion and consolidation retained, facilitation increased the pairing-specific response at 300 seconds by **{improvement * 100:.1f}%**. With depletion disabled, facilitation plus consolidation instead supported persistent low-amplitude activity.
3. **The persistent activity has identified maintenance requirements.** Task activity remained around 0.01715–0.02306 after 300 seconds without task input. Restoring depletion silenced it by 0.65 seconds; disabling facilitation by 0.55 seconds. Disabling only subsequent consolidation left the next 15 seconds of activity unchanged. Both swapped curricula reproduced this result.
4. **The earlier prefix effect is real but strongly dependent on recent history.** After a one-second post-training wait, A→B and D→B favored their respective learned endings. After three seconds, both favored the same ending; twenty seconds did not restore the distinction. This is a state-dependent effect, not established robust sequence learning.
5. **The preregistered converged temporal-output criterion was not met.** All 452 cued formal and extension tests were classified as residual decay. The observations above concern preserved activity trajectories and explicitly secondary mechanistic metrics. The 58 no-task-cue controls intentionally had no carrier window.

## Controls and implementation

D = depletion, F = short-term facilitation, L = positive consolidation of existing-edge weight/stability; 1 on, 0 off. F is not the fast trace named F in the previous study.

The independent research kernel is `threemind.continuous-memory/1`, state `threemind.continuous-memory-state/1`, hypothesis `threemind.hypotheses/continuous-memory1`. Existing continuous/1 and causal/9 remain available. The new default 101 reproduces continuous/1 and does not replace the platform default kernel.

D-off clamps available resources to x=1 while retaining U=0.5 and utilization history: an explicit **unlimited-supply control**, not a physiological default. F-on uses the existing facilitation rule with a 1-second constant; recovery remains 0.8 seconds and active-resource decay 0.003 seconds. L-off blocks only positive changes of existing-edge weight/stability; birth, eligibility, touches, node support, plasticity, fast trace, forgetting and pruning remain active. Inhibition, self-inhibition, decay, local context, thresholds, encoding and other parameters were not casually disabled. Python/Rust equivalence and persistence tests cover all eight combinations.

Anonymous channels were labelled A/B/C/D/E outside the kernel. The short-timescale curriculum used `[A]→[A,B]→[B,C]` and the alternative ending, in 20/10/5 repetitions. Retention used `[A,C]` and `[D,E]`, in 20/10/10 repetitions. Balanced training used all four cross-pairings in 10/5/5 repetitions, matching frame count and channel dose. Two blocks swap C/E; these are paired controls, not independent random training seeds. Training intensity was 1, intervals one simulated second; cue intensity was 0.5. Retention starts at actual delivery of the last training frame.

All formal cases replay the same real host recording at intensity 0.2, with its measured **300.413474-second** period and original sampling jitter. Recorded background channels do not overlap task channels; no cross-edge occurs in any saved endpoint. Background keeps the overall consciousness alive without necessarily maintaining task activation.

## Retention across eight combinations

Each cell is the matching-target minus alternative-target peak, minus the corresponding balanced-curriculum margin, averaged over A/D cues in the two swapped blocks (four copies). Targets receive no direct test stimulus.

{retention}

At 30 and 300 seconds, task nodes in 001, 101 and 111 were inactive before the cue and reactivated afterward. Configuration 011 retained activity throughout; its larger margin is a different regime, not a directly comparable improvement in silent memory.

At 300 seconds, paired edge-weight advantages were approximately 0.1818, 0.1311 and 0.1314 for 001, 101 and 111; 011 retained 1. L-off groups still had weight advantages around 0.0137–0.0197 at 30 seconds, insufficient to activate targets under this cue, and zero advantage at 300 seconds. Structural residue, usable recall and persistent activity are distinct outcomes.

The one-second measurements include residual training activity. Thirty-two additional uncued controls and 64 matched comparisons are retained in `residual_controls`; residual activation must not be called a newly elicited answer. The cleaner quiescent-recall evidence is at 30/300 seconds in 001/101/111.

![Factorial timescale comparisons](../../../docs/images/memory-timescales-2026-09-29.png)

## Existing memory versus learning during the test

L remained on during training and waiting; only immediately before testing was it switched off through public reconfiguration. Balanced curricula received the same intervention. The table shows paired-curriculum matching peak margins:

{readout}

Every paired test retained the correct target advantage with test-time consolidation disabled; the smallest retained fraction was **{min_ratio * 100:.3f}%**. Existing structure supplies the response, while positive consolidation during the test contributes only small changes. Forgetting and other learning-related state were not globally disabled.

## Persistent activity

After 300 seconds without task input, separate copies of the same 011 state received no task cue:

|Intervention at observation start|Result|
|---|---|
|None|Activity continued between about 0.01715 and 0.02306 for the full 15 seconds|
|Enable depletion|Last nonzero sample 0.64 s; zero at 0.65 s|
|Disable facilitation|Last nonzero sample 0.54 s; zero at 0.55 s|
|Both changes|Zero at 0.55 s|
|Disable further positive consolidation|Same activity trajectory as unchanged control|

Both swapped blocks agree. The model exhibits recall from quiescent structure and sustained local feedback. Depletion both carries recent history and limits positive feedback; facilitation can amplify transient responses or support persistent activity through strong connections. Their effects do not simply add. D-off remains an unlimited-supply intervention, so this is not a recommendation to remove depletion. Oscillations follow the existing 100-ms propagation cadence; no new autonomous clock was introduced.

![Quiescent recall and maintenance controls](../../../docs/images/memory-timescales-activity-2026-09-29.png)

## Scope of the prefix effect

After the common 20-second wait, all sixteen preparation states had resource, utilization and fast-trace residuals below 1e−6. Mean matched peak margins follow. Zero average may mean both cues prefer the same target rather than no activation.

{short}

010 at the three-second gap has a measurable 0.0003185 amplitude margin, yet both prefixes within a block still favor the same ending. Enabling L removes this amplitude effect. It is a nonlinear interaction worth retaining, not a successful target-selection result.

Additional copies started directly from training endpoints with F off and L on:

|D|Post-training wait|A→B matched margin|D→B matched margin|
|---:|---:|---:|---:|
|On|1 s|+0.000977870|+0.002735633|
|On|3 s|+0.000970302|−0.000970324|
|Off|1 s|+0.002353496|−0.002354272|
|Off|3 s|+0.002315407|−0.002316217|

The swapped block reproduces these values. Depletion participates in the one-second distinction, which does not survive the three- or twenty-second waits. Waiting also changes inhibition, trace and stability; elapsed-time effects cannot all be assigned to one recovery constant. All pairwise and three-way interaction contrasts, including effects within each fixed-factor background, are preserved in `analysis.json/interactions`.

## Readout and next decisions

The primary criterion remained **end activation ranked within a qualifying converged temporal window**. Full windows, end-value rankings, classifications and raw curves are retained. All 452 cued tests were residual_decay; the 58 uncued controls were no_window. Every formal cue frame was delivered and formal consciousnesses remained alive. Four deaths occurred only in no-background reproduction of the earlier study.

The readout retains its 0.055 activation threshold and other settings; only the preregistered common sequence horizon is 15 seconds (12 seconds for old-result reproduction). At 300 seconds, target peaks in 101/111 are about 0.009–0.011, below that readout threshold. The larger 011 response is still classified as decay. Thus the chosen primary criterion failed while association-specific responses and persistent activity remain directly observable. A future separate study can examine whether residual-decay classification fully captures the intended end of natural competition. This experiment did not alter classification to obtain success.

**Retain consolidation and prioritize the resource-constrained D+F+L regime.** The evidence identifies stored usable structure, facilitation gain and depletion's suppression of persistent feedback. Keep 011 as a mechanistic control for sustained activity. Associations between inputs that never co-occur remain a separate next problem; simultaneous pair training here does not establish that capability.

No additional vocabulary, independent seed sweep, AB/BA generalization, low-U layer or unbounded parameter search was attempted. The scope is these anonymous channels, two swapped blocks and stated intensities. The [previous report appendix](../2026-09-29-continuous-mechanisms/report.en.md) preserves the discussion and seven primary references; this study separates their instantiated roles in ThreeMind.

## Evidence, validation and limits

- 6 reproduction, 210 short-stage and 224 retention-stage instances, plus 158 preregistered follow-up instances: 598 total below the 650 limit. There are 510 formal/extension test copies, including 58 uncued controls.
- Exact old-training state reproduction and default-candidate equivalence; four public-observer copies ended with the exact same kernel hash as their counterparts. All 598 database checkpoints were decoded and matched against local hashes, without failures.
- Python: 95 passed, 1 skipped. Rust core: 5 passed. UI build passed. Browser end-to-end tests were not run in this study.
- Single CPU worker, **{resources[0]} minutes** summed instance compute. Before publication: **{resources[1]} MiB** local evidence and **{resources[2]} MiB** database net growth. Total new-storage cap 2 GiB. The verified ZIP is assembled in memory and stored in the database without another local archive copy. Final accounting is in the delivery record.
- Shared account usage was 41% at design registration and 43% at experiment completion; the coarse shared figure is not exact attribution. The 44% soft stop remains. No paid model, cloud compute or GPU was used.
- `execution-manifest.json` freezes configurations and inputs; extension registrations record rationale and full control sets. A storage-only amendment reduced redundant high-frequency background-node recording in retention, preserving task curves, complete readouts and endpoint states. No stimulus or kernel rule changed.
- Previous evidence ZIP remains `{audit["previous_archive_sha256"]}`. Old data, original design notes and report revisions were neither migrated, deleted nor overwritten.

See [README](README.md) for entry points. Evidence includes configurations, envelopes, checkpoints, 10-ms task trajectories, readout states, local diagnostics and complete factorial effects, downloadable from the platform report attachment.
"""
    for language, body in (("zh", zh), ("en", en)):
        discussion = HERE / f"discussion.{language}.md"
        if discussion.exists():
            body += "\n---\n\n" + discussion.read_text(encoding="utf-8")
        (HERE / f"report.{language}.md").write_text(body, encoding="utf-8")
    for source, dest in (
        ("overview.png", "memory-timescales-2026-09-29.png"),
        ("activity.png", "memory-timescales-activity-2026-09-29.png"),
    ):
        shutil.copy2(WORK / source, ROOT / "docs/images" / dest)


if __name__ == "__main__":
    write()
