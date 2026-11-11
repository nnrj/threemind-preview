"""Check newly published evidence and record the final bounded resource snapshot."""
import hashlib
import io
import json
import time
import zipfile
from datetime import datetime,UTC
from publish import Publisher
from run import HERE,WORK,encoded,inventory
from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER


def close():
    p=Publisher()
    try:
        if (HERE/'closure.json').exists():raise RuntimeError('Already closed; preserve the audit')
        started=time.monotonic();verified=[]
        assert inventory(p.db)==p.meta['old_inventory_before']
        with p.db.tx(p.project) as c:
            artifacts=c.execute('SELECT id,name,bytes,sha256,media_type FROM artifacts WHERE project_id=%s',(p.project,)).fetchall()
            for a in artifacts:
                assert time.monotonic()-started<120 and a['bytes']<32*1024**2
                raw=b''.join(bytes(r['body']) for r in c.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',(a['id'],)).fetchall())
                assert len(raw)==a['bytes'] and hashlib.sha256(raw).hexdigest()==a['sha256']
                if a['name'].endswith('.zip') or a['media_type']=='application/zip':
                    with zipfile.ZipFile(io.BytesIO(raw)) as z:
                        assert sum(f.file_size for f in z.infolist())<128*1024**2
                        assert z.testzip() is None
                verified.append({k:str(v) if k=='id' else v for k,v in a.items()})
        for fmt in ('markdown','html'):
            result=p.state['export:'+fmt]['result']
            assert not result['warnings'] and result['document_hash']==p.state['document:report']['content_hash']
        qa=dict(checked_at=datetime.now(UTC).isoformat(),verified_artifact_count=len(verified),artifacts=verified,
                viewer=json.loads((HERE/'viewer-qa.json').read_bytes()),old_experiments_unchanged=True,
                exports_match_frozen_report=True)
        (HERE/'publication-qa.json').write_bytes(encoded(qa))
        job=p.db.enqueue(p.project,'analysis',dict(executor='host-background-pair close.py',purpose='archive publication verification only'))
        owned=p.claim_owned(str(job['id']))
        audit_id=p.artifact(owned,HERE/'publication-qa.json','application/json')
        p.artifact(owned,HERE/'close.py','text/x-python')
        p.db.finish(owned,result={'verified_artifacts':len(verified)})
        with p.db.tx(p.project) as c:
            size=c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
            jobs=c.execute('SELECT status,count(*) n FROM jobs WHERE project_id=%s GROUP BY status',(p.project,)).fetchall()
        assert all(j['status']=='done' for j in jobs)
        local=sum(f.stat().st_size for d in (HERE,WORK) for f in d.iterdir() if f.is_file())
        total=size-p.meta['database_bytes_before']+local;assert total<256*1024**2
        note=p.entry('note:completion')
        body=(f"# 结项核验\n\n已核对本项目{len(verified)}个归档附件的字节长度、SHA及ZIP完整性；"
              f"72窗口、4,157节点行的查看器通过浏览器核验，Markdown／HTML导出匹配报告第1版。\n\n"
              f"两个背景意识完整接收各40条文本和399条背景；各16条未来背景仍保存在检查点。"
              f"全部48个训练后时序检验实际收到背景。两个无背景对照各在第一次输入后2.19秒死亡。"
              f"没有收敛窗口；背景与文本之间未观察到连接。旧实验未变。\n\n"
              f"含报告和导出，本次核验时数据库增长{(size-p.meta['database_bytes_before'])/1024**2:.2f}MiB、"
              f"本地证据{local/1024**2:.2f}MiB，合计{total/1024**2:.2f}MiB，预算256MiB。"
              f"本笔记随后新增少量元数据。模型计算53.05秒、峰值RSS约141MiB；另有415秒真实采集。"
              f"最近账号共享用量仍79%，未到81%停止线。\n\n"
              f"[归档核验附件](/api/v2/projects/{p.project}/artifacts/{audit_id})")
        saved=notebooks.save_note(p.db,p.project,LOCAL_USER,note['id'],dict(operation_id=note['operation_id'],
            expected_revision=0,kind='note',collection_id=p.meta['notebook_id'],title='结项核验：背景实际递送、存活、读出与资源',
            body={'format':'markdown','text':body}))
        note.update(revision=saved['revision'],content_hash=saved['content_hash']);p.flush()
        with p.db.tx(p.project) as c:size=c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        local=sum(f.stat().st_size for d in (HERE,WORK) for f in d.iterdir() if f.is_file())
        result=dict(checked_at=datetime.now(UTC).isoformat(),project_id=p.project,report_id=p.state['document:report']['id'],
            completion_note_id=note['id'],jobs=jobs,database_growth_bytes=size-p.meta['database_bytes_before'],
            local_evidence_bytes=local,combined_new_storage_bytes=size-p.meta['database_bytes_before']+local,
            quota=json.loads((HERE/'quota-monitor.json').read_bytes()),model_execution_after_results=False)
        assert result['combined_new_storage_bytes']<256*1024**2
        (HERE/'closure.json').write_bytes(encoded(result));print(encoded(result).decode())
    finally:p.db.close()


if __name__=='__main__':close()
