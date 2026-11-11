"""Publish E62 reports and complete evidence without another simulation."""
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import quote, urlsplit
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from lab.tools.study_publication import ArchivedStudy, Publication
from lab.tools.evidence_archive import artifact_once
from lab.tools.streaming_evidence import archive_stream_once
from lab.tools.service_study import new_json
from threemind_lab import research_documents

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/continuous-development-20261007'


def links(body):
    def replace(match):
        label, url = match.groups()
        if not url.startswith(('/', '#')) and '://' not in url:
            target, _, fragment = url.partition('#')
            path = (HERE/target).resolve()
            if path.is_relative_to(ROOT) and path.is_file():
                if path.suffix == '.md':
                    url = '/docs?doc='+quote(path.relative_to(ROOT).as_posix(), safe='')+('#'+fragment if fragment else '')
                else:
                    # The document viewer renders Markdown, not source files.
                    # Preserve a source reference without an invalid UI URL.
                    return f'{label} (`{path.relative_to(ROOT).as_posix()}`)'
        return f'[{label}]({url})'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace, body)


def main():
    from threemind_lab.config import Settings
    url = urlsplit(Settings.from_env().database_url)
    if url.hostname not in ('127.0.0.1', 'localhost') or url.port != 5433 or url.path != '/threemind':
        raise ValueError('only authorized local research database')
    study = ArchivedStudy(WORK); study.name = 'continuous-development/1'; pub = Publication(study)
    try:
        artifacts = {}
        for name, path, mime in [('results.json', HERE/'results.json', 'application/json'),
                                 ('continuous-development.html', WORK/'continuous-development.html', 'text/html')]:
            artifacts[name] = artifact_once(pub, name, path, 'E62 '+name, mime)
        for name in ('recovered-workflow.zh', 'recovered-workflow.en', 'timing-correction.zh',
                     'timing-correction.en', 'control-boundary.zh', 'control-boundary.en',
                     'resource-interruption', 'save-recovery', 'visible-cue-control', 'corrective-policy',
                     'verification', 'README'):
            pub.note('final:'+name, 'E62 '+name, links((HERE/(name+'.md')).read_text(encoding='utf-8')))
        reports = []
        for lang in ('zh', 'en'):
            body = links((HERE/f'report.{lang}.md').read_text(encoding='utf-8'))
            saved = pub.document('report:'+lang, 'report', 'E62 完整系统与基础教学 / Whole-system teaching '+lang, body)
            actual = research_documents.get(study.db, study.project, saved['id'])
            if actual['spec']['blocks'][0]['markdown'] != body:
                raise ValueError('stored report differs')
            reports.append({'id':saved['id'], 'language':lang, 'body_matches':True})
        destination = WORK/'delivered-tools'; destination.mkdir(exist_ok=True)
        for name in ('developmental_motor.py','developmental_session.py','developmental_world.py','developmental_inspect.py',
                     'active_vision_replay.py','active_vision_replay.html','streaming_evidence.py'):
            target = destination/name
            if not target.exists(): shutil.copy2(ROOT/'lab/tools'/name, target)
        archive = archive_stream_once(pub, 'E62 全部输入、活动、完整状态、失败和课程.zip',
                                    omit_derived_names=('continuous-development.html',))
        pub.document('evidence', 'record', 'E62 证据与教学回放',
            f'[全部证据](/api/v2/projects/{study.project}/artifacts/{archive["artifact_id"]})\n\n'
            f'[完整正式教学与测试回放](/api/v2/projects/{study.project}/artifacts/{artifacts["continuous-development.html"]["artifact_id"]})\n\n'
            '包括成功与失败，示范辅助与自身输出分别标注。原失败过程与旧实验不覆盖。')
        with study.db.tx() as tx:
            db_bytes = tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery = {'project_id':study.project,'artifacts':artifacts,'archive':archive,'reports':reports,
                    'local_bytes':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
                    'database_growth_bytes':max(0, db_bytes-study.meta['database_bytes_before'])}
        if not (HERE/'delivery.json').exists(): new_json(HERE/'delivery.json', delivery)
        print(json.dumps(delivery, ensure_ascii=False))
    finally: study.db.close()


if __name__ == '__main__': main()
