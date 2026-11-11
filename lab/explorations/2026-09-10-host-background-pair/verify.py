"""Read-only audit of actual frames, full inherited backgrounds, and source state."""
import hashlib
import io
import json
import zipfile
from collections import Counter
from dataclasses import asdict,replace
from datetime import datetime,UTC

from run import HERE,ROOT,WORK,META,Database,Settings,TextSensor,SENSOR,encoded,sha,background,curriculum,inventory,capture_implementation


def verify():
    meta=json.loads(META.read_bytes());data=json.loads((HERE/'analysis.json').read_bytes())
    for name,value in meta['frozen_sha256'].items():assert sha(HERE/name)==value
    recorded=json.loads((HERE/'implementation.json').read_bytes());now=capture_implementation('native')
    for key in ('source_sha256','native_binary_sha256'):assert now[key]==recorded[key]
    with zipfile.ZipFile(HERE/'implementation-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name,value in recorded['source_files'].items():
            assert sha(ROOT/name)==value;archive.write(ROOT/name,name)
    db=Database(Settings.from_env().database_url);audits=[];probe_audits=[]
    try:
        assert inventory(db)==meta['old_inventory_before']
        with db.tx(meta['project_id']) as c:
            runs=c.execute('SELECT id,spec,state_hash FROM runs WHERE project_id=%s',(meta['project_id'],)).fetchall()
        for run in runs:
            stages=[s for s in data['stages'] if s['run_id']==str(run['id'])];s=max(stages,key=lambda s:s['count'])
            sensor=TextSensor(s['seed'],SENSOR)
            assert run['spec']['config']==json.loads((HERE/'preflight.json').read_bytes())['core']
            assert run['spec']['config']['inhibition'] and run['spec']['config']['plasticity']
            assert run['spec']['text_sensor']==asdict(SENSOR)
            bg=background(s['seed']) if s['arm']=='host' else []
            expected_bg={str(r['stimulus'].time_us):r['stimulus'].to_dict() for r in bg if r['stimulus']}
            with db.tx(meta['project_id']) as c:
                frames=c.execute('SELECT e.adapter_id,e.payload,f.stimulus,f.scheduled_time_us,f.delivered_time_us,f.status '
                  'FROM input_envelopes e JOIN input_frames f ON f.envelope_id=e.id WHERE e.run_id=%s ORDER BY e.ordinal,f.frame_index',
                  (run['id'],)).fetchall()
            texts=[f for f in frames if f['adapter_id']=='text-sensor']
            hosts=[f for f in frames if f['adapter_id']=='host-telemetry']
            assert len(texts)==s['count'] and len(hosts)==len(expected_bg)
            for i,f in enumerate(texts):
                text=curriculum()[i];assert f['payload']=={'text':text,'intensity':.9}
                expected=replace(next(sensor.frames(text,.9))['stimulus'],time_us=i*10_000_000).to_dict()
                assert f['stimulus']==expected and int(f['delivered_time_us'])==i*10_000_000
            for f in hosts:
                assert f['stimulus']==expected_bg[str(f['scheduled_time_us'])]
                if f['status']=='delivered':assert f['delivered_time_us']==f['scheduled_time_us']
            for stage in stages:
                _,image=db.load_checkpoint(meta['project_id'],run['id'],stage['checkpoint_id'])
                assert image.digest==stage['source_hash']
            assert run['state_hash']==s['source_hash']
            nodes=image.to_dict()['nodes'];host_channels={c for r in bg if r['stimulus'] for c,_ in r['stimulus'].channels}
            ids={n['id']:('host' if n['channel'] in host_channels else 'text') for n in nodes}
            edges=Counter(ids[e['source']]+'→'+ids[e['target']] for e in image.to_dict()['edges'])
            audits.append(dict(seed=s['seed'],arm=s['arm'],run_id=str(run['id']),text_inputs=len(texts),
                host_frames=len(hosts),host_delivered=sum(f['status']=='delivered' for f in hosts),
                host_pending=sum(f['status']!='delivered' for f in hosts),life=s['metrics']['life'],time_us=s['metrics']['time_us'],
                active_nodes=sum(n['activation']>0 for n in nodes),
                active_host_nodes=sum(n['activation']>0 and n['channel'] in host_channels for n in nodes),edges_by_origin=dict(edges)))
        for result_file in sorted(WORK.glob('seed-*-results.json')):
            study=json.loads(result_file.read_bytes());assert study['error'] is None
            for stage in study['rows']:
                for measurement in stage['measurements'].values():
                    result=json.loads((WORK/measurement['file']).read_bytes())
                    assert result['source_hash']==stage['source_hash'] and result['source_unchanged']
                    assert result['sensor_config']==asdict(SENSOR)
                    if measurement['mode']!='temporal':continue
                    with db.tx(meta['project_id']) as c:
                        chunks=c.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',
                                         (measurement['artifacts']['bundle_artifact_id'],)).fetchall()
                    raw=b''.join(bytes(p['body']) for p in chunks)
                    assert hashlib.sha256(raw).hexdigest()==measurement['artifacts']['bundle_sha256']
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        for i,row in enumerate(result['rows']):
                            assert row['context_inherited'] and row['learning_during_probe'] and row['temporal']
                            delivered=json.loads(archive.read(f'probes/{i}/deliveries.json'))
                            host=[r for r in delivered if r.get('source')=='host-telemetry']
                            if stage['stage']!='untrained':assert host,'background lost during trained probe'
                            probe_audits.append(dict(seed=stage['seed'],stage=stage['stage'],cue=row['cue'],
                                intensity=row['intensity'],background_deliveries=len(host),window_id=row['temporal']['window_id']))
        with db.tx(meta['project_id']) as c:
            size=c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
            jobs=c.execute('SELECT status,count(*) n FROM jobs WHERE project_id=%s GROUP BY status',(meta['project_id'],)).fetchall()
        assert all(j['status']=='done' for j in jobs)
        local=sum(p.stat().st_size for d in (HERE,WORK) for p in d.iterdir() if p.is_file())
        assert size-meta['database_bytes_before']+local<256*1024**2
        assert len(probe_audits)==72 and sum(a['text_inputs'] for a in audits)==82
        result=dict(checked_at=datetime.now(UTC).isoformat(),project_id=meta['project_id'],runs=audits,probes=probe_audits,
            exact_frame_contents_and_times_verified=True,checkpoints_verified=len(data['stages']),
            source_and_original_experiments_unchanged=True,trained_probes_with_background=48,
            database_growth_bytes=size-meta['database_bytes_before'],local_evidence_bytes=local,
            combined_new_storage_bytes=size-meta['database_bytes_before']+local,jobs=jobs,
            model_seconds=sum(r['elapsed_s'] for r in data['resources']),peak_rss=max(r['peak_rss'] for r in data['resources']))
        (HERE/'acceptance.json').write_bytes(encoded(result))
        print(encoded({k:v for k,v in result.items() if k!='probes'}).decode())
        return result
    finally:db.close()


if __name__=='__main__':verify()
