"""Bounded, alternating native benchmarks; engineering subjects only."""
import argparse
import ctypes
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]


def resources():
    import psutil
    class Performance(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong)] + [(name, ctypes.c_size_t) for name in (
            'CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal', 'PhysicalAvailable',
            'SystemCache', 'KernelTotal', 'KernelPaged', 'KernelNonpaged', 'PageSize')] + [
            (name, ctypes.c_ulong) for name in ('HandleCount', 'ProcessCount', 'ThreadCount')]
    p = Performance(); p.cb = ctypes.sizeof(p)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(p), p.cb):
        raise OSError('GetPerformanceInfo failed')
    values = {'commit': (p.CommitLimit-p.CommitTotal)*p.PageSize,
              'ram': psutil.virtual_memory().available,
              'c': psutil.disk_usage('C:/').free, 'e': psutil.disk_usage('E:/').free}
    for key, reserve in zip(('commit', 'ram', 'c', 'e'), (5, 4, 5, 25)):
        if values[key] < reserve*2**30:
            raise RuntimeError(f'insufficient {key}: {values[key]/2**30:.2f} GiB')
    return values


def worker(q):
    import psutil
    from _threemind_native import NativeLocal61, NativeLocal63
    from threemind_core import Stimulus
    from threemind_kernels.local61_config import Local61Config
    from threemind_kernels.local63_config import Local63Config
    n = q['nodes']; variant = q['variant']
    config = dict(seed=9291299, quiescence_death_us=10**12)
    if variant == '61':
        c = Local61Config(**config); cls = NativeLocal61
    else:
        c = Local63Config(**config, resource_precheck_enabled=variant=='precheck',
                         subthreshold_expiry_enabled=q.get('expiry', False), inhibition_updates_usage=True,
                         inhibition_bypasses_resources=False)
        cls = NativeLocal63
    if q['topology'] == 'dense':
        course = [Stimulus(0, tuple((60000+i, .3) for i in range(n)))]
    else:
        course = [Stimulus(0, ((60000+i, .3), (60000+i+1, .3))) for i in range(0, n, 2)]
    course += [Stimulus(i*500000, tuple((60000+(i*3+j)%n, .4) for j in range(4)))
               for i in range(1, 120)]
    payloads = [json.dumps(s.to_dict()) for s in course]
    e = cls(json.dumps(c.to_dict()), None); gc.collect()
    wall, cpu = time.perf_counter(), time.process_time()
    for s in payloads: e.inject(s)
    e.advance('60000000', False, False)
    elapsed, cpu_elapsed = time.perf_counter()-wall, time.process_time()-cpu
    saved_at = time.perf_counter(); encoded = e.state_json(); saving = time.perf_counter()-saved_at
    state = json.loads(encoded)
    for k in ('schema', 'dynamics', 'definition', 'definition_hash', 'config'): state.pop(k)
    normalized = json.dumps(state, sort_keys=True, separators=(',', ':')).encode()
    mem = psutil.Process().memory_info()
    return q | {'wall_seconds': elapsed, 'cpu_seconds': cpu_elapsed, 'save_seconds': saving,
                'peak_commit_bytes': mem.peak_pagefile, 'snapshot_bytes': len(encoded.encode()),
                'events': state['sequence'], 'edges': len(state['edges']),
                'state_sha256': hashlib.sha256(normalized).hexdigest()}


def run(output, expiry=False):
    if output.exists(): raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []; checks = []
    for n in (32, 128):
        for topology in ('sparse', 'dense'):
            for trial in range(6):
                order = ('61', 'compatible', 'precheck') if trial%2==0 else ('precheck', 'compatible', '61')
                batch = {}
                for variant in order:
                    checks.append(resources())
                    q = {'nodes': n, 'topology': topology, 'variant': variant, 'trial': trial, 'expiry': expiry}
                    p = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()),
                                        '--worker', json.dumps(q)], capture_output=True, text=True,
                                       encoding='utf8', timeout=120, check=True, cwd=ROOT)
                    row = json.loads(p.stdout); rows.append(row); batch[variant] = row
                if not expiry and batch['61']['state_sha256'] != batch['compatible']['state_sha256']:
                    raise AssertionError({'numerical_mismatch': batch})
                print(json.dumps({'nodes': n, 'topology': topology, 'trial': trial,
                                  'seconds': {k:v['wall_seconds'] for k,v in batch.items()}}), flush=True)
                output.with_suffix('.progress.json').write_text(json.dumps({'trials': rows}, indent=2), 'utf8')
    summaries = []
    for n in (32, 128):
        for topology in ('sparse', 'dense'):
            summary = {'nodes': n, 'topology': topology}
            for variant in ('61', 'compatible', 'precheck'):
                sample = [r for r in rows if r['nodes']==n and r['topology']==topology
                          and r['variant']==variant and r['trial']>0]
                summary[variant] = {key:statistics.median(r[key] for r in sample) for key in (
                    'wall_seconds', 'cpu_seconds', 'save_seconds', 'snapshot_bytes', 'peak_commit_bytes')}
            summary['precheck_ratio'] = summary['precheck']['wall_seconds']/summary['compatible']['wall_seconds']
            summary['compatible_vs61'] = summary['compatible']['wall_seconds']/summary['61']['wall_seconds']
            summaries.append(summary)
    ratio = math.exp(statistics.mean(math.log(s['precheck_ratio']) for s in summaries))
    result = {'expiry_enabled': expiry, 'same_compatible_numerical_states': None if expiry else True,
              'results': summaries, 'trials': rows,
              'resource_checks': checks, 'geometric_precheck_ratio': ratio,
              'substantial_improvement_requires_repeat': ratio <= .8 and max(s['precheck_ratio'] for s in summaries) <= 1.2}
    output.write_text(json.dumps(result, indent=2), 'utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('trials', 'resource_checks')}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--worker'); p.add_argument('--output', type=Path)
    p.add_argument('--expiry-enabled', action='store_true')
    a = p.parse_args()
    if a.worker: print(json.dumps(worker(json.loads(a.worker))))
    else: run(a.output, a.expiry_enabled)
