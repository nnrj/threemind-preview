"""Publish E58 measured evidence and reports through existing Lab services."""
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import archive_once,artifact_once
from lab.tools.service_study import new_json
from threemind_lab import research_documents
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/embodied-memory-20261007'
OLD=ROOT/'.work/choice-attribution-20261006'


def links(body, project, artifacts):
    def sub(m):
        label,url=m.group(1),m.group(2)
        if url in artifacts:url=f'/api/v2/projects/{project}/artifacts/{artifacts[url]["artifact_id"]}'
        elif url.endswith('.md') and not url.startswith(('/','#')) and '://' not in url:
            f=(HERE/url).resolve()
            if f.is_relative_to(ROOT) and f.is_file():url='/docs?doc='+quote(f.relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',sub,body)


def copy_once(source,destination):
    if not destination.exists():
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)


def main():
    s=ArchivedStudy(WORK);s.name='embodied-memory/1';p=Publication(s)
    try:
        results=json.loads((HERE/'results.json').read_bytes())
        artifact=artifact_once(p,'results',HERE/'results.json','E58 全部结果 / Measured results','application/json')
        artifacts={'results.json':artifact}
        p.note('execution-notes','E58 执行决定与中止记录',links((HERE/'execution-notes.md').read_text(encoding='utf-8'),s.project,artifacts))
        images=[]
        for name in ('retina','summary'):
            source=WORK/'cases/A-optics/retina.png' if name=='retina' else HERE/'summary.png'
            if source.exists():images.append(p.image('E58-'+name,source))
        verified=[]
        for language in ('zh','en'):
            body=links((HERE/f'report.{language}.md').read_text(encoding='utf-8'),s.project,artifacts)
            if '<!-- FINAL_' in body:raise RuntimeError('unfinished report')
            body+='\n\n'+'\n\n'.join(images)
            saved=p.document('report:'+language,'report','E58 完整视野、反馈与记忆 / Vision, feedback and memory '+language,body)
            row=research_documents.get(s.db,s.project,saved['id'])
            if row['spec']['blocks'][0]['markdown']!=body:raise ValueError('report publication mismatch')
            verified.append({'language':language,'id':saved['id'],'revision':row['content_revision'],'body_matches':True})
        for rel in ('lab/tools/whole_scene_classroom.py','lab/tools/retinal_choice.py','lab/tools/spatial_choice.py',
                    'lab/tools/activity_controller.py','lab/tools/classroom_eye.py','lab/tools/grounded_classroom.py',
                    'lab/tools/shape_color_world.py','lab/tools/choice_attribution.py','lab/tools/choice_interventions.py',
                    'lab/tools/evidence_archive.py','lab/tools/study_publication.py',
                    'tests/test_whole_scene_classroom.py','tests/test_retinal_choice.py',
                    'lab/explorations/2026-10-06-choice-attribution/experiment.py'):
            copy_once(ROOT/rel,WORK/'delivered-tools'/rel)
        # Only fixed historical inputs actually read by E58, not the old tree.
        for seed in (223,279):
            for plasticity in (0,1):
                for history in (0,1):
                    prefix=f'C-s{seed}-p{plasticity}-h{history}'
                    if any(k.startswith(prefix) for k in results['cases']):
                        rel=f'cases/B-s{seed}-p{plasticity}-h{history}-teach/checkpoint.json.gz'
                        copy_once(OLD/rel,WORK/'historical-inputs'/rel)
            for kind in ('learned','unlearned','incoming'):
                for name in ('manifest.json','model.safetensors'):
                    rel=f'cases/B-s{seed}-{kind}-fit/controller/{name}'
                    if (OLD/rel).exists() and (seed==223 or any(f's{seed}-' in k for k in results['cases'])):
                        copy_once(OLD/rel,WORK/'historical-inputs'/rel)
        if 'D-activity' in results['cases']:
            for history in (0,1):
                for split in ('train','test'):
                    rel=f'cases/B-s223-p1-h{history}-teach-{split}-normal/features.npz'
                    copy_once(OLD/rel,WORK/'historical-inputs'/rel)
        copy_once(HERE/'results.json',WORK/'results.json')
        archive=archive_once(p,'E58 完整证据 / Evidence.zip',historical_scope=[
            'Only E57 snapshots/readers and old rehearsal features consumed by E58; old experiments unchanged'])
        p.document('evidence','record','E58 输入、状态、工具与对照记录',
            f'[完整证据 / Evidence](/api/v2/projects/{s.project}/artifacts/{archive["artifact_id"]})\n\n'
            f'[全部结果 / Results](/api/v2/projects/{s.project}/artifacts/{artifact["artifact_id"]})\n\n'
            '原始数据、失败尝试与读取器均保留；未修改内核动力学。 / Core dynamics and prior evidence unchanged.')
        with s.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery={'project_id':s.project,'archive':archive,'results':artifact,'report_verification':verified,
                  'reports':{k:v['id'] for k,v in p.state.items() if k.startswith('report:')},
                  'local_bytes':sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file()),
                  'database_growth_bytes':max(0,size-s.meta['database_bytes_before'])}
        if not (HERE/'delivery.json').exists():new_json(HERE/'delivery.json',delivery)
        print(json.dumps(delivery))
    finally:s.db.close()


if __name__=='__main__':main()
