"""E22A replication: registered persistent-state copies and independent waits."""
import argparse
from dataclasses import replace
import gc
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import materials_recovery as spec
import measurement_recovery as measure
import intervention_active as intervention
sys.path.insert(0,str(HERE.parent/'body_formation'))
import compact_trajectory as compact
x=compact.x.x
s=x.base.s
ROOT=x.ROOT
KERNEL=x.materials.KERNEL
NS = UUID('1c006c11-d2c1-59cc-a353-2fefb22d0ec3')
read=compact.read
allocated=compact.x.allocated


def compatible_sources(folder):
    checks=[]
    for seed,mode in itertools.product(spec.SEEDS,('full','no_imu')):
        refs=[x.base.image(folder/f'{seed}/{mode}/learn{learn}/state.tmind') for learn in ('01','11')]
        for recipient,donor in (refs,refs[::-1]):
            for bits in itertools.product((0,1),repeat=3):
                groups=[g for g,on in zip(spec.GROUPS,bits) if on]
                changed,receipt=intervention.exchange(recipient,donor,groups)
                same,_=intervention.exchange(recipient,recipient,groups)
                assert same.digest==recipient.digest
                checks.append({'seed':seed,'mode':mode,'recipient':recipient.digest,'donor':donor.digest,
                               'groups':groups,'after':changed.digest,'changed_fields':len(receipt['changes']),
                               'retained_events':receipt['retained_queue_events'],'same_source_exact':True})
    assert len(checks)==128
    return {'passed':True,'created_engines':0,'cross_source_checks':128,'same_source_checks':128,'checks':checks}


def check(work):
    previous=work.parent/'body-formation-63-rerun-v1'
    compact.check(previous)
    done=read(previous/'publication/completion.json')
    assert done['coverage']=='verified' and done['pending']==0 and not done['scientific_stop']
    frozen=read(work/'frozen.json')
    for rel,sha in frozen['sources'].items():assert s.sha(ROOT/rel)==sha,rel
    for rel,sha in frozen['materials'].items():assert s.sha(work/rel)==sha,rel
    assert s.sha(work/'cases.json')==frozen['cases_sha256']
    assert read(work/'registration.json')['pending']==0
    return frozen


