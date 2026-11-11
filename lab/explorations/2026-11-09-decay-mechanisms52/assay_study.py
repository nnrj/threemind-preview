"""Registered R46a runner. Serial execution, original evidence and boundary guard."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'lab/explorations/2026-11-09-retention-relaxation'))
import relaxation_study as previous
base=previous.base
load,save,sha,psutil=previous.load,previous.save,previous.sha,previous.psutil
from retention_assay import Assay,COURSES
from threemind_kernels.local52 import KERNEL_ID

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')
RESOURCE='decay-mechanisms52-assay-20261109-v1'
NS=UUID('a7378847-7423-573c-a043-72e696a93986')
POLICY=dict(previous.POLICY)
Guard=previous.Guard
connection=previous.connection


def ident(key):return uuid5(NS,key)


def cases():
    return [dict(key=f'o{o}/{curve}-{int(relaxation)}/{course}/h{h}/d{delay}/q{int(cue)}',origin=o,
        seed=261109200+o,curve=curve,relaxation=relaxation,course=course,history=h,delay=delay,cue=cue)
        for o in range(8)
        for curve in ('exponential','inverse-logarithmic','power-law')
        for relaxation in (True,False)
        for course in COURSES for h in (0,1) for delay in (1,300) for cue in (True,False)]


def manifest():
    files=['retention_assay.py','assay_study.py','analyze_assay.py','audit_assay.py','test_retention_assay.py',
        'test_assay_analysis.py','assay_protocol.zh.md','assay_protocol.en.md','design-notes.zh.md',
        'after_assay.py','inventory_assay.py','figures_assay.py','publish_assay.py']
    result={str((HERE/n).relative_to(ROOT)).replace('\\','/'):sha(HERE/n) for n in files}
    # Existing helpers are operational dependencies, not restored research subjects.
    result.update(previous.manifest())
    return result


def frozen(work):
    assert manifest()==load(work/'runner-manifest.json')
    assert base.capture_implementation('reference')==load(work/'implementation.json')


def prepare(work):
    assert not (work/'registration.json').exists(),'already registered'
    assert load(previous.WORK/'publication/completion.json')['pending']==0
    assert load(previous.WORK/'publication/completion.json')['execution_status']=='completed'
    assert (ROOT/'.work/decay52-staged-v1/promotion.json').exists(),'genuine version not promoted'
    work.mkdir(parents=True,exist_ok=True)
    with base.worker_lock(work),connection() as c:
        resources=base.resource_check(work)
        assert resources['available_bytes']['commit']>=8*2**30 and resources['available_bytes']['data_disk']>=34*2**30
        verified=load(work/'instrument/verified.json')
        assert verified['passed'] and verified['manifest']==manifest()
        title='2026-11-09 ThreeMind · 三种衰减机制与回落开关的局部保持比较 R46a'
        found=[p for p in c.call('projects.list',{}) if p['name']==title]
        assert len(found)<=1
        project=found[0] if found else c.request('POST','/api/v2/projects',body=dict(name=title))
        save(work/'platform.json',dict(project_id=project['id'],resource_id=RESOURCE))
        recorder=base.ResearchRecorder(work,project['id'],client=c)
        recorder.register(dict(source_key='decay52:assay:20261109:v1',title=title,
            classification='development',execution_status='running',executor='ai',kernels=[KERNEL_ID],
            protocol=(HERE/'assay_protocol.zh.md').read_text('utf-8'),protocol_version=base.digest(manifest()),
            required_roles=['protocol','report','note'],metadata=dict(independent_origins=8,sequences=len(cases()),
                work=str(work),policy=POLICY,authorization='2026-11-09 author approved three decay laws by relaxation on/off comparison')),
            request_id=ident('register'))
        recorder.synchronize(strict=True)
        c.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,target_id='managed-research-experiments',
            relative_path='2026-11-09-decay-mechanisms52/assay-v1',registered_work_path=str(work),writer_mode='cooperative',
            expected_revision=0),headers={'X-ThreeMind-Request-ID':str(ident('resource'))})
        c.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=project['id'],resource_id=RESOURCE),
            headers={'X-ThreeMind-Request-ID':str(ident('grant'))})
        save(work/'runner-manifest.json',manifest())
        implementation=base.capture_implementation('reference')
        save(work/'implementation.json',implementation)
        save(work/'policy.json',POLICY);save(work/'cases.json',cases())
        for rel in manifest():recorder.save_original('frozen/'+rel,(ROOT/rel).read_bytes())
        for rel,h in implementation['source_files'].items():
            assert sha(ROOT/rel)==h
            recorder.save_original('frozen-implementation/'+rel,(ROOT/rel).read_bytes())
        for lang in ('zh','en'):
            recorder.text(dict(request_id=str(ident('protocol-'+lang)),identity=str(ident('protocol-doc-'+lang)),
                expected_revision=0,kind='protocol',title='R46a local decay comparison '+lang,
                markdown=(HERE/f'assay_protocol.{lang}.md').read_text('utf-8')))
        recorder.synchronize(strict=True);readback=[]
        for lang in ('zh','en'):
            doc=c.request('GET',f"/api/v2/projects/{project['id']}/research-documents/{ident('protocol-doc-'+lang)}")
            assert len(doc['spec']['blocks'])==1 and doc['spec']['blocks'][0]['markdown']==(HERE/f'assay_protocol.{lang}.md').read_text('utf-8')
            readback.append(dict(language=lang,text_equal=True,revision=doc['revision']))
        save(work/'registration.json',dict(project=project['id'],record=recorder.experiment,pending=recorder.status['pending'],protocol_readback=readback))
        base.atomic_json(work/'status.json',dict(state='registered',sequences_completed=0))
        print(json.dumps(load(work/'registration.json')),flush=True)


def boundary(work):
    previous.rc.boundary(work)


def unit(work,key,s,fn):
    boundary(work);before=s.state();started=time.perf_counter()
    save(work/'in-flight.json',dict(key=key,pid=os.getpid(),created_at=psutil.Process().create_time(),
        time_us=s.core.time_us,before_sha256=base.digest(before)))
    result=fn();after=s.state()
    state_file=f'{key}/whole.json.gz';result_file=f'{key}/result.json.gz'
    receipt=save(work/state_file,after);save(work/result_file,result)
    save(work/f'{key}/complete.json',dict(state_file=state_file,sha256=receipt['sha256'],
        result_file=result_file,result_sha256=sha(work/result_file),before_sha256=base.digest(before),
        after_sha256=base.digest(after),start_us=before['core']['time_us'],end_us=s.core.time_us,
        wall_seconds=time.perf_counter()-started,private_bytes=psutil.Process().memory_info().private))
    base.atomic_json(work/'current.json',dict(unit=key,state_file=state_file,sha256=receipt['sha256'],time_us=s.core.time_us))
    (work/'in-flight.json').unlink()


def run(work):
    with base.worker_lock(work):
        frozen(work);boundary(work)
        assert load(work/'status.json')==dict(state='registered',sequences_completed=0),'fresh start only; inspect existing complete state'
        assert not (work/'in-flight.json').exists()
        prior=load(previous.WORK/'host.json')
        assert not psutil.pid_exists(prior['pid']) or psutil.Process(prior['pid']).create_time()!=prior['created_at']
        resource=base.resource_check(work)
        assert resource['available_bytes']['commit']>=8*2**30 and resource['available_bytes']['data_disk']>=34*2**30
        save(work/'host.json',dict(pid=os.getpid(),created_at=psutil.Process().create_time(),command=psutil.Process().cmdline()))
        with Guard(work):
            for i,case in enumerate(load(work/'cases.json')):
                s=Assay(case['seed'],case['curve'],case['relaxation'],'R46a-'+case['key'])
                key='subjects/'+case['key'];save(work/key/'birth.json.gz',s.state())
                unit(work,key+'/teaching',s,lambda:s.teach(case['course'],False,case['history']))
                unit(work,key+'/probe',s,lambda:s.first_probe(case['delay'],case['cue']))
                base.atomic_json(work/'status.json',dict(state='running',sequences_completed=i+1,last=case['key']))
                print(json.dumps(dict(completed=i+1,total=1920,last=case['key'])),flush=True)
            base.atomic_json(work/'status.json',dict(state='awaiting-analysis',sequences_completed=1920))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare','run','status'))
    p.add_argument('--work',type=Path,default=WORK);args=p.parse_args();work=args.work.resolve()
    if args.command=='prepare':prepare(work)
    elif args.command=='run':run(work)
    else:print(json.dumps(dict(status=load(work/'status.json') if (work/'status.json').exists() else None,
        stop=(work/'STOP').exists(),in_flight=(work/'in-flight.json').exists(),resources=base.resource_check(work))))
