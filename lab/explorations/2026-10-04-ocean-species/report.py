"""Readable E38 findings from recorded outcomes, without new simulations."""
import json
from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json


def main():
    a=read_json(WORK/'analysis.json');branches=a['branches']
    passed=[b['branch'] for b in branches if b['repeated_enclosure']]
    zh_summary=('达到本轮事前登记的重复吞食条件：'+ '、'.join(passed)+'。这表示该候选谱系在新海洋中再次完成了多次包裹吞食。' if passed else
        '本轮没有达到事前登记的重复吞食条件，尚未获得能稳定多次包裹吞食的候选谱系。候选及失败过程全部保留，不继续无期限调参追逐阳性结果。')
    rows=[];events=[];times=[];energy=[]
    for b in branches:
        times.append(f"| {b['branch']} | {b['seconds']:g} | {b['status']} |")
        energy.append(f"| {b['branch']} | {len(b['enclosures'])} | {b['after_fork_capture_count']} | {b['zero_energy_captures']} | {b['capture_energy_received']:.2f} | {b['capture_shell_cost']:.2f} |")
        for e in b['enclosures']:
            events.append(f"| {b['branch']} | {e['time_us']/1e6:.2f} | {e['predator']} → {e['individual']} | {e['cohort']} | {e['generation']} | {e['radius_mm']:.3f} | {e['transferred']:.2f} |")
    for b in a['paired_comparison']:
        for group in ('candidate','other'):
            g=b['groups'][group];ts=b['traits'][group]
            rows.append(f"| {b['branch']} | {group} | {g['physical']} | {g['powered_bodies']} | {g['food']} | {g['captures']} | {g['births']} | {ts['maximum_generation']} |")
    table='\n'.join(rows);event_table='\n'.join(events) or '| — | — | — | — | — | — | — |'
    time_table='\n'.join(times);energy_table='\n'.join(energy)
    attempts='; '.join(f"{b['branch']}: {b['enclosure_starts']} starts, {b['released_count']} releases, median released hold {b['released_median_s']}s" for b in branches)
    project=read_json(WORK/'platform.json')['project_id']
    zh=f'''# E38：成功个体能否成为可复用的吞食谱系

2026-10-04 · 项目`{project}`。

## 直接回答

{zh_summary}

但已有值得保存的转弯摄食候选：10个试验内身份、14份活体快照；其中两名个体在相隔数百秒后再次出现转向后摄食。尚未找到兼会吞食者。具体过程、录像及物种库位置见[转弯候选与结项补记](turning-and-closeout.md)。

实际观察终点如下；只有到900秒的分支才完成登记时长。资源暂停不是个体死亡，也不补算成完整终点。

| 分支 | 实际模拟秒 | 停止状态 |
| --- | --- | --- |
{time_table}

实际账户用量由24%到27%，达到已登记的+3百分点停止扩展线。当前control段正常完成900秒；reduced的600～900秒段未启动。**下表统一比较双方都有的600秒**；不拿900秒和600秒直接判胜负。control的延长结果另列在补记中。

事前标准是：在独立于E37的新海洋中，至少两名候选谱系成员累计完成三次包裹吞食；若有后代成功，再单独记录代际保持。全体始终为意识驱动，没有混入随机控制；普通随机体型差异不等于随机驱动。

| 环境分支（共同600秒） | 谱系 | 末存躯体 | 身体储备>0 | 摄入营养 | 吞食 | 出生 | 最高代次 |
| --- | --- | --- | --- | --- | --- | --- | --- |
{table}

600秒时，原供给全群摄食858颗、末存42体、出生24次；减半供给摄食740颗、末存38体、出生21次。分叉后均无新增吞食。减少营养这次主要降低了摄食和繁殖，没有筛选出更多包裹吞食。

candidate起始11体，继承E37的59号；other起始42体。两组人数不同，本表是生态过程记录，不能直接以两个谱系总数之比认定单位个体优势。E38的第0代在外部谱系上继承E37第1代，场内代次从0计。

## 如何选择与复制

59号曾在E37的226.06秒吞食32号，使用其300秒保存状态作为来源。复制保留结构、躯体和映射，清空活动、按统一规则支付初始能量。原个体没有复活或被覆盖。11个复制体与42个其他意识一起生活，保留完整海洋、随机营养、流动、温度、本体和碰撞反馈。

共同的0～300秒只实际计算一次；之后从同一全海状态分叉。control继续每秒一粒营养；reduced改为每两秒一粒。既有营养不移除。这两个分支不是两个独立随机环境，不能充当独立重复样本。

## 实际吞食过程

| 分支 | 模拟秒 | 吞食者→被吞食者 | 吞食者谱系 | 场内代次 | 半径mm | 获得能量 |
| --- | --- | --- | --- | --- | --- | --- |
{event_table}

过程统计：{attempts}。它能区分完全没有接近，与已经包裹但未保持足够长两种情况。

共同前300秒的事件若列在两个分支中，属于同一事件，不能重复累计。每个自然成功事件结束后立即保存身体与意识包，后来的死亡不会覆盖它。完整世界和全部个体状态另行保存。

## 吞食是否真的得到营养

| 分支 | 累计吞食 | 300秒后新增 | 零能量吞食 | 共获得能量 | 共支付外壳代价 |
| --- | --- | --- | --- | --- | --- |
{energy_table}

共同阶段199.62秒，15号包裹68号，持续300毫秒，超过含外壳的286.87毫秒要求；但猎物的身体储备已为零，吞食者得到0能量，还支付2.25外壳代价。15号属于other，并非59号候选后代。当前环境只转移猎物剩余的身体储备，不把身体材料或Core储备转为食物；因此“能吃掉”与“靠捕食养活自己”不是同一件事。减少营养可能让猎物也空腹，从而削弱捕食的收益，不能默认减粮必定筛选出捕食者。

本轮观察后提出另版环境候选：形成躯体时支付的部分能量作为可消化身体材料保存，被吞食时有损耗地转移，并纳入能量账。它是环境机制建议，本轮未实施；不把此后可能的用户决策倒写成E38已有规则。

用户在E38运行期间已批准另版实现，新环境通过工程校准，E38继续使用旧规则。[追加决定与工具验证](tooling-addendum.md)。

## 结论边界与下一步

减少食物是环境压力，而不是向内核注入“捕食才好”。它可能促进吞食收益，也可能单纯使更多个体饿死。本轮保留实际方向，不把更少个体自动解释成捕食成功。即使重复吞食达标，仍未分离躯体几何、初始运动映射、结构经历和内部联想的贡献，更不把它直接写成学会主动追猎。进一步归因需要用同一候选及相同完整环境做经历重置、内部通路消融和配对对照。

包裹保持时间与外壳规则未为结果而调小，Core动力学未改。下一次值得针对的方向是吞食过程中的进入、持续包裹与脱离，以及成功躯体是否在新环境保持优势；不是无限延长本轮。

## 交付与资源

模拟累计{a['wall_seconds']/60:.2f}墙钟分钟。逐段状态、实际时间、完整指标及能量误差见[结果表](results.json)。录像为完整实测海洋，分支分别输出；候选在“模型与证据→物种库”。原始文件`.work/ocean-species-20261004`，不覆盖E37，也没有扫描或复制旧大数据。

[事前设计与用户原话](design.zh.md) · [命令和保存规则](README.md) · [物种库说明](../../../docs/zh/plans/species-library.md)
'''
    en=f'''# E38: can a successful individual seed a reusable enclosure lineage?

2026-10-04 · Project`{project}`.

{'The predeclared repeated-enclosure criterion was met in: '+', '.join(passed)+'.' if passed else 'No branch met the predeclared repeated-enclosure criterion. A reliably repeating enclosure lineage has not been obtained in this batch. All candidates and failures are retained.'}

Actual endpoints follow. Only a900s endpoint completes the registered duration. A resource pause is not individual death and is not presented as a completed horizon.

| Branch | Actual simulation s | Stop status |
| --- | --- | --- |
{time_table}

Actual shared-account usage rose from24% to27%, reaching the registered +3-point extension stop. The active control segment finished normally at900s; reduced600–900s was not started. The table below compares only the common600s endpoint. The extra control observation is separate. [Turning candidates and closeout](turning-and-closeout.md) describes14 live snapshots from10 source identities, including two individuals with repeated turns followed by feeding; none also has enclosure evidence.

Criterion: at least3 enclosure consumptions by at least2 candidate-lineage individuals in a new habitat independent ofE37. Successful offspring are additionally identified as intergenerational retention. All bodies use Core; varied founder morphology is not random motor control.

| Branch (common600s) | Lineage | Physical survivors | Body reserve>0 | Nutrient intake | Captures | Births | Highest generation |
| --- | --- | --- | --- | --- | --- | --- | --- |
{table}

At600s, original supply yielded858 nutrient ingestions,42 physical survivors and24 births; reduced supply yielded740,38 and21. Neither added a consumption after the fork. Here scarcity reduced feeding and reproduction without increasing enclosure consumption.

Candidate begins with11 inherited individuals; other begins with42. Unequal population totals do not establish per-individual advantage. E38 generation0 inherits E37 generation1; local generations restart at0.

The source is individual59's300s live snapshot, after its226.06s enclosure of32. Researcher copies inherit structure, body and mapping, clear activity and receive the same ordinary founder energy. Original individuals/states are preserved. Full neighbors, random food, flow,temperature,proprioception and collisions remain.

The shared0–300s prefix is simulated once. Complete-state forks retain1particle/s(control) or change future replenishment to1/2s(reduced), without deleting existing food. They are paired forks, not two independent environments.

| Branch | Simulation s | Predator→prey | Predator lineage | Local generation | Radius mm | Energy received |
| --- | --- | --- | --- | --- | --- | --- |
{event_table}

Process summary: {attempts}. This distinguishes absent encounters from containment that ends before successful consumption.

Shared-prefix events listed in both branches are one event. Each successful event immediately archives a body/brain bundle; later starvation cannot overwrite it. Full population/world snapshots are also retained.

| Branch | Cumulative captures | Added after300s | Zero-energy captures | Energy received | Shell cost |
| --- | --- | --- | --- | --- | --- |
{energy_table}

At199.62s, individual15 enclosed68 for300ms, exceeding its286.87ms shell-adjusted requirement. It received0energy because prey body reserve was empty, while paying2.25 shell cost. Predator15 belongs to other, not the59 candidate lineage. The environment transfers only remaining prey body reserve, not tissue-material or Core energy. Killing a body is therefore distinct from feeding oneself. Scarcity may also empty prey reserves and weaken predation's benefit; reducing food is not guaranteed to favor predators.

An observation-driven proposal is to retain part of body-construction energy as digestible material and transfer it with losses, with a balanced ledger, in a separate environment version. It was not implemented inE38; later decisions must not be backdated as existing rules.

The user approved that separate implementation while E38 was still running. The new apparatus passed engineering calibration; E38 remains unchanged. [Additional decision and validation](tooling-addendum.md).

Reduced nutrition is environmental selection pressure, not a neural instruction to hunt. It may increase predation's relative benefits or merely cause starvation. Repeated enclosure, if obtained, does not yet separate body geometry,wiring,structural experience and internal activity, nor demonstrate active pursuit. Paired history resets and internal-pathway ablations in complete habitats are subsequent questions. No Core or containment/shell threshold was tuned to obtain success.

Simulation wall time{a['wall_seconds']/60:.2f}min. [Actual segment outcomes, times and groups](results.json). Videos retain complete habitats and separate branches. Species candidates are in Models & evidence → Species library. Raw evidence:`.work/ocean-species-20261004`; E37 is intact, without duplicate bulk archives.

[Preregistration](design.en.md) · [Operations](README.md) · [Library](../../../docs/en/plans/species-library.md)
'''
    for language,body in [('zh',zh),('en',en)]:
        with (HERE/f'report.{language}.md').open('x',encoding='utf-8') as f:f.write(body)
    print(json.dumps({'criterion_met':passed}))


if __name__=='__main__':main()
