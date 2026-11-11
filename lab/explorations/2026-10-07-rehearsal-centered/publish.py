"""Publish completed E63 documents and one-pass streamed evidence, no simulation."""
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote,urlsplit
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import artifact_once
from lab.tools.streaming_evidence import archive_stream_once
from lab.tools.service_study import new_json
from threemind_lab import research_documents
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/rehearsal-centered-20261007'


def links(body):
    def replace(m):
        label,url=m.groups()
        if not url.startswith(('/','#')) and '://' not in url:
            path=(HERE/url.split('#')[0]).resolve()
            if path.is_relative_to(ROOT) and path.is_file():
                if path.suffix=='.md':url='/docs?doc='+quote(path.relative_to(ROOT).as_posix(),safe='')
                else:return f'{label} (`{path.relative_to(ROOT).as_posix()}`)'
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',replace,body)


def main():
    from threemind_lab.config import Settings
    u=urlsplit(Settings.from_env().database_url)
    if u.hostname not in ('127.0.0.1','localhost') or u.port!=5433 or u.path!='/threemind':raise ValueError('local study database only')
    s=ArchivedStudy(WORK);s.name='rehearsal-centered/1';pub=Publication(s)
    try:
        artifacts={}
        for name,path,mime in [('results.json',HERE/'results.json','application/json'),
                               ('rehearsal-centered.html',WORK/'rehearsal-centered.html','text/html')]:
            artifacts[name]=artifact_once(pub,name,path,'E63 '+name,mime)
        reports=[]
        for lang in ('zh','en'):
            body=links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            saved=pub.document('report:'+lang,'report','E63 复习保持与中央认识 / Rehearsal and recognition '+lang,body)
            stored=research_documents.get(s.db,s.project,saved['id'])
            if stored['spec']['blocks'][0]['markdown']!=body:raise ValueError('stored report mismatch')
            reports.append(dict(language=lang,id=saved['id']))
        for name in ('README','console-correction','verification','execution-decisions','question-calibration-preregistration'):
            pub.note('note:'+name,'E63 '+name,links((HERE/(name+'.md')).read_text(encoding='utf-8')))
        tools=WORK/'delivered-tools';tools.mkdir(exist_ok=True)
        for name in ('developmental_motor.py','rehearsal_memory.py','centered_recognition.py','active_vision_replay.py','active_vision_replay.html'):
            if not (tools/name).exists():shutil.copy2(ROOT/'lab/tools'/name,tools/name)
        archive=archive_stream_once(pub,'E63 全部教学、测试、原始活动和完整系统.zip',omit_derived_names=('rehearsal-centered.html',))
        pub.document('evidence','record','E63 完整过程与回放',
            f'[完整证据](/api/v2/projects/{s.project}/artifacts/{archive["artifact_id"]})\n\n'
            f'[全部正确/错误教学与测试回放](/api/v2/projects/{s.project}/artifacts/{artifacts["rehearsal-centered.html"]["artifact_id"]})')
        with s.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery=dict(project_id=s.project,reports=reports,artifacts=artifacts,archive=archive,
                      local_bytes=sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
                      database_growth_bytes=max(0,size-s.meta['database_bytes_before']))
        if not (HERE/'delivery.json').exists():new_json(HERE/'delivery.json',delivery)
        print(json.dumps(delivery,ensure_ascii=False))
    finally:s.db.close()


if __name__=='__main__':main()
