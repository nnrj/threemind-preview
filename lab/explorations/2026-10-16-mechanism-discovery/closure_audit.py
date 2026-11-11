"""Independent original-file checks; no ThreeMind engine is created or advanced."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

import closure_rig as g
import numpy as np
import pilot_m2 as m
from pilot_m3 import Controller


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def probe_check(whole, result):
    rows=[r for r in whole['rows'] if result['start_us'] < r['time_us'] <= result['start_us']+1_500_000]
    assert len(rows)==1500
    assert result['final_sha256']==m.digest(whole)
    assert result['first']==next(r['response'] for r in rows if r['time_us']==result['start_us']+110_000)
    for lo,hi,key in [(100_000,300_000,'early_integral'),(500_000,1_500_000,'late_integral')]:
        total=sum(r['response']*.001 for r in rows if lo<=r['time_us']-result['start_us']<=hi)
        assert abs(total-result[key])<=1e-15


def replay_rnn(parent):
    """Offline arithmetic replay of an existing baseline's public inputs, not a new scientific source."""
    state=copy.deepcopy(parent['model'])
    for k in ('h','w','memory','W'):state[k]=np.zeros_like(state[k]).tolist()
    state['P']=(np.eye(64)*1000).tolist();state['y']=0.;state['updates']=0
    model=Controller('fixed-rnn-reader',parent['seed'],state['a'],state['b'],state)
    events={}
    for e in parent['inputs']:
        values=events.setdefault(e['time_us'],{})
        for s,v in e['values'].items():values[s]=values.get(s,0.)+v
    ordered=sorted(parent['mappings'].values());records=[]
    for t in range(0,parent['time_us']+1,50_000):
        values=events.get(t,{})
        x=np.zeros(8)
        for s,v in values.items():x[ordered.index(parent['mappings'][s])]+=v
        model.step(x)
        if 1_000_000<=t<=17_000_000:
            records.append({'h':model.h.tolist(),'target':'X' in values or 'Y' in values})
    assert model.save()==parent['model']
    # Only a small view is needed by the purely numerical selection function.
    view=type('SavedModelView',(),{'model':model})()
    return g.rnn_selection(view,records)


def audit(work):
    m.frozen_check(work)
    counts={'X1_trials':0,'X2_probes':0,'X3_probes':0,'RNN_teaching_replays':0,'X1_fast_zero_change':0,
            'X1_bundle_only_endpoints':0,'X3_loop_pairs':0}
    for folder in sorted((work/'units').iterdir()):
        r=m.read(folder/'result.json')
        if r['package']=='X1':
            for t in r['trials']:
                p=folder/t['checkpoint']['path']
                assert hashlib.sha256(p.read_bytes()).hexdigest()==t['checkpoint']['sha256']
                whole=load(p);probe_check(whole,t['result'])
                row=next(v for v in whole['rows'] if v['time_us']==t['result']['start_us']+110_000)
                assert row['body']['gate']==t['result']['choice']
                assert t['success']==(t['result']['choice']==t['goal'])
                counts['X1_trials']+=1
            for h in (0,1):
                receipt=m.read(folder/f'h{h}-fast-intervention.json')
                counts['X1_fast_zero_change']+=not receipt['changed_paths']
                receipt=m.read(folder/f'h{h}-target-bundle-intervention.json')
                counts['X1_bundle_only_endpoints']+=all(
                    {k:v for k,v in old.items() if k!='target'}=={k:v for k,v in new.items() if k!='target'}
                    for old,new in zip(receipt['removed'],receipt['inserted']))
        elif r['package']=='X2':
            for h in r['histories']:
                for name,result in h['tests'].items():
                    whole=load(folder/result['checkpoint']['path']);probe_check(whole,result);counts['X2_probes']+=1
                for role,suffix in [('relearning','relearning'),('untrained','naive-relearning')]:
                    final=load(folder/f'h{h["history"]}-{suffix}-final.json.gz')
                    for lesson in h[role]['lessons']:
                        result=lesson['result'];end=result['start_us']+1_500_000
                        rows=[v for v in final['rows'] if result['start_us']<v['time_us']<=end]
                        assert len(rows)==1500
                        assert result['first']==next(v['response'] for v in rows if v['time_us']==result['start_us']+110_000)
        else:
            for h in r['histories']:
                for name,result in h['cells'].items():
                    probe_check(load(folder/f'h{h["history"]}-{name}-final.json.gz'),result);counts['X3_probes']+=1
                for name,result in h['temporal'].items():
                    probe_check(load(folder/f'h{h["history"]}-temporal-{name}.json.gz'),result);counts['X3_probes']+=1
                if r['kind']=='fixed-rnn-reader':
                    selected=replay_rnn(load(folder/f'h{h["history"]}-parent.json.gz'))
                    assert selected==h['selection'];counts['RNN_teaching_replays']+=1
            for seq,stages in r['worlds'].items():
                for j,stage in enumerate(stages,1):
                    for cue,result in stage['diagnostics'].items():
                        probe_check(load(folder/f'{seq}-stage{j}-diagnostic-{cue}.json.gz'),result);counts['X3_probes']+=1
                live=load(folder/f'{seq}-stage2.json.gz')
                replay=load(folder/f'{seq}-stage2-replay.json.gz')
                reversed_replay=load(folder/f'{seq}-stage2-replay-reversed.json.gz')
                assert live['model']==replay['model']==reversed_replay['model']
                counts['X3_loop_pairs']+=1
    report={'schema':'threemind.goal-closure-independent-file-audit/1','passed':True,'counts':counts,
            'Core_engines_loaded':0,'baseline_replay_is_instrument_verification':True}
    m.original(work/'audit-v1.json',report)
    print(json.dumps(report))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    audit(p.parse_args().work)
