"""Idempotent registration of E58 discussion; no old report edits."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]


def append(path,text):
    p=ROOT/path
    old=p.read_text(encoding='utf-8')
    if text.strip() not in old:p.write_text(old.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')


for language in ('zh','en'):
    zh=language=='zh'
    title='短时痕迹也是记忆，查内容而非资格' if zh else 'Short traces are memory; investigate content, not eligibility'
    text=('用户指出教师指向的短时痕迹与物体—名字对应同属过去经历塑成的内在模式。助手接受此前对立过强，改问模式包含何种关系、由内核与外设怎样分工。E57的因果状态交换与E50的连接证据仍保留，不把短暂、感官来源判成无记忆。另查课堂：身体反馈已有，自身视觉缺失；共享四视场读法不等于完整视野。用户授权E58依次补全视野、区分反馈与控制、平衡末段经历并比较固定/可塑外设，旧核与旧证据不改。当前为登记，尚无新结果。'
          if zh else 'The user noted that teacher-pointing traces and object–name correspondences can both be experience-shaped patterns. The assistant accepted that the earlier opposition was too strong: investigate content and division of work, not whether short sensory traces deserve to be memory. E57 causal state swaps and E50 connection evidence remain. Body feedback exists, visible self does not; shared four-field readers are not a whole-scene eye. E58 is authorized to complete vision, separate feedback/control, balance terminal experience and compare fixed/adaptable external readers. This is registration, not a new measured result; old Core and evidence stay intact.')
    cite='[E58](../../plans/embodied-memory-content.md) · [Source](../sources/2026-10-07-memory-content.md)'
    append(f'docs/{language}/history/chronicles/08-embodied-communication.md',f'## 2026-10-07：{title}\n\n{text}\n\n{cite}')
    append(f'docs/{language}/history/themes/03-memory.md',f'## 2026-10-07：{title}\n\n{text}\n\n{cite}')
    append(f'docs/{language}/history/milestones.md',f'2026-10-07 — E58: {title}。[Plan](../plans/embodied-memory-content.md)')
    append(f'docs/{language}/history/sources/source-register.md','2026-10-07 — [E58 dialogue: memory content and feedback](2026-10-07-memory-content.md).')
    append(f'docs/{language}/plans/index.md','- [E58: Whole-scene vision, feedback and memory content](embodied-memory-content.md)')
    backlog=ROOT/f'docs/{language}/plans/research-backlog.md'
    body=backlog.read_text(encoding='utf-8')
    summary=('**2026-10-07：E58已批准并登记。短时感官痕迹属于记忆；本期查其内容、完整视野与动作反馈，保留E50/E57证据。固定/可塑外设对照在本期范围，融合内核未实施。**'
             if zh else '**2026-10-07: E58 approved and registered. Short sensory traces qualify as memory; investigate content, whole-scene vision and movement feedback. Preserve E50/E57. Fixed/adaptable external-reader comparison is in scope; no merged Core implemented.**')
    if summary not in body:
        first,rest=body.split('\n',1);body=first+'\n\n'+summary+' [E58](embodied-memory-content.md)\n'+rest
        lines=body.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('| R35 /'):
                cells=line.split('|');cells[1]=' R35 / P1 E58 approved / 已批准 '
                cells[4]=' E58：完整视野、可见自身、反馈与控制、相同末段经历、固定/可塑外设；短时痕迹按记忆对待，内容仍需定位。旧待办保留于原阶段记载 / See E58; prior open questions retained below. '
                cells[5]=' [E57](choice-attribution.md) · [E58](embodied-memory-content.md) '
                lines[i]='|'.join(cells)
        backlog.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    append(f'docs/{language}/plans/research-backlog.md',f'## 2026-10-07 · E58 registration\n\n{text}\n\n[Plan](embodied-memory-content.md)')

append('docs/zh/history/classical/shiji-04.md','## 记忆之辨续记\n\n创者曰：师指之迹亦昔事所成，岂因暂留于感官，遂不得谓之记忆乎。议者从之。乃不争其名，转考其所记：记物与名，抑记所受之教，而器据此择答。又命目见全境与己体，分受感与发令而验之。旧据存，核法不改；此时尚属立试，非新功已成。\n\n[今译与史料](../sources/2026-10-07-memory-content.md)')
append('docs/zh/history/classical/tongjian-04.md','### 2026-10-07 · E58立试\n\n用户谓短时感官之迹亦记忆，乃改问其内容与用处，不以短暂废之。察指器已有身感而目未见己，四处别观亦非一目全视。命补其器，辨动作与感知之因，又同其末段所历而验旧忆，终较固器与可塑之器。皆另存，未改旧核。[史料](../sources/2026-10-07-memory-content.md)')
p=ROOT/'docs/history/catalog.json';catalog=json.loads(p.read_text(encoding='utf-8'))
for language in ('zh','en'):
    entry={'id':language+'-memory-content-20261007','work':'modern-'+language,'key':'memory-content-20261007','group':'sources',
           'title':'史料：短时痕迹与记忆内容' if language=='zh' else 'Source: short traces and memory content',
           'path':f'docs/{language}/history/sources/2026-10-07-memory-content.md','period':'2026-10-07','tags':['E58','memory','discussion']}
    entries=catalog['chapters'] if 'chapters' in catalog else catalog['entries']
    if not any(e['id']==entry['id'] for e in entries):entries.append(entry)
p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
