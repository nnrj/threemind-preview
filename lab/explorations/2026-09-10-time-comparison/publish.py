"""Publish only this stopped study's existing evidence; never run a model."""
import hashlib
import importlib.util
import json
import zipfile

from run import HERE,ROOT,WORK,META,encoded,save,resources,old_inventory,capture_implementation
from threemind_lab import notebooks,report_exports
from threemind_lab.database import LOCAL_USER

base_path=HERE.parent/'2026-09-09-calibrated-generalization/publish.py'
loader=importlib.util.spec_from_file_location('time_study_publication_base',base_path)
base=importlib.util.module_from_spec(loader)
loader.loader.exec_module(base)
base.HERE,base.WORK,base.META=HERE,WORK,META
base.WORKER='time-comparison-20260910-publication'


class Publisher(base.Publisher):
    def __init__(self):
        super().__init__()
        self.capabilities.update(executor=str(HERE.relative_to(ROOT)/'publish.py'),
             features={'worker.core':{'state':'available'},'worker.report_export_v1':{'state':'available'}})
        self.db.announce_worker(base.WORKER,self.capabilities)

    def publish(self):
        # Checksummed archive includes complete and explicitly partial evidence.
        archive=WORK/'evidence.zip'
        index=HERE/'evidence-index.json'
        if not archive.exists():
            files=[p for p in HERE.iterdir() if p.is_file() and p.name not in
                   ('platform.json','evidence-index.json','verification.json')]
            files += [p for p in WORK.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                      and p.name!='evidence.zip']
            manifest=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,
                           sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(files)]
            save(index,dict(files=manifest,partial_files=['.work/time-comparison-20260910/dialogue-41701-legacy-no_input.jsonl.gz'],
                            stop_reason='180 second computation deadline',completed=False))
            with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
                for p in files+[index]:z.write(p,p.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(archive) as z:assert z.testzip() is None
        upload=self.entry('archive')
        if not upload.get('done'):
            if not upload.get('job_id'):
                pending=self.db.enqueue(self.project,'analysis',dict(executor=self.capabilities['executor'],
                    purpose='archive stopped time comparison, without model execution'))
                upload['job_id']=str(pending['id']);self.flush()
            job=self.claim_owned(upload['job_id'])
            self.artifact(job,archive,'application/zip')
            self.artifact(job,index,'application/json')
            self.db.finish(job,result={'archived':True,'status':'partial-resource-stop'})
            upload['done']=True;self.flush()
        attachment=self.state['artifact:evidence.zip']['artifact_id']
        picture=self.entry('picture')
        notebooks.save_asset(self.db,self.project,LOCAL_USER,picture['id'],'time-comparison.png',
                             (HERE/'time-comparison.png').read_bytes())
        image_url=f"/api/v2/projects/{self.project}/note-assets/{picture['id']}"
        artifact_url=f"/api/v2/projects/{self.project}/artifacts/{attachment}"
        def rich(text):
            import re
            # Markdown files in the bundle are downloadable; avoid broken
            # relative links inside the platform's document viewer.
            text=text.replace('](time-comparison.png)',']('+image_url+')')
            return re.sub(r'\]\(([^):]+\.(?:md|json))\)',']('+artifact_url+')',text)
        markdown=rich((HERE/'report.md').read_text(encoding='utf-8'))
        markdown+='\n\n[下载完整证据ZIP（含中止标记）]('+artifact_url+')\n'
        record=self.document('record','record','时间对照记录：宿主解耦、帧数影响与资源中止',[],[
            base.commentary('data',markdown)])
        report=self.document('report','report','时间机制第一阶段报告（部分完成，180秒中止）',[],[
            base.commentary('status','本报告保留已完成与中止的实验，未完成项不算通过。','purpose'),
            dict(id='record',type='record_block',record_id=record,revision=1,block_id='data')])
        note=self.entry('note:results')
        if not note.get('revision'):
            saved=notebooks.save_note(self.db,self.project,LOCAL_USER,note['id'],dict(
               operation_id=note['operation_id'],expected_revision=0,kind='note',collection_id=self.meta['notebook_id'],
               title='第一阶段时间对照：结果与下一步边界',body={'format':'markdown','text':markdown}))
            note.update(revision=saved['revision'],content_hash=saved['content_hash']);self.flush()
        for fmt in ('markdown','html'):
            item=self.entry('export:'+fmt)
            self.service_job(item,lambda item=item,fmt=fmt:report_exports.request(self.db,self.project,LOCAL_USER,report,
                dict(operation_id=item['operation_id'],revision=1,format=fmt,language='zh-CN',include_data=True)),
                report_exports.execute)
        self.verify()
        print('Archived existing evidence and published partial report; no model execution.')

    def verify(self):
        verified=[]
        with self.db.tx(self.project) as c:
            artifacts=c.execute('SELECT id,bytes,sha256,name FROM artifacts WHERE project_id=%s ORDER BY id',
                                (self.project,)).fetchall()
            for row in artifacts:
                h=hashlib.sha256(); size=0
                for part in c.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',
                                     (row['id'],)).fetchall():
                    raw=bytes(part['body']);h.update(raw);size+=len(raw)
                assert h.hexdigest()==row['sha256'] and size==row['bytes']
                verified.append(dict(id=str(row['id']),name=row['name'],bytes=size,sha256=h.hexdigest()))
            jobs=c.execute('SELECT id,status FROM jobs WHERE project_id=%s ORDER BY id',(self.project,)).fetchall()
            assert all(job['status']=='done' for job in jobs)
        current=capture_implementation('native')
        old=json.loads((HERE/'implementation.json').read_bytes())['current_implementation']
        assert current['source_files']==old['source_files'] and current['native_binary_sha256']==old['native_binary_sha256']
        assert old_inventory(self.db)==self.meta['previous_projects']
        r=resources(self.db)
        growth=max(0,r['database_bytes']-self.meta['resources_before']['database_bytes'])
        assert growth+r['local_bytes']<512*1024**2
        save(HERE/'verification.json',dict(artifact_hashes_verified=verified,publication_jobs=jobs,
            core_and_mapping_unchanged=True,previous_projects_unchanged=True,resources=r,
            database_growth_bytes=growth,combined_new_storage_bytes=growth+r['local_bytes'],
            quota=dict(start_used_percent=73,last_checked_used_percent=74),model_execution_status='stopped'),exclusive=False)
        print(json.dumps(dict(database_growth_bytes=growth,combined_bytes=growth+r['local_bytes'],
                              project_id=self.project,report_id=self.state['document:report']['id'])))


if __name__=='__main__':
    p=Publisher()
    try:p.publish()
    finally:p.db.close()
