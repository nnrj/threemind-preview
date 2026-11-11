"""Independent complete-boundary and curriculum arithmetic; does not load a subject."""
import argparse
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path
import audit_corrections


def read(p):
    b=p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)


def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run(work):
    assert read(work/'status.json')==dict(state='awaiting-analysis',origins_completed=8)
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    births={f'o{i}':read(work/f'origins/o{i}/birth.json.gz') for i in range(8)}
    for name,birth in births.items():
        assert birth['core']['dynamics']=='threemind.continuous-memory/5.1'
        assert birth['seed']==26110900+int(name[1:])
    correction=audit_corrections.audit(work)
    assert not correction['unhandled_cases'],correction
    commits=sorted((work/'origins').rglob('complete.json'));count=collections.Counter()
    groups=collections.defaultdict(list);curricula=[];total_simulation=0;trial_count=0;mask_cache={}
    for p in commits:
        c=read(p);state=read(work/c['state_file']);result=read(p.parent/'result.json.gz')
        origin=p.relative_to(work).parts[1];birth=births[origin]
        assert state['core']['dynamics']==birth['core']['dynamics']
        assert state['core']['config']==birth['core']['config'] and state['mapping']==birth['mapping']
        assert sha(work/c['state_file'])==c['sha256']
        assert sha(p.parent/'result.json.gz')==c['result_sha256']
        assert digest(state)==c['after_sha256']
        assert int(c['end_us'])==int(state['core']['time_us'])
        total_simulation+=int(c['end_us'])-int(c['start_us'])
        unit=p.parent.name
        if unit.startswith('trial-'):
            count['trial']+=1;trial_count+=1;groups[str(p.parent.parent)].append((int(unit[6:]),c))
            assert int(c['end_us'])-int(c['start_us'])==3_000_000
            branch=p.parent.parent
            if branch not in mask_cache:
                intervention=read(branch/'intervention/result.json.gz')
                mask_cache[branch]=intervention['pairs'] if branch.name in ('target','matched') else []
            assert sorted(state['core']['silenced_edges'])==sorted(mask_cache[branch])
            assert state['parent']['arm']==branch.name
            assert sha(work/state['parent']['path'])==state['parent']['sha256']
            if unit=='trial-000':
                assert read(branch/'intervention/complete.json')['after_sha256']==c['before_sha256']
        elif unit.startswith(('calibration-','teaching-')):
            kind=unit.split('-')[0];count[kind]+=1
            if kind=='teaching':assert state['adapter_digest']==state['frozen_digest']
            groups[str(p.parent.parent)+'/'+kind].append((int(unit.rsplit('-',1)[1]),c))
            t=result['teaching'];waits=t['waits']
            assert [(w['end_us']-w['start_us'])/1e6 for w in waits[-3:]]==[2,6,18]
            lessons=t['lessons']
            assert all(l['end_us']-l['start_us']==1_500_000 and l['teacher_control'] for l in lessons)
            for l in lessons:
                events=[v for v in l['events'] if len(v['channels'])>1]
                assert len(events)==5
                assert [v['time_us']-l['start_us'] for v in events]==[0,250000,500000,750000,1000000]
                assert all(all(x[1]==l['amplitude'] for x in v['channels']) for v in events)
            curricula.append(dict(unit=p.parent.relative_to(work).as_posix(),lessons=len(lessons),
                correction_questions=len(t['correction_questions']),start_us=c['start_us'],end_us=c['end_us'],
                correct=result['correct'],n=result['n'],ready=result['ready'],
                adapter_digest=state['adapter_digest'],core_edges=len(state['core']['edges'])))
        else:
            assert unit=='intervention';count['intervention']+=1
            assert int(c['end_us'])==int(c['start_us'])
    for group,rows in groups.items():
        rows.sort()
        assert [i for i,c in rows]==list(range(len(rows)))
        for (_,prev),(_,cur) in zip(rows,rows[1:]):
            assert int(prev['end_us'])==int(cur['start_us']),group
            assert prev['after_sha256']==cur['before_sha256'],group
    assert trial_count==8*2*7*24
    assert count['intervention']==8*2*7
    matching=[]
    for parent in sorted((work/'origins').glob('o*/h*/test-parent.json.gz')):
        state=read(parent);t=int(state['core']['time_us']);cfg=state['core']['config']
        record=read(parent.parent/'target/intervention/result.json.gz')
        def effective(edge):
            fast=edge.get('fast');v=0.
            if cfg['fast_enabled'] and fast:
                v=fast['value']*math.exp(-(t-int(fast['time_us']))/1e6/cfg['fast_tau_s'])
            return min(1.,edge['weight']+cfg['fast_gain']*v)
        means={k:sum(effective(edge) for edge in record[k])/len(record[k]) if record[k] else None for k in ('target','matched')}
        residual=abs(means['target']-means['matched']) if all(v is not None for v in means.values()) else None
        valid=record['matching_valid'] and residual is not None and residual<=.05
        matching.append(dict(parent=parent.relative_to(work).as_posix(),projected_base_weight_residual=record['weight_residual'],
            effective_weight_residual=residual,source_activity_residual=record['activity_residual'],matching_valid=valid))
        assert valid==record['matching_valid'],'effective weight changes registered matching validity'
    out=dict(schema='threemind.context-integrity-audit/1',complete_boundaries=len(commits),counts=dict(count),
        continuous_groups=len(groups),total_computed_internal_seconds=total_simulation/1e6,
        correction_audit=correction,curricula=curricula,matching=matching,
        kernel_and_configuration_unchanged=True,
        validation='separate arithmetic implementation; no subject restoration or simulation')
    path=work/'integrity-audit-v1.json';raw=json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2).encode()
    if path.exists():assert path.read_bytes()==raw
    else:
        with path.open('xb') as f:f.write(raw)
    print(json.dumps({k:v for k,v in out.items() if k not in ('curricula','correction_audit','matching')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
