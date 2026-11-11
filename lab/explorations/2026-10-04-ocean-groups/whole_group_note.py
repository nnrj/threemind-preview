"""Seal the completed whole-group stage while shared competition continues."""
from experiment import HERE,WORK,study
from lab.tools.ocean_cli import read_json
from lab.tools.study_publication import Publication
from publish import links


def build():
    cases=read_json(WORK/'findings.json')['cases'];rows=[]
    for g in (0,1):
        for control in ('core','random-shadow','random-stopped'):
            c=cases[f'copy-g{g}-{control}']['groups']['all']
            rows.append(f"| {g+1} | {control} | {c['delta']['food']} | {c['delta']['captures']} | {c['birth_events']} | {c['final_alive']} | {c['core_energy_spent']:.1f} | {c['food_heading']['command_alignment']:.4f} |")
    table='\n'.join(rows)
    texts={
      'zh':f'''# E35整组同源比较：已完成阶段结果

2026-10-04。六个60秒分支均完成，E36共海竞争尚在运行。本记录封存这一阶段，不借用尚未产生的E36结果。

**同一整组复制后，意识组的觅食优势仍然出现。**两来源相对于保留内核耗能的随机组，多摄食18.6%和89.1%；相对于停核随机组，分别多18.6%和75.4%。这不是挑了不同身体比较：每个来源从同一个完整世界状态分出三组，连当时的营养、其他个体及环境时间也一并复制。

| 来源 | 控制器 | 新摄食 | 新捕获 | 新生 | 末物理存在 | 内核新增支出 | 动作朝营养梯度余弦 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{table}

`random-shadow`保留自己真实感官输入及内核耗能，只断开控制输出；`random-stopped`完全停止内核输入、供能和推进。两种随机对共同身份/时刻用同一随机命令；意识输出没有限频或匹配随机节律。两组意识的方向余弦明显高于随机，说明新增摄食伴随有方向的行动，不只是最后多碰到几颗的一个孤立数字。该方向指标单独仍不证明意图或定位联想机制；区域干预另见[E34](../2026-10-03-ocean-hunting/report.zh.md)。

人口与觅食并非同一排名。第一来源意识捕获更少，第二来源更多；全都是同组海洋中的互食。第二来源意识组的13次出生仍抵不过18次被捕，最终28体；停核随机组出生12、被捕12，维持33体。停核相对保留耗能的随机组，分别多1和5次出生，同时后一来源多1次捕获，解释了末人口差。

本窗口两停核组末尾所有身体仍有储备，维持供能不足均为0；“停核缺少独立身体饥饿死亡规则”的装置边界仍须保留，但没有在这两条件中形成无能量躯体存活的假优势。保留内核的几个条件出现短时身体供能不足；本窗最终身体损失均可由捕获解释，不据此宣称寿命延长。

本项只涉及两个历史世界、有限窗口和既定独立随机控制器。继承经历在所有三组起点相同，故比较的是谁控制身体，以及是否继续付内核运行成本；不是再做一次抹除经历实验。下一阶段E36让两组同海竞争，并用位置交换辨别地利。[登记](design.zh.md)
''',
      'en':f'''# E35 whole-population controls: completed stage

2026-10-04. All six 60-second forks finished; E36 shared competition is still running. This record does not use future E36 outcomes.

**Feeding advantage persists when the same complete population is copied.** Core feeds 18.6% and 89.1% more than random control retaining neural costs, and 18.6% and 75.4% more than stopped-Core random control. Each triple shares one complete physical and neural world source, including all neighbors, nutrients and environmental time.

| Source | Controller | New food | New captures | Births | Final physical | New Core expense | Command/food-gradient cosine |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{table}

Random-shadow retains its actual sensory inputs and Core costs but disconnects motor output. Random-stopped freezes Core input, energy supply and advance. Both use identical random commands for common identity/time. Core cadence and amplitude remain unrestricted. Its higher directional alignment accompanies feeding advantage, rather than reporting only endpoints. Alignment alone does not establish intention or locate associative mechanisms; see [E34](../2026-10-03-ocean-hunting/report.en.md).

Population and feeding do not have one ranking. Core captures fewer peers in source one and more in source two. Source two's 13 births and 18 capture losses leave 28 bodies; stopped random has 12 births and 12 losses, leaving 33. Stopping Core adds 1 and 5 births relative to random-shadow; the second source also gains one capture, explaining the final population differences.

All stopped-Core bodies have positive reserves at the endpoint and neither condition has unmet bodily maintenance. The missing independent bodily starvation-death rule remains a limitation for longer stopped-Core ecology, but it did not create unfunded-body survival here. Several running-Core conditions incur transient maintenance shortfalls; all final body losses in this window are attributable to captures, not a longevity demonstration.

Two historical sources, a finite window and one random policy bound the claim. All three arms begin with the same experience; this tests control and running costs, not history erasure. E36 next compares both groups in one habitat with controller-position swaps. [Preregistration](design.en.md)
'''}
    for lang,body in texts.items():
        p=HERE/f'whole-group-results.{lang}.md'
        if not p.exists():p.write_text(body,encoding='utf-8')


def publish():
    build();s=study();p=Publication(s)
    try:
        for lang in ('zh','en'):
            body=links((HERE/f'whole-group-results.{lang}.md').read_text(encoding='utf-8'))
            p.document('record:whole-group:'+lang,'record','E35 整组同源结果 / Whole-population results '+lang,body)
    finally:s.db.close()


if __name__=='__main__':publish()
