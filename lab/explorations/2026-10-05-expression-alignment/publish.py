"""Project-scoped publication, preserving old research and user services."""
import re
import shutil
from urllib.parse import quote
import psutil
from experiment import ROOT,HERE,WORK,read_json,new_json
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import artifact_once,archive_once
from threemind_lab import research_documents


def main():
    s=ArchivedStudy(WORK);s.name=s.settings.name;p=Publication(s)
    try:
        artifacts={}
        for key,path,mime in (('results',HERE/'results.json','application/json'),
                              ('interpretation',HERE/'interpretation-checks.json','application/json'),
                              ('viewer',WORK/'expression-alignment.html','text/html'),
                              ('figure',HERE/'findings.png','image/png'),('patterns',HERE/'process-patterns.png','image/png')):
            artifacts[key]=artifact_once(p,key,path,'E47 '+key,mime)
        def render(path):
            def links(match):
                label,url=match.group(1),match.group(2)
                key={'results.json':'results','interpretation-checks.json':'interpretation',
                     'findings.png':'figure','process-patterns.png':'patterns',
                     '../../../.work/expression-alignment-20261005/expression-alignment.html':'viewer'}.get(url)
                if key:url=f"/api/v2/projects/{s.project}/artifacts/{artifacts[key]['artifact_id']}"
                elif url.endswith('.md') and not url.startswith(('http','/','#')):
                    url='/docs?doc='+quote((path.parent/url).resolve().relative_to(ROOT).as_posix(),safe='')
                return f'[{label}]({url})'
            return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',links,path.read_text(encoding='utf-8'))
        for lang in ('zh','en'):
            report=render(HERE/f'report.{lang}.md')
            p.document('report:'+lang,'report','E47 表达延迟、抑制与新经历 / Expression '+lang,report)
            for name in ('design','stage-ab','report','delivery'):
                p.note(name+'-final:'+lang,'E47 '+name+' '+lang,render(HERE/f'{name}.{lang}.md'))
        p.document('record:viewer','record','E47 逐题与时间核查 / Item and time inspection',
            f"[交互查看 / Open viewer](/api/v2/projects/{s.project}/artifacts/{artifacts['viewer']['artifact_id']})\n\n"
            '原始时间、原样文字、训练/测试边界与逐项得分。 / Original times/text, split boundaries and per-item results.')
        final=WORK/'final-artifacts';final.mkdir(exist_ok=True)
        for source in (HERE/'results.json',HERE/'interpretation-checks.json',
                       ROOT/'docs/zh/reference/expression-observation-tools.md',ROOT/'docs/en/reference/expression-observation-tools.md'):
            dest=final/(source.name if source.suffix=='.json' else source.parents[1].name+'-'+source.name)
            if not dest.exists():shutil.copy2(source,dest)
        # Preserve the initial frozen helper copy and additionally ship the
        # final CLI/control implementation and its focused checks.
        for relative in ('lab/tools/expression_observation.py','lab/tools/connection_controls.py',
                         'tests/test_expression_observation.py','tests/test_connection_controls.py'):
            dest=final/relative;dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():shutil.copy2(ROOT/relative,dest)
        for name in ('verification.json','findings.svg'):
            if not (final/name).exists():shutil.copy2(HERE/name,final/name)
        archive=archive_once(p,'E47 expression alignment evidence.zip',historical_scope=(
            'E46 reused snapshot/probe dependencies identified in dependencies.json; full old archive not duplicated',
            'E46 telemetry and frozen input weights copied without modifying the original sources'))
        p.document('record:evidence','record','E47 完整证据及E46依赖 / Evidence and dependencies',
            f"[E47证据包 / Evidence](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})\n\n"
            '包括设计、代码、轨迹、新快照、模型、计时、失败和旧证据定位；旧E46归档保持原处。')
        for key in ('report:zh','report:en','record:viewer','record:evidence'):
            item=p.state[key];got=research_documents.get(s.db,s.project,item['id'],revision=item['revision'])
            if got['content_hash']!=item['content_hash']:raise RuntimeError('published document differs: '+key)
        new_json(HERE/'delivery.json',{'project':s.project,'artifacts':artifacts,'archive':archive,
            'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},'raw_path':str(WORK)})
        with s.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        local=sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file())
        new_json(HERE/'publication-resources.json',{'local_including_archive':local,'archive_bytes':archive['bytes'],
            'database_growth':max(0,size-s.meta['database_bytes_before']),'total_new_storage':local+max(0,size-s.meta['database_bytes_before']),
            'available_memory':psutil.virtual_memory().available,'free_c':shutil.disk_usage('C:/').free,'free_e':shutil.disk_usage('E:/').free,
            'hard_limit':s.settings.storage_hard,'account_latest':read_json(WORK/'usage.json')['used_percent']})
        print('E47 published: '+s.project,flush=True)
    finally:s.db.close()


if __name__=='__main__':main()
