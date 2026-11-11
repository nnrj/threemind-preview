"""Write final bilingual E66 reports from audited results and packed replay."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
WORK=ROOT/'.work/centered-correction-cycles-20261008'
read=lambda p:json.loads(p.read_bytes())
frac=lambda d:f"{d['correct']}/{d['n']}"


def main():
    r=read(HERE/'results.json');c=r['completion'];m=read(HERE/'replay-manifest.json')
    n=c['rounds'];cases=r['cases'];last=r['scores'][c['final_case']]
    ret=r['retention_retest']
    if not ret:raise RuntimeError('registered retention supplement must be handled before final reports')
    devrows=[];finalrows=[];fitrows=[];teachrows=[]
    for i in range(n+1):
        s=r['scores'][f'development-{i}']
        devrows.append(f"| {i} | {frac(s)} | {frac(s['shape'])} | {frac(s['color'])} | {frac(s['combinations'])} |")
    for i in range(n+1):
        key=f'confirmation-{i}'
        if key not in r['scores']:continue
        s=r['scores'][key];status='final held-out / 最终留出' if key==c['final_case'] else 'later development / 后转开发'
        for side in ('0','1'):
            a=s['sides'][side]
            finalrows.append(f"| {i} / {int(side)+1} | {frac(a)} | {frac(a['shape'])} | {frac(a['color'])} | {frac(a['combinations'])} | {status} |")
    for key in ['initial-fit']+[f'fit-{i}' for i in range(1,n+1)]:
        a=cases[key];fitrows.append(f"| {key} | {a['training_correct']}/{a['n']} | {a['loss']:.8f} | {a['computed_updates']} | {a['committed_updates']} |")
    for key,a in r['teaching'].items():
        teachrows.append(f"| {key} | {a['lessons']} | {a['feedback_events']} | {frac(a['current_reanswers'])} | {a['immediate_correct_teacher_feedback']} |")
    devtable='\n'.join(devrows);finaltable='\n'.join(finalrows);fittable='\n'.join(fitrows);teachtable='\n'.join(teachrows)
    base=r['scores']['development-0'];finaldev=r['scores'][f'development-{n}'];paired=r['baseline_to_final_development']
    err=ret['groups']['previous-error'];contrast=ret['groups']['confusable-contrast']
    fit=cases[Path(c['final_source']).parent.name];life=fit['core_time_us']/1e6
    feedback=r['process_audit']['verified_immediate_feedback_pairs'];lessons=sum(v['lessons'] for v in r['teaching'].values())
    wrong=[];words=('球体','圆柱体','立方体','圆锥体');colors=('红色','黄色','蓝色','绿色','灰色')
    for t in last['wrong']:wrong.append(f"| {t['side']+1} | {colors[t['color']]}{words[t['shape']]} | {t['attribute']} | {t['word']} |")
    wrongtable='最后两套新位置题均无错误。 / No errors in either final position.' if not wrong else '| 位置 / Position | 对象 / Object | 属性 / Attribute | 实际回答 / Answer |\n| --- | --- | --- | --- |\n'+'\n'.join(wrong)
    teaching_paths='、'.join(f'correction-{i}' for i in range(1,n+1))
    lead_zh=f'从新的完整空白个体开始，完成 {n} 轮纠错、强化、复习及外设续校。固定开发题 {frac(base)} → {frac(finaldev)}；最后两套新位置确认 {frac(last)}，旧确认错题结项复查 {frac(err)}，易混对照 {frac(contrast)}。'
    lead_en=f'One new blank complete subject completed {n} correction/reinforcement/review/calibration rounds. Fixed development: {frac(base)} → {frac(finaldev)}. Last fresh-position confirmation: {frac(last)}; later-registered old-error retention: {frac(err)}, confusable contrasts: {frac(contrast)}.'
    zh=f"""# E66：空白起点多轮纠错的实测结果

[English](report.en.md) · [原登记](design.zh.md) · [后补复查登记](retention-check.zh.md) · [验证](verification.md) · [交接](HANDOFF.md) · [训练规约](../../../docs/zh/training-protocol.md)

2026-10-08，北京时间。**{lead_zh}** 原计划最多三轮，停止原因记录为 `{c['stop_reason']}`。开发检查与最终留出、后补诊断分别报告，不把不同位置的两次确认当作同题配对改善。

## 1. 同一题组的变化

开发题固定为两个位置各36题：四灰形状，16种彩色形状各问形状、颜色。第0轮是初教及初校准后、纠错前。组合要求同一来源分别回答两属性都对，并非一次同时输出两词。

