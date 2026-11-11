"""Serial new-origin confirmation, reusing the frozen five-system measurement."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID,uuid5

import closure_driver as old
import closure_rig as g
import m3_confirm_spec as spec
import pilot_m2 as m

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m3-confirmation-v2')
NS=UUID('b7cc411b-e608-4ebc-9161-80819830bde6')


def declared_sham_equal(parent,sham):
    expected=parent.save()
    expected['branch']={'parent_sha256':m.digest(parent.save()),'label':'sham','time_us':parent.time}
    return sham.save()==expected


def unit(folder,origin):
    case=spec.cases()[origin];assert g.case_seed('X3',case['rig_origin'])==case['seed']
    systems={}
    for kind in spec.KINDS:
        systems[kind]=old.x3(folder/kind,case['rig_origin'],kind)
    valid=all(row['selection'] is None or row['selection']['passed'] for r in systems.values() for row in r['histories'])
    return {'origin':origin,'case':case,'systems':systems,'valid':valid}


def register(work):
    work.mkdir(parents=True,exist_ok=True)
    with m.worker_lock(work),m.connection() as client:
        if (work/'platform.json').exists():raise RuntimeError('already registered')
        title='2026-10-16 机制发现 · M3 四项判据64新来源确认装置修订v2'
        matches=[p for p in client.call('projects.list',{}) if p['name']==title]
        if len(matches)>1:raise RuntimeError('ambiguous project')
        project=matches[0] if matches else client.request('POST','/api/v2/projects',body={'name':title})
        resource='mechanism-m3-confirmation-v2-20261016'
        m.original(work/'platform.json',{'project_id':project['id'],'resource_id':resource})
        names=['m3_confirm_driver_v2.py','m3_confirm_spec.py','m3_confirm_analyze.py','m3_confirm_audit.py',
               'm3-confirmation-v2-protocol.zh.md','m3-confirmation-v2-protocol.en.md','m3-confirmation-power.json',
               'm3_confirm_power.py','m3_confirm_driver.py','m3-confirmation-protocol.zh.md','m3-confirmation-protocol.en.md','closure_driver.py','closure_rig.py','closure_analyze.py','closure_audit.py',
               'pilot_m1.py','pilot_m2.py','pilot_m3.py']
        paths=[HERE/n for n in names]+[m.ROOT/'lab/tools/study_lock.py',
               m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest={p.relative_to(m.ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json',manifest);m.original(work/'implementation.json',m.capture_implementation('native'))
        m.original(work/'cases.json',spec.cases())
        for p in paths:m.original(work/'frozen'/p.name,{'utf8':p.read_text(encoding='utf-8')})
        r=m.ResearchRecorder(work,project['id'],client=client)
        r.register({'source_key':'mechanism-discovery:m3-confirmation-v2:20261016','title':title,
                    'classification':'formal','execution_status':'running','executor':'ai','kernels':[m.KERNEL],
                    'protocol':(HERE/'m3-confirmation-v2-protocol.zh.md').read_text(encoding='utf-8'),
                    'protocol_version':m.digest(manifest),'required_roles':['protocol','report','note'],
                    'metadata':{'work':str(work),'origins':spec.N,'system_implementations':5,
                                'criteria':'cross-system-criteria/2','Core_changed':False,'E69_resumed':False}},
                   request_id=uuid5(NS,'register'))
        r.synchronize(strict=True)
        client.request('POST','/api/v2/storage/resources',body={'resource_id':resource,
            'target_id':'managed-research-experiments','relative_path':'2026-10-16-mechanism-discovery/m3-confirmation-v2',
            'registered_work_path':str(work),'writer_mode':'cooperative','expected_revision':0},
            headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'resource'))})
        client.request('POST','/api/v2/storage/record-evidence-grants',body={'project_id':project['id'],'resource_id':resource},
                       headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'grant'))})
        for lang in ('zh','en'):
            r.text({'request_id':str(uuid5(NS,'protocol:'+lang)),'identity':str(uuid5(NS,'doc:'+lang)),
                    'expected_revision':0,'kind':'protocol','title':'M3 independent confirmation apparatus revision v2 '+lang,
                    'markdown':(HERE/f'm3-confirmation-v2-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True);print(json.dumps({'project':project['id'],'record':r.experiment,'status':r.status}),flush=True)


def apparatus(work):
    with m.worker_lock(work):
        m.frozen_check(work);m.resource_check(work)
        if any((work/n).exists() for n in ('apparatus.json','apparatus-in-flight.json')):raise RuntimeError('apparatus already attempted')
        m.original(work/'apparatus-in-flight.json',{'pid':os.getpid(),'epoch':time.time()})
        systems={}
        for kind in spec.KINDS:
            p=g.Rig(kind,spec.APPARATUS_SEED);records=g.teaching(p,0)
            selected=g.rnn_selection(p,records) if kind=='fixed-rnn-reader' else None
            old.save(work/'apparatus',kind+'-parent',p)
            hashes={}
            for mode in ('plain','observed','restored','paused'):
                child=g.Rig.restore(p.save())
                g.probe(child,'X',second='Y',frequent=mode=='observed',restore_mid=mode=='restored',pause_mid=mode=='paused')
                hashes[mode]=m.digest(child.save());old.save(work/'apparatus',kind+'-'+mode,child)
            restored,_=g.intervene(p,'restored',selected);sham,_=g.intervene(p,'sham',selected)
            systems[kind]={'whole_hashes':hashes,'selection':selected,
                           'sham_only_declared_lineage':declared_sham_equal(p,sham),'restoration_exact':restored.save()==p.save(),
                           'passed':len(set(hashes.values()))==1 and restored.save()==p.save() and declared_sham_equal(p,sham)
                           and (selected is None or selected['passed'])}
        result={'passed':all(r['passed'] for r in systems.values()),'systems':systems,
                'seed':spec.APPARATUS_SEED,'scientific_origins':0}
        m.original(work/'apparatus.json',result)
        if not result['passed']:raise RuntimeError('apparatus invalid; preserve marker')
        (work/'apparatus-in-flight.json').unlink();print(json.dumps(result),flush=True)


def run(work):
    import psutil
    with m.worker_lock(m.DEFAULT_WORK),m.worker_lock(work),m.connection() as client:
        m.frozen_check(work)
        if any((work/n).exists() for n in ('STOP','in-flight.json','apparatus-in-flight.json','status.json','host.json')):
            raise RuntimeError('prior attempt or unresolved marker; do not rerun')
        if not m.read(work/'apparatus.json')['passed']:raise RuntimeError('apparatus failed')
        m.atomic_json(work/'host.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
        r=m.recorder(work,client);done=0
        with m.Guard(work) as guard:
            for origin in range(spec.N):
                if (work/'STOP').exists():break
                if not guard.thread.is_alive():raise RuntimeError('resource guard absent')
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>4*2**30:
                    m.original(work/'STOP',{'reason':'4GiB original cap'});break
                name=f'o{origin}';folder=work/'units'/name
                m.original(work/'in-flight.json',{'unit':name,'pid':os.getpid(),'epoch':time.time()})
                result=unit(folder,origin);m.original(folder/'result.json',result)
                (work/'in-flight.json').unlink();done+=1
                m.atomic_json(work/'progress.json',{'completed':done,'total':spec.N,'last':name,'epoch':time.time()})
                r.append('result',name,{'unit':name,'valid':result['valid'],'systems':5,
                         'sha256':hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()},request_id=uuid5(NS,'result:'+name))
                r.synchronize();print(json.dumps({'completed':done,'total':spec.N,'pending':r.status['pending']}),flush=True)
                if not result['valid']:
                    m.original(work/'STOP',{'reason':'matching validity failed','unit':name});break
        m.atomic_json(work/'status.json',{'state':'awaiting-analysis' if done==spec.N else 'resource-paused','completed':done,'total':spec.N})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','apparatus','run','status','check'))
    p.add_argument('--work',type=Path,default=WORK);a=p.parse_args();work=a.work.resolve()
    if a.command=='check':print(json.dumps(m.resource_check(work)))
    elif a.command=='status':print(json.dumps({n:m.read(work/n) if (work/n).exists() else None for n in
        ('platform.json','host.json','progress.json','status.json','STOP','in-flight.json','resource-summary.json')}))
    else:{'register':register,'apparatus':apparatus,'run':run}[a.command](work)
