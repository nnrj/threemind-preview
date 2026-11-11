"""Frozen score and continuity analysis; reads saved JSON without advancing subjects."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import random
import relaxation_study as e

spec=importlib.util.spec_from_file_location('r43_window_verifier',e.rc.R43/'analyze.py')
old_analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(old_analysis)
HEADS=('sound','vision','action')


def good(r,window='first',expected=None):
    if expected is None:expected=r['case']['expected']
    return all(r[window]['predictions'][k]==expected for k in HEADS)


def counts(rows):
    old=[r for r in rows if r['case']['kind']=='old'];new=[r for r in rows if r['case']['kind']=='clear'];mixed=[r for r in rows if r['case']['kind']=='ambiguous']
    conf=[r for r in new if r['case']['conflict']]
    c={'old':dict(correct=sum(good(r) for r in old),n=len(old)),'new':dict(correct=sum(good(r) for r in new),n=len(new)),
       'view':dict(correct=sum(r['first']['predictions']['action']==2 for r in mixed),n=len(mixed)),
       'exit':dict(correct=sum(r['second']['predictions']['action']==r['case']['actual'] for r in mixed),n=len(mixed)),
       'revision':dict(correct=sum(good(r,'second',r['case']['actual']) for r in conf),n=len(conf))}
    c.update({k:dict(correct=sum(r['first']['predictions'][k]==r['case']['expected'] for r in new),n=len(new)) for k in HEADS})
    return c


def fraction(c,key):return c[key]['correct']/c[key]['n']
def mean(v):return sum(v)/len(v)
def bootstrap(values):
    rng=random.Random(451109);v=sorted(mean(rng.choices(values,k=8)) for _ in range(20000));return [v[499],v[19499]]


def structure(s,initial_keys):
    edges=e.rc.current_edge_measure(s);now={(x['source'],x['target']) for x in edges}
    target=[x for x in edges if (x['source'],x['target']) in initial_keys]
    return dict(time_us=s['core']['time_us'],nodes=len(s['core']['nodes']),connections=len(edges),
        x_initial=len(initial_keys),x_surviving=len(now&initial_keys),
        x_half_life=[x['half_life'] for x in target],x_weight=[x['weight'] for x in target],
        all_half_life=[x['half_life'] for x in edges])


def main(work):
    assert e.load(work/'status.json')==dict(state='awaiting-analysis',branches_completed=96)
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists();e.frozen(work)
    source_manifest=e.load(work/'source-manifest.json')
    for rel,v in source_manifest['files'].items():assert e.sha(Path(source_manifest['source'])/rel)==v['source_sha256']==e.sha(work/v['copied_path'])
    branches=[];values={};total=Counter();api_control=[];adapters=set()
    for i in range(e.N):
        for h in (0,1):
            for arm in e.ARMS:
                root=work/f'origins/o{i}/h{h}/{arm}';parent=e.load(root/'parent.json.gz');prior=e.base.digest(parent)
                ns=e.rc.names(parent);ports=set(sum(e.old.PORTS.values(),()))
                xkeys={(ns[x['source']],ns[x['target']]) for x in parent['core']['edges'] if
                    (ns[x['source']] in {'X0','X1'} and ns[x['target']] in ports) or (ns[x['target']] in {'X0','X1'} and ns[x['source']] in ports)}
                expected_cfg=dict(parent['core']['config'],memory_half_life_decay_rate=e.RATES[arm.split('-')[1]])
                rows=[];structures=[];previous_h={};monotonic=0;monotonic_violations=0;before_time=int(parent['core']['time_us'])
                for unit in ['intervention','teaching-1','teaching-2']+[f'trial-{j:03d}' for j in range(24)]:
                    c=e.load(root/unit/'complete.json');s=e.load(work/c['state_file']);r=e.load(root/unit/'result.json.gz')
                    assert e.sha(work/c['state_file'])==c['sha256'] and e.sha(root/unit/'result.json.gz')==c['result_sha256']
                    assert c['before_sha256']==prior and c['after_sha256']==e.base.digest(s)
                    assert int(c['start_us'])==before_time and int(c['end_us'])==int(s['core']['time_us'])>=before_time
                    before_time=int(c['end_us']);prior=e.base.digest(s)
                    assert s['core']['config']==expected_cfg and s['core']['dynamics']==e.base.KERNEL
                    for k in ('adapter_digest','frozen_digest','mapping'):assert s[k]==parent[k]
                    for ref in s['adapter_refs'].values():
                        for name,digest in ref['files'].items():
                            path=work/ref['path']/name
                            if path not in adapters:assert e.sha(path)==digest;adapters.add(path)
                    measured=e.rc.current_edge_measure(s);hs={tuple(x['key']):x['half_life'] for x in measured}
                    if arm.endswith('-off'):
                        for key in hs.keys()&previous_h.keys():
                            monotonic+=1;monotonic_violations+=hs[key]<previous_h[key]-1e-10
                    previous_h=hs
                    if unit=='intervention':
                        total['interventions']+=1
                        assert c['start_us']==str(c['end_us']) or int(c['start_us'])==int(c['end_us'])
                        assert r['max_current_physical_change_at_reconfigure']<1e-12
                        assert r['before_sha256']==e.base.digest(parent)
                    elif unit.startswith('teaching-'):
                        total['teaching']+=1
                        ref=e.load(work/f'reference/origins/o{i}/h{h}/{unit}/result.json.gz')['teaching'];t=r['teaching']
                        assert t['lessons']==ref['lessons'] and t['waits']==ref['waits']
                        assert [q['case'] for q in t['correction_questions']]==[q['case'] for q in ref['correction_questions']]
                    else:
                        total['trials']+=1;old_analysis.verify_trial(r,s);rows.append(r)
                        assert int(c['end_us'])-int(c['start_us'])==3000000
                        if arm.endswith('-default'):
                            refarm='baseline' if arm.startswith('natural') else 'target'
                            p=e.rc.WORK/f'early/o{i}/h{h}/{refarm}/{unit}/result.json.gz';ref=e.load(p)
                            api_control.append(dict(origin=i,history=h,arm=arm,unit=unit,
                                categories_equal=all(r[w]['predictions']==ref[w]['predictions'] for w in ('first','second')),
                                raw_equal=all(r[w]['raw']==ref[w]['raw'] for w in ('first','second'))))
                    if unit in ('intervention','teaching-1','teaching-2','trial-023'):structures.append(dict(stage=unit,**structure(s,xkeys)))
                assert monotonic_violations==0
                item=dict(origin=i,history=h,arm=arm,counts=counts(rows),structure=structures,
                    off_monotonic_comparisons=monotonic,off_monotonic_violations=monotonic_violations,
                    new_predictions=[r['first']['predictions'] for r in rows if r['case']['kind']=='clear'])
                branches.append(item);values[i,h,arm]=item
    assert total==dict(interventions=96,teaching=192,trials=2304)
    aggregates={};origins=[];gains={};candidate=tuple(a for a in e.ARMS if not a.endswith('-default'))
    for i in range(e.N):
        scores={};q4={}
        for arm in e.ARMS:
            pair=[values[i,h,arm] for h in (0,1)]
            scores[arm]={k:dict(correct=sum(x['counts'][k]['correct'] for x in pair),n=sum(x['counts'][k]['n'] for x in pair)) for k in pair[0]['counts']}
            dest=aggregates.setdefault(arm,{k:dict(correct=0,n=0) for k in pair[0]['counts']})
            for k,v in scores[arm].items():
                for f in ('correct','n'):dest[k][f]+=v[f]
            changed=sum(all(a[k]!=b[k] for k in HEADS) for a,b in zip(pair[0]['new_predictions'],pair[1]['new_predictions']))/8
            q4[arm]=all(fraction(x['counts'],'new')>=.75 for x in pair) and changed>=.5
        passed={};effect={}
        for arm in candidate:
            control=arm.split('-')[0]+'-default';gain=fraction(scores[arm],'new')-fraction(scores[control],'new')
            loss=fraction(scores[control],'old')-fraction(scores[arm],'old')
            gains.setdefault(arm,[]).append(gain);effect[arm]=dict(new_gain=gain,old_loss=loss)
            passed[arm]=gain>=.25 and loss<=.125
        origins.append(dict(origin=i,scores=scores,effects=effect,benefit_pass=passed,restoration_pass=q4))
    verdict=dict(R1=True,R2={a:sum(x['benefit_pass'][a] for x in origins) for a in candidate if a.startswith('natural')},
        R3={a:sum(x['benefit_pass'][a] for x in origins) for a in candidate if a.startswith('raised')},
        R4={a:sum(x['restoration_pass'][a] for x in origins) for a in e.ARMS})
    effects={a:dict(mean=mean(v),individual=v,bootstrap95=bootstrap(v)) for a,v in gains.items()}
    output=dict(schema='threemind.retention-relaxation-analysis/1',independent_origins=8,reused_origins=True,counts=dict(total),
        complete_boundaries=sum(total.values()),successes=verdict,aggregate=aggregates,effects=effects,origins=origins,branches=branches,
        api_default_comparison=api_control,adapter_files_verified=len(adapters),source_files_verified=len(source_manifest['files']))
    e.save(work/'analysis-v1.json',output)
    print(json.dumps({k:output[k] for k in ('counts','successes','aggregate','effects')},ensure_ascii=False))


if __name__=='__main__':main(e.WORK)
