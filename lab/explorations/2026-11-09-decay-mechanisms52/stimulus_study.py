"""Registered R46b execution; preserve R46a and every complete new subject."""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid5
import assay_study as a
import assay_resume as operational
from assay_scan_resume import accounting
from stimulus_assay import StimulusAssay,cases

HERE,ROOT=a.HERE,a.ROOT
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/stimulus-v1')
RESOURCE='decay52-stimulus-retention-20261110-v1'
NS=uuid5(a.NS,'dedicated-stimulus-retention-v1')
POLICY=dict(a.POLICY)

def ident(key):return uuid5(NS,key)


def manifest():
    own=('stimulus_assay.py','stimulus_study.py','analyze_stimulus.py','audit_stimulus.py',
        'check_stimulus_assay.py','check_stimulus_assay_v2.py','check_stimulus_assay_v3.py',
        'test_stimulus_design.py','test_stimulus_analysis.py','stimulus_protocol.zh.md','stimulus_protocol.en.md',
        'exact_acceleration_v2.py','assay_resume.py','assay_scan_resume.py','assay_prefix.py','evidence_size.py')
    return {**a.manifest(),**{(HERE/n).relative_to(ROOT).as_posix():a.sha(HERE/n) for n in own}}


def frozen(work):
    assert manifest()==a.load(work/'runner-manifest.json')
    assert a.base.capture_implementation('reference')==a.load(work/'implementation.json')


def prepare(work,instrument):
    assert not (work/'registration.json').exists(),'already registered; inspect existing receipt'
    parent=a.load(a.WORK/'publication/completion.json')
    assert parent['execution_status']=='completed' and parent['pending']==0 and parent['coverage']=='verified'
    assert operational.dead(a.load(a.WORK/'host.json'))
    proof=a.load(instrument/'verified.json')
    assert proof['passed'] and proof['scientific_n']==0 and proof['short_sequences']==240
    assert proof['paired_conditions']==48 and len(proof['long_probes'])==12
    for name,h in proof['source_sha256'].items():assert a.sha(HERE/name)==h,name
    assert proof['implementation']==a.base.capture_implementation('reference')
    # Both gain families and all settings have a measured long probe before freezing.
    assert max(x['wall_seconds'] for x in proof['long_probes'])*480+1800<POLICY['wall_seconds'],'revise cost plan before registration'
    work.mkdir(parents=True,exist_ok=True)
    with a.base.worker_lock(work),a.connection() as client:
        resource=a.base.resource_check(work)
        assert resource['available_bytes']['commit']>=8*2**30 and resource['available_bytes']['data_disk']>=34*2**30
        title='2026-11-10 ThreeMind · 强刺激与连接新颖性对保持的作用 R46b'
        found=[p for p in client.call('projects.list',{}) if p['name']==title]
        assert len(found)<=1
        project=found[0] if found else client.request('POST','/api/v2/projects',body=dict(name=title))
        a.save(work/'platform.json',dict(project_id=project['id'],resource_id=RESOURCE))
        recorder=a.base.ResearchRecorder(work,project['id'],client=client)
        recorder.register(dict(source_key='decay52:stimulus-retention:20261110:v1',title=title,
            classification='development',execution_status='running',executor='ai',kernels=[a.KERNEL_ID],
            protocol=(HERE/'stimulus_protocol.zh.md').read_text('utf-8'),protocol_version=a.base.digest(manifest()),
            required_roles=['protocol','report','note'],metadata=dict(matched_input_conditions=8,
                independent_birth_seeds=8,sequences=960,work=str(work),policy=POLICY,
                authorization='Author-approved decay comparison including strong and novel stimuli; R46a input-field correction follow-up.',
                independence='Eight explicitly varied input conditions; nested arms and temporal cohorts are not extra independent N.')),
            request_id=ident('register'))
        recorder.synchronize(strict=True)
        client.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,target_id='managed-research-experiments',
            relative_path='2026-11-09-decay-mechanisms52/stimulus-v1',registered_work_path=str(work),writer_mode='cooperative',
            expected_revision=0),headers={'X-ThreeMind-Request-ID':str(ident('resource'))})
        client.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=project['id'],resource_id=RESOURCE),
            headers={'X-ThreeMind-Request-ID':str(ident('grant'))})
        a.save(work/'runner-manifest.json',manifest());a.save(work/'cases.json',cases());a.save(work/'policy.json',POLICY)
        implementation=a.base.capture_implementation('reference');a.save(work/'implementation.json',implementation)
        for rel in manifest():recorder.save_original('frozen/'+rel,(ROOT/rel).read_bytes())
        for rel,h in implementation['source_files'].items():
            assert a.sha(ROOT/rel)==h
            recorder.save_original('frozen-implementation/'+rel,(ROOT/rel).read_bytes())
        for p in instrument.rglob('*'):
            if p.is_file():recorder.save_original('instrument/'+p.relative_to(instrument).as_posix(),p.read_bytes())
        for lang in ('zh','en'):
            recorder.text(dict(request_id=str(ident('protocol-'+lang)),identity=str(ident('protocol-doc-'+lang)),
                expected_revision=0,kind='protocol',title='R46b strong-stimulus and connection novelty '+lang,
                markdown=(HERE/f'stimulus_protocol.{lang}.md').read_text('utf-8')))
        recorder.synchronize(strict=True);readback=[]
        for lang in ('zh','en'):
            body=client.request('GET',f"/api/v2/projects/{project['id']}/research-documents/{ident('protocol-doc-'+lang)}")
            assert len(body['spec']['blocks'])==1 and body['spec']['blocks'][0]['markdown']==(HERE/f'stimulus_protocol.{lang}.md').read_text('utf-8')
            readback.append(dict(language=lang,text_equal=True,revision=body['revision']))
        a.save(work/'registration.json',dict(project=project['id'],record=recorder.experiment,pending=recorder.status['pending'],protocol_readback=readback))
        a.base.atomic_json(work/'status.json',dict(state='registered',sequences_completed=0))
        print(json.dumps(a.load(work/'registration.json')),flush=True)


