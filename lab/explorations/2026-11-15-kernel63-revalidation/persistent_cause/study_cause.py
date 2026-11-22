"""Preregistered original-scale replication of sustained-activity cause experiments."""
import argparse
from collections import Counter
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import design
import execute_cause as e
from allocation import disk_allocation
s=e.s;ROOT=e.materials.ROOT;read=s.base.read
NS=UUID('33e0fc0c-f359-5b69-8794-6d34011e56a6');CAP=2*2**30


def allocated(folder):
    return sum(disk_allocation(p)['allocated_bytes'] for p in Path(folder).rglob('*') if p.is_file())


def native():
    from _threemind_native import _threemind_native as module
    return Path(module.__file__)


def prior(work):
    sys.path.insert(0,str(HERE.parent/'memory_timescales'))
    import study_timescales as q
    path=work.parent/'memory-timescales-63-rerun-v1';q.check(path)
    result=read(path/'publication/completion.json')
    assert result['coverage']=='verified' and result['pending']==0 and not result['scientific_stop']
    return path


def check(work):
    prior(work);frozen=read(work/'frozen.json')
    for rel,digest in frozen['sources'].items():assert s.sha(ROOT/rel)==digest,rel
    for rel,digest in frozen['materials'].items():assert s.sha(work/rel)==digest,rel
    for name,digest in frozen['historical_design'].items():assert s.sha(design.HISTORY/name)==digest,name
    assert s.sha(native())==frozen['native_sha256'] and s.sha(work/'cases.json')==frozen['cases_sha256']
    assert s.sha(work/'measurement-validation.json')==frozen['measurement_validation_sha256']
    assert read(work/'registration.json')['pending']==0
    return frozen


def register(work):
    assert not work.exists();previous=prior(work)
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>31.125*2**30
    import verify_measurement_cause
    measurement=verify_measurement_cause.verify();assert measurement['passed']
    cases=design.cases();old=read(design.HISTORY/'publication/completion.json')
    assert old['coverage']=='verified' and old['pending']==0
    for c in cases:
        e.base.resolve_kernel('threemind.continuous-memory/'+c['version']).configuration(
            {'seed':e.materials.SEED,**c['initial_config'],**c['birth_patch'],**c['cause_patch'],**c['patch']})
    work.mkdir();materials={}
    s.base.original(work/'measurement-validation.json',measurement)
    for key in sorted({c['material_key'] for c in cases}):
        source=previous/'materials'/key/'frames.jsonl';target=work/'materials'/key/'frames.jsonl'
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        assert s.sha(source)==s.sha(target);materials[target.relative_to(work).as_posix()]=s.sha(target)
    s.base.original(work/'cases.json',cases)
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))
    paths+=[HERE.parent/'memory_timescales'/n for n in ('materials_timescales.py','measurement_timescales.py')]
    paths+=list((ROOT/'src/threemind_kernels').glob('*.py'))+[Path(s.__file__),Path(s.base.__file__),Path(e.support.__file__)]
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    historical={n:s.sha(design.HISTORY/n) for n in ('cases.json','supplement-cases.json','novelty-cases.json',
        'analysis.json','analysis-novelty.json','publication/completion.json')}
    costs={c['key']:allocated(design.HISTORY/'cases'/c['historical_case']) for c in cases}
    s.base.original(work/'frozen.json',{'sources':sources,'materials':materials,'historical_design':historical,
        'native_sha256':s.sha(native()),'cases_sha256':s.sha(work/'cases.json'),'old_allocated_bytes':costs,
        'measurement_validation_sha256':s.sha(work/'measurement-validation.json'),
        'prior_completion_sha256':s.sha(previous/'publication/completion.json'),'stages':476,'blocks':2,
        'originals_cap_bytes':CAP,'current_authorization':'all plan-v2 and additional studies rerun on 6.3'})
    for rel in sources:
        target=work/'frozen-source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,target)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r63t1:persistent-cause:20261116:v1','title':'R63t1：持续活动与前缀区分的原因复验',
            'classification':'formal','execution_status':'running','executor':'ai',
            'kernels':['threemind.continuous-memory/'+v for v in ('1','2','3.1','5.1','5.3','6.3')],
            'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'material_blocks':2,'stages':476,'all_historical_followups_preregistered':True}},
            request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R63t1 protocol '+lang,
                'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)


def execute(case,folder,work,root,**kwargs):
    parent=root/case['parent'] if case['parent'] else None
    initial=e.base.image(parent/'final.tmind') if parent else None
    observer=e.unpacked(parent/'observer.json.xz') if parent else None
    return e.execute(case,folder,work/'materials',initial,observer,**kwargs)


