"""E31 registered scene/transfer commands; all outputs are new evidence."""
import argparse
import copy
import gzip
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_behavior import scene,observe,select_region
from lab.tools.service_study import Study,StudyConfig
from threemind_runtime.codec import ArtifactCodec

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/ocean-behavior-20261003'
OLD=ROOT/'.work/ocean-causality-20261003'


def study(prepare=False):
    return Study(StudyConfig('ocean-behavior/1','E31 海洋：主动觅食、追捕与逃离的归因',HERE,WORK,13,
        instance_limit=1024,wall_seconds=21600,storage_soft=3*2**30,storage_hard=6*2**30,
        usage_soft_delta=8,usage_hard_delta=12),prepare=prepare)


def register():
    s=study(True)
    try:
        write_json(WORK/'usage.json',{'used_percent':13,'observed_epoch':time.time()})
        donors=[]
        for group in (0,1):
            point=OLD/'cases'/f'g{group}-core'/'checkpoints/200000000'
            context=read_json(point/'manifest.json')['context']
            eligible=sorted([b for b in context['bodies'] if b['physical'] and context['time_us']-b['birth_us']>=20000000],key=lambda b:b['id'])
            for b in eligible[:4]:
                name=f'g{group}-i{b["id"]}'
                donor={'name':name,'group':group,'individual':b['id'],'body':b,'protocol':context['protocol'],
                       'source':str((point/f'{b["id"]}.tmind').relative_to(ROOT))}
                donors.append(donor)
        if len(donors)!=8:raise RuntimeError('registered selection did not produce eight donors')
        (WORK/'donors').mkdir(exist_ok=True)
        for d in donors:
            shutil.copy2(ROOT/d['source'],WORK/'donors'/f'{d["name"]}.tmind')
        write_json(WORK/'donors.json',donors)
        (WORK/'sources').mkdir(exist_ok=True)
        shutil.copy2(ROOT/'lab/tools/ocean_behavior.py',WORK/'sources/ocean_behavior.py')
        print(json.dumps({'project':s.project,'donors':[d['name'] for d in donors]}),flush=True)
    finally:s.db.close()


def donor(name):
    data=next(d for d in read_json(WORK/'donors.json') if d['name']==name)
    return data,ArtifactCodec.decode((WORK/'donors'/f'{name}.tmind').read_bytes())


def run_one(s,d,image,task,side,operation,*,plan=None,actions=None,seconds=20,discovery=False):
    bearing=0. if discovery else (math.pi/2 if side==0 else -math.pi/2)
    ordinal=read_json(WORK/'donors.json').index(d)
    seed=311101+ordinal*10+(0 if discovery else 1)
    if task=='transfer':seed=312101+side
    name=f'{d["name"]}-{task}-s{side}-{operation}'
    if discovery:name=f'{d["name"]}-{task}-discovery'
    out=WORK/'cases'/name
    if (out/'result.json').exists() and read_json(out/'result.json')['assay']['seed']!=seed:
        # Preserve the early apparatus check; paired directions use identical noise.
        out=out.with_name(name+'-paired-noise')
    if (out/'result.json').exists():
        r=read_json(out/'result.json')
        if r['status']!='horizon_paused':raise RuntimeError('failed case preserved: '+name)
        return r
    if out.exists():raise RuntimeError('partial case preserved: '+name)
    s.guard(force=True)
    w=scene(d['protocol'],image,d['body'],task=task,bearing=bearing,seed=seed,
            operation=operation,plan=plan,actions=actions)
    class Clock:pass
    clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
    try:
        r,_,_=observe(w,out,seconds,guard=s.guard)
    finally:
        s.active_case=None;s.completed_count=None
    print(json.dumps({'case':name,'food':r['food'],'captures':r['captured'],'alive':r['physical'],
        'toward':r['windows']['0-20']['toward_velocity'],'wall_seconds':r['wall_seconds']}),flush=True)
    return r


def trials(name,phase):
    s=study();d,image=donor(name)
    try:
        for task in ('food','hunt','escape'):
            if phase=='transfer':continue
            discover=WORK/'cases'/f'{name}-{task}-discovery'
            run_one(s,d,image,task,0,'intact',seconds=6,discovery=True)
            planfile=WORK/'plans'/f'{name}-{task}.json'
            if not planfile.exists():
                with gzip.open(discover/'activity.json.gz','rt',encoding='utf-8') as f:activity=json.load(f)
                plan=select_region(image,activity)
                write_json(planfile,plan)
            else:plan=read_json(planfile)
            for side in (0,1):
                run_one(s,d,image,task,side,'intact')
            if phase=='discovery':continue
            operations=['target','matched','all','random','passive','experienced','blank','graft','graft-matched','replay']
            for side in (0,1):
                for op in operations:
                    if op in ('target','matched','graft','graft-matched') and not plan['applicable']:
                        print(json.dumps({'unavailable':name,'task':task,'operation':op,'reason':'no matched region'}),flush=True)
                        continue
                    tape=None
                    if op=='replay':
                        opposite=WORK/'cases'/f'{name}-{task}-s{1-side}-intact'
                        if opposite.with_name(opposite.name+'-paired-noise').exists():opposite=opposite.with_name(opposite.name+'-paired-noise')
                        with gzip.open(opposite/'trajectory.json.gz','rt',encoding='utf-8') as f:
                            tape=[r['action'] for r in json.load(f)]
                    run_one(s,d,image,task,side,op,plan=plan,actions=tape)
        if phase in ('transfer','all'):
            plan=read_json(WORK/'plans'/f'{name}-food.json')
            for side in (0,1):
                for op in ('experienced','blank','graft','graft-matched'):
                    if op.startswith('graft') and not plan['applicable']:continue
                    run_one(s,d,image,'transfer',side,op,plan=plan,seconds=90)
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','trials','batch'))
    p.add_argument('--donor');p.add_argument('--phase',choices=('discovery','local','transfer','all'),default='all')
    a=p.parse_args()
    if a.command=='register':register()
    elif a.command=='batch':
        for item in read_json(WORK/'donors.json'):trials(item['name'],a.phase)
    else:trials(a.donor,a.phase)
