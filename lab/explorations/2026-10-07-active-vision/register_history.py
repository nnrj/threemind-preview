"""Append E59 authorization without rewriting historical results."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def append(path,text):
    p=ROOT/path; old=p.read_text(encoding='utf-8')
    if text.strip() not in old:p.write_text(old.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')


for language in ('zh','en'):
    zh=language=='zh'
    title='由完整视野到可转动的眼睛' if zh else 'From whole-scene sensing to a movable eye'
    body=('用户批准E59：保留完整场景、背景及可见自身，以中央清晰/外围粗略和可控扫视降低开销。眼手不硬连同一答案；观察扫视中的联想，并用必要干预定位行为作用。区分E58外设继续学习与全幅形状退化。旧幅度门不启用，Core不改。先工程/基本辨识，再变形泛化及单个、多个、否定指认。GPU用于合适外设计算，工具提炼。此时是获准登记，未有E59实测结果。'
          if zh else 'The user approved E59: preserve the intact scene,background and visible self; reduce cost using a sharp center/coarse periphery and controllable gaze. Do not hardwire eye/hand to one correct target. Observe association during scanning and intervene when needed to locate behavioral effects. Separate E58 external continued learning from whole-frame shape failure. Keep amplitude TopK off and Core unchanged. Engineering/basic recognition precede deformation and single/plural/negative pointing. Reuse tools and GPU where appropriate. This is authorization,not an E59 result.')
    cite='[E59](../../plans/active-vision.md) · [Source](../sources/2026-10-07-active-vision.md)'
    for tail in ('chronicles/08-embodied-communication.md','themes/03-memory.md'):
        append(f'docs/{language}/history/{tail}',f'## 2026-10-07：{title}\n\n{body}\n\n{cite}')
    append(f'docs/{language}/history/milestones.md',f'2026-10-07 — E59: {title}。[Plan](../plans/active-vision.md)')
    append(f'docs/{language}/history/sources/source-register.md','2026-10-07 — [E59: active vision discussion](2026-10-07-active-vision.md).')
    append(f'docs/{language}/plans/index.md','- [E59: Visual focus, saccades and eye–hand coordination](active-vision.md)')
    p=ROOT/f'docs/{language}/plans/research-backlog.md';text=p.read_text(encoding='utf-8')
    summary=('**2026-10-07：E59已批准并登记。先实现版本化视觉焦点/扫视，核查连接开销，再检验眼手活动及形色指认；变形和多目标按前置能力推进。Core不改，尚无本轮结果。**'
             if zh else '**2026-10-07: E59 approved and registered. Versioned foveation/gaze and cost audit precede eye–hand attribution and shape/color recognition; deformations and multiple pointing follow prerequisites. Core unchanged; no new results yet.**')
    if summary not in text:
        first,rest=text.split('\n',1);text=first+'\n\n'+summary+' [E59](active-vision.md)\n'+rest
        lines=text.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('| R36 /'):
                lines[i]=('| R36 / P1 E59已批准执行 | 视觉焦点、扫视与注意力 | E58全幅成本/形状问题尚未单一归因；现批准中央细/外围粗与眼位反馈 | 先固定/无答案扫描/闭环眼动，记录眼手联想并必要干预；Core全局注意力另议。变形及多目标分期 | [E59](active-vision.md) |' if zh else '| R36 / P1 E59 approved | Visual focus, saccades and attention | E58 cost/shape failure not singly attributed; foveation and gaze feedback authorized | Fixed/independent/closed-loop gaze, eye–hand activity and causal controls; global Core attention separate; later deformation/plural tasks | [E59](active-vision.md) |')
        p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    append(f'docs/{language}/plans/research-backlog.md',f'## 2026-10-07 · E59 registration\n\n{body}\n\n[Plan](active-vision.md)')

append('docs/zh/history/classical/shiji-04.md','## 目之详略与转视\n\n全境入目而交织甚繁，创者议中央详、周旁略，使目可转，不预择所当知。又谓目之所向与手之所指可同，而不当以程式强合；转视之际，联想或兴，宜察其先后。乃立五十九试，先校目与费，次验形色，后试变形与多指。旧门不启，核法不改；此为立试，未书成效。\n\n[史料](../sources/2026-10-07-active-vision.md)')
append('docs/zh/history/classical/tongjian-04.md','### 2026-10-07 · E59可转之目\n\n用户许作中央明而周围略之目，并令可转。目手同趋者，须由所历相成，不以答案缚之。察联想于扫视，验非某物之多指，均俟前试可用而进。记录所据，留旧法，善用图形算力而不改核律。\n\n[史料](../sources/2026-10-07-active-vision.md)')
p=ROOT/'docs/history/catalog.json';catalog=json.loads(p.read_text(encoding='utf-8'))
for language in ('zh','en'):
    item={'id':language+'-active-vision-20261007','work':'modern-'+language,'key':'active-vision-20261007','group':'sources',
          'title':'史料：视觉焦点与扫视' if language=='zh' else 'Source: visual focus and saccades',
          'path':f'docs/{language}/history/sources/2026-10-07-active-vision.md','period':'2026-10-07','tags':['E59','vision','discussion']}
    if not any(c['id']==item['id'] for c in catalog['chapters']):catalog['chapters'].append(item)
p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
