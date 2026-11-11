"""E30 targeted calibration and ecological comparisons. Core outputs stay free."""
import argparse
import json
import shutil
import sys
import time
import psutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_contact import ContactOcean, ContactProtocol
from lab.tools.ocean_contact_cli import run
from lab.tools.service_study import Study, StudyConfig

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/ocean-causality-20261003'
RATE=5.706242779562836


def protocol(group=0,mode='core',**extra):
    p=read_json(ROOT/'lab/explorations/2026-10-03-ocean-evolution/protocols/phase1-0-core.json')
    p.update(schema='threemind.ocean/3',seed=300100+group*100,environment_seed=301101+group,
             side_m=.8,predation=True,mutation_sigma=.12,child_energy=240*RATE,
             random_interval_us=20000 if mode=='random-fast' else 1000000,
             mode='random' if mode.startswith('random') else mode)
    p.update(extra)
    return ContactProtocol.model_validate(p).model_dump(by_alias=True)


def study(prepare=False):
    return Study(StudyConfig('ocean-causality/1','E30 海洋：经历、联想与控制作用',HERE,WORK,10,
        wall_seconds=14400,storage_soft=3*2**30,storage_hard=6*2**30,usage_soft_delta=8,usage_hard_delta=12),prepare=prepare)


def simulation_budget(s):
    """Account for world runs and probes, without reading the large evidence streams."""
    s.guard()
    total=0.; rss=0; processes=set()
    for directory in ('cases','calibration','evaluations','closed-loop'):
        # Early calibration predates worker receipts, but still has timed results.
        total+=sum(read_json(result)['wall_seconds'] for result in (WORK/directory).glob('**/result.json'))
        for worker in (WORK/directory).glob('**/worker.json'):
            result=worker.parent/'result.json'
            if result.exists():continue
            item=read_json(worker)
            if psutil.pid_exists(item['pid']):
                total+=max(0,time.time()-item['started_epoch'])
                processes.add(item['pid'])
    for folder in (WORK/'probes').glob('*'):
        if (folder/'summary.json').exists():total+=read_json(folder/'summary.json')['wall_seconds']
        elif (folder/'failure.json').exists():total+=read_json(folder/'failure.json')['wall_seconds_upper_bound']
        elif (folder/'worker.json').exists():
            item=read_json(folder/'worker.json')
            if psutil.pid_exists(item['pid']):
                total+=max(0,time.time()-item['started_epoch']); processes.add(item['pid'])
    for pid in processes:
        try:rss+=psutil.Process(pid).memory_info().rss
        except psutil.NoSuchProcess:pass
    if total>14400:raise RuntimeError('aggregate simulation budget')
    if rss>4*2**30:raise RuntimeError('combined worker memory budget')
    return total


def register():
    s=study(True)
    try:
        write_json(WORK/'usage.json',{'used_percent':10,'observed_epoch':time.time()})
        for f in (ROOT/'lab/tools').glob('ocean_contact*.py'):
            (WORK/'sources').mkdir(exist_ok=True); shutil.copy2(f,WORK/'sources'/f.name)
        print(json.dumps({'project_id':s.project}),flush=True)
    finally:s.db.close()


def calibrate():
    out=WORK/'calibration'
    out.mkdir(parents=True,exist_ok=False)
    controlled=[]
    for shell in (0,.2,.8):
        w=ContactOcean(protocol(founders=2,nutrient_initial=0,reproduction=False,founder_variation=0))
        a,b=w.bodies.values()
        a.radius,b.radius=.011,.008
        a.elongation=b.elongation=0
        a.position,b.position=[.1,.1],[.119,.1]
        a.angle=b.angle=0; b.shell=shell
        for _ in range(200):
            w.time_us+=w.p.period_us; w._predation([0,1])
            if w.totals['predations']:break
        controlled.append({'shell':shell,'capture_us':w.time_us if w.totals['predations'] else None,
                           'shell_cost':w.totals['shell_heat']})
    write_json(out/'controlled.json',controlled)
    w=ContactOcean(protocol(9,'random',reproduction=False))
    r=run(w,out/'free-motion',60,wall_seconds=900,checkpoint_s=1000)
    answer={'controlled':controlled,'free_motion':{k:r['totals'][k] for k in ('capture_starts','capture_breaks','predations')},
            'wall_seconds':r['wall_seconds'],'status':r['status']}
    write_json(out/'summary.json',answer); print(json.dumps(answer),flush=True)


def execute(group,mode):
    key=f'g{group}-{mode}'
    source=WORK/'calibration/accepted-v2.json'
    c=read_json(source)
    if c['free_motion']['predations']<1 or c['status']!='horizon_paused':
        raise RuntimeError('no predation in free-motion calibration; revise apparatus before formal comparison')
    s=study()
    try:
        def guard():simulation_budget(s)
        born=time.monotonic()
        r=run(ContactOcean(protocol(group,mode)),WORK/'cases'/key,600,guard=guard,wall_seconds=4800)
        print(json.dumps({'case':key,'status':r['status'],'food':sum(b['grains'] for b in r['members']),
                          'predations':r['totals']['predations'],'wall_seconds':r['wall_seconds']}),flush=True)
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('command',choices=('register','calibrate','case'))
    p.add_argument('--group',type=int,choices=(0,1),default=0)
    p.add_argument('--mode',choices=('core','random','random-fast'),default='core')
    a=p.parse_args()
    if a.command=='register':register()
    elif a.command=='calibrate':calibrate()
    else:execute(a.group,a.mode)
