"""Check every delivered carrier against the frozen curriculum, not just counters."""
import hashlib
import io
import json
import shutil
import zipfile
from collections import Counter
from dataclasses import replace
from datetime import datetime, UTC

from run import HERE, WORK, META, SEEDS, SENSOR, GAP, inventory, curriculum, expand, encoded
from threemind_lab import research_documents, notebooks
from threemind_lab.config import Settings
from threemind_lab.database import Database, LOCAL_USER
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.sensory import TextSensor
from paired_control import swapped


def verify():
    meta = json.loads(META.read_bytes())
    for name, sha in meta['frozen_sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == sha
    project = meta['project_id']
    names=[f'seed-{s}' for s in SEEDS]+[f'pair-swap-{s}' for s in meta.get('pair_control',{}).get('seeds',[])]
    phases = [json.loads((WORK/meta['completed_phases'][name]).read_bytes()) for name in names]
    for name,sha in meta.get('pair_control',{}).get('frozen_sha256',{}).items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha
    anchors = [r for p in phases for r in p['rows']]
    db = Database(Settings.from_env().database_url)
    try:
        assert inventory(db) == meta['old_inventory_before'], 'old heads changed'
        with db.tx(project) as c:
            jobs = c.execute('SELECT status,count(*) n FROM jobs WHERE project_id=%s GROUP BY status', (project,)).fetchall()
            assert all(j['status'] == 'done' for j in jobs)
            runs = c.execute('SELECT id,revision,state_hash,status,spec FROM runs WHERE project_id=%s', (project,)).fetchall()
            calibrations = c.execute('SELECT p.id,p.run_id,p.checkpoint_id,p.source_hash,p.protocol,j.result '
                                    'FROM probe_calibrations p JOIN jobs j ON j.id=p.job_id '
                                    'WHERE p.project_id=%s ORDER BY p.created_at,p.id', (project,)).fetchall()
            size = c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        assert len(runs) == 8+len(meta.get('pair_control',{}).get('seeds',[])) and all(r['status'] == 'completed' for r in runs)
        common, normal, crossed = curriculum()
        by_run = {str(a['run_id']): a for a in anchors}
        audits = []
        for r in runs:
            anchor = by_run[str(r['id'])]
            expected = expand(crossed[len(common):]) if anchor['arm']=='crossed' else expand(normal)
            if anchor['arm']=='pair_swap':
                expected=[swapped(text) for text in expected]
            initial_count = 1070 if anchor['arm'] == 'crossed' else 0
            sensor = TextSensor(anchor['seed'], SENSOR)
            with db.tx(project) as c:
                rows = c.execute('SELECT e.payload,e.configuration,e.frame_count,e.status envelope_status,'
                                 'f.frame_index,f.stimulus,f.status frame_status,f.scheduled_time_us,f.delivered_time_us '
                                 'FROM input_envelopes e JOIN input_frames f ON f.envelope_id=e.id '
                                 'WHERE e.run_id=%s ORDER BY e.ordinal,f.frame_index', (r['id'],)).fetchall()
            assert len(rows) == len(expected)
            for i, (row, text) in enumerate(zip(rows, expected)):
                assert row['payload'] == {'text': text, 'intensity': 1}
                assert row['configuration']['adapter']['normalization'] == 'none'
                assert row['frame_count'] == 1 and row['frame_index'] == 0
                assert row['frame_status'] == 'delivered' and row['envelope_status'] == 'completed'
                at = (initial_count+i) * GAP
                assert int(row['scheduled_time_us']) == int(row['delivered_time_us']) == at
                frame = next(sensor.frames(text))
                stimulus = replace(frame['stimulus'], time_us=at).to_dict()
                assert row['stimulus'] == stimulus, 'recorded frame differs from exact original text encoding'
            cp, image = db.load_checkpoint(project, r['id'])
            assert image.digest == anchor['source_hash'] == r['state_hash']
            assert image.to_dict()['config'] == json.loads((HERE/'curriculum.json').read_bytes())['core']
            audits.append(dict(run_id=str(r['id']), seed=anchor['seed'], arm=anchor['arm'],
                               actual_frames=len(rows), every_literal_and_timestamp_verified=True,
                               counts=dict(Counter(expected)), final_hash=image.digest))
        checked_cp = {}
        for a in anchors:
            cp, image = db.load_checkpoint(project, a['run_id'], a['checkpoint_id'])
            assert image.digest == a['source_hash']
            checked_cp[a['checkpoint_id']] = image.digest
        for c in calibrations:
            assert c['source_hash'] == c['result']['source_hash'] == checked_cp[str(c['checkpoint_id'])]
            c['downloads'] = {k: f"/api/v2/projects/{project}/artifacts/{c['result'][k]}"
                              for k in ['artifact_id', 'bundle_artifact_id']}
        checked = []
        selections = [m['id'] for a in anchors if a['seed']==SEEDS[0] and a['stage']=='final'
                      for k,m in a['measurements'].items() if k.startswith('family/')]
        for c in calibrations:
            if str(c['id']) not in selections:
                continue
            with db.tx(project) as tx:
                chunks = tx.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',
                                    (c['result']['bundle_artifact_id'],)).fetchall()
            raw = b''.join(bytes(v['body']) for v in chunks)
            assert hashlib.sha256(raw).hexdigest() == c['result']['bundle_sha256']
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                result = json.loads(z.read('result.json'))
                assert ArtifactCodec.decode(z.read('source.tmind')).digest == c['source_hash']
                for i, row in enumerate(result['rows']):
                    assert ArtifactCodec.decode(z.read(f'probes/{i}/final.tmind')).digest == row['final_hash']
                    trace = json.loads(z.read(f'probes/{i}/trace.json'))
                    assert len(trace['all_node_activations']) == 51
                checked.append(dict(id=str(c['id']), copies=len(result['rows']),
                                    bundle_sha256=c['result']['bundle_sha256']))
        (HERE/'evidence-index.json').write_bytes(encoded(dict(project_id=project, checkpoints=checked_cp,
                                                            measurements=calibrations, input_audits=audits)))
        acceptance = dict(checked_at=datetime.now(UTC).isoformat(), project_id=project,
                          exact_training_frames=sum(a['actual_frames'] for a in audits), source_runs=len(runs),
                          checkpoint_hashes_verified=len(checked_cp), measurement_source_hashes_verified=len(calibrations),
                          all_original_text_and_punctuation_verified=True, all_repetition_counts_verified=True,
                          all_input_frames_delivered=True, old_inventory_unchanged=True,
                          old_model_count=sum(p['runs']['count'] for p in meta['old_inventory_before'].values()),
                          source_config_unchanged=True, core_changed=False, representative_bundles=checked,
                          database_growth_bytes=size-meta['database_bytes_before'], job_status_counts=jobs,
                          local_evidence_bytes=sum(p.stat().st_size for d in [HERE, WORK] for p in d.iterdir() if p.is_file()),
                          free_disk_bytes={d:shutil.disk_usage(d).free for d in ['D:/','E:/']})
        assert acceptance['database_growth_bytes']+acceptance['local_evidence_bytes'] < 4*1024**3
        pub = meta.get('publication', {})
        if 'document:report' in pub:
            report = research_documents.render(db, project, pub['document:report']['id'])
            note = notebooks.note(db, project, LOCAL_USER, pub['note:results']['id'])
            acceptance.update(report_id=report['document_id'], report_hash=report['content_hash'],
                              report_blocks=len(report['blocks']), results_note_revision=note['revision'])
            filename = 'acceptance.json'
        else:
            filename = 'acceptance-prepublish.json'
        (HERE/filename).write_bytes(encoded(acceptance))
        print(encoded(acceptance).decode())
    finally:
        db.close()


if __name__ == '__main__':
    verify()
