"""Audit the actual stored inputs, sources, measurements and published documents."""
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from dataclasses import asdict,replace
from datetime import datetime,UTC

from run import (HERE,WORK,ROOT,META,SEEDS,SENSOR,GAP,Database,Settings,encoded,sha,
                 curriculum,inventory,TextSensor,capture_implementation)
from threemind_lab import notebooks,research_documents
from threemind_lab.database import LOCAL_USER

def expand(blocks):
    return [b['text'] for b in blocks for _ in range(b['repetitions'])]

def verify():
    meta=json.loads(META.read_bytes())
    impl=json.loads((HERE/'implementation.json').read_bytes())
    now=capture_implementation('native')
    for key in ['source_sha256','native_binary_sha256']:assert now[key]==impl[key]
    for name,h in meta['frozen_sha256'].items():assert sha(HERE/name)==h
    archive=HERE/'implementation-source.zip'
    if not archive.exists():
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
            for name,h in impl['source_files'].items():
                assert sha(ROOT/name)==h
                z.write(ROOT/name,name)
    with zipfile.ZipFile(archive) as z:
        for name,h in impl['source_files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==h
    studies=[json.loads(p.read_bytes()) for p in sorted(WORK.glob('seed-*-results.json'))]
    stages=[s for study in studies for s in study['rows']]
    anchors={s['run_id']:s for s in stages}
    db=Database(Settings.from_env().database_url)
    try:
        assert inventory(db)==meta['old_inventory_before']
        audits=[]
        with db.tx(meta['project_id']) as c:
            runs=c.execute('SELECT id,state_hash,spec,revision FROM runs WHERE project_id=%s ORDER BY id',(meta['project_id'],)).fetchall()
            jobs=c.execute('SELECT status,count(*) n FROM jobs WHERE project_id=%s GROUP BY status',(meta['project_id'],)).fetchall()
            readouts=c.execute("SELECT count(*) n FROM events WHERE project_id=%s AND kind='temporal_readout'",(meta['project_id'],)).fetchone()['n']
            measurements=c.execute('SELECT c.id,c.run_id,c.checkpoint_id,c.source_hash,c.protocol,j.status,j.result FROM probe_calibrations c JOIN jobs j ON j.id=c.job_id WHERE c.project_id=%s ORDER BY c.id',(meta['project_id'],)).fetchall()
            physical=c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        assert all(j['status']=='done' for j in jobs),jobs
        course=curriculum()
        for run in runs:
            anchor=anchors[str(run['id'])]
            arm=anchor['arm']
            expected=expand(course[arm])
            offset=1070 if arm=='crossed' else 0
            expected=expected[offset:anchor['count']]
            sensor=TextSensor(anchor['seed'],SENSOR)
            with db.tx(meta['project_id']) as c:
                frames=c.execute('SELECT e.payload,e.configuration,e.frame_count,e.status envelope_status,'
                  'f.frame_index,f.stimulus,f.status frame_status,f.scheduled_time_us,f.delivered_time_us '
                  'FROM input_envelopes e JOIN input_frames f ON f.envelope_id=e.id WHERE e.run_id=%s '
                  'ORDER BY e.ordinal,f.frame_index',(run['id'],)).fetchall()
            assert len(frames)==len(expected)
            for i,(row,text) in enumerate(zip(frames,expected)):
                assert row['payload']=={'text':text,'intensity':1}
                assert row['configuration']['adapter']==asdict(SENSOR)
                assert row['configuration']['transduction']==sensor.describe(text)
                assert row['frame_count']==1 and row['frame_index']==0
                assert row['envelope_status']=='completed' and row['frame_status']=='delivered'
                at=(offset+i)*GAP
                assert int(row['scheduled_time_us'])==int(row['delivered_time_us'])==at
                assert row['stimulus']==replace(next(sensor.frames(text))['stimulus'],time_us=at).to_dict()
            _,image=db.load_checkpoint(meta['project_id'],run['id'])
            assert image.digest==anchor['source_hash']==run['state_hash']
            assert image.to_dict()['config']==json.loads((HERE/'preflight.json').read_bytes())['core']
            assert run['spec']['text_sensor']==asdict(SENSOR)
            audits.append(dict(run_id=str(run['id']),seed=anchor['seed'],arm=arm,actual_inputs=len(frames),
                               sentence_counts=dict(Counter(expected)),hash=image.digest))
        checkpoints={s['checkpoint_id']:s['source_hash'] for s in stages}
        for s in stages:
            cp=db.checkpoint_identity(meta['project_id'],s['run_id'],s['checkpoint_id'])
            assert cp['state_hash']==s['source_hash']
        cases=0
        for m in measurements:
            assert m['status']=='done' and m['source_hash']==checkpoints[str(m['checkpoint_id'])]
            local=WORK/f"calibration-{m['id']}.json"
            data=json.loads(local.read_bytes())
            assert data['source_hash']==m['source_hash'] and data['source_unchanged']
            assert data['sensor_config']==asdict(SENSOR)
            cases+=len(data['rows'])
            if data['schema']=='threemind.temporal-probe/1':
                assert data['protocol']['route']=='continuation' and data['protocol']['blank_us']==0
                assert all(r.get('context_inherited') and r.get('learning_during_probe') for r in data['rows'])
                assert all(r.get('temporal') is not None for r in data['rows'])
            m['downloads']={k:f"/api/v2/projects/{meta['project_id']}/artifacts/{m['result'][k]}" for k in ['artifact_id','bundle_artifact_id']}
        result=dict(checked_at=datetime.now(UTC).isoformat(),project_id=meta['project_id'],source_runs=len(runs),
          completed_seeds=[s['seed'] for s in studies if not s['error']],errors=[s['error'] for s in studies if s['error']],
          exact_training_inputs=sum(a['actual_inputs'] for a in audits),training_temporal_windows=readouts,
          checkpoint_hashes_verified=len(checkpoints),measurement_source_hashes_verified=len(measurements),
          measurement_copies=cases,all_original_carriers_and_frames_verified=True,all_repetition_counts_verified=True,
          old_project_metadata_unchanged=True,core_and_sensor_and_reader_source_unchanged=True,
          source_archive_files_verified=len(impl['source_files']),database_growth_bytes=physical-meta['database_bytes_before'],
          local_evidence_bytes=sum(p.stat().st_size for d in [WORK,HERE] for p in d.iterdir() if p.is_file()),
          cumulative_training_probe_seconds=sum(s['elapsed_s'] for s in studies),peak_rss=max(s['peak_rss'] for s in studies),
          disk_free_bytes={d:shutil.disk_usage(d).free for d in ['D:/','E:/']},jobs=jobs)
        assert result['database_growth_bytes']+result['local_evidence_bytes']<4*1024**3
        assert result['cumulative_training_probe_seconds']<1800
        publication=meta.get('publication',{})
        if 'document:report' in publication:
            report=research_documents.render(db,meta['project_id'],publication['document:report']['id'])
            note=notebooks.note(db,meta['project_id'],LOCAL_USER,publication['note:results']['id'])
            result.update(report_id=str(report['document_id']),report_content_hash=report['content_hash'],
                          report_blocks=len(report['blocks']),results_note_revision=note['revision'])
            target='acceptance.json'
        else:target='acceptance-prepublish.json'
        (HERE/'evidence-index.json').write_bytes(encoded(dict(project_id=meta['project_id'],input_audits=audits,
                                          checkpoints=checkpoints,calibrations=measurements)))
        (HERE/target).write_bytes(encoded(result))
        print(encoded(result).decode())
        return result
    finally:db.close()

if __name__=='__main__':verify()
