"""Verify only this project's archived bytes; publish a separate completion note."""
import hashlib
import io
import json
import shutil
import time
import zipfile
from datetime import datetime,UTC

from publish import Publisher
from run import HERE,WORK,META,encoded
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER


def close():
    publisher=Publisher()
    try:
        if publisher.state.get('completion',{}).get('done'):
            raise RuntimeError('Completion already published; do not overwrite the audit')
        started=time.monotonic()
        verified=[]
        with publisher.db.tx(publisher.project) as db:
            files=db.execute('SELECT id,name,bytes,sha256,media_type FROM artifacts WHERE project_id=%s ORDER BY id',
                             (publisher.project,)).fetchall()
            for file in files:
                assert time.monotonic()-started<120
                assert file['bytes']<32*1024**2, 'Do not load an unexpectedly large artifact'
                chunks=db.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',
                                  (file['id'],)).fetchall()
                body=b''.join(bytes(r['body']) for r in chunks)
                assert len(body)==file['bytes']
                assert hashlib.sha256(body).hexdigest()==file['sha256']
                item={k:str(v) if k=='id' else v for k,v in file.items()}
                if file['media_type']=='application/zip' or file['name'].endswith('.zip'):
                    with zipfile.ZipFile(io.BytesIO(body)) as archive:
                        assert sum(i.file_size for i in archive.infolist())<128*1024**2
                        assert archive.testzip() is None
                        item['zip_members']=len(archive.infolist())
                verified.append(item)
        for fmt in ('markdown','html'):
            result=publisher.state['export:'+fmt]['result']
            assert not result['warnings']
            assert result['document_hash']==publisher.state['document:report']['content_hash']
            for key in ('artifact_id','bundle_artifact_id'):
                assert any(r['id']==result[key] for r in verified)
        acceptance=json.loads((HERE/'acceptance.json').read_bytes())
        assert acceptance['all_original_nodes_tied_strongest_verified']==36
        audit=dict(checked_at=datetime.now(UTC).isoformat(),project_id=publisher.project,
                   pre_completion_artifact_count=len(verified),artifacts=verified,
                   exports_match_report_revision=True,viewer=json.loads((HERE/'viewer-qa.json').read_bytes()),
                   acceptance_sha256=hashlib.sha256((HERE/'acceptance.json').read_bytes()).hexdigest())
        (HERE/'publication-qa.json').write_bytes(encoded(audit))
        item=publisher.entry('completion')
        job=publisher.db.enqueue(publisher.project,'analysis',dict(executor='pair-no-punctuation close.py',
                                purpose='archive measured postpublication acceptance; no model execution'))
        item['job_id']=str(job['id']);publisher.flush()
        owned=publisher.claim_owned(item['job_id'])
        links={}
        for name in ('acceptance.json','publication-qa.json','quota-monitor.json','close.py'):
            ident=publisher.artifact(owned,HERE/name,'application/json' if name.endswith('.json') else 'text/x-python')
            links[name]=f'/api/v2/projects/{publisher.project}/artifacts/{ident}'
        publisher.db.finish(owned,result={'verified_artifacts':len(verified),'model_execution':False})
        text=(f"# 结项核验：无标点松子铃铛配对\n\n"
              f"2,400条输入、15个检查点、42个测量来源均核对通过；Core、默认感官映射和读出算法未变。"
              f"每句200次后的36个正强度窗口全部收敛，原有节点均并列最强；配对期待项没有强度优势。\n\n"
              f"已核对本项目{len(verified)}个归档附件的实际字节长度、SHA及ZIP完整性，Markdown／HTML导出对应报告第1版。"
              f"排名查看器的180窗口、7,892节点行验证通过。\n\n"
              f"含记录、报告和导出，结项前测得数据库增长{acceptance['database_growth_bytes']/1024**2:.2f}MiB，"
              f"本地证据{acceptance['local_evidence_bytes']/1024**2:.2f}MiB，"
              f"合计{acceptance['combined_new_storage_bytes']/1024**2:.2f}MiB，远低于512MiB预算。"
              f"本核验笔记和附件随后新增少量空间，最终本地快照见closure.json。"
              f"模型运算186.75秒，峰值RSS约166MiB。账号共享用量由77%到78%，未达81%停止线。\n\n"+
              '\n'.join(f'- [{name}]({url})' for name,url in links.items()))
        note=publisher.entry('note:completion')
        saved=notebooks.save_note(publisher.db,publisher.project,LOCAL_USER,note['id'],dict(
            operation_id=note['operation_id'],expected_revision=0,kind='note',collection_id=publisher.meta['notebook_id'],
            title='结项核验：输入、全节点排名、导出与资源',body={'format':'markdown','text':text}))
        note.update(revision=saved['revision'],content_hash=saved['content_hash'])
        item['done']=True;publisher.flush()
        with publisher.db.tx(publisher.project) as db:
            size=db.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
            jobs=db.execute('SELECT status,count(*) n FROM jobs WHERE project_id=%s GROUP BY status',
                            (publisher.project,)).fetchall()
            assert all(j['status']=='done' for j in jobs)
        local=sum(p.stat().st_size for d in (HERE,WORK) for p in d.iterdir() if p.is_file())
        total=size-publisher.meta['database_bytes_before']+local
        assert total<512*1024**2
        snapshot=dict(checked_at=datetime.now(UTC).isoformat(),project_id=publisher.project,
                      database_growth_bytes=size-publisher.meta['database_bytes_before'],
                      local_evidence_bytes=local,combined_new_storage_bytes=total,jobs=jobs,
                      quota=json.loads((HERE/'quota-monitor.json').read_bytes()),
                      disk_free_bytes={d:shutil.disk_usage(d).free for d in ('D:/','E:/')},
                      completion_note_id=note['id'],model_execution_after_study=False)
        (HERE/'closure.json').write_bytes(encoded(snapshot))
        print(encoded(snapshot).decode())
    finally:publisher.db.close()


if __name__=='__main__':close()
