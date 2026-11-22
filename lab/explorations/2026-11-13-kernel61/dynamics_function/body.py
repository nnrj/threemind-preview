"""R51t3 registered causal copies and external MuJoCo actuator; no Core edits."""
import argparse
from collections import deque
from copy import deepcopy
from dataclasses import replace
import gc
import gzip
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import mechanism as shared
s=shared.s;e=shared.e;ROOT=shared.ROOT
from threemind_core import Stimulus
from threemind_runtime import ArtifactCodec
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.world import PhysicalWorld
from threemind_runtime.world_schema import Motor,parse_world
from threemind_runtime.world_templates import physical_templates
from threemind_runtime.adapters import channel_id

NS=UUID('8b3ac285-0e04-414d-95a6-a32e4cb06698')
SEEDS=(930101,930102,930103,930104)
MODES=('full','no_imu','dose_matched','shuffled_imu','untrained')
FIELDS=('activation','inhibition','direct','associative')
PERIOD=20000;DURATION=8000000;LIMIT=2.
read=s.base.read

def prior(work):return work.parent/'inertial-reversal61-v1'

def mapping(seed):
    mask=channel_id(seed,'world-port-v1:physical-world-v1',0)
    return {name:((4000<<20)|i)^mask for i,name in enumerate(('A','B','C','X','Y','keep'))}

def table():
    rows=[]
    for seed in SEEDS:
        for mode in MODES:
            for threshold in (.0004,.004):
                for sign in (0,1,-1):rows.append({'kind':'static','seed':seed,'mode':mode,'threshold':threshold,'sign':sign})
                for polarity in (1,-1):
                    for sign in (1,-1):rows.append({'kind':'body','seed':seed,'mode':mode,'threshold':threshold,'sign':sign,'polarity':polarity,'controller':'core'})
        for controller in ('zero','pd'):
            for sign in (1,-1):rows.append({'kind':'body','seed':seed,'mode':'full','threshold':.0004,'sign':sign,'polarity':1,'controller':controller})
    for i,c in enumerate(rows):c['key']=f'{i:04d}-'+c['kind']
    assert len(rows)==296
    return rows

def parent_dir(work,c):return work/'references'/f"v61-{c['seed']}-ordinary-{c['mode']}"

def engine(image):return e.base.resolve_kernel('threemind.continuous-memory/6.1').create(state=image,backend='native')

def save(path,image):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=ArtifactCodec.encode(image);assert ArtifactCodec.decode(raw).digest==image.digest
    return s.blob(path,raw)

def frame_nodes(core):
    return {'time_us':core.time_us,'nodes':core.observation_nodes()}

def begin(work,c,folder,calibration=False):
    initial=e.base.image(parent_dir(work,c)/'final.tmind')
    core=engine(initial);assert core.capture_state().digest==initial.digest
    folder.mkdir(parents=True,exist_ok=False);save(folder/'initial.tmind',initial)
    core.reconfigure(replace(core.config,signal_threshold=c['threshold']))
    changed=core.capture_state();save(folder/'intervened.tmind',changed)
    s.base.original(folder/'intervention.json',{'clock_us':core.time_us,'patch':{'signal_threshold':c['threshold']},
        'same_time':int(initial.to_dict()['time_us'])==core.time_us,
        'changes':e.support.x.differences(initial.to_dict(),changed.to_dict())})
    delivered=[];events=[]
    def sink(event,row):
        if row:delivered.append(row)
    ob=read(parent_dir(work,c)/'observer.json')
    session=ReadoutSession(core,state=deepcopy(ob),record=events.append,event_sink=sink)
    e.packed(folder/'initial-observer.json.xz',ob)
    return core,session,initial,changed,delivered,events

def finish(c,folder,core,session,initial,changed,points,inputs,delivered,events,began,extra=None):
    assert session.bus.pending_count()==0 and len(delivered)==len(inputs)
    assert core.life=='active'
    final=core.capture_state();save(folder/'final.tmind',final)
    e.packed(folder/'observer.json.xz',session.capture())
    e.packed(folder/'trajectory.json.xz',points)
    e.packed(folder/'inputs.json.xz',inputs);e.packed(folder/'delivered.json.xz',delivered)
    e.packed(folder/'events.json.xz',events)
    result={**c,'status':'complete','initial_sha256':initial.digest,'intervened_sha256':changed.digest,
        'final_sha256':final.digest,'begin_us':int(initial.to_dict()['time_us']),'end_us':core.time_us,
        'kernel':final.to_dict()['dynamics'],'inputs':len(inputs),'points':len(points),
        'wall_seconds':time.monotonic()-began,**(extra or {})}
    s.base.original(folder/'result.json',result)
    return result

