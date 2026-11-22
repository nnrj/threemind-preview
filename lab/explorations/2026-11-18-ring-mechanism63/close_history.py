"""Append the completed study and recommendation status without rewriting old evidence."""
from pathlib import Path
import json
import apparatus as a

def append(path, text):
    path=a.ROOT/path
    old=path.read_text('utf8')
    marker=text.strip().splitlines()[0]
    if marker not in old:path.write_text(old.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf8')

def main():
    receipt=a.read(a.HERE/'delivery.json')
    assert receipt['coverage']=='verified' and receipt['complete_api_readback'] and receipt['pending']==0
    a.save(a.ROOT/'lab/artifact-index/2026-11-18-ring-mechanism63.json',{
        'schema':'threemind.ring-mechanism63-artifact-locations/1','date_beijing':'2026-11-18',
        'study':'AS63-03','work':str(a.WORK),'archive_member':'originals.zip','manifest_member':'manifest.json',
        'analysis_member':'analysis-v1/analysis.json','audit_member':'analysis-v1/audit.json',
        'independent_check_member':'analysis-v1/independent-check.json',
        'peripheral_blocks':2,'historical_materials':4,'profiles':3,'stages':312,
        'production_core_or_defaults_changed':False,'addressing_change':'recommendation only',**receipt})
    texts={
    'zh':'''## 2026-11-18：AS63-03定位旧环形外设的编号依赖

作者要求用两套旧外设及相同经历，比较/1、6.3默认和此前前缀成功配置，区分经历形成、出生继承与行为表达。执行前发现旧运动规则按节点编号决定正负系数，而节点编号在/1随形成次序分配，在6.3则等于通道编码；同种子、同代码没有保证相同实际接线。因此登记原规则及按旧通道对应对齐的研究副本，另设空白、培养后、新生子代和子代继续培养，保持旧背景输入。供能模型差异在正式运行前排除，生产Core及默认均未改动。

312段过程全部完成，四份/1旧经历的2400个逐时采样点精确复现。外设9293202中，/1培养后两个历史方向的目标区域比例均为93.917%；6.3默认原规则为4.417%和95.333%，对齐后两个方向均为94.000%。更关键的是，空白6.3接入旧对应表也达到两个方向各93.750%。前缀成功配置没有在原规则下恢复双向分化。另一套外设仍接近50%，相关运动轨迹保留。

出生前已合格的10个材料—配置—输出条件在出生后全部保留偏向；12次出生保留节点与连接及当时有效权重。三配置的固定刺激诊断也均有经历效应。因此，本批主要差异定位在运动对应，不支持将它概括成6.3学习或继承能力退化。旧行为仍可复核，但高停留比例不能独自证明可塑连接学得、遗传或逐代增强了区域偏向；这一解释限制追加于新报告，旧原件不改。

原包经本地API完整下载、逐成员核验，双语报告读回一致并结项。作者提出新的确定性寻址函数意向；建议将稳定身份寻址与运动读取分开，并评估空间、能量及事件排序影响。具体寻址修改尚未实施，也未据此授权。
''',
    'en':'''## 2026-11-18: AS63-03 locates node-ID dependence in the old ring adapter

The author requested a matched comparison of /1, current 6.3 defaults and the previously successful prefix configuration using the two old peripheral sets. Before execution, inspection showed that the old motor rule hashes node IDs into signed coefficients, while /1 allocates IDs in formation order and 6.3 uses channel codes. Identical seeds and code therefore did not ensure identical actual bindings. The study registered original and historically aligned motor rules, with blank, developed, newborn and redeveloped states and the old recorded background. Energy-model confounding was removed before formal execution; production Core code and defaults were unchanged.

All 312 stages completed. The four old /1 histories reproduced exactly at 2,400 sampled points. With peripheral 9293202, developed /1 target occupancy was 93.917% in both historical directions. Default 6.3 gave 4.417% and 95.333% under the original rule, but 94.000% in both directions after alignment. Crucially, blank 6.3 Cores supplied with the same bindings reached 93.750% in both directions. The prefix configuration did not recover opposite preferences under the original rule. The other peripheral remained near 50%, with its trajectories retained.

All 10 qualified history/configuration/output conditions retained their tendency after birth. All 12 births preserved nodes, connections and current effective weights. Fixed-input diagnostics also retained history effects in every configuration. The principal difference was therefore located in motor bindings, not established as a general regression of 6.3 learning or inheritance. Old behavior remains reproducible, but high occupancy alone cannot establish plastic-connection learning, inheritance or cumulative strengthening of regional tendencies. This attribution limit is appended in a new report; originals remain unchanged.

The archive was downloaded completely through the local API and checked member by member; bilingual reports matched on readback and the record was finalized. The author proposed a new deterministic addressing function. Recommendations separate stable identity addressing from motor readout and require evaluation of spatial, energy and event-order effects. No concrete addressing change was implemented or newly authorized.
'''}
    for lang,text in texts.items():
        link=f'[AS63-03](../../../../lab/explorations/2026-11-18-ring-mechanism63/report.{lang}.md)'
        append(Path(f'docs/{lang}/history/chronicles/20-artificial-selection.md'),text+'\n'+link)
        short=text.split('\n\n')[0]+'\n\n'+text.split('\n\n')[2]
        append(Path(f'docs/{lang}/history/themes/04-autonomous-consciousness.md'),short+'\n\n'+link)
        append(Path(f'docs/{lang}/history/milestones.md'),short+'\n\n[AS63-03](chronicles/20-artificial-selection.md)')
        source=f'[AS63-03](2026-11-18-ring-mechanism-comparison.md)'
        append(Path(f'docs/{lang}/history/sources/source-register.md'),text.split('\n\n')[0]+'\n\n'+source)
        path=a.ROOT/f'docs/{lang}/plans/research-backlog.md'
        old=path.read_text('utf8');first,rest=old.split('\n',1)
        marker=text.splitlines()[0]
        if marker not in old:
            summary=(
                'AS63-03已完成312段对照并通过完整原件及API下载核验。主要差异定位为旧运动外设的节点编号依赖：6.3默认在原规则下两个历史方向为4.417%与95.333%，按旧通道对应对齐后均为94.000%；空白内核同样达到93.750%。出生没有丢失节点、连接或当时有效权重；前缀配置未恢复原规则下的双向分化。旧高停留比例的学习与遗传归因需收窄，原报告和论文均未改写。\n\nAS63-ADDR：作者提出稳定函数寻址方向，具体参数身份、碰撞规则、输出读取与动力学影响仍需确定。当前仅提供建议，未修改内核、默认或启动下一批实验。'
                if lang=='zh' else
                'AS63-03 completed all 312 stages with full evidence and API-download verification. The main difference was old motor-adapter dependence on node IDs: default 6.3 gave 4.417% and 95.333% in opposite historical directions under the original rule, but 94.000% in both after aligning old channel bindings; blank Cores also reached 93.750%. Birth lost no nodes, connections or current effective weights, and the prefix configuration did not recover opposite preferences under the original rule. Attribution of old high occupancy to learning/inheritance must narrow; old reports and the manuscript were not rewritten.\n\nAS63-ADDR: The author proposed stable functional addressing. Identity parameters, collision rules, motor readout and dynamics remain design questions. Recommendations only: no kernel/default change or new experimental batch is authorized or started.')
            link2=f'[Report](../../../lab/explorations/2026-11-18-ring-mechanism63/report.{lang}.md) · [Addressing](../../../lab/explorations/2026-11-18-ring-mechanism63/addressing-recommendations.{lang}.md)'
            path.write_text(first+'\n\n'+marker+'\n\n'+summary+'\n\n'+link2+'\n'+rest,encoding='utf8')
    append(Path('docs/zh/history/classical/shiji-06.md'),'''## 十一月十八日：辨编号与经历之功

复试旧环，两器三核，悉用旧习。乃知旧御动之法因节点之号定其向，号又因先后而异；六点三不循此号，行遂异。依旧通道相配，则两向皆显，空白之核亦能近之。出生未失其联与当时之重，前缀旧方亦未复原法之两向。于是存旧行之实，正其归功，不以停留之高独证可塑相传。作者议函数寻址，今录其议而未改核。

[今录](../chronicles/20-artificial-selection.md)''')
    append(Path('docs/zh/history/classical/tongjian-05.md'),'''## 十一月十八日：旧接线之辨

是日，三百一十二段对照毕。旧核四史皆复原迹；六点三循旧通道对应则复两向之偏，空白亦近之。乃辨编号所定之向与可塑经历之功：旧行可存，其归因不可过。亲子结构及当时有效权重皆存，前缀之方未解原法之异。原包尽核，双语结录；函数寻址尚属议论，生产之核不动。

[今录](../chronicles/20-artificial-selection.md)''')
    print('Artifact index, bilingual history/backlog and both Classical adaptations updated.')

if __name__=='__main__':main()
