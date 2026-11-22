"""Check the installed wheel against the frozen engineering states."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'src'))
import support as s


def check(work):
    import _threemind_native as native
    from threemind_core import Stimulus
    from threemind_kernels.registry import DEFAULT_KERNEL, resolve_kernel
    assert DEFAULT_KERNEL == 'threemind.continuous-memory/6.1'
    assert 'site-packages' in native.__file__
    expected = {r['key']: r for r in json.loads((work / 'results.json').read_bytes())}
    times = []
    guard_work = work / 'package-check'
    guard_work.mkdir(exist_ok=False)
    with s.base.worker_lock(work), s.base.Guard(guard_work):
        for nodes in (1024, 4096):
            for repeat in range(3):
                for version, label in (('5.1', '51'), ('6.0', '60'), ('6.1', '61-local')):
                    s.base.resource_check(work)
                    e = resolve_kernel('threemind.continuous-memory/' + version).create(
                        {'quiescence_death_us': 10**12}, backend='native')
                    for i in range(nodes // 2):
                        e.inject(Stimulus(0, ((2*i, .8), (2*i+1, .8))))
                    e.advance_to(0)
                    assert e.capture_state().digest == expected[f'{nodes}-0-{label}']['initial']
                    start = time.perf_counter_ns()
                    e.advance_to(10_000_000)
                    elapsed = (time.perf_counter_ns()-start)/1e9
                    assert e.capture_state().digest == expected[f'{nodes}-0-{label}']['final']
                    times.append({'nodes': nodes, 'label': label, 'repeat': repeat, 'wall_s': elapsed})
    medians = {f'{n}-{label}': statistics.median(r['wall_s'] for r in times if r['nodes']==n and r['label']==label)
               for n in (1024,4096) for label in ('51','60','61-local')}
    ratios={str(n):medians[f'{n}-61-local']/medians[f'{n}-51'] for n in (1024,4096)}
    assert all(v < 2 for v in ratios.values())
    result={'passed':True,'module':native.__file__,'module_sha256':s.sha(native.__file__),
            'matching_initial_and_final_states':36,'trials':times,'medians':medians,'ratio_to_51':ratios}
    s.base.original(work/'packaged-verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    check(p.parse_args().work.resolve())
