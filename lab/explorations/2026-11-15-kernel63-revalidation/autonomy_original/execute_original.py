"""E15 materials and public interventions on genuine 6.3 complete subjects.

This preparation module has no import-time simulation. All advancement is in
execute(), which the registered serial host calls only after apparatus checks.
"""
import copy
from dataclasses import asdict, dataclass, replace
import json
import io
import lzma
import math
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import materials_original as materials
sys.path.insert(0,str(HERE.parent/'body_recovery'))
import study_recovery as support
base=support.x.base
s=support.s
storage=support.x.storage
from threemind_runtime.adapters import channel_id
from threemind_runtime.energy_supply import EnergySupplier, EnergySupplyConfig
from threemind_runtime.inheritance import birth, birth_metadata

KERNEL='threemind.continuous-memory/6.3'
NS=UUID('516040df-0470-50b1-b0f3-b8b26a32e38f')
SUPPLY=EnergySupplyConfig(enabled=True,rate_per_s=10,interval_us=100000,total_supply_limit=None)
MOTOR_NAMESPACE='world-motor-v1:ring-study-v1:0'
SENSORY_NAMESPACE='ring-sensory-v1'


def packed(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with lzma.open(path,'xb',preset=1) as stream:
        with io.TextIOWrapper(stream,encoding='utf-8',newline='') as text:
            json.dump(value,text,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def unpacked(path):
    with lzma.open(path,'rb') as stream:return json.load(stream)


def symbols(seed,calibration=False):
    mask=0x20000000 if calibration else 0
    return {name:channel_id(seed,SENSORY_NAMESPACE,index)^mask for name,index in zip('ABCD',(0,1,4,5))}


@dataclass
class Body:
    x:float=.3125
    v:float=0.
    phase:float=0.

    @property
    def region(self):return int((self.x+self.phase)%1>=.5)

    def move(self,control,seconds):
        decay=math.exp(-.8*seconds);terminal=.3*control/.8
        distance=terminal*seconds+(self.v-terminal)*(1-decay)/.8
        self.x=(self.x+distance)%1
        self.v=terminal+(self.v-terminal)*decay
        return distance


def motor(seed,nodes):
    # Identical declared projection function; 6.3 uses its real virtual node IDs.
    return math.tanh(.5*math.fsum(
        (1 if channel_id(seed,MOTOR_NAMESPACE,int(n['id']))&1 else -1)*n['activation']
        for n in sorted(nodes,key=lambda n:n['id'])))


def sensation(body,seed,at,environment,calibration=False):
    names=(('AB','CD') if environment=='P' else ('AD','CB'))[body.region]
    ids=symbols(seed,calibration);channels=[(ids[name],1.) for name in names]
    if body.v:
        ch=channel_id(seed,SENSORY_NAMESPACE,8+int(body.v<0))^(0x20000000 if calibration else 0)
        channels.append((ch,math.tanh(abs(body.v)/.375)))
    return base.Stimulus(at,tuple(channels),.8)


def task_edges(engine,channels):
    state=engine.capture_state().to_dict()
    ids={n['channel']:n['id'] for n in state['nodes']}
    a,b,d=(ids.get(channels[k]) for k in 'ABD')
    wanted={(a,b),(b,a),(a,d),(d,a)}
    return sorted((e['source'],e['target']) for e in state['edges'] if (e['source'],e['target']) in wanted)


def matched(engine,targets,forbidden=()):
    """Original count/weight/stability rule, measured at the intervention time."""
    nodes=engine.observation_nodes()
    graph=engine.induced_edges([n['id'] for n in nodes])
    by={(r['source'],r['target']):r for r in graph}
    assert set(targets)<=set(by),'target not available to the declared active-edge matching instrument'
    pool={key for key in by if key not in targets and not set(key)&set(forbidden)}
    chosen=[];residuals=[]
    for key in targets:
        assert pool,'insufficient matched edges; preserve apparatus and inspect'
        ref=by[key]
        score=lambda k:(abs(by[k]['weight']-ref['weight'])+abs(by[k]['stability']-ref['stability']),k)
        best=min(pool,key=score);pool.remove(best);chosen.append(best)
        residuals.append({'target':key,'matched':best,'weight_error':by[best]['weight']-ref['weight'],
            'stability_error':by[best]['stability']-ref['stability'],'sum_absolute_error':score(best)[0]})
    return chosen,residuals


def execute(case,folder,root,parent=None,whole=None,*,mode='observed',calibration=False):
    began=time.monotonic();ex=case['historical_details'];stage=ex.get('stage',ex.get('kind'))
    make=lambda image=None:base.resolve_kernel(KERNEL).create(
        None if image else {'seed':9293299 if calibration else case['seed'],
            'energy_simulation_enabled':True,'depletion_enabled':True,'stp_facilitation_tau_s':1.,
            'edge_consolidation_enabled':True},image,backend='native')
    inherited=case['birth_intervention']
    origin=birth(parent,decay_age='preserve') if inherited else parent
    engine=make(origin);initial=engine.capture_state()
    assert engine.time_us==case['begin_us'] and (origin is None or initial.digest==origin.digest)
    folder.mkdir(parents=True,exist_ok=False)
    storage.save(folder/'initial.tmind',initial)
    initial_metrics=engine.metrics()
    ordinary=copy.deepcopy(whole) if whole is not None and not inherited else None
    reader=ordinary['observer'] if ordinary else None
    supplier=EnergySupplier(SUPPLY,engine,ordinary['supplier'] if ordinary else None)
    if stage=='environment' and ex['phase']>1:
        assert ordinary is not None
        body=Body(**ordinary['body'])
    elif stage=='ring_world':body=Body(ex['initial_position'],phase=ex['initial_phase'])
    elif stage=='probe' or stage=='environment':body=Body()
    else:body=Body(**ordinary['body']) if ordinary else Body()
    initial_body=asdict(body)
    events=[];deliveries=[];scheduled=[];points=[];network=[];interventions=[];first=[];milestones={};energy_offers=[]
    def sink(event,entry):
        if entry:deliveries.append(entry)
        if event['kind']=='energy':supplier.delivered(event)
        if event['kind'] in ('energy','spikes'):
            events.append({'kind':'core_event','time_us':event['time_us'],'payload':event})
    if reader is None:
        reader={'schema':'threemind.cli-readouts/1','session_id':str(uuid5(NS,'observer:'+case['key']))}
    session=base.ReadoutSession(engine,record=events.append,config=case['old_readout_config'],
        state=reader,event_sink=sink)
    packed(folder/'initial-whole.json.xz',{'observer':session.capture(),'supplier':supplier.capture(),'body':asdict(body)})
    assert engine.capture_state().digest==initial.digest
    channels=symbols(case['seed'],calibration)

    def change(label,patch=None,action=None,targets=(),details=None):
        before=engine.capture_state()
        if patch:engine.reconfigure(replace(engine.config,**patch))
        if action is not None:engine.intervene(edges=targets,action=action)
        after=engine.capture_state()
        assert before.to_dict()['time_us']==after.to_dict()['time_us']
        interventions.append({'label':label,'patch':patch,'action':action,'targets':targets,
            'before':before.digest,'after':after.digest,'changes':support.x.differences(before.to_dict(),after.to_dict()),
            'details':details})

    if stage=='probe':
        condition=ex['intervention']['condition'];targets=task_edges(engine,channels)
        ids={n['channel']:n['id'] for n in initial.to_dict()['nodes']}
        if condition=='sham':change('sham-empty-edge-operation',action='silence')
        elif condition=='off':change('all-communication-off',{'propagation_rate':0.,'inhibition_diffusion_rate':0.})
        elif condition=='returns':
            targets=sorted((e['source'],e['target']) for e in initial.to_dict()['edges'] if e['target']==ids.get(channels['A']))
            change('returns-to-cue-off',action='silence',targets=targets)
        elif condition=='matched_edges':
            targets,errors=matched(engine,targets,[ids.get(channels[k]) for k in 'ABD'])
            change('matched-edge-silence',action='silence',targets=targets,details={'matching':errors})
        elif condition in ('task_edges','restore'):
            change('task-edge-silence',action='silence',targets=targets)
            if condition=='restore':change('task-edge-restore',action='restore',targets=targets)
        else:assert condition=='normal'
    elif stage=='memory-training' and ex['protocol']=='spaced_no_consolidation':
        change('positive-existing-edge-updates-off',{'edge_consolidation_enabled':False})
    elif stage=='novelty' and ex['condition']=='novelty_off':
        change('local-novelty-gain-off',{'local_novelty_gain':0.})
    intervened=engine.capture_state();storage.save(folder/'intervened.tmind',intervened)
    rows=materials.normalize((root/case['key']/'frames.jsonl').read_bytes(),case)
    if calibration:
        rows=copy.deepcopy(rows)
        for row in rows:row['stimulus']['channels']=[[ch^0x20000000,a] for ch,a in row['stimulus']['channels']]
    if case['new_closed_loop']:rows=[r for r in rows if r['source']!='controlled-environment']
    groups=[]
    for row in rows:
        key=(row['enqueue_us'],row['old_envelope'])
        if groups and groups[-1]['key']==key:groups[-1]['rows'].append(row)
        else:groups.append({'key':key,'rows':[row]})
    index=0;dynamic=[];restored=False;next_point=case['begin_us'];next_first=case['begin_us']
    next_motor=case['begin_us'];next_sense=case['begin_us'];last_monitor=None
    phase=str(uuid5(NS,case['key']))

    def guard():
        if time.monotonic()-began>300:raise RuntimeError('registered stage wall budget; preserve in-flight')

    def enqueue(frames,source,identity,extra=None):
        receipt=session.schedule([{'stimulus':base.Stimulus.from_dict(f)} for f in frames],source=source,
            adapter_id='anonymous-frames',at=0,envelope_id=uuid5(NS,phase+identity))
        scheduled.extend({'enqueue_us':engine.time_us,'receipt':r,'external':extra} for r in receipt)

    with zipfile.ZipFile(folder/'milestones.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        def snapshot(name):
            image=engine.capture_state();raw=base.ArtifactCodec.encode(image)
            assert base.ArtifactCodec.decode(raw).digest==image.digest
            archive.writestr(name+'.tmind',raw);milestones[name]=image.digest
        if stage=='novelty':snapshot('before-training')
        while True:
            guard();now=engine.time_us;relative=now-case['begin_us']
            if case['new_closed_loop'] and now==next_sense and now<case['end_us']:
                stimulus=sensation(body,case['seed'],now,ex['route'][ex['phase']-1],calibration)
                row={'stimulus':stimulus.to_dict(),'body':asdict(body),'region':body.region,
                     'environment':ex['route'][ex['phase']-1]}
                dynamic.append(row);enqueue([stimulus.to_dict()],'controlled-environment',':sense:'+str(relative),row)
                next_sense+=1000000
            while index<len(groups) and groups[index]['key'][0]==now:
                group=groups[index];assert len({r['source'] for r in group['rows']})==1
                enqueue([r['stimulus'] for r in group['rows']],group['rows'][0]['source'],':replay:'+str(index))
                index+=1
            # Supply is an explicit timestamped external input, preserved across stages.
            if now<case['end_us']:
                offer=supplier.prepare(engine)
                if offer is not None:energy_offers.append(offer)
            session.advance_to(now,guard=guard)
            assert engine.life!='dead','unexpected death: preserve complete current evidence'
            if stage=='probe' and now==next_point:
                nodes=engine.observation_nodes();control=motor(case['seed'],nodes)
                if mode!='plain' and (mode!='sparse' or relative%100000==0):
                    points.append({'relative_us':relative,'nodes':nodes,'control':control,'body':asdict(body)})
                if now<case['end_us']:
                    dt=10000 if relative<2000000 else 100000
                    body.move(control,dt/1e6);next_point+=dt
            elif stage in ('environment','ring_world') and now==next_motor and now<case['end_us']:
                nodes=engine.observation_nodes();control=motor(case['seed'],nodes)
                if mode!='plain':points.append({'relative_us':relative,'nodes':nodes,'control':control,
                    'body':asdict(body),'region':body.region})
                body.move(control,.1);next_motor+=100000
            if stage=='novelty' and now==next_first and relative<1000000:
                nodes=engine.observation_nodes()
                if mode!='plain':first.append({'relative_us':relative,'nodes':nodes,'control':motor(case['seed'],nodes)})
                next_first+=10000
            should_monitor=(mode=='observed' or mode in ('restored','paused') or relative%100000==0)
            if (should_monitor or relative%1000000==0) and last_monitor!=now:
                values=engine.metrics();assert values['nodes']<=2000 and values['edges']<=20000
                if mode!='plain':network.append(values)
                last_monitor=now
            if now==case['end_us']:break
            if mode in ('restored','paused') and not restored and relative>=1000000:
                image=engine.capture_state();observer=session.capture();energy=supplier.capture()
                if mode=='restored':
                    engine=make(base.ArtifactCodec.decode(base.ArtifactCodec.encode(image)))
                    supplier=EnergySupplier(SUPPLY,engine,energy)
                    session=base.ReadoutSession(engine,record=events.append,state=observer,event_sink=sink)
                else:time.sleep(.01)
                assert engine.capture_state().digest==image.digest
                restored=True
            candidates=[case['end_us'],now+100000]
            if index<len(groups):candidates.append(groups[index]['key'][0])
            if supplier.deadline is not None:candidates.append(supplier.deadline)
            if stage=='probe':candidates.append(next_point)
            if stage in ('environment','ring_world'):candidates.append(next_motor)
            if case['new_closed_loop']:candidates.append(next_sense)
            if stage=='novelty' and next_first<case['begin_us']+1000000:candidates.append(next_first)
            target=min(v for v in candidates if v>now)
            session.advance_to(target,guard=guard)
        assert index==len(groups)
        if stage=='memory-training' and ex['protocol']=='spaced_no_consolidation':
            change('restore-positive-existing-edge-updates',{'edge_consolidation_enabled':True})
        if stage=='novelty':
            snapshot('before-erasure')
            feature_ids={n['id'] for n in engine.observation_nodes() if n['channel'] in
                [ch^(0x20000000 if calibration else 0) for ch in ex['channels']]}
            targets=sorted((e['source'],e['target']) for e in engine.capture_state().to_dict()['edges']
                if {e['source'],e['target']}<=feature_ids)
            if ex['condition'] in ('erase','matched_erase'):
                errors=[]
                if ex['condition']=='matched_erase':targets,errors=matched(engine,targets,feature_ids)
                change('post-experience-'+ex['condition'],action='disconnect_edges',targets=targets,details={'matching':errors})
        snapshot('end')
    final=engine.capture_state()
    assert engine.time_us==case['end_us'] and final.to_dict()['energy']['unserved_total']<=1e-10
    assert len(deliveries)==len(rows)+len(dynamic) and session.bus.pending_count()==0
    if stage=='probe':session.host.close(engine.time_us,'run_ended')
    assert engine.capture_state().digest==final.digest
    state={'observer':session.capture(),'supplier':supplier.capture(),'body':asdict(body)}
    storage.save(folder/'final.tmind',final);packed(folder/'whole.json.xz',state)
    packed(folder/'trajectory.json.xz',{'rows':points,'first':first,'events':events,
        'initial_metrics':initial_metrics,'network_summaries':network,'energy_offers':energy_offers})
    packed(folder/'inputs.json.xz',{'replayed':rows,'closed_loop':dynamic})
    packed(folder/'scheduled.json.xz',scheduled);packed(folder/'delivered.json.xz',deliveries)
    packed(folder/'interventions.json.xz',interventions)
    windows=[r['payload'] for r in events if r['kind']=='temporal_readout']
    motor_ids={n['id'] for rows_at_time in points+first for n in rows_at_time['nodes']}
    motor_ids.update(n['id'] for n in final.to_dict()['nodes'])
    result={'key':case['key'],'stage':stage,'kernel':KERNEL,'mode':mode,'calibration':calibration,
        'begin_us':case['begin_us'],'end_us':engine.time_us,'life':engine.life,
        'initial_sha256':initial.digest,'intervened_sha256':intervened.digest,'final_sha256':final.digest,
        'parent_sha256':parent.digest if parent else None,'birth_intervention':inherited,
        'birth':birth_metadata(parent) if inherited else None,'initial_body':initial_body,
        'final_body':asdict(body),'milestones':milestones,'inputs':len(deliveries),'points':len(points),
        'window_classifications':[w['classification'] for w in windows],
        'motor_projection':{'namespace':MOTOR_NAMESPACE,'seed':case['seed'],'gain':.5,
            'coefficients':{str(n):1 if channel_id(case['seed'],MOTOR_NAMESPACE,n)&1 else -1 for n in sorted(motor_ids)}},
        'status':'complete','wall_seconds':time.monotonic()-began}
    s.base.original(folder/'result.json',result)
    return result,final,state
