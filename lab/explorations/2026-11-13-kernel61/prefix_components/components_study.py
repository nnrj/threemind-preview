"""Preregister and run R51t6 as isolated research copies, never production kernels."""
import argparse
from copy import deepcopy
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import execute_components as e
import research_kernel as research
sys.path.insert(0,str(HERE.parent/'dynamics_function'))
import prefix_cross as previous
s=e.s; ROOT=e.materials.ROOT; read=s.base.read
NS=UUID('67b5fb06-5912-5a34-a97e-f2b2827d485b')
CAP=1024*2**20
VARIANTS={
 'reference':{},
 'window':{'novelty_mode':'arrival-window'},
 'novelty-off':{'research_novelty_weight':False,'research_novelty_stability':False},
 'novelty-weight-only':{'research_novelty_stability':False},
 'novelty-stability-only':{'research_novelty_weight':False},
 'no-use-protection':{'research_use_protection':False},
 'no-stability-protection':{'research_stability_protection':False},
 'no-eligibility-protection':{'research_eligibility_protection':False},
 'no-pass-weight-gain':{'research_pass_weight_gain':False},
}

def old(work): return work.parent/'prefix-cross61-v1'

def design(work):
    cases=read(old(work)/'cases.json')
    index={c['material_key']:c for c in cases if c['version']=='5.1' and c['retention']=='legacy-edges' and c['novelty']=='immediate'}
    out=[]
    for variant,patch in VARIANTS.items():
        for block in (0,1):
            keys=[f'short/train-{block}',f'history/s{block}/101/d1/AB',f'history/s{block}/101/d1/DB']
            for i,key in enumerate(keys):
                c=deepcopy(index[key]);c.update(key=variant+'/'+key,variant=variant,parent=None if i==0 else variant+'/'+keys[0],
                    birth_patch={'consolidation_mode':'legacy-stability','novelty_mode':'immediate'}|patch,
                    cause_patch={},block=block,comparison='birth-component',weight_donor=None)
                out.append(c)
    for block in (0,1):
        for variant,parent,patch,donor in (
          ('reference-with-window-weights','reference',{},'window'),
          ('window-with-reference-weights','window',{},'reference'),
          ('reference-no-probe-learning','reference',{'edge_consolidation_enabled':False},None),
          ('reference-no-probe-forgetting','reference',{'forgetting_rate':0.0},None)):
            for cue in ('AB','DB'):
                key=f'history/s{block}/101/d1/{cue}';c=deepcopy(index[key])
                c.update(key=variant+'/'+key,variant=variant,parent=parent+f'/short/train-{block}',
                    birth_patch={'consolidation_mode':'legacy-stability','novelty_mode':'arrival-window' if parent=='window' else 'immediate'},
                    cause_patch=patch,block=block,comparison='post-teaching-intervention',
                    weight_donor=donor+f'/short/train-{block}' if donor else None)
                out.append(c)
    assert len(out)==70
    return out

def check(work):
    f=read(work/'frozen.json')
    amended=read(work/'source-amendment.json')['sources'] if (work/'source-amendment.json').exists() else {}
    for rel,sha in (f['sources']|amended).items(): assert s.sha(ROOT/rel)==sha,rel
    for rel,sha in f['materials'].items(): assert s.sha(work/rel)==sha,rel
    assert s.sha(work/'cases.json')==f['cases_sha256']
    assert s.sha(previous.h.previous.native())==f['native_sha256']
    assert read(work/'registration.json')['pending']==0
    return f

