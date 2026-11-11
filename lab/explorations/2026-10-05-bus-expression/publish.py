"""Publish E49 through existing research services, one evidence archive only."""
import re,shutil,psutil
from urllib.parse import quote
from common import *
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import artifact_once,archive_once
from threemind_lab import research_documents


def main():
    s=ArchivedStudy(WORK);s.name=s.settings.name;p=Publication(s)
    try:
        if shutil.disk_usage('D:/').free<15*2**30:raise RuntimeError('database volume reserve')
        artifacts={}
        items=[(name,HERE/(name+'.json'),'application/json') for name in
               ('results','audit','effective-mechanisms','reteaching-results','verification')]
        items.append(('outputs',WORK/'outputs.html','text/html'))
        for key,path,mime in items:artifacts[key]=artifact_once(p,key,path,'E49 '+key,mime)
        def render(path):
            def link(match):
                label,url=match.group(1),match.group(2);key=None
                for candidate,source,_ in items:
                    if not url.startswith(('http','/','#')) and (path.parent/url).resolve()==source.resolve():key=candidate;break
                if key:url=f"/api/v2/projects/{s.project}/artifacts/{artifacts[key]['artifact_id']}"
                elif url.endswith('.md') and not url.startswith(('http','/','#')):
                    url='/docs?doc='+quote((path.parent/url).resolve().relative_to(ROOT).as_posix(),safe='')
                return f'[{label}]({url})'
            return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,path.read_text(encoding='utf-8'))
        for language in ('zh','en'):
            p.document('report:'+language,'report','E49 总线、纠错与跟随表达 / Buses and adaptive expression '+language,render(HERE/f'report.{language}.md'))
            for name in ('report','teaching-amendment','followup-registration','reteaching-registration','joint-registration','shared-registration'):
                p.note(name+'-final:'+language,'E49 '+name+' '+language,render(HERE/f'{name}.{language}.md'))
        p.document('record:outputs','record','E49 原样输出逐题查看 / Original outputs',
            f"[打开查看器 / Open viewer](/api/v2/projects/{s.project}/artifacts/{artifacts['outputs']['artifact_id']})\n\n"
            '包括所有模型的错误和无提示原词；无提示没有预设正确答案。 / Includes errors and unchanged no-cue words; no assumed no-cue semantic answer.')
        final=WORK/'final-artifacts';final.mkdir(exist_ok=True)
        for file in HERE.iterdir():
            if file.suffix in ('.json','.md') and file.is_file():
                target=final/file.name
                if not target.exists():shutil.copy2(file,target)
        for relative in ('lab/tools/expression_calibration.py','src/threemind_runtime/activity_stream.py',
                         'tests/test_raw_activity_stream.py','docs/zh/reference/bus-expression.md','docs/en/reference/bus-expression.md',
                         'docs/zh/plans/bus-and-expression-calibration.md','docs/en/plans/bus-and-expression-calibration.md'):
            target=final/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(ROOT/relative,target)
        archive=archive_once(p,'E49 bus and expression evidence.zip',historical_scope=(
            'E47/E48 parent states and original probes reused read-only; dependencies.json identifies them',
            'New Core review branches, raw probes, original words and adapter checkpoints included',
            'The new raw stream and final calibration tool are copied separately in final-artifacts'))
        p.document('record:evidence','record','E49 完整证据与表达模型 / Evidence and expression models',
            f"[下载证据包 / Download archive](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})\n\n"
            '保存新增状态、输入、过程、模型、登记和失败结果。旧资料通过dependencies.json定位。 / New states, inputs, processes, models, registrations and failures. Historical dependencies remain separately identified.')
        for key in ('report:zh','report:en','record:outputs','record:evidence'):
            item=p.state[key];got=research_documents.get(s.db,s.project,item['id'],revision=item['revision'])
            if got['content_hash']!=item['content_hash']:raise RuntimeError('published document mismatch')
        with s.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        local=sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file());growth=max(0,size-s.meta['database_bytes_before'])
        new_json(HERE/'delivery.json',{'project':s.project,'artifacts':artifacts,'archive':archive,
            'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},'raw_path':str(WORK)})
        resources={'local_including_archive':local,'database_growth':growth,'total_new_storage':local+growth,
            'archive_bytes':archive['bytes'],'hard_limit':s.settings.storage_hard,
            'free_bytes':{drive:shutil.disk_usage(drive+':/').free for drive in ('C','D','E')},
            'available_memory':psutil.virtual_memory().available,'account_latest':read_json(WORK/'usage.json')['used_percent']}
        new_json(HERE/'publication-resources.json',resources)
        print({'published':s.project,'models':14,'storage_mib':round((local+growth)/2**20,1),'archive_mib':round(archive['bytes']/2**20,1)},flush=True)
    finally:s.db.close()


if __name__=='__main__':main()
