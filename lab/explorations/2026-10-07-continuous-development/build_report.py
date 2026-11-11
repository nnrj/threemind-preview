"""Render bilingual E62 reports from completed cases; no new simulation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2]/'.work/continuous-development-20261007'


def main():
    data = json.loads((WORK/'analysis.json').read_text(encoding='utf-8'))
    stages = {r['case']:r for r in data['stages']}
    base = 's223-direct-aligned'
    taught = stages[base]; corrected = stages[base+'-correction']
    evaluation_names = [base+'-system-normal', base+'-system-visible-cue-normal',
        base+'-correction-system-normal', base+'-correction-system-silence', base+'-correction-system-rescue']
    labels = [('教学后，短提示','After teaching, brief cue'),
        ('教学后，持续提示','After teaching, visible cue'), ('纠错后，短提示','After correction, brief cue'),
        ('纠错后，已有连接静默','After correction, existing edges silenced'),
        ('纠错后，连接恢复','After correction, restored edges')]
    tables = [[], []]
    for name, label in zip(evaluation_names, labels):
        if name not in stages: continue
        r = stages[name]; fresh = sum(t['reached_from_outside'] for t in r['by_task'].values())
        for i in (0,1): tables[i].append(f'| {label[i]} | {r["end_reached"]}/{r["n"]} | {r["ever_reached"]}/{r["n"]} | {fresh}/{r["n"]} | {r["mean_eye_error_rad"]:.3f} | {r["mean_hand_error_m"]:.3f} |')
    comparisons = data['action_and_body_comparisons']
    causal_zh = []; causal_en = []
    for r in comparisons:
        kind = '静默' if r['intervention'].endswith('silence') else '恢复'
        causal_zh.append(f'- {kind}：{r["action_changed_frames"]}/{r["frames"]}帧执行命令改变，{r["body_changed_frames"]}/{r["frames"]}帧身体状态改变；最大命令差{r["maximum_command_difference"]:.6g}。比较容差1e-7。')
        causal_en.append(f'- {r["intervention"].rsplit("-",1)[1]}: commands differ in {r["action_changed_frames"]}/{r["frames"]} frames and body state in {r["body_changed_frames"]}/{r["frames"]}; maximum command difference {r["maximum_command_difference"]:.6g}, comparison tolerance 1e-7.')
    if not comparisons:
        causal_zh.append('本批未完成固定外设的连接对照，不能声称已定位内部贡献。')
        causal_en.append('No completed fixed-peripheral connection comparison; internal contribution is not localized by this batch.')
    post = stages[base+'-correction-system-normal']
    zh = f'''# E62：保持同一个意识和运动中枢之后，基础教学怎样了

2026-10-07实验批次；这是有限重试报告，原E61证据及更正保留。研究项目`55e5260f-a406-4aa8-8549-66c4b0aa30e9`。

## 结论先说

**暗换控制器的问题已修复，但修复后这一套单眼、连续教学方案还没有学会可靠的眼手控制。** 空白意识与自己的运动中枢完成156课后，主要独立测试1/12题末时在目标内，且那一题起点已经在目标区；从区外自行进入为0/12。提示一直保留时，出现1次实际从区外指入目标，仍只有1/12题完成。错后继续教同一个系统，再测末时完成{post['end_reached']}/12。没有把教师带动的动作算作学会。

原多视场可用组合没有丢：本轮单独短验6题，选择和实际到达均6/6。它没有被加载到新意识中。这个参考与新系统不止视野一个差别，不能用本轮差距直接断言单眼或ThreeMind理论不可行。

**有一项明确的正结果：纠错后完成的三题，都需要内部连接参与。** 固定运动中枢，静默已有连接后3/12降为0/12；解除静默后恢复3/12，而且960帧命令和身体轨迹与正常组全部一致。因此本组正确动作不是运动外设完全独立完成的；具体记忆内容与局部联想通路尚未定位。

本批止于基础眼手控制，**没有进入新的形色考试，也没有完成学前探索与等时静置的有效比较**。因此不能用这些分数否定形色辨识、学前探索或先前有效的内部活动证据。

## 修正与实际教学

- 完整系统`developmental-system/2`保存Core、队列、读出历史、身体、感官、个人Transformer权重、Adam、教学缓存、随机状态和课程游标。普通阶段不换外设，不单独回滚“最好”的权重。
- 新组从空白Core、随机新外设和新身体开始。共享的是固定物理视网膜单元的读取规则，不是人为裁出的四个对象。外设选择眼与手的位置，伺服执行所选位置；评分答案不进入伺服。
- 先教眼、手、联合动作的四个方向，每个初见连续十课，再分三轮交错复习，间隔2、6、18模拟秒。共156课、{taught['sim_seconds']:.0f}模拟秒，教师样本{taught['examples_seen']}个，原优化器更新{taught['motor_steps']}步。辅助从0.8降到0.2，测试为0。
- 纠错另从教学后的同一完整个体继续：12次自己尝试，其中{corrected['corrected_trials']}题末时失败，逐题再示范三次，辅助0.7→0.4→0.1，接2秒有环境反馈的间隔。原外设累计更新到{corrected['motor_steps']}步，没有重新初始化。
- 身体2kg、阻尼5N·s/m、最大驱动力12N、原风的0.1倍。自身可见手、眼动/手动本体反馈、触觉、玩具声响与物理背景持续存在。Core动力学、默认、旧协议与旧意识不改。

[原流程核查](recovered-workflow.zh.md)明确：E54有独立运动校准；E56成功的共享读取校准在Core形色教学后、正式测试前。没有证据证明E56继承了E54运动头。本轮的“直接”只是不先做无监督学前活动，不是跳过基础校准。

## 无辅助成绩：经过与停留均保留

每组12题，眼看、手指、联合各4题；每题4秒，标准眼误差≤0.075rad、手误差≤0.20m。只看/只指按被要求的器官评分，另一器官仍完整记录；因此主分数不能单独证明能让另一器官保持不动。主要条件光点显示0.75秒；持续提示对照为4秒。眼值按每帧动作前观测、手值按该帧动作后位置，原记录及评分方式均保留，不把50ms内的二者当成精确同一时点。

| 条件 | 末时完成 | 曾进入 | 从区外进入 | 眼平均末误差/rad | 手平均末误差/m |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(tables[0])}

首次主要测试唯一末时成功来自起点已经接近，不算新增目标转移。持续光点使手平均末误差1.010→0.601m，但未使总体可靠，眼误差0.249→0.239rad。它支持继续拆分“看见目标时的控制”和“撤去目标后的保持”，不足以单指某项Core机制。

已见示范的只读诊断：保留256个教师样本，姿态均方误差0.0430，手目标误差中位数0.168m；眼目标误差中位数约0.050rad。这里没有运行或再训练Core，也没有拟合读头。这些是训练缓存成绩，不是独立行为，更不是意图真值。独立闭环明显更差，说明校准精度与连续执行均需继续定位。

**固定活动记录的交叉读取又定位到一项外设问题：继续学新样本后，对旧样本的翻译退化。** 两个时期均是同一个意识、同一个延续训练的运动中枢；仅将保存的活动离线交给前后权重读取，不重新刺激或修改意识。

| 使用的运动中枢权重 | 原教学缓存MSE | 纠错后缓存MSE |
| --- | --- | --- |
| 纠错前 | 0.0430 | 0.3752 |
| 纠错后 | 0.1365 | 0.00553 |

这里旧缓存完全相同，所以0.0430→0.1365确实是外设继续学习后对这批旧样本的翻译退化，不是重跑时意识活动变了。新缓存的大幅拟合改善也真实存在，但不是独立测试成绩。当前缓存按时间保留最近256项；是否需要在同一个外设中更好地保留跨阶段示范、如何跟随意识变化，值得下一步验证。尚未证明缓存策略是唯一原因，不临时修改本轮模型。

## 内部连接对动作的影响

相同完整起点、同一冻结外设、同一问题及环境起点/规则，分别保留已有连接、将已有连接临时静默、再解除静默。行动不同后感官反馈可以自然分叉。Core仍正常塑形，新形成的连接可以工作；这不是永久切断所有未来传播，也不是移除Core。原有读出窗口同样保留。

{chr(10).join(causal_zh)}

动作差异回答“内部连接是否影响控制”；正确性变化另看上表。不能把改变动作自动等同于提高能力，也不能在正常组本就低分时声称已经准确翻译了意识意图。未做局部定位或移植，本批不冒称完成。

用户关于运动中枢的主张已写入[专门记录](control-boundary.zh.md)：意识内部活动提供选择，运动中枢翻译，伺服/驱动/肌肉执行。功能分工合理；目前推理确实只读原始Core输出，但经过Core的直接感官信息仍可能被外设独立识别，不能仅凭通路接线证明全部决定源于学得的内部模式。

## 失败、资源与交付

第一调试分支曾把新教师目标配到尚未收到提示的旧活动上，发现后告知并停止，见[时序更正](timing-correction.zh.md)。修正后的探索组又遇用户压缩任务占用内存，自动停止；按用户要求等待结束后才运行空白直教组。未完成课程不能用于判定学前无效，见[资源记录](resource-interruption.md)。持续提示测试已完成十二题，最终保存遇目录改名权限错误；完整快照和原过程均恢复，未重跑，见[保存恢复](save-recovery.md)。

截至本报告：{len(data['stages'])}个完成阶段，{data['created_or_restored']}次创建/恢复，累计模拟计算{data['total_compute_minutes']:.2f}分钟，包含失败耗时且保存恢复不重复计时。单模拟worker，Transformer实际使用CUDA，Core仍在CPU。配额、磁盘与内存按[登记](design.zh.md)守护；旧数据不删。存储和落库实数见交付清单`delivery.json`。

最后一个事先登记的恢复对照在90分钟停止扩展线之前启动、在91.20分钟完成，之后不再启动模拟。账户使用率实测14%→18%，共享消耗保守计入，达到增加4个百分点的停止扩展线。150分钟、增加6个百分点与4GiB硬限均保留；本批不以剩余硬限继续增加试验。

可复用工具包括完整系统与课程续接、持续学习运动外设、物理伺服、只读校准诊断和完整过程回放。回放包含所有正式教学、纠错、成功及失败测试，明确标出教师辅助；截图/WebM录制按钮沿用现有工具。原始记录与完整快照一并归档。浏览器自动视觉验收受限，未声称已经完成录屏或人工观看验收。[工程检查](verification.md)

## 下一步建议与尚未完成的目标

1. 先把固定、持续可见目标的眼动与保持练稳；逐步引入撤点保持、换目标和手眼联合。仍沿用每一个体自己的外设，不能通过换头掩盖困难。
2. 对同一外设比较已见示范、自己运行时的活动、纠错后的新活动，定位是翻译误差、学习遗忘、活动分布变化还是闭环反馈。当前差距有实测依据，但尚未单独定位。
3. 基础控制过关后再接形色、居中单物体与不规则形状；探索/静置需完整等时对照。第二来源、这些任务及局部移植本批未展开。
4. 保留E56可用组合及其外设贡献限制。新方案的困难不取消旧能力；新组合保持完整也不自动保证学会。

本轮完成的是连续性纠错、必要的基础重试和条件明确的归因检查；可靠单眼注视、眼手协调与形色指认仍未完成。
'''
    en = f'''# E62: basic teaching with one continuing Core and motor peripheral

2026-10-07 study batch. Original E61 evidence and its correction remain. Research project: `55e5260f-a406-4aa8-8549-66c4b0aa30e9`.

## Main result

**Controller replacement is repaired, but this whole-eye continuous-teaching assembly has not learned reliable eye/hand control.** After156 lessons the primary unassisted test finishes within target in1/12 trials, entirely from an already aligned start:0/12 new entries from outside. Keeping the cue visible yields one actual new hand arrival but still1/12 completed trials. Error-contingent teaching of the same whole individual yields{post['end_reached']}/12 endpoints on retest. Assisted demonstrations are not counted as independent success.

The original working E56 assembly still passes6/6 choices and physical arrivals in a short independent recheck. New individuals inherit neither its Core nor peripheral. The assemblies differ beyond field of view; this is not evidence that whole-eye vision or ThreeMind's theory is impossible. New shape/color examinations and a valid matched preschool comparison were not reached.

**A positive causal finding remains: all three post-correction successes require existing internal connections in this fixed-reader test.** Silence changes3/12 to0/12; restoration returns3/12 and every command/body value across960 frames. Those successes were not produced by the peripheral independently of the connections. Specific memory content and local associative pathways have not been isolated.

## What was actually preserved and taught

`developmental-system/2` saves Core, delivery/readout history, body/sensors, personal Transformer, Adam, replay, RNG and curriculum cursor. Normal stages retain the same weights and optimizer, without best-head rollback. Blank Core and random personal peripheral receive156 lessons over{taught['sim_seconds']:.0f}simulated seconds: look, point and combined actions in four directions; each first appears ten consecutive times, followed by interleaved reviews with2/6/18s gaps. There are{taught['examples_seen']}teacher examples and{taught['motor_steps']}optimizer steps. Assistance decreases0.8→0.2 and is zero during evaluation.

Correction continues the same taught individual:12 attempts, with{corrected['corrected_trials']}endpoint failures receiving three demonstrations at0.7/0.4/0.1 assistance and a2s physical interval. The original peripheral reaches{corrected['motor_steps']}updates. Shared physical retinal-cell reading does not crop named objects. The reader selects eye/hand poses; a servo executes those selected poses without consulting scoring answers. The2kg hand,5N·s/m damping,12N actuator and one-tenth original wind are a separate world version. Visible hand, eye/hand proprioception, touch, toy sounds and environmental background remain. Core dynamics/defaults and old instances are unchanged.

[Historical workflow](recovered-workflow.en.md): E54 independently calibrated a motor interface. E56 calibrated its shared reader after Core concept teaching and before evaluation; no evidence establishes inheritance of the E54 head. Here direct teaching omits unsupervised preschool, not basic motor calibration.

## Unassisted behavior

Twelve trials per condition, four each for look/point/both,4s per trial. Registered tolerances remain0.075rad and0.20m. Single-effector tasks score the requested effector; the other remains recorded, so scores do not alone establish independent control. Primary cue duration is0.75s; the supplementary visible-cue condition uses4s. Eye measurements are pre-action observations and hand endpoints follow that50ms action; preserve that original scoring convention rather than claim exact simultaneity.

| Condition | Endpoint | Ever entered | Entry from outside | Mean eye endpoint error/rad | Mean hand endpoint error/m |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(tables[1])}

The primary test's single endpoint success starts already aligned. Continued cue visibility reduces mean hand error1.010→0.601m but does not make control reliable; eye error changes0.249→0.239rad. This motivates separating visible-target control from post-cue retention, without identifying a specific Core defect.

Read-only inspection of256 retained supervised examples gives pose MSE0.0430, median hand-target error0.168m and median eye error approximately0.050rad. Neither Core simulation nor fitting occurred. These are training-cache scores, not held-out behavior or intent truth. Independent closed-loop performance is substantially worse.

Frozen-record cross-reading identifies an adapter issue: continued fitting to new examples degrades translation of earlier examples. With pre-correction weights, MSE is0.0430 on the old cache and0.3752 on the correction cache. Post-correction weights yield0.1365 and0.00553 respectively. The old inputs are literally unchanged, so the old-cache degradation belongs to the adapter update, not a changed Core rerun. New-cache fitting improves, but neither cache is a held-out behavioral test. The current FIFO retains256 recent examples. Better cross-stage retention within the same personal peripheral merits testing, without yet claiming this buffer policy is the sole cause or changing this batch's model.

## Contribution of internal connections

From identical complete starting states, keep the personal reader fixed and compare intact existing edges, temporary silence of those edges and unsilencing before testing. Environmental starting conditions/rules and requests match; sensory feedback can naturally diverge after different actions. New connections may still form; this is not removal of Core or permanent prevention of all future transmission. The original recent activity window is retained.

{chr(10).join(causal_en)}

Changed commands establish an internal causal influence; task benefit must be judged separately from the table. Low intact performance cannot establish accurate intention translation. No local transplantation was performed. [The user's motor-center proposal](control-boundary.en.md) remains the target: internal choice, peripheral translation, physical execution. Raw-Core-only inference is implemented, but direct sensory activity may still permit recognition by the adapter.

## Failures and delivery

An initial pilot paired new teacher targets with preceding pre-prompt activity. It was disclosed, stopped and retained; [timing correction](timing-correction.en.md) defines the new supervision point. A corrected exploration run stopped under external compression-induced memory pressure. Per the user's instruction, new simulation waited until compression finished. Its incomplete teaching cannot evaluate preschool benefit. The visible-cue evaluation completed all twelve trials but encountered a final directory-rename permission error. Its complete snapshot and scores were recovered from original files without rerunning; the original failure remains. See [resource interruption](resource-interruption.md) and [save recovery](save-recovery.md).

This report covers{len(data['stages'])}completed stages,{data['created_or_restored']}creations/restores and{data['total_compute_minutes']:.2f}compute minutes, including failed attempts and counting the recovered case once. One simulation worker, actual CUDA Transformer computation and native CPU Core; memory/disk/account guards remain under the [registration](design.en.md). Storage/publication figures are in `delivery.json`. Historical data are preserved.

The last preregistered rescue began before the90-minute expansion boundary and completed at91.20minutes; no further simulation started. Account usage moved14%→18%, conservatively including shared consumption, reaching the+4point expansion boundary. The150-minute/+6point/4GiB hard limits remain; their remaining room is not used to expand this batch.

Reusable tools provide full-system/curriculum continuation, ongoing personal motor learning, physical servos, read-only calibration and complete recorded replay. All formal teaching, corrections and successful/failed tests are included with assistance provenance and existing PNG/WebM capture controls. Browser visual acceptance and a rendered recording are not claimed. [Engineering verification](verification.md).

## Remaining work

Prioritize reliable visible-target gaze/holding, then cue removal, retargeting and joint movement, always preserving each individual's own peripheral. Compare supervised, independently encountered and post-correction activity to localize translation error, forgetting or closed-loop distribution change; none is isolated yet. Only then expand shape/color, centered objects and deformed shapes. Matched preschool controls, the second source and localized transplantation remain unperformed. Keep E56's working result and its adapter-contribution qualification. Repairing continuity does not by itself guarantee learning, and this new failure does not erase earlier abilities.
'''
    zh += '\n\n## 同日补充：新旧示范共同复习\n\n用户建议每次纠错后同时强化此前正确的翻译。采纳为下一批R41：在同一个外设里配平训练步数及缓存容量，比较最近样本与历史混合复习；不把测试题答案纳入训练，不重置外设、不改Core遗忘。本批已到停止扩展线，因此未追加训练。与中央单物体诊断一起推进。[具体计划](../../../docs/zh/plans/motor-rehearsal.md)。\n'
    en += '\n\n## Same-day follow-up: rehearse old and new demonstrations\n\nThe user proposed strengthening earlier correct translations alongside corrections. Accepted as next-batch R41: compare recent-only and historical mixed rehearsal within the same peripheral, matching update counts and capacity. Exclude held-out answers; no head reset or Core-forgetting change. No additional training was added beyond this batch\'s expansion boundary. Coordinate with centered-object diagnosis. [Plan](../../../docs/en/plans/motor-rehearsal.md).\n'
    for lang, body in [('zh',zh),('en',en)]:
        with (HERE/f'report.{lang}.md').open('x',encoding='utf-8') as f:f.write(body)
    data['calibration_checks'] = {name:json.loads((WORK/name).read_text(encoding='utf-8')) for name in
        ('motor-calibration.json','motor-calibration-after-correction.json','calibration-transfer.json')}
    with (HERE/'results.json').open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    print(json.dumps({'reports':['report.zh.md','report.en.md'],'compute_minutes':data['total_compute_minutes']}))


if __name__ == '__main__':main()
