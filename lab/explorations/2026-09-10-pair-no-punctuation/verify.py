"""Audit actual DB carriers, frame bytes, checkpoints and inherited probe state."""
import importlib.util
import json
from run import HERE,ROOT,WORK,META,sha,encoded,Database,Settings

path=HERE.parent/'2026-09-10-temporal-repetition/verify.py'
loader=importlib.util.spec_from_file_location('prior_temporal_verification',path)
base=importlib.util.module_from_spec(loader);loader.loader.exec_module(base)


def verify():
    result=base.verify()
    meta=json.loads(META.read_bytes())
    dependencies=json.loads((HERE/'preflight.json').read_bytes())['instrumentation_dependencies']
    assert all(sha(ROOT/name)==value for name,value in dependencies.items())
    assert result['completed_seeds']==[41701,41702,41703] and not result['errors']
    assert result['source_runs']==6 and result['exact_training_inputs']==2400
    assert result['checkpoint_hashes_verified']==15
    assert result['measurement_copies']==264  # 180 temporal; 72 fixed cues/doses + 12 built-in baselines.
    assert result['cumulative_training_probe_seconds']<600
    assert result['peak_rss']<1024**3
    combined=result['database_growth_bytes']+result['local_evidence_bytes']
    assert combined<512*1024**2
    cases=json.loads((HERE/'analysis.json').read_bytes())['cases']
    assert len(cases)==180 and sum(c['dose']==1 for c in cases)==90
    assert set(c['cue'] for c in cases)=={'甲是','乙是','甲','乙','松子','铃铛'}
    data=json.loads((HERE/'analysis.json').read_bytes())
    source_ids={}
    db=Database(Settings.from_env().database_url)
    try:
        for s in data['stages']:
            if s['stage']=='each200':
                _,state=db.load_checkpoint(meta['project_id'],s['run_id'],s['checkpoint_id'])
                source_ids[(s['seed'],s['arm'])]={n['id'] for n in state.to_dict()['nodes']}
    finally:db.close()
    original_ties=0
    with (HERE/'node-rankings.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line)
            if r['stage']=='each200' and r['dose']==1:
                strongest={n['node_id'] for n in r['rankings']['end_activation'] if n['rank']==1}
                assert strongest==source_ids[r['seed'],r['arm']]
                original_ties+=1
    assert original_ties==36
    result.update(combined_new_storage_bytes=combined,temporal_windows=180,explicit_fixed_copies=72,
                  fixed_no_input_baselines=12,per_sentence_repetitions=200,training_order_arms=['AB','BA'],
                  all_original_nodes_tied_strongest_verified=original_ties,
                  quota=json.loads((HERE/'quota-monitor.json').read_bytes()),
                  verification_dependency={path.relative_to(ROOT).as_posix():sha(path)})
    target='acceptance.json' if 'document:report' in meta.get('publication',{}) else 'acceptance-prepublish.json'
    (HERE/target).write_bytes(encoded(result))
    print('Additional exact counts, scope, source and budget checks passed.')
    return result


if __name__=='__main__':verify()
