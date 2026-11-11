"""Build bilingual tables from receipts; interpretation is reviewed before publication."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    data = json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    activity = json.loads((HERE/'activity-results.json').read_text(encoding='utf-8'))
    tables = {}
    arms = {'zh': {'feedback': '共同学习＋自听', 'no-feedback': '共同学习，不自听', 'no-core-learning': '关内核学习，外设照学'},
            'en': {'feedback': 'Joint + self-hearing', 'no-feedback': 'Joint, no self-hearing', 'no-core-learning': 'Core plasticity off, adapter learns'}}
    for lang in ('zh', 'en'):
        zh = lang == 'zh'
        header = '| 来源 | 组别 | 阶段 | 教学现场实际回答 | 事后教学拟合 | 独立提问 | 冻结基础表达器 |' if zh else '| Source | Arm | Stage | Actual live answers | Retrospective teaching fit | Independent questions | Frozen initial adapter |'
        rows = [header, '| --- | --- | --- | --- | --- | --- | --- |']
        for source in sorted(data['sources'], key=lambda x: (x['seed'], x['arm'], x['stage'])):
            group = [r for r in data['tests'] if r['item'] >= 0 and all(r[k] == source[k] for k in ('seed', 'arm', 'stage'))]
            score = sum(r['output'] == r['target'] for r in group)
            frozen = sum(r['frozen_output'] == r['target'] for r in group)
            rows.append(f"| {source['seed']} | {arms[lang][source['arm']]} | {source['stage']} | {source['live_correct']}/8 | {source['teaching_fit']}/8 | {score}/{len(group)} | {frozen}/{len(group)} |")
        tables[lang] = '\n'.join(rows)
    strict = ['| Source / 来源 | Stage / 阶段 | Word transcription fit / 转写拟合 | Actual naming / 实际命名 | Frozen transcriber / 冻结转写器 |',
              '| --- | --- | --- | --- | --- |']
    for row in data['transcription']:
        for arm in ('feedback', 'no-feedback', 'no-core-learning'):
            tests = [r for r in row['rows'] if r['item'] >= 0 and r.get('source_arm', 'feedback') == arm]
            strict.append(f"| {row['seed']} / {arm} | {row['stage']} | {row['fit_correct']}/8 | {sum(r['adaptive_output']==r['target'] for r in tests)}/{len(tests)} | {sum(r['frozen_output']==r['target'] for r in tests)}/{len(tests)} |")
    aligned = ['| Source / 来源 | Calibration fit / 校准拟合 | Original head / 原表达器 | Same-checkpoint calibration / 同快照校准 |',
               '| --- | --- | --- | --- |']
    for row in data['aligned_calibration']:
        tests = [r for r in data['aligned_tests'] if r['seed'] == row['seed']]
        aligned.append(f"| {row['seed']} | {row['fit_correct']}/8 | {sum(r['original_output']==r['target'] for r in tests)}/{len(tests)} | {sum(r['output']==r['target'] for r in tests)}/{len(tests)} |")
    linear = ['| 来源 / Source | 转写拟合 / Fit | 新强度听词：线性 / Heard: linear | 同一测试：Transformer | 问答主组 / Main questions | 不自听 / No self-hearing | 关可塑性 / Core plasticity off |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for row in data['linear_transcription']:
        scores = []
        for arm in ('feedback', 'no-feedback', 'no-core-learning'):
            tests = [r for r in row['rows'] if r['arm'] == arm and r['item'] >= 0]
            scores.append(f"{sum(r['output']==r['target'] for r in tests)}/{len(tests)}")
        heard = row['heard_tests']
        linear.append(f"| {row['seed']} | {row['fit_correct']}/8 | {sum(r['output']==r['target'] for r in heard)}/4 | {sum(r['transformer_output']==r['target'] for r in heard)}/4 | "+' | '.join(scores)+' |')
    no_cue = ['| Source / 来源 | Arm / 组别 | Stage / 阶段 | Actual words / 原话 | Association-positive samples / 联想字段非零采样 |',
              '| --- | --- | --- | --- | --- |']
    for row in activity['records']:
        if row['item'] < 0:
            no_cue.append(f"| {row['seed']} | {row['arm']} | {row['stage']} | {row['output'] or '∅'} | {row['nonzero_associative_samples']}/{row['samples']} |")
    totals = {'copies': data['source_probe_count'], 'receipts': data['cases'],
              'minutes': round(data['aggregate_seconds']/60, 2),
              'comparisons': len(activity['comparisons']),
              'different': sum(r['raw_max_absolute_difference'] > 0 for r in activity['comparisons']),
              'collapsed': sum(r['raw_max_absolute_difference'] > 0 and r['same_expression'] for r in activity['comparisons'])}
    for lang in ('zh', 'en'):
        if lang == 'zh':
            body = f'''# E52：读出听词信息的缺口已定位，联想翻译仍未解决

2026-10-05。[English](report.en.md) · [设计及分期补充](design.zh.md) · [实际问题和回答](../../../.work/coadaptive-language-20261005/outputs.html) · [结构化结果](results.json)

本轮把**个体表达器持续学习、保留教学记录、听见自己实际输出、接受教师纠正**的流程真正接通并跑了对照。它仍是外设，Core动力学、默认参数和输入映射均未修改。

最明确的新定位是：**同一批原始活动，线性转写器在两个来源分别读对4/4个未训练强度的实际听词测试，原Transformer分别只有1/4。** 这部分信息已经在外设拿到的数据里，不能归咎于Core没有响应。不过，仅识别听词的转写器仍不能可靠翻译问后联想；下面分开列出。

**“一个不断学习的外设”已经实现；“只把ThreeMind已经形成的内容忠实翻译出来”尚未完成。** 教学拟合与课后提问明显分离，关内核学习的外设也能学会教学样本。不能把外设自己的答题能力记在Core名下；同样，不能因这个外设失准就断言Core中没有信息。旧E50的命名、通路屏蔽与移植证据保持原结论和适用条件。

## 怎样执行

两个来源，每个比较自听、不自听、关Core可塑性三组，共六条持续教学轨迹。每条分三阶段：0先教两个球；1加两个盒；2交换两球的名字，盒名不变。红色和蓝色各有球、盒，以不同语句交叉限定所指，而不是只变观察角度。

例句包括“这个红球叫甲。”“甲是红色的。”“甲是球。”“与红盒同色的球叫甲。”。每条首次连续10遍，再有2/4秒间隔复习。每阶段另有八轮问答教学，表达器每四条更新一次。原始回答包括错词也可经原感官返回，之后教师通过正常文本示范。外设监督来自教师，不进入测试输入；测试只看原始局部活动过程，没有减去无提示副本或按答案选节点。

核心区别：原共同学习组将**问后、回答前的活动**与教师随后给出的正确词配对训练。这可能教会外设自己答题，所以按用户补充，另做只教词语转写、从不给物体—名字答案的严格对照。

## 共同学习的结果

{tables[lang]}

阶段0是两名字判断，始终说一个名字可得4/8；后两阶段四名字均衡，始终说一个名字可得4/16。这是直观参照，不是假设独立同分布后的显著性检验。每道题来自副本，同源题不能当作独立意识。两来源、三组的具体结果都列出，没有只选成功题。

“教学现场实际回答”发生在当轮教师示范及训练更新之前；阶段0的前四次因表达器未校准而静默，也计入8轮分母。它与训练结束后重读旧样本的“拟合”是两件不同的事。

冻结基础外设未学过新增物体名称，其列用于比较后续适配，不是公平的同知识考试。自听组增加真实文本输入，因此它与不自听组的差异也包含额外曝光，不能自动全部归因于“闭环”。

“关内核学习”具体是从空白开始设置`plasticity=false`；仍保留瞬时激活、抑制和触达历史，并不是删除所有状态。该开关同时停用部分结构遗忘更新，故不能把它称为只删除一种生物学习过程。源阶段配置已检查，除了已登记的种子和此开关之外相同。

外设回放按样本等权，不代表历史上四个物体曝光数相等：前两个先学，后两个后加。这是本次持续学习课程的实际边界；同快照校准新增部分每物体两例，但旧回放仍保留该不均衡。不能把本轮结果全归因于“共同学习”这一个因素。

## 不教任务答案，只教词语转写

在主意识的独立副本中，只输入“甲。”“乙。”“丁。”“戊。”，教外设把实际听到的词转写出来；正式问答轨迹不接收这些答案。每阶段8条样本，后续沿用旧参数并回放旧示范。它依然会进行计算，所谓严格是切断任务事实的直接监督，不是假装能从软件结构上证明它绝无答题能力。

{chr(10).join(strict)}

转写训练的成功只证明能读直接听词，问后回忆是否可用仍单独看右侧。若未过7/8转写校准门槛，后续未执行不是Core的阴性结果。直接听词、联想牵动词和准备表达，不能预先认定三者活动分布相同。

### 同一批资料，换一个简单的数值读法

两来源均在阶段0只拟合2/8，故停止原Transformer转写扩展。核查甲/乙的原始活动，差异峰值约0.08584，120ms采样仍约0.06180，并没有全部漏掉。随后登记线性岭回归对照：原始六字段、相同时刻，不减基线、不居中、不归一化；仅阶段0的八个听词样本、固定正则系数0.0001。另取四副本，输入未用于拟合的0.5强度词语。

{chr(10).join(linear)}

线性转写器**已在这两个来源和四词条件下读会了实际听词**，表明Transformer转写失败属于当前外设学习/表示环节的缺口，并非数据里完全没有区别。它只在有限词表中选择，不能生成任意句子，也没有学到物体问答答案。冻结它后读取三个教学阶段的问答，并未出现可靠命名优势。此结果把“直接听词”和“问后表达”区分开了，不能由前者的成功自动补全后者。

## 时间与教学背景的定位补充

在看到首来源“教学8/8、后期提问4/16”后追加此诊断，明确是事后提出的新问题。用同一阶段2快照的8个副本均衡采集示范，仍保留原24条，再训练1000步。另采新视角和两种未校准的新问法，共12题；原表达器和新表达器读取同一实际轨迹。

{chr(10).join(aligned)}

这仍是**有任务答案监督的校准**。如果改善，只能说明同状态校准能缓解部分读出问题，不能据此直接宣布“纯翻译成功”或“内核推理成功”；若仍失败，也不能把所有原因归于Core。两类教学数据的数量、状态覆盖同时变化，不能把差异全归于时间单因子。

## 内部过程与没有问题时的输出

同来源、同阶段、同问法而不同对象的{totals['comparisons']}对原始局部过程，{totals['different']}对存在数值差异；其中{totals['collapsed']}对仍被当前外设说成同一个词。比较只用于分析，差值没有送给表达器或Core。存在差异不等于已经形成语义；但表达相同也不能证明意识活动相同。详细数值见[活动诊断](activity-results.json)。

{chr(10).join(no_cue)}

无提示指没有额外物体或语言问题，**物理遥测背景仍在**。联想字段非零反映记录中的局部过程，不等于这些词已经被证明是“内心独白”。没有给无提示活动强加空白真值，也没有给这些词编故事。

## 工具、预算与边界

新增[可持续学习外设](../../../docs/zh/reference/adaptive-expression.md)：Python/CLI、有界教学回放、延续参数、独立检查点、原话自听；每次更新重建优化器，不是快权重算法。默认自听关闭。5项针对性测试通过，CPU CLI训练/保存/读取跑通，两条实际CPU解码与GPU记录一致；这是小型功能验证，不是全设备数值保证。现有UI可查看研究报告和证据，生产聊天接入新外设尚未实现。

另提炼`lab.tools.local_word_transcriber.LocalWordTranscriber`，支持原始过程训练、解码和无pickle的快照；两项强度泛化、只读性和保存恢复测试通过。本轮合计7项针对性测试。

本批{totals['receipts']}份实验结果记录，计入预算的来源阶段/副本{totals['copies']}，记录计算{totals['minutes']}分钟。原预算640、180分钟，本地证据3GiB软限、含归档及数据库8GiB硬限；共享账户显示用量52%至54%，其中可能含其他任务。最终存储计数保存于本批“交付与资源”记录及仓库`delivery.json`。单worker，旧数据不删除、不覆盖，未操作Docker或用户服务。Core版本、旧表达器、旧实验保持原义；额外校准为另存分支。

已登记的选择性通路对照是否运行，见最终解释附录；不会用没有足够有效命名的组强行解释“语义消失”。复杂关系迁移、自由对话、昨天复述、实际发射流与状态观察流的比较，仍是后续问题。

![实验对照](outcomes.png)
'''
        else:
            body = f'''# E52: heard-word readout failure localized; recalled-content translation remains unresolved

2026-10-05. [中文](report.zh.md) · [Design and amendments](design.en.md) · [Every actual answer](../../../.work/coadaptive-language-20261005/outputs.html) · [Results](results.json)

An individual expression peripheral now continues learning, preserves bounded teaching replay, optionally hears its actual output, and receives ordinary teacher corrections. Core dynamics, defaults and sensory encoding remain unchanged.

The clearest new localization: **on the same raw observations, a linear transcriber recognizes4/4withheld-intensity heard words in each source; the original Transformer recognizes1/4in each.** That information reached the peripheral. Successful heard-word recognition nevertheless does not establish faithful translation of recalled content.

**The learning loop is implemented; faithful translation of content supplied by ThreeMind is not yet established.** Fitting demonstrations is distinct from answering later questions. An adapter attached to a Core with plasticity disabled can also fit demonstrations. Peripheral answering must not be credited to Core; failure of this reader likewise does not prove absence of Core information. Earlier E50 naming, pathway and transfer findings retain their original scope.

## Design

Two source courses, each with self-hearing, no self-hearing, and Core-plasticity-off arms: six continuing trajectories. Stage0 teaches two spheres; stage1 adds two boxes; stage2 exchanges the spheres' names while retaining the boxes. Color and shape are crossed. Different statements about the same referent include its name, color, shape and a same-color relation, rather than camera angles alone.

Every first statement receives10consecutive presentations and later2/4second spaced reviews. Eight interactive teaching turns per stage update the adapter every four turns. Its actual words, including errors, can return through ordinary sensory input before the teacher demonstrates a correction. Labels remain external. Tests receive raw local process observations without baseline subtraction, per-query scaling or target-selected nodes.

The original co-learning arm supervises **pre-answer activity** using the teacher's subsequent answer. That can teach the peripheral to answer independently. The user's clarification therefore adds a stricter transcription-only control, never taught object-name answers.

## Joint learning

{tables[lang]}

A constant name scores4/8 in the initial two-name phase and4/16 in the balanced four-name phases. These are intuitive references, not significance tests over independent minds: sibling probes are not independent subjects. All sources and arms are shown. The frozen initial adapter has not been taught the new objects; it measures adaptation, not equal-knowledge performance. Self-hearing adds real sensory exposure and is not dose-matched to its absence.

Actual live answers precede that turn's demonstration and model update. The first four stage0turns are silent because the adapter is uncalibrated and remain in the eight-turn denominator. Retrospective fitting of old observations is a different measurement.

Core-plasticity-off means`plasticity=false`from a blank start, not deletion of transient activation, inhibition or touch history. The switch also stops some structural forgetting updates. Configuration checks find only the declared seed/plasticity differences. Per-example replay weighting does not imply equal lifetime exposure per object: the first two arrive earlier. The final diagnostic adds two examples per object but retains that historical imbalance. These curriculum/context factors are not isolated by merely naming an arm coadaptive.

## Literal transcription without task-answer supervision

Independent main-source copies hear only the four isolated names at two intensities. The peripheral learns literal transcription, not object-name assignments. Those answer cues never enter actual test trajectories. Each stage adds8examples; later fitting continues weights and replays earlier demonstrations. The boundary blocks direct task-fact supervision, not all possible computation.

{chr(10).join(strict)}

Recognizing a heard word does not establish translation of recalled or intended words. Calibration below7/8 stops expansion and is an instrument limitation, not a negative Core finding.

### Same data, simpler numerical readout

Both initial Transformer transcribers fit only2/8, stopping later phases. The first two .4intensity words differ by up to0.08584in raw fields, still0.06180at120ms. A subsequently registered ridge reader uses the identical raw six-field samples: fixedridge=.0001, intercept, no centering, counterfactual subtraction or per-example scaling. Only the8stage0heard-word demonstrations train it. Four separate copies test withheld intensity.5.

{chr(10).join(linear)}

The finite-vocabulary linear reader succeeds at actually heard words in these two sources, localizing that Transformer failure to the external learning/representation route rather than complete absence of measured information. It cannot generate unrestricted sentences and receives no object-answer supervision. Frozen testing across all three course phases still does not produce reliable object naming. Heard-word and recalled-word patterns must not be assumed interchangeable.

## Context-balanced diagnostic

This amendment was registered after observing the first source's8/8teaching fit and4/16later questions. At each main source's final checkpoint,8independent copies provide balanced visual/description calibration, retaining24prior demonstrations and training once for1000steps. Twelve fresh tests use a new visual view and two previously uncalibrated phrasings. Both original and recalibrated heads read identical raw processes.

{chr(10).join(aligned)}

Calibration still supplies task answers. Any improvement localizes part of the readout problem; it does not establish pure translation or Core reasoning. Sample count and state coverage change together, so this is not an isolated estimate of elapsed-time effects.

## Process differences and unprompted words

Of{totals['comparisons']}same-source/stage/question-style comparisons across objects,{totals['different']}have numerically different raw local processes;{totals['collapsed']}of those still yield identical words. These differences are diagnostic only, never expression or Core inputs. They do not prove learned semantics, while identical expression also cannot establish identical activity. [Detailed measurements](activity-results.json).

{chr(10).join(no_cue)}

No-cue windows retain recorded physical telemetry; they omit extra language/object questions. Nonzero associative measurements do not establish that generated words faithfully describe inner speech. No invented semantic truth or enforced blank target is assigned to these windows.

## Delivery and limits

The[reusable peripheral](../../../docs/en/reference/adaptive-expression.md)offers Python/CLI, bounded teacher replay, continued weights, independent checkpoints and exact self-hearing. Adam restarts per update; this is not a fast-weight implementation. Self-hearing defaults off. Five focused tests pass; CPU CLI teaching/save/decode is exercised and two actual CPU answers match recorded CUDA answers, a small functional check rather than all-device numerical proof. Reports/evidence use the existing UI; production chat integration of this new peripheral is not delivered.

`lab.tools.local_word_transcriber.LocalWordTranscriber`also provides reusable raw-process fitting, decoding and non-pickle checkpoints. Its two additional tests exercise held-out intensity, input preservation and restoration: seven focused tests total.

The batch contains{totals['receipts']}result receipts,{totals['copies']}budget-counted source stages/probes and{totals['minutes']}recorded compute minutes, within640copies/180minutes. Local evidence soft cap3GiB, total including archive/database8GiB. Displayed shared-account usage changed from52%to54%, potentially including other tasks. Final storage is recorded in the study's delivery record and repository`delivery.json`. One worker; old evidence, Core, old adapters and defaults remain intact. No Docker or user-service operation.

The final interpretation appendix records whether conditional pathway interventions ran. Complex relation transfer, free dialogue, yesterday recall and emitted-signal versus copied-state observation remain separate open questions.

![Experimental comparisons](outcomes.png)
'''
        body += '\n'+(HERE/f'interpretation.{lang}.md').read_text(encoding='utf-8')
        if lang == 'en':
            # Spacing in prose only; preserve links and literal protocol names.
            chunks = re.split(r'(`[^`]*`|\[[^\]]*\]\([^)]+\))', body)
            for i in range(0, len(chunks), 2):
                chunks[i] = re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[A-Za-z])', ' ', chunks[i])
            body = ''.join(chunks).replace('The[', 'The [').replace(')offers', ') offers').replace('`also', '` also')
        (HERE/f'report.{lang}.md').write_text(body, encoding='utf-8')


if __name__ == '__main__':
    main()
