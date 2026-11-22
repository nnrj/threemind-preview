"""Read-only state-chain verification and independent prefix scoring."""
import argparse
from copy import deepcopy
from collections import defaultdict
import gzip
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t14_study',HERE/'study.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=t.s


def calculate(case,points,mask):
    codes={k:v^mask for k,v in s.measure.TOKENS.items()}
    correct='C' if case['cue']=='AB' else 'E'
    if case['swap']:correct='E' if correct=='C' else 'C'
    wrong='E' if correct=='C' else 'C'
    start=case['probe_start_us']+round(case['gap_s']*1e6)
    peaks={correct:0.0,wrong:0.0};maximum=[];inhibition=[];sat=0;count=0
    for point in points:
        nodes=[n for n in point['nodes'] if n['channel'] in codes.values()]
        maximum.append(max((n['activation'] for n in nodes),default=0.0))
        inhibition.extend(n['inhibition'] for n in nodes)
        for n in nodes:
            count+=1;sat+=n['activation']>=.95
            if point['time_us']>=start:
                for target in peaks:
                    if n['channel']==codes[target]:peaks[target]=max(peaks[target],n['activation'])
    return {'margin':peaks[correct]-peaks[wrong],'correct':correct,'wrong':wrong,'peaks':peaks,
        'complete':len(points)==1502,'samples':len(points),'minimum':min(maximum,default=0),
        'maximum':max(maximum,default=0),'end':maximum[-1] if maximum else 0,
        'continuous':len(points)==1502 and all(v>1e-6 for v in maximum),
        'saturation_fraction':sat/max(1,count),'maximum_inhibition':max(inhibition,default=0)}


def audit(work):
    t.check(work)
    assert not any((work/n).exists() for n in ('STOP','in-flight.json','audit-final.json'))
    selection=s.read(work/'selection.json')
    phases=['A']+(['B'] if selection['chosen'] else [])
    rows=[];states=0;processes=0;error=0;parents={};historical=[]
    for phase in phases:
        plan=s.read(work/f'phase-{phase}.json')
        assert s.read(work/f'phase-{phase}-summary.json')['stages']==len(plan)
        if phase=='B':assert s.sha(work/'phase-B.json')==s.read(work/'phase-B-frozen.json')['sha256']
        for stage in plan:
            out=work/'cases'/stage['key'];q=s.read(out/'result.json')
            images={k:t.h.get(out/(k+'.rstate.gz')) for k in ('initial','final')}
            for k,image in images.items():
                assert image.digest==q[k+'_sha256']
                assert t.engine(state=image).capture_state().digest==image.digest
                states+=1
            initial,final=(images[k].to_dict() for k in ('initial','final'))
            if phase=='A' and not stage['patch']['separate_inhibition_resources']:
                old_key=stage['key'].replace('-r0/','-u0/')
                old_root=t.t.DATA/'inhibition63-v1'/'cases'/old_key
                for label,image in images.items():
                    prior=t.h.get(old_root/(label+'.rstate.gz'))
                    old,new=deepcopy(prior.to_dict()),deepcopy(image.to_dict())
                    for d in (old,new):
                        d.pop('definition');d.pop('definition_hash')
                        d['config'].pop('separate_inhibition_resources',None)
                    assert old==new, (stage['key'],label,'shared mode changed')
                    historical.append({'key':stage['key'],'boundary':label,
                        'old_sha256':prior.digest,'new_sha256':image.digest,'same_numerical_state':True})
            assert initial['config']==final['config']
            assert all(final['config'][k]==v for k,v in stage['patch'].items())
            assert final['config']['inhibitory_learning_enabled'] and final['config']['inhibition_weight_reinforcement_enabled']
            if stage['parent']:
                parent=t.h.get(work/'cases'/stage['parent']/'final.rstate.gz')
                assert parent.digest==q['parent_sha256']==images['initial'].digest
                parents[stage['key']]=stage['parent']
            else:assert q['parent_sha256'] is None and int(initial['time_us'])==0
            inputs=t.t.inputs(work,stage['case'],stage['mask'])
            assert inputs==s.unpack(out/'inputs.json.gz') and len(inputs)==q['scheduled']
            assert int(final['time_us'])==q['time_us'] and final['life']==q['life']
            if q['life']!='dead':assert q['injected']==len(inputs) and q['time_us']==stage['case']['end_us']
            with gzip.open(out/'course.jsonl.gz','rt',encoding='utf8') as f:
                last=-1
                for line in f:
                    point=json.loads(line);assert point['time_us']>last;last=point['time_us']
            row={k:q[k] for k in ('key','profile','variant','block','cue','time_us','life','wall_seconds','cpu_seconds','snapshot_bytes')}
            row['phase']=phase;row['transport_delta']={k:final['transport'][k]-initial['transport'][k] for k in final['transport']}
            row['events']=final['sequence']-initial['sequence'];row['nodes']=len(final['nodes']);row['edges']=len(final['edges'])
            row['inhibitory_resource_states']=sum(e.get('inhibition_short_term') is not None for e in final['edges'])
            if stage['cue'] not in ('train','wait'):
                points=s.unpack(out/'process.json.gz') if (out/'process.json.gz').exists() else []
                metric=calculate(stage['case'],points,stage['mask']);processes+=1
                if metric['complete']:
                    assert [p['time_us']-stage['case']['probe_start_us'] for p in points]==[0]+list(range(0,15000001,10000))
                for key,value in (q['process'] or {}).items():
                    if isinstance(value,(int,float)):
                        error=max(error,abs(metric[key]-value));assert abs(metric[key]-value)<1e-12
                    else:assert metric[key]==value
                if stage['group']!='prefix':metric.pop('margin',None)
                row['process']=metric
                if stage['group']=='prefix':row['passed']=metric['complete'] and metric['margin']>1e-6
            rows.append(row)
    grouped=defaultdict(list)
    for row in rows:
        if 'passed' in row:grouped[row['phase'],row['profile'],row['variant']].append(row)
    groups=[{'phase':phase,'profile':profile,'variant':variant,
             'passed_blocks':sum(all(r['passed'] for r in members if r['block']==b) for b in (0,1)),
             'rows':members} for (phase,profile,variant),members in grouped.items()]
    result={'passed':True,'scientific_stop':False,'stages':len(rows),'states':states,'processes':processes,
        'max_arithmetic_error':error,'groups':groups,'rows':rows,'parents':parents,'selection':selection,
        'historical_shared_states':historical,
        'wall_seconds':sum(r['wall_seconds'] for r in rows),
        'raw_bytes':sum(p.stat().st_size for p in work.rglob('*') if p.is_file()),
        'resources':{p.name:s.read(p) for p in work.glob('phase-*-resources.json')}}
    assert len(rows)<=60 and result['raw_bytes']<512*2**20
    s.write(work/'analysis-final.json',result)
    s.write(work/'audit-final.json',{k:v for k,v in result.items() if k not in ('rows','groups','parents')})
    print(json.dumps({k:result[k] for k in ('passed','stages','states','processes','max_arithmetic_error','wall_seconds','raw_bytes')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);audit(p.parse_args().work)
