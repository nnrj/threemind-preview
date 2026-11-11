"""Generate bilingual measured E37 reports without replaying the experiment."""
import json
from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json,write_json


def main():
    a=read_json(WORK/'analysis.json');captures=a['captures'];changes=a['radii_change']
    chain=a['sample_lineage'];counts=a['alive_generations']
    lineage=' → '.join(f"#{b['id']} (G{b['generation']}, {b['radius']*1000:.2f} mm)" for b in chain)
    table='\n'.join(f"| {b['id']} | {b['parent'] if b['parent'] is not None else '—'} | {b['generation']} | {b['radius']*1000:.3f} | {b['shell']:.3f} | {b['elongation']:.3f} |" for b in chain)
    events='\n'.join(f"| {e['time_us']/1e6:.2f} | {e['predator']} → {e['individual']} | {e['predator_radius_mm']:.3f} / {e['prey_radius_mm']:.3f} | {e['contact_us']/1e6:.3f} / {e['required_us']/1e6:.3f} | {e['transferred']:.2f} |" for e in captures[:20])
    protocol=read_json(WORK/'protocol.json')
    totals=a['totals'];project=read_json(WORK/'platform.json')['project_id']
    zh=f'''# E37：仅包裹吞食的意识驱动海洋与代际变化

2026-10-04 · 独立项目 `{project}` · 原始证据 `.work/ocean-enclosure-20261004`。

## 直接结果

本轮从53个意识驱动个体开始，实际观察 **{a['seconds']:g}模拟秒**，出生 **{a['births']}** 个后代，最高到 **第{a['max_generation']}代**，结束时 **{a['alive']}** 个躯体存活。完成 **{len(captures)}次完整包裹吞食**；没有接触捕获或随机驱动个体。营养摄入{a['food_eaten']}颗，海中尚余{a['remaining_food']}颗。结束状态为`{a['status']}`，不是把仍活着的个体判死。

后代相对直接亲代的半径：{changes['larger']}次变大、{changes['smaller']}次变小、{changes['same']}次不变。变异不是每次重置到创始体；它从当代亲本参数继续变化。最高代次表示继承链的深度，不是已经出现相同数量的新物种。

末存活代次分布：{'、'.join(f'第{g}代 {n}个' for g,n in counts.items())}。

其中身体储备仍大于零的有{a['powered_bodies']}个；累计未能支付的身体维持需求为{a['body_unserved']:.2f}单位。这里的“存活”首先指躯体仍物理存在，储备不足会限制推进，不把这些个体一概叫作仍有充分活动能力。身体失效分类为`{a['failure_counts']}`，另有原始Core活动/供能状态可查。

![完整过程](figures/process.png)

## 一个实际亲缘链

按“末态存活者中代次最深、同代取较小身份号”选择，不按体型或捕食成功挑选。半径是保持平面面积相等的尺寸参数，不是所有方向的外缘半径。父母即使已死亡，其原始身体和脑状态仍保留。

{lineage}

| 身份 | 亲代 | 代次 | 半径mm | 外壳 | 伸长 |
| --- | --- | --- | --- | --- | --- |
{table}

## 实际包裹事件

以下列前20次，全部事件另存`analysis.json`及各段`events.json`。时间为完整海洋的模拟时间；不是在剪裁出来的一对个体间重新上演。

| 模拟秒 | 吞食者→被吞食者 | 双方半径mm | 包裹持续/要求秒 | 转入能量 |
| --- | --- | --- | --- | --- |
{events or '| — | 本轮无完成事件 | — | — | — |'}

更大躯体拥有几何包容能力，同时也承担原先按体积增长的运动、维持与繁殖构造成本。一次完整海洋能显示真实继承和捕食过程，但不能单凭最大体型或末态数量证明“大一定更好”；本轮没有额外做体型消融或多环境选择优势实验。原E32—E36的控制与内部活动结论不被这段展示性长观察替代。

## 为何另建环境版本

旧Ocean/3在完整包裹前就分离重叠躯体，直接关闭接触捕获会阻挡进入。14/7毫米躯体的5秒相向运动校准最小中心距20.87毫米，包裹却要求≤7毫米。新`threemind.ocean-enclosure/1`允许几何上能容纳对方的软包膜部分重叠进入；只有完整包裹持续满足要求才吞食。外壳延长时间并增加吞食开销。形状不相容者保留碰撞分离，不添加吸引、追逐指令或神经奖励。这是简化的软包膜几何环境，不是流体/组织仿真。

因此它包含“关闭接触吞食”和“软膜允许进入”两个明确环境变化，不能当成与E35只改一个参数的对照。Core仍为`continuous-memory/2`；传播、遗忘、抑制、能量及原有神经遗传规则未改。

## 录像与保存

全景录像保留全部个体、食物和随机补充，6倍速；颜色表示代次，**不是意识/随机两组**。右栏展示代次人数、实际尺寸和一条当时最深亲缘链。吞食片段按每段首个自然事件选择，保留全海，另加局部放大；有事件才生成，不补拍。影片是实测100毫秒采样的保持播放，没有插值或重演。

完整输入和动作每20毫秒无损保存；150秒检查点及段首尾脑/世界状态保留。已付身体维持与运动耗能分别为{totals['body_heat']:.2f}总身体耗散中的组成项；总账误差{a['energy_error']:.3g}。总进程模拟时间{a['wall_seconds']/60:.2f}分钟。出生上限/种群上限导致的暂缓计数{totals['deferred_births']:g}，营养容量阻塞{totals['nutrient_capacity_blocks']:g}；暂缓计数不是独立个体数。详细资源、录像及本地交付清单见交付记录。

[登记、预算与用户原话](design.zh.md) · [执行记录](execution-notes.md) · [命令](README.md)
'''
    # Body heat is an aggregate; do not pretend it equals a component breakdown.
    zh=zh.replace('已付身体维持与运动耗能分别为'+f"{totals['body_heat']:.2f}"+'总身体耗散中的组成项',
        f"身体运动、维持等合计耗散{totals['body_heat']:.2f}能量单位")
    en=f'''# E37: all-Core enclosure-only ocean and inherited variation

2026-10-04 · Project `{project}` · Evidence `.work/ocean-enclosure-20261004`.

## Measured results

53 founders, **{a['seconds']:g} simulated seconds**, **{a['births']} offspring**, highest **generation{a['max_generation']}**, **{a['alive']} physical survivors** and **{len(captures)} completed enclosure consumptions**. All bodies used Core control; no contact capture or random controller. Nutrients consumed{a['food_eaten']}, remaining{a['remaining_food']}. Status`{a['status']}` preserves live states rather than killing at the horizon.

Offspring radius versus immediate parent: {changes['larger']} increases, {changes['smaller']} decreases, {changes['same']} unchanged. Mutation starts from current parental traits, not a reset founder. Generation depth is not a count of species. Living generation counts: {counts}.

{a['powered_bodies']} surviving bodies still have positive bodily reserves. Cumulative unmet bodily maintenance is{a['body_unserved']:.2f}units. Physical presence is distinguished from funded motion; low reserves limit propulsion. Recorded body-failure categories: `{a['failure_counts']}`. Raw Core activity/energy states remain available.

![Complete process](figures/process.png)

## An actual ancestry chain

Selected by deepest generation among final survivors, then lowest ID, not size/capture success. Radius is the equal-planar-area parameter, not extent in every direction. Dead ancestors remain archived.

{lineage}

| ID | Parent | Generation | Radius mm | Shell | Elongation |
| --- | --- | --- | --- | --- | --- |
{table}

## Recorded enclosure events

First20 below; all events remain in`analysis.json` and per-segment`events.json`. Times refer to the complete habitat, not an isolated reenactment.

| Simulation s | Predator→prey | Radii mm | Held/required s | Energy received |
| --- | --- | --- | --- | --- |
{events or '| — | No completed consumption | — | — | — |'}

Larger bodies gain geometric containment capacity but retain volume-dependent maintenance, locomotion and construction costs. A single long habitat records actual inheritance and consumption; it does not by itself establish a general size advantage. No extra body-size ablation or multi-environment selection trial was run. This observation does not replace E32–E36's control/internal-activity evidence.

## Separate apparatus boundary

Ocean/3 overlap separation obstructed entry. A5-second inward-motion calibration of14/7-mm bodies reached20.87-mm minimum center distance versus≤7mm required. New`threemind.ocean-enclosure/1` admits partial overlap only when the larger capsule can geometrically contain the other at current orientations. Consumption still requires continuous actual complete enclosure; shells extend dwell and impose energy cost. Incompatible shapes separate. No attraction, pursuit or neural reward is added. This is a declared soft-envelope approximation, not a tissue/fluid simulation.

Removal of contact capture and membrane entry are two explicitly declared environmental changes, not a one-factor E35 comparison. Core`continuous-memory/2`, propagation, forgetting, inhibition, energy and neural inheritance remain unchanged.

## Footage and evidence

The continuous full-habitat movie runs6×. Colours indicate generations, **not Core/random groups**. The panel displays population by generation, actual sizes and a current deepest ancestry example. Event excerpts select the first natural consumption of each segment, retain the full habitat and add a magnified view. Recorded100ms samples are held without invented interpolation or replay simulation.

Lossless inputs/actions20ms;150s checkpoints and segment boundary full states. Body dissipation{totals['body_heat']:.2f}, energy-ledger error{a['energy_error']:.3g}. Simulation process time{a['wall_seconds']/60:.2f}minutes. Capacity-deferred birth attempts{totals['deferred_births']:g}, nutrient capacity blocks{totals['nutrient_capacity_blocks']:g}; attempts are not independent individuals. Delivery lists resources and actual media.

[Registration](design.en.md) · [Execution](execution-notes.md) · [Commands](README.md)
'''
    for lang,body in [('zh',zh),('en',en)]:
        target=HERE/f'report.{lang}.md'
        with target.open('x',encoding='utf-8') as f:f.write(body)
    print(json.dumps({'seconds':a['seconds'],'births':a['births'],'captures':len(captures),'generation':a['max_generation']}))


if __name__=='__main__':main()