def register(work):
    assert not work.exists()
    assert read(old(work)/'publication/completion.json')['pending']==0
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>28.5*2**30
    cases=design(work)
    for c in cases: research.ResearchConfig(seed=e.materials.SEED,**c['initial_config'],**c['birth_patch'])
    work.mkdir();s.base.original(work/'cases.json',cases)
    materials={}
    for key in sorted({c['material_key'] for c in cases}):
        src=old(work)/'materials'/key/'frames.jsonl';dst=work/'materials'/key/'frames.jsonl'
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        assert s.sha(src)==s.sha(dst);materials[dst.relative_to(work).as_posix()]=s.sha(dst)
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))+[HERE/'source-diff.json']
    for name in ('persistent_cause','memory_timescales','body_recovery'):
        paths+=list((HERE.parent/name).glob('*.py'))
    paths+=list((ROOT/'src/threemind_kernels').glob('*.py'))+[Path(s.__file__),Path(s.base.__file__)]
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    s.base.original(work/'frozen.json',{'sources':sources,'materials':materials,'cases_sha256':s.sha(work/'cases.json'),
       'native_sha256':s.sha(previous.h.previous.native()),'stages':70,'material_blocks':2,'originals_cap_bytes':CAP,
       'research_identity':research.KERNEL_ID,'production_changed':False})
    for rel in sources:
        dst=work/'frozen-source'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dst)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
            token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r51t6:prefix-components:20261114:v2','title':'R51t6：前缀关系中新颖性与旧保持规则的作用拆分',
          'classification':'formal','execution_status':'running','executor':'ai','kernels':[research.KERNEL_ID],
          'protocol':(HERE/'protocol.zh.md').read_text('utf8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
          'required_roles':['protocol','report','note','original'],'metadata':{'material_blocks':2,'stages':70,'main_paused':True,
           'isolated_research_derivative_of':'threemind.continuous-memory/5.1','not_production_62':True}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
              'expected_revision':0,'kind':'protocol','title':'R51t6 protocol '+lang,'markdown':(HERE/f'protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True)
        result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)

def execute(c,folder,work,source=None,mode='observed',calibration=False):
    initial=e.storage.image(source/'final.rstate') if source else None
    observer=e.unpacked(source/'observer.json.xz') if source else None
    return e.execute(c,folder,work/'materials',initial,observer,mode=mode,calibration=calibration)

def scientific_state(doc):
    doc=deepcopy(doc)
    for key in ('schema','dynamics','definition','definition_hash','audit'):doc.pop(key,None)
    doc['config']={k:v for k,v in doc['config'].items() if not k.startswith('research_')}
    return doc

def assert_near(a,b,path=''):
    if isinstance(a,dict):
        assert set(a)==set(b),path
        for k in a:assert_near(a[k],b[k],path+'/'+k)
    elif isinstance(a,list):
        assert len(a)==len(b),path
        for i,(x,y) in enumerate(zip(a,b)):assert_near(x,y,path+'/'+str(i))
    elif isinstance(a,(float,int)) and not isinstance(a,bool):
        assert abs(a-b)<=1e-12*max(1,abs(a),abs(b)),(path,a,b)
    else:assert a==b,(path,a,b)

def apparatus(work):
    check(work);assert not any((work/p).exists() for p in ('apparatus.json','in-flight.json','STOP'))
    cases=read(work/'cases.json');checks=[]
    import psutil
    with s.base.worker_lock(work),s.base.Guard(work):
        s.base.original(work/'in-flight.json',{'phase':'apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
        train=next(c for c in cases if c['variant']=='reference' and c['kind']=='sequence_training' and c['block']==0)
        src=work/'apparatus/research/train';_,a,_=execute(train,src,work,calibration=True)
        native=work/'apparatus/native/train';_,b,_=previous.h.previous.execute(train,native,work,calibration=True)
        assert_near(scientific_state(a.to_dict()),scientific_state(b.to_dict()))
        probe=next(c for c in cases if c['parent']==train['key'] and c['cue']=='AB')
        hashes={};observers=[]
        for mode in ('observed','plain','restored','paused'):
            _,z,observer=execute(probe,work/'apparatus/research'/mode,work,src,mode=mode,calibration=True)
            hashes[mode]=z.digest;observers.append(observer)
        assert len(set(hashes.values()))==1 and all(o==observers[0] for o in observers)
        _,nz,_=previous.h.previous.execute(probe,work/'apparatus/native/probe',work,native,calibration=True)
        assert_near(scientific_state(z.to_dict()),scientific_state(nz.to_dict()))
        checks.append({'native_parity':True,'state_tolerance':1e-12,'observer_hashes':hashes})
        # Each switch remains part of the full snapshot and survives restoration.
        for key in research.SWITCHES:
            c=research.ResearchConfig(consolidation_mode='legacy-stability',**{key:False})
            engine=research.ResearchEngine(c);state=engine.capture_state()
            restored=research.ResearchEngine(state=e.storage.Codec.decode(e.storage.Codec.encode(state)))
            assert restored.capture_state().digest==state.digest and not getattr(restored.config,key)
        s.base.original(work/'apparatus.json',{'passed':True,'checks':checks,'switch_restore':list(research.SWITCHES),'separate_encoding':True})
        (work/'in-flight.json').unlink()
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True}),flush=True)

def run(work):
    check(work);assert read(work/'apparatus.json')['passed']
    assert not any((work/p).exists() for p in ('summary.json','STOP','in-flight.json'))
    import psutil
    cases=read(work/'cases.json');n=0;started=time.monotonic()
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for c in cases:
            if (work/'STOP').exists():break
            if time.monotonic()-started>3600:s.base.original(work/'STOP',{'reason':'one hour scientific host budget'});break
            folder=work/'cases'/c['key'];assert not folder.exists()
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            s.base.original(work/'in-flight.json',{'key':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            src=work/'cases'/c['parent'] if c['parent'] else None
            result,_,_=execute(c,folder,work,src);n+=1
            s.base.atomic_json(work/'current.json',{'complete':n,'total':len(cases),'last':c['key'],'elapsed_seconds':time.monotonic()-started})
            (work/'in-flight.json').unlink();assert e.support.allocated(work)<CAP
            print(json.dumps({'complete':n,'key':c['key'],'seconds':result['wall_seconds']}),flush=True);gc.collect()
        if n==len(cases):s.base.original(work/'summary.json',{'complete':n,'wall_seconds':time.monotonic()-started})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run','check'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
