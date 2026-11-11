"""Verify new-study provenance and bounded representative raw bundles; never scan old payloads."""
import hashlib
import io
import json
import shutil
import zipfile
from datetime import datetime, UTC

from run import HERE, META, WORK, encoded, old_inventory
from threemind_lab import research_documents, notebooks
from threemind_lab.config import Settings
from threemind_lab.database import Database, LOCAL_USER
from threemind_runtime.codec import ArtifactCodec


def verify():
    meta = json.loads(META.read_bytes())
    project = meta['project_id']
    db = Database(Settings.from_env().database_url)
    try:
        assert old_inventory(db) == meta['old_inventory_before'], 'old model/document/note heads changed'
        with db.tx(project) as c:
            rows = c.execute('SELECT c.id,c.run_id,c.checkpoint_id,c.source_hash,c.protocol,j.status,j.result '
                             'FROM probe_calibrations c JOIN jobs j ON j.id=c.job_id '
                             'WHERE c.project_id=%s ORDER BY c.created_at,c.id',(project,)).fetchall()
            artifacts = c.execute('SELECT id,sha256,bytes,name FROM artifacts WHERE project_id=%s',(project,)).fetchall()
            runs = c.execute('SELECT id,revision,state_hash,status FROM runs WHERE project_id=%s ORDER BY id',(project,)).fetchall()
            jobs = c.execute('SELECT status,count(*) n FROM jobs WHERE project_id=%s GROUP BY status',(project,)).fetchall()
            physical = c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        assert all(r['status']=='completed' for r in runs)
        assert all(j['status']=='done' for j in jobs)
        by_id = {str(a['id']):a for a in artifacts}
        by_run = {str(r['id']):r for r in runs}
        for row in rows:
            assert row['source_hash'] == by_run[str(row['run_id'])]['state_hash']
            assert row['result']['source_hash']==row['source_hash']
            row['downloads']={}
            for key in ['artifact_id','bundle_artifact_id']:
                item=by_id[row['result'][key]]
                row['downloads'][key]={**item,'url':f"/api/v2/projects/{project}/artifacts/{item['id']}"}
        index = {'project_id':project,'calibrations':rows,'raw_scope':'All zero/nonzero node activity, actual input frames, '
                 'events, original source and each final model. Word masks affect only observer scoring.',
                 'phase_files':{key:{'file':file,'sha256':hashlib.sha256((WORK/file).read_bytes()).hexdigest()}
                                for key,file in meta['completed_phases'].items()}}
        (HERE/'evidence-index.json').write_bytes(encoded(index))
        # Fixed representatives: first/last birth, first weak-dose and first continuation.
        selected=[rows[0],rows[-1]]
        selected+=next(([r] for r in rows if min(r['protocol']['intensities'])<.1),[])
        selected+=next(([r] for r in rows if r['protocol']['route']=='continuation'),[])
        checked=[]
        for row in {str(r['id']):r for r in selected}.values():
            with db.tx(project) as c:
                chunks=c.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',
                                 (row['result']['bundle_artifact_id'],)).fetchall()
            raw=b''.join(bytes(x['body']) for x in chunks)
            assert hashlib.sha256(raw).hexdigest()==row['result']['bundle_sha256']
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                result=json.loads(archive.read('result.json'))
                image=ArtifactCodec.decode(archive.read('source.tmind'))
                assert image.digest==row['source_hash']
                for i,p in enumerate(result['rows']):
                    state=ArtifactCodec.decode(archive.read(f'probes/{i}/final.tmind'))
                    assert state.digest==p['final_hash']
                    trace=json.loads(archive.read(f'probes/{i}/trace.json'))
                    assert len(trace['all_node_activations'])==1+result['protocol']['window_us']//result['protocol']['sample_us']
                checked.append({'calibration_id':row['id'],'copies':len(result['rows']),'bundle_sha256':row['result']['bundle_sha256']})
        acceptance={'checked_at':datetime.now(UTC).isoformat(),'project_id':project,'parents':len(runs),
                    'calibration_jobs':len(rows),'job_status_counts':jobs,'old_inventory_unchanged':True,
                    'all_source_heads_unchanged':True,'representative_bundles':checked,
                    'database_growth_bytes':physical-meta['database_bytes_before'],
                    'local_evidence_bytes':sum(p.stat().st_size for folder in [HERE,WORK] for p in folder.iterdir() if p.is_file()),
                    'free_disk_bytes':{d:shutil.disk_usage(d).free for d in ['D:/','E:/']},
                    'core_changed':False,'calibration_passed':False}
        pub=meta.get('publication',{})
        if 'document:report' in pub:
            report=research_documents.render(db,project,pub['document:report']['id'])
            note=notebooks.note(db,project,LOCAL_USER,pub['note:results']['id'])
            acceptance.update(report_id=report['document_id'],report_hash=report['content_hash'],
                              report_blocks=len(report['blocks']),results_note_revision=note['revision'])
            name='acceptance.json'
        else:
            name='acceptance-prepublish.json'
        assert acceptance['database_growth_bytes']+acceptance['local_evidence_bytes']<4*1024**3
        (HERE/name).write_bytes(encoded(acceptance))
        print(encoded(acceptance).decode())
    finally:
        db.close()


if __name__=='__main__':
    verify()
