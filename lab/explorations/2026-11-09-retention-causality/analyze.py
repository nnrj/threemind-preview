"""Evidence and registered-score audit; no restoration or subject advancement."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import random
import statistics
import study as e

spec=importlib.util.spec_from_file_location('r43_readonly_analysis',e.R43/'analyze.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)

def mean(v):return sum(v)/len(v)
def joint(r):return all(r['first']['predictions'][k]==r['case']['expected'] for k in e.old.PORTS)
def counts(rows):
    groups={kind:[r for r in rows if r['case']['kind']==kind] for kind in ('old','clear','ambiguous')}
    out={k:dict(correct=sum(joint(r) for r in rs),n=len(rs)) for k,rs in groups.items() if k!='ambiguous'}
    mixed=groups['ambiguous'];conf=[r for r in groups['clear'] if r['case']['conflict']]
    out['view']=dict(correct=sum(r['first']['predictions']['action']==2 for r in mixed),n=len(mixed))
    out['exit']=dict(correct=sum(r['second']['predictions']['action']==r['case']['actual'] for r in mixed),n=len(mixed))
    out['revision']=dict(correct=sum(all(r['second']['predictions'][k]==r['case']['actual'] for k in e.old.PORTS) for r in conf),n=len(conf))
    for k in e.old.PORTS:out[k]=dict(correct=sum(r['first']['predictions'][k]==r['case']['expected'] for r in groups['clear']),n=len(groups['clear']))
    return out

def fraction(c,key):return c[key]['correct']/c[key]['n']

def bootstrap(values):
    rng=random.Random(441109);samples=sorted(mean(rng.choices(values,k=8)) for _ in range(20000))
    return [samples[499],samples[19499]]

def main(work):
    assert e.load(work/'status.json')==dict(state='awaiting-analysis',branches_completed=112)
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists();e.frozen(work)
    dataset={};checked=0;matching=[];boundaries=0
    for phase,arms in e.ARMS.items():
        for i in range(8):
            for h in (0,1):
                for arm in arms:
                    root=work/f'{phase}/o{i}/h{h}/{arm}';parent=e.load(root/'parent.json.gz');prior=e.base.digest(parent)
                    ordered=['intervention']+([f'teaching-{j}' for j in (1,2)] if phase=='early' else [])+[f'trial-{j:03d}' for j in range(24)]
                    rows=[];source_cfg=parent['core']['config'];initial_keys=None
                    for name in ordered:
                        f=root/name;complete=e.load(f/'complete.json');state=e.load(work/complete['state_file']);result=e.load(f/'result.json.gz')
                        assert complete['before_sha256']==prior
                        assert e.sha(work/complete['state_file'])==complete['sha256']
                        assert e.sha(f/'result.json.gz')==complete['result_sha256']
                        assert e.base.digest(state)==complete['after_sha256']
                        assert state['core']['config']==source_cfg and state['core']['dynamics']==e.base.KERNEL
                        assert state['adapter_digest']==parent['adapter_digest']==state['frozen_digest']
                        assert state['mapping']==parent['mapping']
                        prior=e.base.digest(state);boundaries+=1
                        if name=='intervention':
                            altered,expected=e.patch_half_life(parent,arm)
                            assert state['core']==altered['core']
                            assert result['connections']==expected['connections']
                        if name.startswith('trial-'):
                            previous.verify_trial(result,state);rows.append(result);checked+=1
                            if arm=='baseline':
                                reference=e.load(work/f'reference/origins/o{i}/h{h}/intact/{name}/result.json.gz')
                                assert {k:v for k,v in result.items() if k!='edge_measure'}==reference
                        if phase=='early' and arm=='baseline' and name.startswith('teaching-'):
                            reference=e.load(work/f'reference/origins/o{i}/h{h}/{name}/result.json.gz')
                            assert {k:v for k,v in result.items() if k!='edge_measure'}==reference
                    testparent=e.load(root/'test-parent.json.gz')
                    ns=e.names(parent);portnames=set(sum(e.old.PORTS.values(),()))
                    xkeys={(x['source'],x['target']) for x in parent['core']['edges'] if
                        (ns[x['source']] in ('X0','X1') and ns[x['target']] in portnames) or
                        (ns[x['target']] in ('X0','X1') and ns[x['source']] in portnames)}
                    remaining={(x['source'],x['target']) for x in state['core']['edges']}
                    dataset[(phase,i,h,arm)]=dict(counts=counts(rows),retained=len(xkeys&remaining)/len(xkeys),
                        remaining=len(xkeys&remaining),initial=len(xkeys),new_predictions=[r['first']['predictions'] for r in rows if r['case']['kind']=='clear'],
                        parent_time_us=parent['core']['time_us'],test_time_us=testparent['core']['time_us'],end_time_us=state['core']['time_us'],
                        final_edges=len(state['core']['edges']))
                # Matching is assessed from the common unmodified parent.
                target=set(e.selected(parent,'target'));matched=set(e.selected(parent,'matched'));all_edges=parent['core']['edges']
                degrees=Counter()
                for x in all_edges:degrees[x['source']]+=1;degrees[x['target']]+=1
                sig=lambda keys:sorted((degrees[a],degrees[b]) for a,b in keys)
                measures=e.current_edge_measure(parent)
                weights=lambda keys:[x['weight'] for x in measures if tuple(x['key']) in keys]
                residual=abs(mean(weights(target))-mean(weights(matched)))
                valid=len(target)==len(matched)==28 and sig(target)==sig(matched) and residual<=.05
                matching.append(dict(phase=phase,origin=i,history=h,valid=valid,weight_residual=residual,target=len(target),matched=len(matched)))
    assert all(x['valid'] for x in matching),'matching invalid: report as INVALID before interpretation'
    origins=[];aggregate={};deltas={}
    for i in range(8):
        pooled={};q4={}
        for phase,arms in e.ARMS.items():
            for arm in arms:
                both=[dataset[(phase,i,h,arm)] for h in (0,1)];key=phase+':'+arm
                c={name:dict(correct=sum(x['counts'][name]['correct'] for x in both),n=sum(x['counts'][name]['n'] for x in both)) for name in both[0]['counts']}
                pooled[key]=c
                if key not in aggregate:aggregate[key]={name:dict(correct=0,n=0) for name in c}
                for name,v in c.items():
                    aggregate[key][name]['correct']+=v['correct'];aggregate[key][name]['n']+=v['n']
                changed=sum(all(a[k]!=b[k] for k in e.old.PORTS) for a,b in zip(both[0]['new_predictions'],both[1]['new_predictions']))/8
                q4[key]=all(fraction(x['counts'],'clear')>=.75 for x in both) and changed>=.5
        q1=all(dataset[('late',i,h,'target')]['retained']>=.9 and dataset[('late',i,h,'baseline')]['retained']<=.1 for h in (0,1))
        gain={}
        for phase,arms in e.ARMS.items():
            for arm in arms:
                if arm=='baseline':continue
                key=phase+':'+arm;ref=pooled[phase+':baseline'];new=pooled[key]
                gain[key]=fraction(new,'clear')-fraction(ref,'clear')
                deltas.setdefault(key,[]).append(gain[key])
        q2=q1 and gain['late:target']>=.25 and gain['late:target']-gain['late:matched']>=.125 and fraction(pooled['late:baseline'],'old')-fraction(pooled['late:target'],'old')<=.125
        q3={arm:gain['early:'+arm]>=.25 and fraction(pooled['early:baseline'],'old')-fraction(pooled['early:'+arm],'old')<=.125 for arm in ('target','all')}
        origins.append(dict(origin=i,counts=pooled,gains=gain,Q1=q1,Q2=q2,Q3=q3,Q4=q4))
    verdict=dict(Q1=sum(x['Q1'] for x in origins),Q2=sum(x['Q2'] for x in origins),
        Q3={arm:sum(x['Q3'][arm] for x in origins) for arm in ('target','all')},Q4={key:sum(x['Q4'][key] for x in origins) for key in aggregate})
    effects={key:dict(mean=mean(v),individual=v,bootstrap95=bootstrap(v),planning_effect=.25,
        precision='interval spans 25-point benefit' if bootstrap(v)[0]<.25<bootstrap(v)[1] else 'interval does not span 25-point benefit') for key,v in deltas.items()}
    result=dict(schema='threemind.retention-causality-analysis/1',independent_origins=8,reused_origins=True,checked_trials=checked,complete_boundaries=boundaries,
        successes=verdict,aggregate=aggregate,effects=effects,origins=origins,matching=matching,
        branches=[dict(phase=k[0],origin=k[1],history=k[2],arm=k[3],**v) for k,v in dataset.items()])
    e.save(work/'analysis-v1.json',result)
    print(json.dumps({k:result[k] for k in ('successes','aggregate','effects','checked_trials','complete_boundaries')},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=e.WORK);a=p.parse_args();main(a.work.resolve())