| 纠错轮数 | 全部属性题 | 形状 | 颜色 | 形色两问均对 |
| --- | ---: | ---: | ---: | ---: |
{devtable}

起点到最终开发题逐题比较：{paired['wrong_to_correct']}题错变对，{paired['correct_to_wrong']}题对变错，{paired['remained_wrong']}题仍错，{paired['remained_correct']}题保持正确。第一轮19道原错题全部改正，原正确53题全部保持；后续变化见各轮原始预测及本目录 `results.json`。

## 2. 各次新位置确认

| 轮次 / 位置 | 全部 | 形状 | 颜色 | 形色两问均对 | 证据角色 |
| --- | ---: | ---: | ---: | ---: | --- |
{finaltable}

每一轮使用事先保留的新位置；早期确认出错后，原分数封存并明确转为下一轮开发材料。不同轮次的确认位置不同，不能直接用分数差估计同题纠错收益。最后一次确认的两个位置未进入教学或任何外设拟合。四形状在全部20个登记位置的保守投影包围盒均位于中央清晰区，最大绝对光学边界0.06264044，小于中央半宽0.075；眼手命令全部为零。

{wrongtable}

## 3. 教师确实纠正了什么

| 阶段 | 示范课数 | 错题重答数 | 重答时已正确 | 紧随的正确示范数 |
| --- | ---: | ---: | ---: | ---: |
{teachtable}

共{lessons}课，{feedback}次错题重答后都有紧接的普通正确陈述。第一轮针对19道错误、11个对象—属性类型；160课、283模拟秒。第二轮针对第一次确认的4道立方体形状错误：黄色两位置、绿色及灰色各一位置，均曾答成圆柱体；121课、209.5秒。第三轮针对第二次确认的3道立方体形状错误：一位置的红色、黄色及另一位置的蓝色；120课、207秒。每轮另有同形换色、同色换形及另一属性等相似例，并复习全部36类内容。

初教保留E64的104课/180秒。初次连续示范每1.5秒一次，后两次复习同概念的起点间隔18、30秒；纠错轮完整36类复习的对应间隔60、72秒。实际时间包含穿插课程，逐条起止和全部实际间隔保存在原始课表及 `teaching-intervals.json`。这是先密后疏，没有声称匹配人类艾宾浩斯曲线。

## 4. 旧确认错题的结项复查

09:48后补登记，主循环完成后才执行：把已用于纠错的旧确认错误和同位置易混对照，用最终完整来源独立重问。题库按预先声明的规则冻结，最多24题；最终未训练确认题不纳入此诊断。该补查不用于选模型或追加训练，原主循环及停止条件不变。

旧错误 {frac(err)}，对照 {frac(contrast)}；对照原成绩 {contrast['original_correct']}/{contrast['n']}。仍有{err['n']-err['correct']}道旧错题未改正，不能用固定开发题72/72代替原错题原条件的复查。全部逐题结果在 `cases/retention-retest/predictions.json`。这是已见开发题的保持信息，不能冒称新的留出泛化证据。

## 5. 外设校准与完整连续性

| 阶段 | 固定校准记录正确数 | 最低训练损失 | 累计计算步 | 保留状态步数 |
| --- | ---: | ---: | ---: | ---: |
{fittable}

从零建立 `e66-blank-223`，Core continuous-memory/2 seed223，视觉/文本seed91，自出生绑定自己的八词外设。出生快照时钟和学习步数均为0；没有复制E64/E65的已学状态。同一出生种子是方法复用，不是新的独立随机种子验证。

每轮从教学后完整来源采真实、无答案的1秒问题，取20步中首末跨度的8帧原始活动。自己的权重、Adam和采样随机状态延续，所有旧校准记录与新72条共同使用。外设校准不推进Core/身体，选点只依据训练损失，保留匹配的优化器/RNG；计算步数与保留步数不同。现场教学期间外设权重未变。推理只收声明的Core原始活动，不接真值或场景类别。

完整主线包含Core、队列/时钟、身体/世界、映射、当前及近期活动、课程位置、自己的外设与学习状态。下一输入/活动/Core及下一权重/Adam/RNG恢复一致验证通过；逐字段核查所有续校前后物理/Core/近期状态不变。最后主线时间{life:g}模拟秒，来源 `{c['final_source']}`。逐题评估副本不写回主线，恢复次数不是独立训练个体数。

