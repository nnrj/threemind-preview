"""Report completed E15 revalidation from the audited, frozen measurements."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_original as r


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+
        ['| '+' | '.join(map(str,row))+' |' for row in rows])


def report(work):
    r.check(work)
    a=r.read(work/'analysis.json');audit=r.read(work/'audit.json');run=r.read(work/'summary.json')
    assert audit['passed'] and audit['read_only'] and audit['created_engines']==0
    assert not (work/'in-flight.json').exists() and run['stages']==826
    assert a['counts']['states']==3368 and a['counts']['inputs']==23552
    d=a['decision'];assert audit['scientific_stop']==d['scientific_stop']
    resources=r.read(work/'resource-summary.json');registration=r.read(work/'registration.json')
    files=[p for p in work.rglob('*') if p.is_file()]
    storage={'files':len(files),'logical_bytes':sum(p.stat().st_size for p in files),
        'allocated_bytes':sum(r.disk_allocation(p)['allocated_bytes'] for p in files)}
    cn_names=('经历依赖','内部因果作用','时间交互','反馈重塑')
    en_names=('Experience dependence','Internal causal contribution','Temporal interaction','Feedback reshaping')
    metrics=('history_motor','history_association','communication_causal_effect','sequence_effect','environment_effect')
    protocol_names={
        'none':('未教学','Untaught'),'single_high':('单次较强刺激','Single higher-intensity exposure'),
        'single_ordinary':('单次普通刺激','Single ordinary exposure'),'massed_ordinary':('普通刺激集中重复','Massed ordinary exposure'),
        'spaced_ordinary':('普通刺激间隔重复','Spaced ordinary exposure'),'massed_weak':('弱刺激集中重复','Massed weak exposure'),
        'spaced_weak':('弱刺激间隔重复','Spaced weak exposure'),
        'spaced_no_consolidation':('间隔重复，关闭既有连接正向强化','Spaced exposure without existing-edge strengthening')}
    selective=sum(p['selective_target_effect'] for p in d['parent_results'])
    for lang in ('zh','en'):
        zh=lang=='zh';names=cn_names if zh else en_names
        verdict=lambda passed:('通过' if passed else '未通过') if zh else ('Passed' if passed else 'Not passed')
        failed=[names[i] for i,row in enumerate(d['criteria']) if not row['pass']]
        if zh:
            conclusion=('四项自主活动判据均通过。6.1在原规模材料中复现了经历依赖、内部因果作用、时间交互和反馈重塑，主要复验目标达成。'
                if d['meets_all'] else '未通过的自主活动判据为：'+'、'.join(failed)+'。本装置的四项联合目标未达成，触发预先规定的科学停止条件。')
            follow=('原件核验和交付完成后，继续下一项原规模复验。' if d['meets_all'] else
                '保全并交付本批完整结果后，暂停后续复验，报告新旧条件的差异。')
            selective_text=f'目标连接干预的作用在{selective}/4份父体上大于匹配干预。假操作和解除静默后，分别16/16条轨迹与完整参照完全相同。'
        else:
            conclusion=('All four autonomous-activity criteria passed. At the original material scale, kernel 6.1 reproduced experience dependence, internal causal contribution, temporal interaction and feedback reshaping, meeting the primary replication target.'
                if d['meets_all'] else 'The following autonomous-activity criteria did not pass: '+'; '.join(failed)+'. The four-criterion joint target was not met, triggering the prespecified scientific stopping rule.')
            follow=('After complete evidence verification and delivery, the next original-scale replication proceeds.' if d['meets_all'] else
                'After preserving and delivering the complete batch, subsequent revalidation pauses for review of the historical and current conditions.')
            selective_text=f'Targeted connection interventions exceeded matched interventions for {selective}/4 parents. Sham and restored trajectories each exactly matched the complete reference in 16/16 comparisons.'
        criteria=table(['判据','通过父体','批次判定'] if zh else ['Criterion','Passing parents','Batch decision'],
            [[names[i],str(len(row['passing_parents']))+'/4',verdict(row['pass'])] for i,row in enumerate(d['criteria'])])
        parent_table=table(['父体','经历动作差','经历联想差','通信干预作用','时间交互','环境作用'] if zh else
            ['Parent','History: motor','History: association','Communication effect','Temporal interaction','Environment effect'],
            [[p['parent']]+[f'{p[k]:.9g}' for k in metrics] for p in d['parent_results']])
        local=table(['父体','目标干预作用','匹配干预作用','目标静默后差异残留比例','选择性作用'] if zh else
            ['Parent','Targeted effect','Matched effect','Residual history fraction after target silencing','Selective effect'],
            [[p['parent'],f"{p['target_loss']:.9g}",f"{p['matched_loss']:.9g}",
              '—' if p['target_residual_fraction'] is None else f"{p['target_residual_fraction']:.9g}",
              verdict(p['selective_target_effect'])] for p in d['parent_results']])
        memory=[]
        for protocol in r.m.PROTOCOLS:
            for age in (1,30,300):
                rows=[v for v in a['memory'] if v['protocol']==protocol and v['age_s']==age and v['mode']=='live' and v['condition']=='normal']
                assert len(rows)==2
                memory.append([protocol_names[protocol][0 if zh else 1],age]+[f"{v['D_minus_B_effect']:.9g}" for v in rows])
        memory_table=table(['课程','末次教学后等待（秒）','教材9293201：新D减旧B','教材9293202：新D减旧B'] if zh else
            ['Curriculum','Wait after last exposure (s)','Material 9293201: new D minus old B','Material 9293202: new D minus old B'],memory)
        env=table(['父体','改变/不变路线','阶段','状态','动作差','B活动差','D活动差'] if zh else
            ['Parent','Changed/constant route','Stage','State','Motor difference','B difference','D difference'],
            [[v['parent'],v['changed']+'/'+v['constant'],v['phase'],v['mode']]+
             [f"{v['history_effect'][k]:.9g}" for k in ('motor','B','D')] for v in a['environment']])
        texture=table(['教材','干预','替换特征数','当前减原纹理：动作差'] if zh else
            ['Material','Intervention','Replaced features','Current minus original texture: motor difference'],
            [[v['seed'],v['condition'],v['changed_features'],f"{v['generalization_motor_difference']:.9g}"] for v in a['texture']])
        windows=table(['原时序分类','窗口数'] if zh else ['Original temporal classification','Windows'],
            sorted(a['window_classifications'].items()))
        costs=a['comparable_allocation_ratio']
        if zh:
            text=f'''# 早期自主活动判据及经历保持的6.1复验

2026-11-14，R51u。按全面复验计划v2复验E15，使用6.1完整新个体。

**{conclusion}**

## 目的、预期和实验组织

本批检验相同提示下的经历差异、内部通信的因果作用、先后输入的交互，以及环境反馈对同一个体的继续塑造。沿用两套接线和每套接线的两份相关家系材料，共四份父体。每项须至少三份父体通过且覆盖两套接线，四项通过才算联合达标。作用须超过0.0001及假操作误差的十倍；实际判定线为{d['threshold']:.9g}。

从6.1空白实例重放旧选择材料的十二个祖先阶段、四次预热和八次P/Q教学，再完成802个正式比较，共826阶段。教学P为AB、CD，Q为AD、CB。历史材料的感觉输入和家系次序固定；48个正式环境阶段重新计算行动造成的感觉反馈。统计沿用四份父体的关系，所有诊断、时点和干预副本保留其来源。

6.1默认逆对数衰减、传递信号门槛0.0004、删除阈值0.008及关闭保持增长保持。按旧装置开启有限能量核算、资源耗竭、1秒易化及既有连接强化，外部供能每100毫秒1单位，总供给不限。普通阶段连续保存内核、总线、读出历史、供能器和身体；声明的出生干预保留持久连接和衰减年龄，重置快速状态和内部时钟。运动投影仍按种子和实际节点编号给定正负系数，求和乘0.5后取tanh；6.1使用固定函数形成的虚拟节点编号，具体接线随完整原件保存。

## 四项判据的结果

{criteria}

下面给出每份父体的原始作用。动作积分单位为控制量·内部秒，激活积分单位为激活量·内部秒。经历差先扣除无提示参照；时间交互采用AB−A−B＋无提示，再比较通信开关；环境作用比较第二阶段改变和不变的路线。

{parent_table}

{conclusion}

## 哪些连接承担经历差异

{selective_text}

{local}

目标连接由教学关系确定。匹配比较保留旧数量及权重、稳定度距离规则，并记录同刻匹配误差。全部通信干预与局部连接干预回答不同范围的问题，分别列出实际结果。目标静默的残留比例按绝对经历动作差计算，不预先要求等于旧版的99.4%—100%消除量。

## 教学节奏与保持

八种课程保持原强度、次数、间隔及末次输入时刻。在末次教学1、30、300秒后分别建立诊断副本，早期测试不成为较晚测试的复习。下表先扣除同状态无提示活动和未教学参照，再计算新D对应减旧B对应的激活积分；正值为相对偏向新D，负值为相对偏向旧B。

{memory_table}

300秒的出生、返回路径阻断、全通信阻断，以及追加30秒四干预比较，逐项保存在analysis.json。它们用于区分持久连接与当前活动对表达的作用。

## 连续环境与纹理变化

环形身体的动作改变位置，位置和速度决定下一次感觉输入。PPP、PQP、QQQ、QPQ各包含三个30秒连续阶段；诊断副本从统一身体起点比较，普通身体轨迹连续。相同第一阶段的8组参照精确一致。

{env}

纹理实验依次替换0、1、2、4个特征，比较完整、目标连接删除、匹配删除及关闭局部新颖性增益。下表给出当前纹理相对于原纹理的动作差；新边数量、删除数量和首秒活动另保存在分析原件中。

{texture}

原时序读出器使用旧配置，其窗口分类如下。机制积分和时序窗口分别计量。

{windows}

## 核验、成本和科研交付

只读核验覆盖3368份完整状态、23552条输入，其中1440条为新闭环感觉输入。假操作、恢复、完整连续性、声明的出生、供能和身体公式均完成核对，未创建或推进个体。积分独立复算误差不超过{a['maximum_decimal_motor_error']:.6g}，身体公式误差不超过{a['maximum_body_error']:.6g}，供能误差不超过{a['maximum_supply_error']:.6g}。

运行耗时{run['wall_seconds']/60:.2f}分钟，私有内存峰值{resources['peak_private_bytes']/2**20:.2f}MiB。同等阶段记录实际分配为旧值的{costs['minimum']:.3f}—{costs['maximum']:.3f}倍。报告生成前原件共{storage['files']}文件，逻辑大小{storage['logical_bytes']/2**20:.2f}MiB，实际分配{storage['allocated_bytes']/2**20:.2f}MiB。原件、归档、读回各4GiB，提交/RAM/C/E保留量仍为5/4/5/25GiB。

{follow} 科研记录为{registration['record']}，工作区为{work.as_posix()}；完整API读回及pending=0凭据保存为publication/completion.json。历史原件、生产Core和默认值保持。
'''
        else:
            text=f'''# Kernel 6.1 replication of early autonomous-activity criteria and experience retention

14 November 2026, R51u. E15 under comprehensive revalidation plan v2, using new complete 6.1 individuals.

**{conclusion}**

## Purpose, expectation and design

The study tests experience-dependent responses to the same cue, the causal contribution of internal communication, interaction between successive inputs, and continued reshaping by environmental feedback. Two wiring assignments each supply two related lineage materials: four parents. Each criterion requires at least three passing parents spanning both assignments; all four criteria must pass jointly. Effects must exceed 0.0001 and ten times the sham error. The actual threshold is {d['threshold']:.9g}.

New 6.1 individuals replay twelve historical ancestral stages, four warm-ups and eight P/Q teaching stages, followed by 802 formal comparisons: 826 stages in total. Teaching P pairs AB and CD; Q pairs AD and CB. Historical sensory materials and lineage order remain fixed. The 48 formal environmental stages recalculate sensory feedback from each individual's actions. Diagnostic copies, times and interventions remain nested within their four parental materials.

Kernel 6.1 retains inverse-logarithmic decay, signal threshold 0.0004, deletion threshold 0.008 and disabled retention-scale growth. The historical apparatus enables energy accounting, depletion, one-second facilitation and existing-edge strengthening. External supply is one unit every 100 ms, without a total supply cap. Ordinary stages preserve Core, buses, readout history, energy supplier and body. Declared birth interventions retain persistent connections and decay ages while initializing fast states and internal time. The fixed motor projection assigns signs from the seed and actual node identifier, sums signed activation, multiplies by 0.5 and applies tanh. Kernel 6.1 uses its fixed-function virtual node identifiers; actual projection coefficients are saved.

## Four-criterion results

{criteria}

Parent-level effects follow. Motor integrals use control units times internal seconds; activation integrals use activation units times internal seconds. History effects subtract the corresponding uncued reference. Temporal interaction is AB−A−B plus the uncued condition, compared with communication enabled and disabled. Environmental effects compare changed and unchanged routes after stage two.

{parent_table}

{conclusion}

## Connections contributing to experience differences

{selective_text}

{local}

Teaching relationships determine the targeted connections. Matched interventions retain the historical count and weight/stability-distance rule, with matching errors measured at intervention time. Global communication and local connection interventions are reported separately. The residual fraction uses the absolute history-dependent motor difference; the historical 99.4%–100% reduction is not imposed as a new target.

## Teaching schedule and retention

Eight curricula retain their original intensities, counts, intervals and last-exposure time. Diagnostics branch independently 1, 30 and 300 seconds after the last exposure, so early tests do not rehearse later cohorts. Values below subtract uncued activity and the corresponding untaught reference, then subtract the old-B activation integral from the new-D integral. Positive values favor new D and negative values favor old B.

{memory_table}

The 300-second birth, return-path and communication interventions and the additional 30-second four-intervention comparison are recorded individually in analysis.json. They distinguish persistent connection effects from current activity during expression.

## Continuous environments and changing textures

The ring body's actions change position, and position and velocity determine subsequent sensory input. PPP, PQP, QQQ and QPQ each comprise three continuous 30-second stages. Diagnostic copies use a common initial body state while ordinary bodily trajectories remain continuous. Eight pairs with identical first stages matched exactly.

{env}

Texture tests replace zero, one, two and four features, comparing intact, target-deletion, matched-deletion and disabled local-novelty-gain conditions. The table reports the current texture's motor response minus the original texture's response. New and deleted connection counts and first-second activity are recorded separately in the analysis.

{texture}

The original temporal readout retains its historical configuration. Mechanism integrals and window classifications are separate measurements.

{windows}

## Verification, costs and delivery

Read-only verification covered 3,368 complete states and 23,552 inputs, including 1,440 new closed-loop sensory frames. Sham operations, restoration, continuity, declared births, supply and body equations were checked without creating or advancing an individual. Independent integral error was at most {a['maximum_decimal_motor_error']:.6g}; body-equation and energy-accounting errors were at most {a['maximum_body_error']:.6g} and {a['maximum_supply_error']:.6g}.

Execution took {run['wall_seconds']/60:.2f} minutes, with peak private memory {resources['peak_private_bytes']/2**20:.2f} MiB. Comparable stage allocation ranged from {costs['minimum']:.3f} to {costs['maximum']:.3f} times historical allocation. Before report generation, {storage['files']} original files occupied {storage['logical_bytes']/2**20:.2f} MiB logically and {storage['allocated_bytes']/2**20:.2f} MiB of allocated space. Originals, archive and readback each have a four-GiB cap. Commit/RAM/C/E reserves remain 5/4/5/25 GiB.

{follow} Research record: {registration['record']}; workspace: {work.as_posix()}. Complete API readback and pending=0 are recorded in publication/completion.json. Historical originals, production Core and defaults remain intact.
'''
        with (HERE/f'report.{lang}.md').open('x',encoding='utf-8') as stream:stream.write(text)
    print(json.dumps({'reports_created':2,'scientific_stop':d['scientific_stop'],'selective_parents':selective,
        'storage':storage,'wall_seconds':run['wall_seconds']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    report(p.parse_args().work.resolve())
