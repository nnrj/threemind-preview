"""Write the E64 answer report from completed evidence; never run or fit Core."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / '.work/centered-restart-20261008'
WORDS = ('球体', '圆柱体', '立方体', '圆锥体', '红色', '黄色', '蓝色', '绿色')
EN = ('sphere', 'cylinder', 'cube', 'cone', 'red', 'yellow', 'blue', 'green')


def main():
    r = json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    table = ['| Test | Correct /32 | Shape /16 | Color /16 | Calibrated types /20 | Uncalibrated types /12 | Zero activity | Mismatched activity |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for name in ('test-normal', 'confirmation-normal'):
        a, c = r['answers'][name], r['cases'][name]
        table.append(f"| {name} | {a['correct']} | {a['shape_correct']} | {a['color_correct']} | {a['calibrated_type']['correct']} | {a['uncalibrated_type']['correct']} | {c['zero_correct']} | {c['shuffled_correct']} |")
    table = '\n'.join(table)
    wrongs = {}
    cross_property = 0
    for name in ('test-normal', 'confirmation-normal'):
        rows = json.loads((WORK/'cases'/name/'predictions.json').read_text(encoding='utf-8'))
        cross_property += sum((v['label']<4) != (v['selected']<4) for v in rows)
        wrongs[name] = {(v['shape'], v['color'], v['label']) for v in rows if not v['correct']}
    assert cross_property == 0
    assert len(wrongs['test-normal'] & wrongs['confirmation-normal']) == 5
    for lang, words in (('zh', WORDS), ('en', EN)):
        errors = ['| Test / question | Object | Expected | Actual | Type calibrated |', '| --- | --- | --- | --- | --- |']
        for name in ('test-normal', 'confirmation-normal'):
            for v in r['answers'][name]['wrong']:
                color = words[4+v['color']] if v['color']<4 else ('灰色' if lang=='zh' else 'gray')
                errors.append(f"| {v['question_id']} | {color} {words[v['shape']]} | {words[v['label']]} | {words[v['selected']]} | {v['conjunction_calibrated']} |")
        errors = '\n'.join(errors)
        if lang == 'zh':
            body = f'''# E64：恢复成功流程后，中央形色問答明显改善

2026-10-08（北京时间）。**从空白开始，系统两套正式问答分别答对25/32、27/32；颜色都是15/16，形状10/16、12/16。** 旧成功流程值得恢复：现在已经能回答大多数中央形色问题，不能再说完全无法辨识。仍有明确短板：未见的形色搭配较弱，尚未达到本轮预登记的完整通过条件。

## 实际答案

{table}

校准见过的搭配换位置后18/20、20/20；未校准搭配两套都是7/12，五道错误重复出现。64道题均回答了所问的属性类别，没有问形状却答颜色或相反，但其中12次具体词语错误。这把下一步重点缩小到相近形状和未见组合，不能再把全部困难笼统归于单眼或完全没读出问题。

两套题来自**同一个意识＋自己的外设**，只是位置和顺序不同，不是两个独立训练种子。已校准类型不等于全新概念；全新组合的得分必须单列。E63旧方案3/32、纠错7/32，与本轮相比差距很大，但多项方法及种子同时改变，不能把改善全算给某一个因素。

## 实际完成的流程

1. 新空白continuous-memory/2，Core seed223、感官/文本91；出生配置对照E56成功来源。没有导入旧意识或旧外设知识。
2. 104课，180模拟秒；每项先10次，再三轮间隔复习。保留物理环境及本体背景、遗忘、抑制、普通强度1、NFKC与逐字符50ms。不增加分辨率、不改变Core。
3. 独立完整副本采48次真实无答案提问，取整段1秒内8帧原始活动。自己的时间Transformer集中校准1200步，训练48/48。标签只监督外设，不进入Core或推理接口。
4. 12项练习11/12；唯一错项再观察5轮，间隔0/0/0/6/18秒，实际增加39模拟秒。没有偷偷输入正确答案。再采12项，原48项与后12项共同继续校准1200步；保留自己的权重、Adam及学习随机状态。最终训练59/60。
5. 冻结这一表达器，不依据正式题再训练或选检查点；每题从同一完整快照独立恢复，完成32题及另一32题确认。八词选择是本任务输出，不称自由语言或手眼控制。

核心与自己的外设、学习状态、身体、映射、近期读出共同保存。外设离线校准没有推进或教导Core，不能把2400次优化步叫作2400次意识教学。按训练损失选择时同时保存对应的Adam/RNG；累计计算2400步，最终检查点延续2351步。没有按测试分数选择模型。

## 到底证实了什么

**整体系统的识别与作答有明显进步。** 原来的方法差别是实质问题，并非单眼注定不能识别。整段提问、真实问题校准、旧时间读取结构及相应训练流程共同构成了有效的新基线；本次没有单因素拆解，不能宣布其中某一个已被证明是唯一原因。

零活动输入只答对5/32、5/32；把不同题的活动错配则5/32、9/32。实际问题对应的Core活动对输出有用，外设并非始终吐出同一套答案。**这还没有单独证明答案主要由Core的学习连接或自主联想决定**：当前活动也包含感官响应，外设接受过监督识别训练。本批没有运行固定读头的连接静默/恢复，不能用空活动对照替代它。

## 停在何处，为何没有继续旧个体

助手在运行前登记的“进入后续分支”条件是两套均至少24/32，且每套形状、颜色各至少12/16。第一套形状10/16未达；该条件不是用户的意识定义或永久成功标准。总体改善成立，但本批条件性连接干预和旧E63个体校准均未启动，没有修改门槛以便继续。原旧个体、自己的外设和STOP保留。

因此，“空白与旧个体两者都有效后确立严格成功流程”的后半条件未验证。本批保存已验证的方法和必要操作约束，**不把仍未验证的完整方案提升成与核心假设同级的已证实规范**。核心假设正文没有改动。

建议下一轮保持这个新完整基线，先对反复出错的搭配做正常教师纠正及旧正确例复习，再用预先保留的组合验证；机制归因可另登记在已有25/32表现上做固定外设干预，而不必把得满分设为科学归因的前提。这是后续建议，本批未执行。原个体校准是否提前进行需明确调整这次分支安排，不回改本轮判据。

## 全部错题

{errors}

## 工具、资源和证据

9个完成阶段，140次创建/恢复，累计{r['compute_minutes']:.2f}计算分钟；同一实际来源的分支不算140个独立个体。新2项定向测试通过，连同E63的17个不同测试共19项；验证原架构等价、保存恢复和下一次学习延续。未修改Core源码、默认或旧数据。

本批完整回放249段、7100帧，包含教学、校准、练习、间隔、正式正确与错误；HTML41,990,540字节。它只播放已记录数据，不能操纵Core；不是新录制MP4，尚未通过真实浏览器视觉验收。账户共享起点18%，收尾实读22%；这一增长包含其他并行任务，不能全归本实验。存储明细见交付清单。

[启动前逐项核查](audit.md) · [固定设计](design.zh.md) · [机器结果](results.json) · [工程验证](verification.md) · [流程事故核查](../../../docs/zh/plans/experimental-procedure-audit.md) · [交接](HANDOFF.md)
'''
        else:
            body = f'''# E64: recovering the successful procedure substantially improves centered recognition

October8,2026, China time. **A blank-start system answers25/32 and27/32 in two formal sets: color15/16 in both; shape10/16 and12/16.** Most centered shape/color questions now work. Unseen combinations remain weaker; the complete preregistered branch criterion was not met.

## Actual answers

{table}

Previously calibrated types at changed positions score18/20 and20/20; uncalibrated types7/12 in both, with five recurring errors. All64answers name the requested property category;12specific words are wrong. This narrows the remaining problem to shape discrimination and new combinations, rather than an inability to read any question or use a whole eye.

Both sets use one trained Core/peripheral pair, not independent training seeds. Calibrated types are not new concepts. E63 scored3/32, then7/32after correction; the large difference motivates this recovered procedure but is not a single-factor estimate because several methods and the seed changed.

## Completed procedure

Blank continuous-memory/2 seed223, sensory/text91, with E56 birth configurations checked. No old knowledge is imported.104lessons over180simulated seconds use initial tenfold repetition and three expanding reviews. Physical/body background, forgetting, inhibition, intensity1, NFKC and50mscharacters remain unchanged. Core and resolution are not altered.

48genuine answer-free questions are sampled on complete copies, with8raw frames across each full1second question. The individual's own temporal Transformer receives1200supervised calibration updates, training48/48. Teacher labels supervise only the peripheral.12practice questions score11/12. The one error receives5exposure rounds, gaps0/0/0/6/18seconds, adding39seconds without a correct-answer stimulus.12later windows join the original48for1200continued updates, retaining weights/Adam/RNG; training59/60.

The frozen reader answers32formal questions and32confirmation questions. Each starts from the same complete snapshot. Test scores never select checkpoints or train the model. Eight-word classification is not free language or eye/hand control. Offline peripheral calibration does not teach or advance Core. Training-loss selection preserves the matching optimizer and RNG:2400computed updates,2351at the selected checkpoint. Whole-system state includes body, mappings and recent readout history.

## What the result supports

**The complete system's recognition and answers improved substantially.** Genuine query calibration, whole-question activity, the established temporal architecture and its training procedure together give a useful baseline. No single-factor ablation identifies one unique cause.

Zero activity scores5/32and5/32; mismatched activity5/32and9/32. The corresponding Core activity matters to the output. This does not isolate learned Core connections or association as the main source of recognition: activity includes sensory responses and the peripheral received supervised recognition training. Fixed-reader edge silence/rescue was not run; zero-input controls cannot replace it.

## Unexecuted conditional phases

The assistant preregistered a branch gate of≥24/32and≥12/16per property in both sets. Primary shape10/16fails it. This is an operational criterion, not the user's definition of consciousness or a permanent success standard. Accordingly, fixed-reader interventions and oldE63subject calibration did not start. The original subject, peripheral and STOP remain intact. The improvement is real within these tests; both-subject success is untested.

The requested higher-level success-procedure standard remains conditional. Tested methods and necessary continuity safeguards are recorded, but an unverified complete recipe is not promoted to a proven standard alongside the unchanged Core hypotheses. Suggested next work: retain this complete baseline, teach recurring errors while reviewing correct examples, then evaluate held-out combinations. A separately registered attribution study can also use the already successful25/32system; perfect recognition is not intrinsically required for causal investigation. These are recommendations, not completed experiments, and do not retroactively change this gate.

## Every wrong answer

{errors}

## Resources and delivery

9completed phases;140creations/restores;{r['compute_minutes']:.2f}compute minutes. Branches are not140independent trained organisms. Two new focused tests pass (architecture equivalence, complete restoration and next learning update);19distinct tests acrossE63/E64. Core/defaults/mappings and old evidence are untouched.

Replay contains all249clips/7100frames,41,990,540HTMLbytes: teaching, calibration, practice, intervals and both right/wrong formal answers. It replays recorded data only, is not a newly recordedMP4 and has not undergone actual browser visualQA. Shared account origin18%, latest reading22%; other concurrent tasks contribute. Storage is reported in the delivery manifest.

[Preflight audit](audit.md) · [Preregistration](design.en.md) · [Machine results](results.json) · [Engineering verification](verification.md) · [Procedure retrospective](../../../docs/en/plans/experimental-procedure-audit.md) · [Handoff](HANDOFF.md)
'''
        (HERE/f'report.{lang}.md').write_text(body, encoding='utf-8')


if __name__ == '__main__':
    main()
