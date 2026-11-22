"""Read-only artifact verification and preregistered R51d measurements."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent),str(HERE.parents[3]/'src')]
import support as s
from audit import disk_allocation
from threemind_runtime import ArtifactCodec


def read(path):return json.loads(path.read_bytes())
def trace(path):return json.loads(gzip.decompress(path.read_bytes()))


def summarize(work):
    assert not (work/'in-flight.json').exists()
    assert read(work/'summary.json')['conditions']==264
    schedule=read(work/'cases.json');frozen=read(work/'frozen.json')
    assert s.sha(work/'cases.json')==frozen['cases_sha256']
    for name,row in frozen['materials'].items():assert s.sha(work/'materials'/name)==row['sha256']
    results={};states={};processes={};patterns=[]
    for case in schedule:
        key=case['key'];folder=work/'cases'/key
        result=read(folder/'result.json');assert result['status']=='complete'
        assert read(folder/'input.json')==case
        images={stage:ArtifactCodec.decode((folder/f'{stage}.tmind').read_bytes()) for stage in ('initial','final')}
        for stage,image in images.items():assert image.digest==result[stage+'_sha256']
        if case['parent']:assert result['initial_sha256']==results[case['parent']]['final_sha256']
        doc=images['final'].to_dict();assert doc['dynamics']=='threemind.continuous-memory/6.1'
        assert len(doc['nodes'])==result['nodes'] and len(doc['edges'])==result['edges']
        assert all(n['id']==n['channel'] for n in doc['nodes'])
        trajectory=trace(folder/'trajectory.json.gz')
        times=[p['time_us'] for p in trajectory['points']]
        assert times==sorted(set(times))
        assert times[-1]==result['clock_end_us']
        assert result['clock_end_us']==case['target_us'] or result['life']=='dead'
        events=[x['payload'] for x in trajectory['events'] if x.get('payload',{}).get('analysis_schema')]
        if case['stage']=='probe' and case['cue_intensity']>0:
            # A parent that is already dead cannot receive a probe; report it explicitly.
            assert events or result['life']=='dead'
            patterns.append({'key':key,'family':case['family'],'preset':case['preset'],'seed':case['seed'],
                             'detected':any(e.get('analyses',{}).get('pattern',{}).get('status')=='converged' for e in events),
                             'events':len(events),'classifications':[e.get('classification') for e in events],
                             'censored':any(e.get('censored',False) for e in events)})
        results[key]=result;states[key]=doc
        # Retain only the compact four-activity process for later paired analysis.
        processes[key]={p['time_us']:{n['channel']:{f:n.get(f,0.) for f in ('activation','inhibition','direct','associative')} for n in p['nodes']} for p in trajectory['points']}
    topology=[];retention=[];order=[];strength=[];cue_effects=[]
    for seed in (93001,93002):
        for preset in ('ordinary','facilitation'):
            prefix=f'{seed}-{preset}'
            single=results[prefix+'-background-none-fresh-single']
            group=results[prefix+'-background-none-fresh-group']
            split=[results[prefix+f'-physical-{t}-split'] for t in ('inertial-cart','gravity-pendulum')]
            complete=[results[prefix+f'-physical-{t}-complete'] for t in ('inertial-cart','gravity-pendulum')]
            backgrounds=[v for v in results.values() if v['seed']==seed and v['preset']==preset and v['family']=='background' and v['stage']=='teaching']
            valid=single['edges']==2 and group['edges']>2 and all(v['cross_original_edges']==0 for v in backgrounds) and all(v['edges']==0 for v in split) and all(v['edges']>0 for v in complete)
            topology.append({'seed':seed,'preset':preset,'passed':valid,'single_edges':single['edges'],'group_edges':group['edges'],
                             'physical_split_edges':[v['edges'] for v in split],'physical_complete_edges':[v['edges'] for v in complete]})
            for t in ('inertial-cart','gravity-pendulum'):
                a=states[prefix+f'-physical-{t}-complete'];b=states[prefix+f'-physical-{t}-shuffled']
                wa={(e['source'],e['target']):e['weight'] for e in a['edges']};wb={(e['source'],e['target']):e['weight'] for e in b['edges']}
                diff=sum(abs(wa.get(k,0)-wb.get(k,0)) for k in wa.keys()|wb.keys())
                order.append({'seed':seed,'preset':preset,'template':t,'weight_l1_difference':diff,'same_edges':set(wa)==set(wb),
                              'full_weight_sum':sum(wa.values()),'shuffled_weight_sum':sum(wb.values())})
            strength.append({'seed':seed,'preset':preset,**{c:results[prefix+'-intensity-none-'+c]['weight_sum'] for c in ('none','single4','repeated1')},
                             'equal_drive_1':results[prefix+'-equal-drive-none-1']['weight_sum'],'equal_drive_4':results[prefix+'-equal-drive-none-4']['weight_sum']})
            key=prefix+'-retention';before=states[results[key]['parent']];after=states[key]
            weak={(e['source'],e['target']) for e in before['edges'] if e['source'] not in (1001,1002) and e['target'] not in (1001,1002)}
            ends={(e['source'],e['target']) for e in after['edges']}
            strong={(1001,1002),(1002,1001)}
            retention.append({'seed':seed,'preset':preset,'initial_weak':len(weak),'remaining_weak':len(weak&ends),
                              'deleted_weak':len(weak-ends),'strong_remaining':len(strong&ends),'life':results[key]['life'],
                              'support_cross_edges':sum((a==999991)!=(b==999991) for a,b in ends),
                              'final_internal_us':results[key]['clock_end_us'],
                              'passed':not weak&ends and strong<=ends and results[key]['life']!='dead'})
    for key,result in results.items():
        if result['stage']!='probe' or result['cue_intensity']==0:continue
        blank=result['parent']+'-probe-0';a=processes[key];b=processes[blank]
        times=sorted(a.keys()&b.keys());totals={f:0. for f in ('activation','inhibition','direct','associative')};noncue={f:0. for f in totals};peaks={f:0. for f in totals}
        cue={c for c,_ in result['cue']}
        for t,nt in zip(times,times[1:]):
            dt=(nt-t)/1e6
            for channel in a[t].keys()|b[t].keys():
                for f in totals:
                    delta=a[t].get(channel,{}).get(f,0)-b[t].get(channel,{}).get(f,0)
                    totals[f]+=delta*dt;peaks[f]=max(peaks[f],abs(delta))
                    if channel not in cue:noncue[f]+=delta*dt
        cue_effects.append({'key':key,'shared_samples':len(times),'shared_seconds':(times[-1]-times[0])/1e6 if times else 0,
                           'signed_integrals':totals,'noncue_signed_integrals':noncue,'max_abs_node_difference':peaks})
    files=[p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts and p.name not in ('analysis.json','audit.json')]
    allocated=sum(disk_allocation(p)['allocated_bytes'] for p in files)
    analysis={'kernel':'6.1','conditions':264,'encoding_blocks':2,'configuration_combinations':4,
              'topology':topology,'order':order,'strength':strength,'retention':retention,'patterns':patterns,'cue_effects':cue_effects,
              'backgrounds':[{k:v for k,v in r.items() if k in ('seed','preset','condition','nodes','edges','cross_original_edges','input_dose_by_channel')} for r in results.values() if r['family']=='background' and r['stage']=='teaching'],
              'storage':{'logical_bytes':sum(p.stat().st_size for p in files),'allocated_bytes':allocated},
              'wall_seconds':sum(r['wall_seconds'] for r in results.values()),
              'scientific_stop':not all(x['passed'] for x in topology)}
    s.base.original(work/'analysis.json',analysis)
    s.base.original(work/'audit.json',{'passed':True,'conditions':264,'complete_states':528,
                                     'parent_pairs':sum(c['parent'] is not None for c in schedule),'fixed_addressing':True,
                                     'scientific_stop':analysis['scientific_stop']})
    print(json.dumps({k:v for k,v in analysis.items() if k not in ('patterns','cue_effects','backgrounds')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    summarize(p.parse_args().work.resolve())
