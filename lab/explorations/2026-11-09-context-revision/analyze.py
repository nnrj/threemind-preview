"""Read-only independent arithmetic and evidence checks; never restores Core."""
import argparse
import json
import math
from pathlib import Path
import experiment as e


def mean(x):return sum(x)/len(x) if x else None
def joint(p,label):return all(p[k]==label for k in ('sound','vision','action'))
def wilson(k,n):
    z=1.959963984540054;p=k/n;d=1+z*z/n
    a=(p+z*z/(2*n))/d;b=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [a-b,a+b]


def scores(rows):
    old=[r for r in rows if r['case']['kind']=='old'];clear=[r for r in rows if r['case']['kind']=='clear']
    conflict=[r for r in clear if r['case']['conflict']];mixed=[r for r in rows if r['case']['kind']=='ambiguous']
    return dict(old=mean([joint(r['first']['predictions'],r['case']['expected']) for r in old]),
        history=mean([joint(r['first']['predictions'],r['case']['expected']) for r in clear]),
        revised=mean([joint(r['second']['predictions'],r['case']['actual']) for r in conflict]),
        revision_gain=mean([int(joint(r['second']['predictions'],r['case']['actual']))-int(joint(r['first']['predictions'],r['case']['actual'])) for r in conflict]),
        observe_mixed=mean([r['first']['predictions']['action']==2 for r in mixed]),
        observe_clear=mean([r['first']['predictions']['action']==2 for r in clear]),
        mixed_exit=mean([r['second']['predictions']['action']==r['case']['actual'] for r in mixed]),
        denominators=dict(old=len(old),clear=len(clear),conflict=len(conflict),mixed=len(mixed)))


def verify_trial(row,state):
    assert row['end_us']-row['start_us']==3_000_000
    mapping=state['mapping'];ports={mapping[x] for p in e.PORTS.values() for x in p}
    for part in ('first','second'):
        q=row[part];assert len(q['frame_times_us'])==20 and q['indices']==e.INDEX
        assert q['frame_times_us']==[q['start_us']+(i+1)*50_000 for i in range(20)]
        for k,names in e.PORTS.items():
            assert q['predictions'][k]==max(range(len(q['logits'][k])),key=lambda i:q['logits'][k][i])
            channels=sorted(mapping[n] for n in names)
            symbols=[next(s for s,c in mapping.items() if c==ch) for ch in channels]
            for frame,raw in zip(q['frames'][k],q['raw']):
                assert frame==[float(__import__('numpy').float32(raw[s][f])) for s in symbols for f in ('activation','inhibition','direct','associative')]
        assert all(c not in ports for event in q['events'] for c,v in event['channels'])
    c=row['case'];first=row['first'];second=row['second']
    expected=e.sensory(c)
    actual={k: v for ev in first['events'] if ev['time_us']==first['start_us'] for ch,v in ev['channels'] for k,m in mapping.items() if m==ch and k!='K'}
    assert actual==expected
    should=(c['kind']=='clear' or row['mode']=='forced-view' or first['predictions']['action']==2) and c['kind']!='old'
    if row['mode']=='view-blocked' and c['kind']!='clear':should=False
    expected_feedback={f"D{c['actual']}":c['dose']} if should else {}
    assert row['feedback']==expected_feedback and row['world']['observed']==bool(expected_feedback)
    delivered={k:v for ev in second['events'] if ev['time_us']==second['start_us'] for ch,v in ev['channels'] for k,m in mapping.items() if m==ch and k!='K'}
    assert delivered==expected_feedback


def main(work):
    assert e.load(work/'status.json')==dict(state='awaiting-analysis',origins_completed=e.N)
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    e.frozen(work);origins=[];checked=0
    for i in range(e.N):
        histories=[];allrows=[]
        for h in range(2):
            root=work/f'origins/o{i}/h{h}';parent=e.load(root/'test-parent.json.gz');arms={};interventions={};rowsbyarm={}
            for arm in e.ARMS:
                rows=[];last=int(parent['core']['time_us']);interventions[arm]=e.load(root/f'{arm}/intervention/result.json.gz')
                for j in range(24):
                    folder=root/f'{arm}/trial-{j:03d}';commit=e.load(folder/'complete.json');row=e.load(folder/'result.json.gz')
                    state=e.load(work/commit['state_file'])
                    assert e.sha(work/commit['state_file'])==commit['sha256']
                    assert e.sha(folder/'result.json.gz')==commit['result_sha256']
                    assert int(commit['start_us'])==last==row['start_us']
                    last=int(commit['end_us']);assert last==int(state['core']['time_us'])==row['end_us']
                    assert state['adapter_digest']==parent['adapter_digest']==state['frozen_digest']
                    for ref in state['adapter_refs'].values():
                        for name,sha in ref['files'].items():assert e.sha(work/ref['path']/name)==sha
                    verify_trial(row,state);checked+=1;rows.append(row)
                rowsbyarm[arm]=rows;arms[arm]=scores(rows)
            exact={a:all(x['first']==y['first'] and x['second']==y['second'] for x,y in zip(rowsbyarm['intact'],rowsbyarm[a])) for a in ('sham','restored')}
            a=arms['intact'];matching=interventions['target']['matching_valid']
            valid=parent['calibration_valid']
            verdict=dict(G1=valid and a['history']>=.75,
                         G2=valid and a['revised']>=.75 and a['revision_gain']>=.5,
                         G3=valid and a['observe_mixed']>=.75 and a['observe_clear']<=.25 and a['mixed_exit']>=.75 and a['mixed_exit']-arms['view-blocked']['mixed_exit']>=.2,
                         G4=valid and matching and a['history']-arms['target']['history']>=.3 and a['history']-arms['matched']['history']<=.1 and a['old']-arms['target']['old']<=.1 and all(exact.values()))
            histories.append(dict(history=h,calibration_valid=valid,matching_valid=matching,arms=arms,verdict=verdict,exact=exact,
                intervention=interventions['target'],parent_time_us=int(parent['core']['time_us'])))
            allrows.append(rowsbyarm['intact'])
        c0=[r for r in allrows[0] if r['case']['kind']=='clear'];c1=[r for r in allrows[1] if r['case']['kind']=='clear']
        assert [r['case']['cue'] for r in c0]==[r['case']['cue'] for r in c1]
        changed=mean([all(x['first']['predictions'][k]!=y['first']['predictions'][k] for k in e.PORTS) for x,y in zip(c0,c1)])
        verdict={g:all(h['verdict'][g] for h in histories) for g in ('G1','G2','G3','G4')};verdict['G1'] &= changed>=.5
        origins.append(dict(origin=i,histories=histories,opposite_joint_change=changed,verdict=verdict))
    totals={g:sum(o['verdict'][g] for o in origins) for g in ('G1','G2','G3','G4')}
    result=dict(schema='threemind.context-analysis/1',independent_n=e.N,checked_trials=checked,origins=origins,
                successes=totals,intervals={g:wilson(k,e.N) for g,k in totals.items()},
                verdict={g:('pass' if k>=6 else 'not-met') for g,k in totals.items()},
                invalid_interface_origins=[o['origin'] for o in origins if not all(h['calibration_valid'] for h in o['histories'])],
                invalid_matching_origins=[o['origin'] for o in origins if not all(h['matching_valid'] for h in o['histories'])])
    if result['invalid_interface_origins']:
        for g in result['verdict']:result['verdict'][g]='measurement-invalid'
    elif result['invalid_matching_origins']:result['verdict']['G4']='measurement-invalid'
    e.save(work/'analysis-v1.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='origins'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=e.WORK);a=p.parse_args();main(a.work.resolve())
