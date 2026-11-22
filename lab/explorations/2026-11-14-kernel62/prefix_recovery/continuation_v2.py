"""Boundary continuation: stream passive task traces instead of retaining full graphs."""
import argparse
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
import importlib.util
_spec=importlib.util.spec_from_file_location('r51t7_study',Path(__file__).with_name('study.py'))
s=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(s)
from threemind_core import Stimulus
from threemind_runtime import ArtifactCodec


class Trace:
    def __init__(self,path):self.file=gzip.open(path,'xb',compresslevel=1);self.count=0
    def append(self,e):
        d=e.capture_state().to_dict();ids={n['id']:n['channel'] for n in d['nodes']}
        targets=set(s.measure.TOKENS.values())
        nodes=[n for n in e.observation_nodes() if n['channel'] in targets]
        fields=('weight','stability','eligibility','decay_age','last_pass_us','completed_period_us','short_term','fast')
        edges=[{'source':ids[r['source']],'target':ids[r['target']],**{k:r[k] for k in fields if k in r}}
               for r in d['edges'] if ids[r['source']] in targets and ids[r['target']] in targets]
        row={'time_us':e.time_us,'nodes':nodes,'edges':edges,'transport':d.get('transport',{})}
        self.file.write(json.dumps(row,sort_keys=True).encode()+b'\n');self.count+=1
    def close(self):self.file.close()


def execute(engine,case,rows,trace=None):
    index=0;points=[];probe=case.get('probe_start_us');next_point=probe;started=False;wall=time.monotonic()
    def observe():return {'time_us':engine.time_us,'nodes':[n for n in engine.observation_nodes() if n['channel'] in s.measure.TOKENS.values()]}
    while True:
        assert time.monotonic()-wall<300,'stage wall limit; preserve in-flight'
        if probe==engine.time_us and not started:points.append(observe())
        while index<len(rows) and int(rows[index]['source_policy']['resolved_at_us'])==engine.time_us:
            engine.inject(Stimulus.from_dict(rows[index]['stimulus']));index+=1
        engine.advance_to(engine.time_us)
        if probe==engine.time_us and not started:
            started=True;points.append(observe());next_point+=10000
        elif started and engine.time_us==next_point:
            points.append(observe());next_point+=10000
        if trace is not None and probe is None:trace.append(engine)
        if engine.time_us==case['end_us']:break
        times=[case['end_us'],engine.time_us+100000]
        if index<len(rows):times.append(int(rows[index]['source_policy']['resolved_at_us']))
        if next_point is not None:times.append(next_point)
        target=min(times);assert target>engine.time_us;engine.advance_to(target)
        assert engine.life!='dead'
    assert index==len(rows)
    return points


def prepare(work):
    assert not (work/'in-flight.json').exists()
    assert s.read(work/'current.json')['complete']==1
    assert not (work/'source-amendment-v2.json').exists()
    state=ArtifactCodec.decode((work/'cases/old51/0/train/final.tmind').read_bytes())
    assert state.digest==s.read(work/'cases/old51/0/train/result.json')['final_sha256']
    assert state.to_dict()['time_us']=='212200000'
    stop=(work/'STOP').read_bytes();assert s.read(work/'STOP')['reason']=='pilot process private memory exceeds 1 GiB'
    files=[Path(__file__),s.HERE/'instrument-amendment.zh.md',s.ROOT/'src/threemind_kernels/local62.py',s.ROOT/'crates/threemind-core/src/local62_transitions.rs']
    source={str(p.relative_to(s.ROOT)):s.sha(p) for p in files}
    for rel in source:
        p=work/'frozen-source-v2'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s.ROOT/rel,p)
    import _threemind_native
    dll=next(Path(_threemind_native.__file__).parent.glob('*.pyd'))
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client)
        rec.resume_recording()
        rec.text({'identity':str(uuid5(s.NS,'instrument-v2-doc')),'request_id':str(uuid5(s.NS,'instrument-v2')),'expected_revision':0,
                  'kind':'note','title':'R51t7 observation storage amendment','markdown':(s.HERE/'instrument-amendment.zh.md').read_text('utf8')})
        rec.synchronize(strict=True);assert rec.status['pending']==0
    with s.base.worker_lock(work):
        assert not (work/'in-flight.json').exists() and (work/'STOP').read_bytes()==stop
        assert s.base.resource_check(work)['safe']
        # Exactly this completed-boundary STOP is archived before retirement.
        archive=work/'resumptions/observation-v2';archive.mkdir(parents=True)
        (archive/'STOP.json').write_bytes(stop)
        s.write(work/'source-amendment-v2.json',{'sources':source,'native_path':str(dll),'native_sha256':s.sha(dll),
                    'parent_sha256':state.digest,'completed_stages':1,'scientific_rollback':False,'production_dynamics_changed':False})
        (work/'STOP').unlink()
    print('Prepared exact complete-boundary continuation',flush=True)


