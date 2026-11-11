"""E37: all-Core inherited variation, complete enclosure only, long observation."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_contact_cli import run,save
from lab.tools.ocean_enclosure import EnclosureOcean,load
from lab.tools.service_study import Study,StudyConfig

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/ocean-enclosure-20261004'


def study(prepare=False,usage=None):
    if usage is None:usage=read_json(WORK/'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-enclosure/1','E37 全意识驱动：包裹吞食与代际变异',HERE,WORK,usage,
        instance_limit=8,wall_seconds=14400,storage_soft=5*2**30,storage_hard=8*2**30,
        usage_soft_delta=3,usage_hard_delta=5),prepare=prepare)


def register(usage):
    if usage is None:raise ValueError('fresh usage reading required')
    s=study(True,usage)
    try:
        write_json(WORK/'usage.json',{'used_percent':usage,'observed_epoch':time.time()})
        for source in (ROOT/'lab/tools').glob('ocean*.py'):
            dest=WORK/'sources'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        p=read_json(ROOT/'.work/ocean-groups-20261004/cases/copy-g1-core/protocol.json')
        p.update(schema='threemind.ocean-enclosure/1',capture_enabled=False,mode='core',
            seed=370100,environment_seed=372101,population_limit=97,total_birth_limit=1024)
        w=EnclosureOcean(p);w.configure({i:'all' for i in w.bodies},{'all':'core'})
        save(w,WORK/'source');write_json(WORK/'protocol.json',p)
        print(json.dumps({'project':s.project,'usage_start':usage}),flush=True)
    finally:s.db.close()


def batch():
    s=study()
    try:
        previous=WORK/'source'
        for k in range(1,5):
            folder=WORK/'cases'/f'segment-{k:02d}'
            if (folder/'result.json').exists():
                r=read_json(folder/'result.json')
                if r['status']!='horizon_paused':raise RuntimeError('partial segment retained')
                previous=folder/'final';continue
            if folder.exists():raise RuntimeError('partial directory retained')
            s.allow_extension()
            class Clock:pass
            clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
            try:
                r=run(load(previous),folder,300,guard=s.guard,wall_seconds=14400,
                    checkpoint_s=150,trajectory_interval_us=100000,activity_interval_us=1000000)
            finally:s.active_case=None;s.completed_count=None
            print(json.dumps({'segment':k,'status':r['status'],'time_us':r['time_us'],
                'groups':r['groups'],'wall_seconds':r['wall_seconds']}),flush=True)
            if r['status']!='horizon_paused':break
            previous=folder/'final'
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('register','batch'))
    p.add_argument('--usage',type=int);a=p.parse_args()
    if a.command=='register':register(a.usage)
    else:batch()
