"""Event/lineage summaries for the registered full-habitat selection trial."""
import json
from pathlib import Path
import statistics
from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json,write_json


def summarize(branch, common, cases):
    r=read_json(cases[-1]/'result.json');members={m['id']:m for m in r['members']}
    events=common+[e for p in cases for e in read_json(p/'events.json')]
    captures=[e|{'cohort':members[e['predator']]['cohort'],
        'generation':members[e['predator']]['generation'],
        'radius_mm':members[e['predator']]['radius']*1000} for e in events if e['kind']=='body_engulfed']
    assert all(e['method']=='enclosure' for e in captures)
    candidate=[e for e in captures if e['cohort']=='candidate']
    released=[e['contact_us']/1e6 for e in events if e['kind']=='capture_released']
    worlds={k:{'alive':sum(m['physical'] for m in members.values() if m['cohort']==k),
        'maximum_generation':max(m['generation'] for m in members.values() if m['cohort']==k),
        'radii_mm':[m['radius']*1000 for m in members.values() if m['cohort']==k and m['physical']]}
        for k in ('candidate','other')}
    return {'branch':branch,'seconds':r['time_us']/1e6,'status':r['status'],
        'groups':r['groups'],'traits':worlds,'enclosures':captures,
        'candidate_capture_count':len(candidate),'candidate_predators':sorted({e['predator'] for e in candidate}),
        'offspring_captures':sum(e['generation']>0 for e in candidate),
        'repeated_enclosure':len(candidate)>=3 and len({e['predator'] for e in candidate})>=2,
        'enclosure_starts':sum(e['kind']=='capture_started' for e in events),
        'released_count':len(released),'released_median_s':statistics.median(released) if released else None,
        'zero_energy_captures':sum(e['transferred']==0 for e in captures),
        'capture_energy_received':sum(e['transferred'] for e in captures),
        'capture_shell_cost':sum(e['shell_cost'] for e in captures),
        'after_fork_capture_count':sum(e['time_us']>300000000 for e in captures),
        'energy_error':r['energy_balance_error'],'remaining_nutrients':r['nutrient_count']}


def main():
    shared=WORK/'cases/shared-00'
    common=read_json(shared/'events.json')
    results=[];branch_cases={}
    for branch in ('control','reduced'):
        cases=sorted(p for p in (WORK/'cases').glob(branch+'-*') if (p/'result.json').exists())
        if not cases:continue
        branch_cases[branch]=cases
        results.append(summarize(branch,common,cases))
    # Resource limits may stop one branch's next segment. Compare only actual
    # common endpoints, while retaining every later observation separately.
    endpoints=[{read_json(c/'result.json')['time_us'] for c in cases} for cases in branch_cases.values()]
    common_us=max(set.intersection(*endpoints)) if len(endpoints)==2 else None
    paired=[summarize(b,common,[c for c in cases if read_json(c/'result.json')['time_us']<=common_us])
            for b,cases in branch_cases.items()] if common_us else []
    summaries=[]
    for folder in sorted((WORK/'cases').glob('*')):
        if not (folder/'result.json').exists():continue
        r=read_json(folder/'result.json')
        summaries.append({'case':folder.name,'seconds':r['observed_us']/1e6,'time_us':r['time_us'],
            'status':r['status'],'wall_seconds':r['wall_seconds'],'groups':r['groups']})
    a={'schema':'threemind.species-selection-results/1','branches':results,'segments':summaries,
        'paired_endpoint_us':common_us,'paired_comparison':paired,
        'completion':read_json(WORK/'completion.json') if (WORK/'completion.json').exists() else None,
        'shared_prefix_simulated_once':True,'wall_seconds':sum(r['wall_seconds'] for r in summaries)}
    write_json(WORK/'analysis.json',a)
    write_json(HERE/'results.json',a)
    print(json.dumps(a,ensure_ascii=False))


if __name__=='__main__':main()
