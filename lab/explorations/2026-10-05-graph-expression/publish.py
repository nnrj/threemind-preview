"""Publish both preserved E50 phases through Lab services; no simulation."""
import re,shutil
from urllib.parse import quote
from common import *
from lab.tools.study_publication import ArchivedStudy,Publication
from lab.tools.evidence_archive import artifact_once,archive_once
from threemind_lab import research_documents


def main():
    earlier=ArchivedStudy(FIRST);earlier.name=earlier.settings.name
    try:
        p1=Publication(earlier)
        p1.document('record:phase-boundary','record','E50 首阶段与修订边界 / Phase boundary',
            '首版全图表达拟合4/16，失败和原始资料保留。来源223多角度教学亦在此保存；后续外设修订另建关联项目，未改Core。 / First whole-graph fit4/16 is retained. Source223 teaching was collected here; later instrument revisions use a linked project with unchanged Core.')
        a1=archive_once(p1,'E50 initial instrument and source223.zip',historical_scope=('Reuses E48 immutable observations; new source223 teaching and raw probes included',))
    finally:earlier.db.close()
    s=ArchivedStudy(WORK);s.name=s.settings.name;p=Publication(s)
    try:
        items=[('results',HERE/'results.json','application/json'),('verification',HERE/'verification.json','application/json'),
               ('outputs',WORK/'outputs.html','text/html'),('figure',HERE/'outcomes.png','image/png')]
        artifacts={key:artifact_once(p,key,path,'E50 '+key,mime) for key,path,mime in items}
        def render(path):
            def link(match):
                label,url=match.group(1),match.group(2)
                for key,file,_ in items:
                    if not url.startswith(('http','/','#')) and (path.parent/url).resolve()==file.resolve():
                        return f"[{label}](/api/v2/projects/{s.project}/artifacts/{artifacts[key]['artifact_id']})"
                if url.endswith('.md') and not url.startswith(('http','/','#')):
                    url='/docs?doc='+quote((path.parent/url).resolve().relative_to(ROOT).as_posix(),safe='')
                elif url.endswith('.py') and not url.startswith(('http','/','#')):
                    source=(path.parent/url).resolve().relative_to(ROOT).as_posix()
                    return f'{label} (`{source}`)'
                return f'[{label}]({url})'
            return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,path.read_text(encoding='utf-8'))
        for language in ('zh','en'):
            p.document('report:'+language,'report','E50 局部活动表达与共同所指 / Local expression and common referents '+language,render(HERE/f'report.{language}.md'))
            for name in ('local-registration','extension','bus-audit'):
                p.note(name+':'+language,'E50 '+name+' '+language,render(HERE/f'{name}.{language}.md'))
        p.document('record:outputs','record','E50 原话、误答和干预 / Original expression and interventions',
            f"[打开逐题记录 / Open outputs](/api/v2/projects/{s.project}/artifacts/{artifacts['outputs']['artifact_id']})\n\n"
            '所有输出原样保留，未给无提示活动设语义答案。 / Original words retained; no assumed truth for no-cue output.')
        final=WORK/'final-artifacts';final.mkdir(exist_ok=True)
        for file in HERE.iterdir():
            if file.suffix in ('.json','.md','.png') and file.is_file():
                target=final/file.name
                if not target.exists():shutil.copy2(file,target)
        for relative in ('src/threemind_transformer/graph_expression.py','src/threemind_transformer/graph_expression_cli.py',
                         'src/threemind_transformer/local_activity.py','src/threemind_runtime/graph_observation.py',
                         'tests/test_graph_expression.py','tests/test_local_graph_expression.py',
                         'docs/zh/reference/graph-expression.md','docs/en/reference/graph-expression.md'):
            target=final/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():shutil.copy2(ROOT/relative,target)
        previous_receipt={'project':earlier.project,'artifact':a1}
        if not (WORK/'initial-archive.json').exists():new_json(WORK/'initial-archive.json',previous_receipt)
        archive=archive_once(p,'E50 local expression and attribution evidence.zip',historical_scope=(
            'Initial failed instrument and source223 evidence in separately linked initial archive',
            'E48/E49 dependencies reused read-only',
            'Measured source versions preserved; delivered local reader and CLI copied in final-artifacts after experiments'))
        p.document('record:evidence','record','E50 两阶段证据与表达模型 / Evidence and models',
            f"[局部表达与归因 / Local expression](/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']})\n\n"
            f"[首阶段失败模型和教学 / Initial phase](/api/v2/projects/{earlier.project}/artifacts/{a1['artifact_id']})\n\n"
            '旧数据原处保留；两阶段合计受同一预算约束。 / Original evidence retained; both phases share one budget.')
        for key in ('report:zh','report:en','record:outputs','record:evidence'):
            item=p.state[key];got=research_documents.get(s.db,s.project,item['id'],revision=item['revision'])
            if got['content_hash']!=item['content_hash']:raise RuntimeError('published document mismatch')
        new_json(HERE/'delivery.json',{'project':s.project,'initial_phase':previous_receipt,'artifacts':artifacts,'archive':archive,
            'documents':{k:v['id'] for k,v in p.state.items() if k.startswith(('report:','record:'))},'raw_paths':[str(FIRST),str(WORK)]})
        with s.db.tx() as tx:size=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        total_local=sum(f.stat().st_size for base in (FIRST,WORK) for f in base.rglob('*') if f.is_file())
        growth=max(0,size-earlier.meta['database_bytes_before'])
        new_json(HERE/'publication-resources.json',{'local_bytes':total_local,'database_growth':growth,'combined_storage':total_local+growth,
            'hard_limit':s.settings.storage_hard,'free_bytes':{d:shutil.disk_usage(d+':/').free for d in ('C','D','E')},
            'account':read_json(WORK/'usage.json')})
        print({'published':s.project,'total_storage_MiB':round((total_local+growth)/2**20,1)},flush=True)
    finally:s.db.close()


if __name__=='__main__':main()
