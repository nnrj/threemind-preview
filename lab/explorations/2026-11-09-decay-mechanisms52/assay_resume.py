"""Explicit, single-use continuation after the complete R46a cost pause.

Original scientific protocol/source remain frozen. A scoped exact-arithmetic
implementation option is separately registered, witnessed and fingerprinted.
"""
from pathlib import Path
import argparse,json,os,shutil,time
import assay_study as e
from exact_acceleration_v2 import accelerated

TAG='exact-acceleration-v2'
RESUME=e.WORK/'resumptions'/TAG


def extras():
    return {name:e.sha(e.HERE/name) for name in ('assay_resume.py','exact_acceleration.py',
        'exact_acceleration_v2.py','test_exact_acceleration_v2.py','test_assay_resume.py',
        'operations-addendum.zh.md','operations-addendum.en.md')}


def dead(host):
    return not e.psutil.pid_exists(host['pid']) or e.psutil.Process(host['pid']).create_time()!=host['created_at']


def complete_prefix(work):
    cases=e.load(work/'cases.json');completed=0;boundaries=0
    for i,c in enumerate(cases):
        folder=work/'subjects'/c['key'];probe=folder/'probe/complete.json'
        if not probe.exists():
            assert not any((work/'subjects'/other['key']/'probe/complete.json').exists() for other in cases[i+1:])
            break
        before=e.load(folder/'birth.json.gz')
        for phase in ('teaching','probe'):
            row=e.load(folder/phase/'complete.json')
            assert e.sha(work/row['state_file'])==row['sha256']
            assert e.sha(work/row['result_file'])==row['result_sha256']
            after=e.load(work/row['state_file'])
            assert e.base.digest(before)==row['before_sha256'] and e.base.digest(after)==row['after_sha256']
            assert int(before['core']['time_us'])==int(row['start_us'])
            assert int(after['core']['time_us'])==int(row['end_us'])
            before=after;boundaries+=1
        completed+=1
    current=e.load(work/'current.json')
    assert current['unit']=='subjects/'+cases[completed-1]['key']+'/probe'
    assert e.sha(work/current['state_file'])==current['sha256']
    assert e.load(work/'status.json')['sequences_completed']==completed
    # A next birth may already have been saved before the old boundary stop.
    next_folder=work/'subjects'/cases[completed]['key']
    assert not (next_folder/'teaching/complete.json').exists()
    if (next_folder/'birth.json.gz').exists():
        birth=e.load(next_folder/'birth.json.gz');assert int(birth['core']['time_us'])==0
        assert birth['identity']=='R46a-'+cases[completed]['key']
    return dict(sequences=completed,boundaries=boundaries,current=current,
        next_birth_preserved=(next_folder/'birth.json.gz').exists())


def prepare(expected_stop):
    work=e.WORK
    with e.base.worker_lock(work):
        e.frozen(work);assert dead(e.load(work/'host.json'))
        assert not (work/'in-flight.json').exists()
        assert e.sha(work/'STOP')==expected_stop
        assert not RESUME.exists(),'inspect a previous preparation before continuing'
        resources=e.base.resource_check(work)
        assert resources['available_bytes']['commit']>=8*2**30
        checkpoint=complete_prefix(work)
        assert checkpoint['sequences']==175 and checkpoint['boundaries']==350
        proof=e.load(e.ROOT/'.work/r46-exact-acceleration-v3/verified.json')
        assert proof['passed'] and len(proof['records'])==5
        for name,h in proof['source'].items():assert e.sha(e.HERE/name)==h
        RESUME.mkdir(parents=True)
        for name in ('STOP','status.json','current.json','host.json','resource-summary.json','policy.json'):
            shutil.copy2(work/name,RESUME/name)
        for folder in ('r46-exact-acceleration-v2','r46-exact-acceleration-v3'):
            shutil.copytree(e.ROOT/'.work'/folder,RESUME/folder)
        runtime=extras();e.save(RESUME/'runtime-manifest.json',runtime)
        for name in runtime:
            (RESUME/'frozen').mkdir(exist_ok=True)
            shutil.copy2(e.HERE/name,RESUME/'frozen'/name)
        note=(e.HERE/'operations-addendum.zh.md').read_text('utf-8')+'\n\n'+(e.HERE/'operations-addendum.en.md').read_text('utf-8')
        with e.connection() as c:
            platform=e.load(work/'platform.json')
            recorder=e.base.ResearchRecorder(work,platform['project_id'],client=c);recorder.resume_recording()
            recorder.text(dict(request_id=str(e.ident(TAG+'-note')),identity=str(e.ident(TAG+'-document')),
                expected_revision=0,kind='note',title='R46a exact implementation acceleration and complete-state continuation',markdown=note))
            recorder.synchronize(strict=True)
            doc=c.request('GET',f"/api/v2/projects/{platform['project_id']}/research-documents/{e.ident(TAG+'-document')}")
            assert len(doc['spec']['blocks'])==1 and doc['spec']['blocks'][0]['markdown']==note
            e.save(RESUME/'api-readback.json',dict(pending=recorder.status['pending'],text_equal=True,revision=doc['revision']))
        prepared=dict(tag=TAG,checkpoint=checkpoint,stop_sha256=expected_stop,runtime=runtime,
            prior_resources=e.load(RESUME/'resource-summary.json'),original_host=e.load(RESUME/'host.json'),
            rollback=False,completed_at=time.time(),six_hour_total_budget_preserved=True)
        e.save(RESUME/'prepared.json',prepared)
        assert e.sha(work/'STOP')==expected_stop and dead(e.load(work/'host.json'))
        (work/'STOP').unlink()
        e.save(RESUME/'stop-retired.json',dict(sha256=expected_stop,archive='STOP',epoch=time.time()))
        print(json.dumps(dict(prepared=True,checkpoint=checkpoint,pending=0)),flush=True)


