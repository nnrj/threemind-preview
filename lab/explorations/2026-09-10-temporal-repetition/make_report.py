"""Render descriptive figures and readable reports from this study's evidence."""
import json
import math
import statistics
from collections import Counter

from run import HERE,WORK,META,encoded

ZH={'converged':'收敛','residual_decay':'响应衰退','transient':'瞬态','oscillatory':'振荡',
    'unresolved':'未解决','censored':'截断','not_observed':'未观察',
    'tie':'并列','expected':'预期词单独领先','other':'其他词领先','unmeasurable':'覆盖不足',
    'control_no_answer':'裸名字对照'}
STAGE={'pair_20_each':'甲乙各20次','dialogue_1':'对话1轮','dialogue_3':'对话3轮',
       'review':'家系教学及复习后','final':'最终新家系后'}
ARM={'normal':'主线','crossed':'家系事实交换','swapped':'名词互换'}

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])

def write(name,text):
    (HERE/name).write_text(text.strip()+'\n',encoding='utf-8')

def render():
    data=json.loads((HERE/'analysis.json').read_bytes())
    meta=json.loads(META.read_bytes())
    audit=json.loads((HERE/'acceptance-prepublish.json').read_bytes())
    positive=[c for c in data['cases'] if c['dose']==1]
    normal=[c for c in positive if c['arm']=='normal']
    converged=[c for c in positive if c['converged']]
    scored=[c for c in converged if c['role']!='bare_name']
    counts=Counter(c['classification'] for c in data['cases'])
    outcomes=Counter(c['exclusive_outcome']['classification'] for c in scored)
    family=[c for c in positive if c['group']=='family' and c['role']=='grandfather']
    diagnostic_path=WORK/'diagnostic-continuation.json'
    diagnostic=json.loads(diagnostic_path.read_bytes()) if diagnostic_path.exists() else None

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10,
      'figure.facecolor':'#fafbf8','axes.facecolor':'#fafbf8','axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
    fields=[('metrics','nodes','节点数'),(None,'mean_edge_weight','平均连接权重'),(None,'mean_edge_stability','平均连接稳定度')]
    for seed in sorted({s['seed'] for s in data['stages']}):
        rows=[s for s in data['stages'] if s['seed']==seed and s['arm']=='normal']
        for ax,(parent,field,title) in zip(axes,fields):
            values=[s[parent][field] if parent else s[field] for s in rows]
            ax.plot([s['count'] for s in rows],values,marker='o',ms=4,label=str(seed))
            ax.set(xlabel='累计完整句子输入次数',title=title);ax.grid(alpha=.2)
    axes[0].legend(title='编码种子',fontsize=8)
    fig.suptitle('实际训练过程：每句连续20次，完整轮换3轮')
    fig.savefig(HERE/'training.png',dpi=160);plt.close(fig)

    fig,ax=plt.subplots(figsize=(9,4.3),layout='constrained')
    labels=list(STAGE);bottom=[0]*len(labels)
    for classification,color in [('converged','#187b68'),('residual_decay','#dc9a49'),('transient','#6e8ea2'),
                                ('oscillatory','#97689b'),('unresolved','#bf5949'),('censored','#999999')]:
        values=[sum(c['stage']==s and c['classification']==classification for c in normal) for s in labels]
        if sum(values):
            ax.bar(range(len(labels)),values,bottom=bottom,label=ZH[classification],color=color)
            bottom=[a+b for a,b in zip(bottom,values)]
    ax.set_xticks(range(len(labels)),[STAGE[s] for s in labels]);ax.set_ylabel('窗口数（描述计数，不是独立样本数）')
    ax.set_title('主线正刺激的时序读出分类；各阶段检验问题数不同')
    ax.legend(ncol=3);fig.savefig(HERE/'classifications.png',dpi=160);plt.close(fig)

    diag_summary=[]
    if diagnostic:
        by={(r['cue'],r['dose']):r for r in diagnostic['rows']}
        fig,axes=plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
        for cue in ['甲','Z的爷爷是谁？']:
            r=by[(cue,1.0)];zero=by[(cue,0.0)];means=[];diff=[];spreads=[]
            for point,control in zip(r['curve'],zero['curve']):
                a={n['id']:n['activation'] for n in point['nodes']};b={n['id']:n['activation'] for n in control['nodes']}
                means.append(statistics.mean(a.values()));spreads.append(max(a.values())-min(a.values()))
                diff.append(max((abs(a[k]-b[k]) for k in set(a)&set(b)),default=math.nan))
            times=[p['relative_us']/1e6 for p in r['curve']]
            axes[0].plot(times,means,label=cue,lw=1)
            axes[1].plot(times,means,label=cue,marker='.',lw=1)
            axes[2].plot(times,diff,label=cue,lw=1)
            tail=[v for t,v in zip(times,means) if t>=11]
            diag_summary.append(dict(cue=cue,original_classification=r['original_readout']['classification'],
              original_duration_s=(int(r['original_readout']['end_us'])-int(r['original_readout']['start_us']))/1e6,
              sample_count=len(times),last_mean=means[-1],late_mean_min=min(tail),late_mean_max=max(tail),
              last_node_spread=spreads[-1],maximum_positive_zero_difference=max(diff),last_positive_zero_difference=diff[-1],
              same_node_sets_all_times=all({n['id'] for n in p['nodes']}=={n['id'] for n in q['nodes']} for p,q in zip(r['curve'],zero['curve']))) )
        axes[0].set(title='持续观察12秒',xlabel='模拟秒',ylabel='全部节点平均激活')
        axes[1].set(title='末段放大：20毫秒采样',xlabel='模拟秒',xlim=(11.4,12),ylabel='全部节点平均激活')
        axes[2].set(title='正刺激与零强度：同时间比较',xlabel='模拟秒',ylabel='共同节点最大激活差')
        for ax in axes:ax.grid(alpha=.2)
        axes[0].legend(fontsize=8);fig.savefig(HERE/'continuous-observation.png',dpi=160);plt.close(fig)
        (HERE/'diagnostic-summary.json').write_bytes(encoded(diag_summary))

    intro=f'''# 时序收敛复验报告

本轮按原句式进行了足量重复，并把**时序窗口及其结束时的完整节点激活排序**置于主要位置。共完成{len(data['resources'])}个编码种子、{audit['source_runs']}个训练或对照意识，实际递送{audit['exact_training_inputs']:,}个完整短句；每个新句子首次连续20次，整组3轮。原文标点、说话人和默认感官映射全部逐帧核对通过。

时序检验共{len(data['cases'])}个独立状态副本，其中正刺激{len(positive)}个、零强度对照{len(data['cases'])-len(positive)}个；另有{sum(len(f['rows']) for f in data['secondary_fixed'])}个旧固定窗口次要检验副本。多副本和多问题不是独立种子。

主要结果：正刺激中有{len(converged)}个窗口被既有读出器判为收敛。排除不要求答案的裸名字对照后，{len(scored)}个收敛窗口的预设独有通道比较为：{'、'.join(f'{ZH[k]}{v}个' for k,v in outcomes.items())}。本轮未取得能把目标答案与对照可靠区分的收敛结果；这不等于把覆盖不足或未收敛的情况算成答错。下面同时展示其余窗口，不能把未收敛当作答错，也不能把节点编号顺序当作激活领先。

![主线读出分类](classifications.png)

完整设计见[protocol.md](protocol.md)，原始排序见[node-rankings.jsonl](node-rankings.jsonl)，每个检验对应的数据库来源和ZIP下载见[evidence-index.json](evidence-index.json)。所有结论限定于本轮参数、材料、4个编码种子和记录方式。
'''
    write('report-intro.md',intro)
    memory_rows=[]
    for c in positive:
        if c['group']!='pair':continue
        values=c['exclusive_scores']
        memory_rows.append([c['seed'],ARM[c['arm']],STAGE[c['stage']],c['cue'],ZH[c['classification']],
          f"{c['duration_s']:.1f}",'; '.join(f"{t}={v['value']:.9f}" if v['value'] is not None else f"{t}=覆盖不足({v['observed_channels']}/{v['channels']})" for t,v in values.items()),
          ZH[c['exclusive_outcome']['classification']]])
    memory='''# 配对与问答

强度排序直接依据原始 `last_activation`，没有使用AI解码，没有拿窗内累计量冒充结束强度。下表把预先固定的词对应独有通道作外部摘要；完整节点（包括非候选节点）全部保留。覆盖不足意味着这个词在该阶段不能按此指标完整测量，不能填零、不能算答错。

'''+table(['种子','条件','阶段','线索','窗口分类','秒','终态词通道平均激活','比较'],memory_rows)
    who=Counter(c['exclusive_outcome']['classification'] for c in positive if c['group']=='who' and c['converged'])
    memory+=f'''

“谁是…”和“…是谁？”四种完整问句的收敛窗口比较：{'、'.join(f'{ZH[k]}{v}个' for k,v in who.items())}。其余问答窗口的分类及全部节点见原始数据。名词互换对照改变了全部教学对应，保留句式、标点和重复量；需要随对应改变的选择性结果，才支持学到了区分。本轮不能把两个目标同强度激活解释成两个问题都回答正确。广泛联想本身符合项目允许的内部活动；这里检查的是它能否在所提问题上表现出可区分的对应，不将这些联想判为应该删掉的活动。独有通道只是外部对照视图，原始读出没有因此删去任何节点。

![训练状态](training.png)

刺激确实形成并反复作用于网络；节点、连接权重、稳定度的实测变化如图。连接形成或增强本身，与能否在测试时区别答案，是两个分别检验的问题。
'''
    write('memory-record.md',memory)
    family_rows=[]
    for c in family:
        values=c['exclusive_scores']
        family_rows.append([c['seed'],ARM[c['arm']],c['cue'],c['exclusive_outcome']['expected'],ZH[c['classification']],
          f"{c['duration_s']:.1f}",'; '.join(f"{t}={v['value']:.9f}" if v['value'] is not None else f'{t}=覆盖不足' for t,v in values.items()),ZH[c['exclusive_outcome']['classification']]])
    fam='''# 未见名字家系

教学中重复了两套完整家系及“父亲的父亲是爷爷。”。随后只教Z/Y/X、W/V/U的两代父亲事实，没有教对应爷爷答案。交叉对照交换中间父亲事实，使预期答案交换，同时保持字符总频次一致。所有新事实每句连续20次、3轮。

'''+table(['种子','条件','问题','应随事实激活的名字','窗口分类','秒','终态名字通道平均激活','比较'],family_rows)
    fam+='''

每个家系还检验“父亲是谁？”和单独名字。裸名字没有唯一正确答案，只作为活动对照，未纳入正确数。完整明细包括已教家系、父亲问题、裸名字和所有零强度副本，见 analysis.json。未见家系的可靠证据需要区分祖父与父亲、无关家系，并随交换后的事实改变；同强度共同激活不能满足这一点。
'''
    write('family-record.md',fam)
    example=next(c for c in family if c['seed']==41701 and c['arm']=='normal')
    raw='''# 如何解释读出及其限制

本轮有两个需要明确区分的对象：**全部内部活动**，以及**相对既有基线的新响应**。当前时序读出器使用后者的稳定性和衰退情况分类，保留的完整节点数据则包含前者。源码中 `series.total` 是达到读出门槛的超基线响应之和，`series.active_node_count` 也是这类响应节点的数量；不能把它们标为全部激活及全部活跃节点。全部节点的结束活动使用 `nodes[].last_activation` 核对。因此 `residual_decay` 不是“意识消失”，`transient` 也不是“没有内部活动”。

例如种子41701最终检查点，输入“Z的爷爷是谁？”：

'''+f"- 原窗口分类：{ZH[example['classification']]}；长度{example['duration_s']:.1f}秒。\n- 窗口末有{example['active_at_end']}/{example['nodes']}个节点活动；最小与最大激活分别为{example['end_min']:.12f}、{example['end_max']:.12f}。\n- 原始节点按结束强度排序，以下保留并列名次；只是完整数据的前12行展示。\n\n"+table(['并列名次','节点','通道','结束激活','读出候选'],[[n['rank'],n['node_id'],n['channel'],f"{n['activation']:.12f}",n['candidate']] for n in example['top_end']])
    raw+='''

“综合排名”是原读出器将持续时间、尾段活动和超基线强度等合成的分数；它不等同于结束激活强度，原始数据中另列，不曾替换本轮主排序。小于1e-12的数值差异按并列处理，防止浮点误差制造一个赢家。
'''
    if diag_summary:
        raw+='\n\n## 窗口结束后继续观察\n\n补充设计在运行前另存实验笔记。固定41701最终检查点、两条线索及零强度对照，共4个副本，持续观察12秒，每20毫秒保存全部节点。它是额外的连续观察，不改原窗口分类。\n\n'+table(['线索','原窗口秒数','样本数','末1秒平均活动范围','12秒节点强度跨度','12秒正刺激/零强度最大差'],[
          [d['cue'],d['original_duration_s'],d['sample_count'],f"{d['late_mean_min']:.9f}～{d['late_mean_max']:.9f}",f"{d['last_node_spread']:.3g}",f"{d['last_positive_zero_difference']:.3g}"] for d in diag_summary])
        raw+='''

![持续观察与更细采样](continuous-observation.png)

原读出器100毫秒采样与默认100毫秒传播周期相同，可能只看到周期的同一个位置。上图将20毫秒实测样本单独展示：周期内部波动和节点之间的差异是两个维度，应分别判断。“窗口收敛”不能扩展解释成连续时间里每个节点完全不再变化。
'''
    write('reader-record.md',raw)
    fixed_summary=[]
    for f in data['secondary_fixed']:
        sham=next(r for r in f['rows'] if r['cue'] is None)
        diffs=[]
        for r in f['rows']:
            if r['cue'] is None:continue
            diffs.extend(abs(v-sham['endpoint'][t]) for t,v in r['endpoint'].items() if v is not None and sham['endpoint'].get(t) is not None)
        fixed_summary.append(dict(seed=f['seed'],group=f['group'],max_abs_difference=max(diffs) if diffs else None))
    (HERE/'fixed-secondary-summary.json').write_bytes(encoded(fixed_summary))
    conclusion=f'''# 结论、边界和下一步

本轮检验的是：在保持完整说话人场景、原文标点、默认映射和足量逐句重复的情况下，时序读出能否在题目结束后提供有区别的答案活动。**出现收敛窗口不自动等于学会回答；不被读出器判为收敛，也不自动等于没有意识活动。** 上述表格保留两类事实。

本次没有验证到稳定的配对选择或未见家系组合。多数可测的目标词通道终态等强，换问题或交换教学对应后，没有出现能支持正确答案单独领先的结果。这个结论不表示模型完全没有结构记忆，也不表示内部联想没有意义。

两个固定线索的补充观察中，输入到达时确有即时激活差异；在20毫秒样本中，随后正刺激与零强度的节点激活强度轨迹一致，持续到12秒。节点仍共同在约0.744045至0.967683之间起伏，属于持续活动。原100毫秒读出采样看不到周期内部的这段起伏；此测量限制已经单独记录，未靠改分类制造结论。

当前结果需要优先关注活动的区分度、局部连接变化与读出判定边界，而不是先追加更多训练规模。若目标词在实际完整节点终态里同强度，并且零强度或交换对应后仍缺少相应变化，单靠换一个词分数不能获得选择性答案。若只是模板覆盖不足，则应归入测量限制，不归入能力失败。

旧固定窗口探针仅作次要参照：

{table(['种子','检验组','与等时无输入对照的最大绝对积分差'],[[f['seed'],f['group'],f['max_abs_difference']] for f in fixed_summary])}

后续建议（本轮没有实施）：

1. 保持每句足量重复，先用小型实验逐项检查刺激间隔、增益、传播与抑制/遗忘参数如何影响节点活动区分度；不能把“减少重复”当作本轮已经验证的解决方案。
2. 给时序读出同时明确呈现“相对基线的响应”和“全部活动的稳定/振荡”，并检查采样周期与传播周期重合产生的测量盲区。候选节点、完整原始节点、综合分数和终态强度继续分开记录。
3. 检查连接趋于高权重与大范围等强活动之间的关系。二者同时出现不等于已证明因果；若做消融，应保留原机制作为对照，不据本轮结果擅自改Core。
4. 先在配对问题上获得能随对应互换改变、并能与零强度和无关线索区别的结果，再扩展家系规则和训练规模。4个种子不代表所有参数、所有训练方法。本轮也只有文本感官教学，没有躯体、物理互动或多模态经验，不能据此断言AGI不可行或已经实现理解。

## 实际资源与复现

- 训练与检验累计墙钟时间：{audit['cumulative_training_probe_seconds']/60:.2f}分钟；补充连续观察{diagnostic['elapsed_s']:.2f}秒（如上）。
- 训练进程峰值RSS：{audit['peak_rss']/2**20:.1f} MiB；验收前数据库增长{audit['database_growth_bytes']/2**20:.1f} MiB，本轮本地证据{audit['local_evidence_bytes']/2**20:.1f} MiB。预算4 GiB，仍有余量；出版后的实测见acceptance.json。
- 额度起点为总量已用72%，停算线90%；期间账户工具读数保存在quota-monitor.json。读数为账户共享且可能滞后的百分比，不能据整数未变化声称没有消耗。
- 内核causal/9、state/6、TextSensor默认配置、读出实现均未修改，已比较源码与原生二进制摘要。原训练状态不被探针写回，旧项目元数据核对未变。
- 逐条核对了{audit['exact_training_inputs']:,}个存储输入的原文、重复量、默认编码结果、计划时刻及实际递送时刻；训练期保存{audit['training_temporal_windows']:,}个时序窗口。独立检验保存完整原始ZIP、源检查点和全部窗口分类。
- 计划、补充观察计划、记录、报告与原始证据均在独立项目“时序收敛复验：逐句20次与未见家系（2026-09-10）”中，项目ID `{meta['project_id']}`。复现入口见README.md。
'''
    write('report-conclusion.md',conclusion)
    write('report.md','\n\n'.join([intro,memory,fam,raw,conclusion]))
    write('report.en.md',f'''# Temporal readout replication: repeated complete sentences and unseen families

The registered curriculum preserved all speakers, punctuation and the default sensory mapping (NFKC; anonymous-distributed; 192 channels). Each new sentence was presented **20 consecutive times before switching**, over three complete rounds. Four independent encoding seeds were planned; {len(data['resources'])} completed result files are included. We stored and audited {audit['exact_training_inputs']} training deliveries across {audit['source_runs']} source/branch consciousnesses.

The primary evidence is each actual temporal window and its complete recorded nodes sorted by final activation. Ties are retained (1e-12 tolerance); node IDs never break scientific ties. Existing composite ranking, peaks, integrals and fixed-window probes are secondary. A converged window is not synonymous with a correct answer. Non-converged and unmeasurable cases are retained.

There were {len(data['cases'])} temporal probe copies, including {len(positive)} positive-dose copies and equally sized zero-dose controls. Recorded classifications: {dict(counts)}. Among the {len(scored)} converged positive-dose windows that ask for a specific answer, prespecified exclusive-channel outcomes were {dict(outcomes)}. These are descriptive counts within {len(data['resources'])} seeds, not independent statistical replicates.

The full Chinese report contains every pair and unseen-grandfather test in readable tables. analysis.json retains all questions, controls, classification/coverage data and word-channel projections; node-rankings.jsonl retains complete raw-node strength rankings plus the original composite ordering and time series. Missing sensory-template channels are not silently zero-filled. Word projections are an external measurement, not generated speech or proof of semantics.

Important distinction: the existing reader classifies changes above a pre-input baseline; residual_decay/transient do not mean that internal activation has disappeared. In the seed41701 final grandfather example, {example['active_at_end']}/{example['nodes']} nodes remained active, with ending activation from {example['end_min']:.12f} to {example['end_max']:.12f}. Identical ending strengths cannot rank one answer ahead of another.

The predeclared follow-up observed four independent full-state copies for 12 simulated seconds at 20 ms intervals while preserving the original 100 ms temporal-reader output. See diagnostic-plan.md, diagnostic-summary.json and the complete diagnostic evidence for measurements after the original window ended and within a propagation period. It does not relabel the original windows.

The study made no Core, sensory, or reader-algorithm changes. Full-state probes inherited activation, queues, baseline history and ongoing plasticity; they never wrote back to training sources. Training/probing took {audit['cumulative_training_probe_seconds']/60:.2f} minutes; peak training process RSS was {audit['peak_rss']/2**20:.1f}MiB. Prepublication DB growth was {audit['database_growth_bytes']/2**20:.1f}MiB. The study stayed within its 4 GiB storage budget, 30-minute computation limit and the monitored account-allowance stop rule. Account percentage readings are shared/lagged, not exact token accounting.

The findings are limited to these defaults, carriers, seeds and measurement definitions. They neither establish relational reasoning nor demonstrate that AGI is impossible. Future work should examine local activity differentiation, connection-weight dynamics and observation cadence with controlled parameter changes while preserving sufficient contiguous repetitions.
''')
    print('Reports, descriptive figures and secondary summaries generated.')

if __name__=='__main__':render()
