"""Small-file effect summary; no full archive scans or frame-as-sample tests."""
import argparse
import json
import math
import gzip
import numpy as np
from experiment import WORK
from lab.tools.ocean_cli import read_json


def cases(*,recompute_contacts=True):
    donors=read_json(WORK/'donors.json')
    index={d['name']:k for k,d in enumerate(donors)}
    rows=[]
    for f in (WORK/'cases').glob('*/result.json'):
        r=read_json(f)
        if r['status']!='horizon_paused' or f.parent.name.endswith('discovery'):continue
        a=r['assay'];name='-'.join(f.parent.name.split('-')[:2])
        if a['task']!='transfer' and a['seed']!=311102+index[name]*10:continue
        side=(a['seed']-312101 if a['task']=='transfer' else int(a['bearing']<0))
        events=read_json(f.parent/'events.json')
        r['target_food']=sum(e['kind']=='nutrient_contact' and e['individual']==0
            and e.get('particle') in a['target_food_ids'] for e in events)
        contact_events=[e for e in events if
            (a['task']=='food' and e['kind']=='nutrient_contact' and e['individual']==0 and e.get('particle') in a['target_food_ids'])
            or (a['task'] in ('hunt','escape') and e['kind']=='capture_started' and {e['predator'],e['individual']}=={0,1})]
        r['sampled_contact_s']=r['first_contact_s']
        r['physical_contact_s']=min((e['time_us']/1e6-200 for e in contact_events),default=None)
        if recompute_contacts and a['task']!='transfer':
            with gzip.open(f.parent/'trajectory.json.gz','rt',encoding='utf-8') as stream:trace=json.load(stream)
            for key,value in r['windows'].items():
                lo,hi=map(float,key.split('-'))
                pre=[x for x in trace if lo<=x['t']<hi and x['physical'] and x['toward_velocity'] is not None
                     and (r['physical_contact_s'] is None or x['t']<r['physical_contact_s'])]
                value['precontact_samples']=len(pre)
                value['precontact_toward_velocity']=float(np.mean([x['toward_velocity'] for x in pre])) if pre else None
        rows.append(r|{'donor':name,'group':int(name[1]),'side':side,'path':str(f.parent.relative_to(WORK))})
    return rows


def summarize():
    rows=cases();pairs={(r['donor'],r['assay']['task'],r['side'],r['assay']['operation']):r for r in rows}
    output={'valid_cases':len(rows),'by_task':{},'comparisons':{},'cases':[]}
    for task in ('food','hunt','escape','transfer'):
        output['by_task'][task]={}
        for op in sorted({r['assay']['operation'] for r in rows if r['assay']['task']==task}):
            group=[r for r in rows if r['assay']['task']==task and r['assay']['operation']==op]
            windows=[r['windows']['0-20'] for r in group]
            output['by_task'][task][op]={'n':len(group),'food':sum(r['food'] for r in group),
                'target_food':sum(r['target_food'] for r in group),
                'captures':sum(r['captured'] for r in group),'survivors':sum(r['physical'] for r in group),
                'precontact_toward_velocity':float(np.mean([w['precontact_toward_velocity'] for w in windows if w['precontact_toward_velocity'] is not None])) if any(w['precontact_toward_velocity'] is not None for w in windows) else None}
        comparisons={}
        for left,right in (('intact','replay'),('intact','random'),('intact','passive'),
                           ('intact','target'),('intact','matched'),('intact','all'),
                           ('matched','target'),('experienced','blank'),('graft','blank'),('graft','graft-matched')):
            values=[]
            for (name,t,side,op),a in pairs.items():
                if t!=task or op!=left:continue
                b=pairs.get((name,t,side,right))
                if b is None:continue
                sign=-1 if task=='escape' else 1
                windows={}
                for window in a['windows']:
                    x,y=a['windows'][window],b['windows'][window]
                    windows[window]={k:sign*(x[k]-y[k]) if x[k] is not None and y[k] is not None else None
                                     for k in ('toward_action','toward_velocity','precontact_toward_velocity','alignment')}
                values.append({'donor':name,'group':a['group'],'side':side,'food':a['food']-b['food'],
                    'captures':a['captured']-b['captured'],'survival':int(a['physical'])-int(b['physical']),
                    'windows':windows,'left':a['path'],'right':b['path']})
            if values:comparisons[left+' minus '+right]=values
        output['comparisons'][task]=comparisons
    for r in rows:
        output['cases'].append({k:r[k] for k in ('donor','group','side','path','assay','food','target_food','captured','physical','sampled_contact_s','physical_contact_s','windows')})
    path=WORK/'findings.json';tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(path)
    return output


if __name__=='__main__':
    value=summarize()
    print(json.dumps({k:v for k,v in value.items() if k not in ('cases','comparisons')},ensure_ascii=False))
