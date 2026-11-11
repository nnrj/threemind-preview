"""Render complete, audited R46a results. No simulation or partial-result selection."""
from pathlib import Path
import json
import statistics

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')
ZH={'exponential':'指数','inverse-logarithmic':'逆对数','power-law':'幂律'}
EN={'exponential':'Exponential','inverse-logarithmic':'Inverse-logarithmic','power-law':'Power-law'}
COURSE_ZH={'weak':'单次弱','ordinary':'单次普通','strong':'高剂量1.0','massed':'密集重复','spaced':'先密后疏重复'}
COURSE_EN={'weak':'Single weak','ordinary':'Single ordinary','strong':'Higher dose 1.0','massed':'Massed repetition','spaced':'Spaced repetition'}

def load(path):return json.loads(path.read_text('utf-8'))
def label(row,lang):
    return ((ZH if lang=='zh' else EN)[row['curve']]+' / '+
        (('回落开' if row['relaxation'] else '回落关') if lang=='zh' else ('on' if row['relaxation'] else 'off')))
def table(headers,rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join('---' for _ in headers)+'|']+
        ['|'+'|'.join(str(x) for x in row)+'|' for row in rows])
def count_table(data,lang):
    headers=(['设置','高剂量保持','间隔重复保持','弱刺激遗忘','高剂量过程','间隔重复过程','有限淡忘：高/重复','全部目标'] if lang=='zh'
        else ['Setting','Higher dose retained','Spaced retained','Weak forgotten','Higher dose process','Spaced process','Finite fading: higher/spaced','All targets'])
    rows=[]
    for c in data['conditions']:
        x=c['counts'];rows.append([label(c,lang),f"{x['strong']['survives']}/8",f"{x['spaced']['survives']}/8",
            f"{x['weak']['forgotten']}/8",f"{x['strong']['process']}/8",f"{x['spaced']['process']}/8",
            f"{x['strong']['finite_fading']}/8; {x['spaced']['finite_fading']}/8",
            ('通过' if c['selection']['all'] else '未通过') if lang=='zh' else ('Pass' if c['selection']['all'] else 'Fail')])
    return table(headers,rows)

def detail_tables(data,lang):
    measures=[];cost=[];spacing=[]
    for c in data['conditions']:
        selected=[x for x in data['rows'] if x['case']['curve']==c['curve'] and x['case']['relaxation']==c['relaxation']]
        assert len(selected)==320
        for group in load(WORK/'operational-cost-v1.json')['conditions']:
            if group['curve']!=c['curve'] or group['relaxation']!=c['relaxation']:continue
            method=(('原实现' if group['implementation']=='original-frozen' else '精确加速') if lang=='zh' else group['implementation'])
            cost.append([label(c,lang),method,group['sequences'],
                f"{group['mean_wall_seconds']:.3f}",f"{group['max_boundary_private_bytes']/2**30:.3f}"])
        d=c['spacing_weight_difference']
        spacing.append([label(c,lang),f"{d['mean']:.6g}",f"[{d['bootstrap95'][0]:.6g}, {d['bootstrap95'][1]:.6g}]"])
        for course in COURSE_ZH:
            items=[x for x in selected if x['case']['course']==course and x['case']['delay']==300 and x['case']['cue']]
            assert len(items)==16
            h=[edge['half_life'] for x in items for edge in x['initial_connections']]
            w0=[edge['weight'] for x in items for edge in x['initial_connections']]
            w1=[edge['weight'] for x in items for edge in x['current_connections']]
            mean_late=sum(w1)/32
            measures.append([label(c,lang),COURSE_ZH[course] if lang=='zh' else COURSE_EN[course],
                f"{sum(x['formed'] for x in items)}/16",f"{sum(x['surviving'] for x in items)}/32",
                f"{statistics.median(h):.6g}" if h else '—',
                f"{statistics.mean(w0):.6g}" if w0 else '—',f'{mean_late:.6g}'])
    return (
        table(['设置','课程','形成双向连接的历史数','300秒原连接存续','教学末H中位数（秒）','教学末平均权重','300秒平均权重'] if lang=='zh' else
            ['Setting','Course','Histories with both edges','Original edges at 300 s','Median taught H (s)','Mean taught weight','Mean late weight'],measures),
        table(['设置','计算实现','序列数','平均单序列操作墙秒','边界私有内存最大GiB'] if lang=='zh' else
            ['Setting','Implementation','Sequences','Mean operation s/sequence','Maximum boundary private GiB'],cost),
        table(['设置','间隔减密集：300秒平均权重差','来源重采样95%区间'] if lang=='zh' else
            ['Setting','Spaced minus massed: mean late weight','Origin-bootstrap 95% interval'],spacing))

