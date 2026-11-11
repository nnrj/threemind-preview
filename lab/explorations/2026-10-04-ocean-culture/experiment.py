"""E39/E40: three archived lineages in complete habitats, with a sharing fork."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_contact_cli import save,run
from lab.tools.ocean_association import AssociationOcean,load
from lab.tools.ocean_species import seed_founders
from lab.tools.ocean_culture_watch import CultureWatch
from lab.tools.service_study import Study,StudyConfig

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/ocean-culture-20261004'
SOURCES={
 'turn44':ROOT/'.work/ocean-species-20261004/turning-species/E38-control-02-44-900000000.tmspecies',
 'turn59':ROOT/'.work/ocean-species-20261004/turning-species/E38-control-02-59-900000000.tmspecies',
 'engulf15':ROOT/'.work/ocean-species-20261004/event-species/shared-00-199620000-15.tmspecies',
}


def study(prepare=False,usage=None):
    if usage is None:usage=read_json(WORK/'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-culture/1','E39–E40 候选混合培养与邻近分享',HERE,WORK,usage,
        instance_limit=6,wall_seconds=10800,storage_soft=5*2**30,storage_hard=8*2**30,
        usage_soft_delta=3,usage_hard_delta=5),prepare=prepare)


def register(usage):
    if usage is None:raise ValueError('actual account usage required')
    if (WORK/'source').exists():raise RuntimeError('already registered; original source retained')
    partial=(WORK/'platform.json').exists()
    s=study(not partial,usage)
    try:
        if partial:s.complete_registration()
        write_json(WORK/'usage.json',{'used_percent':usage,'observed_epoch':time.time()})
        p=read_json(ROOT/'lab/templates/ocean-material-full-habitat.json')
        p.update(schema='threemind.ocean-association/1',founders=51,seed=390100,environment_seed=392101,
                 intake_share_fraction=0.,association_gap_m=.001,association_dwell_us=1000000)
        w=AssociationOcean(p);cohorts={}
        for k,(name,source) in enumerate(SOURCES.items()):
            ids=list(range(k,51,3));seed_founders(w,source.read_bytes(),ids)
            cohorts.update({i:name for i in ids})
            target=WORK/'founders'/source.name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
        w.configure(cohorts,{name:'core' for name in SOURCES})
        save(w,WORK/'source');write_json(WORK/'protocol.json',w.p.model_dump(by_alias=True))
        for source in (ROOT/'lab/tools').glob('ocean*.py'):
            target=WORK/'sources'/source.name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
        print(json.dumps({'project':s.project,'founders':51,'sources':list(SOURCES),'usage_start':usage}),flush=True)
    finally:s.db.close()


def segment(s,snapshot,monitor_state,name):
    # Check extension limits before loading every archived brain.
    s.allow_extension();w=load(snapshot);folder=WORK/'cases'/name
    if folder.exists():raise RuntimeError('prior segment retained; no overwrite')
    watch=CultureWatch(WORK,name,s.project,state=monitor_state)
    step=w.step
    def observed_step(record=None):
        active=[i for i,b in w.bodies.items() if b.physical and w.engines[i].life!='dead']
        def observe(row):
            if record:record(row)
            watch.observe(w,row,active)
        return step(observe)
    w.step=observed_step
    class Clock:pass
    clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
    try:
        result=run(w,folder,300,guard=s.guard,wall_seconds=10800,checkpoint_s=150,
                   trajectory_interval_us=100000,activity_interval_us=1000000)
    finally:s.active_case=None;s.completed_count=None;watch.close()
    state=watch.capture();write_json(folder/'observer.json',state)
    from threemind_lab import species_library as lib
    from threemind_lab.database import LOCAL_USER
    for bundle in sorted((WORK/'event-species').glob(name+'-*.tmspecies')):
        lib.put(s.db,s.project,LOCAL_USER,bundle.read_bytes())
    print(json.dumps({'case':name,'status':result['status'],'error':result['error'],
        'time_us':w.time_us,'groups':result['groups'],'sharing_contacts':w.totals['sharing_contacts'],
        'wall_seconds':result['wall_seconds']}),flush=True)
    if result['status'] not in ('horizon_paused','physical_extinction'):
        raise RuntimeError('bounded segment stopped; snapshots and evidence retained')
    return folder/'final',state


def batch():
    s=study()
    try:
        shared,watch=segment(s,WORK/'source',None,'shared-00')
        states={}
        for name,fraction in [('culture',0.),('sharing',.25)]:
            w=load(shared);p=w.p.model_dump(by_alias=True)
            w.p=w.protocol_model.model_validate(p|{'intake_share_fraction':fraction})
            w.research['association_transition']={'time_us':w.time_us,'before':0.,'after':fraction,
                'rule':'change future intake sharing only; retain full world and existing proximity history'}
            path=WORK/'branches'/name;save(w,path);states[name]=(path,watch)
        for k in (1,2):
            for name in ('culture','sharing'):
                states[name]=segment(s,*states[name],f'{name}-{k:02d}')
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['register','batch'])
    p.add_argument('--usage',type=int);a=p.parse_args()
    if a.command=='register':register(a.usage)
    else:batch()
