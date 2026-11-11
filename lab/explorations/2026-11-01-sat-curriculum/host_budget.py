"""Host-only 2 GiB process allowance; retains 5/4/5/25 GiB system reserves."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
import psutil
import driver as d
POLICY=dict(schema='sat-host-budget/1',private_bytes=2*2**30,wall_seconds=7200,
            reserve_gib=dict(commit=5,ram=4,system_disk=5,data_disk=25),poll_seconds=1,
            minimum_start_commit_bytes=8*2**30,pause='complete-boundary-only')
POLICY_SHA=d.base.digest(POLICY)
class Guard(d.base.Guard):
    def watch(self):
        while not self.stop.is_set():
            try:
                self.last=d.base.resource_check(self.work)
                private=psutil.Process().memory_info().private
                self.peak_private=max(self.peak_private,private)
                for k,v in self.last['available_bytes'].items():self.minimum[k]=min(v,self.minimum.get(k,v))
                if private>POLICY['private_bytes']:raise RuntimeError('SAT host private memory exceeds 2 GiB')
                if time.monotonic()-self.started>POLICY['wall_seconds']:raise RuntimeError('registered 2 hour host budget reached')
            except Exception as exc:
                try:
                    with (self.work/'STOP').open('x',encoding='utf-8') as f:
                        json.dump(dict(reason=str(exc),epoch=time.time(),last=self.last,policy_sha256=POLICY_SHA),f)
                except FileExistsError:pass
                return
            self.stop.wait(1)

def prepare_resume(work):
    with d.base.worker_lock(work),d.connection() as c:
        d.frozen(work);r=d.recorder(work,c)
        assert not (work/'in-flight.json').exists()
        host=d.load(work/'host.json')
        assert not(psutil.pid_exists(host['pid']) and abs(psutil.Process(host['pid']).create_time()-host['created_at'])<.01)
        stop=(work/'STOP').read_bytes();assert json.loads(stop)['reason']=='pilot process private memory exceeds 1 GiB'
        resources=d.resources(work);assert resources['available_bytes']['commit']>=POLICY['minimum_start_commit_bytes']
        folder=work/'origins/o0/normal';current=d.load(folder/'current.json')
        assert current['time_us']==0 and current['file']=='whole-birth.json.gz'
        assert d.sha(folder/current['file'])==current['sha256']
        student=d.Student.restore(folder,d.load(folder/current['file']))
        assert student.core.time_us==0 and student.reader.committed_updates==0
        for rel in ('STOP','host.json','status.json','resource-summary.json','run-01.stdout.log','run-01.stderr.log'):
            r.save_original('resumptions/birth-budget-2g/'+rel,(work/rel).read_bytes())
        for name in ('host_budget.py','host-budget-note.zh.md','host-budget-note.en.md'):
            r.save_original('host-policy/'+name,(d.HERE/name).read_bytes())
        d.save(work/'host-policy/policy.json',POLICY)
        d.save(work/'host-policy/resumption.json',dict(complete_boundary=current,stop_sha256=hashlib.sha256(stop).hexdigest(),
            policy_sha256=POLICY_SHA,wrapper_sha256=d.sha(Path(__file__)),resources=resources,internal_time_lost=0))
        for lang in ('zh','en'):
            r.text(dict(request_id=str(d.ident('host-policy-note-'+lang)),identity=str(d.ident('host-policy-doc-'+lang)),
                expected_revision=0,kind='note',title='SAT v2 host budget amendment '+lang,
                markdown=(d.HERE/f'host-budget-note.{lang}.md').read_text(encoding='utf-8-sig')))
        r.synchronize(strict=True)
        assert (work/'STOP').read_bytes()==stop
        (work/'STOP').unlink()
        d.state(work,state='ready-from-complete-birth',policy_sha256=POLICY_SHA)
        print(json.dumps(dict(policy_sha256=POLICY_SHA,wrapper_sha256=d.sha(Path(__file__)),pending=r.status['pending'],time_us=0)))

def run(work,policy_sha):
    assert policy_sha==POLICY_SHA and d.load(work/'host-policy/policy.json')==POLICY
    receipt=d.load(work/'host-policy/resumption.json');assert receipt['wrapper_sha256']==d.sha(Path(__file__))
    report=d.resources(work);assert report['available_bytes']['commit']>=POLICY['minimum_start_commit_bytes']
    # Only this process's external host monitor is replaced, not any file or Core object.
    d.base.Guard=Guard
    d.run(work)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare-resume','run'));p.add_argument('--policy-sha256');p.add_argument('--work',type=Path,default=d.WORK)
    a=p.parse_args()
    if a.command=='prepare-resume':prepare_resume(a.work.resolve())
    else:run(a.work.resolve(),a.policy_sha256)
