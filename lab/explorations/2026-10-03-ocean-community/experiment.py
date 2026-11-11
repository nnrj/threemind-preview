"""E32: complete habitats, paired controls and focal-only counterfactuals."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_community import CommunityOcean,load,focal_intervention,run
from lab.tools.ocean_contact import ContactProtocol
from lab.tools.service_study import Study,StudyConfig

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/ocean-community-20261003'
ARMS=('target','matched','random','experienced','blank','graft','graft-matched')


def study(prepare=False,usage=None):
    if usage is None:usage=read_json(WORK/'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-community/1','E32 完整海洋：经历、内部活动与行为收益',HERE,WORK,usage,
        instance_limit=18,wall_seconds=21600,storage_soft=4*2**30,storage_hard=8*2**30,
        usage_soft_delta=6,usage_hard_delta=8),prepare=prepare)


def protocol(group,mode):
    p=read_json(HERE/'base-protocol.json')
    p.update(seed=320100+group*100,environment_seed=322101+group,mode=mode,
        side_m=1.2,founders=53,population_limit=97,total_birth_limit=512,
        nutrient_initial=360,nutrient_capacity=4096,nutrient_interval_us=1000000)
    return ContactProtocol.model_validate(p).model_dump(by_alias=True)


def register(usage):
    if usage is None:raise ValueError('fresh account usage required')
    s=study(True,usage)
    try:
        write_json(WORK/'usage.json',{'used_percent':usage,'observed_epoch':time.time()})
        for path in (ROOT/'lab/tools').glob('ocean*.py'):
            destination=WORK/'sources'/path.name;destination.parent.mkdir(exist_ok=True)
            shutil.copy2(path,destination)
        shutil.copy2(HERE/'base-protocol.json',WORK/'base-protocol.json')
        for g in (0,1):
            for mode in ('core','random'):write_json(WORK/'protocols'/f'g{g}-{mode}.json',protocol(g,mode))
        print(json.dumps({'project_id':s.project,'usage_start':usage}),flush=True)
    finally:s.db.close()


def execute(s,key,make,seconds,**kwargs):
    out=WORK/'cases'/key
    if (out/'result.json').exists():
        result=read_json(out/'result.json')
        if result['status'] not in ('horizon_paused','physical_extinction'):raise RuntimeError('partial case retained: '+key)
        return result
    if out.exists():raise RuntimeError('partial case retained: '+key)
    s.allow_extension()
    class Clock:pass
    clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
    try:
        w=make()
        result=run(w,out,seconds,guard=s.guard,**kwargs)
    finally:s.active_case=None;s.completed_count=None
    print(json.dumps({'complete':key,'status':result['status'],'wall_seconds':result['wall_seconds'],
        'food':sum(b['grains'] for b in result['members']),'captures':result['totals']['predations'],
        'alive':sum(b['physical'] for b in result['members'])}),flush=True)
    return result


def main_world(s,group,mode):
    return execute(s,f'g{group}-{mode}',lambda:CommunityOcean(protocol(group,mode)),120,
                   select_at_s=60 if mode=='core' else None)


def forks(s,group):
    source=WORK/'cases'/f'g{group}-core'
    if not (source/'selection.json').exists():
        write_json(WORK/'unavailable'/f'g{group}.json',{'reason':'main world did not reach selection time'});return
    chosen=read_json(source/'selection.json');i=chosen['individual']
    if i is None:
        write_json(WORK/'unavailable'/f'g{group}.json',chosen);return
    for op in ARMS:
        def make():
            w=load(source/'selection-source');focal_intervention(w,i,op,chosen['plan']);return w
        key=f'g{group}-focal-random' if op=='random' else f'g{group}-{op}'
        execute(s,key,make,60,focal=i)


def batch():
    s=study()
    try:
        # Both independent paired worlds precede the more expensive causal forks.
        for group in (0,1):
            main_world(s,group,'core');main_world(s,group,'random')
        for group in (0,1):forks(s,group)
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('register','batch','world','forks'))
    p.add_argument('--usage',type=int);p.add_argument('--group',type=int,choices=(0,1),default=0)
    p.add_argument('--mode',choices=('core','random'),default='core');a=p.parse_args()
    if a.command=='register':register(a.usage)
    elif a.command=='batch':batch()
    else:
        s=study()
        try:
            if a.command=='world':main_world(s,a.group,a.mode)
            else:forks(s,a.group)
        finally:s.db.close()
