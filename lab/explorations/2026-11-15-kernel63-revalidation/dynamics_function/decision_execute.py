"""Continuous R63t4 subjects, fixed process readout, declared teacher feedback."""
from copy import deepcopy
import json
import math
from pathlib import Path
import time
from uuid import UUID,uuid5
import sys
import os
import psutil

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import mechanism as shared
import decision_design as d
e=shared.e;s=shared.s
NS=UUID('12e184b3-81a2-56d7-9fb8-57c45081d42f')
READERS={'structural_readout':{'enabled':False},'temporal_readout':{'enabled':False}}

class SafePause(Exception):pass

def selected(core,ids):
    return {'time_us':core.time_us,'nodes':[{'channel':n['channel'],**{f:n.get(f,0.) for f in d.FIELDS}}
        for n in core.observation_nodes() if n['channel'] in ids]}

def score(points,ids,end,expected):
    rr=[p for p in points if end-500000<=p['time_us']<=end]
    assert rr[0]['time_us']==end-500000 and rr[-1]['time_us']==end and len(rr)>=11
    sums={}
    for name in ('C','E'):
        sums[name]=math.fsum((next((n['activation'] for n in a['nodes'] if n['channel']==ids[name]),0.)+
            next((n['activation'] for n in b['nodes'] if n['channel']==ids[name]),0.))*.5*(b['time_us']-a['time_us'])/1e6
            for a,b in zip(rr,rr[1:]))
    delta=sums['C']-sums['E'];choice=('C' if delta>0 else 'E') if abs(delta)>1e-6 else 'WAIT'
    return {'areas':sums,'margin_C_minus_E':delta,'choice':choice,'expected':expected,'correct':choice==expected}