## 6. 解释边界及下一步

反复纠正、类似题复习、扩大校准覆盖并继续训练的整体流程，明显改善了本个体的固定开发题。教学经历、校准覆盖、外设续校和经过时间共同变化，尚不能把全部收益单独归因于某一项或Core概念学习。新位置确认及旧错误复查按各自范围解释；未检验新形状类别、长期保持、自由场景、眼动控制、第二训练来源或连接因果贡献。

对第一轮4个立方体错误的只读核查发现，同色同位置圆柱体与立方体的视网膜输入及八帧Core活动均不相同。差异存在不等于已经可被当前读取器稳定使用，也没有单独定位错误原因。结果保存在 `recorded-shape-differences.json`，可用 `diagnose.py` 复核；没有新增模拟或训练。

本批每轮外设新增校准位置始终是 `(.006,-.006)` 和 `(-.006,.006)`。教师在主线呈现并纠正了较远的新位置错题，但没有把那些位置在教学后的真实问答活动另采入外设续校。因而剩余错误仍可能涉及读取器对位置变化的适配；目前没有匹配对照来确定这是否为主因。后续可将已转为开发的错题和相似位置重新采样用于个人外设续校，并另留新题检验。这是后续建议，未在本批执行。E66执行的是冻结的规约v2，后来追加的v2.1明确条件覆盖和原错题复查，没有倒改本次实验。

具体艾宾浩斯曲线排程对照尚未执行。后续应固定曲线/排程算法及模型时间单位，配平教学次数、刺激剂量、总时长与末次接触至测试的延迟，再比较多个保持延迟；文献曲线和模型实测保持曲线须分开。此次一般先密后疏结果不能证明曲线匹配更好。

## 7. 证据与交付

{len(cases)}个完成阶段，{len(r['failures'])}个中止记录；{r['instances']['created']}次完整创建/恢复，一个训练来源，累计计算{r['compute_minutes']:.2f}分钟，含独立评估、保存恢复和后补复查。全程{m['clips']}段、{m['frames']}帧，{len(m['chapters'])}个回放章节，保留全部错误、教师示范、复习、校准和测试。

工作目录 `.work/centered-correction-cycles-20261008`；回放入口 `replays/index.html`；本地研究项目 `2bece525-31f1-4df8-93cf-cb3bd8dc9132`。完整快照、冻结源码/设计、原始活动、选择记录及中英报告归档；交付信息记录于本目录 `delivery.json`。E63停止文件、E64原门槛、旧实验、Core/default保持原位。
"""
    en=f"""# E66: measured blank-start correction-cycle results

[中文](report.zh.md) · [Original registration](design.en.md) · [Retention addendum](retention-check.en.md) · [Verification](verification.md) · [Handoff](HANDOFF.md) · [Training protocol](../../../docs/en/training-protocol.md)

October 8, 2026, Beijing time. **{lead_en}** The original maximum was three rounds; recorded stop reason: `{c['stop_reason']}`. Fixed development, final held-out confirmation and the later diagnostic have separate roles. Scores from different confirmation positions are not matched before/after effects.

## 1. Fixed development bank

Each position has36questions: four gray shapes and both attributes of all16colored shapes. Round0 follows initial teaching/calibration and precedes correction. A conjunction requires two independently restored attribute answers to be correct, not one simultaneous two-word response.

| Correction rounds | All attributes | Shape | Color | Both attributes correct |
| --- | ---: | ---: | ---: | ---: |
{devtable}

Baseline to final development: {paired['wrong_to_correct']}wrong-to-correct, {paired['correct_to_wrong']}correct-to-wrong, {paired['remained_wrong']}persistent failures and {paired['remained_correct']}retained successes. Round one corrected all19baseline errors and retained all53successes. Full per-round predictions and `results.json` preserve subsequent changes.

## 2. Fresh-position confirmations

| Round / position | All | Shape | Color | Both attributes | Evidence role |
| --- | ---: | ---: | ---: | ---: | --- |
{finaltable}

Each round uses a different reserved pair of positions. Failed early confirmation results are sealed, then explicitly reclassified as development for teaching. Cross-round confirmation differences are not paired gains. The last confirmation positions occur in neither teaching nor fitting. Conservative bounding-box projections for all four shapes at20positions remain inside the original clear center: maximum absolute coordinate0.06264044 versus half-width0.075. Every recorded eye/hand command is zero.

{wrongtable}

## 3. Actual teacher feedback and review

