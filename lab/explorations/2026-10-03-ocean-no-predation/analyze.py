"""Summarize predation-disabled populations and their fixed E32 references."""
from collections import Counter
import gzip
import json
from experiment import HERE,WORK,E32
from lab.tools.ocean_cli import read_json,write_json


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:yield json.loads(line)


def reduce_case(folder):
    final=read_json(folder/'result.json');p=read_json(folder/'protocol.json')
    timeline=[];cap=None;maximum=0
    for row in rows(folder/'trajectory.jsonl.gz'):
        alive=sum(b['physical'] for b in row['members']);maximum=max(maximum,alive)
        timeline.append({'time_s':row['time_us']/1e6,'alive':alive,'food':sum(b['grains'] for b in row['members'])})
        if cap is None and alive>=p['population_limit']:cap=row['time_us']/1e6
    alive=sum(b['physical'] for b in final['members']);food=sum(b['grains'] for b in final['members'])
    maximum=max(maximum,alive)
    timeline.append({'time_s':final['time_us']/1e6,'alive':alive,'food':food})
    if cap is None and alive>=p['population_limit']:cap=final['time_us']/1e6
    events=read_json(folder/'events.json');kinds=Counter(e['kind'] for e in events)
    summary={'case':folder.name,'status':final['status'],'food':food,'alive':alive,
        'births':len(final['members'])-len(final['initial_metrics']['members']),
        'living_body_s':final['living_body_s'],'food_per_body_s':food/max(final['living_body_s'],1e-9),
        'captures':final['totals']['predations'],'maximum_alive':maximum,'cap':p['population_limit'],
        'first_observed_cap_s':cap,'observation_s':final['observed_us']/1e6,
        'body_failures':dict(Counter(b['body_failure'] for b in final['members'] if not b['physical'])),
        'core_deaths':kinds['consciousness_dead'],'wall_seconds':final['wall_seconds'],'trajectory':timeline}
    if summary['captures']!=0:raise ValueError('unexpected consumption with predation disabled')
    write_json(WORK/'analysis-cases'/f'{folder.name}.json',summary)
    return summary


def summarize():
    cases={}
    for file in sorted((WORK/'cases').glob('*/result.json')):
        cache=WORK/'analysis-cases'/f'{file.parent.name}.json'
        cases[file.parent.name]=read_json(cache) if cache.exists() else reduce_case(file.parent)
    paired=[]
    for g in (0,1):
        core=cases.get(f'g{g}-core');random=cases.get(f'g{g}-random')
        if core is None or random is None:continue
        reference={m:read_json(E32/'analysis-cases'/f'g{g}-{m}.json') for m in ('core','random')}
        keys=('food','alive','births','living_body_s','food_per_body_s')
        paired.append({'group':g,'without_predation_core_minus_random':{k:core[k]-random[k] for k in keys},
            'with_predation_core_minus_random':{k:reference['core'][k]-reference['random'][k] for k in keys},
            'without_minus_with':{m:{k:cases[f'g{g}-{m}'][k]-reference[m][k] for k in keys} for m in ('core','random')}})
    out={'cases':cases,'paired':paired,'independent_world_seeds':2,
         'cap_time_resolution_s':.1,'cap_time_censoring_s':120}
    temporary=WORK/'findings.tmp';temporary.write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
    temporary.replace(WORK/'findings.json')
    print(json.dumps({'completed':len(cases),'cases':{k:{x:y for x,y in v.items() if x!='trajectory'} for k,v in cases.items()},'paired':paired}))
    return out


if __name__=='__main__':summarize()
