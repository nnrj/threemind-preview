"""R51t1 cross-version replay, derived from the frozen E12 executor; no Core changes."""
import copy
from dataclasses import replace
import gzip
import json
import lzma
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5
import zipfile

HERE=Path(__file__).resolve().parent
import research_kernel as research
sys.path.insert(0,str(HERE.parent/'memory_timescales'))
import materials_timescales as materials
sys.path.insert(0,str(HERE.parent/'body_recovery'))
import study_recovery as support
base=support.x.base
s=support.s
import research_storage as storage
NS=UUID('ac15a27b-70c2-50dd-b80c-7fdbb6d08245')


def packed(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with lzma.open(path,'xb',preset=1) as f:f.write(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8'))


def unpacked(path):
    with lzma.open(path,'rb') as f:return json.load(f)


def material_frames(case,root,calibration=False):
    original_case=dict(case,key=case['material_key'])
    path=root/case['material_key']/'frames.jsonl'
    rows=materials.normalize(path.read_bytes(),original_case)
    if calibration:
        rows=copy.deepcopy(rows)
        for row in rows:row['stimulus']['channels']=[[ch^0x20000000,a] for ch,a in row['stimulus']['channels']]
    return rows


def observe(engine,scope,calibration=False):
    targets={v^(0x20000000 if calibration else 0) for v in materials.TOKENS.values()}
    nodes=engine.observation_nodes()
    assert len(nodes)<=2000
    if scope=='task':nodes=[n for n in nodes if n['channel'] in targets]
    return {'time_us':engine.time_us,'life':engine.life,'nodes':nodes}


def execute(case,folder,root,initial=None,reader=None,*,mode='observed',calibration=False):
    began=time.monotonic()
    config={'seed':9291199 if calibration else materials.SEED,**case['initial_config'],**case['birth_patch']}
    kernel=research.KERNEL_ID
    make=lambda image=None:research.ResearchEngine(None if image else research.ResearchConfig(**config),image)
    engine=make(initial);born=engine.capture_state()
    assert engine.time_us==case['begin_us'] and (initial is None or born.digest==initial.digest)
    folder.mkdir(parents=True,exist_ok=False)
    storage.save(folder/'initial.rstate',born)
    before=engine.observation_nodes()
    patch=case['patch']|case['cause_patch']
    if patch:engine.reconfigure(replace(engine.config,**patch))
    if case.get('weight_donor'):
        donor=storage.image(root.parent/'cases'/case['weight_donor']/'final.rstate').to_dict()
        by_key={(x['source'],x['target']):x for x in donor['edges']}
        assert set(by_key)==set(engine.edges),'weight swap requires identical directed topology'
        assert [(n.id,n.channel) for n in engine.nodes.values()]==[(n['id'],n['channel']) for n in donor['nodes']]
        for key,edge in engine.edges.items(): edge.weight=by_key[key]['weight']
    changed=engine.capture_state()
    assert engine.time_us==case['begin_us']
    storage.save(folder/'intervened.rstate',changed)
    s.base.original(folder/'intervention.json',{'patch':patch,'weight_donor':case.get('weight_donor'),'before':born.digest,'after':changed.digest,
        'advanced_us':0,'changes':support.x.differences(born.to_dict(),changed.to_dict()),
        'projected_before':before,'projected_after':engine.observation_nodes()})
    deliveries=[];events=[];scheduled=[];points=[];snapshots={};monitor=[];projections={}
    def sink(event,entry):
        if entry:deliveries.append(entry)
    session=base.ReadoutSession(engine,record=events.append,config=case['old_readers'],state=copy.deepcopy(reader),event_sink=sink)
    assert engine.capture_state().digest==changed.digest
    packed(folder/'initial-observer.json.xz',session.capture())
    rows=material_frames(case,root,calibration)
    groups=[]
    for row in rows:
        key=(row['enqueue_us'],row['old_envelope'])
        if groups and groups[-1]['key']==key:groups[-1]['rows'].append(row)
        else:groups.append({'key':key,'rows':[row]})
    index=0;restored=False;probe=case.get('probe_start_us');started_probe=False
    next_point=probe
    step=100000 if mode=='sparse' else 10000
    phase_id=str(uuid5(NS,case['key']))
    def guard():
        if time.monotonic()-began>300:raise RuntimeError('stage wall budget; preserve in-flight')
    def queue_due():
        nonlocal index
        while index<len(groups) and groups[index]['key'][0]==engine.time_us:
            group=groups[index];frames=group['rows']
            assert len({r['source'] for r in frames})==1
            receipt=session.schedule([{'stimulus':base.Stimulus.from_dict(r['stimulus'])} for r in frames],
                source=frames[0]['source'],adapter_id='anonymous-frames',at=0,
                envelope_id=uuid5(NS,phase_id+':'+str(index)))
            scheduled.extend({'enqueue_us':engine.time_us,'receipt':v} for v in receipt)
            index+=1
    milestones=set(case.get('milestones',[]))
    with zipfile.ZipFile(folder/'milestones.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        def capture(name):
            state=engine.capture_state();raw=storage.Codec.encode(state)
            assert storage.Codec.decode(raw).digest==state.digest
            archive.writestr(name+'.rstate',raw);snapshots[name]=state.digest
            projections[name]={'time_us':engine.time_us,'nodes':engine.observation_nodes(),
                               'graph':engine.graph(),'metrics':engine.metrics()}
            assert engine.capture_state().digest==state.digest
        while True:
            guard();queue_due()
            if probe is not None and not started_probe and engine.time_us==probe:
                capture('before_probe')
                if mode!='plain':points.append(observe(engine,case['scope'],calibration))
                session.advance_to(probe,guard=guard)
                if mode!='plain':points.append(observe(engine,case['scope'],calibration))
                started_probe=True;next_point=probe+step
            else:session.advance_to(engine.time_us,guard=guard)
            if engine.time_us==case['end_us']:break
            targets=[case['end_us'],engine.time_us+100000]
            if index<len(groups):targets.append(groups[index]['key'][0])
            if probe is not None:
                targets.append(next_point if started_probe else probe)
                targets.extend(probe+t for t in milestones if probe+t>engine.time_us)
            target=min(targets);assert target>engine.time_us
            session.advance_to(target,guard=guard)
            assert engine.life!='dead','unexpected incomplete state'
            if probe is None and mode!='plain':points.append(observe(engine,'task',calibration))
            if started_probe and engine.time_us==next_point:
                if mode!='plain':points.append(observe(engine,case['scope'],calibration))
                next_point+=step
            if probe is not None and started_probe and engine.time_us-probe in milestones:
                capture(str(engine.time_us-probe))
            if engine.time_us%1000000==case['begin_us']%1000000:
                metrics=engine.metrics();assert metrics['nodes']<=2000 and metrics['edges']<=20000
                monitor.append(metrics)
            if mode in ('restored','paused') and started_probe and not restored and engine.time_us>=probe+1000000:
                whole=engine.capture_state();ob=session.capture()
                if mode=='restored':
                    engine=make(storage.Codec.decode(storage.Codec.encode(whole)))
                    session=base.ReadoutSession(engine,record=events.append,state=ob,event_sink=sink)
                else:time.sleep(.01)
                assert whole.digest==engine.capture_state().digest
                restored=True
        assert index==len(groups) and len(deliveries)==len(rows) and session.bus.pending_count()==0
        capture('end')
    final=engine.capture_state()
    # Closing a diagnostic window is a passive readout operation at the same clock.
    session.host.close(engine.time_us,'run_ended')
    assert engine.capture_state().digest==final.digest
    storage.save(folder/'final.rstate',final)
    packed(folder/'observer.json.xz',session.capture())
    packed(folder/'trajectory.json.xz',{'points':points,'events':events,'network_summaries':monitor})
    packed(folder/'projections.json.xz',projections)
    packed(folder/'inputs.json.xz',rows)
    packed(folder/'scheduled.json.xz',scheduled)
    packed(folder/'delivered.json.xz',deliveries)
    manual={r['receipt']['envelope_id'] for r in scheduled if r['receipt']['source']=='manual-probe'}
    windows=[e['payload'] for e in events if e['kind']=='temporal_readout' and e['payload']['envelope_id'] in manual]
    window=windows[-1] if windows else None
    result={'key':case['key'],'kind':case['kind'],'kernel':kernel,'begin_us':case['begin_us'],
        'end_us':engine.time_us,'life':engine.life,'initial_sha256':born.digest,'intervened_sha256':changed.digest,
        'final_sha256':final.digest,'parent_sha256':initial.digest if initial else None,'calibration':calibration,
        'mode':mode,'status':'complete','inputs':len(rows),'snapshots':snapshots,'points':len(points),
        'classification':window['classification'] if window else 'no_window',
        'reason':window['reason'] if window else 'no_window','wall_seconds':time.monotonic()-began}
    s.base.original(folder/'result.json',result)
    return result,final,session.capture()
