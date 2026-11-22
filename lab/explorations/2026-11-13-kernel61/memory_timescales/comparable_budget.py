"""Separate like-for-like evidence cost from additional audit storage."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid5
import lzma

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_timescales as x
from audit import disk_allocation

ORIGINAL=x.s.base.original
COMPARABLE={'final.tmind','trajectory.json.xz','observer.json.xz','result.json'}
SUPPLEMENTAL={'initial.tmind','intervened.tmind','intervention.json','projections.json.xz',
              'inputs.json.xz','delivered.json.xz','scheduled.json.xz','initial-observer.json.xz'}

def compact_original(path,value,*,compressed=False):
    path=Path(path)
    if path.name!='intervention.json':return ORIGINAL(path,value,compressed=compressed)
    assert not compressed
    raw=x.s.base.encoded(value);target=path.with_suffix('.json.xz')
    target.parent.mkdir(parents=True,exist_ok=True)
    payload=lzma.compress(raw,preset=1)
    assert lzma.decompress(payload)==raw
    return x.s.blob(target,payload)

def read(path):
    path=Path(path)
    if path.exists():return x.read(path)
    assert path.name=='intervention.json'
    return json.loads(lzma.decompress(path.with_suffix('.json.xz').read_bytes()))

def cost(folder,kind,replacement=None):
    paths=[p for p in folder.iterdir() if p.is_file()]
    names=COMPARABLE|SUPPLEMENTAL|{'milestones.zip'}
    if (folder/'intervention.json.xz').exists():names=(names-{'intervention.json'})|{'intervention.json.xz'}
    assert {p.name for p in paths}==names
    comparable=COMPARABLE|({'milestones.zip'} if kind=='probe' else set())
    files=[]
    for p in sorted(paths):
        actual=replacement if replacement and p.name=='intervention.json' else p
        files.append({'path':p.name,'sha256':x.s.sha(p),'bytes':p.stat().st_size,
            'allocated_bytes':disk_allocation(actual)['allocated_bytes'],
            'category':'comparable' if p.name in comparable else 'supplemental'})
    return {'files':files,'comparable_bytes':sum(p['allocated_bytes'] for p in files if p['category']=='comparable'),
            'supplemental_bytes':sum(p['allocated_bytes'] for p in files if p['category']=='supplemental'),
            'total_bytes':sum(p['allocated_bytes'] for p in files)}

def prepare(work):
    frozen=x.check(work);app=x.read(work/'apparatus.json');assert app['passed']
    assert not any((work/n).exists() for n in ('cases','summary.json','in-flight.json'))
    stop=(work/'STOP').read_bytes() if (work/'STOP').exists() else None
    if stop:assert json.loads(stop)['reason']=='pilot process private memory exceeds 1 GiB'
    dest=work/'budget-amendment';dest.mkdir(exist_ok=False)
    if stop:(dest/'apparatus-STOP.original.json').write_bytes(stop)
    cases={c['key']:c for c in x.read(work/'cases.json')};costs=[];compression=[]
    for row in app['costs']:
        folder=work/'apparatus/main'/row['key']
        assert x.e.support.allocated(folder)==row['allocated_bytes']
        raw=(folder/'intervention.json').read_bytes();value=json.loads(raw)
        target=dest/'compressed-interventions'/row['key']/'intervention.json'
        compact_original(target,value);target=target.with_suffix('.json.xz')
        assert lzma.decompress(target.read_bytes())==raw
        compression.append({'key':row['key'],'raw_sha256':x.s.sha(folder/'intervention.json'),'packed_sha256':x.s.sha(target)})
        measured=cost(folder,cases[row['key']]['kind'],target)
        costs.append(row|measured)
    comparable_factor=max(1.5,max(c['comparable_bytes']/c['historical_actual_bytes'] for c in costs))
    full_factor=max(1.5,max(c['total_bytes']/c['historical_actual_bytes'] for c in costs))
    extra=max(c['supplemental_bytes'] for c in costs)*1.5
    estimated=sum(frozen['old_allocated_bytes'].values())*comparable_factor+len(cases)*extra+x.e.support.allocated(work)+64*2**20
    passed=comparable_factor<2 and estimated<2*2**30
    paths=[Path(__file__),HERE/'budget-amendment.zh.md',HERE/'budget-amendment.en.md']
    proof={'passed':passed,'created_engines':0,'before_formal_run':True,'costs':costs,
           'comparable_factor':comparable_factor,'full_factor':full_factor,'supplemental_bound_per_stage':extra,
           'compressed_interventions':compression,
           'estimated_full_allocated_bytes':estimated,'originals_cap_bytes':2*2**30,
           'sources':{p.relative_to(x.ROOT).as_posix():x.s.sha(p) for p in paths}}
    assert passed,'preserve original cost proof; formal run not authorized by budget'
    # Re-execute six independent apparatus copies, preserving the completed apparatus.
    # Collect unreachable Python observation objects at every complete stage boundary.
    import psutil
    q=dest/'memory-qualification';q.mkdir();checks=[]
    x.s.base.original=compact_original
    gc.collect()
    with x.s.base.worker_lock(work),x.s.base.Guard(q):
        for key in ('short/train-0','short/s0/101/warm','short/s0/101/g1/AB','short/s0/101/g1/DB',
                    'history/s0/101/d1/AB','history/s0/101/d1/DB'):
            assert not (q/'STOP').exists()
            reference=work/'apparatus/main'/key
            initial=x.e.base.image(reference/'initial.tmind');observer=x.e.unpacked(reference/'initial-observer.json.xz')
            ORIGINAL(q/'in-flight.json',{'phase':'memory-qualification','key':key,'pid':os.getpid(),'created':psutil.Process().create_time()})
            result,state,observed=x.e.execute(cases[key],q/'cases'/key,work/'materials',initial,observer,calibration=True)
            assert state.digest==x.read(reference/'result.json')['final_sha256']
            assert observed==x.e.unpacked(reference/'observer.json.xz')
            assert x.e.unpacked(q/'cases'/key/'trajectory.json.xz')==x.e.unpacked(reference/'trajectory.json.xz')
            checks.append({'key':key,'complete_state_exact':True,'observer_exact':True,'trajectory_exact':True})
            (q/'in-flight.json').unlink()
            del initial,observer,result,state,observed
            gc.collect()
            print('memory qualification',key,flush=True)
    resources=x.read(q/'resource-summary.json')
    assert not (q/'STOP').exists() and resources['peak_private_bytes']<=2**30
    proof.update(memory_qualification=checks,qualification_resources=resources,created_engines=6,formal_individuals_created=0,
                 estimated_full_allocated_bytes=estimated+x.e.support.allocated(q))
    assert proof['estimated_full_allocated_bytes']<2*2**30
    ORIGINAL(dest/'proof.json',proof)
    for p in paths:shutil.copyfile(p,dest/p.name)
    import httpx
    x.s.base.load_env()
    with x.s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        rec=x.s.base.ResearchRecorder(work,x.e.base.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(x.NS,'budget-document-'+lang)),'request_id':str(uuid5(x.NS,'budget-note-'+lang)),
                'expected_revision':0,'kind':'note','title':'R51t comparable storage accounting '+lang,
                'markdown':(HERE/f'budget-amendment.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        x.s.base.original(dest/'registration.json',{'pending':rec.status['pending'],'proof_sha256':x.s.sha(dest/'proof.json')})
    with x.s.base.worker_lock(work):
        assert x.s.base.resource_check(work)['safe'] and not (work/'in-flight.json').exists()
        if stop:
            assert (work/'STOP').read_bytes()==stop==(dest/'apparatus-STOP.original.json').read_bytes()
            ORIGINAL(dest/'stop-retirement.json',{'reason':'complete apparatus; fresh boundary-collection qualification passed',
                'original_stop_sha256':x.s.sha(work/'STOP'),'qualification_peak_private_bytes':resources['peak_private_bytes']})
            (work/'STOP').unlink()
    print(json.dumps({k:proof[k] for k in ('passed','comparable_factor','full_factor','estimated_full_allocated_bytes','created_engines')}),flush=True)

def check(work):
    frozen=x.check(work);proof=x.read(work/'budget-amendment/proof.json')
    receipt=x.read(work/'budget-amendment/registration.json')
    assert proof['passed'] and receipt['pending']==0 and receipt['proof_sha256']==x.s.sha(work/'budget-amendment/proof.json')
    for rel,sha in proof['sources'].items():assert x.s.sha(x.ROOT/rel)==sha
    assert proof['comparable_factor']<2 and proof['estimated_full_allocated_bytes']<2*2**30
    return frozen,proof

def run(work):
    import psutil
    frozen,proof=check(work);x.s.base.original=compact_original
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    cases=x.read(work/'cases.json');start=time.monotonic();completed=0
    with x.s.base.worker_lock(work),x.s.base.Guard(work) as guard:
        x.s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for c in cases:
            if (work/'STOP').exists():break
            assert guard.thread.is_alive() and x.s.base.resource_check(work)['safe']
            x.s.base.original(work/'in-flight.json',{'unit':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            source=work/'cases'/c['parent'] if c['parent'] else None
            parent=x.e.base.image(source/'final.tmind') if source else None
            reader=x.e.unpacked(source/'observer.json.xz') if source else None
            folder=work/'cases'/c['key']
            result,state,observer=x.e.execute(c,folder,work/'materials',parent,reader)
            measured=cost(folder,c['kind']);old=frozen['old_allocated_bytes'][c['key']];completed+=1
            x.s.base.original(work/'costs'/f'{completed:03d}.json',{'unit':c['key'],**measured,
                'historical_allocated_bytes':old,'expected_comparable_bytes':proof['comparable_factor']*old,
                'allocation_method':'FileStandardInfo','wall_seconds':result['wall_seconds']})
            x.s.base.atomic_json(work/'current.json',{'completed':completed,'total':len(cases),'last':c['key']})
            (work/'in-flight.json').unlink()
            reason=('actual comparable stage allocation at least twice historical' if measured['comparable_bytes']>=2*old else
                    'comparable stage allocation exceeds frozen estimate by 50%' if measured['comparable_bytes']>1.5*proof['comparable_factor']*old else
                    'two-hour batch budget' if time.monotonic()-start>7200 else None)
            if x.e.support.allocated(work)>2*2**30:reason='full originals budget'
            if completed%16==0:print(completed,c['key'],flush=True)
            if reason:x.s.base.original(work/'STOP',{'reason':reason,'complete_boundary':c['key']});break
            del parent,reader,state,observer;gc.collect()
        if completed==len(cases):x.s.base.original(work/'summary.json',{'status':'awaiting-analysis','stages':592,
            'teaching_references':34,'diagnostics':510,'material_blocks':2,'wall_seconds':time.monotonic()-start,
            'cost_accounting':'comparable records and full originals separately checked'})

def analyze(work):
    check(work)
    import analyze_timescales
    analyze_timescales.read=read
    analyze_timescales.analyze(work)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','run','analyze'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();{'prepare':prepare,'run':run,'analyze':analyze}[a.action](a.work.resolve())
