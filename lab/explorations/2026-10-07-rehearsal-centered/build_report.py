"""Render bilingual measured-result tables, then leave explicit interpretations."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
motor=['| Policy | Real new arrivals /12 | Endpoint /12 | Old fixed error before → after | Fresh teacher error |',
       '| --- | --- | --- | --- | --- |']
labels={'recent':'最近缓存 / recent','reservoir':'随机历史 / reservoir','representative':'旧代表＋近期 / representative'}
for name,m in r['motor'].items():
    b=m['behavior'] or {}
    motor.append(f'| {labels[name]} | {b.get("new_arrivals","未测")} | {b.get("end_reached","未测")} | {m["old_mse_before"]:.5f} → {m["old_mse_after"]:.5f} | {m["fresh_teacher_MSE"]:.5f} |')
recognition=['| Condition | Total /32 | Shape /16 | Color /16 | Taught basic /8 | New combinations /24 |',
             '| --- | --- | --- | --- | --- | --- |']
conditions={'centered-normal':'首轮 / Initial',
    'centered-variant-normal':'首轮＋相同新题序/位移 / Initial, matched changed test',
    'centered-corrected-normal':'纠错＋旧知识复习 / Correction and reviews',
    'centered-calibrated-normal':'整段提问＋集中校准 / Whole question and calibration',
    'centered-calibrated-silence':'校准后固定读头、既有边静默 / Calibrated, edge silence',
    'centered-calibrated-rescue':'校准后固定读头、解除静默 / Calibrated, rescue'}
for name,x in r['recognition'].items():
    recognition.append(f'| {conditions.get(name,name)} | {x["correct"]} | {x["shape_correct"]} | {x["color_correct"]} | {x["basic_correct"]} | {x["combination_correct"]} |')
for language in ('zh','en'):
    title='# E63：纠错复习与中央单物体认识' if language=='zh' else '# E63: rehearsal and centered-object recognition'
    intro=('2026-10-07登记，执行跨至10月8日（北京时间）。实验对象是完整意识＋自己的外设。首先看实际答对和动作成功，拟合误差仅用于解释。Core动力学、默认及旧证据不改。以下数字来自已保存过程，解释与待办另列。'
           if language=='zh' else 'Registered October 7, execution continued into October 8, 2026 (Asia/Shanghai). The subject is a complete Core with its own peripheral. Actual correct answers and actions take priority; fit error is diagnostic only. Core dynamics, defaults and old evidence remain unchanged. These tables derive from saved records; interpretation and follow-ups are separated.')
    blocks=[title,intro,'## 纠错复习 / Rehearsal','\n'.join(motor),
        ('各组增加936次Adam更新，缓存容量都是256。旧误差来自完全相同的旧活动；新示范误差来自各组真实闭环形成的36个最新教师窗口，输入随行为不同，不能称为共同测试集。末时到达不等于主动到达，起点已在范围内的单列。样本误差是姿态均方误差，非意识指标。'
         if language=='zh' else 'Each policy adds936 Adam updates with capacity256. Old error uses identical fixed activity. Fresh error uses36 final teacher windows from each actual closed-loop trajectory, so it is not a common input test set. Endpoint success differs from a new arrival. These are pose MSEs, not consciousness measures.'),
        '## 单物体认识 / Centered recognition','\n'.join(recognition),
        ('固定眼手是装置条件，排除了扫视/协调任务，未改变原整幅感官转换。教学先每句10次，再交错3轮复习。问句不含答案；输出限于4形状＋4颜色。正式试题答案不用于训练；纠错只针对基础练习题，纠错后另用轻微位移和新顺序提问。不能把受限词表分类称为自由语言或关系推理。'
         if language=='zh' else 'A fixed physical eye/hand removes search and coordination without changing whole-retina conversion. Each statement first repeats10times, followed by3 interleaved reviews. Questions contain no answers; output is restricted to4 shapes and4 colors. Tests are excluded from training; corrective practice uses basic examples, with small displacement/new order in post-correction tests. This is not unrestricted language or relational reasoning.'),
        ('集中校准分支在采样44.45墙钟秒后按用户要求停止，尚无完成的拟合或校准结果。原计划的48次采样、1200步校准不能写成已执行。先从空白重试，只有新空白有效后再考虑原个体；后续结果归入E64，不改写本批证据。'
         if language=='zh' else 'The calibration branch stopped at the user request after44.45wall seconds of sampling. No completed fit or calibration result exists. Its planned48samples/1200updates are not performed results. A blank restart takes priority; any later old-subject continuation belongs toE64 and does not rewrite this evidence.'),
        ('本批未执行集中校准后的交叉读法、静默、恢复或空白Core移植，不能据此提出机制归因。具体计划保留，不将未做项计成完成。'
         if language=='zh' else 'Post-calibration cross-reading, silence, rescue and blank-Core transplant were not performed in this batch. Their plans remain; no mechanism attribution is claimed from unexecuted controls.'),
        '## 资源与原证据 / Resources and evidence',
        f'累计计算 {r["compute_minutes"]:.2f} minutes; creations/restores {r["instances"]["created"]}. Failed stages are counted once, not omitted.',
        '[执行登记 / Registration](design.'+language+'.md) · [B阶段预登记 / B criteria](recognition-preregistration.md) · [校准登记 / Calibration](question-calibration-preregistration.md) · [顺序决定 / Decisions](execution-decisions.md) · [操作 / Commands](README.md) · [摘要异常 / Console correction](console-correction.md)',
        '完整逐帧记录、各阶段完整系统与失败记录保留；回放包括成功与失败。No original data overwrite, best-checkpoint rollback or baseline subtraction.']
    with (HERE/f'report.{language}.md').open('x',encoding='utf-8') as f:f.write('\n\n'.join(blocks)+'\n')
print('Bilingual measured report tables created; append result interpretation before delivery.')
