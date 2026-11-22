"""R51t7. Explicit research branches; production kernels are frozen before run."""
import argparse
import copy
from dataclasses import replace
import gc
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'lab/explorations/2026-11-13-kernel61/prefix_components'))
import components_study as infrastructure
from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec

base=infrastructure.s.base
PROJECT=infrastructure.e.base.PROJECT
NS=UUID('b7e48d5a-1878-4546-9018-166b05794601')
OLD=Path('E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-cross61-v1')
spec=importlib.util.spec_from_file_location('r51t7_measures',ROOT/'lab/explorations/2026-11-13-kernel61/memory_timescales/measurement_timescales.py')
measure=importlib.util.module_from_spec(spec);spec.loader.exec_module(measure)
STABLE={'consolidation_mode':'stability','novelty_mode':'immediate'}
VARIANTS={
 'old51':('5.1',{'consolidation_mode':'legacy-stability','novelty_mode':'immediate'}),
 'compatible62':('6.2',{}),
 'stability-window':('6.2',STABLE|{'novelty_mode':'arrival-window'}),
 'stability-immediate':('6.2',STABLE),
 'inhibitory-weight-off':('6.2',STABLE|{'inhibition_weight_reinforcement_enabled':False}),
 'excitatory-weight-off':('6.2',STABLE|{'activation_weight_reinforcement_enabled':False}),
 'both-weights-off':('6.2',STABLE|{'activation_weight_reinforcement_enabled':False,'inhibition_weight_reinforcement_enabled':False}),
 'inhibitory-learning-off':('6.2',STABLE|{'inhibitory_learning_enabled':False}),
 'compatible-inhibitory-weight-off':('6.2',{'inhibition_weight_reinforcement_enabled':False}),
}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def write(path,value):base.original(path,value)
def packed(path,value):
    with gzip.open(path,'xb',compresslevel=1) as f:f.write(json.dumps(value,ensure_ascii=False,sort_keys=True).encode())
def unpack(path):
    with gzip.open(path,'rb') as f:return json.load(f)

def cases():
    return {c['material_key']:c for c in read(OLD/'cases.json') if c['variant']=='v5.1-legacy-edges-immediate'}

def inputs(work,case,calibration=False):
    rows=[json.loads(x) for x in (work/'materials'/case['material_key']/'frames.jsonl').read_bytes().splitlines()]
    assert rows.pop(0)['run_id']==case['old_id']
    for r in rows:
        assert r['status']=='delivered' and not r['labels']
        assert r['delivered_time_us']==r['scheduled_time_us']==r['stimulus']['time_us']
        if calibration:r['stimulus']['channels']=[[ch^0x20000000,a] for ch,a in r['stimulus']['channels']]
    return sorted(rows,key=lambda r:(int(r['source_policy']['resolved_at_us']),r['core_event_id']))

def create(variant,case,calibration=False,state=None):
    version,patch=VARIANTS[variant]
    descriptor=resolve_kernel('threemind.continuous-memory/'+version)
    if state is not None:return descriptor.create(state=state,backend='native')
    return descriptor.create({'seed':9291199 if calibration else 9291000,**case['initial_config'],**patch},backend='native')

def projection(engine):
    d=engine.capture_state().to_dict();ids={n['id']:n['channel'] for n in d['nodes']}
    return {'time_us':engine.time_us,'nodes':engine.observation_nodes(),
            'edges':[dict(r,source_channel=ids[r['source']],target_channel=ids[r['target']]) for r in d['edges']],
            'transport':d.get('transport',{})}

