"""Build small bilingual reports from completed, checked causal evidence."""
from probe import HERE, ResearchStorage, load_env, read, write


def main():
    load_env();w=ResearchStorage().workspace_path(HERE.name);s=read(w/'analysis/summary.json')
    a,b=s['arms']['2'],s['arms']['3.1'];cases=s['cases']
    assert s['source_unchanged']
    q={(r['arm'],r['question_id']):r for r in cases}
    assert q['3.1','final-0-0']['initial_reader']=='立方体' and q['3.1','final-0-0']['final_reader']=='圆柱体'
    words=['球体','圆柱体','立方体','圆锥体','红色','黄色','蓝色','绿色']
    en=dict(zip(words,['sphere','cylinder','cube','cone','red','yellow','blue','green']))
    table_zh=['| 内核 | 原题号 | 真值 | 正常 | 原连接静默 | 立即恢复 |','|---|---|---|---|---|---|']
    table_en=['| Kernel | Original question | Truth | Normal | Old edges silent | Immediate rescue |','|---|---|---|---|---|---|']
    for r in cases:
        table_zh.append(f"| /{r['arm']} | {r['question_id']} | {words[r['label']]} | {r['normal']} | {r['silence']} | {r['rescue']} |")
        table_en.append(f"| /{r['arm']} | {r['question_id']} | {en[words[r['label']]]} | {en[r['normal']]} | {en[r['silence']]} | {en[r['rescue']]} |")
    contrast_zh='\n'.join(f"| /{arm} | {d['normal_correct']}/12 | {d['silence_correct']}/12 | {d['rescue_correct']}/12 | {d['correct_to_wrong']} | {d['wrong_to_correct']} |"
        for arm,d in s['arms'].items())
    contrast_en=contrast_zh
    reader='\n'.join(f"| /{arm} | {d['reader_correct']['birth']}/12 | {d['reader_correct']['initial_fit']}/12 | {d['reader_correct']['final_fit']}/12 | {d['reader_correct']['zero_input']}/12 |" for arm,d in s['arms'].items())
    zh=f'''# E67 典型题归因：Core 连接与表达器各自改变了什么

2026-10-12；E67 附属诊断第1版。原最终成绩 `/2` 71/72、`/3.1` 67/72 不变；本稿的12题是已知结果后的有目的选样，不能当成新的总体成绩或独立个体重复。

## 明确结论

**两版 Core 的既有连接都对部分形状题的正确答案起了可逆的因果作用；个人表达器的学习也会决定具体答案，并且 `/3.1` 已找到仅因读取函数阶段不同而由对变错的实例。** 因而不能把成功全部归给表达器，也不能把剩余错误直接解释为 Core 遗忘。

固定最终个人表达器与同一输入，`/2` 有 {a['correct_to_wrong']} 道原本正确的题因原连接静默而答错，`/3.1` 有 {b['correct_to_wrong']} 道；恢复后全部回到正常答案和完全相同的八帧活动。这里“决定性”指特定完整系统与提问条件下，干预这些连接会改变对错；没有声称已定位概念存储或证明语义判断全部发生在 Core。

## 固定表达器的连接对照

| 内核 | 正常答对 | 静默后答对 | 恢复后答对 | 正确→错误 | 错误→正确 |
|---|---:|---:|---:|---:|---:|
{contrast_zh}

共12题/版，8道形状、4道颜色。两版所抽四道颜色题在静默前后都答对；它们对本次干预不失分，不代表可以删除整个 Core。正常条件共24次精确复现原八帧活动及原最终答案，恢复条件共24次再次精确复现；72个提问副本的输入均与对应原题相同，表达器权重哈希不变。两版共有 {a['changed_answers']+b['changed_answers']} 次答案改变，其中有原来就错的题改成另一错误答案，故“改变答案”不全是“失去正确性”。

几个典型案例：

- `/2`，位置A的绿色立方体（final-0-0）：立方体→圆柱体→立方体。相同读取器下，既有连接确实使这题答对。
- `/2`，位置A的绿色球体（final-0-2）：球体→圆柱体→球体。不是只有一个立方体孤例。
- `/3.1`，位置A的灰色圆锥体（final-0-3）：圆锥体→球体→圆锥体；黄色立方体（final-0-28）为立方体→圆柱体→立方体。
- `/2` 同一黄色立方体原本已误答圆柱体，静默和恢复仍误答圆柱体。这个对照未解除该错误，不能据此判定是 Core 或表达器单独造成。
- 同一位置的蓝色、红色、黄色、绿色提问，两版答案均保持正确；分数保持不意味着其原始活动没有变化。

位置A为(0.018, -0.006)，位置B为(-0.018, 0.006)，均在中央清晰视野。完整逐题表如下；原物体、位置和概率见 `analysis/paired-cases.csv` 及各题 `result.json`。

{chr(10).join(table_zh)}

## 固定 Core 活动的个人表达器对照

把同一份已保存的最终活动分别交给该个体自己的历史表达器推理，不在原个体上换装，不增加训练，不混用两版个体的读取器：

| 内核 | 出生时表达器 | 初次校准后 | 最终表达器 | 最终表达器读全零活动 |
|---|---:|---:|---:|---:|
{reader}

出生时两个读取器都给这12题同一个词“红色”；全零活动时 `/2` 全答“圆锥体”，`/3.1` 全答“球体”。两者各有一题碰巧吻合。这个控制说明当前读出需要变化的活动，不是关闭全部 Core 的因果检验。

**关键错误是 `/3.1` 的绿色立方体 final-0-0。** 同一最终活动，初教后的个人表达器能输出“立方体”，最终表达器输出“圆柱体”。这直接证明读取函数的改变可以决定本题对错，不能说当前 Core 活动已经完全不可能被已有个人读取器读出正确词。它不证明初期读取器在所有条件更好：本样本初期9/12、最终10/12，另有两题由错变对。

在相同末期活动上，`/2` 初校→最终有 {a['reader_initial_to_final_corrected']} 题改对、{a['reader_initial_to_final_regressed']} 题退步；`/3.1` 有 {b['reader_initial_to_final_corrected']} 题改对、{b['reader_initial_to_final_regressed']} 题退步。这是固定输入下读取函数的直接比较，不是把整段教学收益拆成可相加百分比；历史读取器面对末期活动也存在分布不匹配。

## 干预范围、解释边界与后续判断

一次性静默来源处全部已有连接（`/2` 135,576条、`/3.1` 136,068条），只用既有研究干预API。核验即刻状态仅静默集合和序号改变，未改权重、节点、配置、时钟、个人表达器；恢复是另一个同起点副本先静默再立即解除，随后才提问。无重新教学，也不把静默后成长的副本恢复成基线。

没有清空原节点活动和两条已在途的信号/抑制事件，没有阻止提问时新生连接。静默副本每题仍有 `/2` {a['new_edges_range'][0]}～{a['new_edges_range'][1]}、`/3.1` {b['new_edges_range'][0]}～{b['new_edges_range'][1]} 条新连接，末态原有幸存连接没有漏静默。相对正常条件，这12题新发传输量总计减少约 {a['transport_sent_suppression']*100:.3f}%、{b['transport_sent_suppression']*100:.3f}%，但剩余联想不为零。这是传输测量，**不是认知贡献百分比**。

因此本次已经回答“Core 有没有对答案起决定性作用”：对所列特定题，有。尚未回答“形色语义主要存在哪、Core学到的具体概念是什么”：全连接静默同时改变一般激活/抑制和读取器所见分布，不能定位语义内容。也没有训练直接看原始感官的替代读取器，不能宣称外设单独足够或不足。

对 `/3.1` 的改进判断：先把表达器续校引起的读取边界变化列为实证问题，不能仅凭最终67/72就先调保持参数。本诊断没有解释全部五个形状错误，也未把整体差距唯一归给某一组件；两版都存在已测连接作用，原总体 `/2` 更准、更快的结果仍成立。下一步若追问语义特异作用，应另登记局部/匹配控制及学习历史对照，不在这次12题结果之后追加挑选有利题。

## 连续性、运行与证据

原件在 `E:\\ThreeMindData\\experiments\\2026-10-12-e67-causal-probes`，资源 `research:e67-causal-probes-20261012`，附属到E67统一记录；原完整来源以哈希引用，不复制或替换原个体。协议、问题清单与来源/工具哈希先登记，后完成结果。`plan.json`、`complete.json`、`analysis/summary.json`、逐题轨迹和模型阶段读取表保留，原最终报告及其阴性结果不改。

分析运行在独立CPU进程，单线程、低优先级、单逻辑处理器，无GPU；`/4` 宿主保持原进程和课程并继续推进。同期诊断与四组正式训练开销分开；不能把并行期间的 `/4` 墙钟称作独占基准。工具 `record_cost.py` 追加按资源身份拆分的数据库引用字节，避免旧汇总按同名 `arms/2` 前缀把诊断算进主实验；不改冻结的运行脚本。

[事前协议](design.zh.md) · [实施与接续说明](README.md) · [原E67两组阶段报告](../2026-10-11-shape-color-kernels/report.zh.md)
'''
    english=f'''# E67 typical-case diagnosis: causal contributions of Core edges and the reader

October12,2026, adjunct revision1. Original final scores remain /2 71/72 and /3.1 67/72. These twelve post-outcome, purposively selected cases are not a new held-out score or independent subject replications.

## Findings

**Existing Core connections have a reversible causal role in correct answers to specific shape questions in both versions. Learned reader parameters also determine answers, including one demonstrated /3.1 regression with exactly the same Core activity.** Success cannot be attributed wholly to the reader, and an error cannot automatically be attributed to Core forgetting.

With the final personal reader and identical sensory inputs fixed:

| Kernel | Normal correct | Existing edges silent | Immediate rescue | Correct to wrong | Wrong to correct |
|---|---:|---:|---:|---:|---:|
{contrast_en}

There are eight shape and four color questions per arm. All four sampled color answers remain correct after silencing. All24 normal copies exactly reproduce the original eight activity frames and answers; all24 rescues exactly reproduce normal activity/answers. All72 copies retain matched recorded inputs and unchanged reader weight hashes. There are {a['changed_answers']+b['changed_answers']} changed answers overall, including wrong-to-different-wrong changes; answer dependence is distinct from beneficial correctness.

The /2 green cube at positionA changes cube→cylinder→cube; its green sphere changes sphere→cylinder→sphere. The /3.1 gray cone changes cone→sphere→cone and yellow cube changes cube→cylinder→cube. Conversely /2 already misclassifies that yellow cube as cylinder and retains the error under both controls. This does not identify that error as solely Core or solely reader caused. PositionA is(0.018,-0.006), B(-0.018,0.006), within the central clear field.

{chr(10).join(table_en)}

## Fix activity, vary the individual's own reader stage

The same saved final activity is inferred by that individual's own birth, initial-fit and final-fit reader. No real subject is refitted or transplanted, and readers are not interchanged between individuals.

| Kernel | Birth reader | Initial-fit reader | Final reader | Final reader on zeros |
|---|---:|---:|---:|---:|
{reader}

Both birth readers output red for every selected question. On zero activity the final /2 reader always outputs cone and /3.1 sphere, each accidentally matching one case. This diagnoses input dependence, not whole-Core removal.

For /3.1 green cube final-0-0, identical final Core activity yields **cube with the initial-fit reader but cylinder with the final reader**. The readout function therefore determines this error under a fixed activity representation. It is not evidence that every earlier reader is superior: initial-fit scores9/12 versus final10/12 in this sample, with two corrections and one regression. On fixed final activity /2 has {a['reader_initial_to_final_corrected']} corrections and {a['reader_initial_to_final_regressed']} regressions. Historical readers may see distribution mismatch; these conditional comparisons cannot be added as percentages of the full learning process.

## Intervention and interpretation

One-time silence targets all135,576 source edges in /2 and136,068 in /3.1 through the existing intervention API. Immediate state changes are limited to silence membership and sequence; weights, nodes, configuration, clock and reader are preserved. Rescue is a separate same-source copy silenced and immediately unsilenced before the question, not rewinding a copy after it has developed.

Existing node activity, two in-flight signal/inhibition events and new edges remain. Silent copies form {a['new_edges_range'][0]}–{a['new_edges_range'][1]} new edges per /2 question and {b['new_edges_range'][0]}–{b['new_edges_range'][1]} per /3.1 question; no surviving original edge escapes the silence set. New transport sent across the twelve questions falls by{a['transport_sent_suppression']*100:.3f}% and{b['transport_sent_suppression']*100:.3f}% respectively, but residual association is nonzero. These are transport measurements, **not cognitive contribution percentages**.

The specific necessity question is answered positively for the identified cases. Semantic storage or independent concept recognition inside Core is not localized: silencing also changes general activation/inhibition and the reader's input distribution. Direct-sensory alternative readers were not trained. The diagnosis does not explain all five /3.1 shape errors or uniquely assign its overall deficit. It establishes reader-stage boundary changes as a concrete issue to investigate before assuming retention tuning is the remedy. Further semantic-specific or learning-history controls require a new protocol, not post-result sample expansion.

## Provenance and isolation

Originals use `research:e67-causal-probes-20261012`, under `E:\\ThreeMindData\\experiments\\2026-10-12-e67-causal-probes`, linked to E67 through its normal research APIs. Complete parent systems and source hashes remain unchanged; terminal traces are not represented as resumable trained individuals. Preregistered plan/source hashes, per-case traces, reader-stage results and completion/analysis receipts are preserved. Earlier E67 reports and negative results remain intact.

The independent diagnostic process uses one low-priority CPU thread on one logical processor and no GPU. The existing /4 host continues without restart or curriculum change. Disclose the overlapping interval in later wall-clock comparisons; it is not exclusive-machine benchmarking. `record_cost.py` appends resource-aware database reference accounting, keeping adjunct evidence separate from main-course per-arm costs without changing the frozen publisher.

[Protocol](design.en.md) · [Reproduction and continuation](README.md) · [Original two-arm interim report](../2026-10-11-shape-color-kernels/report.en.md)
'''
    write(HERE/'report.zh.md',zh.encode('utf-8'));write(HERE/'report.en.md',english.encode('utf-8'))
    with ResearchStorage().writer('research:e67-causal-probes-20261012'):
        write(w/'reports/report.zh.md',zh.encode('utf-8'));write(w/'reports/report.en.md',english.encode('utf-8'))
        for name in ('build_report.py','record_cost.py','README.md'):write(w/'source-reference'/name,(HERE/name).read_bytes())
    print('Both reports saved; review before publishing.')


if __name__=='__main__':main()
