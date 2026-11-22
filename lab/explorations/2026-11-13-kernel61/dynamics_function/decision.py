"""R51t4 registration and guarded serial host; no Core or default mutation."""
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
import decision_design as d
import decision_execute as x
s=h.s;e=h.e;ROOT=h.ROOT;read=s.base.read
NS=UUID('5287a211-dad5-5b2e-b522-3250689610af')
CAP=2*2**30

def check(work):
    f=read(work/'frozen.json')
    for rel,sha in f['sources'].items():assert s.sha(ROOT/rel)==sha,rel
    for rel,sha in f['materials'].items():assert s.sha(work/rel)==sha,rel
    assert s.sha(h.previous.native())==f['native_sha256']
    assert read(work/'registration.json')['pending']==0
    assert s.sha(work/'cases.json')==f['cases_sha256']
    return f

def register(work):
    assert not work.exists()
    prior=work.parent/'dynamics-function61-v1';h.check(prior);assert read(prior/'audit.json')['passed']
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>31*2**30
    work.mkdir();cases=d.table();s.base.original(work/'cases.json',cases)
    old=work.parent/'persistent-activity61-v1';oldcases=read(old/'cases.json');materials={}
    for task in ('pair','prefix'):
        for swap in (0,1):
            key=f'retention/s{swap}/011/paired/train' if task=='pair' else f'short/train-{swap}'
            c=next(c for c in oldcases if c['variant']=='v61' and c['material_key']==key)
            rows=e.material_frames(c,old/'materials')
            assert all(r['enqueue_us']<=int(r['stimulus']['time_us']) for r in rows)
            dest=work/'materials'/f'{task}-s{swap}.json'
            s.base.original(dest,{'source_work':str(old),'source_case':c,'frames':rows,'end_us':c['end_us'],
                'original_sha256':s.sha(old/'materials'/key/'frames.jsonl')})
            materials[dest.relative_to(work).as_posix()]=s.sha(dest)
    s.base.original(work/'candidate-selection.json',{'source_analysis_sha256':s.sha(prior/'analysis.json'),
        'source_audit_sha256':s.sha(prior/'audit.json'),'selected':d.PROFILES,
        'selection':'shortest field list among nonsaturating recovered candidates; table-order tie break; prefix least negative worst margin',
        'formal_new_material_used':False})
    paths=[HERE/n for n in ('decision.py','decision_execute.py','decision_design.py','decision_analysis.py',
        'decision_protocol.zh.md','decision_protocol.en.md')]
    paths += [HERE/'mechanism.py',HERE/'mechanism_design.py']
    paths += list((HERE.parent/'persistent_cause').glob('*.py'))+list((HERE.parent/'memory_timescales').glob('*.py'))
    paths += list((HERE.parent/'body_recovery').glob('*.py'))+list((ROOT/'src/threemind_kernels').glob('*.py'))
    paths += [Path(s.__file__),Path(s.base.__file__)]
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    s.base.original(work/'frozen.json',{'sources':sources,'materials':materials,'native_sha256':s.sha(h.previous.native()),
        'cases_sha256':s.sha(work/'cases.json'),'systems':64,'independent_blocks':4,'originals_cap_bytes':CAP})
    for rel in sources:
        dst=work/'frozen-source'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dst)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r51t4:delayed-choice:20261114:v1','title':'R51t4：持续活动的决策作用与前缀区分',
            'classification':'formal','execution_status':'running','executor':'ai','kernels':['threemind.continuous-memory/6.1'],
            'protocol':(HERE/'decision_protocol.zh.md').read_text('utf8'),'protocol_version':s.sha(HERE/'decision_protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],'metadata':{'blocks':4,'systems':64,'campaign_paused':True}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R51t4 protocol '+lang,
                'markdown':(HERE/f'decision_protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True)
        result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)

def apparatus(work):
    check(work);assert not any((work/n).exists() for n in ('apparatus.json','in-flight.json','STOP'))
    c=deepcopy(d.table()[0]);c.update(seed=941199,key='apparatus',patch=d.PROFILES['short-inhibition'])
    hashes={};obs=[]
    with s.base.worker_lock(work),s.base.Guard(work):
        for mode in ('observed','dense','plain','restored','paused'):
            r,im,ob=x.execute(c,work/'apparatus'/mode,work,mode=mode,calibration=True);hashes[mode]=im.digest;obs.append(ob)
        assert len(set(hashes.values()))==1 and all(v==obs[0] for v in obs)
        ids,_=d.mapping(c['seed'])
        points=[{'time_us':t,'nodes':[{'channel':ids['C'],'activation':.2},{'channel':ids['E'],'activation':.1}]} for t in range(0,500001,50000)]
        answer=x.score(points,ids,500000,'C');assert answer['correct'] and abs(answer['margin_C_minus_E']-.05)<1e-12
        s.base.original(work/'apparatus.json',{'passed':True,'hashes':hashes,'same_observers':True,'synthetic_score':answer,'separate_encoding':True})
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True,'hashes':hashes}),flush=True)

def run(work):
    check(work);assert read(work/'apparatus.json')['passed'] and not any((work/n).exists() for n in ('summary.json','in-flight.json','STOP'))
    import psutil
    table=read(work/'cases.json');n=0;started=time.monotonic()
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for c in table:
            folder=work/'cases'/c['key']
            if (folder/'result.json').exists():
                r=read(folder/'result.json');assert e.base.image(folder/'final.tmind').digest==r['final_sha256'];n+=1;continue
            if (work/'STOP').exists():break
            if time.monotonic()-started>7200:
                s.base.original(work/'STOP',{'reason':'two-hour batch budget','complete':n});break
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            try:r,_,_=x.execute(c,folder,work)
            except x.SafePause:break
            n+=1;s.base.atomic_json(work/'current.json',{'complete':n,'total':len(table),'last':c['key'],'elapsed_seconds':time.monotonic()-started})
            assert e.support.allocated(work)<CAP,'originals budget exceeded at complete boundary'
            print(json.dumps({'complete':n,'key':c['key'],'seconds':r['wall_seconds']}),flush=True);gc.collect()
        if n==len(table):s.base.original(work/'summary.json',{'complete':n,'wall_seconds':time.monotonic()-started})
    print(json.dumps({'complete':n,'total':len(table)}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','check','apparatus','run'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