def conclusions(data,lang):
    passed=[label(c,lang) for c in data['conditions'] if c['selection']['all']]
    if passed:
        lead=('**满足本批全部目标的设置是：'+ '、'.join(passed)+'。**这些设置同时通过高剂量与间隔重复的保持、弱刺激遗忘、经历相关过程的再次唤起和有限淡忘要求。' if lang=='zh' else
            '**The settings that met every registered target are: '+', '.join(passed)+'.** They jointly met the higher-dose/spaced retention, weak-exposure forgetting, temporal reinstatement and finite-fading requirements.')
    else:
        lead=('**六种设置均未同时满足本批预先规定的保持、表达和遗忘要求。**本批没有选出同时满足三类要求的候选方案。各项成功和失败如下，均按运行前的标准判定。' if lang=='zh' else
            '**None of the six settings jointly met the preregistered retention, expression and forgetting requirements.** No tested candidate met all three requirements. The component successes and failures below follow the prospective criteria.')
    rows=[]
    fields=[('structure','结构选择原则','selective structural retention'),('process','经历相关过程保持','history-dependent temporal reinstatement'),('finite_fading','有限淡忘','finite fading')]
    for c in data['conditions']:
        good=[z if lang=='zh' else en for f,z,en in fields if c['selection'][f]]
        bad=[z if lang=='zh' else en for f,z,en in fields if not c['selection'][f]]
        if lang=='zh':rows.append('- '+label(c,lang)+'：'+('通过'+ '、'.join(good)+'；' if good else '')+('未通过'+ '、'.join(bad)+'。' if bad else '三项目标全部通过。'))
        else:rows.append('- '+label(c,lang)+': '+('passed '+', '.join(good)+'; ' if good else '')+('failed '+', '.join(bad)+'.' if bad else 'all three targets passed.'))
    return lead+'\n\n'+'\n'.join(rows)

