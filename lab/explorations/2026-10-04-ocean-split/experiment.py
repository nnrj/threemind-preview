"""Conditional E41 cultivation, retaining the complete E39 shared habitat."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_contact_cli import save,run
from lab.tools.ocean_coverage import CoverageOcean,CoverageProtocol,SCHEMA,load
from lab.tools.ocean_culture_watch import CultureWatch
from lab.tools.service_study import Study,StudyConfig
from threemind_runtime.codec import ArtifactCodec

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/ocean-split-20261004'
PRIOR=ROOT/'.work/ocean-culture-20261004'


def condition():
    rows=[read_json(PRIOR/'cases'/f'{branch}-02/result.json') for branch in ('culture','sharing')]
    if any(r['time_us']<900_000_000 or sum(g['captures'] for g in r['groups'].values()) for r in rows):
        raise RuntimeError('activation condition not met: both branches must reach 900s without full consumption')
    return [
        {'branch':b,'time_us':r['time_us'],'captures':sum(g['captures'] for g in r['groups'].values())}
        for b,r in zip(('culture','sharing'),rows)]


def study(prepare=False,usage=None):
    if usage is None:usage=read_json(WORK/'platform.json')['settings']['usage_start']
    return Study(StudyConfig('ocean-split/1','E41 转弯摄食与半包裹分开培养',HERE,WORK,usage,
        instance_limit=4,wall_seconds=7200,storage_soft=4*2**30,storage_hard=6*2**30,
        usage_soft_delta=3,usage_hard_delta=5),prepare=prepare)


def register(usage,contest):
    trigger=condition()
    if (WORK/'platform.json').exists():raise RuntimeError('existing registration retained; no overwrite')
    s=study(True,usage)
    try:
        source=PRIOR/'cases/shared-00/final';context=read_json(source/'manifest.json')['context']['material']
        base=context['enclosure']['group']['community']['world']
        p={k:v for k,v in base['protocol'].items() if k=='schema' or k in CoverageProtocol.model_fields}
        p.update(schema='threemind.ocean-enclosure/3',coverage_contest=contest,coverage_segments=96)
        images={int(i):ArtifactCodec.decode((source/f'{i}.tmind').read_bytes()) for i in base['core_hashes']}
        for branch,predation,fraction in [('turning',False,1.),('coverage',True,.5)]:
            protocol=CoverageProtocol.model_validate(p|{'predation':predation,'enclosure_fraction':fraction})
            material=copy.deepcopy(context)
            material['enclosure']['group']['community']['world']['protocol']=protocol.model_dump(by_alias=True)
            w=CoverageOcean(protocol.model_dump(by_alias=True),
                state={'schema':SCHEMA,'material':material,'contests':[]},images=images)
            w.research['coverage_transition']={'source_project':read_json(PRIOR/'platform.json')['project_id'],
                'source':str(source),'time_us':w.time_us,'predation':predation,'fraction':fraction,
                'scope':'explicit full-habitat fork; Core and body state retained'}
            save(w,WORK/'source'/branch)
        write_json(WORK/'activation.json',{'condition':trigger,'contest':contest,'source':str(source)})
        shutil.copy2(PRIOR/'cases/shared-00/observer.json',WORK/'source/observer.json')
        write_json(WORK/'usage.json',{'used_percent':usage,'observed_epoch':time.time()})
        for path in (ROOT/'lab/tools').glob('ocean*.py'):
            target=WORK/'sources'/path.name;target.parent.mkdir(exist_ok=True);shutil.copy2(path,target)
        print(json.dumps({'project':s.project,'condition':trigger,'contest':contest}),flush=True)
    finally:s.db.close()


def segment(s,snapshot,state,name):
    s.allow_extension();w=load(snapshot);folder=WORK/'cases'/name
    if folder.exists():raise RuntimeError('existing case retained; no replay')
    watch=CultureWatch(WORK,name,s.project,state=state,archive_prefix='E41',
                       consumption_kinds=('body_engulfed','body_consumed_by_coverage'))
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
    try:r=run(w,folder,300,guard=s.guard,wall_seconds=7200,checkpoint_s=150,
              trajectory_interval_us=100000,activity_interval_us=1000000)
    finally:s.active_case=None;s.completed_count=None;watch.close()
    state=watch.capture();write_json(folder/'observer.json',state)
    from threemind_lab import species_library as lib
    from threemind_lab.database import LOCAL_USER
    for path in sorted((WORK/'event-species').glob(name+'-*.tmspecies')):
        lib.put(s.db,s.project,LOCAL_USER,path.read_bytes())
    print(json.dumps({'case':name,'status':r['status'],'error':r['error'],'time_us':w.time_us,
        'groups':r['groups'],'wall_seconds':r['wall_seconds']}),flush=True)
    if r['status'] not in ('horizon_paused','physical_extinction'):
        raise RuntimeError('bounded simulation stopped; evidence retained')
    return folder/'final',state,r['status']=='physical_extinction'


def batch():
    s=study()
    try:
        watch=read_json(WORK/'source/observer.json')
        states={b:(WORK/'source'/b,watch,False) for b in ('turning','coverage')}
        for k in (1,2):
            for branch in ('turning','coverage'):
                snapshot,state,extinct=states[branch]
                if extinct:continue
                states[branch]=segment(s,snapshot,state,f'{branch}-{k:02d}')
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['register','batch'])
    p.add_argument('--usage',type=int);p.add_argument('--contest',choices=['body','larger'],default='body')
    a=p.parse_args()
    if a.command=='register':
        if a.usage is None:p.error('registration requires actual --usage')
        register(a.usage,a.contest)
    else:batch()
