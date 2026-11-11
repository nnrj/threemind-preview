"""Render bilingual results from completed immutable study summaries."""

import shutil
import statistics

from common import HERE, ROOT, WORK, read_json

PLOT = "../../../docs/images/candidate-exploration-2026-09-29.png"


def fmt(x):
    return "—" if x is None else f"{x:.6g}"


def fraction(n, denominator):
    return f"{n}/{denominator}" if denominator else "—"


def write_reports():
    s = read_json(WORK / "summary.json")
    assert s["complete_blocks"] == 6 and s["rows"] == 2832
    gs = s["groups"]
    adapt = ["|Kernel / variant|First emitted|20th emitted|Unit|", "|---|---:|---:|---|"]
    for g in gs:
        k = g["condition"]
        if k[0] != "adaptation" or k[2]:
            continue
        m = g["measurements"]
        adapt.append(
            f"|{k[1]} / {k[3]}|{fmt(statistics.mean(v['first_sent'] for v in m))}|"
            f"{fmt(statistics.mean(v['last_sent'] for v in m))}|{g['transport_unit']}|"
        )
    pairs = [
        "|Kernel|Background|Condition|Retention (s)|Converged / all|Strict target leads / converged|Peak leads / observed (secondary)|",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for g in gs:
        k = g["condition"]
        if k[0] != "pair":
            continue
        n = g["primary_margin"]["n"]
        lead = f"{g['primary_strict_wins']}/{n}" if n else "—"
        pairs.append(
            f"|{k[1]}|{int(k[2])}|{k[3]}|{k[4] / 1e6:g}|{n}/{g['n']}|{lead}|{fraction(g['secondary_peak_strict_wins'], g['secondary_observed_count'])}|"
        )
    sequence = [
        "|Kernel|Background|Overlap|Swapped teaching|Converged / all|Strict target leads / converged|Peak leads / observed (secondary)|",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for g in gs:
        k = g["condition"]
        if k[0] != "sequence":
            continue
        n = g["primary_margin"]["n"]
        lead = f"{g['primary_strict_wins']}/{n}" if n else "—"
        sequence.append(
            f"|{k[1]}|{int(k[2])}|{int(k[3])}|{int(k[4])}|{n}/{g['n']}|"
            f"{lead}|{fraction(g['secondary_peak_strict_wins'], g['secondary_observed_count'])}|"
        )
    count = sum(g["primary_margin"]["n"] for g in gs if g["condition"][0] == "pair")
    wins = sum(g["primary_strict_wins"] for g in gs if g["condition"][0] == "pair")
    seqcount = sum(g["primary_margin"]["n"] for g in gs if g["condition"][0] == "sequence")
    seqwins = sum(g["primary_strict_wins"] for g in gs if g["condition"][0] == "sequence")
    tf = s["transformer"]["target_probability"]
    closure = read_json(WORK / "closure.json")
    focus = {
        g["condition"][1]: g
        for g in gs
        if g["condition"][0] == "pair"
        and g["condition"][2]
        and g["condition"][3] == "trained"
        and g["condition"][4] == 1000000
    }
    baseline = focus["threemind.causal/9"]
    continuous = focus["threemind.continuous/1"]
    focused = [
        "|Kernel|Converged / all|Strict target leads / converged|Peak leads / observed|Median block peak contrast|",
        "|---|---:|---:|---:|---:|",
    ]
    for g in gs:
        k = g["condition"]
        if k[0] == "pair" and k[2] and k[3] == "trained" and k[4] == 1000000:
            contrasts = [r["matched_minus_other"] for r in g["cue_contrasts"]["peak_activation"]]
            n = g["primary_margin"]["n"]
            lead = f"{g['primary_strict_wins']}/{n}" if n else "—"
            focused.append(
                f"|{k[1]}|{n}/{g['n']}|{lead}|"
                f"{fraction(g['secondary_peak_strict_wins'], g['secondary_observed_count'])}|{fmt(statistics.median(contrasts) if contrasts else None)}|"
            )
    topology = [
        "|Kernel|Input condition|Snapshots|Task edges (range)|Task edge weights (range)|Cross-background edges|",
        "|---|---|---:|---:|---|---:|",
    ]
    for kernel in dict.fromkeys(r["kernel"] for r in closure["topology"]):
        for condition in ("pair", "remapped", "sequence-pure", "sequence-overlap"):
            group = [r for r in closure["topology"] if r["kernel"] == kernel and r["condition"] == condition]
            edges = [r["task_edges"] for r in group]
            weights = [w for r in group for w in r["task_edge_weights"]]
            weight_range = f"{fmt(min(weights))}–{fmt(max(weights))}" if weights else "—"
            topology.append(
                f"|{kernel}|{condition}|{len(group)}|{min(edges)}–{max(edges)}|{weight_range}|"
                f"{sum(r['cross_background_edges'] for r in group)}|"
            )
    project = read_json(WORK / "platform.json")["project_id"]
    body_zh = f"""# 多内核初步实验：适应、配对与上下文

[English](report.en.md)

2026-09-29。项目：`{project}`。这是机制探索，不是意识或 AGI 的认证。设计先行写入实验笔记，保留三个内核公式、默认机制和感官映射。本轮使用匿名通道，未测试自然语言理解。

## 已完成范围

72 格校准、6 个输入／环境块、{s["rows"]} 个正式测量结果，以及 12 个独立小型 Transformer。训练使用共同强度 1.0、1 秒间隔；线索强度 0.5。每对先连续 20 次，再分别 10 次和 5 次。背景为 6 段各 300 次真实宿主采样，强度 0.2，按实际时间重放；进程和运行时遥测关闭。每个探测从训练父本另建副本，探测学习不写回父本。

配对测试共有 {count} 个窗口达到既有读出器的收敛判据，其中 {wins} 个窗口的原目标在四个候选中严格领先。顺序测试有 {seqcount} 个收敛窗口，其中 {seqwins} 个指定目标严格领先。**这些总数不能当作统一准确率**：其内包含不同背景、保持时间、消融、重新配对和交换教学。下面按条件分别列出，领先比例的“—”表示没有合格的主判据。

每次提示后最多推进 12 模拟秒。既有时序读出器可以提前结束窗口，例如首块连续模型的一次配对提示在 1.7 秒时以 `tail_amplitude_decline` 结束，归类为 `residual_decay`。主指标取该窗口记录的结束时刻，不强行改成第 12 秒。原始综合分数与排序仍保留；本报告另按 `last_activation` 比较目标，未改写原始读出。

“目标领先”在配对测试中比较四个预先声明的目标，在顺序测试中比较两个候选末符号；它不表示目标是整个意识中激活最强的节点。提示节点、背景节点和其他活动均保留在完整读出。这些比较集合属于外部实验指标，不写入内核，也不裁剪意识活动。

## 值得关注的现象

先看一个固定条件：原始配对训练结束，真实背景开启，等待 1 秒，再以一半强度分别提示四个线索。下表中的“峰值对照差”是每块正确配对的平均峰值减其他配对的平均峰值；它是辅助描述，不替换主判据。

{chr(10).join(focused)}

在这个固定条件中，旧基线有 {baseline["primary_margin"]["n"]}/{baseline["n"]} 个窗口符合收敛判据，其中 {baseline["primary_strict_wins"]} 个目标严格领先。这是可记录的条件性配对现象，不能被其他未收敛案例抹掉。连续模型则有 {continuous["secondary_peak_strict_wins"]}/{continuous["secondary_observed_count"]} 个观测窗口的配对目标峰值严格领先；它与收敛答案是不同层次的现象。二者都需结合无训练、无可塑性、保持时间和逐块数据理解，不以一个总分替代。

1. 短时突触机制改变了重复输入后的传播量。下表是无背景条件，各块第一次与第 20 次输入期间实际发射量的均值；连续模型与 LIF 的单位分别标明。参数消融的差别来自模型自身演化。单一双节点条件中的“无差别”，不能证明局部上下文机制没有作用，因为这里没有丰富的输入竞争。
2. LIF 存在短时间累积：校准中强度 0.5、间隔 10 毫秒的五次输入产生脉冲增量 `[0,0,2,0,2]`；100 毫秒和 1 秒间隔均为 `[0,0,0,0,0]`。这是实际脉冲事件，不能由 100 毫秒界面采样的投影是否亮起替代。后续设计应把刺激的可观测性校准与学习时间窗校准分开。
3. 收敛不自动等于有选择性的答案。首块旧基线的重新配对条件中，存在多个候选几乎并列的持续活动。完整末次激活排序保留在记录中；平局或差值不超过 1e-9 不计严格领先。峰值领先只是次要现象，不能替代收敛末态。`summary.json` 另存逐块“配对目标均值减其他目标均值”，避免固定偏好一个目标就出现 1/4 或 1/2 领先而被误判为线索区分。
4. 小型 Transformer 对两类已教上下文给出了高区分度概率：24 个指定目标概率的中位数为 {fmt(tf["median"])}，范围 {fmt(tf["min"])}–{fmt(tf["max"])}。一阶转移基线对这两个目标各给 0.5。这展示本机可执行的独立概率对照；这里只复测教过的上下文，没有未见名字、逻辑组合或环境泛化的证据，也没有把输出反馈给 ThreeMind。

![实验概览]({PLOT})

## 重复与适应

{chr(10).join(adapt)}

`sent` 是观察窗口内的总发射量，不是“有用传输”，也没有按研究者意图挑选信号。恢复测试的 0.1/1/10 秒各行及死亡标记见原始 `block-*.json` 和数据库中的对应意识。LIF 的 nA 与连续内核的激活冲量不构成同一评分尺度。

## 配对、保持与重新配对

背景 0/1 分别为无背景／真实宿主重放。`trained-aged` 比训练结束多等 40 秒，用于与额外 40 次重新配对匹配经过的时间。`untrained` 没有配对输入；`no-plasticity` 从出生关闭可塑性。`remapped` 的本表仍检查原目标，新目标的差值另存在 `summary.json`，不可把两个问题混用。

{chr(10).join(pairs)}

## 顺序与上下文

输入 A→B→C、D→B→E，交换对照为 A→B→E、D→B→C，两者词频及一阶转移相同。Overlap=0 每帧仅一个符号；Overlap=1 明确把相邻符号共同输入，属于另一个感官条件。共同输入的结果不能冒充纯顺序产生了连接。

{chr(10).join(sequence)}

## 连接结构揭示的边界

以下只读核对 144 个训练父本（每个内核、输入方式包含 6 块 × 有／无背景），状态哈希与保存时一致。没有根据输出好坏筛选父本。边数包含已保存的零权重连接条目，不等于有非零信号经过。

{chr(10).join(topology)}

本轮纯顺序输入没有形成任务通道之间的边；因此本轮尚未真正检验“已有时序连接能否承载上下文”。共同呈现形成了边，但三类内核的保留权重不同。LIF 的同步共同输入后配对边权降为零；其学习在前向信号到达和后节点脉冲时更新，不能把共同外部输入直接等同于必然巩固。

背景与任务之间没有跨边。背景可以改变全网络存活或读出窗口分类，却不等同于任务节点获得持续激活。为研究这种接触如何形成，应另设明确的感官重叠／错时条件或有依据的新生边变种，不能在分析时假定已有连接，也不能补造连接来美化结果。

## 解释边界与下一步

- 这是稀疏匿名模式的短期实验。不能据此证明或否定语言、因果推理或 AGI。六个通道重命名块不自动等于六个统计独立的机制样本；无背景确定性条件可能完全相同，报告只作描述，不提供伪独立的显著性检验。
- 背景来自实际机器，部分录制期间机器同时承担其他本轮任务；时间戳、可用／不可用指标及原始读数都保留。不同块不是平稳独立同分布噪声，块内对照使用同一段记录。
- 训练先后顺序固定，可能存在近因效应；通道重命名不消除此因素。重新配对另有等时等待对照，但没有把额外刺激数量与训练总量也配平，不能把所有差异归于覆盖旧记忆。LIF 的 0.5 剂量线索没有独立通过脉冲可观测性校准；不触发脉冲的结果不能证明该模型不能学习。
- 激活仍在、网络结构仍在、目标有峰值、收敛、选择性答案是不同结果。未收敛、死亡和预算停止分别记录。主判据缺失不补成 0；本表次要峰值包括没有收敛但实际观测到的窗口；没有观测窗的案例不计入峰值分母，“—”表示该次要指标也缺失。必须带分类理解。
- 下一步优先做毫秒级 LIF 事件读出及错时输入对照，并核对当前生边条件如何限制纯顺序学习。先研究实际机制及可观测时间尺度，再决定是否引入新变种。对持续但不具选择性的活动，可单列无提示／零强度提示检验。上述为后续建议，本轮没有追加调参来争取漂亮结果。
- CPU 上的 Transformer 只有 {read_json(WORK / "transformer-results.json")[0]["training"]["parameters"]} 个参数，每个训练 200 步。它验证接口和小任务，不代表大语言模型的资源需求。真实 GPU 尚未测试。

## 执行、资源与审计

模型状态和原始输入、脉冲、时序读出保存在本轮独立项目中；源码、方案版本、通道表、宿主录制、摘要、全部结果和观测文件可从证据包下载。模型状态在数据库检查点中，证据包以状态哈希和意识 ID 引用，可另用实验快照导出；该证据 ZIP 不是可直接导入的模型本体。

执行器曾出现逐秒遍历新增证据目录的监控瓶颈。修复后，轻量安全检查仍每秒进行，目录／数据库体积每分钟统计，提前 512 MiB 停止。独立重放的内核状态哈希和完整读出逐项一致，单例耗时从 18.72 秒降到 3.43 秒。一个无检查点的未提交案例重新执行，全部已提交案例保留；修复及版本记录在实验笔记第三版和 `guard-parity.json`。没有改动内核公式。

限制为单计算任务、2 个数值线程、RSS 4 GiB、24 小时、证据目标 4 GiB／上限 8 GiB、新增总占用 20 GiB，并保留 D/E 各 15 GiB。额度从已用 32% 计起，增加 10 个百分点即停止追加。发布前核对了 {closure["previous_projects_checked"]} 个旧项目的意识修订、状态哈希、状态及研究文档修订，均未变化。发布前资源快照见 `closure.json`；发布后的最终占用另记 `post-publication-closure.json`。

遥测信封的 `payload.frames` 是编码器原始输出（施加本实验强度之前）；实际递送以 `input_frames.stimulus` 为准，核验强度均为 0.2。复放应使用实际帧及原始时间戳，不能把这两层混淆。
"""
    body_en = f"""# Candidate kernels: adaptation, pairing and context

[中文](report.zh.md)

2026-09-29. Project `{project}`. This is a mechanistic exploration, not a certification of consciousness or AGI. The preregistered protocol preserves kernel formulas and sensory mappings. Anonymous channels do not test language understanding.

## Completed scope

72 calibration cells, six input/environment blocks, {s["rows"]} formal outcome rows and 12 independent tiny Transformers. Training intensity 1.0, interval 1 s; cue intensity 0.5. Each pair received 20 blocked repetitions, then 10 and five. Six distinct real host recordings contain 300 samples each; replay intensity is 0.2 with original timestamps. Process/runtime telemetry is off. Each probe uses its own training-state clone and never writes learning back to the parent.

Pairing produced {count} windows satisfying the existing convergence criteria; {wins} had a strict original-target lead among four candidates. Sequence tests produced {seqcount} converged windows and {seqwins} strict expected-target leads. **These totals are not a pooled accuracy**: conditions differ in background, retention, ablation and teaching. The tables separate conditions. A dash in the lead fraction means no qualifying converged evidence.

Each probe advances at most 12 simulated seconds. The existing reader may close earlier: one block-0 continuous-model pairing window closed after 1.7 s as `residual_decay`, reason `tail_amplitude_decline`. The primary metric uses the recorded window endpoint, not an imposed 12 s endpoint. Original composite scores/ranks remain intact; analysis separately compares `last_activation` without rewriting reader evidence.

Target leads compare the four preregistered paired targets, or the two possible sequence endings. They do not imply the target dominates every node in the consciousness. Cue, background and other activity remain in full readouts; candidate sets are external evaluation definitions, never Core instructions or cuts to recorded activity.

## Observations

A fixed comparison is trained pairing with recorded background, retention 1 s, and half-intensity cues. The auxiliary block peak contrast subtracts other-target means from matched-target means; it does not replace the primary endpoint.

{chr(10).join(focused)}

In this fixed condition, the baseline has {baseline["primary_margin"]["n"]}/{baseline["n"]} qualifying converged windows, with {baseline["primary_strict_wins"]} strict target leads. These conditional pairing observations must not be erased by other nonconverged cases. The continuous model has {continuous["secondary_peak_strict_wins"]}/{continuous["secondary_observed_count"]} observed windows with a strict matched-target peak lead, a different phenomenon from a converged answer. Both require untrained/plasticity controls, retention and block-level interpretation rather than one overall score.

1. Short-term synaptic dynamics change emitted transmission after repetition. The first table reports mean first/20th emission under no background, with distinct physical units. An unchanged two-node context ablation does not establish that context competition is ineffective in richer networks.
2. LIF shows temporal accumulation: five inputs of intensity 0.5 at 10 ms intervals produced actual spike increments `[0,0,2,0,2]`; 100 ms or 1 s produced `[0,0,0,0,0]`. A 100 ms display projection cannot replace event-based spike measurement. Observability and the learning time window require separate calibration.
3. Convergence is not necessarily selective recall. Some remapped baseline cases converge with several candidates nearly tied. Full end-of-window activation is retained; ties and differences <=1e-9 are not strict leads. Peak responses remain secondary. Per-block matched-minus-other means in `summary.json` help distinguish cue discrimination from always favoring one target, which can otherwise score 1/4 or 1/2.
4. Tiny Transformers discriminate the two taught contexts: 24 expected-target probabilities have median {fmt(tf["median"])}, range {fmt(tf["min"])}–{fmt(tf["max"])}; the first-order baseline assigns 0.5 to each target. This is a rehearsed-context control, with no evidence of unseen-name or rule generalization and no feedback to ThreeMind.

![Overview]({PLOT})

## Repetition and adaptation

{chr(10).join(adapt)}

Emission includes all transmitted activity, without filtering for human-perceived utility. Recovery at 0.1/1/10 s and lifecycle outcomes are retained in `block-*.json` and the project. LIF nA and continuous activation impulse are not a common intelligence scale.

## Pairing, retention and remapping

Background 0/1 means none/recorded host. `trained-aged` waits an additional 40 s to match the remapping exposure duration. `untrained` has no paired input; `no-plasticity` disables plasticity from birth. This table evaluates the original target under `remapped`; new-target margins are separate in `summary.json`.

{chr(10).join(pairs)}

## Order and context

Teach A→B→C and D→B→E; the swapped control teaches A→B→E and D→B→C, preserving unigram and first-order counts. Overlap=0 presents one symbol per frame. Overlap=1 explicitly co-presents adjacent symbols, a different sensory condition whose results cannot establish pure sequential growth.

{chr(10).join(sequence)}

## Structural boundary

Read-only checks cover 144 training parents (six blocks × background on/off for every kernel/input condition), with hashes matching their committed states. Parents were not selected according to output success. Edge counts include stored zero-weight entries and do not imply nonzero transmission.

{chr(10).join(topology)}

Pure sequential input formed no task-channel edges, so this round does not yet test how an existing temporal pathway could carry context. Co-presentation formed edges, with different retained weights. Synchronous LIF pairing reduced paired-edge weights to zero; learning occurs at presynaptic signal arrivals and postsynaptic spikes, so simultaneous external input does not imply inevitable strengthening.

No edges crossed between task and background channels. Background may affect global survival or window classification without sustaining task-node activation. Sensory overlap, offset timing, or an independently justified edge-growth variant require a separate protocol; analysis must not assume or manufacture absent connections.

## Limits and next steps

- These are small anonymous-pattern tests, not proof for or against language, causal reasoning or AGI. Channel permutations do not create independent mechanism samples; deterministic no-background blocks may coincide. Descriptive results are reported without pseudoreplicated significance tests.
- Real recordings include machine activity during other tasks in this study. Timestamps, availability and raw readings are retained. Blocks are not stationary IID noise; within-block controls use the identical recording.
- Fixed curriculum order permits recency effects; renaming channels does not remove them. Remapping has an age-matched waiting control but no equal-count extra-training control. The 0.5 LIF cue dose was not independently calibrated for spike observability; absent probe spikes do not establish inability to learn.
- Structural persistence, ongoing activation, a target peak, convergence and selective output are distinct. Missing primary evidence is not zero. Death, nonconvergence and resource censoring remain separate; secondary peaks include observed nonconverged windows but exclude unobserved cases from the denominator (a dash denotes missing secondary evidence). Interpret them with their window classifications.
- Next priorities are millisecond-scale LIF event readouts and offset-input protocols, plus auditing how edge-growth conditions constrain pure sequence learning. Persistent nonselective activity merits a separate no-cue/zero-dose control. These are future protocols, not post-hoc parameter tuning in this round.
- Each CPU Transformer has {read_json(WORK / "transformer-results.json")[0]["training"]["parameters"]} parameters and trains for 200 steps. This validates small controls and interfaces, not large-language-model hardware requirements. Real GPU execution remains untested.

## Execution and audit

Model checkpoints, original inputs, spike events and temporal records are stored in the new project. The evidence archive contains protocols, source versions, recordings, observations, summaries and state hashes. Model states remain in database checkpoints and can be exported through experiment snapshots; this evidence ZIP is not an importable model artifact.

Per-second recursive metadata scanning caused an instrumentation bottleneck. Lightweight checks remain per-second; directory/database size scans now run per-minute with 512 MiB stop headroom. Independent replay matched the exact state hash and full temporal readout, reducing one case from 18.72 s to 3.43 s. One uncommitted case without a checkpoint was restarted; all committed evidence remains. Notebook revision 3 and `guard-parity.json` document the fix. No kernel formula changed.

Limits: one compute task, two numerical threads, 4 GiB RSS, 24 h total, 4 GiB target/8 GiB maximum evidence, 20 GiB new occupancy, and 15 GiB reserves on D/E. Account usage starts at 32%, with at most ten additional percentage points. All {closure["previous_projects_checked"]} pre-existing projects retained their run revisions, state hashes, statuses and research-document revisions. The pre-publication snapshot is `closure.json`; final occupancy after publication is recorded separately in `post-publication-closure.json`.

Host envelope `payload.frames` contains encoder output before the explicit study intensity. Actual delivery is recorded in `input_frames.stimulus`, verified as intensity 0.2. Replays must use those actual frames and timestamps rather than confusing the two layers.
"""
    for lang, body in (("zh", body_zh), ("en", body_en)):
        target = HERE / f"report.{lang}.md"
        with target.open("x", encoding="utf-8") as f:
            f.write(body)
    shutil.copy2(WORK / "overview.png", ROOT / "docs/images/candidate-exploration-2026-09-29.png")
    print("Bilingual reports generated from complete summaries.")


if __name__ == "__main__":
    write_reports()
