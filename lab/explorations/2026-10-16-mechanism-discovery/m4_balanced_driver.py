"""One-shot registered M4 balanced course; safe full-stage resource pauses."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
from uuid import UUID,uuid5
import psutil
import torch
import pilot_m2 as m
import m4_instrument_driver as base
import m4_balanced_rig as rig

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m4-balanced-v1')
NS=UUID('f12ab1b7-45a8-4fc8-98d0-2ba4e0e76af9')


class StudyGuard(m.Guard):
    def watch(self):
        while not self.stop.is_set():
            try:
                self.last=m.resource_check(self.work)
                private=psutil.Process().memory_info().private;self.peak_private=max(self.peak_private,private)
                for k,v in self.last['available_bytes'].items():self.minimum[k]=min(v,self.minimum.get(k,v))
                if private>3*2**30:raise RuntimeError('M4 physical host exceeds registered 3GiB private budget')
                if time.monotonic()-self.started>8*3600:raise RuntimeError('M4 registered eight-hour host budget')
            except Exception as exc:
                try:
                    if not (self.work/'STOP').exists():
                        m.original(self.work/'STOP',{'reason':str(exc),'epoch':time.time(),'last':self.last})
                except (FileExistsError,RuntimeError):
                    if not (self.work/'STOP').exists():raise
                return
            self.stop.wait(1)


def sources():
    return sorted(set(base.source_paths())|{HERE/n for n in (
        'm4_subject.py','m4_compact_subject.py','m4_compact_evidence.py','test_m4_compact_evidence.py',
        'm4_balanced_course.py','m4_regional_metrics.py','m4_balanced_rig.py','m4_balanced_driver.py',
        'm4_balanced_analyze.py','m4_balanced_audit.py','m4_instrument_audit_v3.py','test_m4_subject.py',
        'test_m4_balanced_course.py','test_m4_regional_metrics.py','test_m4_balanced_rig.py','test_m4_balanced_safety.py',
        'm4-balanced-protocol.zh.md','m4-balanced-protocol.en.md')})


def register(w):
    w.mkdir(parents=True,exist_ok=True)
    with m.worker_lock(w),m.connection() as client:
        if (w/'platform.json').exists():raise RuntimeError('already registered')
        title='2026-10-17 机制发现 · M4平衡眼手经历与选择性因果分工'
        found=[p for p in client.call('projects.list',{}) if p['name']==title];assert len(found)<=1
        project=found[0] if found else client.request('POST','/api/v2/projects',body={'name':title})
        resource='mechanism-m4-balanced-v1-20261017';m.original(w/'platform.json',{'project_id':project['id'],'resource_id':resource})
        manifest={p.relative_to(m.ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources()}
        m.original(w/'runner-manifest.json',manifest);m.original(w/'implementation.json',m.capture_implementation('native'))
        m.original(w/'cases.json',[{'origin':i,'seed':seed,'bank':rig.course.bank(i)} for i,seed in enumerate(rig.SEEDS)])
        for p in sources():m.original(w/'frozen'/p.relative_to(m.ROOT),{'utf8':p.read_text(encoding='utf-8')})
        r=m.ResearchRecorder(w,project['id'],client=client)
        r.register({'source_key':'mechanism:m4-balanced-v1:20261017','title':title,'classification':'development',
            'execution_status':'running','executor':'ai','kernels':[m.KERNEL],
            'protocol':(HERE/'m4-balanced-protocol.zh.md').read_text(encoding='utf-8'),
            'protocol_version':m.digest(manifest),'required_roles':['protocol','report','note'],
            'metadata':{'work':str(w),'origins':8,'study_phase':'balanced prospective functional and causal division',
                        'maximum_sim_seconds':4056,'private_GiB':3,'maximum_host_hours':8,'maximum_original_GiB':4,
                        'Core_changed':False,'E69_resumed':False}},request_id=uuid5(NS,'register'))
        r.synchronize(strict=True)
        client.request('POST','/api/v2/storage/resources',body={'resource_id':resource,'target_id':'managed-research-experiments',
            'relative_path':'2026-10-16-mechanism-discovery/m4-balanced-v1','registered_work_path':str(w),
            'writer_mode':'cooperative','expected_revision':0},headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'resource'))})
        client.request('POST','/api/v2/storage/record-evidence-grants',body={'project_id':project['id'],'resource_id':resource},
                       headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'grant'))})
        for lang in ('zh','en'):
            r.text({'request_id':str(uuid5(NS,'protocol:'+lang)),'identity':str(uuid5(NS,'doc:'+lang)),
                    'expected_revision':0,'kind':'protocol','title':'M4 balanced functional division protocol '+lang,
                    'markdown':(HERE/f'm4-balanced-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True);print(json.dumps({'project':project['id'],'record':r.experiment,'status':r.status}),flush=True)


def apparatus(w):
    torch.set_num_threads(1)
    with m.worker_lock(m.DEFAULT_WORK),m.worker_lock(w):
        m.frozen_check(w);m.resource_check(w)
        if any((w/n).exists() for n in ('apparatus.json','apparatus-in-flight.json','host.json','STOP')):raise RuntimeError('previous attempt or STOP')
        m.original(w/'apparatus-in-flight.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time()})
        folder=w/'apparatus';folder.mkdir()
        with base.InstrumentGuard(folder) as guard:
            assert guard.thread.is_alive();result=rig.instrument(folder)
        assert not (folder/'STOP').exists()
        m.original(w/'apparatus.json',result)
        if not result['passed']:raise RuntimeError('apparatus failed; preserve marker')
        (w/'apparatus-in-flight.json').unlink();print(json.dumps(result),flush=True)


def run(w):
    torch.set_num_threads(1)
    with m.worker_lock(m.DEFAULT_WORK),m.worker_lock(w),m.connection() as client:
        m.frozen_check(w)
        if any((w/n).exists() for n in ('STOP','in-flight.json','apparatus-in-flight.json','host.json','status.json','current-boundary.json')):
            raise RuntimeError('previous attempt or marker; no blind restart')
        assert m.read(w/'apparatus.json')['passed'] and not (w/'apparatus/STOP').exists()
        resources=m.resource_check(w)
        assert all(resources['available_bytes'][k]>=resources['limits_bytes'][k]+3*2**30 for k in ('commit','ram'))
        m.original(w/'host.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
        r=m.recorder(w,client);done=0;paused=False
        def record(value):
            label=f'o{value["origin"]}:{value["stage"]}'
            r.append('result',label,value,request_id=uuid5(NS,'boundary:'+label));r.synchronize()
            print(json.dumps({'boundary':label,'time_us':value['time_us'],'pending':r.status['pending']}),flush=True)
        with StudyGuard(w) as guard:
            try:
                for origin in range(8):
                    if (w/'STOP').exists():raise rig.BoundaryPause('resource stop before next origin')
                    unit=rig.Unit(w,origin,guard,record);result=unit.run()
                    m.original(w/'units'/f'o{origin}'/'result.json',result);done+=1
                    m.atomic_json(w/'progress.json',{'completed':done,'total':8,'last':origin,'epoch':time.time()})
                    r.append('result',f'o{origin}',result,request_id=uuid5(NS,'result:'+str(origin)));r.synchronize()
                    del unit;rig.gc.collect()
            except rig.BoundaryPause:paused=True
        m.atomic_json(w/'status.json',{'state':'resource-paused' if paused else 'awaiting-analysis',
                                      'completed':done,'total':8,'current':m.read(w/'current-boundary.json') if (w/'current-boundary.json').exists() else None})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','apparatus','run','status','check'));p.add_argument('--work',type=Path,default=WORK)
    a=p.parse_args();w=a.work.resolve()
    if a.command=='check':print(json.dumps(m.resource_check(w)))
    elif a.command=='status':print(json.dumps({n:m.read(w/n) if (w/n).exists() else None for n in ('host.json','progress.json','status.json','current-boundary.json','in-flight.json','STOP','resource-summary.json')}))
    else:{'register':register,'apparatus':apparatus,'run':run}[a.command](w)
