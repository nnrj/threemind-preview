"""Incremental whole-group outcomes, with stopped-body energy caveats visible."""
from collections import Counter
import gzip
import json
from experiment import WORK
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_process import food_heading

SPENT=('consumed_direct','consumed_associative','consumed_inhibition','consumed_maintenance','discarded_total')


def spending(members,cohort):
    return sum(sum(b['core_energy'][k] for k in SPENT) for b in members if b['cohort']==cohort)


def reduce(folder):
    final=read_json(folder/'result.json');initial=final['initial_metrics'];start=initial['time_us']
    timeline=[];living=Counter();cap=None;previous=None
    population_cap=read_json(folder/'protocol.json')['population_limit']
    with gzip.open(folder/'trajectory.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);time_s=(row['time_us']-start)/1e6
            item={'t':time_s,'groups':row['groups']};timeline.append(item)
            if previous:
                for cohort,g in previous['groups'].items():living[cohort]+=g['physical']*(time_s-previous['t'])
            previous=item
            if cap is None and sum(g['physical'] for g in row['groups'].values())>=population_cap:
                cap=time_s
    time_s=final['observed_us']/1e6
    if cap is None and sum(g['physical'] for g in final['groups'].values())>=population_cap:
        cap=time_s
    if previous:
        for cohort,g in previous['groups'].items():living[cohort]+=g['physical']*(time_s-previous['t'])
    timeline.append({'t':time_s,'groups':final['groups']})
    events=read_json(folder/'events.json');members={b['id']:b for b in final['members']};out={}
    for cohort,value in final['groups'].items():
        first=initial['groups'][cohort]
        delta={k:value[k]-first[k] for k in ('food','captures','births','body_unserved')}
        related=lambda i:members[i]['cohort']==cohort
        captures=[e for e in events if e['kind']=='body_engulfed' and related(e['predator'])]
        losses=[e for e in events if e['kind']=='body_engulfed' and related(e['individual'])]
        born=[e for e in events if e['kind']=='birth' and related(e['individual'])]
        core_deaths=[e for e in events if e['kind']=='consciousness_dead' and related(e['individual'])]
        out[cohort]=dict(controller=value['controller'],initial_alive=first['physical'],final_alive=value['physical'],
            powered_bodies=value['powered_bodies'],body_energy=value['body_energy'],core_energy=value['core_energy'],
            delta=delta,living_body_s=living[cohort],food_per_body_s=delta['food']/max(living[cohort],1e-9),
            captured_by_others=len(losses),birth_events=len(born),core_deaths=len(core_deaths),
            other_body_losses=first['physical']+len(born)-value['physical']-len(losses),
            core_energy_spent=spending(final['members'],cohort)-spending(initial['members'],cohort),
            motor_energy=sum(b['motor_energy'] for b in final['members'] if b['cohort']==cohort)-
                sum(b['motor_energy'] for b in initial['members'] if b['cohort']==cohort),
            captures=[{'t':(e['time_us']-start)/1e6,'hunter':e['predator'],'victim':e['individual']} for e in captures])
    if folder.name.startswith('mixed'):
        assert all(members[e['predator']]['cohort']!=members[e['individual']]['cohort'] for e in events if e['kind']=='body_engulfed')
    headings=food_heading(folder/'inputs.jsonl.gz',{i:b['cohort'] for i,b in members.items()})
    for cohort,values in out.items():values['food_heading']=headings.get(cohort)
    result={'case':folder.name,'status':final['status'],'wall_seconds':final['wall_seconds'],
        'groups':out,'timeline':timeline,'cap_time_s':cap,'observation_s':time_s}
    write_json(WORK/'analysis-cases'/f'{folder.name}.json',result);return result


def summarize():
    cases={}
    for path in sorted((WORK/'cases').glob('*/result.json')):
        cache=WORK/'analysis-cases'/f'{path.parent.name}.json'
        cases[path.parent.name]=read_json(cache) if cache.exists() else reduce(path.parent)
    out={'cases':cases,'independent_source_worlds':2,'independent_mixed_worlds':2}
    temp=WORK/'findings.tmp';temp.write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8');temp.replace(WORK/'findings.json')
    print(json.dumps({k:{'status':v['status'],'groups':{g:{key:value for key,value in data.items() if key!='captures'}
        for g,data in v['groups'].items()}} for k,v in cases.items()}))
    return out


if __name__=='__main__':summarize()