def interpretation(data,diagnostics,lang):
    # Retrospective interpretation of the fixed primary scores and saved states.
    repeated=[e for r in data['rows'] if r['case']['course'] in ('massed','spaced')
        and r['case']['delay']==300 and r['case']['cue'] for e in r['initial_connections']]
    assert len(repeated)==384 and all(e['half_life']==30. and e['last_pass_us']=='0' for e in repeated)
    assert all(r['fields'][f]['late_rms']==0 for r in diagnostics['field_processes'] for f in ('activation','direct','associative'))
    assert all(r['distinct_numeric_outcomes']==1 for r in diagnostics['origin_diversity'])
    if lang=='zh':
        return '''## 结果的机制解释

**本批排除了“只要关闭时间尺度回落，就能保住重复教学”的解释。**同一曲线的回落开、关两组，各项判定完全相同。进一步检查教学末状态发现，密集和先密后疏两种课程的384条目标连接，其时间尺度全部为30秒，最后成功联想发送时间全部为0；其中重复共同刺激仍留下了连接更新记录。当前实现只有在连接成功发送联想信号、满足相应学习开关时才延长边的时间尺度。因此，这两种课程增加了连接权重，却没有触发延长其保持时间的条件；关闭回落也就没有更长的时间尺度可保留。单次高剂量确实触发了发送，但关闭回落后的最大时间尺度也只有30.0115秒。这些是保存状态与现有更新规则共同给出的解释。

**改变衰减曲线确实改变了经历的保存范围，但三种曲线各有明确得失。**指数设置在300秒丢失了本批全部五种课程的目标连接。逆对数设置保留了五种课程的连接及经历相关过程，解决了本批重复课程的300秒保持，却未实现弱刺激的选择性遗忘：弱刺激连接仍重约0.009217，高于0.008删除阈值。其高剂量连接在30日条件性预测中还重约0.008369，也略高于预定阈值。幂律设置同时保住高剂量经历、遗忘弱经历，并通过有限淡忘；不过两种重复课程的目标连接在300秒均已消失。因此，逆对数在本批重复经历的保持上胜出，幂律在高剂量与弱剂量的区分上取得收益，整体没有全目标优胜者。

节点与连接的存续还呈现出可区分的情况。指数条件丢失的目标连接均至少缺少一个端点；幂律的两种重复课程则保留了两个端点，但原连接已经消失。后者直接说明，本批重复经历的丢失可以发生在节点仍在时。前者记录的是300秒端点状态，删除先后须由事件记录另行判断。

**300秒时仍可辨认的经历效应，全部表现为抑制过程。**逐字段分解显示，激活、直接激活和联想激活的历史差异均为0；非零差异来自抑制，抑制字段均方根约0.018450，对应四字段合并均方根约0.009225。原主指标事先包含抑制，相关过程保持的通过成绩完整成立。这一结果说明，保存的经历可以通过对后续活动的抑制来表达；只测正向激活会遗漏本批保留下来的经历效应。

同量重复中，先密后疏没有获得300秒权重优势。逆对数条件的间隔课程平均权重约0.019121，密集课程约0.020502，前者低0.001381；另两类曲线的两种课程在该时点均已丢失目标连接。这个结果直接回答本批固定间隔的比较，后续若改变间隔或教学强度，应另立课程。

上述解释使用完整结果和事前指定的字段分解；发送条件的源码核对属于结果出来后的机制解释。它们保持原主指标及其判定。
'''
    return '''## Mechanistic interpretation of the results

**The experiment rejects the explanation that disabling timescale relaxation alone is sufficient to preserve this repeated teaching.** Turning relaxation on or off produced identical component verdicts within each curve. All 384 target connections after the two repeated courses had a teaching-end timescale of 30 seconds and a last successful associative-send time of zero, although repeated co-stimulation had updated connections. In the current implementation, a connection's timescale grows only after successful associative transmission with the corresponding learning switches enabled. These courses increased connection weights without engaging the condition that extends retention time. Disabling relaxation therefore had no extended timescale to preserve. A single higher-dose exposure did trigger transmission, but the largest timescale with relaxation disabled was only 30.0115 seconds. Saved state and the existing update rule jointly support this explanation.

**Changing the decay curve changes which experiences persist, with distinct benefits and costs.** Exponential settings lost all five courses' target connections by 300 seconds. Inverse-logarithmic settings retained all five courses' connections and history-dependent processes. They solved the tested repeated courses' 300-second retention but failed selective forgetting of weak exposure: weak connections still weighed about 0.009217, above the 0.008 deletion threshold. Their higher-dose connections also remained slightly above the prospective threshold in the conditional 30-day forecast, at about 0.008369. Power-law settings retained higher-dose experience, forgot weak experience and passed finite fading, but lost both repeated courses' original target connections by 300 seconds. Thus inverse-logarithmic decay wins the tested repeated-experience retention comparison; power-law decay provides a benefit in distinguishing higher from weak dose. No setting wins across all registered requirements.

Node and connection survival distinguish two observed cases. Every missing target connection under exponential decay lacked at least one endpoint at 300 seconds. Under power-law decay, both repeated courses retained the two endpoints while losing the original connection. The latter directly establishes loss of the tested repeated-experience connection while its nodes remain. The former records endpoint status at 300 seconds; deletion order requires separate event evidence.

**Every detectable history effect at 300 seconds is expressed through inhibition.** Field-wise decomposition gives zero history difference in activation, direct activation and associative activation. Nonzero differences occur in inhibition, with field RMS about 0.018450 and combined four-field RMS about 0.009225. Inhibition was part of the prospective primary measure, so the corresponding temporal-retention passes stand in full. Retained experience can therefore be expressed by inhibiting subsequent activity; measuring positive activation alone would miss the retained history effect in this assay.

Equal-dose spaced teaching did not improve 300-second connection weight over massed teaching. Under inverse-logarithmic decay, mean weights were about 0.019121 for spaced and 0.020502 for massed teaching, a difference of -0.001381. Both courses lost their target connections by this delay under the other curves. This answers the comparison of the fixed schedules used here; altered intervals or doses require a new course.

These explanations use the complete results and the prospectively specified field decomposition. Checking the transmission rule in source is retrospective mechanistic interpretation. Primary measures and verdicts are preserved.
'''

