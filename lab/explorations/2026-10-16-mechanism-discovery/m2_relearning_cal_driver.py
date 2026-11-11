"""Calibrate a bounded learning-curve measurement before testing savings.

New calibration sources only; whole-state continuous within each declared dose
branch. No alteration or reload of historical experimental individuals.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5

import closure_rig as g
import m2_relearning_cal_spec as spec
import pilot_m2 as m

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-relearning-assay-v1')
NS=UUID('6f7d32c2-2d07-45e8-9c86-374b8989860a')


def save(folder,name,rig):
    path=folder/(name+'.json.gz')
    return {'path':path.name, **m.original(path,rig.save(),compressed=True)}


def lesson(rig,history,dose,**observation):
    start=rig.time
    rig.tick(start,dict.fromkeys('XYA' if history==0 else 'XYB',dose))
    rig.advance(start+2_000_000,{start+j*500_000:{'K':.2} for j in range(1,5)})
    result=g.probe(rig,'X',spec.PROBE_DOSE,**observation)
    return {'start_us':start,'end_us':rig.time,'probe':result}


def unit(folder,origin):
    case=spec.cases()[origin]
    parent=g.Rig('threemind',case['seed'],'S')
    save(folder,'birth',parent)
    # An age-matched, unstimulated-by-task reference receives only the declared K/N maintenance.
    g.teaching(parent,0,delay=spec.DELAY_SECONDS,trained=False)
    save(folder,'naive-parent',parent)
    branches=[]
    for dose in spec.DOSES:
        for history in (0,1):
            label=f'd{dose:.2f}-h{history}'
            child=parent.fork(label)
            initial=save(folder,label+'-initial',child)
            baseline=g.probe(child,'X',spec.PROBE_DOSE)
            baseline_checkpoint=save(folder,label+'-baseline',child)
            rows=[]
            for j in range(1,spec.LESSONS+1):
                row=lesson(child,history,dose)
                rows.append({'lesson':j,**row,'checkpoint':save(folder,f'{label}-lesson{j:02d}',child)})
            branches.append({'dose':dose,'history':history,'initial':initial,'baseline':baseline,
                             'baseline_checkpoint':baseline_checkpoint,'lessons':rows})
    return {'origin':origin,'case':case,'valid':True,'branches':branches}


def register(work):
    work.mkdir(parents=True,exist_ok=True)
    with m.worker_lock(work),m.connection() as client:
        if (work/'platform.json').exists(): raise RuntimeError('already registered')
        title='2026-10-16 机制发现 · M2 重学测量窗口校准'
        matches=[p for p in client.call('projects.list',{}) if p['name']==title]
        if len(matches)>1: raise RuntimeError('ambiguous project')
        project=matches[0] if matches else client.request('POST','/api/v2/projects',body={'name':title})
        resource='mechanism-m2-relearning-assay-v1-20261016'
        m.original(work/'platform.json',{'project_id':project['id'],'resource_id':resource})
        paths=[Path(__file__),HERE/'m2_relearning_cal_spec.py',HERE/'m2_relearning_cal_analyze.py',
               HERE/'m2_relearning_cal_audit.py',HERE/'m2-relearning-assay-protocol.zh.md',
               HERE/'m2-relearning-assay-protocol.en.md',HERE/'closure_rig.py',HERE/'closure_audit.py',
               HERE/'pilot_m2.py',HERE/'pilot_m1.py',HERE/'pilot_m3.py',m.ROOT/'lab/tools/study_lock.py',
               m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest={p.relative_to(m.ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json',manifest)
        m.original(work/'implementation.json',m.capture_implementation('native'))
        m.original(work/'cases.json',spec.cases())
        for p in paths: m.original(work/'frozen'/p.name,{'utf8':p.read_text(encoding='utf-8')})
        r=m.ResearchRecorder(work,project['id'],client=client)
        r.register({'source_key':'mechanism-discovery:m2-relearning-assay-v1:20261016','title':title,
                    'classification':'calibration','execution_status':'running','executor':'ai','kernels':[m.KERNEL],
                    'protocol':(HERE/'m2-relearning-assay-protocol.zh.md').read_text(encoding='utf-8'),
                    'protocol_version':m.digest(manifest),'required_roles':['protocol','report','note'],
                    'metadata':{'work':str(work),'study_phase':'assay calibration','origins':spec.N,
                                'savings_effect_tested':False,'Core_changed':False,'E69_resumed':False}},
                   request_id=uuid5(NS,'register'))
        r.synchronize(strict=True)
        client.request('POST','/api/v2/storage/resources',body={'resource_id':resource,
            'target_id':'managed-research-experiments','relative_path':'2026-10-16-mechanism-discovery/m2-relearning-assay-v1',
            'registered_work_path':str(work),'writer_mode':'cooperative','expected_revision':0},
            headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'resource'))})
        client.request('POST','/api/v2/storage/record-evidence-grants',body={'project_id':project['id'],'resource_id':resource},
                       headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'grant'))})
        for lang in ('zh','en'):
            r.text({'request_id':str(uuid5(NS,'protocol:'+lang)),'identity':str(uuid5(NS,'doc:'+lang)),
                    'expected_revision':0,'kind':'protocol','title':'M2 relearning assay v1 '+lang,
                    'markdown':(HERE/f'm2-relearning-assay-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps({'project':project['id'],'record':r.experiment,'status':r.status}),flush=True)


def apparatus(work):
    with m.worker_lock(work):
        m.frozen_check(work); m.resource_check(work)
        if any((work/n).exists() for n in ('apparatus.json','apparatus-in-flight.json')):
            raise RuntimeError('apparatus already attempted')
        m.original(work/'apparatus-in-flight.json',{'pid':os.getpid(),'epoch':time.time()})
        p=g.Rig('threemind',spec.APPARATUS_SEED,'S')
        g.teaching(p,0,delay=spec.DELAY_SECONDS,trained=False)
        save(work/'apparatus','parent',p)
        hashes={}
        for mode in ('plain','observed','restored','paused'):
            c=g.Rig.restore(p.save())
            g.probe(c,'X',spec.PROBE_DOSE)
            lesson(c,0,.20,frequent=mode=='observed',restore_mid=mode=='restored',pause_mid=mode=='paused')
            hashes[mode]=m.digest(c.save()); save(work/'apparatus',mode,c)
        result={'passed':len(set(hashes.values()))==1,'whole_hashes':hashes,
                'scientific_savings_origins':0,'seed':spec.APPARATUS_SEED}
        m.original(work/'apparatus.json',result)
        if not result['passed']: raise RuntimeError('measurement apparatus invalid; preserve marker')
        (work/'apparatus-in-flight.json').unlink()
        print(json.dumps(result),flush=True)


def run(work):
    import psutil
    with m.worker_lock(m.DEFAULT_WORK),m.worker_lock(work),m.connection() as client:
        m.frozen_check(work)
        if any((work/n).exists() for n in ('STOP','in-flight.json','apparatus-in-flight.json','status.json','host.json')):
            raise RuntimeError('existing attempt or unresolved marker; inspect instead of rerunning')
        if not m.read(work/'apparatus.json')['passed']: raise RuntimeError('apparatus did not pass')
        m.atomic_json(work/'host.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
        r=m.recorder(work,client); done=0
        with m.Guard(work) as guard:
            for origin in range(spec.N):
                if (work/'STOP').exists(): break
                if not guard.thread.is_alive(): raise RuntimeError('resource guard absent')
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>4*2**30:
                    m.original(work/'STOP',{'reason':'4GiB original cap'}); break
                name=f'o{origin}'; folder=work/'units'/name
                m.original(work/'in-flight.json',{'unit':name,'pid':os.getpid(),'epoch':time.time()})
                result=unit(folder,origin); m.original(folder/'result.json',result)
                (work/'in-flight.json').unlink(); done+=1
                m.atomic_json(work/'progress.json',{'completed':done,'total':spec.N,'last':name,'epoch':time.time()})
                r.append('result',name,{'unit':name,'assay_calibration':True,
                    'sha256':hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()},request_id=uuid5(NS,'result:'+name))
                r.synchronize(); print(json.dumps({'completed':done,'total':spec.N,'pending':r.status['pending']}),flush=True)
        m.atomic_json(work/'status.json',{'state':'awaiting-analysis' if done==spec.N else 'resource-paused',
                                        'completed':done,'total':spec.N})


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('command',choices=('register','apparatus','run','status','check'))
    p.add_argument('--work',type=Path,default=WORK); a=p.parse_args(); work=a.work.resolve()
    if a.command=='check': print(json.dumps(m.resource_check(work)))
    elif a.command=='status': print(json.dumps({n:m.read(work/n) if (work/n).exists() else None for n in
        ('platform.json','host.json','progress.json','status.json','STOP','in-flight.json','resource-summary.json')}))
    else: {'register':register,'apparatus':apparatus,'run':run}[a.command](work)
