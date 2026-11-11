"""Versioned Lab publication and complete archive readback; no simulation here."""
import argparse
import hashlib
import json
import re
from datetime import UTC,datetime
from common import GIB,HERE,WORK,encoded,read_json
from publication_base import Publisher
from threemind_lab import notebooks,research_documents
from threemind_lab.database import LOCAL_USER

FIGURES=('pathways','retention','adaptation','erasure')

def publish(p):
    audit=read_json(WORK/'analysis.json')
    assert audit['cases']==802 and not audit['failures'] and (WORK/'STOP').exists()
    archive=p.archive();images={}
    for name in FIGURES:
        identity=p.identity('figure:'+name)
        notebooks.save_asset(p.db,p.project,LOCAL_USER,identity,name+'.png',(WORK/(name+'.png')).read_bytes())
        images[name]=f'/api/v2/projects/{p.project}/note-assets/{identity}'
    evidence=f"\n\n[完整原始证据 / Complete evidence](/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']})\n"
    for lang in ('zh','en'):
        body=(HERE/f'report.{lang}.md').read_text(encoding='utf-8')
        for name,url in images.items():
            body=body.replace(f'../../../docs/images/experience-autonomy-{name}-2026-09-29.png',url)
        body=re.sub(r'\[([^\]]+)\]\(([^):]+\.md)\)',r'\1',body)+evidence
        title='经历、内部通路与自主活动：802 实例的明确判定' if lang=='zh' else 'Experience and autonomy: explicit decision from 802 instances'
        p.document('report:'+lang,'report',title,body)
        p.note('results-note:'+lang,title,body)
    records=(('pathways','内部机制：选择性阻断与恢复','112 个副本，完整状态、实际边清单与匹配误差、假干预和恢复轨迹。'),
             ('retention','记忆保持：单次强刺激与逐渐稀疏的重复','320 个副本（含追加 80 个）。最后一次输入后 1、30、300 秒；同龄无训练对照；出生及路径阻断验证。'),
             ('adaptation','连续互动与同一个体的环境改变','64 个前后刺激副本、176 个闭环环境及统一测试副本。控制运动出口非线性造成的表面相互作用。'),
             ('erasure','新颖性、泛化与重复擦除','130 个副本。八个纹理通道、四种条件、四轮变化及统一提示。'))
    for name,title,description in records:
        p.document('record:'+name,'record',title,description+f'\n\n![{title}]({images[name]})'+evidence)
    p.guard(force=True)
    print(json.dumps({'project':p.project,'reports':{k:p.state['report:'+k]['id'] for k in ('zh','en')},'archive':archive},default=str),flush=True)

def verify(p,usage):
    audit=read_json(WORK/'analysis.json');decision=read_json(WORK/'criteria-decision.json')
    for lang in ('zh','en'):
        saved=p.state['report:'+lang]
        actual=research_documents.get(p.db,p.project,saved['id'],revision=saved['revision'])
        assert actual['content_hash']==saved['content_hash']
        assert '802' in actual['spec']['blocks'][0]['markdown']
    assert len(research_documents.listing(p.db,p.project,kind='record')['rows'])==4
    assert len(research_documents.listing(p.db,p.project,kind='report')['rows'])==2
    sha=hashlib.sha256();size=0
    with p.db.tx(p.project) as db,db.cursor(name='experience_autonomy_readback') as cursor:
        cursor.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',(p.state['archive']['artifact_id'],))
        for row in cursor:sha.update(row['body']);size+=len(row['body'])
    assert sha.hexdigest()==p.state['archive']['sha256'] and size==p.state['archive']['bytes']
    with p.db.tx() as db:total=db.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
    local=sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file());growth=max(0,total-p.meta['database_bytes_before'])
    assert local+growth<4*GIB
    out={'verified_at':datetime.now(UTC).isoformat(),'project_id':p.project,
         'reports':{lang:p.state['report:'+lang]['id'] for lang in ('zh','en')},'archive':p.state['archive'],
         'archive_database_readback_verified':True,'instances':audit['cases'],'compute_seconds':audit['compute_seconds'],
         'total_new_bytes':local+growth,'local_bytes':local,'database_growth_bytes':growth,
         'usage_start_percent':p.meta['usage_start_percent'],'usage_end_percent':usage,'simulation_stopped':(WORK/'STOP').exists(),
         'criteria':decision['criteria'],'meets_all':decision['meets_all']}
    (WORK/'publication-verification.json').write_bytes(encoded(out))
    for lang in ('zh','en'):
        body=f'''# {'交付验证' if lang=='zh' else 'Delivery verification'}

2026-09-29. 802 instances. Further simulation stopped.

- Project: `2026-09-29 经历保持、内部通路与自主活动判据` / `{p.project}`.
- 中文: `{out['reports']['zh']}`. English: `{out['reports']['en']}`.
- Four experiment records; bilingual reports and design/result notes; analysis registration.
- Archive `{p.state['archive']['artifact_id']}`: {size/2**20:.1f} MiB, {p.state['archive']['verified_members']} checked members.
- SHA-256: `{sha.hexdigest()}`. Full DB readback verified.
- All 802 final states compared against DB; actual input deliveries exported and checked.
- New local+DB storage: {(local+growth)/GIB:.3f} GiB / 4 GiB.
- Aggregate simulation wall time: {audit['compute_seconds']/60:.2f} minutes / 90 minutes.
- Shared account usage: {p.meta['usage_start_percent']}% → {usage}%; another project was active, so this is not attributable solely to this study.
- Core, defaults, old data and old archive unchanged. Previous bilingual report advanced to revision 2 with appended discussion.
'''
        (HERE/f'delivery.{lang}.md').write_text(body,encoding='utf-8')
        p.note('delivery:'+lang,'交付验证 / Delivery verification '+lang,body)
    print(json.dumps(out,default=str),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('publish','verify'));parser.add_argument('--usage',type=int,default=0)
    args=parser.parse_args();p=Publisher()
    try:publish(p) if args.command=='publish' else verify(p,args.usage)
    finally:p.db.close()
