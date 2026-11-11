"""R46b preregistered analysis of saved originals; no subject creation."""
import json
import math
import stimulus_study as e
from analyze_assay import forecast_weight, retained
from retention_assay import FIELDS


def rms(values):
    return math.sqrt(math.fsum(x*x for x in values)/len(values))


def response_vector(result):
    return [r['out0'][f]-b['out0'][f]
            for r,b in zip(result['response']['raw'],result['baseline']['raw']) for f in FIELDS]


def target_edges(graph):
    return [r for r in graph['edges'] if {r['source_symbol'],r['target_symbol']}=={'cue','out0'}]


def benefit(active,control,absolute,relative=0.):
    difference=active-control
    return dict(active=active,control=control,difference=difference,
                relative_difference=difference/control if control else None,
                passed=difference>absolute and difference>=relative*control)


def main(work):
    assert e.a.load(work/'status.json')==dict(state='awaiting-analysis',sequences_completed=960)
    assert not any((work/p).exists() for p in ('STOP','in-flight.json','analysis-v1.json'))
    assert e.operational.dead(e.a.load(work/'host.json'))
    e.frozen(work)
    rows=[];lookup={};boundaries=0;internal_seconds=0.
    for case in e.a.load(work/'cases.json'):
        root=work/'subjects'/case['key'];prior=e.a.load(root/'birth.json.gz')
        assert prior['case']==case and int(prior['core']['time_us'])==0
        cfg=prior['core']['config']
        assert cfg['decay_curve']==case['curve'] and cfg['retention_relaxation_enabled']==case['relaxation']
        wall=0.;peak=0
        for phase in ('teaching','probe'):
            receipt=e.a.load(root/phase/'complete.json')
            assert e.a.sha(work/receipt['state_file'])==receipt['sha256']
            assert e.a.sha(work/receipt['result_file'])==receipt['result_sha256']
            state=e.a.load(work/receipt['state_file']);result=e.a.load(work/receipt['result_file'])
            assert e.a.base.digest(prior)==receipt['before_sha256']
            assert e.a.base.digest(state)==receipt['after_sha256']
            assert int(receipt['start_us'])==int(prior['core']['time_us'])
            assert int(receipt['end_us'])==int(state['core']['time_us'])
            assert state['case']==case and state['mapping']==prior['mapping'] and state['identity']==prior['identity']
            assert state['core']['dynamics']==e.a.KERNEL_ID and state['core']['config']==cfg
            if phase=='teaching':taught=result;taught_state=state
            internal_seconds+=(int(receipt['end_us'])-int(receipt['start_us']))/1e6
            prior=state;boundaries+=1;wall+=receipt['wall_seconds'];peak=max(peak,receipt['private_bytes'])
        assert int(taught_state['core']['time_us'])==1_000_000
        assert result['response']['start_us']==1_000_000+case['delay']*1_000_000
        assert int(state['core']['time_us'])==2_000_000+case['delay']*1_000_000
        events=state['events'];teaching=[x for x in events if x['role']=='target-teaching']
        assert len(teaching)==1
        p=case['profile'];event=teaching[0]
        if case['family']=='strong':
            intensity=1. if case['arm']=='equal-drive-normal' else p['strong_intensity']
            assert event['intensity']==intensity and event['time_us']==100_000
            amplitude=p['drive']/intensity
            sample=taught['samples']['immediate']
        else:
            assert event['intensity']==1. and event['time_us']==100_000+p['new_offset_us']
            amplitude=p['new_amplitude'];sample=taught['samples']['after_window']
            old=[x for x in events if x['role']=='prior-connection']
            assert len(old)==1 and old[0]['time_us']==100_000 and old[0]['intensity']==1.
            assert dict(old[0]['channels'])=={state['mapping']['cue']:p['old_amplitude'],state['mapping']['out1']:p['old_amplitude']}
        assert dict(event['channels'])=={state['mapping']['cue']:amplitude,state['mapping']['out0']:amplitude}
        probes=[x for x in events if x['role']=='cue-probe']
        assert len(probes)==int(case['cue']) and result['cue_present']==case['cue']
        if case['cue']:assert probes[0]['channels']==[[state['mapping']['cue'],.8]] and probes[0]['intensity']==1.
        for name in ('baseline','response'):
            window=result[name]
            assert len(window['raw'])==20
            assert window['frame_times_us']==[window['start_us']+(i+1)*50_000 for i in range(20)]
            assert all(set(n)==set(FIELDS) for frame in window['raw'] for n in frame.values())
        initial=target_edges(sample['graph']);keys={(x['source'],x['target']) for x in initial}
        current=[x for x in target_edges(result['before']) if (x['source'],x['target']) in keys]
        saved={(r['source'],r['target']):r for r in taught_state['core']['edges']}
        forecast=[forecast_weight(saved[key],taught_state,30*86400) if key in saved else 0. for key in sorted(keys)]
        row=dict(case=case,formed=len(keys)==2,surviving=len(current),
            initial_connections=initial,current_connections=current,
            initial_mean_weight=math.fsum(r['weight'] for r in initial)/2,
            current_mean_weight=math.fsum(r['weight'] for r in current)/2,
            taught_core_sha256=e.a.base.digest(taught_state['core']),
            pre_probe_sha256=e.a.base.digest(result['before']),baseline_sha256=e.a.base.digest(result['baseline']),
            forecast_30days=forecast,finite_fading=len(forecast)==2 and all(x<cfg['prune_weight'] for x in forecast),
            response_vector=response_vector(result),wall_seconds=wall,max_boundary_private_bytes=peak)
        rows.append(row);lookup[case['origin'],case['curve'],case['relaxation'],case['arm'],case['delay'],case['cue']]=row
    origins=[]
    for o in range(8):
        for curve in ('exponential','inverse-logarithmic','power-law'):
            for relaxation in (True,False):
                arms={}
                for arm in ('equal-drive-normal','strong-intensity','strong-gain-zero','arrival-novelty','arrival-gain-zero'):
                    parts={(d,q):lookup[o,curve,relaxation,arm,d,q] for d in (1,300) for q in (True,False)}
                    assert len({r['taught_core_sha256'] for r in parts.values()})==1
                    for d in (1,300):
                        for f in ('pre_probe_sha256','baseline_sha256'):assert parts[d,True][f]==parts[d,False][f]
                    effect={d:[x-y for x,y in zip(parts[d,True]['response_vector'],parts[d,False]['response_vector'])] for d in (1,300)}
                    arms[arm]=dict(formed=all(r['formed'] for r in parts.values()),
                        survives=parts[300,True]['surviving']==2,initial_mean_weight=parts[1,True]['initial_mean_weight'],
                        late_mean_weight=parts[300,True]['current_mean_weight'],finite_fading=all(r['finite_fading'] for r in parts.values()),
                        process=retained(effect[1],effect[300]),effect=effect,
                        late_fields_rms={f:rms(effect[300][i::4]) for i,f in enumerate(FIELDS)})
                comparisons={}
                for family,active,control in (('strong-gain','strong-intensity','strong-gain-zero'),
                        ('novelty-gain','arrival-novelty','arrival-gain-zero'),
                        ('overall-intensity','strong-intensity','equal-drive-normal')):
                    x,y=arms[active],arms[control]
                    immediate=benefit(x['initial_mean_weight'],y['initial_mean_weight'],1e-8)
                    structure=benefit(x['late_mean_weight'],y['late_mean_weight'],1e-6,.1)
                    structure['passed']=structure['passed'] and x['survives']
                    activity=benefit(x['process']['late_rms'],y['process']['late_rms'],1e-6,.1)
                    activity['passed']=activity['passed'] and x['process']['late_rms']>1e-4
                    comparisons[family]=dict(immediate=immediate,structure=structure,activity=activity)
                origins.append(dict(origin=o,curve=curve,relaxation=relaxation,arms=arms,comparisons=comparisons))
    conditions=[]
    for curve in ('exponential','inverse-logarithmic','power-law'):
        for relaxation in (True,False):
            selected=[r for r in origins if r['curve']==curve and r['relaxation']==relaxation]
            counts={name:{f:sum(r['comparisons'][name][f]['passed'] for r in selected) for f in ('immediate','structure','activity')}
                    for name in ('strong-gain','novelty-gain','overall-intensity')}
            retention={arm:dict(structure=sum(r['arms'][arm]['survives'] for r in selected),
                process=sum(r['arms'][arm]['process']['passed'] for r in selected),
                finite_fading=sum(r['arms'][arm]['finite_fading'] for r in selected)) for arm in ('strong-intensity','arrival-novelty')}
            conditions.append(dict(curve=curve,relaxation=relaxation,counts=counts,
                gates={name:{f:n>=6 for f,n in row.items()} for name,row in counts.items()},retention=retention))
    out=dict(schema='threemind.stimulus-retention-analysis/1',matched_input_conditions=8,independent_birth_seeds=8,
        sequences=len(rows),complete_boundaries=boundaries,internal_seconds=internal_seconds,
        conditions=conditions,origins=origins,rows=rows)
    e.a.save(work/'analysis-v1.json',out)
    print(json.dumps({k:v for k,v in out.items() if k not in ('rows','origins')}))


if __name__=='__main__':main(e.WORK)
