"""Write the final report only after all four registered worlds finish."""
import json
from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json


def build():
    data=read_json(WORK/'findings.json');cases=data['cases']
    expected={f'g{g}-{mode}' for g in (0,1) for mode in ('core','random')}
    if set(cases)!=expected or any(c['status']!='horizon_paused' for c in cases.values()):
        raise RuntimeError('all registered worlds must finish before final reporting')
    table=[];changes=[]
    for g in (0,1):
        c,r=cases[f'g{g}-core'],cases[f'g{g}-random']
        changes.append(f"{100*(c['food']/r['food']-1):+.1f}%")
        for mode in ('core','random'):
            x=cases[f'g{g}-{mode}']
            cap='>120 s' if x['first_observed_cap_s'] is None else str(x['first_observed_cap_s'])+' s'
            table.append(f"| {g+1} | {mode} | {x['food']} | {x['births']} | {x['alive']} | {x['living_body_s']:.2f} | {x['food_per_body_s']:.5f} | {cap} |")
    table='\n'.join(table);minutes=sum(c['wall_seconds'] for c in cases.values())/60
    assert all(c['captures']==0 for c in cases.values())
    failures={key:c['body_failures'] for key,c in cases.items()}
    population=[cases[f'g{g}-core']['alive']-cases[f'g{g}-random']['alive'] for g in (0,1)]
    direction='两对均更高' if all(cases[f'g{g}-core']['food']>cases[f'g{g}-random']['food'] for g in (0,1)) else '不同世界的方向不一致'
    en_direction='higher in both paired worlds' if direction=='两对均更高' else 'not consistently higher across both worlds'
    zh=f'''# E33：拿掉相互吞食，意识组的摄食与种群表现怎样？

[English](report.en.md) · [登记方案](design.zh.md) · [执行记录](execution-notes.md) · [操作](README.md)

登记于2026-10-03，完成于2026-10-04。四个120模拟秒世界全部完成，来源是两个独立环境种子；四个分支不是四个独立环境重复。

## 直接答案

**禁止相互吞食后，意识组摄食{direction}：两对分别比随机组{changes[0]}、{changes[1]}。**末存活差为{population[0]:+d}和{population[1]:+d}。本实验保留全部身体、随机营养刷新、水流、温度、碰撞、本体感官、变异、繁殖及有限供能，不是单个体小装置。

| 世界 | 驱动 | 营养摄入 | 新生个体 | 末存活 | 累计活体秒 | 营养/活体秒 | 首次到达97个体 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
{table}

![禁止吞食后的种群和摄食过程](figures/no-predation.png)

“>120 s”表示观察结束尚未到达上限，不能说谁更早达到。死亡原因原始汇总为`{json.dumps(failures,ensure_ascii=False)}`；没有死亡时，末存活差来自繁殖，不能改称已经证明更长寿。观察到120秒只是保存并暂停，不把期限设为个体死亡年龄。

## 这回答了此前哪个疑点

E32允许吞食时，意识组摄食213/270颗，随机组197/180颗；但末存活是28/29对32/30，意识组反而少4/1个。同时意识组捕获34/43个，随机组28/26个。现在关闭相互吞食，食量与种群差发生上述变化。**因此，仅凭E32末存活较少来否定意识控制，是不成立的；捕食环境确实改变了人口统计的解释。**

这不是说已经把E32每一例减少都逐一证明为“更擅长捕猎”。禁止吞食也让原本会成为猎物的个体继续摄食和繁殖，后续生态会分岔；不能把两轮总量相减当成单一神经机制的精确效应。捕获行为的局部原因交由另行登记的E34分析。

## 对照究竟改变了什么

复用E32的两个种子、同样的53个初始身体、1.2米边长、360颗初始营养、每秒补1颗、容量4096、种群上限97，以及全部原参数；只在新世界显式关闭原有`predation`。初始随机位置、身体参数和感官映射按相同种子生成，后续各组行为引起的世界变化自然保留。

该开关关闭吞食/捕获链，包括依赖捕获状态的持续黏附和相关消耗；几何碰撞及反馈仍存在。不能把它说成仅取消最后一下吞咽而其余钳制都完全不变。设计阶段已登记此边界。

随机组用原有每1模拟秒更新的独立随机动作；其内核仍接收自身实际感官输入并耗能，但输出不控制身体。**这是随机控制对照，不是已经停用整个内核的对照。**两者的区别已按用户最新要求列入下一阶段整组分叉计划。正常意识的20毫秒控制输出没有被限频、限幅或改造成随机组的节律。

本轮不改变Core动力学，不关闭遗忘、抑制、能量耗竭恢复，不注入“食物是好事”的标签。也不把整组优势直接归因于经历或联想；E32的完整环境局部静默已提供一例具体摄食贡献，E34继续定位捕获过程。

## 资源和交付

四项模拟合计{minutes:.2f}进程分钟，单worker。设计、状态、输入、事件和100毫秒生态轨迹保留；只把双语报告、图表与说明写入本机ThreeMind项目，完整证据包留本地，不扫描旧大数据、不反复重算哈希。图中每点来自实际模拟记录。

独立项目：`0d64c773-bdab-4de5-a4a5-fcbc48964403`。命令和证据目录见[README](README.md)，归档大小及报告编号见交付记录。本轮不增加一条新的意识判据，也不撤销已有`autonomy-criteria/1`结论。
'''
    en=f'''# E33: feeding and population growth without mutual predation

[中文](report.zh.md) · [Registration](design.en.md) · [Execution](execution-notes.md) · [Commands](README.md)

Registered2026-10-03; completed2026-10-04. All four120-simulated-second worlds finished. There are two independent environment seeds, not four independent ecological replicates.

## Direct answer

**Core-controlled feeding is {en_direction}: {changes[0]} and {changes[1]} relative to random control.** Final living-population differences are {population[0]:+d} and {population[1]:+d}. The complete habitats retain other bodies, random nutrient renewal, water, temperature, collisions, proprioception, mutation, reproduction and finite energy.

| World | Control | Nutrients | Births | Final alive | Living-body seconds | Nutrients/body-second | First population97 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
{table}

![Population and feeding without predation](figures/no-predation.png)

“>120 s” is right-censoring, not an observed cap time. Body-failure counts are `{json.dumps(failures)}`. In the absence of deaths, population differences reflect births, not demonstrated longevity. The120s horizon pauses and saves organisms rather than killing them.

## What changed in the interpretation

With predation in E32, Core populations ate213/270 nutrients versus197/180, but finished with28/29 living bodies versus32/30. They also captured34/43 bodies versus28/26. The no-predation results above show why fewer survivors alone cannot invalidate Core control: predation changes the population comparison.

Removing predation also lets potential prey keep feeding and reproducing. Subtracting the two experiments' totals does not isolate one neural mechanism or prove every earlier population loss resulted from superior hunting. E34 independently tests local pathways around prospective capture encounters.

## Exact comparison

The two E32 seeds,53 initial bodies,1.2m square,360 initial nutrients,one new nutrient per second,4096 nutrient capacity,97 population cap and other parameters are retained. Only the existing`predation`flag is disabled in new worlds. Initial bodies/positions/sensory mappings use paired seeds; subsequent behavior-induced environmental divergence remains natural.

The flag disables the capture/consumption chain, including capture-dependent persistent adhesion and its cost. Geometric collisions and feedback remain. This boundary was declared before simulation; it is not a final-swallow-only intervention.

Random control uses the original independent command updated every simulated second. Its Core still receives its own actual sensory input and consumes energy, while its output does not drive the body. **It is a random-controller comparison, not a fully stopped-Core comparison.** The user's newer request for whole-population copies with both versions is recorded separately. Normal Core action cadence/amplitude remain unrestricted at20ms.

No Core equations,forgetting,inhibition,energy depletion/recovery or sensory mappings changed. No good-food label was injected. The group advantage is not fully attributed to experience or association by this result; E32 contributes a specific complete-habitat feeding example, and E34 examines capture mechanisms.

## Resources and delivery

The four cases used{minutes:.2f}simulation-process minutes with one worker. States,inputs,events and100ms ecological trajectories are retained. Bilingual reports,figures and descriptions are published only to the verified local ThreeMind project; the full evidence archive stays local. No old-data scan or repeated full hashing was performed.

Project:`0d64c773-bdab-4de5-a4a5-fcbc48964403`. See[commands](README.md) and the delivery receipt for archive/report identifiers. This experiment does not introduce a new consciousness criterion or revoke the existing`autonomy-criteria/1`result.
'''
    for lang,body in (('zh',zh),('en',en)):
        with (HERE/f'report.{lang}.md').open('x',encoding='utf-8') as f:f.write(body)


if __name__=='__main__':build()
