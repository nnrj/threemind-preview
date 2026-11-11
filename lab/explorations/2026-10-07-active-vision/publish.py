"""Publish E59 reports and immutable evidence through existing Lab services."""
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
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/active-vision-20261007'


def links(body,project,artifacts):
    def sub(m):
        label,url=m.group(1),m.group(2)
        if url=='../../../.work/active-vision-20261007/active-vision.html':url='active-vision.html'
        if url in artifacts:url=f'/api/v2/projects/{project}/artifacts/{artifacts[url]["artifact_id"]}'
        elif url.endswith('.md') and not url.startswith(('/','#')) and '://' not in url:
            path=(HERE/url).resolve()
            if path.is_relative_to(ROOT) and path.is_file():url='/docs?doc='+quote(path.relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',sub,body)


def copy_once(source,target):
    if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)


def main():
    study=ArchivedStudy(WORK);study.name='active-vision/1';pub=Publication(study)
    try:
        artifacts={'results.json':artifact_once(pub,'results',HERE/'results.json','E59 全部实测结果','application/json')}
        for filename,mime in (('active-vision.html','text/html'),):
            artifacts[filename]=artifact_once(pub,filename,WORK/filename,'E59 完整问题与眼手活动回放.html',mime)
        for key in ('execution-notes','tools'):
            pub.note('final:'+key,'E59 '+key,links((HERE/f'{key}.md').read_text(encoding='utf-8'),study.project,artifacts))
        images=[pub.image('E59-cost',HERE/'summary.png'),pub.image('E59-central-optics',WORK/'central-optics.png')]
        verified=[]
        for language in ('zh','en'):
            body=links((HERE/f'report.{language}.md').read_text(encoding='utf-8'),study.project,artifacts)
            if '<!-- FINAL_' in body:raise ValueError('unfinished report')
            body+='\n\n'+'\n\n'.join(images)
            saved=pub.document('report:'+language,'report','E59 视觉焦点、扫视与眼手配合 / Active vision '+language,body)
            row=research_documents.get(study.db,study.project,saved['id'])
            if row['spec']['blocks'][0]['markdown']!=body:raise ValueError('report publication mismatch')
            verified.append({'language':language,'id':saved['id'],'revision':row['content_revision'],'body_matches':True})
        for name in ('active_eye.py','active_vision_replay.py','active_vision_replay.html','foveal_choice.py','foveal_sequence.py',
                     'sensorimotor_session.py','gaze_activity.py','whole_scene_classroom.py','classroom_eye.py','grounded_classroom.py',
                     'shape_color_world.py','choice_attribution.py','activity_controller.py','service_study.py','study_publication.py','evidence_archive.py'):
            copy_once(ROOT/'lab/tools'/name,WORK/'delivered-tools/lab/tools'/name)
        copy_once(ROOT/'tests/test_active_eye.py',WORK/'delivered-tools/tests/test_active_eye.py')
        copy_once(HERE/'results.json',WORK/'results.json')
        archive=archive_once(pub,'E59 输入、活动、眼手轨迹及模型完整证据.zip')
        pub.document('evidence','record','E59 完整证据与回放',
            f'[全部证据](/api/v2/projects/{study.project}/artifacts/{archive["artifact_id"]})\n\n'
            f'[全部结果](/api/v2/projects/{study.project}/artifacts/{artifacts["results.json"]["artifact_id"]})\n\n'
            f'[完整回放](/api/v2/projects/{study.project}/artifacts/{artifacts["active-vision.html"]["artifact_id"]})\n\n'
            '保留全部问题与失败；Core动力学、默认和旧证据未改。 / All questions and failures retained; Core/defaults/old evidence unchanged.')
        with study.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery={'project_id':study.project,'archive':archive,'artifacts':artifacts,'report_verification':verified,
            'reports':{k:v['id'] for k,v in pub.state.items() if k.startswith('report:')},
            'local_bytes':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
            'database_growth_bytes':max(0,size-study.meta['database_bytes_before'])}
        if not (HERE/'delivery.json').exists():new_json(HERE/'delivery.json',delivery)
        print(json.dumps(delivery))
    finally:study.db.close()


if __name__=='__main__':main()
