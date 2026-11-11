"""Second implementation of registered scoring from original question records."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ARMS=('intact','sham','target','matched','restored','view-blocked','forced-view')
HEADS=('sound','vision','action')


def read(p):
    raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)


def tuple_at(r,phase):return tuple(r[phase]['predictions'][h] for h in HEADS)


def count(rows,kind,phase,label_key):
    selected=[r for r in rows if r['case']['kind']==kind]
    return sum(tuple_at(r,phase)==(r['case'][label_key],)*3 for r in selected),len(selected)


def main(work):
    assert read(work/'status.json')==dict(state='awaiting-analysis',origins_completed=8)
    a=read(work/'analysis-v1.json');integrity=read(work/'integrity-audit-v1.json')
    assert not a['invalid_interface_origins'] and not a['invalid_matching_origins']
    assert all(m['matching_valid'] for m in integrity['matching'])
    totals={g:0 for g in ('G1','G2','G3','G4')};origins=[];checked=0
    for i in range(8):
        history_flags=[];intact_clear=[]
        for h in (0,1):
            arm_rows={arm:[read(work/f'origins/o{i}/h{h}/{arm}/trial-{j:03d}/result.json.gz') for j in range(24)] for arm in ARMS}
            measures={}
            for arm,rows in arm_rows.items():
                checked+=len(rows)
                old,nold=count(rows,'old','first','expected');new,nnew=count(rows,'clear','first','expected')
                mixed=[r for r in rows if r['case']['kind']=='ambiguous']
                clear=[r for r in rows if r['case']['kind']=='clear']
                conflict=[r for r in clear if r['case']['conflict']]
                before=sum(tuple_at(r,'first')==(r['case']['actual'],)*3 for r in conflict)
                after=sum(tuple_at(r,'second')==(r['case']['actual'],)*3 for r in conflict)
                obs=sum(r['first']['predictions']['action']==2 for r in mixed)
                extra=sum(r['first']['predictions']['action']==2 for r in clear)
                exit_correct=sum(r['second']['predictions']['action']==r['case']['actual'] for r in mixed)
                assert (nold,nnew,len(conflict),len(mixed))==(4,8,4,12)
                m=dict(old=old/nold,history=new/nnew,revised=after/4,revision_gain=(after-before)/4,
                    observe_mixed=obs/12,observe_clear=extra/8,mixed_exit=exit_correct/12)
                for key,value in m.items():assert value==a['origins'][i]['histories'][h]['arms'][arm][key],(i,h,arm,key)
                measures[arm]=m
            z=measures['intact'];matched=measures['matched'];target=measures['target']
            exact={arm:all(tuple((x[p] for p in ('first','second')))==tuple((y[p] for p in ('first','second')))
                for x,y in zip(arm_rows['intact'],arm_rows[arm])) for arm in ('sham','restored')}
            flags=dict(G1=z['history']>=.75,G2=z['revised']>=.75 and z['revision_gain']>=.5,
                G3=z['observe_mixed']>=.75 and z['observe_clear']<=.25 and z['mixed_exit']>=.75 and z['mixed_exit']-measures['view-blocked']['mixed_exit']>=.2,
                G4=z['history']-target['history']>=.3 and z['history']-matched['history']<=.1 and z['old']-target['old']<=.1 and all(exact.values()))
            assert flags==a['origins'][i]['histories'][h]['verdict']
            history_flags.append(flags)
            intact_clear.append([r for r in arm_rows['intact'] if r['case']['kind']=='clear'])
        changed=sum(all(x!=y for x,y in zip(tuple_at(r0,'first'),tuple_at(r1,'first')))
            for r0,r1 in zip(*intact_clear))/8
        flags={g:all(row[g] for row in history_flags) for g in totals}
        flags['G1']=flags['G1'] and changed>=.5
        assert changed==a['origins'][i]['opposite_joint_change'] and flags==a['origins'][i]['verdict']
        for g in totals:totals[g]+=int(flags[g])
        origins.append(dict(origin=i,opposite_joint_change=changed,verdict=flags))
    assert totals==a['successes']
    verdict={g:'pass' if n>=6 else 'not-met' for g,n in totals.items()}
    assert verdict==a['verdict']
    result=dict(schema='threemind.context-score-audit/1',checked_trials=checked,independent_origins=8,
        primary_counts=totals,primary_verdict=verdict,origins=origins,
        analysis_sha256=hashlib.sha256((work/'analysis-v1.json').read_bytes()).hexdigest(),
        method='Separately written count-based arithmetic from original records; not a new experiment or external replication.')
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode();path=work/'score-audit-v1.json'
    if path.exists():assert path.read_bytes()==raw
    else:
        with path.open('xb') as f:f.write(raw)
    print(json.dumps({k:v for k,v in result.items() if k!='origins'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();main(a.work.resolve())
