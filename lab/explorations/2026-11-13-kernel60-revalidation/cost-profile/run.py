"""Bounded engineering profiling with complete state equality checks."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(work, module, instrumented):
    sys.path[:0] = [str(module), str(ROOT/'src'), str(ROOT/'lab/explorations/2026-10-16-mechanism-discovery')]
    import _threemind_native as native
    import pilot_m2 as base
    import psutil
    from threemind_core import Stimulus
    from threemind_kernels.registry import resolve_kernel
    from threemind_runtime import ArtifactCodec

    assert Path(native.__file__).parent.resolve() == module.resolve()
    assert not work.exists(), 'Use a new registered engineering directory; do not clear in-flight.'
    base.resource_check(work.parent)
    work.mkdir(parents=True)
    base.original(work/'frozen.json', {'runner_sha256':sha(__file__), 'protocol_sha256':sha(HERE/'protocol.md'),
                                      'module':native.__file__, 'module_sha256':sha(native.__file__),
                                      'instrumented':instrumented, 'engineering_only':True})
    for p in (Path(__file__),HERE/'protocol.md',HERE/'prepare.py'):
        with (work/p.name).open('xb') as stream:
            stream.write(p.read_bytes())
    trials=[]
    if not instrumented:
        for repeat in range(5):
            variants=[('5.1',{}),('6.0',{}),('6.0',{'structure_check_interval_us':1000000}),
                      ('6.0',{'decay_curve':'exponential'}),
                      ('6.0',{'structure_check_interval_us':1000000,'decay_curve':'exponential'})]
            if repeat%2:variants.reverse()
            for version,config in variants:
                label='default' if not config else '-'.join(k+str(v) for k,v in sorted(config.items()))
                trials.append((f'r{repeat}-{version}-{label}',version,config,512,0,False))
        for repeat in range(3):
            for version in ('5.1','6.0')[::1 if repeat%2==0 else -1]:
                trials.append((f'scale{repeat}-{version}',version,{},2048,0,False))
    else:
        for repeat in range(3):
            for version in ('5.1','6.0'):
                for level in (0,1,2):
                    trials.append((f'r{repeat}-{version}-level{level}',version,{},512,level,False))
            trials.append((f'r{repeat}-6.0-segmented','6.0',{},512,1,True))
    results=[]
    with base.worker_lock(work), base.Guard(work):
        for key,version,config,pairs,level,segments in trials:
            if (work/'STOP').exists():raise RuntimeError('Resource STOP at complete boundary')
            base.resource_check(work)
            folder=work/key;folder.mkdir()
            proc=psutil.Process()
            base.original(work/'in-flight.json',{'key':key,'pid':proc.pid,'created':proc.create_time()})
            descriptor=resolve_kernel('threemind.continuous-memory/'+version)
            cfg=descriptor.configuration({'quiescence_death_us':10**12}|config)
            if instrumented:native.cost_profile_reset(0)
            e=descriptor.create(cfg,backend='native')
            for i in range(pairs):e.inject(Stimulus(0,((2*i,.8),(2*i+1,.8))))
            e.advance_to(0)
            initial=e.capture_state()
            assert [(n['id'],n['channel']) for n in initial.to_dict()['nodes']]==[(i,i) for i in range(2*pairs)]
            (folder/'initial.tmind').write_bytes(ArtifactCodec.encode(initial,'tmind'))
            chunks=[]
            for target in ((1000000,10000000) if segments else (10000000,)):
                if instrumented:native.cost_profile_reset(level)
                wall,cpu=time.perf_counter_ns(),time.process_time_ns()
                e.advance_to(target)
                timing={'wall_s':(time.perf_counter_ns()-wall)/1e9,'cpu_s':(time.process_time_ns()-cpu)/1e9,
                        'target_us':target}
                if instrumented:
                    timing['profile']=json.loads(native.cost_profile_report());native.cost_profile_reset(0)
                state=e.capture_state()
                timing['state']=state.digest;timing['audit']=state.to_dict()['audit']
                timing['transport']=state.to_dict()['transport']
                chunks.append(timing)
            final=e.capture_state(); raw=ArtifactCodec.encode(final,'tmind')
            (folder/'final.tmind').write_bytes(raw)
            assert ArtifactCodec.decode(raw).digest==final.digest==e.capture_state().digest
            row={'key':key,'version':version,'overrides':config,'nodes':2*pairs,'level':level,'segments':segments,
                 'initial':initial.digest,'final':final.digest,'chunks':chunks,
                 'wall_s':sum(r['wall_s'] for r in chunks),'cpu_s':sum(r['cpu_s'] for r in chunks),
                 'state_bytes':len(raw),'private_bytes':proc.memory_info().private}
            base.original(folder/'result.json',row);results.append(row)
            (work/'in-flight.json').unlink()
            base.atomic_json(work/'current.json',{'complete':key,'final':final.digest})
            print(json.dumps({'key':key,'wall_s':row['wall_s'],'cpu_s':row['cpu_s']}),flush=True)
        base.original(work/'results.json',results)
    print(json.dumps({'complete':True,'trials':len(results)}),flush=True)


def analyze(root):
    stocks=json.loads((root/'stock/results.json').read_bytes())
    ins=json.loads((root/'instrument/results.json').read_bytes())
    baselines={version:next(r['final'] for r in stocks if r['version']==version and r['nodes']==1024 and not r['overrides'])
               for version in ('5.1','6.0')}
    for row in ins:
        assert row['final']==baselines[row['version']], ('instrument changed state',row['key'])
    groups={}
    for kind,rows in (('stock',stocks),('instrument',ins)):
        for row in rows:
            key=json.dumps([kind,row['version'],row['nodes'],row['overrides'],row['level'],row['segments']],sort_keys=True)
            groups.setdefault(key,[]).append(row)
    summaries=[]
    for key,rows in groups.items():
        summaries.append({'condition':json.loads(key),'n':len(rows),'wall_s':statistics.median(r['wall_s'] for r in rows),
                          'cpu_s':statistics.median(r['cpu_s'] for r in rows),'state':rows[0]['final']})
    result={'instrument_exact_state_match':True,'instrument_trials':len(ins),'stock_trials':len(stocks),'groups':summaries}
    output=root/'summary.json'
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stock','instrument','analyze']);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--module',type=Path)
    args=p.parse_args()
    if args.action=='analyze':analyze(args.work.resolve())
    else:run(args.work.resolve(),args.module.resolve(),args.action=='instrument')
