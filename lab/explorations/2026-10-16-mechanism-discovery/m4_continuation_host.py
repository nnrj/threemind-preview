"""One reviewed continuation, fresh host per existing complete M4 stage.

The supervisor holds the global study lock. Workers require its exact live
identity and a single-use ticket; all science stays in frozen v2 methods.
"""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from uuid import UUID,uuid5
import psutil
import pilot_m2 as m

NS=UUID('a889ae07-9367-4a65-af5d-4571c26a3ef6')
HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m4-balanced-v2')
REL='continuations/c111-private3-20261017'
EXPECTED_SHA='144670e21efb4454ba3a01aa81a9694813cfa8168bf68bf72f80559b4a3d5840'


def frozen(work,expected):
    folder=work/REL;plan=m.read(folder/'plan.json')
    if m.digest(plan)!=expected:raise ValueError('continuation plan hash mismatch')
    m.frozen_check(work)
    for name,sha in plan['files'].items():
        path=(m.ROOT/name).resolve()
        if not path.is_relative_to(m.ROOT.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('continuation source changed: '+name)
    return plan


class Guard(m.Guard):
    def __init__(self,work,evidence,*,private_gib,remaining_seconds):
        super().__init__(work);self.evidence=evidence;self.private_gib=private_gib;self.remaining_seconds=remaining_seconds

    def watch(self):
        while not self.stop.is_set():
            try:
                self.last=m.resource_check(self.work)
                private=psutil.Process().memory_info().private;self.peak_private=max(self.peak_private,private)
                for k,v in self.last['available_bytes'].items():self.minimum[k]=min(v,self.minimum.get(k,v))
                if private>self.private_gib*2**30:raise RuntimeError(f'continuation host exceeds {self.private_gib}GiB private budget')
                if time.monotonic()-self.started>self.remaining_seconds:raise RuntimeError('original cumulative eight-hour M4 host budget')
            except Exception as exc:
                if not (self.work/'STOP').exists():
                    try:m.original(self.work/'STOP',{'reason':str(exc),'epoch':time.time(),'last':self.last,'host_pid':os.getpid()})
                    except (FileExistsError,RuntimeError):
                        if not (self.work/'STOP').exists():raise
                return
            self.stop.wait(1)

    def __exit__(self,*args):
        self.stop.set();self.thread.join(3)
        m.original(self.evidence/'resource-summary.json',{'peak_private_bytes':self.peak_private,
                   'minimum_available_bytes':self.minimum,'wall_seconds':time.monotonic()-self.started,
                   'private_budget_gib':self.private_gib,'system_reserves_gib':[5,4,5,25]})


def live_identity(info,required):
    try:
        p=psutil.Process(info['pid'])
        return abs(p.create_time()-info['created_at'])<.01 and all(x in p.cmdline() for x in required)
    except (psutil.NoSuchProcess,psutil.AccessDenied):return False


def worker(work,expected,ticket_path):
    import torch
    import m4_stage_continuation as stages
    torch.set_num_threads(1)
    plan=frozen(work,expected);folder=work/REL
    ticket_path=ticket_path.resolve()
    if not ticket_path.is_relative_to((folder/'workers').resolve()):raise ValueError('ticket escapes continuation')
    ticket=m.read(ticket_path);supervisor=m.read(folder/'host.json')
    if not live_identity(supervisor,[str(Path(__file__).resolve()),'run','--plan-sha256',expected]):raise RuntimeError('supervisor missing/reused')
    if ticket['supervisor']!=supervisor or ticket['plan_sha256']!=expected:raise RuntimeError('ticket supervisor or plan mismatch')
    if not any(p.pid==supervisor['pid'] and abs(p.create_time()-supervisor['created_at'])<.01 for p in psutil.Process().parents()):
        raise RuntimeError('worker was not created by the registered supervisor')
    evidence=ticket_path.parent
    with m.worker_lock(work),m.connection() as client:
        if (evidence/'host.json').exists() or (work/'STOP').exists():raise RuntimeError('single-use ticket spent or STOP')
        if ticket['step']!=stages.next_stage(work):raise RuntimeError('stale work ticket')
        m.original(evidence/'host.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
        r=m.recorder(work,client)
        def record(value):
            label=f'o{value["origin"]}:{value["stage"]}'
            # Same idempotency namespace as the original M4 v2 boundary writer.
            old=UUID('9cf7d155-2f6d-4913-a23e-52fb4609163c')
            r.append('result',label,value,request_id=uuid5(old,'boundary:'+label));r.synchronize()
            print(json.dumps({'boundary':label,'time_us':value['time_us'],'pending':r.status['pending']}),flush=True)
        paused=False;value=None
        with Guard(work,evidence,private_gib=3,remaining_seconds=ticket['remaining_seconds']) as guard:
            if not guard.thread.is_alive() or (work/'STOP').exists():raise RuntimeError('resource guard not ready')
            try:value=stages.execute(work,ticket['step'],guard,record)
            except stages.rig.BoundaryPause:paused=True
        if value is not None:
            origin=value['origin'];old=UUID('9cf7d155-2f6d-4913-a23e-52fb4609163c')
            r.append('result',f'o{origin}',value,request_id=uuid5(old,'result:'+str(origin)));r.synchronize()
            m.atomic_json(work/'progress.json',{'completed':origin+1,'total':8,'last':origin,'epoch':time.time()})
        if (work/'in-flight.json').exists():raise RuntimeError('worker returned with in-flight marker')
        m.original(evidence/'completed.json',{'step':ticket['step'],'paused':paused or (work/'STOP').exists(),
                   'current':m.read(work/'current-boundary.json'),'pending':r.status['pending'],'epoch':time.time()})
        return 3 if paused or (work/'STOP').exists() else 0


def validate_retirement(work,folder,plan):
    """All evidence remains; only exactly matched active STOP is retired."""
    if (folder/'host.json').exists() or (folder/'STOP.retired').exists():raise RuntimeError('continuation already attempted')
    if (work/'in-flight.json').exists():raise RuntimeError('in-flight; do not recover')
    old=m.read(work/'host.json')
    if live_identity(old,['run']):raise RuntimeError('old scientific host remains alive')
    current=m.read(work/'current-boundary.json')
    if current!=plan['current'] or current['canonical_sha256']!=EXPECTED_SHA:raise RuntimeError('complete current state changed')
    active=(work/'STOP').read_bytes();archived=(work/'pauses/c111-private3-20261017/STOP').read_bytes()
    if active!=archived or hashlib.sha256(active).hexdigest()!=plan['stop_sha256']:raise RuntimeError('different active STOP')
    if m.read(work/'status.json')['state']!='resource-paused':raise RuntimeError('not a complete pause')
    prof=m.read(work/'pauses/c111-private3-20261017/readonly-restoration-profile.json')
    if not prof['exact'] or prof['simulation_advanced'] or prof['peak_private_bytes']>=3*2**30:raise RuntimeError('restoration evidence invalid')
    if not m.read(folder/'instrument/verification.json')['passed']:raise RuntimeError('fresh-process continuation instrument failed')
    resource=m.resource_check(work)
    # Entirely new host allocation + small supervisor, above unchanged reserves.
    for key in ('commit','ram'):
        if resource['available_bytes'][key]<resource['limits_bytes'][key]+4*2**30:raise RuntimeError('insufficient startup headroom')
    size=sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
    if size>4*2**30 or resource['available_bytes']['data_disk']+size<38_464_092_091:
        raise RuntimeError('originals/archive/API readback forecast or 4GiB original cap insufficient')
    # The independent canonical audit and exact restoration already completed.
    # Rehash their unchanged bytes here without retaining a second big subject.
    checkpoint=(work/current['path']).resolve();receipt=m.read(checkpoint/'complete.json')
    if receipt['canonical_sha256']!=EXPECTED_SHA:raise RuntimeError('current whole state mismatch')
    actual={p.relative_to(checkpoint).as_posix() for p in checkpoint.rglob('*') if p.is_file()}-{'complete.json'}
    if actual!=set(receipt['files']):raise RuntimeError('current whole file membership differs')
    for rel,sha in receipt['files'].items():
        path=(checkpoint/rel).resolve()
        if not path.is_relative_to(checkpoint) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise RuntimeError('current whole file differs')
    for ref in receipt['dependencies']:
        path=(work/'units/o0'/ref['path']).resolve()
        if not path.is_relative_to((work/'units/o0').resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
            raise RuntimeError('current immutable corpus differs')
    resource=m.resource_check(work)
    for key in ('commit','ram'):
        if resource['available_bytes'][key]<resource['limits_bytes'][key]+4*2**30:raise RuntimeError('post-audit startup headroom')
    m.original(folder/'locked-preflight.json',{'current':current,'resources':resource,'original_bytes':size,
               'STOP_sha256':plan['stop_sha256'],'no_in_flight':True,'exact_whole_state':True,'epoch':time.time()})
    source=(work/'STOP').resolve();target=(folder/'STOP.retired').resolve()
    if not source.is_relative_to(work.resolve()) or not target.is_relative_to(work.resolve()):raise ValueError('retirement escapes work')
    if source.read_bytes()!=active:raise RuntimeError('STOP changed while locked')
    source.rename(target)


def run(work,expected):
    folder=work/REL;plan=frozen(work,expected)
    with m.worker_lock(m.DEFAULT_WORK):
        with m.worker_lock(work):
            validate_retirement(work,folder,plan)
            m.original(folder/'host.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
            m.atomic_json(work/'status.json',{'state':'running-continuation','completed':0,'total':8,'current':plan['current']})
        remaining=8*3600-plan['prior_host_wall_seconds'];started=time.monotonic();index=0;failure=None
        with Guard(work,folder,private_gib=1,remaining_seconds=remaining) as guard:
            while not (work/'STOP').exists():
                import m4_continuation_plan as stages
                step=stages.next_stage(work)
                if step is None:break
                if not guard.thread.is_alive():raise RuntimeError('supervisor guard disappeared')
                evidence=folder/'workers'/f'{index:03d}-o{step["origin"]}-{step["stage"]}'
                evidence.mkdir(parents=True,exist_ok=False)
                ticket=evidence/'ticket.json'
                m.original(ticket,{'step':step,'remaining_seconds':max(0.,remaining-(time.monotonic()-started)),
                           'supervisor':m.read(folder/'host.json'),'plan_sha256':expected,'epoch':time.time()})
                command=[sys.executable,'-X','utf8',str(Path(__file__).resolve()),'worker','--work',str(work),
                         '--plan-sha256',expected,'--ticket',str(ticket)]
                with (evidence/'stdout.log').open('xb') as out,(evidence/'stderr.log').open('xb') as err:
                    child=subprocess.Popen(command,cwd=m.ROOT,stdout=out,stderr=err,
                                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    code=child.wait()
                print(json.dumps({'stage':step,'exit_code':code,'epoch':time.time()}),flush=True)
                if code not in (0,3) or not (evidence/'completed.json').exists():
                    failure={'stage':step,'exit_code':code,'evidence':str(evidence),'epoch':time.time()}
                    m.original(folder/'failure.json',failure);break
                if code==3 or (work/'STOP').exists():break
                index+=1
        completed=sum((work/'units'/f'o{i}/result.json').exists() for i in range(8))
        state='requires-review' if failure else 'resource-paused' if (work/'STOP').exists() else 'awaiting-analysis'
        if state=='awaiting-analysis' and completed!=8:raise RuntimeError('premature batch completion')
        m.atomic_json(work/'status.json',{'state':state,'completed':completed,'total':8,'current':m.read(work/'current-boundary.json')})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('run','worker'));p.add_argument('--work',type=Path,default=WORK)
    p.add_argument('--plan-sha256',required=True);p.add_argument('--ticket',type=Path)
    a=p.parse_args();work=a.work.resolve()
    if work!=WORK.resolve():raise ValueError('only the authorized M4 v2 work is supported')
    if a.command=='worker':
        if a.ticket is None:p.error('worker ticket required')
        sys.exit(worker(work,a.plan_sha256,a.ticket))
    run(work,a.plan_sha256)
