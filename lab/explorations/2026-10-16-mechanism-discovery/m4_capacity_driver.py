"""One bounded sustained physical-instrument path, N=0; never launches M4 science."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5

import psutil
import torch
import pilot_m2 as m
import m4_instrument_driver as base
from m4_instrument import Whole, calibrate_instrument, digest

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m4-capacity-v1')
NS=UUID('5d2a2d3d-7568-4833-9a34-d8308fb36984')
SEED=1117002
FORCES=(((.20,-.10),(0.,0.)),((0.,0.),(.20,.10)),((-.15,.12),(-.15,.18)))


def sources():
    return sorted(set(base.source_paths())|{Path(__file__),HERE/'m4_capacity_audit.py',HERE/'m4_instrument_audit_v3.py',
        HERE/'m4-capacity-protocol.zh.md',HERE/'m4-capacity-protocol.en.md'})


def register(work):
    work.mkdir(parents=True,exist_ok=True)
    with m.worker_lock(work),m.connection() as client:
        if (work/'platform.json').exists():raise RuntimeError('already registered')
        title='2026-10-16 机制发现 · M4完整物理装置30秒持续成本验收'
        found=[p for p in client.call('projects.list',{}) if p['name']==title]
        if len(found)>1:raise RuntimeError('ambiguous project')
        project=found[0] if found else client.request('POST','/api/v2/projects',body={'name':title})
        resource='mechanism-m4-capacity-v1-20261016'
        m.original(work/'platform.json',{'project_id':project['id'],'resource_id':resource})
        manifest={p.relative_to(m.ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources()}
        m.original(work/'runner-manifest.json',manifest);m.original(work/'implementation.json',m.capture_implementation('native'))
        for name in manifest:m.original(work/'frozen'/name,{'utf8':(m.ROOT/name).read_text(encoding='utf-8')})
        r=m.ResearchRecorder(work,project['id'],client=client)
        r.register({'source_key':'mechanism:m4-capacity-v1:20261016','title':title,'classification':'development',
            'execution_status':'running','executor':'ai','kernels':[m.KERNEL],
            'protocol':(HERE/'m4-capacity-protocol.zh.md').read_text(encoding='utf-8'),
            'protocol_version':m.digest(manifest),'required_roles':['protocol','report','note'],
            'metadata':{'work':str(work),'scientific_origins':0,'seed':SEED,'sim_seconds':30,
                        'peripheral_updates':40,'Core_changed':False,'E69_resumed':False}},request_id=uuid5(NS,'register'))
        r.synchronize(strict=True)
        client.request('POST','/api/v2/storage/resources',body={'resource_id':resource,'target_id':'managed-research-experiments',
            'relative_path':'2026-10-16-mechanism-discovery/m4-capacity-v1','registered_work_path':str(work),
            'writer_mode':'cooperative','expected_revision':0},headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'resource'))})
        client.request('POST','/api/v2/storage/record-evidence-grants',body={'project_id':project['id'],'resource_id':resource},
            headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'grant'))})
        for lang in ('zh','en'):
            r.text({'request_id':str(uuid5(NS,'protocol:'+lang)),'identity':str(uuid5(NS,'doc:'+lang)),
                'expected_revision':0,'kind':'protocol','title':'M4 sustained cost protocol '+lang,
                'markdown':(HERE/f'm4-capacity-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True);print(json.dumps({'project':project['id'],'record':r.experiment,'status':r.status}))


def run(work):
    torch.set_num_threads(1)
    with m.worker_lock(work),m.connection() as client:
        m.frozen_check(work)
        if any((work/n).exists() for n in ('host.json','status.json','STOP','in-flight.json')):
            raise RuntimeError('previous attempt; preserve it and do not repeat')
        resources=m.resource_check(work)
        assert all(resources['available_bytes'][k]>=resources['limits_bytes'][k]+3*2**30 for k in ('commit','ram'))
        m.original(work/'host.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
        r=m.recorder(work,client);completed=0
        with base.InstrumentGuard(work) as guard:
            m.original(work/'in-flight.json',{'unit':'birth','pid':os.getpid(),'epoch':time.time()})
            a=Whole(SEED,identity='m4-capacity-v1');a.save(work/'birth')
            (work/'in-flight.json').unlink()
            for segment in range(5):
                if (work/'STOP').exists():break
                if not guard.thread.is_alive():raise RuntimeError('guard absent')
                m.original(work/'in-flight.json',{'unit':segment,'pid':os.getpid(),'epoch':time.time()})
                started=time.perf_counter();rows=[];learning=[]
                for offset in range(120):
                    step=segment*120+offset;phase=(step//60)%3
                    a.phase=('eye-command','hand-command','joint-command')[phase]
                    text=list(a.session.sensor.frames(('看','指','看指')[phase]))
                    frame=text[step%60] if step%60<len(text) else None
                    eye,hand=FORCES[phase]
                    rows.append(a.session.tick(frame,eye=eye,hand=hand));a.cursor+=1
                    if (step+1)%30==0:
                        before=a.session.engine.time_us;t=time.perf_counter()
                        update=calibrate_instrument(a,rows[-8:])
                        assert a.session.engine.time_us==before
                        learning.append({'step':step+1,'sim_time_us':before,'wall_seconds':time.perf_counter()-t,'update':update})
                path=work/'segments'/f's{segment}';t=time.perf_counter();a.save(path/'whole')
                save_seconds=time.perf_counter()-t
                m.original(path/'trajectory.json.gz',rows,compressed=True);m.original(path/'calibration.json',learning)
                restored=None
                if segment==2:
                    before=digest(a.canonical());del a;gc.collect();t=time.perf_counter();a=Whole.restore(path/'whole')
                    restored={'canonical_sha256':digest(a.canonical()),'equal':digest(a.canonical())==before,
                              'wall_seconds':time.perf_counter()-t};assert restored['equal']
                state=a.session.engine.capture_state().to_dict()
                result={'segment':segment,'time_us':a.session.engine.time_us,'frames':len(rows),
                    'motor_updates':a.motor.committed_updates,'word_updates':a.words.committed_updates,
                    'nodes':len(state['nodes']),'edges':len(state['edges']),'save_seconds':save_seconds,
                    'wall_seconds':time.perf_counter()-started,'restored':restored,'scientific_origins':0}
                m.original(path/'result.json',result);(work/'in-flight.json').unlink();completed+=1
                m.atomic_json(work/'progress.json',{'completed':completed,'total':5,'last':segment,'epoch':time.time()})
                r.append('result',f's{segment}',result,request_id=uuid5(NS,f'result:{segment}'));r.synchronize()
                print(json.dumps({'completed':completed,'total':5,'result':result,'pending':r.status['pending']}),flush=True)
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>512*2**20:
                    if not (work/'STOP').exists():m.original(work/'STOP',{'reason':'registered 512MiB original cap','epoch':time.time()})
                    break
                del state,rows;gc.collect()
        m.atomic_json(work/'status.json',{'state':'awaiting-analysis' if completed==5 and not (work/'STOP').exists() else 'resource-paused',
                                        'completed':completed,'total':5,'scientific_origins':0})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','run','status','check'));p.add_argument('--work',type=Path,default=WORK)
    a=p.parse_args();w=a.work.resolve()
    if a.command=='check':print(json.dumps(m.resource_check(w)))
    elif a.command=='status':print(json.dumps({n:m.read(w/n) if (w/n).exists() else None for n in ('host.json','progress.json','status.json','STOP','in-flight.json','resource-summary.json')}))
    else:{'register':register,'run':run}[a.command](w)
