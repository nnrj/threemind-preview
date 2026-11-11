"""Read completed full habitats and event records; never advance their state."""
import json
from pathlib import Path
from experiment import HERE,WORK,PRIOR
from lab.tools.ocean_cli import read_json,write_json


def main():
    baseline=read_json(PRIOR/'cases/shared-00/result.json')
    initial=read_json(WORK/'source/observer.json')
    cases=sorted(p.parent for p in (WORK/'cases').glob('*/result.json'))
    summaries=[];observations=[];consumptions=[];starts=[];releases=[]
    for case in cases:
        r=read_json(case/'result.json');watch=read_json(case/'observer.json')
        groups={};by_id={b['id']:b for b in r['members']}
        for source,g in r['groups'].items():
            ids={i for i,b in by_id.items() if b['cohort']==source}
            turns=sum(v['turns'] for i,v in watch['stats'].items() if int(i) in ids)
            before=sum(v['turns'] for i,v in initial['stats'].items() if int(i) in ids)
            groups[source]=dict(g)|{
                'new_food':g['food']-baseline['groups'][source]['food'],
                'new_births':g['births']-baseline['groups'][source]['births'],
                'new_turns':turns-before,'turns_including_prefix':turns,
                'maximum_generation':max(by_id[i]['generation'] for i in ids),
                'combined_individuals':[int(i) for i,v in watch['stats'].items()
                    if int(i) in ids and v['turns'] and v['captures']]}
        summaries.append({'case':case.name,'time_us':r['time_us'],'observed_us':r['observed_us'],
            'status':r['status'],'error':r['error'],'wall_seconds':r['wall_seconds'],
            'groups':groups,'energy_balance_error':r['energy_balance_error']})
        for e in read_json(case/'events.json'):
            row=e|{'case':case.name}
            if e['kind'] in ('body_consumed_by_coverage','body_engulfed'):consumptions.append(row)
            elif e['kind']=='capture_started':starts.append(row)
            elif e['kind']=='capture_released':releases.append(row)
        path=case/'observer-events.jsonl'
        if path.exists():observations.extend(json.loads(x)|{'case':case.name}
            for x in path.read_text(encoding='utf-8').splitlines())
    latest={b:max((r for r in summaries if r['case'].startswith(b)),
                 key=lambda r:r['time_us'],default=None) for b in ('turning','coverage')}
    inventory=[]
    traits=('radius','elongation','thrust','grip','shell','reflectance','sensor_range')
    for branch,endpoint in latest.items():
        if endpoint is None:continue
        folder=WORK/'cases'/endpoint['case']
        members={b['id']:b for b in read_json(folder/'result.json')['members']}
        scores=read_json(folder/'observer.json')['stats']
        archived={}
        for o in sorted(observations,key=lambda o:o['time_us']):
            if o['case'].startswith(branch+'-') and o.get('bundle'):
                archived[o['individual']]=o
        for identity,o in sorted(archived.items()):
            b=members[identity];parent=members.get(b['parent'])
            inventory.append({'branch':branch,'individual':identity,'cohort':b['cohort'],
                'generation':b['generation'],'parent':b['parent'],
                'counts':scores[str(identity)],'physical_at_endpoint':b['physical'],
                'body_energy_at_endpoint':b['storage'],
                'archive_time_us':o['time_us'],'bundle':str(Path(o['bundle']).relative_to(WORK)),
                'traits':{k:b[k] for k in traits},
                'parent_traits':{k:parent[k] for k in traits} if parent else None})
    out={'schema':'threemind.ocean-split-results/1','activation':read_json(WORK/'activation.json'),
        'segments':summaries,'latest':latest,'wall_seconds':sum(r['wall_seconds'] for r in summaries),
        'consumptions':consumptions,'capture_starts':starts,'capture_releases':releases,
        'observations':observations,'candidate_inventory':inventory,'archives':[str(p.relative_to(WORK))
            for p in sorted((WORK/'event-species').glob('*.tmspecies'))]}
    write_json(HERE/'results.json',out);write_json(WORK/'analysis.json',out)
    print(json.dumps({'segments':len(summaries),'consumptions':len(consumptions),
                      'archives':len(out['archives']),'wall_minutes':out['wall_seconds']/60}))


if __name__=='__main__':main()