def run(work):
    with a.base.worker_lock(work):
        frozen(work)
        assert operational.dead(a.load(a.WORK/'host.json'))
        assert a.load(work/'status.json')==dict(state='registered',sequences_completed=0),'fresh start only; inspect complete current state'
        assert not any((work/n).exists() for n in ('STOP','in-flight.json','host.json'))
        resource=a.base.resource_check(work)
        assert resource['available_bytes']['commit']>=8*2**30 and resource['available_bytes']['data_disk']>=34*2**30
        a.save(work/'host.json',dict(pid=os.getpid(),created_at=a.psutil.Process().create_time(),command=a.psutil.Process().cmdline()))
        with a.Guard(work),operational.accelerated(),accounting():
            for i,case in enumerate(a.load(work/'cases.json')):
                subject=StimulusAssay(case,'R46b-'+case['key']);key='subjects/'+case['key']
                a.save(work/key/'birth.json.gz',subject.state())
                operational.unit(work,key+'/teaching',subject,subject.teach_mechanism)
                operational.unit(work,key+'/probe',subject,lambda:subject.first_probe(case['delay'],case['cue']))
                a.base.atomic_json(work/'status.json',dict(state='running',sequences_completed=i+1,last=case['key']))
                print(json.dumps(dict(completed=i+1,total=960,last=case['key'])),flush=True)
            a.base.atomic_json(work/'status.json',dict(state='awaiting-analysis',sequences_completed=960))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare','run'));p.add_argument('--work',type=Path,default=WORK)
    p.add_argument('--instrument',type=Path);args=p.parse_args()
    if args.command=='prepare':
        assert args.instrument is not None
        prepare(args.work.resolve(),args.instrument.resolve())
    else:run(args.work.resolve())
