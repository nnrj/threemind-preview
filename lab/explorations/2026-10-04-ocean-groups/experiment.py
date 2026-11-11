"""E35 whole-population copies, followed by E36 mixed-cohort competition."""
import argparse
import copy
from dataclasses import asdict
import json
import math
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_community import load as load_community,run
from lab.tools.ocean_groups import GroupOcean,copy_community,load
from lab.tools.ocean_contact import ContactBody
from lab.tools.ocean_contact_cli import save
from lab.tools.service_study import Study,StudyConfig
from threemind_runtime import create_engine

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/ocean-groups-20261004'
E32=ROOT/'.work/ocean-community-20261003'
CONTROLS=('core','random-shadow','random-stopped')


def study(prepare=False,usage=None):
    if usage is None:usage=read_json(WORK/'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-groups/1','E35–E36 整组同源对照与共同海洋竞争',HERE,WORK,usage,
        instance_limit=10,wall_seconds=21600,storage_soft=8*2**30,storage_hard=12*2**30,
        usage_soft_delta=6,usage_hard_delta=8),prepare=prepare)


def register(usage):
    if usage is None:raise ValueError('fresh account reading required')
    s=study(True,usage)
    try:
        write_json(WORK/'usage.json',{'used_percent':usage,'observed_epoch':time.time()})
        for source in (ROOT/'lab/tools').glob('ocean*.py'):
            dest=WORK/'sources'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        for g in (0,1):
            # One actual full-world snapshot per group, not independently sampled bodies.
            w=copy_community(load_community(E32/'cases'/f'g{g}-core'/'selection-source'))
            w.configure({i:'all' for i in w.bodies},{'all':'core'})
            save(w,WORK/'sources-worlds'/f'g{g}')
            # Area doubled; exact body/brain twin pairs at separately random positions.
            p=read_json(E32/'protocols'/f'g{g}-core.json')
            p.update(schema='threemind.ocean-groups/1',side_m=1.2*math.sqrt(2),founders=106,
                population_limit=194,total_birth_limit=1024,nutrient_initial=720,
                nutrient_capacity=8192,nutrient_interval_us=500000,
                seed=350100+g*100,environment_seed=352101+g)
            mixed=GroupOcean(p)
            for i in range(53):
                other=i+53;position=mixed.bodies[other].position[:]
                values=asdict(mixed.bodies[i]);values.update(id=other,position=position)
                mixed.bodies[other]=ContactBody(**values)
                mixed.seeds[other]=mixed.seeds[i]
                mixed.engines[other]=create_engine(state=mixed.engines[i].capture_state(),backend=mixed.backend)
            mixed.configure({i:('A' if i<53 else 'B') for i in mixed.bodies},
                            {'A':'core','B':'random-shadow'},cross_only=True)
            save(mixed,WORK/'mixed-worlds'/f'g{g}')
        print(json.dumps({'project':s.project,'usage_start':usage}),flush=True)
    finally:s.db.close()


def execute(s,key,make,seconds):
    folder=WORK/'cases'/key
    if (folder/'result.json').exists():
        result=read_json(folder/'result.json')
        if result['status'] not in ('horizon_paused','physical_extinction'):raise RuntimeError('partial case retained: '+key)
        return
    if folder.exists():raise RuntimeError('partial case retained: '+key)
    s.allow_extension()
    class Clock:pass
    clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
    try:result=run(make(),folder,seconds,guard=s.guard)
    finally:s.active_case=None;s.completed_count=None
    print(json.dumps({'complete':key,'status':result['status'],'groups':result['groups'],
        'wall_seconds':result['wall_seconds']}),flush=True)


def batch(phase):
    s=study()
    try:
        if phase in ('all','copies'):
            for g in (0,1):
                for control in CONTROLS:
                    def make(g=g,control=control):
                        w=load(WORK/'sources-worlds'/f'g{g}')
                        w.configure({i:'all' for i in w.bodies},{'all':control});return w
                    execute(s,f'copy-g{g}-{control}',make,60)
        if phase in ('all','mixed'):
            for g in (0,1):
                for swap in (False,True):
                    def make(g=g,swap=swap):
                        w=load(WORK/'mixed-worlds'/f'g{g}')
                        w.configure(w.cohorts,{'A':'random-shadow' if swap else 'core',
                            'B':'core' if swap else 'random-shadow'},cross_only=True);return w
                    execute(s,f'mixed-g{g}-swap{int(swap)}',make,120)
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('register','batch'))
    p.add_argument('--usage',type=int);p.add_argument('--phase',choices=('all','copies','mixed'),default='all');a=p.parse_args()
    if a.command=='register':register(a.usage)
    else:batch(a.phase)
