"""Bounded historical factor crossing with retained originals and true kernel identities."""
import argparse
from copy import deepcopy
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
import mechanism as h
s=h.s;e=h.e;ROOT=h.ROOT;read=s.base.read
NS=UUID('365307cd-8d5d-54f1-9378-3fa2270cda9c')
CAP=512*2**20

def old(work):return work.parent/'persistent-activity61-v1'

def design(work):
    prior=old(work);oldcases=read(prior/'cases.json')+read(prior/'supplement-cases.json');index={c['key']:c for c in oldcases}
    out=[];refs=[]
    for version in ('3.1','5.1'):
        basevar='v'+version.replace('.','')
        for retention in ('current','legacy-edges','legacy-all'):
            basepatch={} if retention=='current' else {'consolidation_mode':'legacy-stability'}
            if retention=='legacy-all':basepatch|={'node_retention_mode':'manual'}
            for novelty in ('arrival-window','immediate'):
                variant=f'v{version}-{retention}-{novelty}'
                oldvar=basevar+('' if retention=='current' else '-'+retention)
                existing=novelty=='arrival-window' and any(c['variant']==oldvar for c in oldcases)
                for b in (0,1):
                    keys=[f'short/train-{b}',f'history/s{b}/101/d1/AB',f'history/s{b}/101/d1/DB']
                    for i,key in enumerate(keys):
                        if existing:
                            c=deepcopy(index[oldvar+'/'+key]);c.update(matrix_variant=variant,block=b,retention=retention,novelty=novelty)
                            refs.append(c);continue
                        c=deepcopy(index[basevar+'/'+key]);c.update(key=variant+'/'+key,variant=variant,matrix_variant=variant,
                            parent=None if i==0 else variant+'/'+keys[0],birth_patch=basepatch|{'novelty_mode':novelty},
                            cause_patch={},block=b,retention=retention,novelty=novelty)
                        out.append(c)
    assert len(out)==42 and len(refs)==30
    return out,refs

def check(work):
    f=read(work/'frozen.json')
    for rel,sha in f['sources'].items():assert s.sha(ROOT/rel)==sha,rel
    for rel,sha in f['materials'].items():assert s.sha(work/rel)==sha,rel
    for rel,sha in f['references'].items():assert s.sha(old(work)/rel)==sha,rel
    assert s.sha(work/'cases.json')==f['cases_sha256'] and s.sha(h.previous.native())==f['native_sha256']
    assert read(work/'registration.json')['pending']==0
    return f

