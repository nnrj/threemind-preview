"""Publish E48 reports and evidence once, through the existing Lab services."""
import re,shutil,psutil
from urllib.parse import quote
from experiment import *
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import artifact_once,archive_once
from threemind_lab import research_documents


def main():
    s=ArchivedStudy(WORK);s.name=s.settings.name;p=Publication(s)
    try:
        # PostgreSQL's Windows service is on D; retain a database-volume reserve
        # in addition to the already registered C/E reserves.
        if shutil.disk_usage('D:/').free<15*2**30:raise RuntimeError('database volume reserve')
        artifacts={}
        items=[('results',HERE/'results.json','application/json'),('raw-old',HERE/'raw-old.json','application/json'),
            ('raw-timing',HERE/'raw-timing.json','application/json'),('timing-followup-results',HERE/'timing-followup-results.json','application/json'),
            ('events-results',HERE/'events-results.json','application/json'),('figure',HERE/'findings.png','image/png'),
            ('viewer',WORK/'raw-expression.html','text/html')]
        for key,path,mime in items:artifacts[key]=artifact_once(p,key,path,'E48 '+key,mime)
        def render(path):
            def link(match):
                label,url=match.group(1),match.group(2);key=None
                for candidate,source,_ in items:
                    if not url.startswith(('http','/','#')) and (path.parent/url).resolve()==source.resolve():
                        key=candidate;break
                if key:url=f"/api/v2/projects/{s.project}/artifacts/{artifacts[key]['artifact_id']}"
                elif url.endswith('.md') and not url.startswith(('http','/','#')):
                    url='/docs?doc='+quote((path.parent/url).resolve().relative_to(ROOT).as_posix(),safe='')
                return f'[{label}]({url})'
            return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,path.read_text(encoding='utf-8'))
        for language in ('zh','en'):
            p.document('report:'+language,'report','E48 原始状态、时序与表达 / Raw state and expression '+language,render(HERE/f'report.{language}.md'))
            for name in ('report','scoring-correction','decoder-fit-registration','trajectory-registration',
                         'timing-followup-registration','events-registration','resource-amendment'):
                p.note(name+'-final:'+language,'E48 '+name+' '+language,render(HERE/f'{name}.{language}.md'))
        p.document('record:viewer','record','E48 原样输出逐题查看 / Inspect original outputs',
            f"[打开逐题查看器 / Open viewer](/api/v2/projects/{s.project}/artifacts/{artifacts['viewer']['artifact_id']})\n\n"
            '并列实际答对、旧提示特异评分及无提示文字；无提示没有预设的语义真值。 / Actual correctness, old cue-specific score and unchanged no-cue text; no assumed semantic truth for no-cue activity.')
        final=WORK/'final-artifacts';final.mkdir(exist_ok=True)
        for file in HERE.iterdir():
            if file.suffix in ('.json','.md','.png','.svg') and file.is_file():
                target=final/file.name
                if not target.exists():shutil.copy2(file,target)
        for relative in ('lab/tools/raw_state_expression.py','lab/tools/visual_event_world.py',
            'tests/test_raw_state_expression.py','tests/test_visual_event_world.py',
            'docs/zh/reference/raw-state-expression.md','docs/en/reference/raw-state-expression.md'):
            target=final/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(ROOT/relative,target)
        dependencies=WORK/'dependencies.json'
        if not dependencies.exists():new_json(dependencies,{'reused_E47_project':read_json(OLD/'platform.json')['project_id'],
            'scope':'source states and original probe processes remain in immutable E47 evidence; copied telemetry and frozen input dependency',
            'old_work':str(OLD),'old_base_commit':'a6b7aa4','new_registration_commit':'9b0cdc1'})
        archive=archive_once(p,'E48 raw state and temporal expression evidence.zip',historical_scope=(
            'E47 source states and probes are reused read-only; full old archive is not duplicated',
            'The original resource registration and dated amendment are both retained'))
        p.document('record:evidence','record','E48 完整证据与模型 / Evidence and decoders',
            f"[证据包 / Evidence archive](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})\n\n"
            '包含新轨迹、完整状态样本、训练模型、输入、代码、失败及更正；E47依赖在dependencies.json中定位。 / New processes, state samples, models, inputs, code, failures and corrections; E47 dependencies are identified in dependencies.json.')
        for key in ('report:zh','report:en','record:viewer','record:evidence'):
            item=p.state[key];got=research_documents.get(s.db,s.project,item['id'],revision=item['revision'])
            if got['content_hash']!=item['content_hash']:raise RuntimeError('published document mismatch')
        with s.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        local=sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file());growth=max(0,size-s.meta['database_bytes_before'])
        new_json(HERE/'delivery.json',{'project':s.project,'artifacts':artifacts,'archive':archive,
            'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},'raw_path':str(WORK)})
        new_json(HERE/'publication-resources.json',{'local_including_archive':local,'database_growth':growth,
            'total_new_storage':local+growth,'archive_bytes':archive['bytes'],'hard_limit':s.settings.storage_hard,
            'free_bytes':{drive:shutil.disk_usage(drive+':/').free for drive in ('C','D','E')},
            'available_memory':psutil.virtual_memory().available,'account_latest':read_json(WORK/'usage.json')['used_percent']})
        print('E48 published: '+s.project,flush=True)
    finally:s.db.close()


if __name__=='__main__':main()