def execute(engine,case,rows,trace=True,mode='observed',calibration=False):
    index=0;points=[];teaching=[];probe=case.get('probe_start_us');next_point=probe;started=False
    wall=time.monotonic();restored=False
    targets={v^(0x20000000 if calibration else 0) for v in measure.TOKENS.values()}
    def observe():return {'time_us':engine.time_us,'nodes':[r for r in engine.observation_nodes() if r['channel'] in targets]}
    while True:
        assert time.monotonic()-wall<300,'stage wall limit; preserve in-flight'
        if probe==engine.time_us and not started and mode!='plain':points.append(observe())
        while index<len(rows) and int(rows[index]['source_policy']['resolved_at_us'])==engine.time_us:
            engine.inject(Stimulus.from_dict(rows[index]['stimulus']));index+=1
        engine.advance_to(engine.time_us)
        if probe==engine.time_us and not started:
            started=True
            if mode!='plain':points.append(observe())
            next_point+=10000
        elif started and engine.time_us==next_point:
            if mode!='plain':points.append(observe())
            next_point+=10000
        if trace and probe is None:teaching.append(projection(engine))
        if mode in ('restored','paused') and not restored and engine.time_us>case['begin_us']+1000000:
            saved=engine.capture_state()
            if mode=='restored':engine=resolve_kernel(saved.to_dict()['dynamics']).create(state=ArtifactCodec.decode(ArtifactCodec.encode(saved)),backend='native')
            else:time.sleep(.01)
            assert saved.digest==engine.capture_state().digest
            restored=True
        if engine.time_us==case['end_us']:break
        times=[case['end_us'],engine.time_us+(37000 if mode=='partitioned' else 100000)]
        if index<len(rows):times.append(int(rows[index]['source_policy']['resolved_at_us']))
        if next_point is not None:times.append(next_point)
        target=min(times);assert target>engine.time_us
        engine.advance_to(target)
        assert engine.life!='dead'
    assert index==len(rows)
    return engine,points,teaching

