"""Idempotent documentation registration/append for this dated study."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]


def append(path,text,marker):
    path=ROOT/path;s=path.read_text(encoding='utf-8')
    if marker not in s:path.write_text(s.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')


def main():
    catalog=ROOT/'docs/history/catalog.json';data=json.loads(catalog.read_text(encoding='utf-8'))
    for lang,title in [('zh','史料：学前探索与先天偏好'),('en','Source: bodily exploration and innate preferences')]:
        item={'id':f'{lang}-body-exploration-20261007','work':f'modern-{lang}','key':'body-exploration-20261007',
            'group':'sources','title':title,'path':f'docs/{lang}/history/sources/2026-10-07-body-exploration.md',
            'period':'2026-10-07','tags':['E61','development','discussion']}
        if not any(x['id']==item['id'] for x in data['chapters']):data['chapters'].append(item)
    catalog.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for lang in ('zh','en'):
        zh=lang=='zh';base=f'docs/{lang}'
        text=('用户提出先学会身体、再接受教师教学，补充彩色玩具、感官反馈、NPC和先天偏好的候选。E61先比较空白意识自由探索、等时环境、同动作暂关结构学习；后续同课程，固定读头及连接干预归因。只增外设，不改Core。全身移动、NPC/语言中枢和环境选择先天偏好留待独立条件。此处为登记，尚无完整结果。' if zh else
            'The user proposed learning the body before instruction, with colored toys, sensory feedback, and possible NPC/innate-preference conditions. E61 compares blank-Core exploration, equal-time quiet exposure and matched actions without preschool structural learning, followed by identical lessons and fixed-reader/connection controls. Only external apparatus changes. Locomotion, NPC/language exposure and evolved preferences remain separate future conditions. This is registration, not a completed result.')
        links=f'[E61](../../plans/body-exploration.md) · [Source](../sources/2026-10-07-body-exploration.md)'
        append(f'{base}/history/chronicles/08-embodied-communication.md','## 2026-10-07：E61 / Body before teaching\n\n'+text+'\n\n'+links,'E61 / Body before teaching')
        append(f'{base}/history/themes/02-instruments.md','## 2026-10-07：E61 / Multisensory playground\n\n'+text+'\n\n'+links,'E61 / Multisensory playground')
        append(f'{base}/history/milestones.md',f'| 2026-10-07 | E61: '+('教学前学会身体，已登记' if zh else 'Learning the body before instruction, registered')+' | [Plan](../plans/body-exploration.md) |','E61:')
        append(f'{base}/history/sources/source-register.md',f'- 2026-10-07 / E61：[Body exploration](2026-10-07-body-exploration.md)，'+('原话、后续评估与文献边界。' if zh else 'Original statements, assessment and evidence boundaries.'),'2026-10-07 / E61')
        append(f'{base}/plans/index.md','- [E61: '+('学前探索与学会身体' if zh else 'Bodily exploration before teaching')+'](body-exploration.md)','body-exploration.md')
        path=ROOT/f'{base}/plans/research-backlog.md';s=path.read_text(encoding='utf-8')
        if '| R38 /' not in s:
            lines=s.splitlines();at=next(i for i,x in enumerate(lines) if x.startswith('| R37 /'))+1
            lines.insert(at,('| R38 / P1 已批准，E61实施中 | 教学前自由探索能否改善眼手控制 | 两来源、三种学前条件、相同教学与归因；保留背景与Core | 先测探索机会；先天偏好/移动/NPC另列，形色扩展依赖基本控制 | [E61](body-exploration.md) |' if zh else
                '| R38 / P1 Approved, E61 in progress | Can bodily exploration improve later eye/hand control? | Two sources, three preschool conditions, identical teaching and attribution; background and Core preserved | Measure exploration opportunity first; innate selection/locomotion/NPC separate, shape/color depends on basic control | [E61](body-exploration.md) |'))
            lines.insert(2,('**2026-10-07：E61学前探索已登记并实施。** 玩具、触觉、双耳与自发声音反馈已接通；先检查真实探索，再判断教学增益。先天偏好不是本轮前置要求。[计划](body-exploration.md)\n' if zh else
                '**2026-10-07: E61 bodily exploration registered and in progress.** Toys, touch, stereo sound and vocal feedback connected. Measure actual exploration before interpreting teaching gains. Innate selection is not a prerequisite this batch. [Plan](body-exploration.md)\n'))
            path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        append(f'{base}/plans/research-backlog.md','### 2026-10-07 · E61 registration\n\n'+text+'\n\n[E61](body-exploration.md)','E61 registration')
    append('docs/zh/history/classical/shiji-04.md','## 学体议（2026-10-07，E61登记）\n\n既教转眸指物而未稳，乃议先使之识其身。置彩玩，容推而复返，触之有声；目手口耳，各受其报。以自游、静处、同行而暂罢塑学三者相校，继而同授其课。若先天偏好有益，当另由境选，不径书趋物之令于核。此记议定，功效未验。\n\n[今文与原话](../sources/2026-10-07-body-exploration.md)','学体议（2026-10-07，E61登记）')
    append('docs/zh/history/classical/tongjian-04.md','## 十月七日，议先游而后教（E61）\n\n研究者谓：婴儿学前，尝以身探物；可置玩具，使目手之动与诸感相合。乃定三途相校，先观其能否真有所探，再问教后有无进益。全身迁行、旁人言语、先天偏好，各候别试，不杂以乱其因。\n\n[今文与原话](../sources/2026-10-07-body-exploration.md)','议先游而后教（E61）')


if __name__=='__main__':main()
