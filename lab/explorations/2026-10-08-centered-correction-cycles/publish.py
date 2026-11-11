"""Publish completed E66 records to the existing local Lab; no simulations."""
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote,urlsplit
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import artifact_once
from lab.tools.service_study import read_json,new_json
from threemind_lab import research_documents
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/centered-correction-cycles-20261008'

def links(body):
    def replace(m):
        label,url=m.groups()
        if not url.startswith(('/','#')) and '://' not in url:
            path=(HERE/url.split('#')[0]).resolve()
            if path.is_relative_to(ROOT) and path.is_file():
                if path.suffix=='.md': url='/docs?doc='+quote(path.relative_to(ROOT).as_posix(),safe='')
                else: return f'{label} (`{path.relative_to(ROOT).as_posix()}`)'
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',replace,body)


def main():
    from threemind_lab.config import Settings
    u=urlsplit(Settings.from_env().database_url)
    if u.hostname not in ('127.0.0.1','localhost') or u.port!=5433 or u.path!='/threemind':raise ValueError('existing local database only')
    read_json(WORK/'completion.json')
    s=ArchivedStudy(WORK);s.name='centered-correction-cycles/1';pub=Publication(s)
    try:
        artifacts={};manifest=read_json(HERE/'replay-manifest.json')
        artifacts['results.json']=artifact_once(pub,'results.json',HERE/'results.json','E66 measured results','application/json')
        for chapter in manifest['chapters']:
            name=chapter['file'];artifacts[name]=artifact_once(pub,name,WORK/'replays'/name,'E66 '+chapter['label'],'text/html')
        body=(WORK/'replays/index.html').read_text(encoding='utf-8')
        for chapter in manifest['chapters']:
            name=chapter['file'];url=f'/api/v2/projects/{s.project}/artifacts/{artifacts[name]["artifact_id"]}'
            body=body.replace('href="'+name+'"','href="'+url+'"')
        cloud=WORK/'replays/lab-index.html'
        if not cloud.exists():cloud.write_text(body,encoding='utf-8')
        elif cloud.read_text(encoding='utf-8')!=body:raise AssertionError('stored replay links changed')
        artifacts['index.html']=artifact_once(pub,'index.html',cloud,'E66 全程回放目录','text/html')
        reports=[]
        for lang in ('zh','en'):
            body=links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            saved=pub.document('report:'+lang,'report','E66 空白起点多轮纠错 / Blank-start correction cycles '+lang,body)
            stored=research_documents.get(s.db,s.project,saved['id'])
            if stored['spec']['blocks'][0]['markdown']!=body:raise AssertionError('stored report differs')
            reports.append(dict(language=lang,id=saved['id']))
        for name in ('README','verification','HANDOFF','consolidation-audit.zh','consolidation-audit.en'):
            pub.note('note:'+name,'E66 '+name,links((HERE/(name+'.md')).read_text(encoding='utf-8')))
        derived=WORK/'delivered-results';derived.mkdir(exist_ok=True)
        for path in HERE.glob('*.json'):
            if path.name!='delivery.json' and not (derived/path.name).exists():shutil.copy2(path,derived/path.name)
        # A preserved E56 configuration is historical reference data; no learned E64/E65 subject was copied.
        archive=pub.archive('E66 全部纠错、问答、完整系统及学习状态.zip',historical_data_included=True)
        pub.document('evidence','record','E66 全部过程与完整证据',
            f'[全程分章回放](/api/v2/projects/{s.project}/artifacts/{artifacts["index.html"]["artifact_id"]})\n\n'
            f'[全部原始记录、完整系统及源码](/api/v2/projects/{s.project}/artifacts/{archive["artifact_id"]})')
        with s.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery=dict(project_id=s.project,reports=reports,artifacts=artifacts,archive=archive,
            local_bytes=sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
            database_growth_bytes=max(0,size-s.meta['database_bytes_before']),
            database_growth_scope='positive shared database growth; not exclusive attribution',
            executed_scope='one blank complete subject, bounded correction cycles, no E63 or connection intervention')
        if not (HERE/'delivery.json').exists():new_json(HERE/'delivery.json',delivery)
        print(json.dumps(delivery,ensure_ascii=False))
    finally:s.db.close()


if __name__=='__main__':main()
