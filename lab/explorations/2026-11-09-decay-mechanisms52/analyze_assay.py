"""Read-only R46a analysis; never instantiate a scientific subject."""
from __future__ import annotations
import json
import math
import random
import assay_study as e
from retention_assay import FIELDS
from threemind_kernels.decay52 import advance_age,remaining,Trace,Contribution


def vector(result):
    return [r[f'out{k}'][f]-b[f'out{k}'][f]
        for r,b in zip(result['response']['raw'],result['baseline']['raw'])
        for k in (0,1) for f in FIELDS]


def rms(v):return math.sqrt(math.fsum(x*x for x in v)/len(v))


def cue_history_difference(parts,delay):
    effects={h:[a-b for a,b in zip(parts[h,delay,True]['response_vector'],parts[h,delay,False]['response_vector'])]
        for h in (0,1)}
    return [b-a for a,b in zip(effects[0],effects[1])]


def retained(early,late):
    a,b=rms(early),rms(late)
    cosine=math.fsum(x*y for x,y in zip(early,late))/(len(early)*a*b) if a and b else None
    return dict(early_rms=a,late_rms=b,cosine=cosine,
        passed=a>1e-4 and b>1e-4 and b>=.1*a and cosine>=.8)


def target_edges(measure,history):
    pair={'cue',f'out{history}'}
    return [r for r in measure['edges'] if {r['source_symbol'],r['target_symbol']}==pair]


def forecast_weight(row,state,seconds):
    c=state['core'];cfg=c['config']
    dt=(int(c['time_us'])-int(row['state_us']))/1e6+seconds
    age,_=advance_age(row['half_life'],dt,cfg['memory_half_life_min_s'],
        cfg['memory_half_life_decay_rate'] if cfg['retention_relaxation_enabled'] else 0.)
    if cfg['decay_curve']=='exponential':return row['weight']*remaining('exponential',age)
    return Trace(cfg['decay_curve'],tuple(Contribution(*x) for x in row['decay_contributions'])).value(age)


def interval(values):
    rng=random.Random(461109)
    bs=sorted(sum(rng.choices(values,k=8))/8 for _ in range(20000))
    return [bs[499],bs[19499]]