| Stage | Demonstrations | Failed-question reanswers | Already correct on reanswer | Immediate correct demonstrations |
| --- | ---: | ---: | ---: | ---: |
{teachtable}

There are {lessons} demonstrations and {feedback} failed-question reanswers immediately followed by ordinary correct sensory statements. Round one covers 19 failed questions/11 types, 160 lessons and 283 simulated seconds. Round two covers four first-confirmation cube-shape errors: yellow at both positions, green and gray at one position, all previously answered cylinder; 121 lessons/209.5 seconds. Round three covers three second-confirmation cube errors: red/yellow at one position and blue at the other; 120 lessons/207 seconds. Every round includes one-factor neighbors and rehearsal of the complete 36-type grid.

Initial teaching retains E64's104lessons/180seconds. Concentrated demonstrations recur every1.5seconds; the last two initial review start intervals are18and30seconds. Full correction-round reviews recur at60and72seconds for the same type. Interleaved lessons count toward these intervals. Raw timing and `teaching-intervals.json` retain actual times. This is dense-to-sparse practice, not a fitted human Ebbinghaus schedule.

## 4. Later-registered retention diagnostic

Registered at09:48 and executed only after the original loop: restore final complete copies to re-answer all previously reclassified confirmation failures plus matched confusable contrasts, under a24-question cap. Freeze the bank by the declared rule before answering, exclude the final never-trained bank, and do not use this diagnostic for model selection or further fitting.

Old errors: {frac(err)}. Contrasts: {frac(contrast)}, originally {contrast['original_correct']}/{contrast['n']}. There are {err['n']-err['correct']} persistent old errors, so 72/72 on the fixed development bank cannot replace exact-condition retesting. Full rows are in `cases/retention-retest/predictions.json`. These are exposed development examples, not fresh generalization evidence.

## 5. Calibration and complete continuity

| Stage | Correct fixed calibration records | Minimum training loss | Computed updates | Committed-state updates |
| --- | ---: | ---: | ---: | ---: |
{fittable}

Create `e66-blank-223` from zero: continuous-memory/2,Core223,sensory/text91, its own untrained eight-word peripheral at birth. The birth clock and update count are zero. No learned E64/E65 state is imported; reuse of a birth seed is not an independent-seed replication.

Questions last1second/20ticks with eight samples spanning the whole answer-free query. Continue personal weights,Adam and RNG on all earlier calibration records plus72new records per round. Offline calibration leaves Core/body unchanged; minimum training loss selects matching weights/optimizer/RNG, explaining computed versus committed counters. Teaching leaves peripheral weights unchanged. Inference receives only declared raw Core activity, with no truth or scene-category input.

Preserve Core,queues/clocks,body/world,mappings,current/recent activity,lesson cursor and personal learning state. Isolated next-input/activity/Core and next-weight/Adam/RNG restoration agree. Every fit preserves complete physical/Core/recent state field by field. Final mainline age is{life:g}simulated seconds, at `{c['final_source']}`. Independent evaluation copies do not write back and are not independent trained subjects.

## 6. Interpretation and remaining work

The combined package of feedback,similar-example/old-example rehearsal,broader calibration and continued fitting improves this subject's fixed development answers. Teaching,coverage,fitting and elapsed time change together; no single component or Core concept-learning contribution is isolated. Interpret fresh confirmations and exposed-error retention within their respective scopes. New shape classes,long-term retention,free scenes,eye control,a second training source and connection attribution remain untested.

Read-only comparison of the four first-confirmation cube failures with matched same-color/position cylinders finds distinct retinal input and distinct sampled Core activity in every pair. Distinctness does not establish sufficient discriminability or identify the failure mechanism. `recorded-shape-differences.json` and `diagnose.py` preserve this comparison; it adds no simulation or learning.

New peripheral-calibration positions remain fixed at `(.006,-.006)` and `(-.006,.006)` each round. The continuous subject experiences teacher correction at farther failed positions, but post-teaching question activity at those positions is not added to peripheral fitting. Residual errors may therefore involve reader adaptation to position changes; no matched comparison identifies this as the cause. A later study could recollect already-reclassified failures and nearby examples for personal calibration, with fresh final questions. This proposal was not executed here. E66 used the frozen protocol v2; subsequent v2.1 guidance records coverage checks and exact-condition error retesting without changing this experiment.

The explicit Ebbinghaus-based schedule comparison is unexecuted. A later design should specify its curve/algorithm and model-time units,match demonstration counts,stimulus dose,total duration and recency,and measure several retention delays. Distinguish a literature curve from this model's fitted retention curve. General increasing-spacing results do not show that curve matching is better.

