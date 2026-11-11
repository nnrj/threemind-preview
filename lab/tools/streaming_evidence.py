"""One-pass ZIP upload with bounded memory, without a duplicate local archive.

Original files remain intact. ZIP CRC is produced while reading each member;
the normal database upload computes its own SHA256. No full reread is needed.
"""
import io
import json
from pathlib import Path
import queue
import threading
import zipfile
from lab.tools.service_study import encoded


class ZipStream:
    def __init__(self, entries, *, check=lambda: None, omitted_derived_files=()):
        self.queue=queue.Queue(maxsize=8);self.cancel=threading.Event();self.buffer=bytearray()
        self.finished=False;self.error=None;self.manifest=[];self.bytes_read=0
        self.entries=list(entries);self.check=check
        self.omitted_derived_files=list(omitted_derived_files)
        names=[name for name,path in self.entries]
        if len(names)!=len(set(names)) or 'archive-manifest.json' in names:
            raise ValueError('unique archive member names')
        if any(name.startswith('/') or '..' in Path(name).parts for name in names):raise ValueError('relative safe archive paths')
        self.thread=threading.Thread(target=self._produce,daemon=True);self.thread.start()

    def _put(self,value):
        while not self.cancel.is_set():
            try:self.queue.put(value,timeout=.1);return
            except queue.Full:pass
        raise InterruptedError('archive consumer closed')

    def _produce(self):
        owner=self
        class Sink(io.RawIOBase):
            def writable(self):return True
            def write(self,data):
                for start in range(0,len(data),2**20):owner._put(bytes(data[start:start+2**20]))
                return len(data)
            def flush(self):pass
        try:
            with zipfile.ZipFile(Sink(),'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
                for name,path in self.entries:
                    self.check()
                    if self.cancel.is_set():raise InterruptedError('archive cancelled')
                    archive.write(path,name,compress_type=zipfile.ZIP_STORED if path.suffix in ('.gz','.npz','.png','.webm','.mp4') else zipfile.ZIP_DEFLATED)
                    info=archive.getinfo(name)
                    self.manifest.append({'path':name,'bytes':info.file_size,'zip_crc32':f'{info.CRC:08x}'})
                archive.writestr('archive-manifest.json',encoded({'files':self.manifest,'historical_data_included':False,
                    'omitted_derived_files':self.omitted_derived_files,
                    'verification':'one-pass ZIP CRC and normal upload SHA256; originals retained; no duplicate local ZIP'}))
        except BaseException as error:self.error=error
        finally:
            if not self.cancel.is_set():
                try:self._put(None)
                except InterruptedError:pass

    def read(self,count):
        if not isinstance(count,int) or count<=0:raise ValueError('positive bounded read size')
        while len(self.buffer)<count and not self.finished:
            value=self.queue.get()
            if value is None:
                self.finished=True
                if self.error:raise RuntimeError('archive production failed') from self.error
            else:self.buffer.extend(value)
        value=bytes(self.buffer[:count]);del self.buffer[:count];self.bytes_read+=len(value);return value

    def close(self):
        self.cancel.set();self.thread.join(timeout=3)
        if self.thread.is_alive():raise RuntimeError('archive producer did not stop')


def archive_stream_once(publication,title,*,omit_derived_names=()):
    p=publication
    if p.state.get('archive',{}).get('artifact_id'):return p.state['archive']
    entries=[];omitted=[]
    for path in p.work.rglob('*'):
        if (path.is_file() and path.name not in ('publication.json','streamed-archive-manifest.json')
            and path.suffix not in ('.tmp','.pyc','.zip') and '__pycache__' not in path.parts and '.partial' not in path.name):
            name=path.relative_to(p.work).as_posix()
            if path.name in omit_derived_names:
                omitted.append({'path':name,'bytes':path.stat().st_size,'reason':'derived file; retained locally; original process and reconstruction code archived'})
            else:entries.append((name,path))
    existing={n for n,_ in entries}
    for path in p.study.here.rglob('*'):
        name='publication-sources/'+path.relative_to(p.study.here).as_posix()
        if path.is_file() and path.suffix in ('.py','.md','.json','.png') and name not in existing:entries.append((name,path))
    entries.sort(key=lambda x:x[0])
    p.guard(reserve=int(sum(path.stat().st_size for _,path in entries)*1.15))
    item=p.state.get('archive')
    if item is None:
        p.queue_clear();item=p.remember('archive',{'job_id':p.db.enqueue(p.project,'analysis',{'purpose':'stream registered evidence; no Core execution'})['id']})
    with p.owned(item['job_id']) as job:
        stream=ZipStream(entries,check=p.guard,omitted_derived_files=omitted)
        try:
            artifact=p.db.put_artifact_stream(job,title,'application/zip',stream,metadata={
                'schema':'study-evidence/3','study':p.study.name,'streamed':True,'member_count':len(entries)})
            if artifact['bytes']!=stream.bytes_read or not stream.finished:raise ValueError('incomplete stream upload')
            p.db.finish(job,result={'artifact_id':str(artifact['id'])})
            manifest={'files':stream.manifest,'omitted_derived_files':omitted,'artifact_id':str(artifact['id']),'bytes':stream.bytes_read}
        finally:stream.close()
    (p.work/'streamed-archive-manifest.json').write_bytes(encoded(manifest))
    return p.remember('archive',item|{'artifact_id':str(artifact['id']),'sha256':artifact['sha256'],
        'bytes':artifact['bytes'],'streamed_without_local_zip':True,'members':len(entries)})
