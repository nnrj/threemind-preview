"""Build tables from this project's evidence; interpretation is reviewed separately."""
import json

from run import HERE, META, DIALOGUE, USER_FAMILY


def read(name):
    return json.loads((HERE / name).read_bytes())


def fmt(value):
    if value is None:
        return '无法评分'
    if isinstance(value, float):
        return f'{value:.10g}'
    return str(value)


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(fmt(v).replace('|', '/') for v in row) + ' |' for row in rows]) + '\n'


def save(name, text):
    (HERE / name).write_bytes((text.rstrip() + '\n').encode('utf-8'))


def build():
    summary, meta = read('summary.json'), json.loads(META.read_bytes())
    measures, accept = read('measurements.json'), read('acceptance-prepublish.json')
    continuity = read('edge-continuity.json')['rows']
    raw = read('raw-activity-differences.json')['rows']
    audit = read('evidence-index.json')['input_audits']
    quota = read('quota-monitor.json')
    final = [a for a in summary['aggregates'] if a['stage'] == 'final']
    route = {'continuation': '连续状态', 'birth': '结构出生副本'}
    group = {'pair': '配对', 'who': '问答', 'family': '未见家系', 'seen_family': '已教家系'}
    arm = {'normal': '原对应', 'pair_swap': '名词互换', 'crossed': '家系互换'}
    final_table = table(['教学', '观察方式', '项目', '目标严格领先/可评分', '总提示数', '并列', '种子平均量'], [
        [arm[a['arm']], route[a['route']], group[a['group']],
         f"{a['strict_target_top']}/{a['scorable_queries']}", a['total_queries'], a['ties'], a['mean']] for a in final])
    intro = f'''# 默认映射复验：逐句20次与完整标点

2026-09-09。平台项目：默认映射复验：逐句20次与完整标点 · 2026-09-09。
项目编号：`{meta['project_id']}`。

本次按用户纠正重新实验：完整原句由发送层原样提交，现有默认感官继续执行NFKC。没有为标点改变映射器、感官参数或内核。上一轮关闭NFKC是执行条件错误，旧记录保留但不作为本轮条件的证据。

下面的“目标领先”是外部词模板相关活动超过其他候选，不能自动解释为意识生成了该文字答案。连续状态是主观察；结构出生副本清空活动后再激活，必须分开理解。配对/问答的平均量是目标减另一个候选；家系平均量是角色区分量，不是准确率。

## 最终观察汇总

{final_table}
完整候选数值、阶段变化、对照及方法限制在以下记录中；无法评分不填零，并列不计为严格领先。
'''
    training = '''## 实际教学与映射核验

用户14条原句如下；每行完整发送，不带方括号：

```text
''' + '\n'.join(DIALOGUE + USER_FAMILY) + '''
```

对话每句连续20次后换句，完整3轮共600次；7条家系/规则句同样每句20次、3轮共420次；再回顾10条对话，每句5次共50次；最后4条未见家系事实每句20次、3轮共240次。对话最终每句65次，家系句每句60次。每条完整课程1,310次，间隔0.8模拟秒，共1,048模拟秒。附加家系仅替换名字，陈述句都以句号结束。

4个固定种子41701—41704。每个种子的家系互换分支继承第1,070次后的完整状态；名词互换另用前两个固定种子从空白开始。这些对照均在任何本轮教学前登记。名词互换仅将松子/铃铛在所有相关对话中一致交换，所有说话人及标点保持。

完整使用`TextSensorConfig()`：默认匿名分布式192通道、NFKC、24字符分帧、20毫秒帧间隔、增益1。输入强度1；本轮每条训练句都只有1帧，最长17字符。原文全角标点在信封中不变，感官按既有NFKC规则转换后编码；这两个阶段分别审计。Core使用`Config()`，源码与原生二进制摘要与训练前一致。

本次与上一轮同时存在NFKC设置纠正和家系句号补全，不能把跨轮差别仅归因于某一项。所有新增证据属于独立项目，旧意识、笔记和报告均未改写。

### 每条实际意识记录

''' + table(['种子', '教学', '实际递送帧数', '意识ID'], [
        [a['seed'], arm[a['arm']], a['actual_frames'], a['run_id']] for a in sorted(audit, key=lambda r: (r['seed'], r['arm']))])
    training += f"\n已逐条核验 {accept['exact_training_frames']} 个原文载体、默认配置、规范化摘要、输入强度、帧通道与幅度、递送顺序和时间；核验 {accept['checkpoint_hashes_verified']} 个恢复点及 {accept['measurement_source_hashes_verified']} 个测量来源摘要。\n"
    training += '''
### 连接形成、保持及重新形成

下表追踪第20次输入时的连接，以起点、终点及出生时间区分原连接延续和同端点重新生边。缺失不隐藏，重新形成不冒充一直保留。均为只读观察，不保护或指定任何连接。

''' + table(['种子', '输入数', '节点', '边', '权重为1的边', '原出生连接仍在', '同端点新生', '原端点缺失'], [
        [r['seed'], r['count'], r['total_nodes'], r['total_edges'], r['edges_at_weight_one'],
         f"{r['same_birth_edges']}/{r['original_edges']}", r['recreated_endpoint_edges'], r['missing_endpoints']]
        for r in continuity if r['count'] in [20, 40, 200, 600, 1310]])
    training += '\n![完整教学中的连接与稳定度变化](training.png)\n\n图中原端点集合可能包含重新生边；出生身份区分以上表和原始JSON为准。\n'
    memory = '''## 配对、问答与名词互换

每个提示和无提示对照从同一阶段独立复制。连续状态保留当前活动、抑制、在途信号和时钟，等待0秒。结构出生副本依据既有`threemind.birth/1`规则保留长期网络结构，清空激活、抑制、近期痕迹、资格迹和在途队列，并重置时钟及相关运行状态；它不是原意识暂停后恢复，也不只是换了显示方式。测试期间学习开启，但绝不写回教学意识。

主要数值为0.2至1模拟秒的活动积分平均减同源无提示对照。另保存0至0.2秒和全部曲线。词模板重叠与直接提示通道仅在评分中排除；完整零/非零激活仍保存在原始ZIP中。此工具没有让AI填词或生成答句。

### 原对应的阶段结果

''' + table(['输入阶段', '项目', '观察方式', '目标严格领先/可评分', '种子平均差值'], [
        [a['stage'], group[a['group']], route[a['route']], f"{a['strict_target_top']}/{a['scorable_queries']}", a['mean']]
        for a in summary['aggregates'] if a['arm'] == 'normal' and a['group'] in ['pair', 'who']])
    memory += '\n![分阶段配对与问答](learning.png)\n\n### 最终每条提示的候选活动\n\n'
    memory += table(['种子', '教学', '方式', '提示', '预期', '目标减另一个', '候选净活动'], [
        [m['seed'], arm[m['arm']], route[m['route']], c['cue'], c['expected'], c['margin'],
         '; '.join(f'{k}={fmt(v)}' for k, v in c['values'].items())]
        for m in measures if m['stage'] == 'final' and m['group'] in ['pair', 'who'] for c in m['late']['cases']])
    memory += '''
### 是否跟随名词互换

以下比较同一个编码种子在两种完整教学中的偏向。两列“正确方向差值”均按各组实际对应计算；其和是固定词方向下原组减互换组的差异。若要认为两组都偏向自身学到的对应，两组差值都应为正，不能只检查和为正。

''' + table(['种子', '方式', '项目', '原对应正确方向差值', '互换后正确方向差值', '固定词方向的组间变化'], [
        [r['seed'], route[r['route']], group[r['group']], r['normal_correct_margin'],
         r['swapped_correct_margin'], r['following_difference']]
        for r in summary['follows_swapped_pairs'] if r['stage'] == 'final'])
    family = '''## 已教家系及未见名字关系组合

已教C→B→A、F→E→D，同时教授其爷爷事实及“父亲的父亲是爷爷。”。未见Z→Y→X、W→V→U只提供父亲事实；最终独立提示“Z的爷爷是谁？”等。家系互换分支改为Z→Y→U、W→V→X，没有输入对应爷爷答案。

角色区分量R为：(爷爷问题中预期爷爷减父亲的活动)−(父亲问题中预期爷爷减父亲的活动)。它须结合目标是否领先、裸名字对照及事实互换方向判断；R为正不自动表示答对。

### 已教家系阶段

''' + table(['方式', '严格领先/可评分', '总提示数', '平均R'], [
        [route[a['route']], f"{a['strict_target_top']}/{a['scorable_queries']}", a['total_queries'], a['mean']]
        for a in summary['aggregates'] if a['group'] == 'seen_family'])
    family += '\n### 最终所有祖父问题的完整候选\n\n'
    family += table(['种子', '教学', '方式', '孩子', '预期爷爷', 'X', 'Y', 'U', 'V', '目标减最强其他', 'R'], [
        [m['seed'], arm[m['arm']], route[m['route']], c['child'], c['expected_grandfather'],
         *[c['values'][k] for k in ['X', 'Y', 'U', 'V']], c['target_margin'], c['role']]
        for m in measures if m['stage'] == 'final' and m['group'] == 'family' for c in m['late']['cases']])
    family += '\n### 相同名字在家系事实互换后的变化\n\n'
    family += table(['种子', '方式', 'Z家系方向变化', 'W家系方向变化', '两家系平均'], [
        [r['seed'], route[r['route']], *r['by_family'], r['mean']] for r in summary['follows_crossed_facts']])
    family += '\n![预先固定首个种子的全部候选时间曲线](family-curves.png)\n'
    family += '''
### 不依赖词投影的全节点活动检查

以下只读取原有连续状态探针ZIP，以通道对应比较提示与无提示的全部激活，不额外模拟。末次差异采样点单位是微秒，数值容差仅为1e-12。每20毫秒采样可能漏掉间隔中的变化，激活也不是全部动力学状态，不能由这里的相同断言全部状态相同。

''' + table(['种子', '提示', '最大L1差异', '末次有差异采样点'], [
        [r['seed'], r['cue'], r['max_l1'], r['last_changed_sample_us']] for r in raw])
    resource = f'''## 资源与验收

- 固定预算：新增4 GiB、累计实验计算30分钟，达到3 GiB先停止计算并留发布余量；账户66%起始、84%停止。
- 本轮实验进程计时 **{summary['resources']['elapsed_s'] / 60:.2f}分钟**，包含训练、测量和相关数据库操作，不含报告编写。
- 进程采样最大RSS **{summary['resources']['max_process_rss'] / 1024**2:.2f} MiB**；这不是整机内存峰值或未采样瞬间的保证。
- 发布前数据库增长 **{accept['database_growth_bytes'] / 1024**2:.2f} MiB**，本地证据 **{accept['local_evidence_bytes'] / 1024**2:.2f} MiB**；发布后的最终数值见`acceptance.json`。
- {summary['resources']['source_runs']}条教学意识、{summary['resources']['delivered_training_carriers']}次实际教学输入、{summary['resources']['checkpoints']}个恢复点、{summary['resources']['measurement_jobs']}个测量任务、{summary['resources']['probe_copies']}个提示/无提示副本。
- 最近额度观测{quota['used_percent']}%，起始66%；账户级读数可能滞后且包含其他任务。最终记录见`quota-monitor.json`。
- {accept['old_model_count']}条既有实验意识及其所在项目笔记/记录/报告头摘要未改变；未清理旧数据。产品源码和原生二进制摘要一致，感官与内核完整默认配置一致。
- 逐条输入、所有恢复点与测量来源摘要已校验；固定首种子的正常/交叉家系、连续/出生共4个原始ZIP及其中所有最终模型和完整活动采样已抽检。其余ZIP保留可审计，但不声称逐个解压检查过。
- 仅运行本轮自有任务，不启动通用worker领取其他任务。不声称做过本轮未执行的浏览器交互验收。

平台内保存方案笔记、3份实验记录、关联报告、结果笔记以及Markdown/HTML导出；`evidence-index.json`连接原始ZIP、恢复点和输入核验，`implementation.json`固定实际实现身份。
'''
    conclusion = (HERE / 'report-conclusion.md').read_text(encoding='utf-8')
    for name, text in [('report-intro.md', intro), ('training-record.md', training),
                       ('memory-record.md', memory), ('family-record.md', family), ('report-resources.md', resource)]:
        save(name, text)
    save('report.md', '\n\n'.join([intro, conclusion, training, memory, family, resource]))
    english = f'''# Default-mapping replication: blocked sentence teaching

2026-09-09. Project `{meta['project_id']}`. The complete Chinese report contains every final candidate and stage table.

The previous experiment incorrectly disabled NFKC when interpreting the requirement to preserve source punctuation. This replication uses the complete existing `TextSensorConfig()` and `Config()` defaults, with frozen product-source and native-binary hashes. Literal input payloads preserve speakers, punctuation and sentence components; the unchanged sensor applies its default NFKC and encoding. The four family examples now end with the periods supplied by the user. This is a separate project; no previous data were altered.

Every dialogue sentence is delivered 20 consecutive times before switching, repeated for three sweeps (600 deliveries). Seven family/rule sentences follow with the same blocked repetition (420). Dialogue review then uses five consecutive deliveries per sentence (50); finally four held-out-name parent facts use 20 consecutive deliveries for three sweeps (240). Each complete course has 1,310 deliveries at fixed 0.8-s simulated intervals. The maximum carrier length is 17 characters; all training carriers fit the existing single-frame default. No extra background text is used.

Four fixed encoding seeds are 41701–41704. Each has a counterfactual family branch from exactly the same 1,070-input state. Two additional models with the first two fixed seeds consistently swap the two dialogue objects, preserving every speaker and punctuation mark. All controls were planned before this replication began. This is a small descriptive experiment, not a confirmatory significance claim.

Primary measurements continue the full current state with zero wait. Auxiliary copies use the existing `threemind.birth/1` rule: retain long-term topology and attributes, but clear activation, inhibition, recent traces, eligibility and the in-flight queue, and reset clocks and related runtime state. They are new initial conditions, not a resumption of the same individual. Each cue and no-cue baseline starts from an independent copy, learning remains enabled, and no probe changes are written back to the teaching model. The fixed main summary is sham-corrected mean activity over 0.2–1.0 s. Early activity and full traces are retained. Scoring masks do not remove any raw node activations; unavailable masks remain missing, not zero. The tables below describe observer projections, not generated natural-language answers.

## Final numerical results

''' + table(['Arm', 'Route', 'Measure', 'Strict target top / scorable', 'Total', 'Ties', 'Mean contrast'], [
        [a['arm'], a['route'], a['group'], f"{a['strict_target_top']}/{a['scorable_queries']}",
         a['total_queries'], a['ties'], a['mean']] for a in final])
    english += '\n## Pair-swap controls\n\n' + table(
        ['Seed', 'Route', 'Measure', 'Normal correct margin', 'Swapped correct margin', 'Following difference'], [
            [r['seed'], r['route'], r['group'], r['normal_correct_margin'], r['swapped_correct_margin'], r['following_difference']]
            for r in summary['follows_swapped_pairs'] if r['stage'] == 'final'])
    english += '\n## Crossed-family controls\n\n' + table(['Seed', 'Route', 'Z difference', 'W difference', 'Mean'], [
        [r['seed'], r['route'], *r['by_family'], r['mean']] for r in summary['follows_crossed_facts']])
    english += '\n' + (HERE / 'interpretation.en.md').read_text(encoding='utf-8')
    english += f'''

## Resources and provenance

Experiment-process time: {summary['resources']['elapsed_s'] / 60:.2f} min; sampled maximum process RSS: {summary['resources']['max_process_rss'] / 1024**2:.2f} MiB. {summary['resources']['delivered_training_carriers']} literal deliveries, {summary['resources']['source_runs']} teaching records, {summary['resources']['checkpoints']} checkpoints, {summary['resources']['measurement_jobs']} measurement jobs and {summary['resources']['probe_copies']} probe/sham copies. Pre-publication database growth: {accept['database_growth_bytes'] / 1024**2:.2f} MiB; local evidence: {accept['local_evidence_bytes'] / 1024**2:.2f} MiB. Final post-publication measurements are in `acceptance.json`. Account usage baseline was 66%, stop line 84%; observations are account-wide and can lag.

All recorded source carriers, defaults, normalized hashes, actual stimulus channels/amplitudes and delivery timestamps were verified; all source/checkpoint hashes were checked. Four fixed representative ZIP bundles and their final model hashes and 51-sample raw activation traces were checked. All {accept['old_model_count']} prior consciousness heads and associated old document/note heads remained unchanged. Source and native-binary hashes are unchanged. This does not claim a browser UI test or exhaustive unpacking of every ZIP.

The platform stores the plans, three records, linked report, result notebook and Markdown/HTML exports. Raw ZIP links and checkpoints are indexed in `evidence-index.json`. Full source identity is in `implementation.json`.
'''
    save('report.en.md', english.replace('无法评分', 'unscorable'))
    print('Reports and record tables generated from this project only.')


if __name__ == '__main__':
    build()
