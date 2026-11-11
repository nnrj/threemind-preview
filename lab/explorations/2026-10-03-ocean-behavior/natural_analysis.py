"""Analyse prospective encounters without advancing a model or selecting winners."""
import json
from experiment import WORK
from process_analysis import read,compare,activity_difference
from lab.tools.ocean_cli import read_json


def run():
    output={'scouts':[],'encounters':[]}
    for group in (0,1):
        root=WORK/'natural'/f'g{group}'
        if not (root/'scout/result.json').exists():continue
        output['scouts'].append({'group':group,**read_json(root/'scout/result.json')})
        for task in ('food','hunt','escape'):
            folder=root/task
            if not (folder/'selection.json').exists():continue
            selection=read_json(folder/'selection.json')
            event=selection['encounter'];start=event['trigger']['world_time_us']
            rows={};traces={}
            for op in ('intact','target','matched'):
                result=folder/op/'result.json'
                if not result.exists():continue
                r=read_json(result);r['path']=str(result.parent.relative_to(WORK))
                events=read_json(result.parent/'events.json')
                relevant=[e for e in events if
                    (task=='food' and e['kind']=='nutrient_contact' and e['individual']==event['focal'] and e['particle']==event['target'])
                    or (task!='food' and e['kind']=='capture_started' and {e['predator'],e['individual']}=={event['focal'],event['target']})]
                r['physical_contact_s']=min(((e['time_us']-start)/1e6 for e in relevant),default=None)
                r['specified_target_captured']=any(e['kind']=='body_engulfed' and e['predator']==event['focal']
                    and e['individual']==event['target'] for e in events)
                r['specified_predator_captured_focal']=any(e['kind']=='body_engulfed' and e['predator']==event['target']
                    and e['individual']==event['focal'] for e in events)
                r['focal_events']=[e for e in events if e.get('individual')==event['focal'] or e.get('predator')==event['focal']]
                rows[op]=r;traces[op]=read(r)
            comparisons={}
            if 'intact' in rows:
                for op in ('target','matched'):
                    if op not in rows:continue
                    comparisons[op]={'windows':compare(traces['intact'],traces[op],.8),
                        'target_activity':activity_difference(rows['intact'],rows[op],set(selection['plan']['targets'])),
                        'food_delta':rows[op]['food']-rows['intact']['food'],
                        'capture_delta':rows[op]['captured']-rows['intact']['captured'],
                        'survival_delta':int(rows[op]['physical'])-int(rows['intact']['physical'])}
            output['encounters'].append({'group':group,'task':task,'focal':event['focal'],'target':event['target'],
                'time_us':start,'results':rows,'comparisons':comparisons})
    path=WORK/'natural-findings.json';temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(output,separators=(',',':')),encoding='utf-8');temp.replace(path)
    print(json.dumps({'encounters':len(output['encounters']),
        'completed_forks':sum(len(e['results']) for e in output['encounters'])}))
    return output


if __name__=='__main__':run()
