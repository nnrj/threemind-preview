"""Read-only selection/recording of prospective encounters in a shared Ocean/3.

Targets below are observer annotations; engines receive only original senses.
"""
from collections import deque
from dataclasses import asdict
import gzip
import json
import math
from pathlib import Path
import time
import numpy as np
from lab.tools.ocean import difference,rotation
from lab.tools.ocean_contact import capsule,point_segment
from lab.tools.ocean_contact_cli import save
from lab.tools.ocean_cli import write_json


def measurement(w,focal,task,target):
    b=w.bodies[focal];e=w.engines[focal]
    action=w.action(focal) if b.physical and e.life!='dead' else [0.,0.,0.]
    channels,raw=w.senses(focal)
    point=None;gap=None;other_velocity=np.zeros(2)
    if task=='food':
        if target in w.food_ids:point=w.food[w.food_ids.index(target)]
    elif target in w.bodies and w.bodies[target].physical:
        point=w.bodies[target].position;gap=w.geometry(focal,target)[0]
        other_velocity=np.asarray(w.bodies[target].velocity)
    toward_velocity=toward_action=closing=None
    if point is not None:
        delta=difference(point,b.position,w.p.side_m);distance=float(np.linalg.norm(delta))
        direction=delta/max(distance,1e-12)
        if task=='food':
            a,c,r=capsule(b);local=np.asarray(b.position)+delta
            gap=float(point_segment(local,a,c))-r-w.p.nutrient_radius_m
            other_velocity=w.environment(point)[0]
        flow,_=w.environment(b.position)
        toward_velocity=float((np.asarray(b.velocity)-flow)@direction)
        toward_action=float((rotation(b.angle)@np.asarray(action[:2]))@direction)
        closing=float((np.asarray(b.velocity)-other_velocity)@direction)
    return {'world_time_us':w.time_us,'physical':b.physical,'life':e.life,'action':action,
        'position':list(b.position),'angle':b.angle,'gap':gap,'toward_velocity':toward_velocity,
        'toward_action':toward_action,'closing_velocity':closing,'raw':raw,
        'direct_channels':[c for c,v in channels if v],'food':b.grains,'captured':b.captured,
        'consumed_by':b.consumed_by}


def candidate(w,task):
    """First ID satisfying pre-contact geometry and relative approach; no outcomes."""
    for i,b in sorted(w.bodies.items()):
        if not b.physical or w.engines[i].life=='dead':continue
        if task=='food':
            if not len(w.food):continue
            distances=np.linalg.norm(difference(w.food,b.position,w.p.side_m),axis=1)
            choices=[w.food_ids[int(np.argmin(distances))]]
        else:
            strength=lambda x:x.thrust*(.25+x.grip)*x.radius**2
            choices=[j for j,c in sorted(w.bodies.items()) if j!=i and c.physical
                and ((strength(b)>strength(c)) if task=='hunt' else (strength(b)<strength(c)))
                and float(np.linalg.norm(difference(c.position,b.position,w.p.side_m)))<b.sensor_range+2*(b.radius+c.radius)]
        for j in choices:
            m=measurement(w,i,task,j)
            if m['gap'] is not None and w.p.contact_skin_m<m['gap']<b.sensor_range and m['closing_velocity']>0:
                return {'focal':i,'target':j,'task':task,'trigger':m}
    return None


class ActivityHistory:
    def __init__(self):self.inputs={};self.activity={}
    def sample(self,w,origin,ids=None):
        for i,b in w.bodies.items():
            if not b.physical or (ids is not None and i not in ids):continue
            channels=[c for c,v in w.senses(i)[0] if v]
            recent=self.inputs.setdefault(i,deque());recent.append((w.time_us,channels))
            while recent and recent[0][0]<w.time_us-1000000:recent.popleft()
            if (w.time_us-origin)%100000==0:
                rows=self.activity.setdefault(i,deque());rows.append({'t':(w.time_us-origin)/1e6,
                    'recent_channels':sorted({c for _,cs in recent for c in cs}),
                    'nodes':w.engines[i].observation_nodes()})
                while rows and rows[0]['t']<(w.time_us-origin)/1e6-2:rows.popleft()


def observe_encounter(w,folder,encounter,operation,seconds=20,guard=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    i=encounter['focal'];task=encounter['task'];target=encounter['target']
    start=w.time_us;born=time.monotonic();trace=[];activity=[];events=[];history=ActivityHistory()
    before=asdict(w.bodies[i]);status='observing';error=None
    write_json(folder/'assay.json',{'task':task,'operation':operation,'focal':i,'target':target,
        'protocol':w.p.model_dump(by_alias=True),'scene':'natural shared ocean; original physical state'})
    save(w,folder/'initial')
    try:
        with gzip.open(folder/'inputs.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as out:
            def record(row):
                out.write(json.dumps(row,separators=(',',':'))+'\n');events.extend(row['events'])
            while w.time_us<start+round(seconds*1e6):
                if (w.time_us-start)%1000000==0:
                    if guard:guard()
                    if time.monotonic()-born>1800:raise RuntimeError('natural encounter wall budget')
                m=measurement(w,i,task,target);m['t']=(w.time_us-start)/1e6;trace.append(m)
                history.sample(w,start,(i,))
                if (w.time_us-start)%100000==0:
                    m.update(bodies=[asdict(b) for b in w.bodies.values()],food_positions=w.food.tolist(),food_ids=w.food_ids[:])
                    rows=history.activity.get(i,[])
                    if rows and rows[-1]['t']==(w.time_us-start)/1e6:activity.append(rows[-1])
                w.step(record)
            status='horizon_paused'
    except (Exception,KeyboardInterrupt) as exc:status='paused_error';error=f'{type(exc).__name__}: {exc}'
    for name,rows in (('trajectory',trace),('activity',activity)):
        with gzip.open(folder/f'{name}.json.gz','wt',encoding='utf-8',compresslevel=1) as out:json.dump(rows,out,separators=(',',':'))
    save(w,folder/'final');write_json(folder/'events.json',events)
    b=w.bodies[i];contact=next((r['t'] for r in trace if r['physical'] and r['gap'] is not None and r['gap']<=w.p.contact_skin_m),None)
    windows={}
    for lo,hi in ((0,.5),(.5,2),(2,6),(6,20),(0,20)):
        rows=[r for r in trace if lo<=r['t']<hi and r['physical'] and r['toward_action'] is not None]
        pre=[r for r in rows if contact is None or r['t']<contact]
        windows[f'{lo}-{hi}']={'samples':len(rows),'precontact_samples':len(pre),
          **{key:float(np.mean([r[key] for r in rows])) if rows else None for key in ('toward_action','toward_velocity')},
          'precontact_toward_velocity':float(np.mean([r['toward_velocity'] for r in pre])) if pre else None}
    result={'status':status,'error':error,'wall_seconds':time.monotonic()-born,'observed_us':w.time_us-start,
        'focal':i,'target':target,'task':task,'operation':operation,'first_contact_s':contact,'windows':windows,
        'food':b.grains-before['grains'],'captured':b.captured-before['captured'],'physical':b.physical,
        'consumed_by':b.consumed_by,'energy_balance_error':w.metrics()['energy_balance_error']}
    write_json(folder/'result.json',result)
    if status!='horizon_paused':raise RuntimeError(error)
    return result
