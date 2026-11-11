"""Publish already completed E65 evidence to the existing local Lab only."""
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.study_publication import ArchivedStudy, Publication
from lab.tools.evidence_archive import artifact_once
from lab.tools.service_study import new_json
from threemind_lab import research_documents

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/centered-learning-20261008'


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
    if u.hostname not in ('127.0.0.1','localhost') or u.port!=5433 or u.path!='/threemind':
        raise ValueError('local study database only')
    s=ArchivedStudy(WORK); s.name='centered-learning/1'; pub=Publication(s)
    try:
        artifacts={}
        for name,path,mime in [('results.json',HERE/'results.json','application/json'),
                              ('centered-learning.html',WORK/'centered-learning.html','text/html')]:
            artifacts[name]=artifact_once(pub,name,path,'E65 '+name,mime)
        reports=[]
        for lang in ('zh','en'):
            body=links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            saved=pub.document('report:'+lang,'report','E65 中央形色续学 / Central shape-color continuation '+lang,body)
            stored=research_documents.get(s.db,s.project,saved['id'])
            if stored['spec']['blocks'][0]['markdown']!=body: raise ValueError('stored report mismatch')
            reports.append(dict(language=lang,id=saved['id']))
        for name in ('README','verification','HANDOFF'):
            pub.note('note:'+name,'E65 '+name,links((HERE/(name+'.md')).read_text(encoding='utf-8')))
        dest=WORK/'delivered-tools'; dest.mkdir(exist_ok=True)
        for name in ('recognition_session.py','calibrated_activity.py','active_vision_replay.py','active_vision_replay.html'):
            if not (dest/name).exists(): shutil.copy2(ROOT/'lab/tools'/name,dest/name)
        # Also include small derived analyses, which the generic archive's source glob does not include.
        derived=WORK/'delivered-results'; derived.mkdir(exist_ok=True)
        for path in HERE.glob('*.json'):
            if path.name=='delivery.json': continue
            if not (derived/path.name).exists(): shutil.copy2(path,derived/path.name)
        # E64's reference state and 60 calibration records ARE historical data.
        # This archive API records that fact and verifies every member hash.
        archive=pub.archive('E65 全部教学、问答、完整系统及学习状态.zip',historical_data_included=True)
        pub.document('evidence','record','E65 全部过程与回放',
            f'[完整证据](/api/v2/projects/{s.project}/artifacts/{archive["artifact_id"]})\n\n'
            f'[教学和问答全程回放](/api/v2/projects/{s.project}/artifacts/{artifacts["centered-learning.html"]["artifact_id"]})')
        with s.db.tx() as tx: size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery=dict(project_id=s.project,reports=reports,artifacts=artifacts,archive=archive,
            local_bytes=sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
            database_growth_bytes=max(0,size-s.meta['database_bytes_before']),
            database_growth_scope='shared database; positive growth includes concurrent projects',
            executed_scope='one registered continuation; original E64 untouched; no E63 or edge interventions')
        if not (HERE/'delivery.json').exists(): new_json(HERE/'delivery.json',delivery)
        print(json.dumps(delivery,ensure_ascii=False))
    finally: s.db.close()


if __name__=='__main__': main()
