"""Sixteen declared post-teaching copies; complete parents remain immutable."""
import argparse
from copy import deepcopy
from dataclasses import replace
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import uuid5
sys.path.insert(0,str(Path(__file__).parent))
import run_transport as rt
import run_threshold as rh
s=rt.s;c=rt.c;r=rt.r
TYPES=('failed-with-success-config','success-with-failed-config','failed-with-success-weights','success-with-failed-weights')

def differences(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        return sum((differences(a.get(k),b.get(k),path+'/'+str(k)) for k in sorted(set(a)|set(b))),[])
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
        return sum((differences(x,y,path+'/'+str(i)) for i,(x,y) in enumerate(zip(a,b))),[])
    return [] if a==b else [{'path':path,'before':a,'after':b}]

def prepare(work):
    rt.check(work);rh.check(work)
    assert not any((work/p).exists() for p in ('STOP','in-flight.json'))
    t=s.read(work/'threshold/summary.json')['results']
    higher=[x for x in t if x['variant']=='threshold-old-inhibition' and x['cue']!='train']
    assert len(higher)==4
    positive='threshold/cases/threshold-old-inhibition' if all(x['signed_peak']>1e-6 for x in higher) else 'transport/cases/old-emission'
    negative='transport/cases/old-inhibition'
    folder=work/'exchanges';folder.mkdir(exist_ok=False)
    cases=[]
    for block in (0,1):
        parents={name:root+f'/{block}/train/final.rstate.gz' for name,root in (('success',positive),('failed',negative))}
        images={k:rt.get(work/v) for k,v in parents.items()}
        task=set(s.measure.TOKENS.values())
        selected={k:{(e['source'],e['target']) for e in v.to_dict()['edges'] if e['source'] in task and e['target'] in task} for k,v in images.items()}
        assert selected['success']==selected['failed'] and len(selected['success'])==8
        cfgdiff=differences(images['success'].to_dict()['config'],images['failed'].to_dict()['config'])
        assert all(x['path'] in ('/research_transport','/activation_signal_threshold') for x in cfgdiff)
        for name in TYPES:
            recipient,donor=('failed','success') if name.startswith('failed') else ('success','failed')
            for cue in ('AB','DB'):
                cases.append({'key':f'{name}/{block}/{cue}','variant':name,'block':block,'cue':cue,
                              'parent_file':parents[recipient],'donor_file':parents[donor],'kind':'weights' if name.endswith('weights') else 'config'})
    s.write(folder/'cases.json',cases)
    sources={str(p.relative_to(s.ROOT)):s.sha(p) for p in (Path(__file__),s.HERE/'exchange-supplement.zh.md',s.HERE/'exchange-supplement.en.md')}
    for rel in sources:
        out=folder/'frozen-source'/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s.ROOT/rel,out)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(s.NS,'exchange-doc-'+lang)),'request_id':str(uuid5(s.NS,'exchange-register-'+lang)),
                      'expected_revision':0,'kind':'protocol','title':'R51t7 post-teaching exchanges '+lang,'markdown':(s.HERE/f'exchange-supplement.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True);assert rec.status['pending']==0
    s.write(folder/'frozen.json',{'sources':sources,'cases_sha256':s.sha(folder/'cases.json'),'stages':16,'positive':positive,'negative':negative,'task_edges':8})
    print(json.dumps({'positive':positive,'negative':negative,'stages':16}),flush=True)

def check(work):
    rt.check(work);rh.check(work);f=s.read(work/'exchanges/frozen.json')
    for rel,h in f['sources'].items():assert s.sha(s.ROOT/rel)==h,rel
    assert s.sha(work/'exchanges/cases.json')==f['cases_sha256']

def run(work):
    check(work);folder=work/'exchanges';assert not (folder/'summary.json').exists()
    assert not any((work/p).exists() for p in ('STOP','in-flight.json'))
    index=s.read(work/'cases.json');results=[];began=time.monotonic();import psutil
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.write(folder/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for spec in s.read(folder/'cases.json'):
            if (work/'STOP').exists():return
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            out=folder/'cases'/spec['key'];out.mkdir(parents=True,exist_ok=False)
            s.write(work/'in-flight.json',{'phase':'exchanges','key':spec['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            parent=rt.get(work/spec['parent_file']);donor=rt.get(work/spec['donor_file'])
            e=r.ResearchEngine(state=parent);d=r.ResearchEngine(state=donor)
            case=index[f'history/s{spec["block"]}/101/d1/{spec["cue"]}']
            e.reconfigure(replace(e.config,**case['patch']))
            before=e.capture_state();selected=[]
            if spec['kind']=='config':
                changes={k:getattr(d.config,k) for k in ('research_transport','activation_signal_threshold')}
                e.reconfigure(replace(e.config,**changes))
            else:
                task=set(s.measure.TOKENS.values())
                selected=sorted(k for k in e.edges if k[0] in task and k[1] in task)
                assert len(selected)==8
                for key in selected:
                    assert key in d.edges and int(e.edges[key].state_us)==int(d.edges[key].state_us)==e.time_us
                    assert e.edges[key].weight>=e.config.prune_weight and d.edges[key].weight>=e.config.prune_weight
                    e.edges[key].weight=d.edges[key].weight;e._edge_timer(e.edges[key])
            initial=e.capture_state();diff=differences(before.to_dict(),initial.to_dict())
            if spec['kind']=='weights':
                assert all(x['path'].startswith('/edges/') and x['path'].endswith('/weight') for x in diff),diff
            else:
                assert all(x['path'].startswith(('/config/','/definition/','/audit/')) or x['path']=='/definition_hash' for x in diff),diff
            assert e.time_us==int(parent.to_dict()['time_us'])==int(donor.to_dict()['time_us'])
            rt.put(out/'before-intervention.rstate.gz',before);rt.put(out/'initial.rstate.gz',initial)
            s.write(out/'intervention.json',{'parent':parent.digest,'donor':donor.digest,'before':before.digest,'after':initial.digest,
                    'time_advanced_us':0,'task_connections':selected,'changes':diff})
            t=time.monotonic();points=c.execute(e,case,s.inputs(work,case))
            final=e.capture_state();rt.put(out/'final.rstate.gz',final);assert rt.get(out/'final.rstate.gz').digest==final.digest
            s.packed(out/'process.json.gz',points)
            q=s.measure.process(case,points);q.update(spec,kernel=r.KERNEL_ID,parent_sha256=parent.digest,initial_sha256=initial.digest,
                final_sha256=final.digest,time_us=e.time_us,wall_seconds=time.monotonic()-t)
            s.write(out/'result.json',q);results.append(q)
            s.base.atomic_json(folder/'current.json',{'complete':len(results),'total':16,'last':spec['key']})
            (work/'in-flight.json').unlink()
            print(json.dumps({'complete':len(results),'key':spec['key'],'margin':q['signed_peak']}),flush=True)
            del e,d,points;gc.collect()
        s.write(folder/'summary.json',{'stages':len(results),'results':results,'wall_seconds':time.monotonic()-began})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','check','run'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
