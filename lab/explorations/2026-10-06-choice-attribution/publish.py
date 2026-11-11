"""Publish E57 through ThreeMind services; no simulation or old-data mutation."""
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
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/choice-attribution-20261006'


def links(body, *, project=None, artifacts=None):
    def sub(m):
        label,url=m.group(1),m.group(2)
        if project and artifacts and url in artifacts:
            url=f'/api/v2/projects/{project}/artifacts/{artifacts[url]["artifact_id"]}'
        elif url.endswith('.md') and not url.startswith(('/','#')) and '://' not in url:
            f=(HERE/url).resolve()
            if f.is_relative_to(ROOT) and f.is_file():url='/docs?doc='+quote(f.relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',sub,body)


def main():
    s=ArchivedStudy(WORK);s.name='choice-attribution/1';p=Publication(s)
    try:
        result=artifact_once(p,'results',HERE/'results.json','E57 全部归因结果','application/json')
        audit=artifact_once(p,'input-audit',HERE/'input-audit.json','E57 同输入归因边界核查','application/json')
        artifacts={'results.json':result,'input-audit.json':audit}
        p.note('execution-notes','E57 追加问题、决定与执行记录',
               links((HERE/'execution-notes.md').read_text(encoding='utf-8')))
        verified=[]
        for language in ('zh','en'):
            body=links((HERE/f'report.{language}.md').read_text(encoding='utf-8'),project=s.project,artifacts=artifacts)
            if '<!-- FINAL_' in body:raise RuntimeError('report still has unfinished sections')
            saved=p.document('report:'+language,'report','E57 指认答案来自哪里 / Choice attribution '+language,body)
            row=research_documents.get(s.db,s.project,saved['id'])
            if row['spec']['blocks'][0]['markdown']!=body:raise ValueError('published report differs from local source')
            verified.append({'language':language,'id':saved['id'],'revision':row['content_revision'],'body_matches':True})
        for rel in ('lab/tools/choice_attribution.py','lab/tools/choice_interventions.py','lab/tools/spatial_choice.py',
                    'lab/tools/activity_controller.py','lab/tools/classroom_eye.py','lab/tools/grounded_classroom.py',
                    'lab/tools/shape_color_world.py','lab/tools/connection_controls.py',
                    'tests/test_choice_attribution.py','tests/test_spatial_choice.py','tests/test_activity_controller_validation.py',
                    'lab/explorations/2026-10-06-vision-correction/experiment.py',
                    'lab/explorations/2026-10-06-grounded-reviews/experiment.py',
                    'lab/explorations/2026-10-06-vision-correction/confirmation-tasks.json'):
            dest=WORK/'delivered-tools'/rel
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
        # Only the historical files actually used by C/D; never scan the old
        # evidence tree or copy unrelated experiments.
        historical=ROOT/'.work/vision-correction-20261006'
        for rel in ('cases/r4-exposure-shared-fit/controller/model.safetensors',
                    'cases/r4-exposure-shared-fit/controller/manifest.json',
                    'cases/r4-exposure/checkpoint.json.gz',
                    'cases/r4-exposure-shared-confirmation-silence/features.npz',
                    'cases/r4-exposure-shared-confirmation-rescue/features.npz'):
            dest=WORK/'historical-inputs/vision-correction-20261006'/rel
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(historical/rel,dest)
        for name in ('results.json','input-audit.json'):
            dest=WORK/name
            if not dest.exists():shutil.copy2(HERE/name,dest)
        archive=archive_once(p,'E57 指认归因完整证据.zip',historical_scope=[
            'E56 selected request-window input/activity,60train+24test per Core condition',
            'C frozen E56 reader,world checkpoint and24tasks; D existing-edge silence/rescue feature arrays'])
        p.document('evidence','record','E57 全部输入、状态与读取器 / Complete evidence',
                   f'[完整证据 / Evidence](/api/v2/projects/{s.project}/artifacts/{archive["artifact_id"]})\n\n'
                   f'[全部结果 / Results](/api/v2/projects/{s.project}/artifacts/{result["artifact_id"]})\n\n'
                   f'[同输入核查 / Input check](/api/v2/projects/{s.project}/artifacts/{audit["artifact_id"]})\n\n'
                   '只读复核E56并新建E57，不覆盖既有实验。 / Old experiments retained unchanged.')
        with s.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery={'project_id':s.project,'archive':archive,'results':result,'input_audit':audit,
                  'report_verification':verified,
                  'reports':{k:v['id'] for k,v in p.state.items() if k.startswith('report:')},
                  'local_bytes':sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file()),
                  'database_growth_bytes':max(0,size-s.meta['database_bytes_before'])}
        if not (HERE/'delivery.json').exists():new_json(HERE/'delivery.json',delivery)
        print(json.dumps(delivery))
    finally:s.db.close()


if __name__=='__main__':main()
