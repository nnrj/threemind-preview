"""Bilingual factual report for the separately cultivated complete habitats."""
from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json


def main():
    a=read_json(HERE/'results.json');project=read_json(WORK/'platform.json')['project_id']
    rows=[]
    for branch,r in a['latest'].items():
        if r is None:continue
        for source,g in r['groups'].items():
            rows.append(f"| {branch} | {r['time_us']/1e6:g} | {source} | {g['physical']} | {g['powered_bodies']} | {g['new_food']} | {g['captures']} | {g['new_births']} | {g['new_turns']} | {g['maximum_generation']} |")
    table='\n'.join(rows)
    special=[o for o in a['observations'] if 'both' in o['flags'] or any(f.startswith('improved-') for f in o['flags'])]
    flags='\n'.join(f"| {o['case']} | {o['time_us']/1e6:.2f} | {o['individual']} | {o['cohort']} | {o['generation']} | {', '.join(o['flags'])} |" for o in special) or '| — | — | — | — | — | none / 无 |'
    captures='\n'.join(f"| {e['case']} | {e['time_us']/1e6:.2f} | {e['predator']} → {e['individual']} | {e['coverage_measured']:.3f} | {e['contact_us']/1e6:.3f} / {e['required_us']/1e6:.3f} | {e['transferred']:.2f} | {e['material_received']:.2f} | {e['shell_cost']:.3f} |" for e in a['consumptions']) or '| — | — | — | — | — | — | — | — |'
    cases='\n'.join(f"| {r['case']} | {r['time_us']/1e6:g} | {r['status']} | {r['wall_seconds']/60:.2f} |" for r in a['segments'])
    turns=[o for o in a['observations'] if any(e['kind']=='turning_food' for e in o['events'])]
    turning='\n'.join(f"| {o['case']} | {o['time_us']/1e6:.2f} | {o['individual']} | {o['cohort']} | {o['generation']} | {o['counts']['turns']} |" for o in turns)
    combined=[c for c in a['candidate_inventory'] if c['branch']=='coverage'
              and c['counts']['turns'] and c['counts']['captures']]
    descendants=[c for c in combined if c['generation']>0]
    repeated=[c for c in a['candidate_inventory'] if c['counts']['captures']>=2]
    improvements=[o for o in special if any(f.startswith('improved-') for f in o['flags'])]
    selected=[c for c in a['candidate_inventory'] if
              c['counts']['turns']>=3 or c['counts']['captures']>=2 or
              (c['counts']['turns'] and c['counts']['captures'])]
    candidates='\n'.join(f"| {c['branch']} | {c['individual']} | {c['cohort']} | {c['generation']} | {c['parent'] if c['parent'] is not None else '—'} | {c['counts']['turns']} / {c['counts']['captures']} | {'在场 / present' if c['physical_at_endpoint'] else '已失去 / lost'} | {c['archive_time_us']/1e6:.2f} |" for c in selected)
    zh=f'''# E41：转弯摄食与半包裹分开培养

2026-10-04 · 项目`{project}`。

## 实际结果

**已有{len(combined)}个同一身份兼有转弯后摄食和部分包裹吞食记录，其中{len(descendants)}个是自然出生的后代；{len(repeated)}个个体不止一次成功吞食。** 这些是可继续复用的具体候选，已保存活体状态。它们完成的是新环境允许的至少半面积包裹；旧完全包裹试验没有因此被改写成成功。本轮亲代改善筛查触发{len(improvements)}条，不能把代次增加直接当作能力提高。

启动条件是E39与E40均观察到900模拟秒、没有完整包裹成功。两支从同一300秒完整世界分开，保留全部70个躯体、营养、网络、亲缘和环境状态。turning禁个体间吞食；coverage允许覆盖猎物面积至少50%并持续满足外壳/保持条件后吞食。既没有删去其他生物，也没有写入觅食、追逐和转弯动作。

本轮记录部分包裹吞食{len(a['consumptions'])}次，新的转弯后摄食过程{len(turns)}次，保存{len(a['archives'])}份候选状态。下表只把300秒以后新增的摄食、出生、转弯列作新观察；最高代次及末存状态是实际终点。两种培养方向的可吞食规则不同，不能直接将末存数量比较称为意识控制能力胜负。

| 分支 | 终点模拟秒 | 来源 | 末存躯体 | 尚有身体能量 | 新摄食 | 吞食 | 新出生 | 新转弯摄食 | 最高代次 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{table}

## 吞食实际过程

| 段 | 模拟秒 | 吞食者→对象 | 面积比例 | 保持秒/所需秒 | 能量所得 | 其中身体材料 | 外壳代价 |
| --- | --- | --- | --- | --- | --- | --- | --- |
{captures}

同强个体按环境种子与相遇时刻随机定胜负，并保持至分离；不同强度按既有体型、推进和抓持能力竞争。只接触不等于吞食。成功记录名为`body_consumed_by_coverage`，不能当作旧版完全包裹成功，也不直接证明主动捕猎；需要结合内部活动消融定位。

## 候选、后代与转弯

| 段 | 模拟秒 | 个体 | 来源 | 代次 | 组合或亲代改善标记 |
| --- | --- | --- | --- | --- | --- |
{flags}

标记沿用事前被动观察规则。改善要求亲子都有至少60秒活动暴露、子代至少3次转弯或2次吞食、单位活动时间发生率达到亲代两倍；这是筛选，不排除身体、地点、机会与年龄差别。物种库中保留完整意识、躯体、通道接线与过程证据，未给候选写入新行为。

下面列出重复或组合表现候选。累计次数包含真实共有的300秒前经历；存档时刻不一定等于分支终点。即使个体后来已失去，事先保存的活体状态仍在。完整候选清单、包路径、身体性状及亲代性状见结果表`candidate_inventory`。

| 分支 | 个体 | 来源 | 代次 | 亲代 | 累计转弯/吞食 | 分支终点躯体 | 最新候选存档秒 |
| --- | --- | --- | --- | --- | --- | --- | --- |
{candidates or '| — | — | — | — | — | — | — | — |'}

| 段 | 模拟秒 | 个体 | 来源 | 代次 | 含共同历史的累计转弯次数 |
| --- | --- | --- | --- | --- | --- |
{turning or '| — | — | — | — | — | — |'}

## 范围、证据与未结项

| 段 | 实际终点模拟秒 | 状态 | 墙钟分钟 |
| --- | --- | --- | --- |
{cases}

模拟墙钟合计{a['wall_seconds']/60:.2f}分钟。未完成段及资源停止原因在执行记录说明；不为追求成功继续扩展。原始证据保留于`.work/ocean-split-20261004`，报告、物种及全海录像入本项目。旧E39、E40及Core未修改。本轮只有一个历史来源的两条新环境线，不能推出通用稳定物种或一般演化规律。

[事前设计与用户确认](design.zh.md) · [结果表](results.json) · [操作](README.md)
'''
    en=f'''# E41: separate turning/feeding and partial-coverage cultivation

2026-10-04 · Project`{project}`.

**{len(combined)} continuing identities have both turning/feeding and partial-consumption records, including {len(descendants)} naturally born descendants; {len(repeated)} individuals consumed more than once.** Living event states are retained for reuse. This is the new at-least-half-area condition, not a retrospective success in full enclosure. There are {len(improvements)} preregistered parent-improvement markers; generation advancement alone does not demonstrate improvement.

Both E39/E40 branches reached900s without full enclosure, activating the preregistered fallback. Entire300s habitat copies preserve all70 bodies, brains, food, ancestry and environment. Turning disables body consumption; coverage requires≥50% prey area, dwell and shell costs. No steering/pursuit policy or Core change was introduced.

Observed {len(a['consumptions'])} partial-coverage consumptions, {len(turns)} new qualifying turn/feeding episodes and {len(a['archives'])} archived candidates. New food/birth/turn counts exclude the inherited300s prefix. Different consumption rules mean population totals do not constitute a controller contest.

| Branch | Endpoint s | Source | Physical survivors | Bodies with energy | New food | Consumptions | New births | New turns | Max generation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{table}

| Segment | Time s | Consumer→prey | Area fraction | Held/required s | Energy received | Material received | Shell cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
{captures}

Body capability resolves reciprocal coverage; exact ties are reproducibly random and persist until separation. Contact alone is insufficient. `body_consumed_by_coverage` is not old full enclosure and does not by itself establish active pursuit.

| Segment | Time s | Individual | Source | Generation | Combined/parent improvement markers |
| --- | --- | --- | --- | --- | --- |
{flags}

Improvement screening requires parent/child activity exposure≥60s, child≥3 turns/2 consumptions and double the parental event rate. This preserves candidates, not matched causal superiority. Full body/brain/wiring/evidence assets are retained.

Repeated/combined candidates follow. Cumulative counts include the actual shared pre300s history; archive times need not equal the endpoint. Prior living states remain available after a body is lost. Full paths, traits and parental traits are in `candidate_inventory` in the results.

| Branch | Individual | Source | Generation | Parent | Cumulative turns/consumptions | Endpoint body | Latest candidate archive s |
| --- | --- | --- | --- | --- | --- | --- | --- |
{candidates or '| — | — | — | — | — | — | — | — |'}

| Segment | Time s | Individual | Source | Generation | Cumulative turns including prefix |
| --- | --- | --- | --- | --- | --- |
{turning or '| — | — | — | — | — | — |'}

| Segment | Actual endpoint s | Status | Wall min |
| --- | --- | --- | --- |
{cases}

Total simulation wall {a['wall_seconds']/60:.2f}min. Raw evidence at`.work/ocean-split-20261004`; reports, species and full-world footage are published in the project. Earlier studies and Core are intact. These two environments share one historical source, not independent evolutionary replications. Resource stops/unfinished work are recorded explicitly.

[Preregistration](design.en.md) · [Detailed results](results.json) · [Operations](README.md).
'''
    for lang,body in [('zh',zh),('en',en)]:
        with (HERE/f'report.{lang}.md').open('x',encoding='utf-8') as stream:stream.write(body)


if __name__=='__main__':main()