## 7. Evidence

{len(cases)}completed stages,{len(r['failures'])}stopped records,{r['instances']['created']}complete creations/restores,one trained source,{r['compute_minutes']:.2f}aggregate compute minutes including evaluation,restoration and the supplement. Replay preserves all{m['clips']}clips/{m['frames']}frames in{len(m['chapters'])}chapters, including every success,failure,teacher statement,review,calibration and test.

Workspace: `.work/centered-correction-cycles-20261008`; replay entry:`replays/index.html`; local Lab project:`2bece525-31f1-4df8-93cf-cb3bd8dc9132`. Complete snapshots,frozen source/design,raw activity,selection records and bilingual reports are archived; `delivery.json` records publication details. E63 STOP,E64 historical gates,old experiments and Core/defaults remain intact.
"""
    for lang,text in [('zh',zh),('en',en)]:
        with (HERE/f'report.{lang}.md').open('x',encoding='utf-8') as f:f.write(text)
    verification=f"""# E66 verification / 验证记录

2026-10-08，北京时间；[实测报告](report.zh.md)与工具验证分开。

开跑前检查通过：初教104课/180秒、初校48题、开发题72题、20个位置互相隔离的用途、完整36类覆盖、无答案问句及纠错/相似题生成规则。四种形状各20位置的保守包围盒投影共80例，最大0.0626404340439525 < 0.075。出生配置与保存的E56 Core/text配置一致；出生time_us=0，外设updates=0。开跑前修正过纯检查中的位置计数常量22→20，未产生刺激或试验数据。

本批CUDA完整恢复检查通过：下一输入/原始活动/Core状态完全一致，同一材料的下一权重/Adam/RNG更新完全一致。验证副本未写回主线。所有教学前后外设权重文件相同；所有拟合前后Core、身体/世界、队列/时钟、当前与近期历史、映射和课程位置逐字段相同。原E56配置参照仍与拷贝一致。

审计逐条评分满足selected==label，所有开发/确认题覆盖16搭配两属性及四灰形状，固定开发题ID逐轮一致。{feedback}次错误重答后，下一个记录均为同题正确示范，教师开始时刻等于重答结束时刻；示范1.5秒、问句1秒，课表时长与实际主线一致。全部{r['process_audit']['total_frames']}帧具有正确世界版本、空教师标记，眼手命令最大绝对值为0。最终留出位置与全部实际教学和外设校准位置无交集。

原始分数：开发{frac(base)}→{frac(finaldev)}，最后确认{frac(last)}。结项旧错误复查{frac(err)}，易混对照{frac(contrast)}，有09:48的后补登记，单列开发诊断。所有阶段的失败或旧分数原位保留。

回放{m['clips']}段/{m['frames']}帧，与全部原始过程一致；分{len(m['chapters'])}章，合计{m['bytes']}字节。播放器仅读取记录，不模拟或补画轨迹。`diagnose.py`复核的是第一轮既有错题与易混形状的感官/活动差异，不是新增机制试验。

{len(cases)}完成阶段、{len(r['failures'])}中止记录、{r['instances']['created']}次完整创建/恢复、{r['compute_minutes']:.6f}计算分钟；一个训练来源。原预算未提高，实际账户读数保存在usage-readings.jsonl，属于共享账户；不能把全部账户或数据库增长独占归于本批。

源文件语法、回放脚本、文档链接和史书检查以及发布读回结果，在交付检查完成后追加。未声称浏览器人工视觉验收或新录制视频。
"""
    with (HERE/'verification.md').open('x',encoding='utf-8') as f:f.write(verification)
    with (HERE/'HANDOFF.md').open('a',encoding='utf-8') as f:
        f.write(f"\n## 本批完成状态\n\n完成{n}轮，最后主线`{c['final_source']}`，{life:g}模拟秒；开发{frac(base)}→{frac(finaldev)}，最后确认{frac(last)}，旧错题复查{frac(err)}，易混对照{frac(contrast)}。停止原因`{c['stop_reason']}`。全部执行后结项；追加实验、修改外设/控制路径或Core仍需新的明确方案。原始证据、具体范围和待验证项见报告。\n")
    print(json.dumps(dict(rounds=n,development=frac(finaldev),confirmation=frac(last),retention=frac(err),contrasts=frac(contrast)),ensure_ascii=False))


if __name__=='__main__':main()
