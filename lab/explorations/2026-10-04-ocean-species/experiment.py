"""E38: complete-habitat candidate inheritance and nutrient-supply selection."""
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
from lab.tools.ocean_species import seed_founders,save_candidate,save_live_candidate
from lab.tools.service_study import Study,StudyConfig

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/ocean-species-20261004'
SOURCE=ROOT/'.work/ocean-enclosure-20261004/species/59-g1-300s.tmspecies'


def study(prepare=False,usage=None):
    if usage is None:usage=read_json(WORK/'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-species/1','E38 物种候选复用与营养选择',HERE,WORK,usage,
        instance_limit=8,wall_seconds=14400,storage_soft=5*2**30,storage_hard=8*2**30,
        usage_soft_delta=3,usage_hard_delta=5),prepare=prepare)


def register(usage):
    if usage is None:raise ValueError('fresh usage required')
    s=study(True,usage)
    try:
        write_json(WORK/'usage.json',{'used_percent':usage,'observed_epoch':time.time()})
        shutil.copy2(SOURCE,WORK/'founder-candidate.tmspecies')
        for source in (ROOT/'lab/tools').glob('ocean*.py'):
            dest=WORK/'sources'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        p=read_json(ROOT/'.work/ocean-enclosure-20261004/protocol.json')
        p.update(seed=380100,environment_seed=382101)
        w=EnclosureOcean(p)
        seed_founders(w,SOURCE.read_bytes(),list(range(11)))
        w.configure({i:'candidate' if i<11 else 'other' for i in w.bodies},
                    {'candidate':'core','other':'core'})
        save(w,WORK/'source');write_json(WORK/'protocol.json',p)
        print(json.dumps({'project':s.project,'usage_start':usage}),flush=True)
    finally:s.db.close()


def segment(s,w,name):
    folder=WORK/'cases'/name
    if folder.exists():raise RuntimeError('existing case retained')
    s.allow_extension()
    class Clock:pass
    clock=Clock();clock.born_wall=time.monotonic();s.active_case=clock
    step=w.step
    def observed_step(record=None):
        events=step(record)
        for event in events:
            if event['kind']=='body_engulfed':
                i=event['predator'];out=WORK/'event-species'/f'{name}-{w.time_us}-{i}.tmspecies'
                save_live_candidate(w,i,out,name=f'E38 {name} #{i} at {w.time_us/1e6:g}s',
                    evidence=[event|{'summary':f"#{i} enclosed #{event['individual']} at {w.time_us/1e6:g}s"}],
                    source={'case':name,'project':s.project,'record':'natural-event-end-of-step'})
                print(json.dumps({'natural_enclosure':event,'candidate_bundle':str(out)}),flush=True)
        return events
    w.step=observed_step
    try:
        r=run(w,folder,300,guard=s.guard,wall_seconds=14400,checkpoint_s=150,
              trajectory_interval_us=100000,activity_interval_us=1000000)
    finally:s.active_case=None;s.completed_count=None
    # Publish the event snapshots; later starvation must not overwrite the
    # successful individual's original body and brain. Full end states also stay.
    from threemind_lab import species_library as lib
    from threemind_lab.database import LOCAL_USER
    for bundle in sorted((WORK/'event-species').glob(name+'-*.tmspecies')):
        lib.put(s.db,s.project,LOCAL_USER,bundle.read_bytes())
    print(json.dumps({'case':name,'status':r['status'],'time_us':r['time_us'],
                     'groups':r['groups'],'wall_seconds':r['wall_seconds']}),flush=True)
    if r['status'] not in ('horizon_paused','physical_extinction'):raise RuntimeError('bounded segment stopped; evidence retained')
    return folder/'final'


def batch():
    s=study()
    try:
        # Freeze the read-only event-archive tool revision added before execution.
        source=ROOT/'lab/tools/ocean_species.py'
        shutil.copy2(source,WORK/'event-archive-tool.py')
        shared=segment(s,load(WORK/'source'),'shared-00')
        states={}
        for name,interval in (('control',1000000),('reduced',2000000)):
            w=load(shared)
            before=w.p.model_dump(by_alias=True);after=before|{'nutrient_interval_us':interval}
            w.p=w.protocol_model.model_validate(after);w.next_food_us=w.time_us+interval
            w.research['environment_transition']={'time_us':w.time_us,'before':before,
                'after':after,'rule':'retain existing food; change future replenishment only'}
            source=WORK/'branches'/name;save(w,source);states[name]=source
        for k in (1,2):
            for name in ('control','reduced'):
                w=load(states[name])
                if not any(b.physical for b in w.bodies.values()):continue
                states[name]=segment(s,w,f'{name}-{k:02d}')
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('register','batch'))
    p.add_argument('--usage',type=int);a=p.parse_args()
    if a.command=='register':register(a.usage)
    else:batch()