def check(work):
    f=s.read(work/'frozen.json');a=s.read(work/'source-amendment-v2.json')
    for rel,h in (f['sources']|a['sources']).items():assert s.sha(s.ROOT/rel)==h,rel
    for rel,h in f['materials'].items():assert s.sha(work/rel)==h,rel
    assert s.sha(Path(a['native_path']))==a['native_sha256']


def run(work):
    check(work);assert not any((work/p).exists() for p in ('STOP','in-flight.json','summary.json'))
    import psutil
    index=s.read(work/'cases.json');results=[];began=time.monotonic()
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host-v2.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for variant in s.VARIANTS:
            for block in (0,1):
                for cue in ('train','AB','DB'):
                    key=f'{variant}/{block}/{cue}';folder=work/'cases'/key
                    if (folder/'result.json').exists():
                        q=s.read(folder/'result.json');assert ArtifactCodec.decode((folder/'final.tmind').read_bytes()).digest==q['final_sha256']
                        results.append(q);continue
                    if (work/'STOP').exists():return
                    assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
                    assert time.monotonic()-began<7200
                    folder.mkdir(parents=True,exist_ok=False)
                    s.write(work/'in-flight.json',{'key':key,'pid':os.getpid(),'created':psutil.Process().create_time()})
                    c=index[f'short/train-{block}' if cue=='train' else f'history/s{block}/101/d1/{cue}']
                    parent=None if cue=='train' else ArtifactCodec.decode((work/'cases'/variant/str(block)/'train/final.tmind').read_bytes())
                    e=s.create(variant,c,state=parent)
                    if parent is not None:e.reconfigure(replace(e.config,**c['patch']))
                    initial=e.capture_state();(folder/'initial.tmind').write_bytes(ArtifactCodec.encode(initial))
                    trace=Trace(folder/'teaching.jsonl.gz') if cue=='train' else None
                    t=time.monotonic();points=execute(e,c,s.inputs(work,c),trace)
                    if trace:trace.close()
                    final=e.capture_state();(folder/'final.tmind').write_bytes(ArtifactCodec.encode(final))
                    assert ArtifactCodec.decode((folder/'final.tmind').read_bytes()).digest==final.digest
                    if cue!='train':s.packed(folder/'process.json.gz',points)
                    q={} if cue=='train' else s.measure.process(c,points)
                    q.update(key=key,variant=variant,block=block,cue=cue,kernel=final.to_dict()['dynamics'],
                       initial_sha256=initial.digest,final_sha256=final.digest,parent_sha256=parent.digest if parent else None,
                       time_us=e.time_us,wall_seconds=time.monotonic()-t)
                    s.write(folder/'result.json',q);results.append(q)
                    s.base.atomic_json(work/'current.json',{'complete':len(results),'total':54,'last':key,'wall_seconds':time.monotonic()-began})
                    (work/'in-flight.json').unlink()
                    print(json.dumps({'complete':len(results),'key':key,'margin':q.get('signed_peak'),'seconds':q['wall_seconds']}),flush=True)
                    del e,points;gc.collect()
                margins=[r['signed_peak'] for r in results[-2:]]
                if variant=='old51':
                    expected=s.read(work/'reference-peaks.json')['blocks'][block]['margins']
                    assert all(abs(a-b)<1e-9 for a,b in zip(margins,expected)),('positive reference',margins,expected)
                if variant=='stability-immediate':
                    assert all(abs(a-b)<1e-12 for a,b in zip(margins,(.0009972873948763047,-.0009973317550409089))),('6.2 reference',margins)
                assert sum(p.stat().st_size for p in work.rglob('*') if p.is_file())<2**30
        s.write(work/'summary.json',{'stages':len(results),'results':results,'wall_seconds':time.monotonic()-began})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','check','run'));p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();globals()[a.action](a.work)
