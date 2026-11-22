"""Create bilingual reports only after the frozen read-only R51t audit passes."""
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import comparable_budget_v3 as r


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+
        ['| '+' | '.join(map(str,row))+' |' for row in rows])


def report(work):
    r.check(work)
    read=lambda p:json.loads(p.read_bytes())
    a=read(work/'analysis.json');audit=read(work/'audit.json');summary=read(work/'summary.json')
    assert audit['passed'] and audit['read_only'] and audit['created_engines']==0
    assert not (work/'in-flight.json').exists() and summary['stages']==592
    d=a['decisions'];index={v['key']:v for v in a['process']}
    assert d['scientific_stop']==audit['scientific_stop']
    assert a['counts']['states']==4746 and a['counts']['inputs']==41248
    costs=[read(p) for p in sorted((work/'costs').glob('*.json'))]
    assert len(costs)==592
    resources=read(work/'resource-summary.json')
    files=[p for p in work.rglob('*') if p.is_file()]
    storage={'logical_bytes':sum(p.stat().st_size for p in files),
        'allocated_bytes':sum(r.x.e.support.compact.x.disk_allocation(p)['allocated_bytes'] for p in files),
        'files':len(files)}
    ratios=[c['comparable_bytes']/c['historical_allocated_bytes'] for c in costs]
    qualified=[v for v in a['process'] if v['cue']!='none' and v['qualified']]
    qualified_targets=[v for v in qualified if v['cue'] in ('A','D','AB','DB')]
    qualified_correct=sum(v['qualified_target_margin']>r.x.m.EPS for v in qualified_targets)
    cued=[v for v in a['process'] if v['cue']!='none']
    assert len(cued)==452
    assert sum(v['cue'] in ('A','D','AB','DB') for v in cued)==404
    assert sum(v['cue']=='B' for v in cued)==48
    names=[('default_retention_passed','重复配对的保持','Retention of repeated pairings'),
           ('stored_memory_passed','提示前关闭连接强化后的表达','Expression with test-time strengthening disabled'),
           ('sustained_mechanism_passed','持续活动及其资源控制','Sustained activity and resource control'),
           ('prefix_preserved_or_extended','共享中间刺激的前缀作用','Prefix effects with a shared middle stimulus')]
    failed=[name for key,name,_ in names if not d[key]]
    failed_en=[name for key,_,name in names if not d[key]]
    short_zh='四项主要目标均达成，本批未触发停止条件，继续下一项原规模复验。' if not failed else (
        '未达成的主要目标为：'+'、'.join(failed)+'。本批触发事前规定的科学停止条件；完成原件交付后，暂停后续复验并报告。')
    short_en='All four primary targets were met. No scientific stopping rule was triggered, and the next original-scale replication proceeds.' if not failed_en else (
        'The following primary targets were not met: '+'; '.join(failed_en)+'. The preregistered scientific stopping rule was triggered. After evidence delivery, subsequent revalidation pauses for review.')
    at300=next(v for v in d['retention'] if v['bits']=='101' and v['delay_s']==300)
    historical300=mean(index[f'retention/s{s}/101/paired/d300/{cue}']['old_signed_peak']-
        index[f'retention/s{s}/101/balanced/d300/{cue}']['old_signed_peak'] for s in (0,1) for cue in ('A','D'))
    retained=[v['retained_fraction'] for row in d['test_time_L_off'] if row['bits']=='101' for v in row['cells']]
    silent_sustain=all(v['maximum']==0 for cell in d['sustained'] for v in cell['variants'].values())
    sampled_activity=[]
    for swap in (0,1):
        values=[]
        for delay in (1,30,300):
            row=next(v for v in a['structure'] if v['key']==f'retention/s{swap}/011/paired/d{delay}/A')
            values.append(max(row['pre_cue_task_activation'].values(),default=0.))
        sampled_activity.append(values)
    outputs={}
    for lang in ('zh','en'):
        zh=lang=='zh'
        yes,no=('达成','未达成') if zh else ('Met','Not met')
        target_table=table(['目标','结果'] if zh else ['Target','Outcome'],
            [[cn if zh else en,yes if d[key] else no] for key,cn,en in names])
        retention=[]
        for cell in d['retention']:
            old=[]
            for v in cell['cells']:
                base=f"retention/s{v['swap']}/{cell['bits']}"
                old.append(index[f"{base}/paired/d{cell['delay_s']}/{v['cue']}"]['old_signed_peak']-
                           index[f"{base}/balanced/d{cell['delay_s']}/{v['cue']}"]['old_signed_peak'])
            retention.append([cell['bits'],cell['delay_s'],f"{cell['mean_effect']:.9g}",f'{mean(old):.9g}',
                str(cell['positive'])+'/4',yes if cell['passed'] else no])
        retention_table=table(['D/F/L','等待（秒）','6.1配对作用','旧版配对作用','正向比较','完整条件判定'] if zh else
            ['D/F/L','Wait (s)','6.1 pairing effect','Historical effect','Positive comparisons','Full condition'],retention)
        readouts=[]
        for c in d['test_time_L_off']:
            readouts.append([c['bits'],c['delay_s'],f"{mean(v['on'] for v in c['cells']):.9g}",
                f"{mean(v['off'] for v in c['cells']):.9g}",f"{mean(v['effect'] for v in c['cells']):.9g}",
                yes if c['passed'] else no])
        readout_table=table(['教学D/F/L','等待（秒）','L开启：目标优势','L关闭：目标优势','L关闭：配对作用','判定'] if zh else
            ['Teaching D/F/L','Wait (s)','Target margin, L on','Target margin, L off','Pairing effect, L off','Outcome'],readouts)
        sustained=[]
        labels={'unchanged':('不干预','Unchanged'),'depletion-on':('开启耗竭','Enable depletion'),
            'facilitation-off':('关闭易化','Disable facilitation'),'both':('同时改变二者','Both changes'),
            'consolidation-off':('仅关闭L','Disable L only')}
        for c in d['sustained']:
            for name,v in c['variants'].items():
                sustained.append([c['swap'],labels[name][0 if zh else 1],f"{v['first']:.9g}",f"{v['end']:.9g}",
                    '—' if v['last_positive_us'] is None else f"{v['last_positive_us']/1e6:g}"])
        sustained_table=table(['教材区组','条件','开始时活动','15秒末活动','末次非零活动（干预后秒）'] if zh else
            ['Material block','Condition','Initial activity','Activity at 15 s','Last positive activity (s after intervention)'],sustained)
        prefixes=[]
        for c in d['prefix']:
            prefixes.append([c['bits'],c['delay_s'],str(sum(v['passed'] for v in c['cells']))+'/2',
                '; '.join('/'.join(f'{n:.9g}' for n in v['values']) for v in c['cells'])])
        prefix_table=table(['D/F/L','教学后等待（秒）','两前缀均正确的区组','区组0及1的AB/DB目标优势'] if zh else
            ['D/F/L','Post-teaching wait (s)','Blocks passing both prefixes','AB/DB target margins in blocks 0 and 1'],prefixes)
        classification_table=table(['时序分类','次数'] if zh else ['Temporal classification','Count'],sorted(a['classifications'].items()))
        interactions=table(['作用','1秒','30秒','300秒'] if zh else ['Effect','1 s','30 s','300 s'],
            [[name]+[f"{d['interactions'][str(delay)][name]['mean']:.9g}" for delay in (1,30,300)]
             for name in ('D','F','L','DF','DL','FL','DFL')])
        full_qualified=(f'452次有提示诊断中，{len(qualified)}次被原时序读出器判为合格收敛。404次具有指定结尾的A、D、AB、DB提示中，合格窗口为{len(qualified_targets)}次，其中{qualified_correct}次的所教目标优势超过1e−6。另48次单独B提示用于共同中间刺激对照，只报告窗口及两个结尾的活动，不给它强加唯一正确结尾。'
            if zh else f'Of 452 cued diagnostics, {len(qualified)} were classified as converged by the original temporal readout. Among the 404 A, D, AB and DB cues with a specified ending, {len(qualified_targets)} produced qualified windows and {qualified_correct} had a taught-target margin above 1e-6. The remaining 48 B-only cues control for the shared middle stimulus; their windows and both ending responses are reported without assigning a unique correct ending.')
        retention_conclusion=('默认101在30和300秒的四次比较均保持目标优势和正向配对作用，重复教学的保持目标得到复现。'
            if d['default_retention_passed'] else '默认101没有在两个预定保持时点都满足全部四次比较；重复教学的主要保持目标未在本批复现。') if zh else (
            'Default 101 retained the taught target and a positive pairing effect in all four comparisons at both 30 and 300 seconds. The repeated-teaching retention target was reproduced.'
            if d['default_retention_passed'] else 'Default 101 did not satisfy all four comparisons at both prespecified delays. The primary repeated-teaching retention target was not reproduced in this batch.')
        expression_conclusion=('仅在提示前关闭L后，默认101仍在30和300秒通过，说明既有经历可以在不继续强化连接的条件下表达。'
            if d['stored_memory_passed'] else '提示前关闭L的默认101条件未在两保持时点全部通过，原定“无需测试期强化仍能表达”的目标未复现。') if zh else (
            'Disabling L immediately before the cue preserved the default-101 effect at both delays. Established experience can therefore be expressed without further connection strengthening during the test.'
            if d['stored_memory_passed'] else 'Default 101 with L disabled before the cue did not pass at both delays. Expression independent of test-time strengthening was not reproduced as specified.')
        sustain_conclusion=('两个区组均支持预定机制：011条件保持活动，开启耗竭或关闭易化使活动终止，而仅关闭L保留活动。'
            if d['sustained_mechanism_passed'] else '至少一个区组没有满足预定的持续活动及干预组合，旧011条件的维持机制未完整复现。各条件的起点与终点见表，不能把所有失败写成同一种原因。') if zh else (
            'Both blocks supported the prespecified mechanism: activity persisted under 011, ended after depletion was enabled or facilitation disabled, and persisted when only L was disabled.'
            if d['sustained_mechanism_passed'] else 'At least one block failed the prespecified combination of sustained activity and intervention effects. The historical 011 maintenance mechanism was not fully reproduced. The table distinguishes absent initial persistence from altered intervention effects.')
        prefix_conclusion=('默认101至少有一个预定等待时点在两个区组都区分两种前缀，短时输入交互目标达成。'
            if d['prefix_preserved_or_extended'] else '默认101在1、3和20秒均未形成两个区组共同通过的双前缀区分，原定短时输入交互目标未达成。') if zh else (
            'Default 101 distinguished both prefixes in both blocks at at least one prespecified delay, meeting the short-term input-interaction target.'
            if d['prefix_preserved_or_extended'] else 'Default 101 did not distinguish both prefixes in both blocks at any of 1, 3 or 20 seconds. The short-term input-interaction target was not met.')
        if d['default_retention_passed']:
            retention_conclusion+= (f' 300秒的平均配对作用为{at300["mean_effect"]:.9g}，旧版/2原批为{historical300:.9g}，当前约为旧值的{at300["mean_effect"]/historical300:.2f}倍。本装置中的重复配对保持得到增强。' if zh else
                f' At 300 s the mean pairing effect was {at300["mean_effect"]:.9g}, compared with {historical300:.9g} in the original kernel-/2 batch, a ratio of {at300["mean_effect"]/historical300:.2f}. Retention of repeated pairings improved in this apparatus.')
        if d['stored_memory_passed']:
            expression_conclusion+= (f' 这八次比较保留了L开启时目标优势的{100*min(retained):.4f}%—{100*max(retained):.4f}%。先前教学的作用无需在测试时继续增强既有连接的基础权重，便能得到表达。' if zh else
                f' Across these eight comparisons, {100*min(retained):.4f}%–{100*max(retained):.4f}% of the L-on target margin remained. Prior teaching can be expressed without further increases to existing connections\' base weights during the test.')
        if silent_sustain:
            assert sampled_activity[0]==sampled_activity[1] and sampled_activity[0][1:]==[0.,0.]
            sustain_conclusion=('两个教材区组在1秒检查点的任务节点最大激活均为'+f'{sampled_activity[0][0]:.9g}'+
                '，30秒和300秒检查点均为零。持续活动在干预开始前已经消失；随后五种条件的整个15秒窗口也全部为零。因此，旧011条件下持续活动能够维持至300秒的结果没有在6.1中复现。开启耗竭或关闭易化后的零终点不记为终止活动的因果效果，因为各组都从零活动起点开始。') if zh else (
                f'In both material blocks, maximum task-node activation was {sampled_activity[0][0]:.9g} at the one-second checkpoint and zero at 30 and 300 seconds. Activity had already ceased before intervention. Every sample in all five subsequent 15-second conditions was also zero. Kernel 6.1 therefore failed to reproduce persistence to 300 seconds under the historical 011 condition. Zero endpoints after enabling depletion or disabling facilitation are not counted as causal termination: all branches started with zero task activity.')
        if not d['prefix_preserved_or_extended']:
            normal=[v for v in d['prefix'] if v['bits']=='101']
            assert all(not c['passed'] for v in normal for c in v['cells'])
            assert all((c['values'][0]<0<c['values'][1]) if v['delay_s'] in (1,3) else
                (c['values'][1]<0<c['values'][0]) for v in normal for c in v['cells'])
            assert all(index[f'history/s{s}/101/d1/{cue}']['old_signed_peak']>r.x.m.EPS for s in (0,1) for cue in ('AB','DB'))
            prefix_conclusion+= (' 旧默认条件在教学后1秒的两个区组均能分别识别AB与DB的对应结尾；6.1在同一条件下的联合通过数为0/2。新结果中，1秒和3秒时两种前缀都偏向D序列的结尾，20秒时都偏向A序列的结尾。等待改变了优势结尾，却没有恢复按前缀区分两条序列的能力。' if zh else
                ' At the one-second wait, both historical default-condition blocks distinguished the endings associated with AB and DB; kernel 6.1 passed jointly in 0/2 blocks. In the new results, both prefixes favored the D-sequence ending at one and three seconds, and the A-sequence ending at 20 seconds. Waiting changed the dominant ending without restoring prefix-specific discrimination.')
        meaning=('本批确认，6.1在这套装置中保留并增强了重复配对的保持，先前教学的作用也能在关闭测试期连接强化后表达。同时，旧011条件下的持续活动，以及共享中间刺激时按前缀区分结尾的能力，没有复现。这是两项明确的不利动力学差异，触发全面复验计划事先规定的暂停条件。\n\n后续应先用相同教材比较历史内核与6.1，定位相关更新规则的作用，再决定如何继续全面复验。已有的连接因果、移植和四项判据结果按各批实际记录保留；本批不修改默认参数或生产内核。') if zh else (
            'This batch establishes that kernel 6.1 retains and strengthens repeated-pairing retention in this apparatus, and expresses prior teaching when test-time connection strengthening is disabled. It fails to reproduce two historical properties: persistent activity under 011 and prefix-specific endings when sequences share a middle stimulus. These are two explicit adverse dynamical differences and trigger the comprehensive plan\'s preregistered pause.\n\nThe next step is a same-material comparison of historical kernels and 6.1 to locate the responsible update rules before deciding how to resume comprehensive revalidation. Connection-causality, transplantation and four-criterion findings from other batches retain their recorded outcomes. This batch changes no default parameter or production Core.')
        record=read(work/'registration.json')['record']
        if zh:
            outputs[lang]=f'''# 突触资源、易化与连接强化的6.1复验

2026-11-14，R51t，按全面复验计划v2重做E12的原规模科学比较。

**{short_zh}**

{target_table}

## 实验目的与方法

本批检验重复经历能否留下可被提示唤起的对应关系，以及连接强化、突触资源耗竭和短时易化如何参与保持与表达。D、F、L分别表示资源耗竭、短时易化和既有连接的正向强化，1表示开启，0表示关闭。F开启时使用1秒时间常数。L只控制当前实现中相应的既有连接权重更新；初次建边和其他局部机制仍按各自配置运行。

使用两个交换C/E对应的教材区组，每区组比较八种D/F/L组合。配对教材与平衡教材的刺激剂量相同；三阶段重复教学及间隔沿用旧输入。保持测试在最后教学后1、30、300秒进行。另设共享中间刺激B的两条序列、仅在测试前关闭L，以及011条件下持续活动的五种干预。Core采用真实6.1，传递信号门槛0.0004、删除阈值0.008、逆对数衰减及关闭保持增长等默认机制保持。

共34份连续教学参照、48份后续等待或共同参照、510次诊断，合计592阶段。诊断包括58次无任务提示和452次有提示；条件副本归属于两个教材区组。普通教学保留完整状态，因果副本和保持队列分别登记。41,248条输入使用旧API原件的固定重放，背景强度0.2，未将当前宿主负载作为新输入。每次诊断观察15内部秒，每10毫秒保存激活、抑制、直接及联想活动。

主指标先计算所教目标与另一目标的激活峰值差，称为目标优势；再减去平衡教材的相同差值，得到配对作用。超过1e−6为可辨别正向作用。保持条件要求两区组、每区组两提示均具有目标优势和正向配对作用。完整时序读出另用原阈值0.055和原分类规则评价。

## 重复经历的保持

{retention_conclusion}

每格汇总两个教材区组、两种提示。旧版列由同一输入条件的原始峰值重新计算；各区组原值及完整活动曲线均保留。

{retention_table}

八种条件的差异说明该结果依赖哪些局部机制。下面给出D、F、L及其交互的预定差分，正值表示增加平均配对作用，负值表示降低。三因素全组合按同一公式计算，未按结果筛选条件。

{interactions}

## 已有连接与测试期强化

{expression_conclusion}

{readout_table}

这些比较从同一完整参照建立副本，只在提示前通过公开配置接口改变L。配置调用导致的同刻状态结算也保存在逐字段干预记录中。报告区分教学已留下的对应关系与测试过程中继续发生的权重变化。

## 持续活动的维持与终止

{sustain_conclusion}

以下活动值是任务节点中最大的激活强度。计时从等待300秒后的干预开始，随后15秒没有新的任务刺激，记录的背景输入继续。最后非零时刻按10毫秒采样报告。

{sustained_table}

## 前缀如何影响共同中间刺激

{prefix_conclusion}

两条已教序列共享B。测试时比较A→B与D→B能否分别唤起相应结尾；表中每个区组的两个数依次对应这两种前缀。单提示、无提示和0.1、1、3秒提示间隔的完整结果保存在分析原件中。

{prefix_table}

## 原时序读出器的结果

{full_qualified}旧批452次有提示测试的合格收敛数为0。本项使用同一规则独立计分。

{classification_table}

激活峰值衡量机制作用，时序分类衡量原读出器是否形成合格窗口，两者的分母及分数分别保留。提示前结构、无提示活动和64次残余活动扣除结果也已写入analysis.json，供逐条件复算。

## 科学结论与对ThreeMind的意义

{meaning}

本批把“经历已留下何种连接作用”与“当前资源条件能否使它表达”放在同一组受控比较中。上述四项目标按原判据逐项结论，不以合格读出分数替代内部机制结果，也不以某一组合的成绩概括所有配置。{short_zh}

## 核验、成本和证据

只读分析核对592阶段、4746份完整状态、41,248条输入、192组提示前结构和4次观察工具对照，未创建或推进任何内核。独立高精度积分的最大误差为{a['maximum_arithmetic_error']:.6g}。装置的正常观察、降低观察频率、保存恢复和暂停保持完整终态一致。

正式计算耗时{summary['wall_seconds']/60:.2f}分钟，私有内存峰值{resources['peak_private_bytes']/2**20:.2f}MiB。同等记录的单阶段实际分配为旧对应阶段的{min(ratios):.3f}—{max(ratios):.3f}倍。报告生成前整批原件逻辑体积{storage['logical_bytes']/2**20:.2f}MiB，实际分配{storage['allocated_bytes']/2**20:.2f}MiB；包含独立装置和保留的写入资格检查材料。

原装置及流式写入v2先后触及1GiB私有内存线，均在完整边界保留。v3将投影缓存无损压缩，六校准阶段的完整状态、观察者、过程及投影字节一致，私有峰值756.20MiB，通过后正式批只启动一次。原件、归档、读回预算各8GiB，5/4/5/25GiB系统保留量保持；修订不改变Core、课程或评分。

只读核验先后修正两处工具错误：空总线应按接口检查空字典；四组观察对照应按冻结题表比较任务节点范围。592份最终总线均无待递送输入；四组6008个任务采样点、八份共同完整快照分别精确一致。原脚本、v2脚本和失败说明保留，v3完成全批核验。科学测量和判定门槛始终未变，没有重跑学生。两次修正及证明分别见audit-amendment-v2/proof.json和audit-amendment-v3/proof.json。

工作区：{work.as_posix()}。科研记录：{record}。双语报告、方案、工具、输入、完整状态和分析由同一科研记录交付；原包API读回凭据位于publication/completion.json。旧报告和作者论文保留。本次独立算术复算属于工具核验，外部研究者复现另行登记。
'''
        else:
            outputs[lang]=f'''# Kernel 6.1 replication of synaptic resources, facilitation and connection strengthening

14 November 2026, R51t. Original-scale E12 comparisons under comprehensive revalidation plan v2.

**{short_en}**

{target_table}

## Purpose and methods

The study tests whether repeated experience leaves cue-retrievable associations and how connection strengthening, synaptic-resource depletion and short-term facilitation contribute to retention and expression. D, F and L denote depletion, facilitation and positive strengthening of existing connections; one means enabled and zero disabled. Enabled F uses a one-second time constant. L controls the corresponding existing-connection weight updates, while initial edge creation and other local mechanisms follow their declared settings.

Two material blocks exchange the C/E target assignments. Each tests all eight D/F/L combinations. Paired and balanced teaching use equal stimulus doses and the original three-stage repetitions and spacing. Retention is tested 1, 30 and 300 seconds after teaching. Additional comparisons use two sequences sharing middle stimulus B, disable L only before testing, and apply five interventions to sustained activity under 011. Genuine kernel 6.1 retains transmission threshold 0.0004, deletion threshold 0.008, inverse-logarithmic decay and disabled retention-scale growth.

There are 34 continuous teaching references, 48 subsequent waiting or common-reference stages, and 510 diagnostics: 592 stages in total. Diagnostics include 58 uncued and 452 cued cases. Copies remain nested within the two material blocks. Ordinary teaching preserves complete state; causal copies and retention cohorts are registered separately. The 41,248 inputs replay original API records, including background intensity 0.2; current host load is not introduced as new input. Each diagnostic records activation, inhibition, direct and associative activity every 10 ms for 15 internal seconds.

The primary target margin subtracts the other target's activation peak from the taught target's peak. Subtracting the corresponding balanced-teaching margin gives the pairing effect. Values above 1e-6 are positive. A retention condition requires both target and pairing advantages for both cues in both material blocks. The original temporal readout is evaluated separately with threshold 0.055 and its original classification rules.

## Retention of repeated experience

{retention_conclusion}

Each cell summarizes two blocks and two cues. Historical effects are recalculated from the original peaks under the same input conditions. All block-level values and complete trajectories remain available.

{retention_table}

The following prespecified factorial differences quantify D, F, L and their interactions. Positive and negative values respectively increase and reduce the mean pairing effect. All combinations use the same formula; none was selected after observing the result.

{interactions}

## Established connections and test-time strengthening

{expression_conclusion}

{readout_table}

These comparisons branch from the same complete reference and change L through the public configuration interface immediately before the cue. Field-by-field receipts include any settling of current state caused by that call. The comparison distinguishes established teaching effects from continued test-time weight changes.

## Maintaining and terminating activity

{sustain_conclusion}

Activity is the maximum activation among task nodes. Time starts at intervention after the 300-second wait. The following 15 seconds contain no new task stimulus; recorded background input continues. Last positive times use the 10-ms sampling interval.

{sustained_table}

## Prefix effects on a common middle stimulus

{prefix_conclusion}

Both taught sequences share B. A→B and D→B test whether each prefix retrieves its corresponding ending. Each block's two margins below follow that order. Single-cue, uncued and 0.1-, 1- and 3-second inter-cue comparisons remain in the complete analysis.

{prefix_table}

## Original temporal readout

{full_qualified} The historical batch had zero converged windows among its 452 cued tests. This target is scored independently with the same rule.

{classification_table}

Activation peaks measure a mechanism effect, while temporal classification tests whether the original readout forms a qualified window. Their scores and denominators remain separate. Pre-cue structure, uncued activity and 64 residual-activity subtractions are included in analysis.json for condition-level recalculation.

## Scientific conclusions and meaning for ThreeMind

{meaning}

The controlled comparisons distinguish the connection effects left by experience from their expression under current resource conditions. Each of the four targets receives its own conclusion under the original rules. Temporal-readout scores do not replace mechanism results, and one configuration does not stand for all configurations. {short_en}

## Verification, cost and evidence

Read-only analysis verified 592 stages, 4,746 complete states, 41,248 inputs, 192 pre-cue structural records and four observation controls, creating and advancing no Core. Independent high-precision integration differed by at most {a['maximum_arithmetic_error']:.6g}. Normal and lower-frequency observation, restoration and host pauses preserved identical complete final states in apparatus qualification.

Formal execution took {summary['wall_seconds']/60:.2f} minutes; peak private memory was {resources['peak_private_bytes']/2**20:.2f} MiB. Comparable stage allocation ranged from {min(ratios):.3f} to {max(ratios):.3f} times the historical counterpart. Before report generation, originals occupied {storage['logical_bytes']/2**20:.2f} MiB logically and {storage['allocated_bytes']/2**20:.2f} MiB of actual allocation, including apparatus and retained writer-qualification evidence.

The original apparatus and streaming writer v2 reached the one-GiB private-memory limit and stopped at complete boundaries. Version v3 losslessly compressed cached projections. Six calibration stages had identical complete states, observer states, trajectories and decoded projection bytes, with a 756.20-MiB private-memory peak. The formal batch then started once. Originals, archive and readback each have an eight-GiB budget; system reserves remain 5/4/5/25 GiB. This storage amendment changed no Core, curriculum or score.

The read-only audit corrected two tool errors: the bus interface requires an empty pending mapping, and the four observation controls must be compared at their frozen task-node scope. All 592 final buses contained no pending inputs; all 6,008 shared task samples and eight shared complete snapshots agreed exactly. The original auditor, v2 and both failure records are retained; v3 completed the full audit. Scientific measurements and thresholds remained unchanged, and no student was rerun. Evidence is in audit-amendment-v2/proof.json and audit-amendment-v3/proof.json.

Workspace: {work.as_posix()}. Research record: {record}. Bilingual reports, protocols, tools, inputs, complete states and analysis are delivered under that record. The archive API-readback receipt is at publication/completion.json. Historical reports and the author's manuscript are preserved. Independent arithmetic here means tool verification; external researcher replication is recorded separately.
'''
    for lang,text in outputs.items():
        with (HERE/f'report.{lang}.md').open('x',encoding='utf-8') as f:f.write(text)
    print(json.dumps({'reports_created':2,'scientific_stop':d['scientific_stop'],'failed_targets':failed,
        'qualified_cued':len(qualified),'qualified_directional':len(qualified_targets),
        'qualified_correct':qualified_correct,'resources':resources,
        'storage':storage,'wall_seconds':summary['wall_seconds']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    report(p.parse_args().work.resolve())
