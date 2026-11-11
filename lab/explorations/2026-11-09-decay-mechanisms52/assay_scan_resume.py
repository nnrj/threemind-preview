"""Complete-boundary continuation with equivalent evidence-size accounting.

No source or dynamics mutation. The prior exact scalar/vector operations and
cumulative six-hour budget are retained. A completed teaching phase is restored
as the current state, never replayed from birth.
"""
import argparse
from contextlib import contextmanager
import json
import os
import time
from pathlib import Path
import assay_study as e
import assay_resume as old
from assay_prefix import validate
from evidence_size import logical_bytes

TAG='exact-acceleration-v2-scandir-v1'
RESUME=e.WORK/'resumptions'/TAG

def extras():
    return {name:e.sha(e.HERE/name) for name in ('assay_scan_resume.py','assay_prefix.py','evidence_size.py',
        'test_evidence_size.py','test_assay_prefix.py','scan-addendum.zh.md','scan-addendum.en.md')}

def prefix():return validate(e.WORK,e.load(e.WORK/'cases.json'),e.load,e.sha,e.base.digest)

def fast_boundary(work):
    if (work/'STOP').exists():raise InterruptedError('complete boundary pause')
    e.base.resource_check(work)
    if logical_bytes(work)['logical_bytes']>e.previous.rc.POLICY['originals_bytes']:
        raise InterruptedError('originals budget exceeded')

@contextmanager
def accounting():
    original=e.boundary;e.boundary=fast_boundary
    try:yield
    finally:e.boundary=original

def prepare(expected_stop):
    work=e.WORK
    assert not (RESUME/'prepared.json').exists(),'preparation already complete'
    with e.base.worker_lock(work):
        host=e.load(work/'host.json');assert old.dead(host)
        assert not (work/'in-flight.json').exists(),'dead in-flight must be preserved'
        assert e.sha(work/'STOP')==expected_stop
        assert e.load(work/'STOP')['reason']=='verified equivalent evidence-size accounting'
        e.frozen(work);assert old.extras()==e.load(old.RESUME/'runtime-manifest.json')
        checkpoint=prefix();resources=e.base.resource_check(work)
        assert resources['available_bytes']['commit']>=8*2**30
        assert e.load(work/'policy.json')['wall_seconds']==21600
        verification=e.load(e.ROOT/'.work/r46-scan-verification-v1.json')
        assert verification['passed'] and verification['source_sha256']==extras()
        RESUME.mkdir(parents=True,exist_ok=True)
        for name in ('STOP','host.json','status.json','current.json','resource-summary.json'):
            destination=RESUME/('previous-'+name)
            if destination.exists():assert destination.read_bytes()==(work/name).read_bytes()
            else:
                with destination.open('xb') as f:f.write((work/name).read_bytes())
        for name,h in extras().items():
            p=RESUME/'frozen'/name;p.parent.mkdir(exist_ok=True)
            if p.exists():assert e.sha(p)==h
            else:
                with p.open('xb') as f:f.write((e.HERE/name).read_bytes())
        e.save(RESUME/'runtime-manifest.json',extras())
        e.save(RESUME/'verification.json',verification)
        e.save(RESUME/'size-benchmark.json',e.load(e.ROOT/'.work/r46-evidence-size-benchmark-v1.json'))
        with e.connection() as client:
            platform=e.load(work/'platform.json')
            recorder=e.base.ResearchRecorder(work,platform['project_id'],client=client);recorder.resume_recording()
            text=(e.HERE/'scan-addendum.zh.md').read_text('utf-8')+'\n\n'+(e.HERE/'scan-addendum.en.md').read_text('utf-8')
            doc=str(e.ident('scandir-continuation-note-document'))
            recorder.text(dict(request_id=str(e.ident('scandir-continuation-note-request')),identity=doc,
                expected_revision=0,kind='note',title='Equivalent evidence-size accounting and complete continuation',markdown=text))
            recorder.synchronize(strict=True)
            body=client.request('GET',f"/api/v2/projects/{platform['project_id']}/notes/{doc}",params={'revision':1})
            assert body['body']==dict(format='markdown',text=text)
            assert recorder.status['pending']==0
            e.save(RESUME/'api-readback.json',dict(id=doc,revision=1,content_hash=body['content_hash'],text_equal=True,pending=0))
        assert e.sha(work/'STOP')==expected_stop and prefix()==checkpoint
        e.save(RESUME/'prepared.json',dict(tag=TAG,checkpoint=checkpoint,stop_sha256=expected_stop,
            original_host=host,prior_resources=e.load(work/'resource-summary.json'),resources=resources,
            runtime=extras(),six_hour_total_budget_preserved=True,rollback=False,completed_at=time.time()))
        (work/'STOP').unlink()
        e.save(RESUME/'stop-retired.json',dict(sha256=expected_stop,epoch=time.time(),reason='exact archived STOP retired under worker lock'))
        print(json.dumps(dict(prepared=True,checkpoint=checkpoint,pending=0)),flush=True)

def run():
    work=e.WORK
    with e.base.worker_lock(work):
        e.frozen(work);assert old.extras()==e.load(old.RESUME/'runtime-manifest.json')
        prepared=e.load(RESUME/'prepared.json');assert old.dead(prepared['original_host'])
        assert extras()==prepared['runtime']==e.load(RESUME/'runtime-manifest.json')
        assert not (RESUME/'started.json').exists(),'single-use continuation'
        assert not any((work/n).exists() for n in ('STOP','in-flight.json'))
        assert prefix()==prepared['checkpoint']
        resources=e.base.resource_check(work);assert resources['available_bytes']['commit']>=8*2**30
        host=dict(pid=os.getpid(),created_at=e.psutil.Process().create_time(),command=e.psutil.Process().cmdline(),implementation=TAG)
        e.save(RESUME/'started.json',host);e.base.atomic_json(work/'host.json',host)
        guard=e.Guard(work);guard.started-=prepared['prior_resources']['wall_seconds']
        guard.minimum=dict(prepared['prior_resources']['minimum_available_bytes'])
        guard.peak_private=prepared['prior_resources']['peak_private_bytes']
        resume=prepared['checkpoint']['resume']
        with guard,old.accelerated(),accounting():
            for i,case in enumerate(e.load(work/'cases.json')):
                if i<resume['index']:continue
                key='subjects/'+case['key'];birth=work/key/'birth.json.gz'
                if i==resume['index'] and resume['state_file']:
                    subject=e.Assay.restore(e.load(work/resume['state_file']))
                elif birth.exists():raise RuntimeError('unexpected later existing birth')
                else:
                    subject=e.Assay(case['seed'],case['curve'],case['relaxation'],'R46a-'+case['key'])
                    e.save(birth,subject.state())
                if i!=resume['index'] or resume['phase']!='probe':
                    old.unit(work,key+'/teaching',subject,lambda:subject.teach(case['course'],False,case['history']))
                old.unit(work,key+'/probe',subject,lambda:subject.first_probe(case['delay'],case['cue']))
                e.base.atomic_json(work/'status.json',dict(state='running',sequences_completed=i+1,last=case['key']))
                print(json.dumps(dict(completed=i+1,total=1920,last=case['key'],implementation=TAG)),flush=True)
            e.base.atomic_json(work/'status.json',dict(state='awaiting-analysis',sequences_completed=1920))
        e.save(RESUME/'completed.json',dict(state='awaiting-analysis',sequences_completed=1920,epoch=time.time()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare','run'));p.add_argument('--stop-sha256')
    args=p.parse_args()
    if args.command=='prepare':prepare(args.stop_sha256)
    else:run()
