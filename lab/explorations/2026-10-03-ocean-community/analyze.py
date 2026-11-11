"""Single streaming reduction per completed case; preserve raw observations."""
import argparse
import gzip
import json
import math
from pathlib import Path
import numpy as np
from experiment import WORK
from lab.tools.ocean_cli import read_json,write_json


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:yield json.loads(line)


def average(values):return float(np.mean(values)) if values else None


def reduce_case(folder):
    result=read_json(folder/'result.json');initial=result['initial_metrics']
    t0=initial['time_us'];i=result['focal'];p=read_json(folder/'protocol.json')
    def total(key,items):return sum(x[key] for x in items)
    summary={'case':folder.name,'status':result['status'],'observed_s':result['observed_us']/1e6,
        'initial_bodies':len(initial['members']),'initial_alive':total('physical',initial['members']),
        'initial_nutrients':initial['nutrient_count'],'final_nutrients':result['nutrient_count'],
        'food':total('grains',result['members'])-total('grains',initial['members']),
        'captures':result['totals']['predations']-initial['totals']['predations'],
        'births':len(result['members'])-len(initial['members']),
        'alive':total('physical',result['members']),'living_body_s':result['living_body_s'],
        'wall_seconds':result['wall_seconds'],'mean_command_change':result['mean_command_change'],
        'mean_action_square':result['mean_action_square'],'focal':i}
    summary['food_per_body_s']=summary['food']/max(1e-9,summary['living_body_s'])
    sums={k:0. for k in ('toward','alignment','speed','gradient','n','angular_n')}
    for row in rows(folder/'inputs.jsonl.gz'):
        for item in row['inputs']:
            raw=item['raw'];action=item['action'];gx,gy=raw[1]-raw[3],raw[2]-raw[4]
            g=math.hypot(gx,gy);speed=math.hypot(*action[:2])
            if g<=1e-10:continue
            toward=(gx*action[0]+gy*action[1])/g
            sums['toward']+=toward;sums['speed']+=speed;sums['gradient']+=g;sums['n']+=1
            if speed>1e-10:sums['alignment']+=toward/speed;sums['angular_n']+=1
    summary['food_gradient']={k:sums[k]/max(1,sums['angular_n'] if k=='alignment' else sums['n'])
        for k in ('toward','alignment','speed','gradient')}
    summary['food_gradient']['observations']=int(sums['n'])
    events=read_json(folder/'events.json');focal_events=[]
    if i is not None:
        focal=[r for r in rows(folder/'focal.jsonl.gz') if r['time_us']>=60000000]
        if focal:
            before=focal[0]['body'];after=next(b for b in result['members'] if b['id']==i)
            summary['focal_outcome']={'food':after['grains']-before['grains'],'captures':after['captured']-before['captured'],
                'alive':after['physical'],'consumed_by':after['consumed_by'],'body_failure':after['body_failure'],
                'motor_energy':after['motor_energy']-before['motor_energy'],'path_m':after['path_m']-before['path_m']}
            summary['focal_process']={}
            for task in ('food','hunt','escape'):
                local=[r['objects'][task] for r in focal if task in r['objects'] and
                    r['objects'][task]['gap'] is not None and p['contact_skin_m']<r['objects'][task]['gap']<r['body']['sensor_range']]
                summary['focal_process'][task]={'observed_s':len(local)*.1,
                    **{k:average([r[k] for r in local if r[k] is not None])
                       for k in ('toward_action','toward_velocity','closing_velocity')}}
        focal_events=[e for e in events if e['time_us']>=60000000 and (e.get('individual')==i or e.get('predator')==i)]
    summary['focal_events']=focal_events
    write_json(WORK/'analysis-cases'/f'{folder.name}.json',summary)
    return summary


def focal_trace(folder):
    return {r['time_us']:r for r in rows(folder/'focal.jsonl.gz') if r['time_us']>=60000000}


