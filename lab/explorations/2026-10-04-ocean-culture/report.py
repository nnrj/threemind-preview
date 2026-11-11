"""Readable observed culture outcomes; no unmeasured abilities are inferred."""
from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json


def main():
    a=read_json(HERE/'results.json');latest=a['latest'];paired=a['paired_comparison']
    times='\n'.join(f"| {r['case']} | {r['time_us']/1e6:g} | {r['status']} | {r['wall_seconds']/60:.2f} |" for r in a['segments'])
    rows=[]
    for branch,r in (paired or latest).items():
        for name,g in r['groups'].items():
            rows.append(f"| {branch} | {name} | {g['physical']} | {g['food']} | {g['captures']} | {g['births']} | {g['turning_events']} | {g['maximum_generation']} | {g['share_received']:.2f} |")
    table='\n'.join(rows) or '| — | — | — | — | — | — | — | — | — |'
    observations=a['observations'];turns=[o for o in observations if any(e['kind']=='turning_food' for e in o['events'])]
    offspring=[o for o in turns if o['generation']>0]
    combined=[o for o in observations if 'both' in o['flags']]
    improvements=[o for o in observations if any(f.startswith('improved-') for f in o['flags'])]
    events='\n'.join(f"| {e['case']} | {e['time_us']/1e6:.2f} | {e['predator']} → {e['individual']} | {e['transferred']:.2f} | {e.get('prey_material',0):.2f} |" for e in a['consumptions']) or '| — | — | — | — | — |'
    special='\n'.join(f"| {o['case']} | {o['time_us']/1e6:.2f} | {o['individual']} | {o['cohort']} | {o['generation']} | {', '.join(o['flags'])} |" for o in observations if o in combined or o in improvements) or '| — | — | — | — | — | 未触发 / none |'
    activity='\n'.join(f"| {o['case']} | {o['time_us']/1e6:.2f} | {o['individual']} | {o['cohort']} | {o['generation']} | {o['counts']['turns']} |" for o in turns)
    transfers=a['sharing_events'];exchanged=sum(e['received'] for e in transfers)
    pairs='\n'.join(f"| {p['branch']} | {' / '.join(map(str,p['individuals']))} | {p['relationship']} | {p['transfers']} | {p['received']:.2f} | {'yes' if len(p['directions'])>1 else 'no'} | "
        + ' / '.join(f"{b['id']}: {'alive' if b['physical'] else 'lost'}" for b in p['endpoint_members'])+' |'
        for p in a['sharing_pair_outcomes']) or '| — | — | — | 0 | 0 | — | — |'
    duration=max((r['association_max_s'] for r in a['segments']),default=0)
    project=read_json(WORK/'platform.json')['project_id']
    common=f"{a['common_endpoint_us']/1e6:g}" if a['common_endpoint_us'] else '无 / none'
    zh=f'''# E39–E40：三类候选共同培养与邻近分享

2026-10-04 · 项目`{project}`。

## 先说观察到了什么

- 新海洋记录到{len(turns)}次通过转弯摄食筛查的过程，其中{len(offspring)}次来自自然出生的后代。共同段只计一次；两个分支中的后续观察不是独立随机环境重复。
- 完整包裹吞食{len(a['consumptions'])}次；兼具转弯摄食和吞食的首次标记{len(combined)}项。
- 相对自然亲代达到事前改善筛查的记录{len(improvements)}项。所有符合保存规则且当步仍存活的候选即时存档，本项目有{len(a['archives'])}份候选包。
- 实际分享{len(transfers)}笔，接收方合计获得{exchanged:.2f}能量；最长连续近邻过程{duration:.2f}模拟秒。这两项分别是转移和接近记录，不能直接互换为主动合作或融合。

这批试验培养的是已有候选，而非从空白等起。转弯与吞食的过程记录保留下来，尚未用本批消融判定其内部机制。下面的明细保留不成功、未触发和预算未完成的部分。

## 实际执行范围

| 段 | 实际终点模拟秒 | 状态 | 模拟墙钟分钟 |
| --- | --- | --- | --- |
{times}

合计{a['wall_seconds']/60:.2f}模拟墙钟分钟。双方共同完成终点：{common}模拟秒。若不存在共同分叉终点，下表只是各自实际观察，不判分享胜负。资源到线则停止扩展，实际停止原因另在执行记录追加；存活状态保留。

| 分支 | 来源谱系 | 末存躯体 | 营养摄入 | 吞食 | 出生 | 转弯摄食 | 最高代次 | 分享收入 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{table}

turn44、turn59分别来自E38/44、59在900秒的最新快照；engulf15来自E38/15在199.62秒的吞食事件快照。每类17创始体，同在完整海洋，均由意识控制。身体/映射/结构继承，按既有出生规则清空即时活动；没有给它们写转弯、追逐或合作动作。来源、材料环境和初始位置与E38不同，不能将跨实验差异独归训练。

## 吞食、代际改善与组合表现

| 段 | 模拟秒 | 吞食者→对象 | 获得能量 | 猎物躯体材料 |
| --- | --- | --- | --- | --- |
{events}

| 段 | 模拟秒 | 个体 | 来源 | 代次 | 保存标记 |
| --- | --- | --- | --- | --- | --- |
{special}

`both`表示同一个体有两类观察记录；`improved-turns/captures`表示双方活动至少60秒、子代次数至少3/2、每活动秒发生率至少为亲代2倍。标签用于保存候选，不输入Core，不等于排除了体型、位置、机会或年龄差异。具体亲代、计数和活动时长在物种包证据中。

## 转弯过程清单

| 段 | 模拟秒 | 个体 | 来源 | 代次 | 该体累计筛查次数 |
| --- | --- | --- | --- | --- | --- |
{activity or '| — | — | — | — | — | — |'}

筛查沿用E38规则，没有因结果临时降低条件，也不把规则外的转弯视为不存在。重复转弯后摄食比单次更值得观察，但自身绕圈碰巧摄食仍需匹配对照进一步区分。

## 分享究竟意味着什么

两支从300秒完整状态分叉，保持其余规则、已有邻近计时及相同环境随机序列。sharing只在边缘持续靠近1秒后，分享新摄入的25%，传递效率90%，多个邻居均分；旧储备不再分配，收到的分享不能同一步转赠。身体吞食所得也计新摄入。深度包裹中的对象不能作为贴边伙伴领取能量。静止相邻允许，追随、吸引、黏附与躯体融合均未加入。

有转移只说明外部条件生效；能形成持续联合、双方受益，或反而资助后来吞食自己的邻体，要结合各对关系和完整对照判断。没有实际转移时，也不能把“没有触发该条件”写成“分享没有价值”。本批只有一个共同来源海洋，配对分支不是多个独立环境。

| 分支 | 个体对 | 亲缘关系 | 转移笔数 | 实收能量 | 有双向转移 | 分支末躯体状态 |
| --- | --- | --- | --- | --- | --- | --- |
{pairs}

parent-child为亲子，siblings为同亲子代，other为其他关系；alive/lost只表示躯体在场/已失去。出生时子代放置在亲代附近，因此亲子长时间接近不能单独当作主动寻伴。详细结果还记录首次分享后的首次分开时间、两者后续各自摄食和是否互相吞食。

## 查阅与复用

在本项目“模型与证据→物种库”查看实时候选；“记录与报告”查看本报告与完整海洋录像。原始世界、输入、动作、观察器记录及状态在`.work/ocean-culture-20261004`。未覆盖E38或修改Core。完整[结果表](results.json)保留事件、计数和档案路径。

[事前登记与用户原话](design.zh.md) · [执行记录](execution-notes.md) · [操作入口](README.md)
'''
    en=f'''# E39–E40: joint candidate culture and proximity sharing

2026-10-04 · Project`{project}`.

Observed {len(turns)} qualifying turn/feeding episodes, including {len(offspring)} in natural descendants; {len(a['consumptions'])} full enclosures; {len(combined)} first combined-capability markers; {len(improvements)} parent-rate improvement markers; {len(a['archives'])} archived living candidate states. There were {len(transfers)} real transfers totaling {exchanged:.2f} received energy. Longest proximity episode: {duration:.2f} s. Shared-prefix observations are counted once; later fork events are not independent-world replications.

| Segment | Actual endpoint s | Status | Simulation wall min |
| --- | --- | --- | --- |
{times}

Total simulation wall time: {a['wall_seconds']/60:.2f} min. Common completed fork endpoint: {common} s. If none exists, the next table is descriptive endpoints only, not a sharing comparison. Resource stops and unfinished segments are documented separately; living states are retained.

| Branch | Source | Physical survivors | Nutrients | Consumptions | Births | Turning episodes | Max generation | Shared energy received |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{table}

Seventeen founders each inherit E38/44 and 59 at 900 s and 15 immediately after its 199.62 s consumption. All remain Core-controlled in the complete habitat. Existing birth rules retain structure/body/mapping but clear immediate activity. Source composition, material rules and placement differ from E38; cross-study changes cannot be attributed solely to training.

| Segment | Time s | Consumer→prey | Energy gained | Prey material |
| --- | --- | --- | --- | --- |
{events}

| Segment | Time s | Individual | Source | Generation | Archive markers |
| --- | --- | --- | --- | --- | --- |
{special}

Both means two recorded capabilities in one individual. Improvement requires both natural parent and child to have 60 s observed activity, child counts ≥3 turns or ≥2 consumptions and twice the parent's event rate. These identify candidates, not matched causal superiority; body, age, placement and opportunity remain alternatives. Exact evidence accompanies each asset.

| Segment | Time s | Individual | Source | Generation | Individual cumulative turns |
| --- | --- | --- | --- | --- | --- |
{activity or '| — | — | — | — | — | — |'}

The existing E38 passive criteria were retained, not relaxed to obtain results. Incidental circling is not excluded, and slower/other turns may be missed. No steering, pursuit or cooperation policy was added.

Full-state forks at 300 s differ only in newly ingested sharing 0/25%. Surfaces must remain within 1 mm for 1 s; transfers are 90% efficient and divided among eligible neighbors. Both nutrient and body-consumption receipts qualify, existing reserves do not, and received shares cannot be retransferred in the same step. Deeply enclosed bodies are not edge partners. Stationary proximity is allowed; no attraction, adhesion, following or fusion is imposed. Actual transfer, lasting association, mutual benefit and active cooperation remain distinct observations. If no transfer occurs, this is a trigger-opportunity issue rather than evidence that sharing is useless. One source world and paired forks do not establish generality.

| Branch | Pair | Relationship | Transfers | Received energy | Both directions | Endpoint body status |
| --- | --- | --- | --- | --- | --- | --- |
{pairs}

New offspring are placed near their parent, so lasting parent/child proximity alone is not evidence of seeking partners. The detailed results also record the first subsequent separation, later nutrient contacts and any later consumption of a sharing partner. Body presence is distinct from consciousness activity.

Species assets, reports and measured full-habitat videos are in the project. Raw evidence remains at`.work/ocean-culture-20261004`, without overwriting E38 or changing Core. [Detailed results](results.json) · [Preregistration](design.en.md) · [Execution notes](execution-notes.md).
'''
    for language,body in [('zh',zh),('en',en)]:
        with (HERE/f'report.{language}.md').open('x',encoding='utf-8') as f:f.write(body)


if __name__=='__main__':main()
