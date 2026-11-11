import json
import statistics as st
from experiment import WORK,HERE
from lab.tools.ocean_cli import read_json,write_json

def summary():
    result={'main':[],'closed':[],'probes':[],'event_changes':[]}
    for base,key in ((WORK/'cases','main'),(WORK/'closed-loop','closed')):
        for f in sorted(base.glob('*/process-summary.json')):
            r=read_json(f);result[key].append({k:v for k,v in r.items() if k not in ('counters','series','interpretation')})
    for g in (0,1):
        for at in (200,600):
            name=f'g{g}-core-{at}'+('-retry1' if (g,at)==(0,600) else '')
            root=WORK/'probes'/name;r=read_json(root/'summary.json');p=read_json(root/'process-analysis.json')
            balanced=read_json(WORK/'probes'/f'g{g}-core-{at}-balanced'/'summary.json')
            usable=[x for x in r['individuals'] if x.get('plan',{}).get('applicable') and 'comparisons' in x]
            clean=[x for x in p['individuals'] if x.get('target',{}).get('clean_prefix_samples',0)>0]
            born=balanced['individuals']
            result['probes'].append({'group':g,'at':at,'n':len(usable),'clean_n':len(clean),
                'clean_activity_reduced':sum(x['target']['clean_target_signed_mean']>0 for x in clean),
                'clean_action_changed':sum(x['target']['clean_motor_peak']>1e-8 for x in clean),
                'target_motor_mean':st.mean(x['comparisons']['target']['motor_mean_absolute'] for x in usable),
                'matched_motor_mean':st.mean(x['comparisons']['matched']['motor_mean_absolute'] for x in usable),
                'restoration_max':max(x['comparisons']['restore']['motor_peak_absolute'] for x in usable),
                'balanced_birth_different':sum(x['experience']['motor_mean_absolute']>1e-8 for x in born),
                'balanced_birth_mean':st.mean(x['experience']['motor_mean_absolute'] for x in born),
                'all_births_active':all(x['blank_active_samples'] and x['experienced_active_samples'] for x in born),
                'graft_closer_than_blank':sum(x['graft']['target']['motor_mean_absolute']<x['experience']['motor_mean_absolute'] for x in born if x['graft']),
                'graft_closer_than_matched':sum(x['graft']['target']['motor_mean_absolute']<x['graft']['matched']['motor_mean_absolute'] for x in born if x['graft'])})
    for g in (0,1):
        base=read_json(WORK/'closed-loop'/f'g{g}-sham'/'events.json')
        nutrients={x['particle']:x for x in base if x['kind']=='nutrient_contact'}
        kills={x['individual']:x for x in base if x['kind']=='body_engulfed'}
        for op in ('target','matched','history-strength-zero','region','region-matched'):
            events=read_json(WORK/'closed-loop'/f'g{g}-{op}'/'events.json')
            altered={x['particle']:x for x in events if x['kind']=='nutrient_contact'}
            pred={x['individual']:x for x in events if x['kind']=='body_engulfed'}
            changes=[]
            for particle in nutrients.keys()|altered.keys():
                a,b=nutrients.get(particle),altered.get(particle)
                if a is None or b is None or a['individual']!=b['individual']:
                    changes.append({'particle':particle,'sham':a,'altered':b})
            killchanges=[{'victim':i,'sham':kills.get(i),'altered':pred.get(i)} for i in kills.keys()|pred.keys()
                if kills.get(i,{}).get('predator')!=pred.get(i,{}).get('predator')]
            result['event_changes'].append({'group':g,'operation':op,'food_recipient_or_presence_changes':changes,'capture_changes':killchanges})
    return result

if __name__=='__main__':
    r=summary();write_json(WORK/'findings.json',r);print(json.dumps(r,ensure_ascii=False,indent=2))
