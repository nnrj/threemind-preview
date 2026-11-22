"""Registered, bounded novelty-timing contrast; existing birth configuration only."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid5
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import supplement as q
h=q.h;s=h.s;e=h.e

def check(work):
    q.check(work)
    f=h.read(work/'novelty-frozen.json')
    for name,digest in f['sources'].items():assert s.sha(HERE/name)==digest
    assert s.sha(work/'novelty-cases.json')==f['cases_sha256']
    assert h.read(work/'novelty-registration.json')['pending']==0

def register(work):
    q.check(work);assert not (work/'novelty-frozen.json').exists()
    base=[c for c in h.read(work/'cases.json') if c['variant']=='v2' and ('/short/train-' in c['key'] or '/history/' in c['key'])]
    cases=[]
    for name,version in [('v2-immediate','2'),('v61-immediate','6.1')]:
        for c in base:
            d=dict(c,key=name+'/'+c['material_key'],variant=name,version=version,birth_patch={'novelty_mode':'immediate'},
                   parent=(name+'/'+c['parent'].split('/',1)[1]) if c['parent'] else None)
            e.base.resolve_kernel('threemind.continuous-memory/'+version).configuration({'seed':e.materials.SEED,**d['initial_config'],**d['birth_patch']})
            cases.append(d)
    assert len(cases)==12
    s.base.original(work/'novelty-cases.json',cases)
    files=[HERE/'novelty_followup.py',HERE/'analyze_novelty.py',HERE/'novelty-followup.zh.md',HERE/'novelty-followup.en.md']
    s.base.original(work/'novelty-frozen.json',{'sources':{p.name:s.sha(p) for p in files},'cases_sha256':s.sha(work/'novelty-cases.json'),
        'registered_after_initial_version_observations':True,'stages':12})
    for p in files:
        dst=work/'novelty-source'/p.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(p,dst)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(h.NS,'novelty-protocol-'+lang)),'request_id':str(uuid5(h.NS,'novelty-registration-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R51t1 novelty timing follow-up '+lang,
                'markdown':(HERE/f'novelty-followup.{lang}.md').read_text('utf8')})
        rec.append('protocol','r51t1:novelty-timing',{'stages':12,'cases_sha256':s.sha(work/'novelty-cases.json')},request_id=uuid5(h.NS,'novelty-cases'))
        rec.synchronize(strict=True)
        result={'record':rec.experiment,'pending':rec.status['pending'],'stages':12}
        s.base.original(work/'novelty-registration.json',result);print(json.dumps(result))

def apparatus(work):
    check(work);assert h.read(work/'audit.json')['passed']
    assert not any((work/x).exists() for x in ('in-flight.json','STOP','novelty-apparatus.json'))
    import psutil
    cs={c['key']:c for c in h.read(work/'novelty-cases.json')};checks=[]
    shutil.copyfile(work/'resource-summary.json',work/'supplement-resources.json')
    with s.base.worker_lock(work),s.base.Guard(work):
        s.base.original(work/'in-flight.json',{'phase':'novelty-apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
        for key in ('v2-immediate/short/train-0','v2-immediate/history/s0/101/d1/AB'):
            c=cs[key];src=work/'novelty-apparatus/main'/c['parent'] if c['parent'] else None
            _,state,observer=h.execute(c,work/'novelty-apparatus/main'/key,work,src,calibration=True)
            if c['kind']=='probe':
                hashes={'observed':state.digest}
                for mode in ('plain','restored'):
                    _,other,ob=h.execute(c,work/'novelty-apparatus'/mode/key,work,src,mode=mode,calibration=True)
                    assert observer==ob;hashes[mode]=other.digest
                assert len(set(hashes.values()))==1;checks.append(hashes)
        s.base.original(work/'novelty-apparatus.json',{'passed':True,'checks':checks});(work/'in-flight.json').unlink()
    shutil.copyfile(work/'resource-summary.json',work/'novelty-apparatus-resources.json')

def run(work):
    check(work);assert h.read(work/'novelty-apparatus.json')['passed']
    assert not any((work/x).exists() for x in ('in-flight.json','STOP','novelty-summary.json'))
    import psutil
    began=time.monotonic()
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.original(work/'novelty-host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        completed=0
        for c in h.read(work/'novelty-cases.json'):
            if (work/'STOP').exists():break
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            folder=work/'cases'/c['key'];assert not folder.exists()
            s.base.original(work/'in-flight.json',{'key':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            src=work/'cases'/c['parent'] if c['parent'] else None
            r,_,_=h.execute(c,folder,work,src);completed+=1
            (work/'in-flight.json').unlink();assert e.support.allocated(work)<h.CAP
            s.base.atomic_json(work/'novelty-current.json',{'complete':completed,'total':12,'last':c['key']})
            print(json.dumps({'novelty':completed,'key':c['key'],'seconds':r['wall_seconds']}),flush=True);gc.collect()
        if completed==12:s.base.original(work/'novelty-summary.json',{'complete':12,'wall_seconds':time.monotonic()-began})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run'));p.add_argument('--work',required=True,type=Path)
    a=p.parse_args();globals()[a.action](a.work)
