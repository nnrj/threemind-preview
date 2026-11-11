"""Publish existing E54 records through research services, never run trials."""
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

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/shape-color-20261006'


def document_links(body):
    def replace(match):
        label,url=match.group(1),match.group(2)
        if url.endswith('.md') and not url.startswith(('/','#')) and '://' not in url:
            path=(HERE/url).resolve()
            if path.is_relative_to(ROOT) and path.is_file():
                url='/docs?doc='+quote(path.relative_to(ROOT).as_posix(),safe='')
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',replace,body)


def main():
    s=ArchivedStudy(WORK);s.name='shape-color-pointing/1';p=Publication(s)
    try:
        for lang in ('zh','en'):
            p.document('report:'+lang,'report','E54 形状、颜色、指向 / Shape, colour, pointing '+lang,
                       document_links((HERE/f'report.{lang}.md').read_text(encoding='utf-8')))
        p.note('execution','E54 原始设计与执行补充',
               document_links((HERE/'design.zh.md').read_text(encoding='utf-8')+'\n\n'+(HERE/'execution-notes.md').read_text(encoding='utf-8')))
        artifacts={}
        for key,file,mime in [('results',HERE/'results.json','application/json'),('replay',WORK/'replay.html','text/html')]:
            artifacts[key]=artifact_once(p,'artifact:'+key,file,'E54 '+file.name,mime)
        p.document('record:replay','record','E54 实际课堂与动作回放 / Recorded classroom and actions',
            f"[下载交互回放 / Download replay](/api/v2/projects/{s.project}/artifacts/{artifacts['replay']['artifact_id']})\n\n"
            '下载HTML在浏览器打开，可选择实际试次、拖动时间、截图。左侧是记录的几何布局和指针轨迹，右侧是实际低分辨率RGB、回答与评分。'
            '回答显示的是完整观察窗口的读出；不是回放现场重新推理。不补画未记录动作，不把教师动作当自主动作。\n\n'
            'The diagram renders recorded geometry and pointer positions; pixels and outputs are recorded data. '
            'Displayed answers belong to the completed observation window, not new online inference.')
        # Freeze the small reusable tools as well as the study runner; no old data scan.
        for rel in ('lab/tools/activity_controller.py','lab/tools/shape_color_world.py','lab/tools/imitation_world.py',
                    'tests/test_shape_color_world.py'):
            dest=WORK/'delivered-tools'/rel
            if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dest)
        # Only this new study is archived; no earlier experiment is copied in.
        archive=archive_once(p,'E54 shape colour pointing evidence.zip')
        p.document('record:evidence','record','E54 输入、状态与工具 / Inputs, states and tools',
            f"[完整证据包 / Evidence](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})\n\n"
            f"[汇总结果 / Results](/api/v2/projects/{s.project}/artifacts/{artifacts['results']['artifact_id']})")
        with s.db.tx() as tx:dbbytes=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        info={'project_id':s.project,'archive':archive,'artifacts':artifacts,
              'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},
              'local_bytes':sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file()),
              'database_growth_bytes':max(0,dbbytes-s.meta['database_bytes_before']),'usage':read_json(WORK/'usage.json')}
        if not (HERE/'delivery.json').exists():new_json(HERE/'delivery.json',info)
        print(json.dumps({'project':s.project,'evidence_GiB':(info['local_bytes']+info['database_growth_bytes'])/2**30}))
    finally:s.db.close()


if __name__=='__main__':main()
