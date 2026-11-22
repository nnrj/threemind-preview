"""R51t2 host. Public configuration interventions only; historical files stay read-only."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'persistent_cause')]
import mechanism_design as design
import investigate as previous
e=previous.e;s=previous.s;ROOT=previous.ROOT
NS=UUID('280f0c07-7a99-41fb-83a4-a5343a3cb98f')
CAP=2*2**30
read=s.base.read

def old(work):return work.parent/'persistent-activity61-v1'

def check(work):
    f=read(work/'frozen.json')
    for rel,sha in f['sources'].items():assert s.sha(ROOT/rel)==sha,rel
    assert s.sha(previous.native())==f['native_sha256']
    assert s.sha(work/'cases.json')==f['cases_sha256']
    for rel,sha in f['materials'].items():assert s.sha(work/rel)==sha,rel
    assert read(work/'registration.json')['pending']==0
    for rel,sha in f['references'].items():assert s.sha(old(work)/rel)==sha,rel
    return f

def register(work):
    assert not work.exists()
    prior=old(work);completion=read(prior/'publication/completion.json')
    assert completion['coverage']=='verified' and completion['pending']==0
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>31*2**30
    cases=design.cases(read(prior/'cases.json'))
    for c in cases:e.base.resolve_kernel('threemind.continuous-memory/6.1').configuration(
        {'seed':e.materials.SEED,**c['initial_config'],**c['birth_patch'],**c['cause_patch']})
    work.mkdir();materials={};refs={}
    for key in sorted({c['material_key'] for c in cases}|{'retention/s0/011/paired/train'}):
        src=prior/'materials'/key/'frames.jsonl';dest=work/'materials'/key/'frames.jsonl'
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
        assert s.sha(src)==s.sha(dest);materials[dest.relative_to(work).as_posix()]=s.sha(dest)
    for b in (0,1):
        root=prior/'cases'/f'v61/retention/s{b}/011/paired/train'
        for name in ('final.tmind','observer.json.xz','result.json'):
            p=root/name;refs[p.relative_to(prior).as_posix()]=s.sha(p)
    refs['publication/completion.json']=s.sha(prior/'publication/completion.json')
    s.base.original(work/'cases.json',cases)
    paths=[HERE/n for n in ('mechanism.py','mechanism_design.py','mechanism_analysis.py',
        'mechanism_protocol.zh.md','mechanism_protocol.en.md')]
    paths+=list((HERE.parent/'persistent_cause').glob('*.py'))
    paths+=list((HERE.parent/'memory_timescales').glob('*.py'))
    paths+=list((HERE.parent/'body_recovery').glob('*.py'))
    paths+=list((ROOT/'src/threemind_kernels').glob('*.py'))+[Path(s.__file__),Path(s.base.__file__)]
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    s.base.original(work/'frozen.json',{'sources':sources,'materials':materials,'references':refs,
        'cases_sha256':s.sha(work/'cases.json'),'native_sha256':s.sha(previous.native()),'stages':110,
        'originals_cap_bytes':CAP,'material_blocks':2,'authorization':'2026-11-14 three dynamical questions; campaign paused'})
    for rel in sources:
        dst=work/'frozen-source'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dst)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r51t2:dynamics-function:20261114:v1','title':'R51t2：保留抑制的持续活动与前缀区分',
            'classification':'formal','execution_status':'running','executor':'ai',
            'kernels':['threemind.continuous-memory/6.1'],'protocol':(HERE/'mechanism_protocol.zh.md').read_text('utf8'),
            'protocol_version':s.sha(HERE/'mechanism_protocol.zh.md'),'required_roles':['protocol','report','note','original'],
            'metadata':{'material_blocks':2,'stages':110,'exploratory':True,'campaign_paused':True}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R51t2 protocol '+lang,
                'markdown':(HERE/f'mechanism_protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True)
        result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)

def execute(c,work,folder=None,source=None,**kwargs):
    if c['parent'] and source is None:
        source=(old(work)/'cases'/c['parent'].removeprefix('external:')) if c['parent'].startswith('external:') else work/'cases'/c['parent']
    return previous.execute(c,folder or work/'cases'/c['key'],work,source,**kwargs)

def apparatus(work):
    check(work);assert not any((work/x).exists() for x in ('apparatus.json','in-flight.json','STOP'))
    import psutil
    checks=[];cases=read(work/'cases.json')
    with s.base.worker_lock(work),s.base.Guard(work):
        s.base.original(work/'in-flight.json',{'phase':'apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
        parent=next(c for c in read(old(work)/'cases.json') if c['key']=='v61/retention/s0/011/paired/train')
        src=work/'apparatus/retention-parent'
        previous.execute(parent,src,work,calibration=True)
        c=next(c for c in cases if c['group']=='persistent' and c['block']==0 and c['kind']=='readout_wait')
        hashes={};observers=[]
        for mode in ('observed','plain'):
            _,state,ob=execute(c,work,work/'apparatus'/('retention-'+mode),src,mode=mode,calibration=True)
            hashes[mode]=state.digest;observers.append(ob)
        assert len(set(hashes.values()))==1 and observers[0]==observers[1];checks.append(hashes)
        train=next(c for c in cases if c['group']=='prefix' and c['block']==0 and c['kind']=='sequence_training')
        src=work/'apparatus/prefix-parent';execute(train,work,src,calibration=True)
        probe=next(c for c in cases if c['parent']==train['key'] and c['cue']=='AB')
        hashes={};observers=[]
        for mode in ('observed','plain','restored','paused'):
            _,state,ob=execute(probe,work,work/'apparatus'/('prefix-'+mode),src,mode=mode,calibration=True)
            hashes[mode]=state.digest;observers.append(ob)
        assert len(set(hashes.values()))==1 and all(x==observers[0] for x in observers);checks.append(hashes)
        s.base.original(work/'apparatus.json',{'passed':True,'separate_encoding':True,'checks':checks})
        (work/'in-flight.json').unlink()
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True,'checks':checks}),flush=True)

def run(work):
    check(work);assert read(work/'apparatus.json')['passed']
    assert not any((work/x).exists() for x in ('summary.json','in-flight.json','STOP'))
    import psutil
    cases=read(work/'cases.json');started=time.monotonic();n=0
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for c in cases:
            if (work/'STOP').exists():break
            folder=work/'cases'/c['key']
            if folder.exists():
                r=read(folder/'result.json');assert r['status']=='complete' and e.base.image(folder/'final.tmind').digest==r['final_sha256'];n+=1;continue
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            s.base.original(work/'in-flight.json',{'key':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            r,_,_=execute(c,work);n+=1
            s.base.atomic_json(work/'current.json',{'complete':n,'total':len(cases),'last':c['key'],'elapsed_seconds':time.monotonic()-started})
            (work/'in-flight.json').unlink()
            assert e.support.allocated(work)<CAP,'originals budget exceeded at complete boundary'
            print(json.dumps({'complete':n,'key':c['key'],'seconds':r['wall_seconds']}),flush=True);gc.collect()
        if n==len(cases):s.base.original(work/'summary.json',{'complete':n,'wall_seconds':time.monotonic()-started})
    print(json.dumps({'complete':n,'total':len(cases)}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run','check'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