def static(work,c,folder):
    began=time.monotonic();core,session,initial,changed,delivered,events=begin(work,c,folder)
    rows=read(parent_dir(work,c)/f"probe-{c['sign']}.json")['frames'];index=0;points=[];inputs=[]
    start=core.time_us;end=start+5600000
    while True:
        while index<len(rows) and rows[index]['enqueue_us']==core.time_us:
            row=rows[index]
            session.schedule([{'stimulus':Stimulus.from_dict(row['stimulus'])}],source=row['source'],
                adapter_id='r51t3-frozen-body-probe',at=0,envelope_id=uuid5(NS,c['key']+':'+str(index)))
            inputs.append(row);index+=1
        if (core.time_us-start)%100000==0:points.append(frame_nodes(core))
        if core.time_us==end:break
        nxt=min(end,((core.time_us-start)//100000+1)*100000+start,rows[index]['enqueue_us'] if index<len(rows) else end)
        assert nxt>core.time_us
        session.advance_to(nxt);assert core.life=='active' and time.monotonic()-began<300
    return finish(c,folder,core,session,initial,changed,points,inputs,delivered,events,began)

class ActuatedWorld(PhysicalWorld):
    """External research actuator: accepts an already chosen torque, never an answer."""
    requested=0.
    def _control(self,activations):
        command=max(-LIMIT,min(LIMIT,float(self.requested)))
        self.data.actuator('a_motor').ctrl[0]=command
        self.last_controls=[{'id':'motor','control':command}]

def world_spec(sign):
    raw=physical_templates()['gravity-pendulum'].model_dump(mode='json')
    raw['joints'][0]['initial']=sign*.7
    raw['motors']=[Motor(id='motor',port=0,joint_id='hinge',control_limit=LIMIT).model_dump(mode='json')]
    return parse_world(raw)

def sensory(unit,mode,seed,rng):
    unit=deepcopy(unit);unit['intensity']=.3
    mask=channel_id(seed,'world-port-v1:physical-world-v1',0)
    imu={((port<<20)|i)^mask for port in (0,1) for i in range(6)}
    elements=unit['elements'];joint=sum(x['value'] for x in elements if x['channel'] not in imu);total=sum(x['value'] for x in elements)
    if mode=='no_imu':elements=[x for x in elements if x['channel'] not in imu]
    elif mode=='dose_matched':elements=[dict(x,value=x['value']*joint/total) for x in elements] if total else elements
    elif mode=='shuffled_imu':
        ids=sorted(imu);values=[next((x['value'] for x in elements if x['channel']==ch),0.) for ch in ids];rng.shuffle(values)
        elements=[x for x in elements if x['channel'] not in imu]+[{'channel':ch,'value':v} for ch,v in zip(ids,values) if v]
    unit['elements']=sorted(elements,key=lambda x:x['channel'])
    return unit

def integral(window):
    return math.fsum((b[0]-a[0])*(a[1]+b[1])/2e6 for a,b in zip(window,list(window)[1:]))

def body(work,c,folder,*,restore=False,extra_observe=False,pause=False):
    began=time.monotonic();core,session,initial,changed,delivered,events=begin(work,c,folder)
    start=core.time_us;ids=mapping(c['seed']);rng=random.Random(f"r51t3:{c['seed']}:{c['sign']}")
    window=deque();points=[];inputs=[];spec=world_spec(c['sign']);world=ActuatedWorld(spec,c['seed'])
    def whole():
        return {'core_sha256':core.capture_state().digest,'observer':session.capture(),'body':world.capture(),
            'requested':world.requested,'window':list(window),'rng':rng.getstate(),'elapsed_core_us':core.time_us-start}
    e.packed(folder/'body-initial.json.xz',whole())
    def queue(stim,source):
        session.schedule([{'stimulus':stim}],source=source,adapter_id='r51t3-closed-body',at=0,
            envelope_id=uuid5(NS,c['key']+':'+str(len(inputs))))
        inputs.append({'enqueue_us':core.time_us,'source':source,'stimulus':stim.to_dict()})
    try:
        for local in range(0,DURATION,PERIOD):
            assert core.time_us==start+local and world.elapsed_us==local
            nodes=core.observation_nodes();vals={n['channel']:n for n in nodes}
            a=vals.get(ids['A'],{}).get('activation',0.);b=vals.get(ids['B'],{}).get('activation',0.)
            window.append((core.time_us,a-b))
            while window and window[0][0]<core.time_us-500000:window.popleft()
            area=integral(window);choice=1 if area>1e-6 else -1 if area< -1e-6 else 0
            q=float(world.data.joint('j_hinge').qpos[0]);v=float(world.data.joint('j_hinge').qvel[0])
            request=LIMIT*choice*c['polarity'] if c['controller']=='core' else max(-LIMIT,min(LIMIT,-3*q-v)) if c['controller']=='pd' else 0.
            world.requested=request
            world.data.qfrc_applied[:]=c['sign']*.5 if 4000000<=local<4200000 else 0.
            if extra_observe:
                before=whole();core.graph();world.observation();assert whole()==before
            points.append({'time_us':core.time_us,'local_us':local,'nodes':nodes,'q':q,'velocity':v,
                'command':request,'choice':choice,'process_area':area,'body':world.capture()})
            if local%500000==0:queue(Stimulus(core.time_us,((ids['keep'],1.),),.2),'registered-background')
            physical=world.sample(core.time_us)
            unit=sensory(world.stimulus_unit(physical,capture_us=world.elapsed_us),c['mode'],c['seed'],rng)
            stim=Stimulus(int(unit['time_us']),tuple((x['channel'],x['value']) for x in unit['elements']),unit['intensity'])
            assert not {ids['A'],ids['B']} & {ch for ch,_ in stim.channels}
            queue(stim,'closed-loop-body')
            session.advance_to(start+local+10000)
            points.append({'time_us':core.time_us,'local_us':local+10000,'nodes':core.observation_nodes(),'intermediate':True})
            session.advance_to(start+local+PERIOD)
            assert core.life=='active' and time.monotonic()-began<300
            if local+PERIOD==4000000 and (restore or pause):
                oldwhole=whole();image=ArtifactCodec.decode(ArtifactCodec.encode(core.capture_state()))
                if pause:time.sleep(.01)
                if restore:
                    body_state=world.capture();world.close();world=ActuatedWorld(spec,c['seed'],state=body_state);world.requested=oldwhole['requested']
                    core=engine(image);session=ReadoutSession(core,state=oldwhole['observer'],record=events.append,
                        event_sink=lambda event,row:delivered.append(row) if row else None)
                    window=deque(oldwhole['window']);rng.setstate(oldwhole['rng'])
                assert whole()==oldwhole
        points.append({'time_us':core.time_us,'local_us':DURATION,'nodes':core.observation_nodes(),
            'q':float(world.data.joint('j_hinge').qpos[0]),'velocity':float(world.data.joint('j_hinge').qvel[0]),
            'command':world.requested,'body':world.capture()})
        e.packed(folder/'body-final.json.xz',whole())
    finally:world.close()
    return finish(c,folder,core,session,initial,changed,points,inputs,delivered,events,began,
        {'observer_test':{'restore':restore,'extra_observe':extra_observe,'pause':pause}})

def check(work):
    f=read(work/'frozen.json')
    for rel,digest in f['sources'].items():assert s.sha(ROOT/rel)==digest,rel
    for rel,digest in f['references'].items():assert s.sha(work/rel)==digest,rel
    assert s.sha(shared.previous.native())==f['native_sha256']
    assert s.sha(work/'cases.json')==f['cases_sha256'] and read(work/'registration.json')['pending']==0

def register(work):
    assert not work.exists();assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>31*2**30
    done=read(prior(work)/'publication/completion.json');assert done['coverage']=='verified' and done['pending']==0
    work.mkdir();refs={};rows=table();s.base.original(work/'cases.json',rows)
    for seed in SEEDS:
        for mode in MODES:
            key=f'v61-{seed}-ordinary-{mode}';dest=work/'references'/key;dest.mkdir(parents=True)
            src=prior(work)/'subjects'/key
            files={name:src/'wait1'/name for name in ('final.tmind','observer.json','result.json')}
            files.update({f'probe-{sign}.json':src/f'intact-{sign}'/'input.json' for sign in (0,1,-1)})
            for name,p in files.items():
                shutil.copyfile(p,dest/name);assert s.sha(p)==s.sha(dest/name)
                refs[(dest/name).relative_to(work).as_posix()]=s.sha(dest/name)
    paths=[HERE/n for n in ('body.py','body_analysis.py','body_protocol.zh.md','body_protocol.en.md')]
    paths+=[Path(shared.__file__),Path(e.__file__),Path(s.__file__),Path(s.base.__file__)]
    paths+=list((ROOT/'src/threemind_kernels').glob('*.py'))
    paths+=[ROOT/'src/threemind_runtime'/n for n in ('world.py','world_ports.py','world_schema.py','world_templates.py','readout_session.py')]
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    s.base.original(work/'frozen.json',{'sources':sources,'references':refs,'cases_sha256':s.sha(work/'cases.json'),
        'native_sha256':s.sha(shared.previous.native()),'stages':296,'material_blocks':4,'originals_cap_bytes':2*2**30})
    for rel in sources:
        p=work/'frozen-source'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r51t3:closed-body:20261114:v1','title':'R51t3：同一经历下的响应翻转与闭环身体作用',
            'classification':'formal','execution_status':'running','executor':'ai','kernels':['threemind.continuous-memory/6.1'],
            'protocol':(HERE/'body_protocol.zh.md').read_text('utf8'),'protocol_version':s.sha(HERE/'body_protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],'metadata':{'material_blocks':4,'stages':296,'campaign_paused':True}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
            'expected_revision':0,'kind':'protocol','title':'R51t3 '+lang,'markdown':(HERE/f'body_protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True);result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)

def apparatus(work):
    check(work);assert not any((work/x).exists() for x in ('in-flight.json','STOP','apparatus.json'))
    # A separately born coding source, never one of the four scientific parents.
    seed=930198;c={'kind':'body','seed':seed,'mode':'full','threshold':.0004,'sign':1,'polarity':1,'controller':'core','key':'apparatus'}
    p=parent_dir(work,c);p.mkdir(parents=True)
    core=e.base.resolve_kernel('threemind.continuous-memory/6.1').create({'seed':seed},backend='native')
    ids=mapping(seed);session=ReadoutSession(core,record=lambda _:None)
    for t in range(0,1000000,100000):session.schedule([{'stimulus':Stimulus(t,((ids['A'],.4),(ids['keep'],.2)),.3)}],at=0)
    session.advance_to(1000000);save(p/'final.tmind',core.capture_state());s.base.original(p/'observer.json',session.capture())
    checks={};whole=[]
    with s.base.worker_lock(work),s.base.Guard(work):
        for name,kwargs in [('plain',{}),('observed',{'extra_observe':True}),('restored',{'restore':True}),('paused',{'pause':True})]:
            folder=work/'apparatus'/name;r=body(work,c,folder,**kwargs);checks[name]=r['final_sha256'];whole.append(e.unpacked(folder/'body-final.json.xz'))
            print('body apparatus',name,flush=True)
        assert len(set(checks.values()))==1 and all(x==whole[0] for x in whole)
        s.base.original(work/'apparatus.json',{'passed':True,'separate_seed':seed,'complete_hashes':checks,'whole_states_equal':True})
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')

def run(work):
    check(work);assert read(work/'apparatus.json')['passed']
    assert not any((work/x).exists() for x in ('summary.json','in-flight.json','STOP'))
    import psutil
    started=time.monotonic();n=0
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for c in read(work/'cases.json'):
            if (work/'STOP').exists():break
            folder=work/'cases'/c['key']
            if folder.exists():
                r=read(folder/'result.json');assert r['status']=='complete' and e.base.image(folder/'final.tmind').digest==r['final_sha256'];n+=1;continue
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            s.base.original(work/'in-flight.json',{'key':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            r=static(work,c,folder) if c['kind']=='static' else body(work,c,folder);n+=1
            (work/'in-flight.json').unlink();assert e.support.allocated(work)<2*2**30
            s.base.atomic_json(work/'current.json',{'complete':n,'total':296,'last':c['key'],'elapsed_seconds':time.monotonic()-started})
            print(json.dumps({'complete':n,'key':c['key'],'seconds':r['wall_seconds']}),flush=True);gc.collect()
        if n==296:s.base.original(work/'summary.json',{'complete':n,'wall_seconds':time.monotonic()-started})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run','check'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
