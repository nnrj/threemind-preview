"""Store E30 reports and evidence without redundant whole-archive rereads."""
import json
import hashlib
import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import quote
from experiment import study,WORK,HERE
from lab.tools.study_publication import Publication
from lab.tools.service_study import encoded
from threemind_lab import research_documents
from threemind_lab.database import LOCAL_USER


def archive_once(publication):
    if publication.state.get('archive',{}).get('artifact_id'):return publication.state['archive']
    path=WORK/'evidence.zip';partial=WORK/'evidence.zip.partial'
    if not path.exists():
        files=[p for p in WORK.rglob('*') if p.is_file() and p not in (path,partial,publication.path)
               and p.suffix not in ('.tmp','.pyc') and '__pycache__' not in p.parts and '.partial' not in p.name]
        publication.guard(reserve=sum(p.stat().st_size for p in files))
        manifest=[]
        with zipfile.ZipFile(partial,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
            for source in sorted(files):
                publication.guard();name=source.relative_to(WORK).as_posix()
                z.write(source,name,compress_type=zipfile.ZIP_STORED if source.suffix in ('.gz','.png') else zipfile.ZIP_DEFLATED)
                info=z.getinfo(name)
                manifest.append({'path':name,'bytes':info.file_size,'zip_crc32':f'{info.CRC:08x}'})
            for source in sorted(HERE.iterdir()):
                if source.suffix in ('.py','.mjs','.md'):
                    name='publication-sources/'+source.name;z.write(source,name)
                    info=z.getinfo(name);manifest.append({'path':name,'bytes':info.file_size,'zip_crc32':f'{info.CRC:08x}'})
            z.writestr('archive-manifest.json',encoded({'files':manifest,'historical_data_included':False,
                'verification':'one-pass ZIP CRC and size; database upload SHA256; no redundant content reread or full Core replay'}))
        partial.replace(path)
    # Header checks detect assembly omissions; data integrity is represented by ZIP CRC
    # and the hash calculated during the database's normal upload, not a second read.
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read('archive-manifest.json'))['files']
        if set(z.namelist()) != {f['path'] for f in manifest}|{'archive-manifest.json'}:raise ValueError('archive member list')
    publication.guard(reserve=int(path.stat().st_size*1.15))
    item=publication.state.get('archive')
    if item is None:
        publication.queue_clear()
        item=publication.remember('archive',{'job_id':publication.db.enqueue(publication.project,'analysis',
            {'purpose':'store E30 evidence; no Core execution'})['id']})
    with publication.owned(item['job_id']) as job,path.open('rb') as stream:
        artifact=publication.db.put_artifact_stream(job,'E30 ocean causal evidence','application/zip',stream,
            metadata={'schema':'study-evidence/2','study':'ocean-causality/1','header_checked_members':len(manifest),
                      'verification':'single upload hash; no independent database reread'})
        if artifact['bytes']!=path.stat().st_size:raise ValueError('upload size mismatch')
        publication.db.finish(job,result={'artifact_id':str(artifact['id']),'evidence_archive':True})
    return publication.remember('archive',item|{'artifact_id':str(artifact['id']),'sha256':artifact['sha256'],
        'bytes':artifact['bytes'],'header_checked_members':len(manifest)})


if __name__=='__main__':
    s=study();p=Publication(s)
    try:
        for lang in ('zh','en'):
            source=HERE/f'report.{lang}.md'
            body=source.read_text(encoding='utf-8')
            def document_link(match):
                label,url=match.group(1),match.group(2)
                if url.endswith('.md') and not url.startswith(('/','http','#')):
                    relative=(HERE/url).resolve().relative_to(HERE.parents[2]).as_posix()
                    return f'[{label}](/docs?doc={quote(relative,safe="")})'
                return match.group(0)
            body=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',document_link,body)
            for figure in ('ecology','causal-process','closed-loop'):
                image=WORK/'figures'/f'{figure}.png'
                if image.exists():body=re.sub(r'!\[[^\]]*\]\(figures/'+figure+r'\.png\)',p.image(f'E30-{figure}',image),body)
            key='report:'+lang
            if key in p.state:
                previous=research_documents.get(s.db,s.project,p.state[key]['id'])
                if previous['spec']['blocks'][0]['markdown']!=body:
                    spec=previous['spec'];spec['blocks'][0]['markdown']=body
                    updated=research_documents.save(s.db,s.project,LOCAL_USER,previous['id'],
                        {'operation_id':s.identity(key+':content:'+hashlib.sha256(body.encode()).hexdigest()),'expected_revision':previous['revision'],'spec':spec})
                    p.remember(key,updated)
            else:p.document(key,'report','E30 海洋控制与内部作用 / Ocean control and internal contribution '+lang,body)
            p.note('results:'+lang,'E30 实验结论 / Findings '+lang,body)
        p.note('execution-notes','E30 执行与更正',(HERE/'execution-notes.md').read_text(encoding='utf-8'))
        artifact=archive_once(p)
        link=f'/api/v2/projects/{s.project}/artifacts/{artifact["artifact_id"]}'
        p.document('record:evidence','record','E30 原始证据与可交互回放',
            f'本批原始输入、快照、干预轨迹、代码和HTML回放：[下载证据包]({link})。\n\n解压后打开 views/g0-core.html 或其他回放。历史实验不包含其中。')
        p.guard()
        print(json.dumps({'project':s.project,'archive_bytes':artifact['bytes'],
                          'reports':{k:v['id'] for k,v in p.state.items() if k.startswith('report:')}}),flush=True)
    finally:s.db.close()