def birth_repeatability(diagnostics,lang):
    assert len(diagnostics['origin_diversity'])==240
    assert all(r['distinct_numeric_outcomes']==1 for r in diagnostics['origin_diversity'])
    return ('本装置固定课程和初始参数，并关闭能量消耗。只读核查发现，在全部240个条件单元中，八个出生种子重新分配匿名通道编号后，数值结果完全相同。原8来源分母保留，用于报告这些重复；表中退化为一点的重采样区间描述这一固定条件的重复性。输入剂量、时序或环境变化的推广，应由实际改变这些条件的实验检验。' if lang=='zh' else
        'The assay fixes courses and initial parameters and disables energy consumption. In all 240 condition cells, the eight birth seeds remapped anonymous channel identities but produced exactly identical numeric outcomes. The original eight-origin denominator is retained to describe these repetitions. Point-valued bootstrap intervals describe repeatability under the fixed condition. Generalization across doses, timings or environments is assessed by experiments that actually vary those conditions.')

def main():
    assert load(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=1920)
    assert not any((WORK/x).exists() for x in ('STOP','in-flight.json'))
    data=load(WORK/'analysis-v1.json');audit=load(WORK/'independent-audit-v1.json')
    assert audit['passed'] and audit['complete_boundaries']==3840 and audit['auditor_revision']==2
    assert data['sequences']==1920 and data['independent_origins']==8
    resources=load(WORK/'resource-summary.json');storage=load(WORK/'storage-inventory-v1.json')
    diagnostics=load(WORK/'secondary-diagnostics-v1.json')
    resource_text='/'.join(f"{resources['minimum_available_bytes'][k]/2**30:.3f}" for k in ('commit','ram','system_disk','data_disk'))
    for lang in ('zh','en'):
        details,cost,spacing=detail_tables(data,lang)
        if lang=='zh':
            text=f'''# R46a：六种衰减设置对保持、唤起与遗忘的影响

首版科学报告。运行前协议于2026-11-09冻结；报告生成在全部计算和独立复核完成后。[English](report.en.md) · [事前协议](assay_protocol.zh.md)

## 明确结论

{conclusions(data,lang)}

## 目的、预期与实际设计

作者要求比较指数、对数、幂律衰减及延长后的时间尺度回落开关，寻找能保留反复教学和强刺激、遗忘微弱经历、长期不用仍会淡忘的设置。R45已发现，单独关闭回落没有改善原课程的联合判断，且自然教学的半衰期增长很小。R46a因而直接比较三种实际衰减曲线，先回答局部连接及其提示响应能否满足这些要求。

六组均使用真实5.2参考实现。对数在本批指逆对数函数；幂律指数为1。时间尺度固定时，三种曲线的单项新贡献均在一个时间尺度后降为一半；回落开启时，时间尺度沿用原线性规则缩短。所有公式、参数、刺激剂量、测量与门槛在运行前冻结。旧5.1、安装原生模块和全局默认未改变。

8个独立出生来源接受五种课程：单次弱0.12、普通0.4、高剂量1.0，及0.4强度的八次密集或先密后疏重复。两种重复的总剂量、末次刺激和课程结束时刻相同。每个来源包含两种相反教学史、1秒或300秒首次测试、呈现或省略提示，共1,920条从出生连续培养的序列。来源内条件均为嵌套观察，不增加独立样本数。课程结束为128内部秒；整个批次累计推进{audit['aggregate_internal_seconds']:,.0f}内部秒。

本批使用固定刺激适配器及固定时序测量工具，没有训练输出头。每个窗口保存1秒20帧的激活、抑制、直接和联想四字段。先从提示后的过程减去此前背景过程，再减去同龄、同经历的省略提示对照，最后比较相反教学史。由此测量提示引起的经历相关变化。两种提示条件在提示前的Core、测量状态及背景窗口哈希相同。

## 事前目标与成绩

运行中对输入字段的复核发现：本批每路幅值虽有0.12、0.4、1.0三档，`Stimulus.intensity`却全部是默认1.0，未触发要求整体强度大于1.0的专门强刺激项。原名`strong`因此按实际操作表述为“高剂量1.0”。原数值标准和分数完整保留；本批完成高剂量与重复经历的曲线比较，专门强刺激机制的保持目标仍需追加对照。该设计遗漏在全批结果生成前登记，见[刺激字段更正](stimulus-scope-correction.zh.md)。

结构目标要求：高剂量1.0和间隔重复的两条原目标连接在300秒仍保留，单次弱的原连接消失；各项须至少6/8来源同时满足两种教学史。过程目标要求高剂量1.0和间隔重复的历史差异在300秒仍可唤起：均方根超过1e-4、至少为1秒时的十分之一、两段过程的余弦相似度至少0.8，各须6/8来源。有限淡忘使用教学末完整状态，按登记公式推算在无新增强化或结构损伤时30内部日后的权重，须低于删除阈值；这项是条件性解析预测。

{count_table(data,lang)}

表中分母均为8个独立来源，每项至少6/8才通过；“有限淡忘”两列分别是高剂量1.0与间隔重复。通过全部目标要求结构、过程及有限淡忘同时通过。教学后未形成的连接独立记录，未被计作形成后的遗忘。

{interpretation(data,diagnostics,lang)}

{birth_repeatability(diagnostics,lang)}

## 保持量与间隔教学

{details}

每行包含8来源的两种历史。300秒平均权重以32条原目标连接为分母，消失者按0计；这是结构量，不是答题正确率。H指教学结束时的衰减时间尺度。

{spacing}

间隔与密集课程的次数及每路剂量相同。本表直接报告间隔减密集的方向；没有因为采用先密后疏教学而预设其必然更好。

## 对ThreeMind的意义和后续决定

本批证实，衰减曲线决定了这里的结构保持与遗忘取舍，关闭时间尺度回落则没有解决重复课程的保持问题。对ThreeMind的直接改进方向，是查清共同刺激造成的权重增加，为什么没有转化为足够的持久保持，并区分连接保存与抑制过程表达。当前不依据单项收益修改全局默认。

下一步先按已批准范围完成专门强刺激项与连接新颖性项的匹配对照，使用八种实际不同的输入条件，检验即时增强是否成为300秒结构和活动收益。完整个人时序Transformer的联合任务仍保留为下一层目标；原课程和旧个体保持。新的保持更新规则须另列候选及授权，不能把本批阴性结果当成静默修改Core的许可。

## 成本、完整性与交付

{cost}

平均单序列操作墙时来自教学与测试回执，包含模拟推进、状态捕获和原件写入，排除操作前的目录预算检查及外层控制开销。前175条使用原实现，其后1745条采用单独冻结的精确加速工具。两阶段的来源和课程构成不同，表中分层耗时用于核算实际成本。五份隔离长测验的原始窗口和完整状态与原实现精确相同；其中幂律两例从约154—156秒降至18秒。工具保留运算顺序、公式及所有贡献项，未改生产内核源码。科学宿主累计墙时{resources['wall_seconds']:,.2f}秒，包含完整暂停前的2288.56秒；在第1751个完整边界后，目录预算检查另经十二项工程检查及四个不变目录的字节核对改用等价实现；此前累计10136.22秒继续计入总墙时。第876条直接承接其128秒教学末态，没有重教。[目录检查补充](scan-addendum.zh.md)。工程验证耗时另存。峰值私有内存{resources['peak_private_bytes']/2**30:.3f}GiB。提交/RAM/C/E最小余量为{resource_text}GiB。保持原5/4/5/25GiB资源保护。[操作补充](operations-addendum.zh.md)

全部3,840个边界的哈希、连续时间、身份及映射通过核验。独立复算直接读取JSON并另写公式，不载入个体。冻结审计脚本存在末尾计数变量覆盖问题；原文件及失败日志保留，修订2只修正该变量并加入源码身份，完整数据复算通过。原有科学输入、分数和判据均未更改，详见[工具修正](postprocessing-correction-v2.md)。

归档前共{storage['study']['files']:,}个原件文件，逻辑大小{storage['study']['logical_bytes']/2**20:.3f}MiB，按文件身份去重后的实际分配{storage['study']['allocated_unique_bytes']/2**20:.3f}MiB。最大单份完整个体压缩状态{storage['largest_state']['compressed_bytes']:,}字节，解压JSON为{storage['largest_state']['decoded_json_bytes']:,}字节；含{storage['largest_state']['nodes']}个节点、{storage['largest_state']['directed_connections']}条有向连接和{storage['largest_state']['contributions']:,}项衰减贡献。该层完整个体含固定适配器和时序仪器，没有另存训练权重的依赖。Windows实际分配按文件身份去重，目录/MFT/数据库另计；清点表为`storage-inventory-v1.json`。图、原始输入和时序、完整个体、全部源码指纹、分析及复核记录一并归档。审阅归属于执行助手与独立算术实现，外部研究者复现另记。

原件目录：`{WORK.as_posix()}`。科研记录`e03f79a3-c92c-505d-bb37-6fad8e21355e`；API完整读回、归档哈希、最终pending及后续决定见[交付](delivery.md)。
'''
        else:
            text=f'''# R46a: effects of six decay settings on retention, reinstatement and forgetting

First scientific report. The prospective protocol was frozen on 9 November 2026; this report is generated after full computation and independent verification. [中文](report.zh.md) · [Prospective protocol](assay_protocol.en.md)

## Scientific conclusion

{conclusions(data,lang)}

## Purpose, expectation and actual design

The author requested exponential, logarithmic and power-law decay crossed with relaxation on/off, seeking retention after strong or repeated exposure, forgetting of weak exposure and eventual fading without further review. R45 found that disabling relaxation alone did not improve the previous joint task and that natural half-life growth was small. R46a therefore directly compares the decay curves through local connections and their cue-driven responses.

All six settings use genuine 5.2 with the reference backend. Logarithmic means the specified inverse-logarithmic function; the power exponent is one. A single new contribution reaches one half at the same fixed timescale in all curves. Enabled relaxation retains the original linear rule. Formulas, settings, doses, measurements and thresholds were frozen before execution. Historical 5.1, the installed native module and global defaults remain unchanged.

Eight independent birth origins receive five courses: single weak (0.12), ordinary (0.4), higher dose (1.0), and eight massed or progressively spaced presentations at 0.4. Repeated courses match total dose, final presentation and course end. Opposite teaching histories, separate 1/300-second first-test cohorts and cue-present/omission controls yield 1,920 sequences continuously developed from birth. Nested conditions do not increase independent N. Courses end at internal second 128; the aggregate advance is {audit['aggregate_internal_seconds']:,.0f} internal seconds.

Fixed stimulus adapters and a fixed temporal instrument are used, with no trained output head. Each one-second window preserves 20 frames of activation, inhibition, direct and associative activity. The post-cue process is differenced against the preceding background window, then against a same-age, same-history omission control, and finally between opposite histories. This isolates the history-dependent cue effect. Paired cue conditions have identical pre-cue Core, measurement and background-window hashes.

## Prospective targets and results

Review of the actual stimulus fields during execution found three channel amplitudes (0.12, 0.4 and 1.0), while `Stimulus.intensity` remained at its default 1.0 throughout. The dedicated strong-stimulus term, requiring overall intensity above 1.0, was not engaged. The registered `strong` course is therefore described by its actual operation: “higher dose 1.0.” Original numeric criteria and scores are retained. This batch completes the higher-dose/repetition curve comparison; retention attributable to the dedicated strong-stimulus mechanism requires the additional control. The design omission was recorded before full-batch outcomes were generated: [stimulus-field correction](stimulus-scope-correction.en.md).

Structural selection requires both original target connections after higher-dose and spaced exposure to survive 300 seconds and weak-exposure connections to disappear. Each component requires at least six of eight origins to meet it in both histories. Temporal reinstatement requires the 300-second history difference to have RMS above 1e-4, retain at least one tenth of the one-second RMS, and have cosine similarity at least 0.8; higher-dose and spaced courses each require six of eight origins. Finite fading projects teaching-end state for 30 internal days under no further reinforcement or structural damage, requiring weights below the deletion threshold. This is a conditional analytic prediction.

{count_table(data,lang)}

Every denominator is eight independent origins, with six-of-eight thresholds. Finite-fading entries are higher-dose/spaced, respectively. Overall success requires structural selection, temporal reinstatement and finite fading together. Connections never formed are reported separately and are not counted as forgotten.

{interpretation(data,diagnostics,lang)}

{birth_repeatability(diagnostics,lang)}

## Retention quantities and spacing

{details}

Each row includes two histories per origin. Mean late weight uses 32 original target connections, counting absent connections as zero; it is a structural measurement, not answer accuracy. H denotes the teaching-end decay timescale.

{spacing}

Spaced and massed teaching match presentation count and per-channel dose. The table reports the observed spaced-minus-massed direction without assuming a spacing benefit.

## Meaning for ThreeMind and subsequent choice

The experiment establishes that the decay curve determines the observed retention–forgetting tradeoff, while disabling timescale relaxation does not solve retention of the repeated courses. The immediate research direction is to identify why weight increases from co-stimulation fail to become sufficiently durable retention, while distinguishing connection persistence from expression through inhibition. Component benefits do not change global defaults.

The next approved step is the matched comparison of the dedicated strong-stimulus and connection-novelty terms, using eight genuinely different input conditions to test whether immediate enhancement becomes a 300-second structural and activity benefit. The complete personal temporal Transformer joint task remains the next-layer objective, with existing courses and individuals preserved. A new retention update rule requires a separately stated candidate and authorization.

## Cost, integrity and delivery

{cost}

Mean per-sequence operation time sums teaching and probe receipts, including simulation, state capture and original writing, while excluding preceding directory-budget checks and outer control overhead. The first 175 sequences used the original implementation; the remaining 1,745 used a separately frozen exact-acceleration tool. The strata differ in origin and course composition and describe actual costs. Five isolated long-probe copies exactly matched original raw windows and complete states; two power-law probes fell from about 154–156 seconds to 18 seconds. The tool preserves operations, formulas and every contribution; production Core source is unchanged. Total scientific-host wall time was {resources['wall_seconds']:,.2f} seconds, including 2,288.56 seconds before the complete pause. After complete boundary 1,751, directory-budget accounting was replaced by an equivalent implementation after twelve engineering checks and byte comparisons on four immutable directories. The prior 10,136.22 seconds remain included. Sequence 876 resumed its 128-second taught state without reteaching. [Directory-accounting addendum](scan-addendum.en.md). Engineering validation time is separately recorded. Peak private memory was {resources['peak_private_bytes']/2**30:.3f} GiB. Minimum commit/RAM/C/E headroom was {resource_text} GiB; reserves remained 5/4/5/25 GiB. [Operational addendum](operations-addendum.en.md)

All 3,840 boundary hashes, continuous times, identities and mappings passed verification. The independent audit reads JSON and directly implements the formulas without loading subjects. Its frozen revision had a final counter overwritten by a condition dictionary. The original and failure log are retained; revision 2 only corrects that variable and records its own provenance, then passes complete-data verification. Scientific inputs, scores and criteria are unchanged; see [tool correction](postprocessing-correction-v2.md).

Before publication, {storage['study']['files']:,} original files occupied {storage['study']['logical_bytes']/2**20:.3f} MiB logically and {storage['study']['allocated_unique_bytes']/2**20:.3f} MiB in allocated streams deduplicated by file identity. The largest complete compressed subject occupied {storage['largest_state']['compressed_bytes']:,} bytes, expanding to {storage['largest_state']['decoded_json_bytes']:,} JSON bytes; it contained {storage['largest_state']['nodes']} nodes, {storage['largest_state']['directed_connections']} directed connections and {storage['largest_state']['contributions']:,} decay contributions. This assay's complete subject includes fixed adapters and a temporal instrument, without separately stored learned-weight dependencies. Windows allocation excludes directory/MFT/database overhead; details are in `storage-inventory-v1.json`. Figures, inputs, temporal observations, complete subjects, source fingerprints, analysis and audit records are archived together. Review is attributed to the executing assistant and an independent arithmetic implementation; external replication is a separate category.

Originals: `{WORK.as_posix()}`. Research record: `e03f79a3-c92c-505d-bb37-6fad8e21355e`. Full API readback, archive hashes, final pending count and subsequent decisions are recorded in [delivery](delivery.md).
'''
        dest=HERE/f'report.{lang}.md'
        assert not dest.exists(),'preserve an existing report; append a dated revision'
        dest.write_text(text,encoding='utf-8')
    print(json.dumps(dict(reports_created=True,selected=[label(c,'en') for c in data['conditions'] if c['selection']['all']],storage=storage),ensure_ascii=False))

if __name__=='__main__':main()
