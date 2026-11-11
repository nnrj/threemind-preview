"""All-channel diagnostic on existing raw ZIPs; no re-simulation or word mask."""
import io
import json
import zipfile

from run import HERE, WORK, META, SEEDS, encoded
from threemind_lab.config import Settings
from threemind_lab.database import Database


def inspect():
    meta=json.loads(META.read_bytes())
    db=Database(Settings.from_env().database_url)
    output=[]
    try:
        for seed in SEEDS:
            phase=json.loads((WORK/meta['completed_phases'][f'seed-{seed}']).read_bytes())
            source=next(a for a in phase['rows'] if a['stage']=='final' and a['arm']=='normal')
            measurement=source['measurements']['family/continuation']
            with db.tx(meta['project_id']) as tx:
                parts=tx.execute('SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal',
                                 (measurement['artifacts']['bundle_artifact_id'],)).fetchall()
            with zipfile.ZipFile(io.BytesIO(b''.join(bytes(p['body']) for p in parts))) as z:
                result=json.loads(z.read('result.json'))
                sham=json.loads(z.read('probes/0/trace.json'))
                def channels(trace, sample):
                    return {trace['node_channels'][str(i)]:v for i,v in sample[1]}
                for i,row in enumerate(result['rows'][1:],1):
                    trace=json.loads(z.read(f'probes/{i}/trace.json'))
                    samples=[]
                    for index,(p,b) in enumerate(zip(trace['all_node_activations'],sham['all_node_activations'])):
                        pa,ba=channels(trace,p),channels(sham,b)
                        differences=[abs(pa.get(k,0)-ba.get(k,0)) for k in set(pa)|set(ba)]
                        samples.append(dict(offset_us=index*20000, l1=sum(differences),
                                            maximum=max(differences), changed_channels=sum(d>1e-12 for d in differences)))
                    output.append(dict(seed=seed,cue=row['cue'],source_hash=source['source_hash'],samples=samples,
                                       max_l1=max(p['l1'] for p in samples),
                                       last_changed_sample_us=max((p['offset_us'] for p in samples if p['changed_channels']),default=None)))
    finally:
        db.close()
    (HERE/'raw-activity-differences.json').write_bytes(encoded(dict(
        scope='Existing primary final family probes only; all anonymous channels, no word-scoring mask.',
        limitation='20 ms samples can miss between-sample changes; activation is not the full dynamical state.',
        motivation='Post hoc diagnostic of zero word-projection differences, not a new confirmatory endpoint.',rows=output)))
    print(encoded([{k:r[k] for k in ['seed','cue','max_l1','last_changed_sample_us']} for r in output]).decode())


if __name__=='__main__':
    inspect()
