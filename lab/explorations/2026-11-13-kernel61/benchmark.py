"""Bounded R51c engineering trials. No historical subject is loaded or changed."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT/'src'), str(HERE.parent/'2026-11-13-kernel60-revalidation')]
import support as f

VARIANTS = [
    ('51', '5.1', {}), ('60', '6.0', {}),
    ('61-global-zero', '6.1', dict(deletion_strategy='global-scan', activation_send_threshold=0, inhibition_send_threshold=0)),
    ('61-local-zero', '6.1', dict(activation_send_threshold=0, inhibition_send_threshold=0)),
    ('61-global', '6.1', dict(deletion_strategy='global-scan')),
    ('61-local', '6.1', {}),
]


def run(work, module):
    sys.path.insert(0, str(module))
    import _threemind_native as native
    import psutil
    from threemind_core import Stimulus
    from threemind_kernels.registry import resolve_kernel
    from threemind_runtime import ArtifactCodec
    assert Path(native.__file__).parent.resolve() == module.resolve()
    assert (work/'registration.json').exists(), 'Register before timing'
    root = work/'trials'
    assert not root.exists(), 'Never clear or blindly restart an incomplete batch'
    f.base.resource_check(work)
    root.mkdir()
    sources = {p.relative_to(ROOT).as_posix(): f.sha(p)
               for folder in ('src/threemind_kernels', 'crates/threemind-core/src')
               for p in (ROOT/folder).glob('*') if p.is_file() and '61' in p.name}
    frozen = {'sources':sources, 'module_sha256':f.sha(native.__file__), 'module_path':native.__file__,
              'protocol_sha256':f.sha(HERE/'protocol.md'), 'runner_sha256':f.sha(__file__)}
    f.base.original(work/'frozen.json', frozen)
    rows=[]
    with f.base.worker_lock(work), f.base.Guard(work):
        for pairs, repeats in ((512,5), (2048,3)):
            for repeat in range(repeats):
                order = VARIANTS if repeat%2 == 0 else list(reversed(VARIANTS))
                for label,version,overrides in order:
                    f.base.resource_check(work)
                    assert not (work/'STOP').exists(), 'STOP retained at complete boundary'
                    key=f'{pairs*2}-{repeat}-{label}'
                    folder=root/key; folder.mkdir()
                    proc=psutil.Process()
                    f.base.original(work/'in-flight.json', {'key':key,'pid':proc.pid,'created':proc.create_time()})
                    desc=resolve_kernel('threemind.continuous-memory/'+version)
                    engine=desc.create(desc.configuration({'quiescence_death_us':10**12}|overrides), backend='native')
                    for i in range(pairs): engine.inject(Stimulus(0,((2*i,.8),(2*i+1,.8))))
                    engine.advance_to(0)
                    initial=engine.capture_state()
                    f.blob(folder/'initial.tmind',ArtifactCodec.encode(initial))
                    mem_before=proc.memory_info().private
                    wall,cpu=time.perf_counter_ns(),time.process_time_ns()
                    engine.advance_to(10_000_000)
                    elapsed=(time.perf_counter_ns()-wall)/1e9; cpu=(time.process_time_ns()-cpu)/1e9
                    mem_after=proc.memory_info().private
                    final=engine.capture_state(); raw=ArtifactCodec.encode(final)
                    file=f.blob(folder/'final.tmind',raw)
                    assert ArtifactCodec.decode(raw).digest == final.digest == engine.capture_state().digest
                    doc=final.to_dict()
                    row={'key':key,'label':label,'kernel':version,'nodes':pairs*2,'repeat':repeat,
                         'wall_s':elapsed,'cpu_s':cpu,'file':file,'initial':initial.digest,'final':final.digest,
                         'private_before':mem_before,'private_after':mem_after,'timers':len(doc['timers']),
                         'audit':doc['audit'],'transport':doc['transport']}
                    f.base.original(folder/'result.json',row);rows.append(row)
                    (work/'in-flight.json').unlink()
                    f.base.atomic_json(work/'current.json',{'complete':key,'completed':len(rows),'expected':48})
                    print(json.dumps({'complete':key,'wall_s':elapsed}),flush=True)
                    del engine
    for name, expected in sources.items(): assert f.sha(ROOT/name)==expected, name
    f.base.original(work/'results.json',rows)
    groups=[]
    for n in (1024,4096):
        for label,_,_ in VARIANTS:
            rs=[r for r in rows if r['nodes']==n and r['label']==label]
            assert len({r['final'] for r in rs})==1
            groups.append({'nodes':n,'label':label,'repeats':len(rs),
                **{k:statistics.median(r[k] for r in rs) for k in ('wall_s','cpu_s','private_before','private_after','timers')},
                'file':rs[0]['file'],'audit':rs[0]['audit']})
    ratios={str(n):next(g['wall_s'] for g in groups if g['nodes']==n and g['label']=='61-local') /
                      next(g['wall_s'] for g in groups if g['nodes']==n and g['label']=='51') for n in (1024,4096)}
    f.base.original(work/'summary.json',{'trials':len(rows),'groups':groups,'ratio_to_51':ratios,
                                       'performance_gate_passed':all(v<2 for v in ratios.values())})
    print(json.dumps({'complete':True,'ratios':ratios}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--module',type=Path,required=True)
    a=p.parse_args();run(a.work.resolve(),a.module.resolve())