def register(work):
    assert not work.exists()
    previous=work.parent/'body-formation-63-rerun-v1'
    compact.check(previous)
    done=read(previous/'publication/completion.json')
    assert done['coverage']=='verified' and done['pending']==0 and not done['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free>28.125*2**30
    history=spec.check();work.mkdir()
    s.base.original(work/'historical-check.json',history)
    s.base.original(work/'measurement-check.json',measure.check())
    s.base.original(work/'cases.json',spec.parents())
    materials={};lineage=[]
    def copy(source,target):
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        assert s.sha(source)==s.sha(target)
        materials[target.relative_to(work).as_posix()]=s.sha(target)
    for parent in spec.parents():
        prior=previous/'cases'/parent['key']/'test11/sign1/physical1'
        for source_name,target_name in [('intervened.tmind','state.tmind'),('initial-observer.json','observer.json')]:
            copy(prior/source_name,work/'references'/parent['key']/target_name)
        lineage.append({'parent':parent,'source_record':done['record'],'source_archive':done['archive_sha256'],
                        'state':str(prior/'intervened.tmind'),'state_sha256':x.base.image(prior/'intervened.tmind').digest,
                        'observer':str(prior/'initial-observer.json'),'observer_sha256':s.sha(prior/'initial-observer.json')})
        for stage in spec.stages(parent):
            for name in ('inputs-frames.jsonl.gz','result.json'):
                copy(spec.OLD/stage['key']/name,work/'materials'/stage['key']/name)
        # Preserve the exact R63o process used by the sham comparison.
        for sign,physical in itertools.product((1,-1),(0,1)):
            old=previous/'cases'/parent['key']/f'test11/sign{sign}/physical{physical}'
            for name in ('input.json','result.json','trajectory.json.xz'):
                copy(old/name,work/'r63o-reference'/parent['key']/f'sign{sign}/physical{physical}'/name)
    # Isolated calibration teaching uses original E21C input, with a new anonymous encoding.
    for mode,learn in itertools.product(('full','no_imu'),('01','11')):
        for name in ('inputs-frames.jsonl.gz','result.json'):
            source=previous/'materials'/f'930101/{mode}/learn{learn}/train'/name
            copy(source,work/'calibration-materials'/f'930101/{mode}/learn{learn}/train'/name)
    s.base.original(work/'lineage.json',lineage)
    s.base.original(work/'compatibility.json',compatible_sources(work/'references'))
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))
    dependencies=[Path(compact.__file__),Path(x.__file__),Path(compact.x.__file__),
                  Path(x.materials.__file__),Path(compact.x.measure.__file__),intervention.SOURCE]
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths+dependencies}
    old_sizes={p['key']:sum(allocated(spec.OLD/family/p['key']) for family in ('cut','recovery')) for p in spec.parents()}
    s.base.original(work/'frozen.json',{'kernel':KERNEL,'sources':sources,'materials':materials,
        'cases_sha256':s.sha(work/'cases.json'),'lineage_sha256':s.sha(work/'lineage.json'),
        'historical_actual_bytes':old_sizes,'source_completion_sha256':s.sha(previous/'publication/completion.json')})
    for p in paths+dependencies:
        dest=work/'frozen-source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    s.base.load_env()
    import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,x.base.PROJECT,client=client)
        rec.register({'source_key':'r63p:body-recovery:20261115:v1','title':'R63p：身体响应的持久状态交换与等待',
            'classification':'formal','execution_status':'running','executor':'ai','kernels':[KERNEL],
            'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'material_blocks':4,'references':16,'diagnostic_copies':704,'holding_copies':48}},
            request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),
                'request_id':str(uuid5(NS,'protocol-'+lang)),'expected_revision':0,'kind':'protocol',
                'title':'R63p protocol '+lang,'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result={'project':x.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)


def runtime_spec(parent,stage):
    p={**parent,'teaching_depletion':parent['learn']=='11','teaching_competition':True}
    prefix=stage['family']+'/'+parent['key']+'/'
    assert stage['key'].startswith(prefix)
    st={**stage,'name':stage['key'][len(prefix):]}
    if st['kind']=='probe':st.update(test_depletion=True,test_competition=True)
    return p,st


def execute(work,parent,stage,folder,state,observer,*,calibration_seed=None,mode='observed'):
    p,st=runtime_spec(parent,stage)
    return x.execute(p,st,folder,state,observer,work/'materials'/stage['family'],
                     calibration_seed=calibration_seed,mode=mode,no_reconfigure=True)


def exchanged(folder,recipient,donor,groups):
    image,receipt=intervention.exchange(recipient,donor,groups)
    folder.mkdir(parents=True,exist_ok=False)
    x.storage.save(folder/'changed.tmind',image)
    s.base.original(folder/'exchange.json',receipt)
    return image


def unit(work,parent,recipient,donor,observer,*,apparatus=False):
    prefix=work/('apparatus' if apparatus else 'cases')
    states={};hold_states={};checks=[]
    calibration_seed=930194 if apparatus else None
    for stage in spec.stages(parent):
        dest=prefix/stage['key']
        if stage['family']=='cut':
            label=''.join(stage['groups']) or 'none'
            if label not in states:
                states[label]=exchanged(prefix/'cut'/parent['key']/label,recipient,donor,stage['groups'])
                if apparatus:
                    same,_=intervention.exchange(recipient,recipient,stage['groups'])
                    assert same.digest==recipient.digest
                    restored=x.base.resolve_kernel(KERNEL).create(None,states[label],backend='native')
                    assert restored.capture_state().digest==states[label].digest
                    checks.append({'groups':stage['groups'],'same_source_exact':True,'native_restore_exact':True,
                                   'retained_events':len(states[label].to_dict()['queue'])})
            _,final,_=execute(work,parent,stage,dest,states[label],observer,calibration_seed=calibration_seed)
            if apparatus and label=='W' and stage['sign']==1 and stage['physical']:
                hashes={'observed':final.digest}
                for mode in ('plain','sparse','restored','paused'):
                    _,f,_=execute(work,parent,stage,prefix/'instrument-modes'/parent['key']/mode,
                                 states[label],observer,calibration_seed=calibration_seed,mode=mode)
                    hashes[mode]=f.digest
                assert len(set(hashes.values()))==1
                checks.append({'mode_hashes':hashes})
        elif stage['kind']=='hold':
            _,held,reader=execute(work,parent,stage,dest,recipient,observer,calibration_seed=calibration_seed)
            hold_states[stage['delay_s']]=(held,reader)
        else:
            state,reader=hold_states[stage['delay_s']]
            execute(work,parent,stage,dest,state,reader,calibration_seed=calibration_seed)
    return checks


def apparatus(work):
    import psutil
    frozen=check(work)
    assert not any((work/n).exists() for n in ('apparatus.json','cases','STOP','in-flight.json'))
    s.base.original=compact.write
    start=time.monotonic();checks=[];costs=[]
    with s.base.worker_lock(work),s.base.Guard(work):
        s.base.original(work/'in-flight.json',{'phase':'apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
        refs={}
        for mode,learn in itertools.product(('full','no_imu'),('01','11')):
            p=next(p for p in spec.parents() if p['seed']==930101 and p['mode']==mode and p['learn']==learn)
            rp={**p,'teaching_depletion':learn=='11','teaching_competition':True}
            folder=work/'apparatus/teaching'/p['key']
            _,taught,observer=x.execute(rp,x.materials.stages(rp)[0],folder,root=work/'calibration-materials',calibration_seed=930194)
            engine=x.base.resolve_kernel(KERNEL).create(None,taught,backend='native')
            before=x.base.observe(engine)
            engine.reconfigure(replace(engine.config,depletion_enabled=True,context_enabled=True))
            after=engine.capture_state()
            assert engine.time_us==20200000
            x.storage.save(folder/'reference.tmind',after)
            s.base.original(folder/'settlement.json',{'before':taught.digest,'after':after.digest,
                'changes':x.differences(taught.to_dict(),after.to_dict()),'projection_before':before,
                'projection_after':x.base.observe(engine),'advanced_us':0})
            refs[(mode,learn)]=(after,observer)
        for p in [p for p in spec.parents() if p['seed']==930101]:
            recipient,observer=refs[(p['mode'],p['learn'])]
            donor=refs[(p['mode'],'11' if p['learn']=='01' else '01')][0]
            checks.append({'parent':p,'checks':unit(work,p,recipient,donor,observer,apparatus=True)})
            size=sum(allocated(work/'apparatus'/family/p['key']) for family in ('cut','recovery'))
            costs.append({'parent':p['key'],'allocated_bytes':size,'historical_actual_bytes':frozen['historical_actual_bytes'][p['key']]})
        # Retain budget failures as apparatus results; never start formal work after one.
        budget=all(c['allocated_bytes']<2*c['historical_actual_bytes'] for c in costs)
        s.base.original(work/'apparatus.json',{'passed':True,'budget_passed':budget,'calibration_seed':930194,
             'checks':checks,'costs':costs,'wall_seconds':time.monotonic()-start,'formal_individuals_created':0})
        (work/'in-flight.json').unlink()
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True,'budget_passed':budget,'costs':costs}),flush=True)


