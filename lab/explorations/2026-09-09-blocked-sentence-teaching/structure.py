"""Read saved birth timestamps to distinguish persistence from reconnection."""
import json
import statistics

from run import HERE, WORK, META, SEEDS, encoded
from threemind_lab.config import Settings
from threemind_lab.database import Database


def inspect():
    meta = json.loads(META.read_bytes())
    db = Database(Settings.from_env().database_url)
    rows = []
    try:
        for seed in SEEDS:
            data = json.loads((WORK/meta['completed_phases'][f'seed-{seed}']).read_bytes())
            anchors = [a for a in data['rows'] if a['arm']=='normal']
            first = next(a for a in anchors if a['count']==20)
            _, image = db.load_checkpoint(meta['project_id'], first['run_id'], first['checkpoint_id'])
            original = {(e['source'], e['target']): e['birth_us'] for e in image.to_dict()['edges']}
            for anchor in anchors:
                _, image = db.load_checkpoint(meta['project_id'], anchor['run_id'], anchor['checkpoint_id'])
                state = image.to_dict()
                current = {(e['source'],e['target']):e for e in state['edges']}
                same = [current[k] for k,born in original.items() if k in current and current[k]['birth_us']==born]
                recreated = [current[k] for k,born in original.items() if k in current and current[k]['birth_us']!=born]
                rows.append(dict(seed=seed, stage=anchor['stage'], count=anchor['count'], source_hash=image.digest,
                                 original_edges=len(original), same_birth_edges=len(same),
                                 recreated_endpoint_edges=len(recreated), missing_endpoints=len(original)-len(same)-len(recreated),
                                 same_birth_mean_weight=statistics.mean(e['weight'] for e in same) if same else None,
                                 total_nodes=len(state['nodes']), total_edges=len(state['edges']),
                                 edges_at_weight_one=sum(e['weight']>=1-1e-12 for e in state['edges']),
                                 max_weight=max(e['weight'] for e in state['edges'])))
    finally:
        db.close()
    result = dict(method='source,target,birth_us identity of edges present after first 20 inputs',
                  reason='Endpoint pairs alone can include an edge deleted and later recreated. '
                         'This read-only diagnostic was added after noticing counts could increase again; '
                         'it does not alter training or replace preregistered probe scores.', rows=rows)
    (HERE/'edge-continuity.json').write_bytes(encoded(result))
    print(encoded([r for r in rows if r['count'] in [20,40,200,600,1310]]).decode())


if __name__=='__main__':
    inspect()
