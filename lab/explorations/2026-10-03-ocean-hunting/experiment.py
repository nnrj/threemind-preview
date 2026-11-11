"""E34: prospective encounter selection and focal interventions in whole oceans."""
import argparse
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import shutil
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.ocean import difference
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_community import load,focal_intervention
from lab.tools.ocean_behavior import select_region
from lab.tools.ocean_encounter import ActivityHistory,measurement,observe_encounter
from lab.tools.ocean_contact_cli import save
from lab.tools.service_study import Study,StudyConfig

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/ocean-hunting-20261003'
E32=ROOT/'.work/ocean-community-20261003'
ARMS=('intact','target','matched','random','experienced','blank','graft','graft-matched')


def study(prepare=False,usage=None):
    if usage is None:usage=read_json(WORK/'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-hunting/1','E34 捕获归因：完整环境的消融与移植',HERE,WORK,usage,
        instance_limit=34,wall_seconds=14400,storage_soft=3*2**30,storage_hard=6*2**30,
        usage_soft_delta=6,usage_hard_delta=8),prepare=prepare)


def register(usage):
    if usage is None:raise ValueError('fresh account reading required')
    s=study(True,usage)
    try:
        write_json(WORK/'usage.json',{'used_percent':usage,'observed_epoch':time.time()})
        for source in (ROOT/'lab/tools').glob('ocean*.py'):
            target=WORK/'sources'/source.name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
        print(json.dumps({'project':s.project,'usage_start':usage}),flush=True)
    finally:s.db.close()


def choose(w,history,excluded):
    strength=lambda b:b.thrust*(.25+b.grip)*b.radius**2
    for i,b in sorted(w.bodies.items()):
        if i in excluded or not b.physical or w.engines[i].life=='dead' or w.time_us-b.birth_us<20000000:continue
        candidates=[]
        for j,other in w.bodies.items():
            if j==i or not other.physical or strength(b)<=strength(other) or w._protected_pair(i,j,w.time_us):continue
            if tuple(sorted((i,j))) in w.contacts:continue
            delta=difference(other.position,b.position,w.p.side_m)
            if float(np.linalg.norm(delta))>b.sensor_range+2*(b.radius+other.radius):continue
            m=measurement(w,i,'hunt',j)
            if m['gap'] is not None and w.p.contact_skin_m<m['gap']<b.sensor_range and m['closing_velocity']>0:
                candidates.append((m['gap'],j,m))
        if not candidates:continue
        rows=list(history.activity.get(i,[]));plan=select_region(w.engines[i].capture_state(),rows)
        if not plan['applicable']:continue
        _,target,trigger=min(candidates,key=lambda row:(row[0],row[1]))
        return {'focal':i,'target':target,'task':'hunt','time_us':w.time_us,'trigger':trigger,'plan':plan},rows
    return None


def scout(s,g):
    folder=WORK/'cases'/f'scout-g{g}'
    if (folder/'result.json').exists():
        result=read_json(folder/'result.json')
        if result['status']!='selection_complete':raise RuntimeError('partial scout retained')
        return result['selected']
    if folder.exists():raise RuntimeError('partial scout retained')
    s.allow_extension();folder.mkdir(parents=True)
    class Clock:pass
    clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
    w=load(E32/'cases'/f'g{g}-core'/'selection-source')
    w.research['parent_protection']='bilateral-until-maturity/1'
    start=w.time_us;history=ActivityHistory();selected=[];excluded={0 if g==0 else 2}
    status='selecting';error=None;events=[];last_progress=0
    save(w,folder/'initial')
    try:
        with gzip.open(folder/'inputs.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as inp, \
             gzip.open(folder/'trajectory.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as frames:
            def record(row):inp.write(json.dumps(row,separators=(',',':'))+'\n');events.extend(row['events'])
            while w.time_us<start+20000000 and len(selected)<2:
                if (w.time_us-start)%1000000==0:s.guard()
                history.sample(w,start)
                if (w.time_us-start)%100000==0:
                    m=w.metrics();m.update(food_positions=w.food.tolist(),food_ids=w.food_ids[:])
                    frames.write(json.dumps(m,separators=(',',':'))+'\n')
                    if w.time_us-start>=3000000:
                        choice=choose(w,history,excluded)
                        if choice:
                            item,rows=choice;key=f'g{g}-e{len(selected)}';destination=WORK/'selections'/key
                            save(w,destination/'world');write_json(destination/'encounter.json',item)
                            with gzip.open(destination/'activity.json.gz','wt',encoding='utf-8') as stream:json.dump(rows,stream)
                            excluded.add(item['focal']);selected.append(key)
                            print(json.dumps({'selected':key,'focal':item['focal'],'target':item['target'],
                                'time_us':w.time_us,'edges':item['plan']['selected_edges']}),flush=True)
                if len(selected)==2:break
                w.step(record)
                if time.monotonic()-clock.born_wall-last_progress>30:
                    last_progress=time.monotonic()-clock.born_wall
                    print(json.dumps({'scout':g,'time_us':w.time_us,'selected':selected,'wall_seconds':last_progress}),flush=True)
            status='selection_complete'
    except (Exception,KeyboardInterrupt) as exc:status='paused_error';error=f'{type(exc).__name__}: {exc}'
    finally:
        save(w,folder/'final');write_json(folder/'events.json',events)
        write_json(folder/'result.json',{'status':status,'error':error,'selected':selected,
            'time_us':w.time_us,'observed_us':w.time_us-start,'wall_seconds':time.monotonic()-clock.born_wall})
        s.active_case=None;s.completed_count=None
    if error:raise RuntimeError(error)
    return selected


def execute(s,key,op):
    out=WORK/'cases'/f'{key}-{op}'
    if (out/'result.json').exists():
        if read_json(out/'result.json')['status']!='horizon_paused':raise RuntimeError('partial case retained')
        return
    if out.exists():raise RuntimeError('partial case retained')
    s.allow_extension()
    class Clock:pass
    clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
    try:
        source=WORK/'selections'/key;item=read_json(source/'encounter.json');w=load(source/'world')
        focal_intervention(w,item['focal'],op,item['plan'])
        result=observe_encounter(w,out,item,op,seconds=20,guard=s.guard)
    finally:s.active_case=None;s.completed_count=None
    print(json.dumps({'complete':out.name,**result}),flush=True)


def batch():
    s=study()
    try:
        selections=[]
        for g in (0,1):selections.extend(scout(s,g))
        for key in selections:
            for op in ARMS:execute(s,key,op)
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('register','batch'))
    p.add_argument('--usage',type=int);a=p.parse_args()
    if a.command=='register':register(a.usage)
    else:batch()