def run(work):
    import psutil
    frozen=check(work);app=read(work/'apparatus.json')
    assert app['passed'] and app['budget_passed']
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    s.base.original=compact.write
    start=time.monotonic();completed=0
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for parent in spec.parents():
            if (work/'STOP').exists():break
            assert guard.thread.is_alive();s.base.resource_check(work)
            s.base.original(work/'in-flight.json',{'unit':parent['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            begin=time.monotonic();source=work/'references'/parent['key']
            recipient=x.base.image(source/'state.tmind');observer=read(source/'observer.json')
            donor=x.base.image(work/'references'/f"{parent['seed']}/{parent['mode']}/learn{'11' if parent['learn']=='01' else '01'}/state.tmind")
            unit(work,parent,recipient,donor,observer)
            size=sum(allocated(work/'cases'/family/parent['key']) for family in ('cut','recovery'))
            old=frozen['historical_actual_bytes'][parent['key']]
            completed+=1
            s.base.original(work/'costs'/f'{completed:03d}.json',{'unit':parent['key'],'allocated_bytes':size,
                'historical_allocated_bytes':old,'expected_allocated_bytes':1.5*old,
                'allocation_method':'FileStandardInfo','wall_seconds':time.monotonic()-begin})
            s.base.atomic_json(work/'current.json',{'completed':completed,'total':16,'last':parent['key']})
            (work/'in-flight.json').unlink()
            reason=('actual unit allocation at least twice historical' if size>=2*old else
                    'actual unit allocation exceeds estimate by 50%' if size>2.25*old else
                    'two-hour budget' if time.monotonic()-start>7200 else None)
            if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>2**30:reason='originals budget'
            print(completed,parent['key'],flush=True)
            if reason:s.base.original(work/'STOP',{'reason':reason,'complete_boundary':parent['key']});break
            del recipient,donor,observer;gc.collect()
        if completed==16:s.base.original(work/'summary.json',{'status':'awaiting-analysis','references':16,
            'diagnostics':704,'holding_copies':48,'stages':752,'material_blocks':4,'wall_seconds':time.monotonic()-start})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run'))
    p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    {'register':register,'apparatus':apparatus,'run':run}[a.action](a.work.resolve())
