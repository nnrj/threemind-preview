"""Publish existing E55 records through research services, never run trials."""
import json
from pathlib import Path
import shutil
import sys
import re
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import archive_once,artifact_once
from lab.tools.service_study import read_json,new_json

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/grounded-reviews-20261006'


def document_links(body,publication):
    def replace(match):
        label,url=match.group(1),match.group(2)
        if url in ('results.json','analysis.json','structure.json'):
            item=publication.state.get('artifact:'+Path(url).stem)
            if item and item.get('artifact_id'):
                url=f'/api/v2/projects/{publication.project}/artifacts/{item["artifact_id"]}'
        elif url.endswith('.md') and not url.startswith(('/','#')) and '://' not in url:
            path=(HERE/url).resolve()
            if path.is_relative_to(ROOT) and path.is_file():
                url='/docs?doc='+quote(path.relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',replace,body)


def main():
    s=ArchivedStudy(WORK);s.name='grounded-reviews/1';p=Publication(s)
    try:
        artifacts={}
        for key,file,mime in [('results',HERE/'results.json','application/json'),('analysis',HERE/'analysis.json','application/json'),
                              ('structure',HERE/'structure.json','application/json'),('replay',WORK/'replay.html','text/html')]:
            artifacts[key]=artifact_once(p,'artifact:'+key,file,'E55 '+file.name,mime)
        for lang in ('zh','en'):
            p.document('report:'+lang,'report','E55 辨认形色与按话指向 / Recognizing and pointing '+lang,
                       document_links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'),p))
        p.note('execution','E55 原始设计与执行补充',
               document_links((HERE/'design.zh.md').read_text(encoding='utf-8')+'\n\n'+(HERE/'execution-notes.md').read_text(encoding='utf-8'),p))
        p.document('record:replay','record','E55 实际课堂与动作回放 / Recorded classroom and actions',
            f"[下载交互回放 / Download replay](/api/v2/projects/{s.project}/artifacts/{artifacts['replay']['artifact_id']})\n\n"
            '下载HTML在浏览器打开，可选择实际试次、拖动时间、截图。左侧是记录的几何布局和指针轨迹，右侧是实际低分辨率RGB、回答与评分。'
            '回答显示的是完整观察窗口的读出；不是回放现场重新推理。不补画未记录动作，不把教师动作当自主动作。\n\n'
            'The diagram renders recorded geometry and pointer positions; pixels and outputs are recorded data. '
            'Displayed answers belong to the completed observation window, not new online inference.')
        # Freeze the small reusable tools as well as the study runner; no old data scan.
        for rel in ('lab/tools/activity_controller.py','lab/tools/shape_color_world.py','lab/tools/grounded_classroom.py','lab/tools/classroom_reviews.py',
                    'lab/tools/classroom_motor.py','tests/test_grounded_classroom.py','tests/test_classroom_motor.py',
                    'tests/test_activity_controller_validation.py'):
            dest=WORK/'delivered-tools'/rel
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
        for name in ('results.json','analysis.json','structure.json'):
            dest=WORK/'derived'/name
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(HERE/name,dest)
        # Only this new study is archived; no earlier experiment is copied in.
        archive=archive_once(p,'E55 grounded spaced classroom evidence.zip')
        p.document('record:evidence','record','E55 输入、状态与工具 / Inputs, states and tools',
            f"[完整证据包 / Evidence](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})\n\n"
            f"[汇总结果 / Results](/api/v2/projects/{s.project}/artifacts/{artifacts['results']['artifact_id']})")
        with s.db.tx() as tx:dbbytes=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        info={'project_id':s.project,'archive':archive,'artifacts':artifacts,
              'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},
              'local_bytes':sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file()),
              'database_growth_bytes':max(0,dbbytes-s.meta['database_bytes_before']),'usage':read_json(WORK/'usage.json')}
        p.document('record:delivery','record','E55 交付与验收 / Delivery and acceptance',
            document_links((HERE/'delivery.zh.md').read_text(encoding='utf-8')+'\n\n'+(HERE/'delivery.en.md').read_text(encoding='utf-8'),p)+
            '\n\n```json\n'+json.dumps({k:info[k] for k in ('local_bytes','database_growth_bytes','usage')},indent=2)+'\n```')
        info['documents']['record:delivery']=p.state['record:delivery']['id']
        if not (HERE/'delivery.json').exists():new_json(HERE/'delivery.json',info)
        print(json.dumps({'project':s.project,'evidence_GiB':(info['local_bytes']+info['database_growth_bytes'])/2**30}))
    finally:s.db.close()


if __name__=='__main__':main()
