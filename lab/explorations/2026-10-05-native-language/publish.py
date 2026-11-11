"""Publish E46 through project-scoped research services; no Core jobs."""
import re
import shutil
from urllib.parse import quote

import psutil

from experiment import HERE, ROOT, WORK, read_json, new_json
from lab.tools.study_publication import ArchivedStudy, Publication
from lab.tools.evidence_archive import artifact_once, archive_once
from threemind_lab import research_documents


def main():
    study=ArchivedStudy(WORK);study.name=study.settings.name;p=Publication(study)
    try:
        artifacts={}
        for key,path,mime in (
            ('results',HERE/'results.json','application/json'),
            ('viewer',WORK/'native-expression.html','text/html'),
            ('figure',HERE/'findings.png','image/png'),('vector',HERE/'findings.svg','image/svg+xml')):
            artifacts[key]=artifact_once(p,key,path,'E46 '+key,mime)
        def render(path):
            def links(match):
                label,url=match.group(1),match.group(2)
                key={'results.json':'results','findings.png':'figure','findings.svg':'vector',
                     '../../../.work/native-language-20261005/native-expression.html':'viewer'}.get(url)
                if key:url=f"/api/v2/projects/{study.project}/artifacts/{artifacts[key]['artifact_id']}"
                elif url.endswith('.md') and not url.startswith(('http','/','#')):
                    url='/docs?doc='+quote((path.parent/url).resolve().relative_to(ROOT).as_posix(),safe='')
                return f'[{label}]({url})'
            return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',links,path.read_text(encoding='utf-8'))
        for language in ('zh','en'):
            body=render(HERE/f'report.{language}.md')
            p.document('report:'+language,'report','E46 个体模式与语言释读 / Native expression '+language,body)
            p.note('findings:'+language,'E46 Results '+language,body)
            for key,file in (('design','design'),('calibration','calibration-source'),('mediation','initial-mediation'),('delivery','delivery')):
                p.note(key+'-final:'+language,'E46 '+key+' '+language,render(HERE/f'{file}.{language}.md'))
            p.note('adapter-roles:'+language,'E46 中枢适配器、观察释读与表达 / Adapter roles '+language,
                render(ROOT/f'docs/{language}/reference/central-adapters.md'))
        p.document('record:continuous','record','E46 真实活动与原样释读 / Activity and raw interpretation',
            f"[交互回放 / Interactive replay](/api/v2/projects/{study.project}/artifacts/{artifacts['viewer']['artifact_id']})\n\n"
            '九条连续历史，2289个重叠两秒窗。背景保留，无新教学；被动文字不能自动视为主动表达。 / Nine continuous histories,2289 overlapping two-second windows. Background retained, no new teaching; passive text is not automatically voluntary expression.')
        copies=WORK/'final-artifacts';copies.mkdir(exist_ok=True)
        for source in HERE.iterdir():
            if source.is_file() and source.suffix in ('.json','.svg'):
                target=copies/source.name
                if not target.exists():shutil.copy2(source,target)
        for language in ('zh','en'):
            for stem in ('central-adapters','native-expression-tools'):
                target=copies/f'{stem}.{language}.md'
                if not target.exists():shutil.copy2(ROOT/f'docs/{language}/reference/{stem}.md',target)
        archive=archive_once(p,'E46 reproducible native-language evidence.zip',historical_scope=(
            'E45 input-model71 copied without change','E45/E44 physical-telemetry tape copied without change',
            'E45 input-route reanalysis summaries; full old evidence remains in E45'))
        p.document('record:evidence','record','E46 完整证据 / Complete evidence',
            f"[完整证据包 / Evidence ZIP](/api/v2/projects/{study.project}/artifacts/{archive['artifact_id']})\n\n"
            '课程、原始轨迹、快照、模型、校准与测试清单、反转、干预、连续原文及失败说明。 / Teaching, raw processes, snapshots, weights, calibration/test manifests, reversals, interventions, continuous raw words and setup notes.')
        for key in ('report:zh','report:en','record:continuous','record:evidence'):
            item=p.state[key]
            got=research_documents.get(study.db,study.project,item['id'],revision=item['revision'])
            if got['content_hash']!=item['content_hash']:raise RuntimeError('published document differs: '+key)
        p.guard(reserve=1)
        if not (HERE/'delivery.json').exists():
            new_json(HERE/'delivery.json',{'project':study.project,
                'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},
                'artifacts':artifacts,'archive':archive,'raw_path':str(WORK),
                'completed_cases':read_json(HERE/'results.json')['completed_cases']})
        with study.db.tx() as tx:
            database=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        local=sum(path.stat().st_size for path in WORK.rglob('*') if path.is_file())
        resources={'local_including_archive':local,'archive_bytes':archive['bytes'],
            'database_growth':max(0,database-study.meta['database_bytes_before']),
            'total_new_storage':local+max(0,database-study.meta['database_bytes_before']),
            'hard_limit':study.settings.storage_hard,'available_memory':psutil.virtual_memory().available,
            'free_c':shutil.disk_usage('C:/').free,'free_e':shutil.disk_usage('E:/').free,
            'account_latest':read_json(WORK/'usage.json')['used_percent'],
            'storage_scope':'includes shared database growth conservatively; final receipt is outside its own archive'}
        if not (HERE/'publication-resources.json').exists():new_json(HERE/'publication-resources.json',resources)
        print('E46 published: '+study.project)
        print('Total new storage bytes: '+str(resources['total_new_storage']))
    finally:study.db.close()


if __name__=='__main__':main()
