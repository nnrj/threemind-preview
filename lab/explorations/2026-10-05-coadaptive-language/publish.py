"""Publish only this bounded study, using the existing research-document services."""
import re
import shutil
import psutil
from urllib.parse import quote

from experiment import ROOT, WORK, HERE, read_json, new_json
from lab.tools.study_publication import ArchivedStudy, Publication
from lab.tools.evidence_archive import artifact_once, archive_once
from threemind_lab import research_documents


def main():
    s = ArchivedStudy(WORK)
    s.name = s.settings.name
    p = Publication(s)
    try:
        # Small derived analyses accompany the raw evidence; old source data stay intact.
        analysis = WORK/'final-analysis'
        analysis.mkdir(exist_ok=True)
        for name in ('results.json', 'activity-results.json', 'sampling-diagnostic.json', 'conclusions.json', 'verification.json'):
            shutil.copy2(HERE/name, analysis/name)
        files = {'results': (HERE/'results.json', 'application/json'),
                 'activity': (HERE/'activity-results.json', 'application/json'),
                 'sampling': (HERE/'sampling-diagnostic.json', 'application/json'),
                 'outputs': (WORK/'outputs.html', 'text/html'),
                 'figure': (HERE/'outcomes.png', 'image/png')}
        artifacts = {key: artifact_once(p, key, path, 'E52 '+key, mime)
                     for key, (path, mime) in files.items()}
        for lang in ('zh', 'en'):
            def render(file):
                def link(match):
                    label, url = match.group(1), match.group(2)
                    for key, (path, _) in files.items():
                        if (file.parent/url).resolve() == path.resolve():
                            return f"[{label}](/api/v2/projects/{s.project}/artifacts/{artifacts[key]['artifact_id']})"
                    if url.endswith('.md') and not url.startswith(('http', '/', '#')):
                        url = '/docs?doc='+quote((file.parent/url).resolve().relative_to(ROOT).as_posix(), safe='')
                    return f'[{label}]({url})'
                return re.sub(r'\[([^\]]*)\]\(([^)]+)\)', link, file.read_text(encoding='utf-8'))
            p.document('report:'+lang, 'report', 'E52 个体语言外设、反馈与忠实翻译 / Co-adaptive language '+lang,
                       render(HERE/f'report.{lang}.md'))
            p.note('registration-final:'+lang, 'E52 计划与执行前补充 / Registration '+lang,
                   render(HERE/f'design.{lang}.md'))
        p.document('record:words', 'record', 'E52 每道问题和真实回答 / Every actual answer',
            f"[原样输出 / Original outputs](/api/v2/projects/{s.project}/artifacts/{artifacts['outputs']['artifact_id']})")
        archive = archive_once(p, 'E52 coadaptive language evidence.zip', historical_scope=(
            'E48 frozen input encoder and recorded physical telemetry remain read-only dependencies',
            'E50 raw local six-field observation and graph-expression/2 retained',
            'No Core/default changes; self-hearing is explicit ordinary sensory input'))
        p.document('record:evidence', 'record', 'E52 课程、原始活动与个人表达器 / Evidence and adapters',
            f"[完整证据 / Evidence](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})")
        for key in ('report:zh', 'report:en'):
            row = p.state[key]
            actual = research_documents.get(s.db, s.project, row['id'], revision=row['revision'])
            if actual['content_hash'] != row['content_hash']:
                raise RuntimeError('report publication mismatch')
        with s.db.tx() as tx:
            dbbytes = tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        resources = {'local_bytes': sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file()),
                     'database_growth': max(0, dbbytes-s.meta['database_bytes_before']),
                     'usage': read_json(WORK/'usage.json'),
                     'available_memory_bytes': psutil.virtual_memory().available,
                     'free_bytes': {d: shutil.disk_usage(d+':/').free for d in ('C', 'D', 'E')}}
        p.document('record:delivery', 'record', 'E52 交付与资源 / Delivery and resources',
            f"项目 / Project: `{s.project}`\n\n"
            f"本地证据（含归档）/ Local evidence including archive: {resources['local_bytes']/2**20:.1f} MiB.\n\n"
            f"发布后数据库增长 / Database growth since registration: {resources['database_growth']/2**20:.1f} MiB; may include other project writes.\n\n"
            "共享账户 / Shared-account usage: 52% → 54%, not task-exclusive billing.\n\n"
            "340 budget-counted source stages/probes; 72.93 recorded compute minutes; seven focused tests passed.\n\n"
            "Core/defaults/old evidence unchanged. Local commits only, no push.\n\n"
            "原始回答、完整证据、中英报告在同一研究项目中 / Original answers, evidence and bilingual reports are stored in this project.")
        delivery = {'project': s.project, 'archive': archive, 'artifacts': artifacts,
                    'documents': {k: v['id'] for k, v in p.state.items() if k.startswith(('report:', 'record:'))},
                    'resources': resources}
        if not (HERE/'delivery.json').exists():
            new_json(HERE/'delivery.json', delivery)
        print({'project': s.project, 'storage_MiB': round((resources['local_bytes']+resources['database_growth'])/2**20, 1)}, flush=True)
    finally:
        s.db.close()


if __name__ == '__main__':
    main()
