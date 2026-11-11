"""One-shot registered bounded M2 expression diagnosis, preserving old runs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5
import psutil
import m2_cue_rig as spec
import pilot_m2 as m

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-cue-diagnostic-v1')
NS=UUID('97738272-0f4a-46b9-a74d-58892e56070f')


def sources():
    return [HERE/n for n in ('m2_cue_driver.py','m2_cue_rig.py','m2_cue_analyze.py','m2_cue_audit.py',
        'test_m2_cue.py','m2-cue-diagnostic-protocol.zh.md','m2-cue-diagnostic-protocol.en.md',
        'm2_relearning_cal_driver.py','m2_relearning_cal_spec.py','closure_rig.py','closure_audit.py',
        'pilot_m2.py','pilot_m1.py','pilot_m3.py')]+[
        m.ROOT/'lab/tools/study_lock.py',m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']


def register(work):
    work.mkdir(parents=True,exist_ok=True)
    with m.worker_lock(work),m.connection() as client:
        if (work/'platform.json').exists():raise RuntimeError('already registered')
        title='2026-10-16 机制发现 · M2同末态弱强提示表达诊断'
        matches=[p for p in client.call('projects.list',{}) if p['name']==title]
        if len(matches)>1:raise RuntimeError('ambiguous project')
        project=matches[0] if matches else client.request('POST','/api/v2/projects',body={'name':title})
        resource='mechanism-m2-cue-diagnostic-v1-20261016'
        m.original(work/'platform.json',{'project_id':project['id'],'resource_id':resource})
        paths=sources();manifest={p.relative_to(m.ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json',manifest);m.original(work/'implementation.json',m.capture_implementation('native'))
        m.original(work/'cases.json',spec.cases())
        for p in paths:m.original(work/'frozen'/p.name,{'utf8':p.read_text(encoding='utf-8')})
        r=m.ResearchRecorder(work,project['id'],client=client)
        r.register({'source_key':'mechanism-discovery:m2-cue-diagnostic-v1:20261016','title':title,
                    'classification':'development','execution_status':'running','executor':'ai','kernels':[m.KERNEL],
                    'protocol':(HERE/'m2-cue-diagnostic-protocol.zh.md').read_text(encoding='utf-8'),
                    'protocol_version':m.digest(manifest),'required_roles':['protocol','report','note'],
                    'metadata':{'work':str(work),'origins':spec.N,'study_phase':'fixed-parent cue expression diagnosis',
                                'Core_changed':False,'E69_resumed':False,'savings_test':False}},request_id=uuid5(NS,'register'))
        r.synchronize(strict=True)
        client.request('POST','/api/v2/storage/resources',body={'resource_id':resource,
            'target_id':'managed-research-experiments','relative_path':'2026-10-16-mechanism-discovery/m2-cue-diagnostic-v1',
            'registered_work_path':str(work),'writer_mode':'cooperative','expected_revision':0},
            headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'resource'))})
        client.request('POST','/api/v2/storage/record-evidence-grants',body={'project_id':project['id'],'resource_id':resource},
                       headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'grant'))})
        for lang in ('zh','en'):
            r.text({'request_id':str(uuid5(NS,'protocol:'+lang)),'identity':str(uuid5(NS,'doc:'+lang)),
                    'expected_revision':0,'kind':'protocol','title':'M2 cue expression diagnosis '+lang,
                    'markdown':(HERE/f'm2-cue-diagnostic-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps({'project':project['id'],'record':r.experiment,'status':r.status}),flush=True)


def apparatus(work):
    with m.worker_lock(work):
        m.frozen_check(work);m.resource_check(work)
        if any((work/n).exists() for n in ('apparatus.json','apparatus-in-flight.json')):raise RuntimeError('apparatus already attempted')
        m.original(work/'apparatus-in-flight.json',{'pid':os.getpid(),'epoch':time.time()})
        result=spec.instrument(work/'apparatus');m.original(work/'apparatus.json',result)
        if not result['passed']:raise RuntimeError('apparatus failed; preserve marker')
        (work/'apparatus-in-flight.json').unlink()
        print(json.dumps(result),flush=True)


def run(work):
    with m.worker_lock(m.DEFAULT_WORK),m.worker_lock(work),m.connection() as client:
        m.frozen_check(work);m.resource_check(work)
        if any((work/n).exists() for n in ('STOP','in-flight.json','apparatus-in-flight.json','status.json','host.json')):
            raise RuntimeError('prior attempt or unresolved marker; do not repeat')
        if not m.read(work/'apparatus.json')['passed']:raise RuntimeError('apparatus failed')
        m.original(work/'host.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
        r=m.recorder(work,client);done=0
        with m.Guard(work) as guard:
            for origin in range(spec.N):
                if (work/'STOP').exists():break
                if not guard.thread.is_alive():raise RuntimeError('resource guard absent')
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>4*2**30:
                    m.original(work/'STOP',{'reason':'4GiB original cap'});break
                name=f'o{origin}';folder=work/'units'/name
                m.original(work/'in-flight.json',{'unit':name,'pid':os.getpid(),'epoch':time.time()})
                result=spec.unit(folder,origin);m.original(folder/'result.json',result)
                (work/'in-flight.json').unlink();done+=1
                m.atomic_json(work/'progress.json',{'completed':done,'total':spec.N,'last':name,'epoch':time.time()})
                r.append('result',name,{'unit':name,'sha256':hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()},request_id=uuid5(NS,'result:'+name))
                r.synchronize();print(json.dumps({'completed':done,'total':spec.N,'pending':r.status['pending']}),flush=True)
        m.atomic_json(work/'status.json',{'state':'awaiting-analysis' if done==spec.N else 'resource-paused','completed':done,'total':spec.N})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','apparatus','run','status','check'));p.add_argument('--work',type=Path,default=WORK)
    a=p.parse_args();work=a.work.resolve()
    if a.command=='check':print(json.dumps(m.resource_check(work)))
    elif a.command=='status':print(json.dumps({n:m.read(work/n) if (work/n).exists() else None for n in ('platform.json','host.json','progress.json','status.json','STOP','in-flight.json','resource-summary.json')}))
    else:{'register':register,'apparatus':apparatus,'run':run}[a.command](work)