def main(work):
    assert e.load(work/'status.json')==dict(state='awaiting-analysis',sequences_completed=1920)
    assert not any((work/p).exists() for p in ('STOP','in-flight.json'))
    e.frozen(work)
    rows=[];lookup={};boundaries=0
    for case in e.load(work/'cases.json'):
        root=work/'subjects'/case['key'];before=e.load(root/'birth.json.gz')
        assert int(before['core']['time_us'])==0
        wall=0.;peak=0
        for phase in ('teaching','probe'):
            receipt=e.load(root/phase/'complete.json')
            assert e.sha(work/receipt['state_file'])==receipt['sha256']
            assert e.sha(work/receipt['result_file'])==receipt['result_sha256']
            state=e.load(work/receipt['state_file']);result=e.load(work/receipt['result_file'])
            assert e.base.digest(before)==receipt['before_sha256']
            assert e.base.digest(state)==receipt['after_sha256']
            assert int(receipt['start_us'])==int(before['core']['time_us'])
            assert receipt['end_us']==int(state['core']['time_us'])
            assert state['mapping']==before['mapping'] and state['identity']==before['identity']
            assert state['core']['dynamics']==e.KERNEL_ID
            assert state['core']['config']['decay_curve']==case['curve']
            assert state['core']['config']['retention_relaxation_enabled']==case['relaxation']
            if phase=='teaching':taught=result;taught_state=state
            before=state;boundaries+=1;wall+=receipt['wall_seconds'];peak=max(peak,receipt['private_bytes'])
        assert int(taught['time_us'])==128000000
        assert result['response']['start_us']==128000000+case['delay']*1000000
        assert int(state['core']['time_us'])==129000000+case['delay']*1000000
        events=state['events'];paired=[x for x in events if x['role']=='paired-teaching']
        from retention_assay import TIMES,DOSES
        assert [x['time_us'] for x in paired]==[round(t*1e6) for t in TIMES[case['course']]]
        expected={state['mapping']['cue']:DOSES[case['course']],state['mapping'][f"out{case['history']}"]:DOSES[case['course']]}
        assert all(dict(x['channels'])==expected for x in paired)
        probes=[x for x in events if x['role']=='cue-probe']
        assert len(probes)==int(case['cue']) and result['cue_present']==case['cue']
        if case['cue']:assert probes[0]['channels']==[[state['mapping']['cue'],.8]]
        for window in ('baseline','response'):
            w=result[window]
            assert len(w['raw'])==20 and w['frame_times_us']==[w['start_us']+(i+1)*50000 for i in range(20)]
            assert all(set(n)==set(FIELDS) for frame in w['raw'] for n in frame.values())
        initial=target_edges(taught,case['history']);current=target_edges(result['before'],case['history'])
        initial_keys={(x['source'],x['target']) for x in initial}
        current_keys={(x['source'],x['target']) for x in current}
        raw_initial=[r for r in taught_state['core']['edges'] if (r['source'],r['target']) in initial_keys]
        forecast=[forecast_weight(r,taught_state,30*86400) for r in raw_initial]
        row=dict(case=case,formed=len(initial)==2,surviving=len(initial_keys&current_keys),
            taught_core_sha256=e.base.digest(taught_state['core']),
            pre_probe_sha256=e.base.digest(result['before']),baseline_sha256=e.base.digest(result['baseline']),
            initial_connections=initial,current_connections=current,forecast_30days=forecast,
            finite_fading=len(forecast)==2 and all(x<taught_state['core']['config']['prune_weight'] for x in forecast),
            response_vector=vector(result),wall_seconds=wall,max_boundary_private_bytes=peak,
            nodes=len(state['core']['nodes']),edges=len(state['core']['edges']),
            contributions=sum(len(r['decay_contributions']) for r in state['core']['nodes']+state['core']['edges']))
        rows.append(row);lookup[case['origin'],case['curve'],case['relaxation'],case['course'],case['history'],case['delay'],case['cue']]=row
    origins=[]
    conditions=[(c,r) for c in ('exponential','inverse-logarithmic','power-law') for r in (True,False)]
    for o in range(8):
        for curve,relaxation in conditions:
            courses={}
            for course in e.COURSES:
                parts={(h,d,q):lookup[o,curve,relaxation,course,h,d,q] for h in (0,1) for d in (1,300) for q in (True,False)}
                for h in (0,1):
                    for d in (1,300):
                        for field in ('taught_core_sha256','pre_probe_sha256','baseline_sha256'):
                            assert parts[h,d,True][field]==parts[h,d,False][field]
                differences={d:cue_history_difference(parts,d) for d in (1,300)}
                courses[course]=dict(formed=all(x['formed'] for x in parts.values()),
                    survives=all(parts[h,300,True]['formed'] and parts[h,300,True]['surviving']==2 for h in (0,1)),
                    forgotten=all(parts[h,300,True]['formed'] and parts[h,300,True]['surviving']==0 for h in (0,1)),
                    finite_fading=all(x['finite_fading'] for x in parts.values()),
                    process=retained(differences[1],differences[300]),
                    mean_late_weight=sum(sum(e['weight'] for e in parts[h,300,True]['current_connections']) for h in (0,1))/4)
            origins.append(dict(origin=o,curve=curve,relaxation=relaxation,courses=courses))
    summaries=[]
    for curve,relaxation in conditions:
        selected=[x for x in origins if x['curve']==curve and x['relaxation']==relaxation]
        count={course:{field:sum(x['courses'][course][field] for x in selected)
            for field in ('formed','survives','forgotten','finite_fading')} for course in e.COURSES}
        for course in count:count[course]['process']=sum(x['courses'][course]['process']['passed'] for x in selected)
        structure=count['weak']['forgotten']>=6 and all(count[c]['survives']>=6 for c in ('strong','spaced'))
        process=all(count[c]['process']>=6 for c in ('strong','spaced'))
        finite=all(count[c]['finite_fading']>=6 for c in ('strong','spaced'))
        spacing=[x['courses']['spaced']['mean_late_weight']-x['courses']['massed']['mean_late_weight'] for x in selected]
        summaries.append(dict(curve=curve,relaxation=relaxation,counts=count,
            selection=dict(structure=structure,process=process,finite_fading=finite,all=structure and process and finite),
            spacing_weight_difference=dict(mean=sum(spacing)/8,values=spacing,bootstrap95=interval(spacing))))
    output=dict(schema='threemind.decay-assay-analysis/1',independent_origins=8,sequences=len(rows),
        complete_boundaries=boundaries,conditions=summaries,origins=origins,rows=rows,
        interpretation='actual local mechanism assay; whole-system task and analytic forecast remain separate')
    e.save(work/'analysis-v1.json',output)
    print(json.dumps(dict(sequences=len(rows),boundaries=boundaries,conditions=summaries)))


if __name__=='__main__':main(e.WORK)