def execute(c,folder,work,*,mode='observed',calibration=False):
    started=time.monotonic();seed=c['seed'];ids,mask=d.mapping(seed)
    cfg={'seed':seed,'depletion_enabled':c['task']=='prefix','stp_facilitation_tau_s':1. if c['task']=='pair' else 0.,
        'edge_consolidation_enabled':True,**c['patch']}
    make=lambda image=None:e.base.resolve_kernel('threemind.continuous-memory/6.3').create(None if image else cfg,image,backend='native')
    assert not folder.exists(), 'Existing subject requires independent complete-boundary review'
    core=make();folder.mkdir(parents=True)
    if not (folder/'initial.tmind').exists():e.storage.save(folder/'initial.tmind',core.capture_state())
    assert e.base.image(folder/'initial.tmind').digest==core.capture_state().digest
    deliveries=[];events=[]
    def sink(event,row):
        if row:deliveries.append(row)
    session=e.base.ReadoutSession(core,config=READERS,record=events.append,event_sink=sink)
    recent=[];records=[];once=False
    def guard():
        if time.monotonic()-started>300:raise RuntimeError('complete subject wall budget; preserve current in-flight')
    def phase(name,rows,duration,question=None):
        nonlocal core,session,recent,once
        target=folder/name;begin=core.time_us;end=begin+duration
        if (target/'result.json').exists():
            r=s.base.read(target/'result.json');assert r['begin_us']==begin and r['status']=='complete'
            im=e.base.image(target/'final.tmind');assert im.digest==r['final_sha256']
            core=make(im);session=e.base.ReadoutSession(core,state=e.unpacked(target/'observer.json.xz'),record=events.append,event_sink=sink)
            recent=e.unpacked(target/'recent.json.xz');records.append(r);return r
        if (work/'STOP').exists():raise SafePause('complete boundary pause')
        assert not target.exists(),'incomplete phase must be preserved'
        target.mkdir();before=core.capture_state();e.storage.save(target/'initial.tmind',before)
        e.packed(target/'initial-observer.json.xz',session.capture())
        if not calibration:s.base.original(work/'in-flight.json',{'subject':c['key'],'phase':name,'begin_us':begin,'pid':os.getpid(),'created':psutil.Process().create_time()})
        rows=deepcopy(rows)
        for r in rows:
            r['enqueue_us']=r.get('enqueue_us',r['time_us'])+begin
            r['time_us']+=begin
        rows.sort(key=lambda r:r['enqueue_us'])
        index=0;points=[];delivered_start=len(deliveries);scheduled=[]
        step=10000 if mode=='dense' else 50000
        next_sample=begin
        def observe():
            nonlocal recent
            p=selected(core,set(ids.values()));recent=[x for x in recent if x['time_us']>core.time_us-500000]
            recent.append(p)
            if mode!='plain' or question is not None:points.append(p)
        while True:
            guard()
            while index<len(rows) and rows[index]['enqueue_us']==core.time_us:
                r=rows[index];st=e.base.Stimulus.from_dict({'time_us':r['time_us'],'channels':r['channels'],'intensity':r['intensity']})
                receipt=session.schedule([{'stimulus':st}],source=r['source'],adapter_id='anonymous-frames',at=0,
                    envelope_id=uuid5(NS,c['key']+':'+name+':'+str(index)))
                scheduled.extend(receipt);index+=1
            session.advance_to(core.time_us,guard=guard)
            if core.time_us==next_sample:
                if mode!='plain' or question is not None:observe()
                next_sample+=step
            if core.time_us==end:break
            targets=[end,next_sample]
            if index<len(rows):targets.append(rows[index]['enqueue_us'])
            t=min(targets);assert t>core.time_us
            session.advance_to(t,guard=guard)
            assert core.life!='dead','unexpected incomplete state'
            if core.time_us%1000000==begin%1000000:
                m=core.metrics();assert m['nodes']<=2000 and m['edges']<=20000
            if calibration and mode in ('restored','paused') and not once and core.time_us>=begin+1000000:
                im=core.capture_state();ob=session.capture()
                if mode=='restored':
                    core=make(e.base.ArtifactCodec.decode(e.base.ArtifactCodec.encode(im)))
                    session=e.base.ReadoutSession(core,state=ob,record=events.append,event_sink=sink)
                else:time.sleep(.01)
                assert core.capture_state().digest==im.digest;once=True
        assert index==len(rows) and len(deliveries)-delivered_start==len(rows) and session.bus.pending_count()==0
        final=core.capture_state();e.storage.save(target/'final.tmind',final)
        ob=session.capture();e.packed(target/'observer.json.xz',ob)
        e.packed(target/'trajectory.json.xz',points);e.packed(target/'recent.json.xz',recent)
        e.packed(target/'inputs.json.xz',rows);e.packed(target/'delivered.json.xz',deliveries[delivered_start:])
        e.packed(target/'scheduled.json.xz',scheduled)
        assert core.capture_state().digest==final.digest
        r={'status':'complete','phase':name,'begin_us':begin,'end_us':end,'initial_sha256':before.digest,
            'final_sha256':final.digest,'inputs':len(rows),'points':len(points),'question':question,'config':cfg}
        if question is not None:r['answer']=score(points,ids,end,d.expected(c,question['cue']))
        s.base.original(target/'result.json',r);records.append(r)
        if not calibration:(work/'in-flight.json').unlink()
        return r
    def frames(pulses,duration,source):
        out=[{'time_us':int(t),'channels':[[ids[n],1.] for n in names],'intensity':strength,'source':source}
            for t,names,strength in pulses]
        out += [{'time_us':t,'channels':[[ids['keep'],1.]],'intensity':.2,'source':'fixed-background'}
            for t in range(0,duration+1,500000)]
        return out
    if calibration:
        pulses=d.lesson(c,'A',0)+d.lesson(c,'D',4000000)
        phase('calibration',frames(pulses,8000000,'apparatus-teacher'),8000000)
    else:
        material=s.base.read(work/'materials'/f"{c['task']}-s{c['swap']}.json")
        raw=material['frames'];rows=[]
        for r in raw:
            assert r['enqueue_us']<=int(r['stimulus']['time_us'])
            rows.append({'time_us':int(r['stimulus']['time_us']),'enqueue_us':r['enqueue_us'],
                'channels':[[int(ch)^mask,a] for ch,a in r['stimulus']['channels']],
                'intensity':r['stimulus']['intensity'],'source':r['source']})
        phase('00-teaching',rows,material['end_us'])
        pulses,duration=d.review(c);phase('01-review',frames(pulses,duration,'spaced-review'),duration)
        for i,q in enumerate(c['development']):
            pulses,duration,origin=d.question(c,q)
            r=phase(f'02-dev{i}',frames(pulses,duration,'development-cue'),duration,q)
            pulses,duration=d.correction(c,q['cue'],not r['answer']['correct'])
            phase(f'03-correction{i}',frames(pulses,duration,'teacher-correction'),duration)
        for i,q in enumerate(c['tests']):
            pulses,duration,origin=d.question(c,q)
            phase(f'04-final{i:02d}',frames(pulses,duration,'test-cue'),duration,q)
    final=core.capture_state();e.storage.save(folder/'final.tmind',final)
    e.packed(folder/'observer.json.xz',session.capture())
    result={'key':c['key'],'status':'complete','kernel':'threemind.continuous-memory/6.3','config':cfg,
        'begin_us':0,'end_us':core.time_us,'initial_sha256':e.base.image(folder/'initial.tmind').digest,
        'final_sha256':final.digest,'phases':len(records),'inputs':sum(r['inputs'] for r in records),
        'wall_seconds':time.monotonic()-started,'calibration':calibration,'mode':mode}
    s.base.original(folder/'result.json',result)
    return result,final,session.capture()
