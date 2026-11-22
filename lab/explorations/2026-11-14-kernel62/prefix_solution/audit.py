"""Independent read-only recomputation from saved R51t11 observations."""
import argparse
from collections import defaultdict
import gzip
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t11_audit_study',HERE/'study.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=t.s
fallback=t.module('r51t11_audit_routing',HERE/'fallback.py')
t.engine=fallback.factory(t.engine)


def calculation(case,points,mask):
    channels={k:v^mask for k,v in s.measure.TOKENS.items()}
    correct=('C' if case['cue']=='AB' else 'E')
    if case['swap']:correct='E' if correct=='C' else 'C'
    wrong='E' if correct=='C' else 'C'
    start=case['probe_start_us']+round(case['gap_s']*1e6)
    peaks={correct:0.0,wrong:0.0};maximum=[];inhibition=[];sat=0;count=0
    for p in points:
        task=[n for n in p['nodes'] if n['channel'] in channels.values()]
        maximum.append(max((n['activation'] for n in task),default=0.0))
        inhibition.extend(n['inhibition'] for n in task)
        for n in task:
            count+=1;sat+=n['activation']>=.95
            if p['time_us']>=start:
                for target in peaks:
                    if n['channel']==channels[target]:peaks[target]=max(peaks[target],n['activation'])
    return {'margin':peaks[correct]-peaks[wrong],'correct':correct,'wrong':wrong,'peaks':peaks,
        'complete':len(points)==1502,'samples':len(points),'minimum':min(maximum,default=0),
        'maximum':max(maximum,default=0),'end':maximum[-1] if maximum else 0,
        'continuous':len(points)==1502 and all(v>1e-6 for v in maximum),
        'saturation_fraction':sat/max(1,count),'maximum_inhibition':max(inhibition,default=0)}


def audit(work):
    t.check(work)
    assert not any((work/n).exists() for n in ('STOP','in-flight.json','audit.json'))
    phases=sorted(p for p in work.glob('phase-*.json') if p.stem.count('-')==1)
    assert phases and (work/'phase-D-summary.json').exists()
    rows=[];states=0;observations=0;max_error=0;parents={};configurations={};phase_results={}
    for file in phases:
        phase=file.stem[-1];plan=s.read(file)
        assert s.read(work/f'phase-{phase}-summary.json')['stages']==len(plan)
        if phase!='A':
            frozen=s.read(work/f'phase-{phase}-frozen.json');assert s.sha(file)==frozen['sha256']
            for rel,sha in frozen['sources'].items():assert s.sha(t.ROOT/rel)==sha,rel
        for stage in plan:
            out=work/'cases'/stage['key'];q=s.read(out/'result.json')
            images={k:t.h.get(out/(k+'-intervention.rstate.gz' if k=='before' else k+'.rstate.gz'))
                    for k in ('before','initial','final')}
            for k,image in images.items():
                assert image.digest==q[k+'_sha256']
                # Validation loads the whole state and never advances it.
                assert t.engine(state=image).capture_state().digest==image.digest
                states+=1
            before,initial,final=[images[k].to_dict() for k in ('before','initial','final')]
            if stage.get('parent'):
                parent=t.h.get(work/'cases'/stage['parent']/'final.rstate.gz')
                assert parent.digest==q['parent_sha256']==images['before'].digest
                parents[stage['key']]=stage['parent']
            else:assert q['parent_sha256'] is None and int(before['time_us'])==0
            patch=stage['case'].get('patch',{})
            assert before['config']|patch==initial['config']==final['config']
            assert before['time_us']==initial['time_us']
            assert int(final['time_us'])==q['time_us'] and final['life']==q['life']
            inputs=t.inputs(work,stage['case'],stage['mask'])
            assert inputs==s.unpack(out/'inputs.json.gz') and len(inputs)==q['scheduled']
            assert q['injected']<=len(inputs)
            if q['life']!='dead':assert q['injected']==len(inputs) and q['time_us']==stage['case']['end_us']
            with gzip.open(out/'course.jsonl.gz','rt',encoding='utf8') as f:
                last=-1
                for line in f:
                    p=json.loads(line);assert p['time_us']>last;last=p['time_us']
            row={k:q[k] for k in ('key','group','variant','block','cue','time_us','life','wall_seconds')}
            row['phase']=phase;row['patch']=stage['patch'];row['mask']=stage['mask'];row['seed']=stage['seed']
            row['transport_delta']={k:final['transport'][k]-initial['transport'][k] for k in final['transport']}
            row['nodes']=len(final['nodes']);row['edges']=len(final['edges'])
            configurations[stage['key']]=initial['config']
            if (out/'process.json.gz').exists():
                points=s.unpack(out/'process.json.gz');observations+=1
                metric=calculation(stage['case'],points,stage['mask'])
                if metric['complete']:
                    assert [p['time_us']-stage['case']['probe_start_us'] for p in points]==[0]+list(range(0,15000001,10000))
                for key,value in q['process'].items():
                    if isinstance(value,(int,float)):
                        max_error=max(max_error,abs(metric[key]-value));assert abs(metric[key]-value)<1e-12
                    else:assert metric[key]==value
                row['process']=metric
                row['passed']=metric['complete'] and (metric['margin']>1e-6 if stage['group']=='prefix' else metric['continuous'])
            elif stage['case'].get('probe_start_us') is not None:
                assert q['process'] is None and q['life']=='dead'
                row['process']=calculation(stage['case'],[],stage['mask']);row['passed']=False
            rows.append(row)
        phase_results[phase]=s.read(work/f'phase-{phase}-summary.json')
    grouped=defaultdict(list)
    for row in rows:
        if 'passed' in row:grouped[(row['phase'],row['variant'],row['group'])].append(row)
    groups=[]
    for (phase,variant,group),members in grouped.items():
        passed=sum(all(x['passed'] for x in members if x['block']==b) for b in (0,1))
        groups.append({'phase':phase,'variant':variant,'group':group,'passed_blocks':passed,'rows':members})
    config_pairs=[]
    for g in s.read(work/'phase-C-selection.json')['groups']:
        for b in (0,1):
            prefix=next(k for k in g['prefix'] if k.endswith(f'/{b}/train'))
            persistent=next(k for k in g['persistent'] if k.endswith(f'/persistent-{b}/train'))
            assert configurations[prefix]==configurations[persistent],g['name']
            config_pairs.append({'profile':g['name'],'block':b,'identical_complete_configuration':True})
    result={'passed':True,'scientific_stop':False,'stages':len(rows),'states':states,'processes':observations,
        'max_arithmetic_error':max_error,'groups':groups,'rows':rows,'parents':parents,
        'phases':phase_results,'wall_seconds':sum(r['wall_seconds'] for r in rows),
        'raw_bytes':sum(p.stat().st_size for p in work.rglob('*') if p.is_file()),
        'decision':s.read(work/'phase-D-selection.json'),
        'resources':{p.name:s.read(p) for p in work.glob('phase-*-resources.json')},
        'same_complete_configuration_checks':config_pairs}
    assert result['stages']<=192 and result['raw_bytes']<2**30
    s.write(work/'analysis.json',result)
    s.write(work/'audit.json',{k:v for k,v in result.items() if k not in ('groups','rows','parents','decision')})
    print(json.dumps({k:result[k] for k in ('passed','stages','states','processes','max_arithmetic_error','wall_seconds','raw_bytes')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();audit(a.work)
