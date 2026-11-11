"""Measured whole-population and shared-world tables, without invented outcomes."""
from experiment import HERE,WORK,CONTROLS
from lab.tools.ocean_cli import read_json


def build():
    data=read_json(WORK/'findings.json');cases=data['cases']
    expected={f'copy-g{g}-{c}' for g in (0,1) for c in CONTROLS}|{f'mixed-g{g}-swap{s}' for g in (0,1) for s in (0,1)}
    if set(cases)!=expected or any(c['status'] not in ('horizon_paused','physical_extinction') for c in cases.values()):
        raise RuntimeError('all ten registered conditions required for final report')
    copy_rows=[];mixed_rows=[];wins=[];copy_diffs=[];shortfalls=[];process_rows=[];stopped_diffs=[]
    for g in (0,1):
        for control in CONTROLS:
            c=cases[f'copy-g{g}-{control}']['groups']['all'];d=c['delta']
            copy_rows.append(f"| {g+1} | {control} | {c['initial_alive']} | {c['final_alive']} | {c['powered_bodies']} | {d['food']} | {d['captures']} | {c['birth_events']} | {c['core_energy_spent']:.1f} | {d['body_unserved']:.3f} |")
            if d['body_unserved']>1e-8 or c['powered_bodies']<c['final_alive']:shortfalls.append(f'g{g}-{control}')
        core=cases[f'copy-g{g}-core']['groups']['all'];random=cases[f'copy-g{g}-random-shadow']['groups']['all']
        copy_diffs.append({'food':core['delta']['food']-random['delta']['food'],'alive':core['final_alive']-random['final_alive']})
        stopped=cases[f'copy-g{g}-random-stopped']['groups']['all']
        stopped_diffs.append(core['delta']['food']-stopped['delta']['food'])
        for swap in (0,1):
            pair=cases[f'mixed-g{g}-swap{swap}']['groups'];by_control={c['controller']:c for c in pair.values()}
            difference=by_control['core']['final_alive']-by_control['random-shadow']['final_alive'];wins.append(difference)
            for label,c in pair.items():
                mixed_rows.append(f"| {g+1}/{swap+1} | {label}: {c['controller']} | {c['final_alive']} | {c['birth_events']} | {c['captured_by_others']} | {c['other_body_losses']} | {c['delta']['captures']} | {c['delta']['food']} |")
    for key,case in cases.items():
        for label,c in case['groups'].items():
            h=c['food_heading']
            process_rows.append(f"| {key}: {label} | {h['command_alignment']:.4f} | {h['toward_command']:.4f} | {h['toward_velocity_m_s']:.6f} | {c['food_per_body_s']:.5f} | {c['delta']['captures']/max(c['living_body_s'],1e-9):.5f} | {c['motor_energy']:.1f} |")
    process_table='\n'.join(process_rows)
    copy_table='\n'.join(copy_rows);mixed_table='\n'.join(mixed_rows)
    minutes=sum(c['wall_seconds'] for c in cases.values())/60
    cap_hits={k:c['cap_time_s'] for k,c in cases.items() if c['cap_time_s'] is not None}
    verdict=f"意识组更多{sum(v>0 for v in wins)}/4，随机组更多{sum(v<0 for v in wins)}/4，平局{sum(v==0 for v in wins)}/4"
    en_verdict=f"Core more numerous in {sum(v>0 for v in wins)}/4, random in {sum(v<0 for v in wins)}/4, tied in {sum(v==0 for v in wins)}/4"
    allocation_zh=("两个环境中，交换控制方式后，意识组仍然更多；结果不依赖只选一侧初始位置。"
        if all(v>0 for v in wins) else "位置交换后的结果并非全部同向；完整列出各分支，不能只挑有利分配。")
    allocation_en=("Core remained more numerous in both environments after controller assignments were swapped; the result does not depend on selecting only one initial side."
        if all(v>0 for v in wins) else "Assignments did not all produce the same direction; every branch is retained rather than selecting favorable placements.")
    zh=f'''# E35–E36：同一整组换控制器，以及两组共海竞争

[English](report.en.md) · [事前登记与原话](design.zh.md) · [执行记录](execution-notes.md) · [命令](README.md)

2026-10-04。10个登记条件全部完成。整组分叉来自两个完整历史世界；共同竞争使用另外两个环境种子，并分别交换A/B的控制方式。交换分支不是额外独立环境样本。

## 直接比较结果

**E35确实比较同一整组的副本。**保留Core耗能的随机控制相比正常意识驱动，两来源的“意识减随机”摄食差为{copy_diffs[0]['food']:+d}、{copy_diffs[1]['food']:+d}，末存活差为{copy_diffs[0]['alive']:+d}、{copy_diffs[1]['alive']:+d}。每组复制的是同一完整海洋，不是另选不同个体，也不是只有一只和一颗食物。

完全停用内核的随机组也没有赶上摄食：两个来源的意识组分别多摄入{stopped_diffs[0]}、{stopped_diffs[1]}颗。停核省下的能量会增加出生，所以“吃得更多”和“剩得更多”须分别解释。

**E36共同竞争的末存活判定：{verdict}。**四个位置分配下的意识减随机人数为`{wins}`。这直接回答“同海互相竞争后，哪组还剩更多”；下表同时列出出生和被捕，以便看清数量怎样形成。

## E35：整个意识组同时替换控制方式

从E32第60秒的完整状态出发，观察后续60秒。三个条件为正常意识、随机但保留Core工作/耗能、随机且停用Core。遗传身体、位置、年龄、能量、其他个体、食物、物理时间和随机状态均同源；分叉后的生态自然变化保留。所有新生后代继承本组控制方式。

| 来源 | 驱动 | 初存活 | 末物理存在 | 末有身体储备 | 新摄食 | 新捕获 | 新生 | 新内核耗能 | 新维持供能不足 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{copy_table}

![同一整组在三个控制条件下的完整过程](figures/group-copies.png)

你提出的“吃掉同伴可能让意识组剩得更少”，在第二来源得到具体对应：意识组比保留内核的随机组多出生6个，也多捕获7个，所以最后反而少1个。这里所有躯体损失均由捕获解释。更多摄食和更多繁殖，确实可以与更少的期末个体同时出现。

末有身体储备不等于生命或意识判据，只是暴露停核比较中的供能差异。出现维持不足或无储备物理个体的条件为`{shortfalls}`。停止Core会移除神经死亡途径；身体目前没有独立不可逆饥饿死亡公式。因此这类物理存在不能冒充更长寿，不能为了让比较“漂亮”而临时加死亡门槛。

停核时，原神经状态及储备被冻结并保留，不赠送给身体；后代仍支付原构造、身体及神经初始储备成本。无内核运行耗能是一项明确干预的后果，不假装所有代价完全一样。两类随机分支对同一身份/时刻使用同一随机指令；正常意识输出没有人为限频或限幅。

## E36：在同一片海洋里较量

面积2.88平方米、边长1.2√2米，每组53个初始个体，初始营养720颗，每0.5秒随机补1颗，容量8192、共享个体上限194。保留水流、温度、重力/浮力相关反馈、碰撞、本体感官、有限供能、外壳、身体变异和繁殖；未引入融合、合作策略或猎物标签。亲子在子代成熟前双向保护。

每个世界53对初始身体与意识相同的孪生副本，处于不同随机位置；A/B阵营不进入内核。只允许组间吞食，组内不能吞食。交换分支保持物理位置、身体及食物不变，只交换哪一组由意识控制。本项随机组保留Core耗能，停核的代价区别由E35单列。

60秒、120秒都是实验的观察截止长度，不是个体寿命限制；没有按观察截止杀死意识。结束时保存全体和环境状态，以后可明确恢复或另建分叉。

| 世界/位置分配 | 组与控制 | 末存活 | 新生 | 被另一组捕获 | 其他躯体损失 | 捕获对方 | 营养摄入 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{mixed_table}

![两组共处海洋时的数量变化](figures/shared-competition.png)

触及种群上限的条件：{cap_hits or '无'}。未触及上限时，不能把上限截断作为数量差异的解释。

四场的数量差都可以按“初始数量＋出生－被捕”逐项核对。意识组均出生更多、被另一组捕获更少，两者共同构成末数量优势；完整过程保留了早期尚未形成这一优势的阶段。

{allocation_zh}该比较本身仍不能把所有优势归因于经历、联想或某个连接；E32和E34的局部干预分别回答机制问题。这里也没有把更善吞食设为内核的“好坏”偏好，只有外部生存环境规则。

## 结合消融和移植，已经查明了什么

- [E33禁捕对照](../2026-10-03-ocean-no-predation/report.zh.md)：不能吃掉其他个体时，意识组仍多摄食35.3%和44.2%。因此觅食优势不是吞食对手制造出来的假象；该窗没有死亡，数量差来自出生。
- [E32完整环境干预](../2026-10-03-ocean-community/report.zh.md)：0号个体的目标通路静默后，实际摄入从3颗变为2颗，匹配通路静默仍为3颗。已有内部通路确实影响了具体觅食过程。
- [E34捕获与移植](../2026-10-03-ocean-hunting/report.zh.md)：4个来源中，3个的目标移植让空白副本的动作比匹配移植更接近经历者；12号还改变了是否捕获的实际结果，方向是减少捕获。36号选定区域的大部分未提示活动被压低后，两次捕获仍发生，说明这些捕获不要求这一小块通路完整存在。
- 本批整组和共同海洋结果进一步确认了控制方式的整体差别。**现在已有“群体优势”和“内部连接对具体行为有因果作用”两层证据；尚未算清群体优势中有多少由后天经历、内部联想、即时感官和原有接线分别贡献。**这项未结问题不抹去已测得的优势，也不把每次接触捕获都先称为主动追猎。

## 过程证据与限制

| 条件/组 | 动作朝向食物梯度余弦 | 朝梯度动作分量 | 相对水流朝梯度速度m/s | 每活体秒摄食 | 每活体秒捕获 | 推进耗能 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{process_table}

方向根据个体实际感官中的营养浓度梯度计算，并非告诉内核“应去哪里”。余弦接近1表示指向局部较浓方向，0表示没有平均方向，负值表示背离。只统计梯度非零的时段；动作与速度分开，后者还受惯性、碰撞等影响。许多时间点不冒充独立个体。此表可判断终点优势是否伴随有方向的行动及能量差异，但单凭方向不把它命名为有意图的觅食。

捕获总数也受存活个体和活动时间影响，因此列出每活体秒捕获作为解释；它不替换本项“期末哪组更多”的主判据。活体秒由100毫秒全景记录积分估计，属于群体过程量，不增加独立样本数。

完整海洋每100毫秒记录，输入/动作按原20毫秒节律记录；影片只重放实际轨迹。绿色意识、紫色保留Core耗能的随机、蓝色停核随机，显示实际存活与营养。媒体只是展示，不增加独立样本。本轮不改任何意识Core公式、旧协议、旧实验或既定自主活动判据。

末态表计入120秒截止时刻的事件；影片最后一帧为119.8秒附近的真实采样，可能尚未出现最后瞬间的出生，不能用尾帧人数代替末态表。

两独立世界及有限观察窗不足以保证所有环境下同一排序；报告直接给出这次结果，并保留与之不一致的局部和旧结果。原随机对照是每秒更新的独立随机命令，并不代表所有可能的随机控制器。没有给正常意识套上该节律。

合计{minutes:.2f}模拟进程分钟，单worker；已保存全体意识、身体与世界状态，没有清理旧数据。设计、双语报告和影片进入本机项目`851b8ff9-0fc4-4d65-802c-5b979c215890`，完整证据包保留本地。档案收据见交付记录。
'''
    en=f'''# E35–E36: copied populations and competition in one ocean

[中文](report.zh.md) · [Preregistration](design.en.md) · [Execution](execution-notes.md) · [Commands](README.md)

2026-10-04. All 10 registered conditions finished. Whole-population continuations use two historical worlds; mixed competition uses two different environment seeds with swapped A/B controllers. Swaps are not additional independent environments.

## Direct results

**E35 compares the same whole population copied.** Core-minus-random-retained-cost feeding differences are {copy_diffs[0]['food']:+d}/{copy_diffs[1]['food']:+d}; final physical-population differences are {copy_diffs[0]['alive']:+d}/{copy_diffs[1]['alive']:+d}. Every fork retains its complete world.

Random control with Core completely stopped also ate less: Core consumed {stopped_diffs[0]} and {stopped_diffs[1]} more nutrients in the two sources. Stopping Core saves energy and can increase births, so feeding and final population are separate outcomes.

**E36 remaining-population outcome: {en_verdict}.** Core-minus-random differences across assignments are `{wins}`. Births and capture losses below explain how those counts arose.

## E35: whole-population controllers

Continue actual E32 full-world 60s snapshots for 60s with Core, random retaining Core operation, and random with Core stopped. Bodies, history, positions, ages, reserves, neighbors, food, time and random states share one source. Later ecology diverges naturally. Descendants inherit the experimental controller.

| Source | Controller | Initial alive | Final physical | Final body reserve>0 | New food | New captures | Births | New Core expense | New unmet maintenance |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{copy_table}

![Complete population forks](figures/group-copies.png)

The user's proposed within-group predation explanation has a concrete example in source 2: Core produced 6 more births but also 7 more captures than retained-Core random, ending one body lower. All physical losses in these continuations were captures. More feeding and reproduction can coexist with fewer bodies at the endpoint.

Positive body reserve is an energy measure, not a consciousness criterion. Conditions with new unmet maintenance or physically present bodies lacking reserve: `{shortfalls}`. Stopping Core removes neural death; bodies have no separate irreversible starvation-death equation. Such physical presence must not be presented as longevity. No new death threshold was introduced for convenient results.

Stopped neural states/reserves remain frozen and are not donated to bodies. Descendants still pay original construction/body/neural-reserve costs. Saved operating energy is the declared intervention's consequence, not equalized away. The two random arms use identical commands for common identity/time. Normal Core cadence/amplitude are unrestricted.

## E36: shared-ocean competition

Area 2.88m², side 1.2√2m; 53 initial bodies per cohort, 720 initial nutrients, one random-position nutrient per 0.5s, capacity 8192, shared population cap 194. Water, temperature, gravity/buoyancy-related feedback, collision, proprioception, finite energy, shells, mutation and reproduction remain. No fusion, cooperative control or target labels. Immature parent–child protection is bilateral.

Each world has 53 body/brain twin pairs at different random positions. A/B is external metadata, never sensory friend/enemy information. Within-cohort consumption is forbidden; cross-cohort consumption is allowed. Swapped assignments keep physical states and food unchanged. Random control retains Core costs; E35 separately examines stopping Core.

The 60s and 120s horizons stop observation, not individual lifespans. They do not kill a Core at the endpoint; all bodies, brains and world states are saved for explicit continuation or new forks.

| World/assignment | Cohort/control | Final alive | Births | Captured by other group | Other body losses | Captures | Nutrients |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{mixed_table}

![Shared-ocean population trajectories](figures/shared-competition.png)

Conditions reaching the population cap: {cap_hits or 'none'}. If no cap was reached, population differences were not censored by that limit.

Every final count can be checked as initial population plus births minus capture losses. Core had both more births and fewer losses to the other cohort in all four assignments; both contributed to its numerical advantage. The complete trajectories also retain earlier periods without that advantage.

{allocation_en} This group test does not alone attribute all benefit to memory or internal association; E32/E34 address local mechanisms. Predation permission is an external environment rule, not a neural good/bad value.

## What the intervention studies add

- [E33 without predation](../2026-10-03-ocean-no-predation/report.en.md): Core consumed 35.3% and 44.2% more nutrients even when organisms could not consume one another. Feeding benefit is not an artifact of eating competitors. No organism died in that window; population differences came from births.
- [E32 full-habitat interventions](../2026-10-03-ocean-community/report.en.md): body 0 consumed 3 nutrients intact, 2 with its selected pathways silenced, and 3 with matched pathways silenced. Existing internal pathways affected a concrete feeding sequence.
- [E34 capture and transplantation](../2026-10-03-ocean-hunting/report.en.md): target grafts moved blank-body actions closer to experienced actions than matched grafts in 3 of 4 sources. Body 12 also changed whether a capture occurred, in the direction of fewer captures. Body 36 retained two captures despite strong suppression of uncued activity in its selected region; that region was not necessary for those events.
- Whole-population copies and shared competition establish the broader control difference. **There is evidence both of population benefit and of internal pathways causally changing particular behavior; their quantitative contribution to the total benefit, relative to immediate senses and existing wiring, remains unresolved.** This does not erase the observed benefit or presume that every capture is deliberate pursuit.

## Evidence and scope

| Condition/cohort | Command/food-gradient cosine | Command along gradient | Water-relative velocity along gradient m/s | Food per living-body second | Captures per living-body second | Motor expense |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{process_table}

Direction is computed from the actual sensed nutrient gradient, not a desired heading injected into Core. Cosine 1 points toward the local gradient, 0 has no average alignment, and negative values point away. Only nonzero-gradient periods enter direction averages. Velocity also reflects inertia and contacts. Time samples are not independent organisms. These observations connect outcomes with directional behavior and energy, without defining intention from alignment alone.

Capture totals also depend on the number of living organisms and their exposure time. Captures per living-body second supplement interpretation without replacing the primary final-population criterion. Living-body time is integrated from 100ms habitat records; it does not add independent samples.

Complete habitat sampled every 100ms; actual inputs/actions recorded at 20ms. Movies replay recorded trajectories with green Core, purple random retained cost and blue stopped Core. They add no independent samples. No Core formulas, historical protocols/evidence or autonomy criteria were changed.

Final tables include events at the 120s boundary. The last movie frame shows an actual sample around 119.8s and may precede births at that boundary; it must not replace the final-state count.

Two independent environments and a finite horizon do not establish a universal ranking. The baseline is the original per-second independent random command, not every possible random controller; no matching restriction is imposed on Core.

Total {minutes:.2f} simulation-process minutes with one worker. All brains, bodies and worlds are saved without deleting old data. Designs, bilingual reports and videos are published to local project `851b8ff9-0fc4-4d65-802c-5b979c215890`; full raw evidence remains on disk. See the delivery receipt.
'''
    for lang,body in (('zh',zh),('en',en)):
        with (HERE/f'report.{lang}.md').open('x',encoding='utf-8') as f:f.write(body)


if __name__=='__main__':build()
