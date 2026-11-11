"""Publish and read back this study's versioned Lab evidence."""
import argparse
import hashlib
import json
import re
from datetime import UTC, datetime

from common import GIB, HERE, WORK, encoded, read_json
from publication_base import Publisher
from threemind_lab import notebooks, research_documents
from threemind_lab.database import LOCAL_USER

def publish(p):
    audit=read_json(WORK/'analysis.json')
    assert audit['cases']==180 and not audit['failures']
    assert (WORK/'STOP').exists()
    archive=p.archive()
    images={}
    for name in ('intervention','retention','recall'):
        identity=p.identity('figure:'+name)
        notebooks.save_asset(p.db,p.project,LOCAL_USER,identity,name+'.png',(WORK/(name+'.png')).read_bytes())
        images[name]=f'/api/v2/projects/{p.project}/note-assets/{identity}'
    evidence=f"\n\n[原始证据 / Raw evidence](/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']})\n"
    for lang in ('zh','en'):
        body=(HERE/f'report.{lang}.md').read_text(encoding='utf-8')
        for name,url in images.items():
            body=body.replace(f'../../../docs/images/internal-activity-{name}-2026-09-29.png',url)
        body=re.sub(r'\[([^\]]+)\]\(([^):]+\.md)\)',r'\1',body)+evidence
        title='内部活动确实改变了行为：180 实例因果对照' if lang=='zh' else 'Internal activity changes behavior: 180 causal tests'
        p.document('report:'+lang,'report',title,body)
        p.note('results-note:'+lang,title,body)
    p.document('record:expression','record','同状态、同输入：内部通信的阻断与恢复',
               '四父本、32 表现分支。四个假干预逐值复现；临时通信阻断改变动作，恢复后差异减小。'
               '\n\n完整动作、节点、身体轨迹与前后干预状态摘要见附件 expression/ 和 expression-analysis.json。'
               f"\n\n![干预与恢复]({images['intervention']})"+evidence)
    p.document('record:experience','record','后天经历改变联想与动作：出生保持验证',
               '同一起点，等通道剂量的 AB/CD 与 AD/CB 经历。16 训练、96 提示、32 出生验证副本。'
               '\n\n出生清空短时活动后，四父本仍有经历差异；测试期关闭通信，本次未提示活动及运动差异均为零。'
               '\n\n80 个提示时序窗的原始结果、末端激活排序、完整 P/Q 和无提示对照全部在附件中。'
               f"\n\n![出生保持]({images['retention']})"+evidence)
    p.guard(force=True)
    print(json.dumps({'project':p.project,'reports':{k:p.state['report:'+k]['id'] for k in ('zh','en')},
                      'archive':archive},default=str),flush=True)

def verify(p,usage):
    audit=read_json(WORK/'analysis.json')
    for lang in ('zh','en'):
        saved=p.state['report:'+lang]
        doc=research_documents.get(p.db,p.project,saved['id'],revision=saved['revision'])
        assert doc['content_hash']==saved['content_hash']
        assert '180' in doc['spec']['blocks'][0]['markdown']
    assert len(research_documents.listing(p.db,p.project,kind='record')['rows'])==2
    assert len(research_documents.listing(p.db,p.project,kind='report')['rows'])==2
    sha=hashlib.sha256()
    size=0
    with p.db.tx(p.project) as db, db.cursor(name='internal_activity_archive_readback') as cursor:
        cursor.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',(p.state['archive']['artifact_id'],))
        for row in cursor:
            sha.update(row['body']);size+=len(row['body'])
    assert sha.hexdigest()==p.state['archive']['sha256'] and size==p.state['archive']['bytes']
    with p.db.tx() as db:
        database=db.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
    local=sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file())
    growth=max(0,database-p.meta['database_bytes_before'])
    assert local+growth<2*GIB
    result={'verified_at':datetime.now(UTC).isoformat(),'project_id':p.project,
            'reports':{lang:p.state['report:'+lang]['id'] for lang in ('zh','en')},
            'archive':p.state['archive'],'archive_database_readback_verified':True,
            'instances':audit['cases'],'compute_seconds':audit['compute_seconds'],
            'local_bytes':local,'database_growth_bytes':growth,'total_new_bytes':local+growth,
            'usage_start_percent':p.meta['usage_start_percent'],'usage_end_percent':usage,
            'simulation_stopped':(WORK/'STOP').exists()}
    (WORK/'publication-verification.json').write_bytes(encoded(result))
    for lang in ('zh','en'):
        body=f'''# {'实验交付记录' if lang=='zh' else 'Experiment delivery'}

2026-09-29. 180 {'实例完成，停止新增模拟。' if lang=='zh' else 'instances complete; further simulation stopped.'}

- Project: `2026-09-29 内部活动与行为的因果验证` / `{p.project}`.
- 中文报告: `{result['reports']['zh']}`; English report: `{result['reports']['en']}`.
- {'两类实验记录、双语设计与出生验证笔记、双语结果笔记和报告。' if lang=='zh' else 'Two records, bilingual designs and birth-extension notes, bilingual result notes and reports.'}
- Archive: `{p.state['archive']['artifact_id']}`; {size/2**20:.1f} MiB; {p.state['archive']['verified_members']} verified members.
- SHA-256: `{sha.hexdigest()}`. {'已流式读回整个数据库附件并核验。' if lang=='zh' else 'Entire database artifact streamed back and verified.'}
- {'新增本地 / 数据库净增 / 合计' if lang=='zh' else 'New local / database net growth / total'}: {local/2**20:.1f} MiB / {growth/2**20:.1f} MiB / **{(local+growth)/2**30:.3f} GiB**, budget 2 GiB.
- CPU {'实例累计墙钟' if lang=='zh' else 'aggregate case wall time'}: {audit['compute_seconds']/60:.2f} min. No GPU / cloud / paid AI.
- {'验证：3 项实验工具测试和 3 项文档资源测试通过；文档测试首次被沙箱临时目录权限阻止，获准重跑后通过。' if lang=='zh' else 'Checks: 3 experiment-tool and 3 document-resource tests passed. Document tests initially hit sandbox temporary-directory permissions and passed on an approved retry.'}
- {'16 份教材逐帧核对：均为 80 帧、每通道 40 次、间隔 1 秒、强度 0.8。' if lang=='zh' else 'All 16 training streams verified: 80 frames, 40 occurrences/channel, 1 s spacing, intensity 0.8.'}
- {'账户共享额度，非精确任务用量' if lang=='zh' else 'Shared account usage, not exact task usage'}: {p.meta['usage_start_percent']}% → {usage}%.
- [中文](report.zh.md) · [English](report.en.md).

{'本交付记录在归档后生成，未放入已封存附件。旧证据保持；新工作目录含核验详情。' if lang=='zh' else 'This delivery record was written after sealing and is not inside the archive. Old evidence remains; verification details reside in the new work directory.'}
'''
        (HERE/f'delivery.{lang}.md').write_text(body,encoding='utf-8')
        note_body=re.sub(r'\[([^\]]+)\]\(([^):]+\.md)\)',r'\1',body)
        p.note('delivery:'+lang,'交付核验 / Delivery '+lang,note_body)
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['publish','verify'])
    parser.add_argument('--usage-used',type=int)
    args=parser.parse_args()
    p=Publisher()
    try:
        if args.command=='publish':publish(p)
        else:
            if args.usage_used is None:raise ValueError('read current account usage first')
            verify(p,args.usage_used)
    finally:p.db.close()
