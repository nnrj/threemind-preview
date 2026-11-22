"""R63a continuous mechanism courses and explicitly registered causal copies."""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(ROOT/'src'),str(HERE.parent)]
import support as s
from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.readout_config import ActivityReadoutConfig, TemporalReadoutConfig
from threemind_runtime.readout_session import ReadoutSession

KERNEL='threemind.continuous-memory/6.3'
NS=UUID('3502b500-c12b-5d32-84d8-89a236506358')
READERS={'structural_readout':{'enabled':False},
         'temporal_readout':asdict(TemporalReadoutConfig(max_response_us=5000000,baseline_us=0,max_active_windows=256)),
         'activity_readout':asdict(ActivityReadoutConfig(max_response_us=5000000,interval_us=100000,baseline_us=0))}


def state_write(path,image):
    raw=ArtifactCodec.encode(image)
    assert ArtifactCodec.decode(raw).digest==image.digest
    return s.blob(path,raw)


def new_engine(config=None,state=None):
    return resolve_kernel(KERNEL).create(config,state,backend='native')


def trial(work,case):
    key=case['key'];folder=work/'cases'/key;folder.mkdir(parents=True,exist_ok=False)
    parent=case['parent']
    image=ArtifactCodec.decode((work/'cases'/parent/'final.tmind').read_bytes()) if parent else None
    engine=new_engine(None if parent else case['config'],image)
    initial=engine.capture_state();state_write(folder/'initial.tmind',initial)
    assert image is None or image.digest==initial.digest
    events=[]
    cfg=READERS if case['stage']=='probe' else {k:{'enabled':False} for k in READERS}
    session=ReadoutSession(engine,record=events.append,config=cfg)
    assert engine.capture_state().digest==initial.digest
    for i,row in enumerate(case['inputs']):
        stim=Stimulus.from_dict(row['stimulus'])
        session.schedule([{'stimulus':stim}],source='manual-registered-probe' if row['kind']=='probe' else 'background-registered-teaching',
                         adapter_id='registered-anonymous-replay',at=0,envelope_id=uuid5(NS,key+f':{i}'))
    s.base.original(folder/'initial-observer.json',session.capture())
    points=[];spans=[];alive={};start=time.monotonic();paused=None
    def guard():
        if time.monotonic()-start>300:raise TimeoutError('condition wall-clock budget reached')
    try:
        while True:
            before=engine.capture_state();doc=before.to_dict();now=engine.time_us
            nodes=engine.observation_nodes();metrics=engine.metrics()
            assert before.digest==engine.capture_state().digest,'observer changed Core'
            edges={(e['source'],e['target']) for e in doc['edges']}
            for edge in edges-alive.keys():alive[edge]=now
            for edge in alive.keys()-edges:
                spans.append({'edge':list(edge),'start_us':alive.pop(edge),'end_us':now,'right_censored':False})
            points.append({'time_us':now,'nodes':nodes,'metrics':metrics})
            if len(doc['nodes'])>2000 or len(edges)>20000:raise TimeoutError('registered network budget reached')
            if now>=case['target_us'] or engine.life=='dead':break
            session.advance_to(min(case['target_us'],now+100000),guard=guard)
    except TimeoutError as exc:
        paused=str(exc)
    if case['stage']=='probe':session.host.close(engine.time_us,'run_ended' if paused is None else 'budget_paused')
    final=engine.capture_state();doc=final.to_dict()
    spans += [{'edge':list(edge),'start_us':at,'end_us':engine.time_us,'right_censored':True} for edge,at in alive.items()]
    state_file=state_write(folder/'final.tmind',final)
    s.base.original(folder/'observer.json',session.capture())
    s.base.original(folder/'input.json',case)
    s.base.original(folder/'trajectory.json.gz',{'points':points,'edge_spans':spans,'events':events},compressed=True)
    dose=Counter()
    for row in case['inputs']:
        stim=Stimulus.from_dict(row['stimulus'])
        for channel,value in stim.channels:dose[channel]+=value*stim.intensity
    original={1001,1002}
    edges=doc['edges']
    result={k:v for k,v in case.items() if k!='inputs'}
    result.update({'status':'paused-budget' if paused else 'complete','pause_reason':paused,
                   'initial_sha256':initial.digest,'final_sha256':final.digest,'final_file':state_file,
                   'clock_start_us':int(initial.to_dict()['time_us']),'clock_end_us':engine.time_us,'life':engine.life,
                   'nodes':len(doc['nodes']),'edges':len(edges),'cross_original_edges':sum((e['source'] in original)!=(e['target'] in original) for e in edges),
                   'weight_sum':sum(e['weight'] for e in edges),'input_dose_by_channel':dict(dose),'wall_seconds':time.monotonic()-start})
    s.base.original(folder/'result.json',result)
    return result


def run(work):
    assert (work/'registration.json').exists() and (work/'instrument-check.json').exists()
    assert json.loads((work/'instrument-check.json').read_bytes())['passed']
    manifest=json.loads((work/'frozen.json').read_bytes())
    for name,digest in manifest['sources'].items():assert s.sha(ROOT/name)==digest,name
    from _threemind_native import _threemind_native as native
    assert s.sha(native.__file__)==manifest['native_sha256']
    cases=json.loads((work/'cases.json').read_bytes())
    assert len(cases)==264
    if (work/'summary.json').exists():raise RuntimeError('Completed computation; analyze or publish, never rerun')
    with s.base.worker_lock(work),s.base.Guard(work):
        assert not (work/'in-flight.json').exists(),'Orphaned in-flight: preserve and ask'
        results=[]
        for case in cases:
            done=work/'cases'/case['key']/'result.json'
            if done.exists():
                result=json.loads(done.read_bytes());assert result['status']=='complete'
                assert ArtifactCodec.decode(done.with_name('final.tmind').read_bytes()).digest==result['final_sha256']
                results.append(result);continue
            if (work/'STOP').exists():raise RuntimeError('Complete-boundary STOP retained')
            s.base.resource_check(work)
            import psutil
            proc=psutil.Process()
            s.base.original(work/'in-flight.json',{'key':case['key'],'pid':proc.pid,'created':proc.create_time()})
            result=trial(work,case);results.append(result)
            (work/'in-flight.json').unlink()
            s.base.atomic_json(work/'current.json',{'completed':sum(r['status']=='complete' for r in results),'total':264,'last':case['key']})
            print(json.dumps({'complete':case['key'],'nodes':result['nodes'],'edges':result['edges'],'wall_s':result['wall_seconds']}),flush=True)
            size=sum(p.stat().st_size for p in (work/'cases').rglob('*') if p.is_file())
            if result['status']!='complete' or size>512*2**20 or sum(r['wall_seconds'] for r in results)>5400:
                s.base.original(work/'STOP',{'reason':result['pause_reason'] or 'batch evidence/time budget','complete_boundary':case['key']})
                raise RuntimeError('Complete state saved; registered budget stop')
        s.base.original(work/'summary.json',{'status':'awaiting-analysis','conditions':len(results),'kernel':KERNEL,
                                         'encoding_blocks':2,'configuration_pairs':4,'wall_seconds':sum(r['wall_seconds'] for r in results)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    run(p.parse_args().work.resolve())
