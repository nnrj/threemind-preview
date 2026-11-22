"""Registered excitatory-threshold comparison using the isolated transmission implementation."""
import argparse
from copy import deepcopy
from dataclasses import replace
import gc
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid5
sys.path.insert(0,str(Path(__file__).parent))
import continuation_v2 as c
import research_transport as r
s=c.s
from threemind_core import StateImage,Stimulus

VARIANTS={'threshold-current': {'research_transport':'reference','activation_signal_threshold':0.004},
          'threshold-old-inhibition': {'research_transport':'old-inhibition','activation_signal_threshold':0.004}}

def put(path,image):s.packed(path,image.to_dict())
def get(path):return StateImage.from_dict(s.unpack(path))

def create(mode,case,state=None):
    if state is not None:return r.ResearchEngine(state=state)
    return r.ResearchEngine(r.ResearchConfig(seed=9291000,**(case['initial_config']|s.STABLE),**VARIANTS[mode]))

def scientific(d):
    d=deepcopy(d)
    for k in ('schema','dynamics','definition','definition_hash'):d.pop(k)
    d['config'].pop('research_transport',None)
    return d

def apparatus(work):
    c.check(work);assert (work/'summary.json').exists() and not (work/'in-flight.json').exists()
    folder=work/'threshold';folder.mkdir(exist_ok=False)
    case=deepcopy(s.read(work/'cases.json')['short/train-0']);case['end_us']=10_000_000
    rows=[x for x in s.inputs(work,case,True) if int(x['source_policy']['resolved_at_us'])<=case['end_us']]
    results=[];began=time.monotonic()
    def drive(e,step=100000,restore=False,observe=False):
        i=0;restored=False
        while True:
            while i<len(rows) and int(rows[i]['source_policy']['resolved_at_us'])==e.time_us:
                e.inject(Stimulus.from_dict(rows[i]['stimulus']));i+=1
            e.advance_to(e.time_us)
            if observe:
                before=e.capture_state().digest;e.observation_nodes();e.capture_state();assert e.capture_state().digest==before
            if restore and not restored and e.time_us>=2_000_000:
                before=e.capture_state();e=r.ResearchEngine(state=StateImage.from_dict(before.to_dict()))
                assert e.capture_state().digest==before.digest;restored=True
            if e.time_us==case['end_us']:break
            targets=[case['end_us'],e.time_us+step]
            if i<len(rows):targets.append(int(rows[i]['source_policy']['resolved_at_us']))
            e.advance_to(min(targets))
        return e.capture_state()
    with s.base.worker_lock(work),s.base.Guard(work):
        cfg={'seed':9291199,**case['initial_config'],**s.STABLE}
        prod=drive(r.production.Local62Engine(r.Local62Config(**cfg)))
        for mode in ('reference',)+tuple(VARIANTS):
            hashes={}
            for label,step,restore,observe in [('plain',100000,False,False),('observed',100000,False,True),('restored',100000,True,False),('partitioned',37000,False,False)]:
                state=drive(r.ResearchEngine(r.ResearchConfig(**cfg,**VARIANTS.get(mode,{'research_transport':mode}))),step,restore,observe)
                hashes[label]=state.digest
                if mode=='reference':assert scientific(state.to_dict())==scientific(prod.to_dict())
            assert len(set(hashes.values()))==1,(mode,hashes)
            results.append({'mode':mode,'hashes':hashes})
    s.write(folder/'apparatus.json',{'passed':True,'separate_encoding':True,'checks':results,'wall_seconds':time.monotonic()-began})
    print(json.dumps({'apparatus':True,'seconds':time.monotonic()-began}),flush=True)

def register(work):
    c.check(work);folder=work/'threshold'
    assert s.read(folder/'apparatus.json')['passed'] and not (folder/'frozen.json').exists()
    paths=[Path(__file__),Path(r.__file__),s.HERE/'threshold-supplement.zh.md',s.HERE/'threshold-supplement.en.md']
    sources={str(p.relative_to(s.ROOT)):s.sha(p) for p in paths}
    for rel in sources:
        dst=folder/'frozen-source'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s.ROOT/rel,dst)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(s.NS,'threshold-doc-'+lang)),'request_id':str(uuid5(s.NS,'threshold-register-'+lang)),'expected_revision':0,
                      'kind':'protocol','title':'R51t7 threshold supplement '+lang,'markdown':(s.HERE/f'threshold-supplement.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True);assert rec.status['pending']==0
    s.write(folder/'frozen.json',{'sources':sources,'variants':VARIANTS,'stages':12,'registered_before_scientific_run':True})

def check(work):
    c.check(work);f=s.read(work/'threshold/frozen.json')
    for rel,h in f['sources'].items():assert s.sha(s.ROOT/rel)==h,rel
    assert s.read(work/'threshold/apparatus.json')['passed']

def run(work):
    check(work);folder=work/'threshold'
    assert not any((work/p).exists() for p in ('in-flight.json','STOP'))
    assert not (folder/'summary.json').exists()
    import psutil
    index=s.read(work/'cases.json');results=[];began=time.monotonic()
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.write(folder/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for variant in VARIANTS:
            for block in (0,1):
                for cue in ('train','AB','DB'):
                    if (work/'STOP').exists():return
                    assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
                    assert time.monotonic()-began<7200
                    key=f'{variant}/{block}/{cue}';out=folder/'cases'/key;out.mkdir(parents=True,exist_ok=False)
                    s.write(work/'in-flight.json',{'phase':'threshold','key':key,'pid':os.getpid(),'created':psutil.Process().create_time()})
                    case=index[f'short/train-{block}' if cue=='train' else f'history/s{block}/101/d1/{cue}']
                    parent=None if cue=='train' else get(folder/'cases'/variant/str(block)/'train/final.rstate.gz')
                    e=create(variant,case,parent)
                    if parent is not None:e.reconfigure(replace(e.config,**case['patch']))
                    initial=e.capture_state();put(out/'initial.rstate.gz',initial)
                    trace=c.Trace(out/'teaching.jsonl.gz') if cue=='train' else None;t=time.monotonic()
                    points=c.execute(e,case,s.inputs(work,case),trace)
                    if trace:trace.close()
                    final=e.capture_state();put(out/'final.rstate.gz',final)
                    assert get(out/'final.rstate.gz').digest==final.digest
                    if cue!='train':s.packed(out/'process.json.gz',points)
                    q={} if cue=='train' else s.measure.process(case,points)
                    q.update(key=key,variant=variant,block=block,cue=cue,kernel=r.KERNEL_ID,
                             initial_sha256=initial.digest,final_sha256=final.digest,parent_sha256=parent.digest if parent else None,
                             time_us=e.time_us,wall_seconds=time.monotonic()-t)
                    s.write(out/'result.json',q);results.append(q)
                    s.base.atomic_json(folder/'current.json',{'complete':len(results),'total':12,'last':key})
                    (work/'in-flight.json').unlink()
                    print(json.dumps({'complete':len(results),'key':key,'margin':q.get('signed_peak'),'seconds':q['wall_seconds']}),flush=True)
                    del e,points;gc.collect()
                assert sum(p.stat().st_size for p in work.rglob('*') if p.is_file())<2**30
        s.write(folder/'summary.json',{'stages':len(results),'results':results,'wall_seconds':time.monotonic()-began})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('apparatus','register','check','run'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
