"""Publish recorded E56 evidence through ThreeMind services. No simulation."""
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import archive_once,artifact_once
from lab.tools.service_study import read_json,new_json
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/vision-correction-20261006'


def links(body,p):
    def sub(m):
        label,url=m.group(1),m.group(2)
        if url in ('results.json','optical-audit.json','circle-audit.json','circle-core-disabled.json'):
            v=p.state.get('artifact:'+Path(url).stem,{})
            if v.get('artifact_id'):url=f'/api/v2/projects/{p.project}/artifacts/{v["artifact_id"]}'
        elif url == 'circle_core_disabled.py':
            v=p.state.get('artifact:circle-source',{})
            if v.get('artifact_id'):url=f'/api/v2/projects/{p.project}/artifacts/{v["artifact_id"]}'
        elif url.endswith('.md') and not url.startswith(('/','#')) and '://' not in url:
            f=(HERE/url).resolve()
            if f.is_relative_to(ROOT) and f.is_file():url='/docs?doc='+quote(f.relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',sub,body)


def main():
    s=ArchivedStudy(WORK);s.name='vision-correction/1';p=Publication(s)
    try:
        artifacts={}
        for key,file,mime in [('results',HERE/'results.json','application/json'),
              ('optical-audit',HERE/'optical-audit.json','application/json'),
              ('circle-audit',HERE/'circle-audit.json','application/json'),
              ('circle-core-disabled',HERE/'circle-core-disabled.json','application/json'),
              ('circle-source',HERE/'circle_core_disabled.py','text/plain'),
              ('optical-samples',WORK/'optical-samples.png','image/png'),('replay',WORK/'replay.html','text/html')]:
            artifacts[key]=artifact_once(p,'artifact:'+key,file,'E56 '+file.name,mime)
        if (WORK/'pointing.mp4').exists():
            artifacts['video']=artifact_once(p,'artifact:video',WORK/'pointing.mp4','E56 全部指向与归因对照','video/mp4')
        for lang in ('zh','en'):
            p.document('report:'+lang,'report','E56 看清形状与纠错指认 / Vision and correction '+lang,
                     links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'),p))
        p.note('execution','E56 纠错教学与执行记录',links((HERE/'execution-notes.md').read_text(encoding='utf-8'),p))
        p.document('record:circle-control','record','E55 画圈：停用Core后的物理对照 / Circles with Core absent',
            f'[补测结果 / Physical rerun](/api/v2/projects/{s.project}/artifacts/{artifacts["circle-core-disabled"]["artifact_id"]})\n\n'
            '不创建Core，保留同样初始身体、风和场景，从出生重算516模拟秒。10320个位置与原记录一致，两段用户指出的画圈均保留。'
            '原轨迹只供比较，未写回控制。此前关闭学习不是停用Core，本次补齐这一对照。结论仅限这段未接意识运动输出的课程。\n\n'
            'No Core is created. The same physical world is independently advanced for516simulated seconds, reproducing all10320positions, including both reported circles. '
            'Recorded motion is never a control input. This supplements the earlier learning-off comparison and applies only to the course with no Core motor output connected.')
        p.document('record:replay','record','E56 全部指向试次 / All completed pointing trials',
            f'[交互回放 / Recorded replay](/api/v2/projects/{s.project}/artifacts/{artifacts["replay"]["artifact_id"]})\n\n'
            '包括正确与错误、正式与练习。图标为场景示意，RGB格是实际感官采样；选择来自原始活动读头，伺服只执行其选择。'
            '不重新运行Core，不把目标答案交给执行器。 / All outcomes retained; the servo executes the decoded choice, not the scoring target.')
        if 'video' in artifacts:
            p.document('record:video','record','E56 指向与归因对照录像 / Pointing and attribution video',
                f'[全部已完成指向试次 / All completed pointing trials](/api/v2/projects/{s.project}/artifacts/{artifacts["video"]["artifact_id"]})\n\n'
                '保留全部对错及对照；不是精选成功片段。教学原始过程见完整证据。 / All outcomes and controls, not a success montage; teaching processes are in the evidence archive.')
        for rel in ('lab/tools/classroom_eye.py','lab/tools/grounded_classroom.py','lab/tools/shape_color_world.py',
                    'lab/tools/activity_controller.py','lab/tools/spatial_choice.py','lab/tools/classroom_trial_export.js',
                    'tools/export_classroom_replay.mjs',
                    'lab/explorations/2026-10-06-grounded-reviews/experiment.py'):
            dest=WORK/'delivered-tools'/rel
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
        for source in HERE.glob('*.json'):
            dest=WORK/'delivered-analysis'/source.name
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        archive=archive_once(p,'E56 vision correction evidence.zip')
        p.document('record:evidence','record','E56 完整输入、状态与外设 / Complete evidence',
            f'[下载证据 / Evidence](/api/v2/projects/{s.project}/artifacts/{archive["artifact_id"]})')
        with s.db.tx() as tx:dbbytes=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        info={'project_id':s.project,'archive':archive,'artifacts':artifacts,
              'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},
              'local_bytes':sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file()),
              'database_growth_bytes':max(0,dbbytes-s.meta['database_bytes_before'])}
        if not (HERE/'delivery.json').exists():new_json(HERE/'delivery.json',info)
        print(json.dumps({'project':s.project,'evidence_GiB':(info['local_bytes']+info['database_growth_bytes'])/2**30}))
    finally:s.db.close()

if __name__=='__main__':main()
