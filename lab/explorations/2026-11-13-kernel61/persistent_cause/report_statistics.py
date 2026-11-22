"""Descriptive costs and intervention fields, after the scientific audits."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import investigate as h

def read(path):return json.loads(path.read_bytes())

def summarize(work):
    a=read(work/'audit.json');b=read(work/'audit-novelty.json')
    assert a['passed'] and b['passed'] and a['stages']+b['stages']==476
    cases=sum((read(work/n) for n in ('cases.json','supplement-cases.json','novelty-cases.json')),[])
    times=defaultdict(float);stages=defaultdict(int);changes={};kinds=defaultdict(int);births=[];waiting_task_inputs=0
    for c in cases:
        folder=work/'cases'/c['key'];r=read(folder/'result.json')
        times[c['variant']]+=r['wall_seconds'];stages[c['variant']]+=1;kinds[c['kind']]+=1
        delta=read(folder/'intervention.json')['changes']
        if delta:changes[c['key']]=delta
        if c['kind']=='readout_wait':
            waiting_task_inputs+=sum(any(ch in h.e.materials.TOKENS.values() for ch,_ in x['stimulus']['channels'])
                                     for x in h.e.unpacked(folder/'inputs.json.xz'))
        if c['parent'] is None:
            config=h.e.base.image(folder/'initial.tmind').to_dict()['config']
            declared={'seed':h.e.materials.SEED,**c['initial_config'],**c['birth_patch']}
            assert all(config[k]==v for k,v in declared.items()),c['key']
            births.append({'key':c['key'],'declared':declared})
    resources={name:read(work/name) for name in ('apparatus-resources.json','primary-resources.json',
        'supplement-apparatus-resources.json','supplement-resources.json','novelty-apparatus-resources.json','resource-summary.json')
        if (work/name).exists()}
    walls={n:read(work/n)['wall_seconds'] for n in ('summary.json','supplement-summary.json','novelty-summary.json')}
    result={'stages':476,'kinds':dict(kinds),'complete_states':a['complete_states']+b['complete_states'],
        'inputs':a['inputs']+b['inputs'],'times_by_condition':dict(times),'stages_by_condition':dict(stages),
        'scientific_host_seconds':sum(walls.values()),'host_times':walls,
        'peak_private_bytes':max(r['peak_private_bytes'] for r in resources.values()),
        'minimum_available_bytes':{k:min(r['minimum_available_bytes'][k] for r in resources.values())
            for k in ('commit','ram','system_disk','data_disk')},
        '61_to_51_recorded_stage_time_ratio':times['v61']/times['v51'],
        'maximum_arithmetic_error':max(a['maximum_arithmetic_error'],b['maximum_arithmetic_error']),
        'intervention_changes':changes,'declared_births_checked':births,'waiting_task_inputs':waiting_task_inputs,
        'registered_after_initial_observations':['supplement-cases.json','novelty-cases.json']}
    out=work/'report-statistics.json';raw=json.dumps(result,ensure_ascii=False,sort_keys=True).encode('utf8')
    if out.exists():assert out.read_bytes()==raw
    else:
        with out.open('xb') as stream:stream.write(raw)
    print(json.dumps({k:v for k,v in result.items() if k not in ('intervention_changes','declared_births_checked')},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);args=p.parse_args();summarize(args.work)
