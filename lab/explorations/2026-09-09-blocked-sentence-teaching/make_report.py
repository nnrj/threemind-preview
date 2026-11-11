"""Build factual report sections from evidence; interpretations are reviewed separately."""
import json

from run import HERE, META, encoded


def fmt(value):
    return '无法评分' if value is None else f'{value:.8g}'


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])


def build():
    s = json.loads((HERE/'summary.json').read_bytes())
    a = json.loads((HERE/'acceptance-prepublish.json').read_bytes())
    meta = json.loads(META.read_bytes())
    m = json.loads((HERE/'measurements.json').read_bytes())
    intro = f'''# 逐句重复教学：完整说话人与祖父关系

实验日期：2026-09-09。项目：**逐句重复教学：完整说话人与祖父关系 · 2026-09-09**。
项目编号：`{meta['project_id']}`。

## 这次实际怎样教

每句先连续发送 **20次**，然后才换下一句。用户给出的10条对话句，按原顺序完整练习3轮，每句60次；家系及规则7条短句也完整练习3轮，每句60次；随后10条对话各回顾5次；最后学习新家系4条短句，每句连续20次、3轮，共240次。每个正式意识累计 **1,310次输入、1,048模拟秒（17分28秒）**。

| 阶段 | 连续重复与轮数 | 阶段输入数 | 累计输入数 |
| --- | --- | --- | --- |
| 原文对话 | 每句20次 × 10句 × 3轮 | 600 | 600 |
| 两个已教家系及规则 | 每句20次 × 7句 × 3轮 | 420 | 1020 |
| 对话回顾 | 每句5次 × 10句 | 50 | 1070 |
| 新家系两条链 | 每句20次 × 4句 × 3轮 | 240 | 1310 |

`甲是松子。`等10条原文的说话人、字词、成分、标点全部保留。`C的父亲是B`等4条用户家系示例没有句末标点，也原样保留。最长训练句17字符，所有训练句均为一个完整输入帧；没有拆开问答、没有去除说话人、没有拼接成长文本。完整逐句清单见`protocol.md`与`curriculum.json`。

4个固定编码种子为41701至41704。每个种子在前1070次输入后另取一个完整状态副本，仅交换新家系中X/U的位置作为对照，仍完整重复。原方案共交付6,200条训练载体，形成4个正式意识、4个同源家系对照；统计独立单位是4个种子。

完成原方案后，针对结构副本出现的正向配对偏好，先登记补充方案，再用前两个固定种子增加2个完整的名词配对互换对照：从空白开始，把所有对话中的松子/铃铛一致互换，其他内容及20次重复安排不动。每个仍1310次输入。它是预先登记后执行的探索性跟进，不冒充最初方案。本轮含此补充共交付 **{a['exact_training_frames']:,}条训练载体**，共10个数据库意识。

## 实现与检验约束

Core causal/9保持默认参数；匿名分布式感官192通道，输入强度1，间隔0.8模拟秒。为保留全角标点，显式关闭感官NFKC规范化，设置`normalization=none`。与上轮还存在句式、教学安排和测量方式差异，跨轮差异不能全部归因于重复次数。

主检验保留训练后的激活、抑制、时钟与在途信号，在同一恢复点分别接收各个问题；无问题对照也从同一点开始。等待时间0，检验副本保持学习开启，测试结果不写回正式意识。辅助测量清空活动后从继承结构出生，单独报告。两者没有混成一种结论。

观察0—1秒的全部节点活动，主摘要为0.2—1秒积分平均减无提示对照；0—0.2秒摘要及原始曲线也保存。评分才排除共享通道和问题直接触达的通道；原始活动完整保存。无法形成独占观察通道的案例标记为无法评分，不填零、不换种子。饱和不作为取消教学的条件。

4个种子的小规模结果采用描述统计，没有确认性p值或“理解准确率”。数值等于零的判定容差1e-12只用于浮点比较，不代表心理或生物学阈值。词投影是外部测量，不是自动生成的自然语言回答。
'''
    (HERE/'report-intro.md').write_text(intro, encoding='utf-8')
    selected = [r for r in s['training_anchors'] if r['count'] in [20, 40, 600, 1310]]
    training = '## 连接在重复和后续教学中怎样变化\n\n' + table(
        ['种子', '累计输入', '节点/边', '最初端点对仍有连接', '这些边平均权重', '这些边平均稳定度'],
        [[r['seed'], r['count'], f"{r['metrics']['nodes']}/{r['metrics']['edges']}",
          f"{r['retained_first_sentence_edges']}/{r['first_sentence_edges']}",
          fmt(r['anchor_mean_weight']), fmt(r['anchor_mean_stability'])] for r in selected])
    training += ('\n\n观察集合来自第20次输入后的连接端点，程序没有给予保护。表中端点对仍有连接的数量，'
                 '可能包含原边消失后在同一端点重新形成的边，不能据此声称它始终存在。'
                 '为区分二者，额外读取已保存模型中的连接出生时间，得到下表。'
                 '此项核查在发现端点数量可重新增加后补充，未改变训练或预定联想指标。'
                 '每个重复块的完整统计见`training-traces.json`。\n\n![训练连接轨迹](training.png)\n')
    if (HERE/'edge-continuity.json').exists():
        identities = json.loads((HERE/'edge-continuity.json').read_bytes())['rows']
        training += '\n\n' + table(['种子','累计输入','原出生连接仍在','同端点重建','端点已无连接','全部边中权重已达1'],
            [[r['seed'],r['count'],f"{r['same_birth_edges']}/{r['original_edges']}",
              r['recreated_endpoint_edges'],r['missing_endpoints'],f"{r['edges_at_weight_one']}/{r['total_edges']}"]
             for r in identities if r['count'] in [200,600,1310]]) + '\n'
    memory = '## 配对与问答的分阶段检验\n\n'
    memory += ('表中数值是预期对象减另一个对象的净活动差：配对检查甲→松子、乙→铃铛；'
               '问答检查四个“谁是/是谁”问题。正值表示这个外部投影更偏向预期对象，零不代表无活动。\n\n')
    labels = {'pair_20_each':'各20次后', 'dialogue_1':'对话第1轮后', 'dialogue_3':'对话第3轮后',
              'review':'家系学习及回顾后', 'final':'新家系学习后'}
    for route, title in [('continuation', '主检验：保留当前活动'), ('birth', '辅助：清空活动的结构出生副本')]:
        rows = [r for r in s['aggregates'] if r['arm']=='normal' and r['group'] in ['pair', 'who'] and r['route']==route]
        memory += '### ' + title + '\n\n' + table(
            ['阶段', '检查', '平均差', '正方向种子/可评分种子', '预期对象较强/可评分问题'],
            [[labels[r['stage']], '配对' if r['group']=='pair' else '问答', fmt(r['mean']),
              f"{r['positive_seeds']}/{r['complete_seeds']}", f"{r['strict_target_top']}/{r['scorable_queries']}"] for r in rows]) + '\n\n'
    memory += '![分阶段配对与问答](learning.png)\n'
    if s.get('follows_swapped_pairs'):
        memory += '\n\n### 补充：配对互换后，偏向是否随教学变化\n\n'
        memory += ('互换组一致训练甲＝铃铛、乙＝松子。下面两列分别按各自教学对应计算正负：'
                   '如果只是词本身的固定偏向，互换组的“正确方向”通常反而变负；'
                   '若两列都为正，则该组活动偏向跟随了相反的教学对应。两个种子是探索性复核。\n\n')
        memory += table(['种子','测量','检查','普通组正确方向差','互换组正确方向差','事实跟随差'],
            [[r['seed'],r['route'],r['group'],fmt(r['normal_correct_margin']),
              fmt(r['swapped_correct_margin']),fmt(r['following_difference'])]
             for r in s['follows_swapped_pairs'] if r['stage']=='final']) + '\n'
    family = '## 爷爷关系与交叉家系检验\n\n'
    family += ('普通家系期待Z→X、W→U；交叉家系期待Z→U、W→X。两种情况下Z的父亲仍是Y，W的父亲仍是V。'
               '“爷爷较强”要求预期爷爷在X/Y/U/V全部可评分候选中严格最高；平局不算命中。'
               '角色区分量比较爷爷问题与父亲问题是否产生不同的爷爷/父亲活动偏向。\n\n')
    family += table(['测量', '家系', '角色区分量均值', '完整种子', '爷爷较强/可评分问题', '无法评分问题'],
        [['连续状态' if r['route']=='continuation' else '结构出生',
          '已教例子' if r['group']=='seen_family' else ('新家系' if r['arm']=='normal' else '交叉新家系'),
          fmt(r['mean']), r['complete_seeds'], f"{r['strict_target_top']}/{r['scorable_queries']}",
          r['total_queries']-r['scorable_queries']] for r in s['aggregates'] if r['group'] in ['family','seen_family']])
    family += '\n\n### 每个新家系问题的全部候选（主要0.2—1秒窗口）\n\n'
    rows = []
    for item in m:
        if item['group']=='family':
            for c in item['late']['cases']:
                rows.append([item['seed'], item['arm'], item['route'], c['child'], c['expected_grandfather'],
                             *[fmt(c['values'][k]) for k in ['X','Y','U','V']], fmt(c['target_margin'])])
    family += table(['种子','家系','测量','被问者','预期爷爷','X','Y','U','V','预期减最强其他'], rows)
    family += '\n\n### 活动是否跟随交换后的事实\n\n'
    family += table(['种子', '测量', '两个家系平均事实跟随差'],
                    [[r['seed'], r['route'], fmt(r['mean'])] for r in s['follows_crossed_facts']])
    family += ('\n\n事实跟随差先计算普通家系的原爷爷减另一个家系爷爷，再减交叉家系中相同两个名字的差；'
               '正值才表示该投影随交换事实向相应方向移动。完整种子需要两个家系都可评分。'
               '\n\n下图固定展示第一个种子41701，未按最好结果选例子。\n\n![家系完整候选曲线](family-curves.png)\n')
    if (HERE/'raw-activity-differences.json').exists():
        raw=json.loads((HERE/'raw-activity-differences.json').read_bytes())['rows']
        questions=[r for r in raw if '？' in r['cue']]
        assert all(r['last_changed_sample_us']==0 for r in questions)
        family += ('\n\n### 补充核查原始激活，避免把零差误解成没有反应\n\n'
                   '直接读取既有ZIP的全部匿名通道，不使用词评分掩码：四个种子的16个完整父亲/爷爷问题，'
                   '在到达时均有相对于无问题对照的激活变化；从下一次20毫秒采样直到1秒，全部节点的激活差均在1e-12内。'
                   '因此此处有即时输入反应，但未保持到后续采样；词评分为零不是没有输入或没有活动。'
                   '该结论只涉及这16个问题与这些采样时点，不能排除20毫秒以内的差异或其他内部状态差异。'
                   '种子41703的裸名字Z/W存在持续的其他通道差异，不能把完整问题的结果泛化到所有输入。'
                   '完整诊断见`raw-activity-differences.json`。\n')
    for name, text in [('training',training), ('memory',memory), ('family',family)]:
        (HERE/(name+'-record.md')).write_text(text, encoding='utf-8')
    resources = s['resources']
    footer = f'''## 资源与证据核对

- 累计实验进程时间：{resources['elapsed_s']:.2f}秒（{resources['elapsed_s']/60:.2f}分钟）；包含训练、测量及其数据库操作，不含写报告时间。
- {resources['source_runs']}个数据库意识，{resources['checkpoints']}个阶段恢复点，{resources['measurement_jobs']}次测量任务，{resources['probe_copies']}个探针/无提示副本。
- 采样到的单进程RSS最高{resources['max_process_rss']/1024**2:.2f} MiB；不是整机或数据库服务内存峰值。
- 发布前数据库增长{a['database_growth_bytes']/1024**2:.2f} MiB，本地证据{a['local_evidence_bytes']/1024**2:.2f} MiB；最终值另见`acceptance.json`。
- 预算4 GiB、累计计算30分钟；Codex基线65%，83%停止新实验、为20个百分点上限留余量。最终账户级观测见`quota-monitor.json`。
- 数据库逐一核对{a['exact_training_frames']:,}个训练帧：原文、全角标点、次数、发送顺序、编码后的通道、计划及实际递送时间全部一致，均已递送。
- {a['checkpoint_hashes_verified']}个恢复点摘要、{a['measurement_source_hashes_verified']}个测量来源摘要核对通过；4个固定代表ZIP中的28个最终模型和全部零/非零采样结构核对通过。
- 此前三个实验项目共{a['old_model_count']}个意识及其文档/笔记头摘要保持不变。没有清理旧数据，没有修改Core。

完整数据在ThreeMind本实验项目的恢复点与实验记录/报告中；`evidence-index.json`提供探针ZIP和结果的下载路径。`curriculum.json`保存完整发送清单，`measurements.json`包括早期窗口、晚期窗口、无提示基线和全部候选；不能只用表中的排名代替原始活动。
'''
    (HERE/'report-resources.md').write_text(footer, encoding='utf-8')
    conclusion = (HERE/'report-conclusion.md').read_text(encoding='utf-8') if (HERE/'report-conclusion.md').exists() else ''
    (HERE/'report.md').write_text('\n\n'.join([intro, training, memory, family, conclusion, footer]), encoding='utf-8')
    final=[r for r in s['aggregates'] if r['stage']=='final']
    english=f'''# Blocked sentence teaching with intact speakers and punctuation

2026-09-09. Project `{meta['project_id']}`. The full Chinese report is in `report.md`.

## Exact execution

Each complete sentence was delivered **20 consecutive times before switching**, for three full sweeps. The ten original dialogue sentences retained every speaker, component and punctuation mark. This produced 600 dialogue inputs. Seven family/rule sentences received the same schedule (420 inputs), followed by five repetitions of each dialogue sentence (50 inputs), and three 20-repetition sweeps of four held-out family facts (240 inputs). Each normal trajectory received **1,310 inputs over 1,048 simulated seconds**.

The four user family examples had no final punctuation and were preserved as supplied. Every training carrier fit one frame (maximum 17 characters). Anonymous distributed encoding used 192 channels, intensity 1 and a fixed 0.8-second interval. Unicode normalization was explicitly set to `none` so full-width punctuation was not converted. Core causal/9 defaults were unchanged.

Four fixed seeds 41701-41704 were trained. Each also had a continuation branch from the common 1,070-input checkpoint with X/U swapped in the subsequent family facts, preserving total character counts and time. After the original study completed, positive pair projections motivated a prospectively recorded follow-up using the first two fixed seeds: complete new training with pinecone/bell swapped consistently everywhere in the dialogue. Speakers, sentence form, punctuation and repetitions were unchanged. This follow-up was exploratory, not part of the original plan. There was no confirmatory statistical test in either part.

All {a['exact_training_frames']:,} delivered training frames were checked against their exact literal carrier, channel encoding and timestamp. Previous projects were not modified.

## Measurements

The primary route preserved trained activity, inhibition, clocks and in-flight events. Each query and no-query baseline used an independent continuation copy, no blank delay, and learning enabled. Auxiliary birth copies inherited structure with activity cleared. Tests never wrote back to teaching sources. Both routes sampled all nodes at 20 ms intervals for one second. The declared primary summary was the 0.2-1.0 s trapezoidal mean minus the no-query baseline; 0-0.2 s summaries were also retained.

Word masks only affect the observer score, never raw activity. Missing exclusive channels are reported as unscorable, not replaced by zero. Saturation did not cancel training. A difference tolerance of 1e-12 handles floating-point ties only. These projections are not generated language responses or calibrated language accuracy.

## Final descriptive measurements

'''
    english+=table(['Arm','Group','Route','Mean contrast','Complete seeds','Expected target strongest / scorable'],
        [[r['arm'],r['group'],r['route'],'unscorable' if r['mean'] is None else f"{r['mean']:.8g}",
          r['complete_seeds'],f"{r['strict_target_top']}/{r['scorable_queries']}"] for r in final])
    english+='\n\n## Pair-swap follow-up\n\n'
    english+=table(['Seed','Route','Group','Normal correct margin','Swapped correct margin','Following difference'],
        [[r['seed'],r['route'],r['group'],fmt(r['normal_correct_margin']),fmt(r['swapped_correct_margin']),
          fmt(r['following_difference'])] for r in s['follows_swapped_pairs'] if r['stage']=='final'])
    english+='''

## Structural and raw-activity checks

Some initial edges were removed and some endpoint pairs reconnected. Birth timestamps distinguish these cases in `edge-continuity.json`. By the 600-input checkpoint, every extant edge in all four normal trajectories had reached weight 1; the final checkpoints had the same property. This describes the sampled states, not a claim that every edge was always saturated between checkpoints.

For the 16 complete grandfather/father questions in final primary copies, the all-channel raw traces show an immediate response at input time. At the subsequent 20 ms samples through one second, their activation vectors matched the no-query baseline within 1e-12. This does not exclude sub-20 ms effects or differences in other state variables. Bare-name probes in seed 41703 had continuing differences in other channels, so the complete-question result is not generalized to every stimulus. No word mask was used for this diagnostic.

The training schedule, framing, normalization and measurement route differ from the preceding study. Cross-study differences cannot be attributed exclusively to blocked repetition. Four encoding seeds and two exploratory pair-swap controls do not establish general language understanding or role composition. Positive cases, ties, negative margins and unscorable cases are all retained.

## Interpretation

The original birth-copy probes favored the taught targets in 7/8 pair queries and 14/16 who-queries. In the two follow-up seeds, mean pair and who-query preferences reversed with the consistently swapped teaching; the swapped targets were favored in 3/4 pair queries and 7/8 who-queries. This supports a small-scale trainable reactivation preference, beyond a fixed word preference, under the tested auxiliary route. It does not establish general command of the meaning of “is” or speaker roles.

Late primary continuation measurements had zero target contrasts. The source was active and input-responsive, but the difference in sampled activation did not persist for the complete family questions. Learned reactivation preference and usable differentiation in ongoing activity must therefore be assessed separately.

Only 1/6 fully scorable novel-grandfather queries in normal birth copies had the expected grandfather strictly strongest; two additional queries were unscorable. The positive case was seed 41704, Z: X=0.85218214 versus the strongest other candidate V=0.85199378. W did not favor its expected U, and this seed's query projections did not change when the held-out family facts were crossed. This isolated case does not establish relational composition.

The next useful investigation is the transition to widespread recurrent strengthening, not an automatic increase in training scale. Preserve the explicit teaching format while isolating sensory overlap, stimulus timing/strength and existing consolidation/inhibition/decay settings one factor at a time. Inspect finer temporal or other state representations before equating a zero word projection with absent internal differentiation. No such parameter search or Core revision was performed here.

![Training](training.png)

![Pair learning](learning.png)

![Family curves](family-curves.png)

## Resources and evidence

'''
    english+=f"{resources['elapsed_s']/60:.2f} minutes of experiment-process time; {resources['source_runs']} database sources, {resources['checkpoints']} checkpoints, {resources['measurement_jobs']} measurement jobs and {resources['probe_copies']} probe/sham copies. Highest sampled process RSS {resources['max_process_rss']/1024**2:.2f} MiB. The budget remained 30 minutes and 4 GiB. Final storage and integrity checks are in `acceptance.json`; account-level quota observations are in `quota-monitor.json` and are not exact per-task billing.\n\n"
    english+='The plan, supplemental plan, three records, linked report, notebook and Markdown/HTML exports are stored in the project. `evidence-index.json` links original ZIPs and all source hashes. No Core modification, old-data migration or cleanup was performed.\n'
    (HERE/'report.en.md').write_text(english,encoding='utf-8')
    print('Factual report sections generated from verified evidence.')


if __name__ == '__main__':
    build()