def unit(work,key,subject,fn):
    e.boundary(work);before=subject.state();started=time.perf_counter()
    e.save(work/'in-flight.json',dict(key=key,pid=os.getpid(),created_at=e.psutil.Process().create_time(),
        time_us=subject.core.time_us,before_sha256=e.base.digest(before),implementation=TAG))
    result=fn();after=subject.state()
    state_file=f'{key}/whole.json.gz';result_file=f'{key}/result.json.gz'
    receipt=e.save(work/state_file,after);e.save(work/result_file,result)
    e.save(work/f'{key}/complete.json',dict(state_file=state_file,sha256=receipt['sha256'],
        result_file=result_file,result_sha256=e.sha(work/result_file),before_sha256=e.base.digest(before),
        after_sha256=e.base.digest(after),start_us=before['core']['time_us'],end_us=subject.core.time_us,
        wall_seconds=time.perf_counter()-started,private_bytes=e.psutil.Process().memory_info().private,
        implementation=TAG))
    e.base.atomic_json(work/'current.json',dict(unit=key,state_file=state_file,sha256=receipt['sha256'],time_us=subject.core.time_us))
    (work/'in-flight.json').unlink()


def run():
    work=e.WORK
    with e.base.worker_lock(work):
        e.frozen(work);assert extras()==e.load(RESUME/'runtime-manifest.json')
        prepared=e.load(RESUME/'prepared.json');assert dead(prepared['original_host'])
        assert not (RESUME/'started.json').exists(),'single-use continuation; inspect any new stop'
        assert not any((work/name).exists() for name in ('STOP','in-flight.json'))
        assert complete_prefix(work)==prepared['checkpoint']
        resources=e.base.resource_check(work)
        assert resources['available_bytes']['commit']>=8*2**30
        host=dict(pid=os.getpid(),created_at=e.psutil.Process().create_time(),command=e.psutil.Process().cmdline(),implementation=TAG)
        e.save(RESUME/'started.json',host);e.base.atomic_json(work/'host.json',host)
        guard=e.Guard(work)
        guard.started-=prepared['prior_resources']['wall_seconds']
        guard.minimum=dict(prepared['prior_resources']['minimum_available_bytes'])
        guard.peak_private=prepared['prior_resources']['peak_private_bytes']
        with guard,accelerated():
            for i,case in enumerate(e.load(work/'cases.json')):
                if i<prepared['checkpoint']['sequences']:continue
                key='subjects/'+case['key'];birth=work/key/'birth.json.gz'
                if birth.exists():subject=e.Assay.restore(e.load(birth))
                else:
                    subject=e.Assay(case['seed'],case['curve'],case['relaxation'],'R46a-'+case['key'])
                    e.save(birth,subject.state())
                unit(work,key+'/teaching',subject,lambda:subject.teach(case['course'],False,case['history']))
                unit(work,key+'/probe',subject,lambda:subject.first_probe(case['delay'],case['cue']))
                e.base.atomic_json(work/'status.json',dict(state='running',sequences_completed=i+1,last=case['key']))
                print(json.dumps(dict(completed=i+1,total=1920,last=case['key'],implementation=TAG)),flush=True)
            e.base.atomic_json(work/'status.json',dict(state='awaiting-analysis',sequences_completed=1920))
        e.save(RESUME/'completed.json',dict(state='awaiting-analysis',sequences_completed=1920,epoch=time.time()))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('prepare','run'))
    parser.add_argument('--stop-sha256');args=parser.parse_args()
    if args.command=='prepare':prepare(args.stop_sha256)
    else:run()