def apparatus_cases(cases):
    by={c['key']:c for c in cases};keys=set()
    for variant in ('v1','v2','v63'):
        for suffix in ('sustain/s0/unchanged','history/s0/101/d1/AB'):keys.add(variant+'/'+suffix)
    for variant in ('v2-immediate','v63-immediate'):keys.add(variant+'/history/s0/101/d1/AB')
    for key in list(keys):
        current=by[key]
        while current['parent']:
            keys.add(current['parent']);current=by[current['parent']]
    return [c for c in cases if c['key'] in keys]


def apparatus(work):
    import psutil
    frozen=check(work);cases=apparatus_cases(read(work/'cases.json'));checks=[];costs=[];began=time.monotonic()
    assert not any((work/n).exists() for n in ('apparatus','apparatus.json','cases','STOP','in-flight.json'))
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for case in cases:
            assert guard.thread.is_alive() and not (work/'STOP').exists()
            s.base.original(work/'in-flight.json',{'phase':'apparatus','key':case['key'],'pid':os.getpid(),
                'created':psutil.Process().create_time()})
            result,state,observer=execute(case,work/'apparatus/main'/case['key'],work,work/'apparatus/main',calibration=True)
            costs.append({'key':case['key'],'bytes':allocated(work/'apparatus/main'/case['key']),
                'old_bytes':frozen['old_allocated_bytes'][case['key']],'wall_seconds':result['wall_seconds']})
            if case['kind']=='probe':
                hashes={'observed':state.digest}
                for mode in ('plain','restored','paused'):
                    _,other,ob=execute(case,work/'apparatus'/mode/case['key'],work,work/'apparatus/main',mode=mode,calibration=True)
                    assert ob==observer;hashes[mode]=other.digest
                assert len(set(hashes.values()))==1;checks.append({'key':case['key'],'hashes':hashes,'observers_equal':True})
            (work/'in-flight.json').unlink();print('apparatus',case['key'],flush=True)
            del state,observer;gc.collect()
        ratio=max(c['bytes']/c['old_bytes'] for c in costs)
        factor=max(1.1,ratio)*1.25
        estimate=sum(frozen['old_allocated_bytes'].values())*factor+allocated(work)+128*2**20
        budget=ratio<2 and estimate<CAP and not (work/'STOP').exists()
        s.base.original(work/'apparatus.json',{'passed':True,'budget_passed':budget,'checks':checks,'costs':costs,
            'estimate_factor':factor,'estimated_full_bytes':estimate,'maximum_allocation_ratio':ratio,
            'calibration_seed':9291199,'formal_individuals_created':0,'wall_seconds':time.monotonic()-began})
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True,'budget_passed':budget,'stages':len(cases)}),flush=True)


def run(work):
    import psutil
    frozen=check(work);app=read(work/'apparatus.json');assert app['passed'] and app['budget_passed']
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    assert shutil.disk_usage(work).free>31.125*2**30
    cases=read(work/'cases.json');began=time.monotonic();completed=0;accounted=allocated(work)+128*2**20
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for case in cases:
            if (work/'STOP').exists():break
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            s.base.original(work/'in-flight.json',{'key':case['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            result,state,observer=execute(case,work/'cases'/case['key'],work,work/'cases')
            size=allocated(work/'cases'/case['key']);old=frozen['old_allocated_bytes'][case['key']]
            completed+=1;cost_path=work/'costs'/f'{completed:03d}.json'
            s.base.original(cost_path,{'key':case['key'],'bytes':size,'historical_bytes':old,
                'allocation_method':'FileStandardInfo','wall_seconds':result['wall_seconds']})
            accounted+=size+disk_allocation(cost_path)['allocated_bytes']
            s.base.atomic_json(work/'current.json',{'completed':completed,'total':476,'last':case['key']})
            (work/'in-flight.json').unlink()
            reason=('matched allocation at least twice historical' if size>=2*old else
                'unit exceeds frozen estimate by 50%' if size>1.5*app['estimate_factor']*old else
                'full originals budget' if accounted>CAP else 'two-hour host budget' if time.monotonic()-began>7200 else None)
            if completed%16==0:print(completed,'/476',case['key'],flush=True)
            if reason:s.base.original(work/'STOP',{'reason':reason,'complete_boundary':case['key']});break
            del state,observer;gc.collect()
        if completed==476:
            assert allocated(work)<=accounted<CAP
            s.base.original(work/'summary.json',{'status':'awaiting-analysis','stages':476,'blocks':2,
                'wall_seconds':time.monotonic()-began,'parts':dict(Counter(c['design_part'] for c in cases))})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('register','apparatus','run'))
    parser.add_argument('--work',type=Path,required=True);args=parser.parse_args()
    {'register':register,'apparatus':apparatus,'run':run}[args.action](args.work.resolve())
