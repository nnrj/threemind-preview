"""Registered E21C replication; uses existing recorder, lock and resource guard."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid5

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import execute_formation as x
import measurement_formation as measure
from allocation import disk_allocation
ROOT, s, spec = x.ROOT, x.base.s, x.materials
PROJECT = x.base.PROJECT


def read(p): return json.loads(Path(p).read_bytes())
def allocated(folder): return sum(disk_allocation(p)['allocated_bytes'] for p in folder.rglob('*') if p.is_file())


def check(work):
    x.storage.check(work.parent/'order-recall-63-rerun-v1')
    x.base.frozen_check(work.parent/'order-recall-63-rerun-v1')
    frozen = read(work/'frozen.json')
    for path, sha in frozen['sources'].items(): assert s.sha(ROOT/path) == sha
    assert s.sha(work/'cases.json') == frozen['cases_sha256']
    assert read(work/'registration.json')['pending'] == 0
    for path, sha in frozen['materials'].items(): assert s.sha(work/path) == sha
    return frozen


def register(work):
    assert not work.exists()
    previous = read(work.parent/'order-reference-63-rerun-v1/publication/completion.json')
    assert previous['coverage'] == 'verified' and previous['pending'] == 0 and not previous['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > 28.125*2**30
    history = spec.check(); work.mkdir()
    s.base.original(work/'historical-check.json', history)
    s.base.original(work/'measurement-check.json', measure.check())
    s.base.original(work/'cases.json', spec.parents())
    materials = {}
    for parent in spec.parents():
        for stage in spec.stages(parent):
            for name in ('inputs-frames.jsonl.gz', 'result.json'):
                source = spec.OLD/parent['key']/stage['name']/name
                target = work/'materials'/source.relative_to(spec.OLD)
                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source,target)
                assert s.sha(source) == s.sha(target)
                materials[target.relative_to(work).as_posix()] = s.sha(target)
    prior=work.parent/'inertial-reversal-63-rerun-v1'
    done=read(prior/'publication/completion.json')
    assert done['coverage']=='verified' and done['pending']==0
    for seed in spec.SEEDS:
        for mode in ('full','no_imu'):
            subject=f'v63-{seed}-ordinary-{mode}'
            for stage in ('teaching','wait1','intact-0','intact-1','intact--1'):
                names=('result.json','final.tmind') if stage in ('teaching','wait1') else ('result.json','trajectory.json.gz')
                for name in names:
                    source=prior/'subjects'/subject/stage/name
                    target=work/'r63i-reference'/subject/stage/name
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
                    assert s.sha(source)==s.sha(target)
                    materials[target.relative_to(work).as_posix()]=s.sha(target)
    paths = list(HERE.glob('*.py'))+list(HERE.glob('*.md'))
    s.base.original(work/'frozen.json', {'kernel':spec.KERNEL,
        'sources':{p.relative_to(ROOT).as_posix():s.sha(p) for p in paths},
        'cases_sha256':s.sha(work/'cases.json'), 'materials':materials,
        'historical_actual_bytes':{p['key']:allocated(spec.OLD/p['key']) for p in spec.parents()}})
    for p in paths:
        dest=work/'frozen-source'/p.name; dest.parent.mkdir(exist_ok=True); shutil.copyfile(p,dest)
    s.base.load_env()
    import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        recorder=s.base.ResearchRecorder(work,PROJECT,client=client)
        recorder.register({'source_key':'r63o:body-formation:20261115:v1','title':'R63o：身体经历的教学形成与测试表达',
            'classification':'formal','execution_status':'running','executor':'ai','kernels':[spec.KERNEL],
            'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'material_blocks':4,'teaching_references':32,'diagnostic_copies':512}},request_id=uuid5(x.NS,'register'))
        for lang in ('zh','en'):
            recorder.text({'identity':str(uuid5(x.NS,'protocol-document-'+lang)),
                'request_id':str(uuid5(x.NS,'protocol-'+lang)),'expected_revision':0,'kind':'protocol',
                'title':'R63o protocol '+lang,'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        recorder.synchronize(strict=True)
        result={'project':PROJECT,'record':recorder.experiment,'pending':recorder.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)


def trajectory_error(left, right):
    import gzip
    def curve(folder):
        points=json.loads(gzip.decompress((folder/'trajectory.json.gz').read_bytes()))['points']
        return {p['time_us']:{n['channel']:{f:n[f] for f in measure.FIELDS} for n in p['nodes']} for p in points}
    a,b=curve(left),curve(right); assert a.keys()==b.keys()
    error=0.
    for t in a:
        assert a[t].keys()==b[t].keys()
        error=max(error,*(abs(a[t][ch][f]-b[t][ch][f]) for ch in a[t] for f in measure.FIELDS))
    return error


def apparatus(work):
    import psutil
    check(work)
    assert not any((work/n).exists() for n in ('apparatus.json','STOP','in-flight.json','cases'))
    with s.base.worker_lock(work),s.base.Guard(work):
        s.base.original(work/'in-flight.json',{'phase':'apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
        checks=[];costs=[]
        for parent in [p for p in spec.parents() if p['seed']==930101 and p['teaching_depletion'] and p['teaching_competition']]:
            folder=work/'apparatus'/parent['mode']
            _,taught,observer=x.execute(parent,spec.stages(parent)[0],folder/'train',root=work/'materials',calibration_seed=930195)
            for stage in [st for st in spec.stages(parent)[1:] if st['physical'] and st['sign']==1]:
                hashes={}
                for mode in ('observed','plain','sparse','restored','paused'):
                    _,final,_=x.execute(parent,stage,folder/stage['name']/mode,taught,observer,
                                        work/'materials',calibration_seed=930195,mode=mode)
                    hashes[mode]=final.digest
                assert len(set(hashes.values()))==1
                checks.append({'sensory':parent['mode'],'test':stage['name'],'hashes':hashes})
                if stage['test_depletion'] and stage['test_competition']:
                    other=folder/'no-reconfigure'
                    x.execute(parent,stage,other,taught,observer,work/'materials',calibration_seed=930195,no_reconfigure=True)
                    error=trajectory_error(folder/stage['name']/'observed',other); assert error<1e-9
                    checks.append({'sensory':parent['mode'],'unchanged_configuration_error':error})
                    blank=dict(stage,physical=False,name=stage['name'].removesuffix('physical1')+'physical0')
                    values={}
                    for prequeue in (False,True):
                        out=folder/f'blank-prequeue-{prequeue}'
                        _,final,_=x.execute(parent,blank,out,taught,observer,work/'materials',
                                            calibration_seed=930195,prequeue_blank=prequeue)
                        values[str(prequeue)]=final.digest
                    checks.append({'sensory':parent['mode'],'blank_queue_hashes':values,
                        'blank_queue_response_error':trajectory_error(folder/'blank-prequeue-False',folder/'blank-prequeue-True')})
            observed=[folder/st['name']/'observed' for st in spec.stages(parent)[1:] if st['physical'] and st['sign']==1]
            estimated=allocated(folder/'train')+8*max(map(allocated,observed))+8*allocated(folder/'blank-prequeue-False')
            old=read(work/'frozen.json')['historical_actual_bytes'][parent['key']]
            costs.append({'sensory':parent['mode'],'conservative_example_allocation':estimated,'historical_actual_bytes':old})
        s.base.original(work/'apparatus.json',{'passed':True,'calibration_seed':930195,'checks':checks,
            'allocation_examples':costs,'formal_individuals_created':0})
        (work/'in-flight.json').unlink()
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True,'checks':len(checks)}),flush=True)


def run(work):
    import psutil
    frozen=check(work); apparatus_result=read(work/'apparatus.json');assert apparatus_result['passed']
    assert all(c['conservative_example_allocation']<2*c['historical_actual_bytes'] for c in apparatus_result['allocation_examples'])
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    start,completed=time.monotonic(),0
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for parent in spec.parents():
            if (work/'STOP').exists():break
            assert guard.thread.is_alive();s.base.resource_check(work)
            s.base.original(work/'in-flight.json',{'unit':parent['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            folder=work/'cases'/parent['key'];begin=time.monotonic()
            _,taught,observer=x.execute(parent,spec.stages(parent)[0],folder/'train',root=work/'materials')
            for stage in spec.stages(parent)[1:]:
                x.execute(parent,stage,folder/stage['name'],taught,observer,work/'materials')
            completed+=1
            s.base.atomic_json(work/'current.json',{'completed':completed,'total':32,'last':parent['key']})
            (work/'in-flight.json').unlink()
            size,old=allocated(folder),frozen['historical_actual_bytes'][parent['key']]
            s.base.original(work/'costs'/f'{completed:03d}.json',{'unit':parent['key'],'allocated_bytes':size,
                'historical_allocated_bytes':old,'expected_allocated_bytes':1.5*old,'allocation_method':'FileStandardInfo',
                'wall_seconds':time.monotonic()-begin})
            reason=('actual unit allocation at least twice historical' if size>=2*old else
                    'actual unit allocation exceeds estimate by 50%' if size>2.25*old else
                    'two-hour budget' if time.monotonic()-start>7200 else None)
            if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>2**30:reason='originals budget'
            print(completed,parent['key'],flush=True)
            if reason:s.base.original(work/'STOP',{'reason':reason,'complete_boundary':parent['key']});break
            del taught,observer;gc.collect()
        if completed==32:s.base.original(work/'summary.json',{'status':'awaiting-analysis','references':32,'probes':512,
            'stages':544,'material_blocks':4,'wall_seconds':time.monotonic()-start})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run'))
    p.add_argument('--work',type=Path,required=True);args=p.parse_args()
    {'register':register,'apparatus':apparatus,'run':run}[args.action](args.work.resolve())