def register(work):
    assert not work.exists()
    assert base.resource_check(work.parent)['safe']
    assert shutil.disk_usage(work.parent).free>28*2**30
    work.mkdir();index=cases();write(work/'cases.json',index)
    reference=next(r for r in read(OLD/'analysis.json')['matrix'] if r['version']=='5.1' and r['retention']=='legacy-edges' and r['novelty']=='immediate')
    write(work/'reference-peaks.json',reference)
    for key in index:
        dest=work/'materials'/key/'frames.jsonl';dest.parent.mkdir(parents=True)
        shutil.copyfile(OLD/'materials'/key/'frames.jsonl',dest)
    files=list(HERE.glob('*.py'))+list(HERE.glob('protocol.*.md'))
    files+=list((ROOT/'src/threemind_kernels').glob('*.py'))
    files+=list((ROOT/'crates/threemind-core/src').glob('local62*'))
    files+=[ROOT/'src/threemind_runtime/host.py',Path(measure.__file__),Path(base.__file__)]
    frozen={str(p.relative_to(ROOT)):sha(p) for p in files}
    import _threemind_native
    native=Path(_threemind_native.__file__).parent
    dll=next(native.glob('*.pyd'))
    write(work/'frozen.json',{'sources':frozen,'native_path':str(dll),'native_sha256':sha(dll),
          'variants':VARIANTS,'materials':{str(p.relative_to(work)):sha(p) for p in (work/'materials').rglob('frames.jsonl')},
          'stages':54,'originals_cap':2**30,'total_peak_bytes':3*2**30})
    for rel in frozen:
        dest=work/'frozen-source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest)
    base.load_env();import httpx
    with base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=base.ResearchRecorder(work,PROJECT,client=client)
        rec.register({'source_key':'r51t7:prefix-recovery62:20261114:v1','title':'R51t7：6.2强化开关与前缀恢复定位',
          'classification':'formal','execution_status':'running','executor':'ai','kernels':['threemind.continuous-memory/5.1','threemind.continuous-memory/6.2'],
          'protocol':(HERE/'protocol.zh.md').read_text('utf8'),'protocol_version':sha(HERE/'protocol.zh.md'),
          'required_roles':['protocol','report','note','original'],'metadata':{'material_blocks':2,'stages':54,'main_paused':True}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-doc-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R51t7 protocol '+lang,'markdown':(HERE/f'protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True)
        write(work/'registration.json',{'project':PROJECT,'record':rec.experiment,'pending':rec.status['pending']})
    print(json.dumps(read(work/'registration.json')),flush=True)

def check(work):
    f=read(work/'frozen.json')
    for rel,h in f['sources'].items():assert sha(ROOT/rel)==h,rel
    for rel,h in f['materials'].items():assert sha(work/rel)==h,rel
    assert sha(Path(f['native_path']))==f['native_sha256']
    assert read(work/'registration.json')['pending']==0

def apparatus(work):
    check(work);assert not (work/'apparatus.json').exists()
    index=read(work/'cases.json');c=index['short/train-0'];results=[]
    with base.worker_lock(work),base.Guard(work):
        for variant in ('old51','stability-immediate','inhibitory-weight-off'):
            e,_,_=execute(create(variant,c,True),c,inputs(work,c,True),trace=False,calibration=True)
            parent=e.capture_state();p=index['history/s0/101/d1/AB'];hashes={}
            folder=work/'apparatus'/variant;folder.mkdir(parents=True)
            (folder/'parent.tmind').write_bytes(ArtifactCodec.encode(parent))
            for mode in ('observed','plain','restored','paused','partitioned'):
                e=create(variant,c,True,state=parent);e.reconfigure(replace(e.config,**p['patch']))
                e,points,_=execute(e,p,inputs(work,p,True),trace=False,mode=mode,calibration=True)
                hashes[mode]=e.capture_state().digest
            assert len(set(hashes.values()))==1,(variant,hashes)
            results.append({'variant':variant,'hashes':hashes})
        write(work/'apparatus.json',{'passed':True,'checks':results,'separate_encoding':True})
    print(json.dumps({'apparatus':True}),flush=True)

def run(work):
    check(work);assert read(work/'apparatus.json')['passed']
    assert not any((work/p).exists() for p in ('STOP','in-flight.json','summary.json'))
    import psutil
    index=read(work/'cases.json');results=[];began=time.monotonic()
    with base.worker_lock(work),base.Guard(work) as guard:
        write(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for variant in VARIANTS:
            for block in (0,1):
                for cue in ('train','AB','DB'):
                    assert guard.thread.is_alive()
                    if (work/'STOP').exists():return
                    assert base.resource_check(work)['safe']
                    assert time.monotonic()-began<7200
                    key=f'{variant}/{block}/{cue}';folder=work/'cases'/key;folder.mkdir(parents=True,exist_ok=False)
                    write(work/'in-flight.json',{'key':key,'pid':os.getpid(),'created':psutil.Process().create_time()})
                    c=index[f'short/train-{block}' if cue=='train' else f'history/s{block}/101/d1/{cue}']
                    parent=None if cue=='train' else ArtifactCodec.decode((work/'cases'/variant/str(block)/'train/final.tmind').read_bytes())
                    e=create(variant,c,state=parent)
                    if parent is not None:e.reconfigure(replace(e.config,**c['patch']))
                    initial=e.capture_state();(folder/'initial.tmind').write_bytes(ArtifactCodec.encode(initial))
                    t=time.monotonic();e,points,trace=execute(e,c,inputs(work,c))
                    final=e.capture_state();(folder/'final.tmind').write_bytes(ArtifactCodec.encode(final))
                    assert ArtifactCodec.decode((folder/'final.tmind').read_bytes()).digest==final.digest
                    packed(folder/'process.json.gz',points if cue!='train' else trace)
                    q={} if cue=='train' else measure.process(c,points)
                    q.update(key=key,variant=variant,block=block,cue=cue,kernel=final.to_dict()['dynamics'],
                         initial_sha256=initial.digest,final_sha256=final.digest,parent_sha256=parent.digest if parent else None,
                         time_us=e.time_us,wall_seconds=time.monotonic()-t)
                    write(folder/'result.json',q);results.append(q)
                    base.atomic_json(work/'current.json',{'complete':len(results),'total':54,'last':key,'wall_seconds':time.monotonic()-began})
                    (work/'in-flight.json').unlink()
                    print(json.dumps({'complete':len(results),'key':key,'margin':q.get('signed_peak'),'seconds':q['wall_seconds']}),flush=True)
                    del e;gc.collect()
                margins=[r['signed_peak'] for r in results[-2:]]
                if variant=='old51':
                    expected=read(work/'reference-peaks.json')['blocks'][block]['margins']
                    assert all(abs(a-b)<1e-9 for a,b in zip(margins,expected)),('positive reference',margins,expected)
                if variant=='stability-immediate':
                    assert all(abs(a-b)<1e-12 for a,b in zip(margins,(.0009972873948763047,-.0009973317550409089))),('6.2 reference',margins)
                assert sum(p.stat().st_size for p in work.rglob('*') if p.is_file())<2**30
        write(work/'summary.json',{'stages':len(results),'results':results,'wall_seconds':time.monotonic()-began})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','check','apparatus','run'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
