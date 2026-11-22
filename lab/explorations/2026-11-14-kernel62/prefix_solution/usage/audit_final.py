"""Append verification of the usage experiment to the preserved primary audit."""
import argparse
from collections import defaultdict
import gzip
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t11_usage_driver',HERE/'driver.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
t=d.t;s=t.s
base=t.module('r51t11_original_audit',HERE.parent/'audit.py')


def audit(work):
    d.check(work);t.check(work)
    assert not any((work/n).exists() for n in ('STOP','in-flight.json','audit-final.json'))
    old=s.read(work/'analysis.json');assert old['passed'] and old['stages']==168
    selected=s.read(work/'usage-selection.json');phases=('E','G','H') if selected['chosen'] else ('E',)
    rows=[];states=0;processes=0;max_error=0.0;configurations={}
    for phase in phases:
        plan=s.read(work/f'phase-{phase}.json');frozen=s.read(work/f'phase-{phase}-frozen.json')
        assert s.sha(work/f'phase-{phase}.json')==frozen['sha256']
        for rel,sha in frozen['sources'].items():assert s.sha(t.ROOT/rel)==sha,rel
        assert s.read(work/f'phase-{phase}-summary.json')['stages']==len(plan)
        for stage in plan:
            out=work/'cases'/stage['key'];q=s.read(out/'result.json')
            images={name:t.h.get(out/(name+'-intervention.rstate.gz' if name=='before' else name+'.rstate.gz'))
                    for name in ('before','initial','final')}
            for name,image in images.items():
                assert image.digest==q[name+'_sha256']
                assert d.engine(state=image).capture_state().digest==image.digest;states+=1
            before,initial,final=[images[k].to_dict() for k in ('before','initial','final')]
            if stage.get('parent'):
                parent=t.h.get(work/'cases'/stage['parent']/'final.rstate.gz')
                assert parent.digest==images['before'].digest==q['parent_sha256']
            else:assert q['parent_sha256'] is None and int(before['time_us'])==0
            assert before['config']|stage['case'].get('patch',{})==initial['config']==final['config']
            assert before['time_us']==initial['time_us']
            assert int(final['time_us'])==q['time_us'] and final['life']==q['life']
            inputs=t.inputs(work,stage['case'],stage['mask'])
            assert inputs==s.unpack(out/'inputs.json.gz') and len(inputs)==q['scheduled']
            if q['life']!='dead':assert q['time_us']==stage['case']['end_us'] and q['injected']==len(inputs)
            with gzip.open(out/'course.jsonl.gz','rt',encoding='utf8') as stream:
                last=-1
                for line in stream:
                    p=json.loads(line);assert p['time_us']>last;last=p['time_us']
            row={k:q[k] for k in ('key','group','variant','block','cue','time_us','life','wall_seconds')}
            row.update(phase=phase,patch=stage['patch'],mask=stage['mask'],seed=stage['seed'],
                nodes=len(final['nodes']),edges=len(final['edges']),
                transport_delta={k:final['transport'][k]-initial['transport'][k] for k in final['transport']})
            configurations[stage['key']]=initial['config']
            if stage['case'].get('probe_start_us') is not None:
                points=s.unpack(out/'process.json.gz') if (out/'process.json.gz').exists() else []
                if points:processes+=1
                metric=base.calculation(stage['case'],points,stage['mask'])
                if metric['complete']:
                    assert [p['time_us']-stage['case']['probe_start_us'] for p in points]==[0]+list(range(0,15000001,10000))
                if q['process']:
                    for k,v in q['process'].items():
                        max_error=max(max_error,abs(metric[k]-v));assert abs(metric[k]-v)<1e-12
                else:assert q['life']=='dead' and not points
                row['process']=metric
                row['passed']=metric['complete'] and (metric['margin']>1e-6 if stage['group']=='prefix' else metric['continuous'])
            rows.append(row)
    groups=[];grouped=defaultdict(list)
    for row in rows:
        if 'passed' in row:grouped[(row['phase'],row['variant'],row['group'])].append(row)
    for (phase,variant,group),members in grouped.items():
        groups.append({'phase':phase,'variant':variant,'group':group,
            'passed_blocks':sum(all(x['passed'] for x in members if x['block']==b) for b in (0,1)),
            'rows':members})
    pairs=[]
    if selected['chosen']:
        name=selected['chosen']['name']
        for b in (0,1):
            assert configurations[f'E/{name}/{b}/train']==configurations[f'G/{name}/{b}/train']
            pairs.append({'profile':name,'block':b,'identical_complete_configuration':True})
    result=dict(old)
    result.update(stages=old['stages']+len(rows),states=old['states']+states,processes=old['processes']+processes,
        max_arithmetic_error=max(old['max_arithmetic_error'],max_error),
        groups=old['groups']+groups,rows=old['rows']+rows,
        wall_seconds=old['wall_seconds']+sum(x['wall_seconds'] for x in rows),
        raw_bytes=sum(p.stat().st_size for p in work.rglob('*') if p.is_file()),usage_selection=selected,
        original_analysis_sha256=s.sha(work/'analysis.json'),original_audit_sha256=s.sha(work/'audit.json'),
        usage_complete_configuration_checks=pairs,
        resources={p.name:s.read(p) for p in work.glob('phase-*-resources.json')})
    assert result['stages']<=192 and result['raw_bytes']<2**30
    s.write(work/'analysis-final.json',result)
    s.write(work/'audit-final.json',{k:v for k,v in result.items() if k not in ('groups','rows','parents','decision','usage_selection')})
    print(json.dumps({k:result[k] for k in ('passed','stages','states','processes','wall_seconds','max_arithmetic_error','raw_bytes')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();audit(a.work)
