"""R63o lossless trajectory storage; frozen experimental operations unchanged."""
import argparse
import gc
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_formation as x
ORIGINAL=x.s.base.original


def write(path,value,*,compressed=False):
    path=Path(path)
    if path.name!='trajectory.json.gz':return ORIGINAL(path,value,compressed=compressed)
    assert compressed
    raw=x.s.base.encoded(value);packed=lzma.compress(raw,preset=1)
    assert lzma.decompress(packed)==raw
    target=path.with_suffix('.xz');assert not path.exists()
    target.parent.mkdir(parents=True,exist_ok=True)
    result=x.s.blob(target,packed)
    assert lzma.decompress(target.read_bytes())==raw
    return result


def read(path):
    path=Path(path)
    if not path.exists() and path.name=='trajectory.json.gz':path=path.with_suffix('.xz')
    raw=path.read_bytes()
    if path.suffix=='.xz':raw=lzma.decompress(raw)
    elif path.suffix=='.gz':raw=gzip.decompress(raw)
    return json.loads(raw)


def prepare(work):
    x.check(work);app=x.read(work/'apparatus.json');assert app['passed']
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    dest=work/'storage-amendment';dest.mkdir(exist_ok=False)
    checked=[];replacements={};start=time.monotonic()
    for source in sorted((work/'apparatus').rglob('trajectory.json.gz')):
        raw=gzip.decompress(source.read_bytes());value=json.loads(raw)
        assert x.s.base.encoded(value)==raw
        target=dest/'trajectories'/source.relative_to(work/'apparatus').with_suffix('.xz')
        target.parent.mkdir(parents=True,exist_ok=True)
        write(target.with_suffix('.gz'),value,compressed=True)
        assert lzma.decompress(target.read_bytes())==raw and read(target)==value
        replacements[source]=target
        checked.append({'source':source.relative_to(work).as_posix(),'source_sha256':x.s.sha(source),
            'decoded_sha256':hashlib.sha256(raw).hexdigest(),'target':target.relative_to(work).as_posix(),
            'target_sha256':x.s.sha(target),'decoded_bytes':len(raw),
            'old_allocated_bytes':x.disk_allocation(source)['allocated_bytes'],
            'new_allocated_bytes':x.disk_allocation(target)['allocated_bytes']})
    def estimate(folder):
        return sum(x.disk_allocation(replacements.get(p,p))['allocated_bytes'] for p in folder.rglob('*') if p.is_file())
    costs=[]
    for row in app['allocation_examples']:
        mode=row['sensory'];folder=work/'apparatus'/mode
        measured=[folder/f'test{d}{c}/sign1/physical1/observed' for d in (0,1) for c in (0,1)]
        size=estimate(folder/'train')+8*max(map(estimate,measured))+8*estimate(folder/'blank-prequeue-False')
        assert size<2*row['historical_actual_bytes']
        costs.append(row|{'xz_conservative_example_allocation':size})
    paths=[Path(__file__),HERE/'storage-amendment.zh.md',HERE/'storage-amendment.en.md']
    proof={'passed':True,'created_engines':0,'trajectory_count':len(checked),'checks':checked,'costs':costs,
        'wall_seconds':time.monotonic()-start,'encoding':'xz preset 1, identical decoded JSON bytes',
        'sources':{p.relative_to(x.ROOT).as_posix():x.s.sha(p) for p in paths}}
    assert len(checked)==48
    ORIGINAL(dest/'proof.json',proof)
    for p in paths:shutil.copyfile(p,dest/p.name)
    import httpx
    x.s.base.load_env()
    with x.s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        rec=x.s.base.ResearchRecorder(work,x.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(x.x.NS,'xz-document-'+lang)),'request_id':str(uuid5(x.x.NS,'xz-note-'+lang)),
                'expected_revision':0,'kind':'note','title':'R63o lossless trajectory storage '+lang,
                'markdown':(HERE/f'storage-amendment.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        ORIGINAL(dest/'registration.json',{'pending':rec.status['pending'],'before_formal_run':True,
                                           'proof_sha256':x.s.sha(dest/'proof.json')})
    print(json.dumps({'passed':True,'trajectories':len(checked),'costs':costs,'created_engines':0}),flush=True)


def check(work):
    frozen=x.check(work);proof=x.read(work/'storage-amendment/proof.json')
    registration=x.read(work/'storage-amendment/registration.json')
    assert proof['passed'] and registration['pending']==0 and registration['proof_sha256']==x.s.sha(work/'storage-amendment/proof.json')
    for rel,sha in proof['sources'].items():assert x.s.sha(x.ROOT/rel)==sha
    assert all(r['xz_conservative_example_allocation']<2*r['historical_actual_bytes'] for r in proof['costs'])
    return frozen


def run(work):
    import psutil
    frozen=check(work)
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    x.s.base.original=write
    start,completed=time.monotonic(),0
    with x.s.base.worker_lock(work),x.s.base.Guard(work) as guard:
        x.s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for parent in x.spec.parents():
            if (work/'STOP').exists():break
            assert guard.thread.is_alive();x.s.base.resource_check(work)
            ORIGINAL(work/'in-flight.json',{'unit':parent['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            folder=work/'cases'/parent['key'];begin=time.monotonic()
            _,taught,observer=x.x.execute(parent,x.spec.stages(parent)[0],folder/'train',root=work/'materials')
            for stage in x.spec.stages(parent)[1:]:x.x.execute(parent,stage,folder/stage['name'],taught,observer,work/'materials')
            completed+=1
            x.s.base.atomic_json(work/'current.json',{'completed':completed,'total':32,'last':parent['key']})
            (work/'in-flight.json').unlink()
            size,old=x.allocated(folder),frozen['historical_actual_bytes'][parent['key']]
            ORIGINAL(work/'costs'/f'{completed:03d}.json',{'unit':parent['key'],'allocated_bytes':size,
                'historical_allocated_bytes':old,'expected_allocated_bytes':1.5*old,'allocation_method':'FileStandardInfo',
                'wall_seconds':time.monotonic()-begin})
            reason=('actual unit allocation at least twice historical' if size>=2*old else
                    'actual unit allocation exceeds estimate by 50%' if size>2.25*old else
                    'two-hour budget' if time.monotonic()-start>7200 else None)
            if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>2**30:reason='originals budget'
            print(completed,parent['key'],flush=True)
            if reason:ORIGINAL(work/'STOP',{'reason':reason,'complete_boundary':parent['key']});break
            del taught,observer;gc.collect()
        if completed==32:ORIGINAL(work/'summary.json',{'status':'awaiting-analysis','references':32,'probes':512,
            'stages':544,'material_blocks':4,'wall_seconds':time.monotonic()-start})


def analyze(work):
    check(work)
    import analyze_formation as a
    a.read=read
    a.analyze(work)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','run','analyze'));p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();{'prepare':prepare,'run':run,'analyze':analyze}[args.action](args.work.resolve())
