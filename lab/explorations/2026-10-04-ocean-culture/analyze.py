"""Summarize actual culture endpoints and passive events without rerunning worlds."""
import json
from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json,write_json


def summary(case):
    r=read_json(case/'result.json');watch=read_json(case/'observer.json')
    groups={k:dict(v) for k,v in r['groups'].items()}
    by_id={b['id']:b for b in r['members']}
    for group,g in groups.items():
        ids={i for i,b in by_id.items() if b['cohort']==group}
        stats=[v for i,v in watch['stats'].items() if int(i) in ids]
        g['turning_events']=sum(v['turns'] for v in stats)
        g['active_body_s']=sum(v['observed_us'] for v in stats)/1e6
        g['maximum_generation']=max(by_id[i]['generation'] for i in ids)
        g['combined_individuals']=[int(i) for i,v in watch['stats'].items()
                                   if int(i) in ids and v['turns'] and v['captures']]
        g['share_received']=sum(by_id[i]['share_received'] for i in ids)
        g['share_sent']=sum(by_id[i]['share_sent'] for i in ids)
    return {'case':case.name,'time_us':r['time_us'],'observed_us':r['observed_us'],
        'status':r['status'],'error':r['error'],'wall_seconds':r['wall_seconds'],'groups':groups,
        'association_max_s':r['association_max_us']/1e6,'association_pairs':r['association_pairs'],
        'energy_balance_error':r['energy_balance_error'],
        'improvement_markers':[x for x in watch['markers'] if x[1].startswith('improved-')]}


def main():
    cases=sorted((p.parent for p in (WORK/'cases').glob('*/result.json')),
                 key=lambda p:(int(p.name.rsplit('-',1)[1]),p.name))
    summaries=[summary(p) for p in cases]
    latest={};times={}
    for branch in ('culture','sharing'):
        rows=[r for r in summaries if r['case'].startswith(branch+'-')]
        if rows:
            latest[branch]=max(rows,key=lambda r:r['time_us'])
            times[branch]={r['time_us'] for r in rows}
    common=max(set.intersection(*times.values())) if len(times)==2 and set.intersection(*times.values()) else None
    paired={k:next(r for r in summaries if r['case'].startswith(k+'-') and r['time_us']==common)
            for k in times} if common else {}
    events=[];observations=[]
    for case in cases:
        events.extend(e|{'case':case.name} for e in read_json(case/'events.json')
            if e['kind'] in ('body_engulfed','intake_resource_exchange','association_ended','nutrient_contact','birth'))
        path=case/'observer-events.jsonl'
        if path.exists():
            observations.extend(json.loads(line)|{'case':case.name} for line in path.read_text(encoding='utf-8').splitlines())
    # Follow actual transfer partners, rather than replacing process evidence
    # with only a final population total. Shared prefixes are read once per
    # branch here only to give each branch its inherited history.
    pair_outcomes=[]
    for branch,last in latest.items():
        relevant=[e for e in events if e['case']=='shared-00' or e['case'].startswith(branch+'-')]
        final=read_json(WORK/'cases'/last['case']/'result.json')
        members={b['id']:b for b in final['members']}
        pairs={tuple(sorted((e['donor'],e['receiver']))) for e in relevant
               if e['kind']=='intake_resource_exchange'}
        for pair in sorted(pairs):
            shares=[e for e in relevant if e['kind']=='intake_resource_exchange'
                    and tuple(sorted((e['donor'],e['receiver'])))==pair]
            first=min(e['time_us'] for e in shares)
            ended=[e for e in relevant if e['kind']=='association_ended'
                   and tuple(e['individuals'])==pair and e['time_us']>=first]
            deaths=[e for e in relevant if e['kind']=='body_engulfed'
                    and e['predator'] in pair and e['individual'] in pair and e['time_us']>=first]
            a,b=(members[i] for i in pair)
            relationship='parent-child' if a['parent']==b['id'] or b['parent']==a['id'] else (
                'siblings' if a['parent'] is not None and a['parent']==b['parent'] else 'other')
            pair_outcomes.append({'branch':branch,'individuals':list(pair),
                'relationship':relationship,
                'first_transfer_us':first,'last_transfer_us':max(e['time_us'] for e in shares),
                'transfers':len(shares),'received':sum(e['received'] for e in shares),
                'directions':sorted({(e['donor'],e['receiver']) for e in shares}),
                'first_separation_after_transfer_us':min((e['time_us'] for e in ended),default=None),
                'later_nutrient_contacts':{i:sum(e['kind']=='nutrient_contact' and e['individual']==i
                    and e['time_us']>first for e in relevant) for i in pair},
                'partner_consumptions_after_transfer':deaths,
                'endpoint_members':[members[i] for i in pair]})
    out={'schema':'threemind.ocean-culture-results/1','segments':summaries,'latest':latest,
         'common_endpoint_us':common,'paired_comparison':paired,
         'shared_prefix_counted_once':True,'wall_seconds':sum(r['wall_seconds'] for r in summaries),
         'consumptions':[e for e in events if e['kind']=='body_engulfed'],
         'sharing_events':[e for e in events if e['kind']=='intake_resource_exchange'],
         'association_episodes':[e for e in events if e['kind']=='association_ended' and e['duration_us']>=1000000],
         'sharing_pair_outcomes':pair_outcomes,
         'observations':observations,'archives':[str(p.relative_to(WORK)) for p in sorted((WORK/'event-species').glob('*.tmspecies'))]}
    write_json(HERE/'results.json',out);write_json(WORK/'analysis.json',out)
    print(json.dumps({'segments':len(summaries),'common_us':common,'consumptions':len(out['consumptions']),
                      'sharing_events':len(out['sharing_events']),'archives':len(out['archives'])}))


if __name__=='__main__':main()