def register(work):
    assert not work.exists();assert read(old(work)/'publication/completion.json')['pending']==0
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>27*2**30
    cases,refs=design(work)
    for c in cases:e.base.resolve_kernel('threemind.continuous-memory/'+c['version']).configuration({'seed':e.materials.SEED,**c['initial_config'],**c['birth_patch']})
    work.mkdir();s.base.original(work/'cases.json',cases);s.base.original(work/'reference-cases.json',refs)
    materials={};references={}
    for key in sorted({c['material_key'] for c in cases}):
        src=old(work)/'materials'/key/'frames.jsonl';dst=work/'materials'/key/'frames.jsonl';dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        assert s.sha(src)==s.sha(dst);materials[dst.relative_to(work).as_posix()]=s.sha(dst)
    for c in refs:
        for name in ('initial.tmind','final.tmind','observer.json.xz','trajectory.json.xz','result.json'):
            src=old(work)/'cases'/c['key']/name;references[src.relative_to(old(work)).as_posix()]=s.sha(src)
            dest=work/'references'/c['key']/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
            materials[dest.relative_to(work).as_posix()]=s.sha(dest)
    for name in ('audit.json','audit-novelty.json','publication/completion.json'):
        src=old(work)/name;references[name]=s.sha(src)
        dest=work/'reference-audit'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
        materials[dest.relative_to(work).as_posix()]=s.sha(dest)
    paths=[HERE/n for n in ('prefix_cross.py','prefix_cross_analysis.py','prefix_cross_protocol.zh.md','prefix_cross_protocol.en.md','mechanism.py','mechanism_design.py')]
    paths += list((HERE.parent/'persistent_cause').glob('*.py'))+list((HERE.parent/'memory_timescales').glob('*.py'))+list((HERE.parent/'body_recovery').glob('*.py'))
    paths += list((ROOT/'src/threemind_kernels').glob('*.py'))+[Path(s.__file__),Path(s.base.__file__)]
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    s.base.original(work/'frozen.json',{'sources':sources,'materials':materials,'references':references,'cases_sha256':s.sha(work/'cases.json'),
        'native_sha256':s.sha(h.previous.native()),'new_stages':42,'reused_stages':30,'originals_cap_bytes':CAP})
    for rel in sources:
        dst=work/'frozen-source'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dst)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r51t5:prefix-crossing:20261114:v1','title':'R51t5：新颖性时机与保持规则的前缀交叉定位',
            'classification':'formal','execution_status':'running','executor':'ai','kernels':['threemind.continuous-memory/3.1','threemind.continuous-memory/5.1'],
            'protocol':(HERE/'prefix_cross_protocol.zh.md').read_text('utf8'),'protocol_version':s.sha(HERE/'prefix_cross_protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],'metadata':{'material_blocks':2,'new_stages':42,'reused_stages':30,'main_paused':True}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),'expected_revision':0,
                'kind':'protocol','title':'R51t5 protocol '+lang,'markdown':(HERE/f'prefix_cross_protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True);result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)

def apparatus(work):
    check(work);assert read(work.parent/'delayed-choice61-v1'/'summary.json')['complete']==64
    assert not any((work/p).exists() for p in ('apparatus.json','in-flight.json','STOP'))
    cases=read(work/'cases.json');checks=[]
    with s.base.worker_lock(work),s.base.Guard(work):
        for version in ('3.1','5.1'):
            train=next(c for c in cases if c['version']==version and c['retention']=='legacy-all' and c['novelty']=='immediate' and c['kind']=='sequence_training' and c['block']==0)
            src=work/'apparatus'/version/'train';h.previous.execute(train,src,work,calibration=True)
            probe=next(c for c in cases if c['parent']==train['key'] and c['cue']=='AB');hashes={};obs=[]
            for mode in ('observed','plain','restored','paused'):
                _,state,ob=h.previous.execute(probe,work/'apparatus'/version/mode,work,src,mode=mode,calibration=True);hashes[mode]=state.digest;obs.append(ob)
            assert len(set(hashes.values()))==1 and all(v==obs[0] for v in obs);checks.append({'version':version,'hashes':hashes})
        s.base.original(work/'apparatus.json',{'passed':True,'checks':checks,'separate_encoding':True})
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json');print(json.dumps({'passed':True}),flush=True)

def run(work):
    check(work);assert read(work/'apparatus.json')['passed'] and read(work.parent/'delayed-choice61-v1'/'summary.json')['complete']==64
    assert not any((work/p).exists() for p in ('summary.json','STOP','in-flight.json'))
    import psutil
    cases=read(work/'cases.json');n=0;started=time.monotonic()
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for c in cases:
            if (work/'STOP').exists():break
            if time.monotonic()-started>1800:s.base.original(work/'STOP',{'reason':'30 minute host budget'});break
            f=work/'cases'/c['key'];assert not f.exists(),'new run only; inspect complete boundary before any resume'
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            s.base.original(work/'in-flight.json',{'key':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            src=work/'cases'/c['parent'] if c['parent'] else None
            r,_,_=h.previous.execute(c,f,work,src);n+=1
            s.base.atomic_json(work/'current.json',{'complete':n,'total':len(cases),'last':c['key'],'elapsed_seconds':time.monotonic()-started})
            (work/'in-flight.json').unlink();assert e.support.allocated(work)<CAP
            print(json.dumps({'complete':n,'key':c['key'],'seconds':r['wall_seconds']}),flush=True);gc.collect()
        if n==42:s.base.original(work/'summary.json',{'complete':n,'wall_seconds':time.monotonic()-started})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run','check'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