def action_compare(a,b):
    common=sorted(set(a)&set(b));out={}
    for end in (2,10,60):
        ts=[t for t in common if t<60000000+end*1000000 and a[t]['body']['physical'] and b[t]['body']['physical']]
        differences=[np.asarray(a[t]['action'])-b[t]['action'] for t in ts]
        values=np.asarray(differences)
        out[str(end)]={'common_alive_s':len(ts)*.1,'action_mae':float(np.abs(values).mean()) if ts else None,
            'action_peak':float(np.abs(values).max()) if ts else None,
            'first_change_s':next(((t-60000000)/1e6 for t,d in zip(ts,differences) if np.abs(d).max()>1e-8),None)}
    return out


def activity_trace(folder):
    return {r['time_us']:r for r in rows(folder/'activity.jsonl.gz') if r['time_us']>=61000000}


def activity_compare(a,b,targets):
    total_a=total_b=0.;count=0;first=None
    for t in sorted(set(a)&set(b)):
        if t>=70000000:continue  # First ten seconds after intervention, first one excluded.
        direct=set(a[t]['recent_channels'])|set(b[t]['recent_channels'])
        nb={n['id']:n for n in b[t]['nodes']}
        for n in a[t]['nodes']:
            if n['id'] not in targets or n['channel'] in direct or n['id'] not in nb:continue
            x,y=n['activation'],nb[n['id']]['activation'];total_a+=x*.1;total_b+=y*.1;count+=1
            if first is None and abs(x-y)>1e-8:first=(t-60000000)/1e6
    return {'common_uncued_node_samples':count,'intact_activation_seconds':total_a,'other_activation_seconds':total_b,
            'intact_minus_other':total_a-total_b,'first_difference_s':first}


def summarize():
    summaries={}
    for f in sorted((WORK/'cases').glob('*/result.json')):
        cache=WORK/'analysis-cases'/f'{f.parent.name}.json'
        summaries[f.parent.name]=read_json(cache) if cache.exists() else reduce_case(f.parent)
    out={'cases':summaries,'paired_worlds':[],'focal_comparisons':{},'independent_world_seeds':2}
    for g in (0,1):
        base=f'g{g}';normal=summaries.get(base+'-core');random=summaries.get(base+'-random')
        if normal and random:
            out['paired_worlds'].append({'group':g,'core_minus_random':{k:normal[k]-random[k] for k in
                ('food','captures','births','alive','living_body_s','food_per_body_s','mean_command_change','mean_action_square')},
                'food_gradient_toward_difference':normal['food_gradient']['toward']-random['food_gradient']['toward'],
                'food_gradient_alignment_difference':normal['food_gradient']['alignment']-random['food_gradient']['alignment']})
        key=base+'-core';selection=WORK/'cases'/key/'selection.json'
        if not selection.exists() or read_json(selection)['individual'] is None:continue
        chosen=read_json(selection);trace={};activity={}
        for op in ('core','target','matched','random','experienced','blank','graft','graft-matched'):
            name=base+('-focal-random' if op=='random' else '-'+op)
            if name not in summaries or summaries[name]['focal'] is None:continue
            trace[op]=focal_trace(WORK/'cases'/name)
            if op in ('core','target','matched'):activity[op]=activity_trace(WORK/'cases'/name)
        comparisons={}
        for left,right in (('core','target'),('core','matched'),('core','random'),('experienced','blank'),
                           ('experienced','graft'),('experienced','graft-matched')):
            if left in trace and right in trace:comparisons[left+' vs '+right]=action_compare(trace[left],trace[right])
        for op in ('target','matched'):
            if 'core' in activity and op in activity:
                comparisons['uncued core vs '+op]=activity_compare(activity['core'],activity[op],set(chosen['plan']['targets']))
        out['focal_comparisons'][base]={'individual':chosen['individual'],'selected_edges':chosen['plan']['selected_edges'],
            'matching_mean_error':average(chosen['plan']['matching_errors']),'comparisons':comparisons}
    temporary=WORK/'findings.tmp'
    temporary.write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    temporary.replace(WORK/'findings.json')
    return out


if __name__=='__main__':
    out=summarize()
    print(json.dumps({'completed':len(out['cases']),'paired_worlds':out['paired_worlds'],'focal_comparisons':out['focal_comparisons']},ensure_ascii=False))
