"""One-pass evidence archive with ZIP CRC and the normal database upload hash.

No repeated full-content audit or automatic deletion. Existing source evidence
is retained, and archives are assembled only from a registered study directory.
"""
import json
import zipfile
from lab.tools.service_study import encoded


def prepare_archive(publication,*,historical_scope=()):
    """Write a local archive only; database transfer is a separate operation."""
    p=publication;work=p.work
    path=work/'evidence.zip';partial=work/'evidence.zip.partial'
    if not path.exists():
        files=[f for f in work.rglob('*') if f.is_file() and f not in (path,partial,p.path)
               and f.suffix not in ('.tmp','.pyc') and '__pycache__' not in f.parts and '.partial' not in f.name]
        p.guard(reserve=sum(f.stat().st_size for f in files));manifest=[]
        with zipfile.ZipFile(partial,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
            for source in sorted(files):
                p.guard();name=source.relative_to(work).as_posix()
                z.write(source,name,compress_type=zipfile.ZIP_STORED if source.suffix in ('.gz','.png','.mp4','.webm') else zipfile.ZIP_DEFLATED)
                info=z.getinfo(name);manifest.append({'path':name,'bytes':info.file_size,'zip_crc32':f'{info.CRC:08x}'})
            for source in sorted(p.study.here.rglob('*')):
                if source.is_file() and source.suffix in ('.py','.mjs','.md','.png') and '__pycache__' not in source.parts:
                    name='publication-sources/'+source.relative_to(p.study.here).as_posix();z.write(source,name)
                    info=z.getinfo(name);manifest.append({'path':name,'bytes':info.file_size,'zip_crc32':f'{info.CRC:08x}'})
            z.writestr('archive-manifest.json',encoded({'files':manifest,'historical_data_included':bool(historical_scope),
                'historical_scope':list(historical_scope),
                'verification':'one-pass ZIP CRC and size; normal upload SHA256; no redundant full reread'}))
        partial.replace(path)
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read('archive-manifest.json'))['files']
        if set(z.namelist())!={f['path'] for f in manifest}|{'archive-manifest.json'}:raise ValueError('archive member list')
    return path,len(manifest)


def archive_once(publication,title,*,historical_scope=()):
    p=publication
    if p.state.get('archive',{}).get('artifact_id'):return p.state['archive']
    path,count=prepare_archive(p,historical_scope=historical_scope)
    return artifact_once(p,'archive',path,title,'application/zip',
        metadata={'schema':'study-evidence/2','study':p.study.name,'header_checked_members':count,
                  'verification':'single upload hash; no independent full database reread'})


def artifact_once(publication,key,path,title,mime,*,metadata=None):
    p=publication
    if p.state.get(key,{}).get('artifact_id'):return p.state[key]
    p.guard(reserve=int(path.stat().st_size*1.15))
    item=p.state.get(key)
    if item is None:
        p.queue_clear()
        item=p.remember(key,{'job_id':p.db.enqueue(p.project,'analysis',{'purpose':'store measured research artifact; no Core execution'})['id']})
    with p.owned(item['job_id']) as job,path.open('rb') as stream:
        artifact=p.db.put_artifact_stream(job,title,mime,stream,metadata=metadata or {})
        if artifact['bytes']!=path.stat().st_size:raise ValueError('upload size mismatch')
        p.db.finish(job,result={'artifact_id':str(artifact['id']),'media_type':mime})
    return p.remember(key,item|{'artifact_id':str(artifact['id']),'sha256':artifact['sha256'],'bytes':artifact['bytes']})
