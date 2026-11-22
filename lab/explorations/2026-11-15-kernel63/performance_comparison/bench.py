"""Serial, bounded engineering comparison; never changes production kernels."""
import argparse
import gc
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/kernel63-performance-20261115'
sys.path.insert(0, str(HERE.parent / 'default_alignment'))
from benchmark import resources

CASES = {
    'native-sparse128': ('native', 'sparse', 128, 120),
    'native-dense128': ('native', 'dense', 128, 120),
    'native-sparse512': ('native', 'sparse', 512, 120),
    'native-weak128': ('native', 'weak', 128, 120),
    'python-sparse32': ('reference', 'sparse', 32, 20),
    'python-weak32': ('reference', 'weak', 32, 20),
}
VARIANTS = ('61', '63', '63-compatible')
METRICS = ('advance_seconds', 'enqueue_seconds', 'observe_seconds', 'save_seconds', 'restore_seconds')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inputs(case):
    from threemind_core import Stimulus
    backend, kind, n, seconds = CASES[case]
    if kind == 'weak':
        rows = []
        for i in range(seconds * 10):
            t = i * 100000
            if i % 5 == 0:
                rows.append(Stimulus(t, ((90000, .3),)))
            for j in range(4):
                rows.append(Stimulus(t, ((60000+(4*i+j)%n, .0001),)))
    else:
        rows = ([Stimulus(0, tuple((60000+i, .3) for i in range(n)))] if kind == 'dense' else
                [Stimulus(0, ((60000+i, .3), (60000+i+1, .3))) for i in range(0, n, 2)])
        rows += [Stimulus(i*500000, tuple((60000+(i*3+j)%n, .4) for j in range(4)))
                 for i in range(1, seconds*2)]
    return rows, seconds * 1000000


def numerical(state):
    state = dict(state)
    for key in ('schema', 'dynamics', 'config', 'definition', 'definition_hash'):
        state.pop(key)
    return sha(json.dumps(state, sort_keys=True, separators=(',', ':')).encode())


def worker(q):
    import psutil
    from threemind_kernels.registry import resolve_kernel
    from threemind_kernels.local63_config import Local63Config
    variant, case = q['variant'], q['case']
    backend = CASES[case][0]
    descriptor = resolve_kernel('threemind.continuous-memory/' + ('6.1' if variant == '61' else '6.3'))
    config = Local63Config(subthreshold_expiry_enabled=False) if variant == '63-compatible' else None
    course, until = inputs(case)
    input_hash = sha(json.dumps([s.to_dict() for s in course], sort_keys=True).encode())
    process = psutil.Process()
    baseline_commit = process.memory_info().pagefile
    engine = None
    times = []
    for _ in range(q['repeats']):
        engine = None
        gc.collect()
        start = time.perf_counter(); engine = descriptor.create(config, backend=backend)
        birth = time.perf_counter() - start
        start = time.perf_counter()
        for stimulus in course: engine.inject(stimulus)
        enqueue = time.perf_counter() - start
        start, cpu = time.perf_counter(), time.process_time()
        engine.advance_to(until)
        times.append({'birth_seconds': birth, 'enqueue_seconds': enqueue,
                      'advance_seconds': time.perf_counter()-start,
                      'advance_cpu_seconds': time.process_time()-cpu})
    advancement_memory = process.memory_info()
    before = engine.capture_state()
    d = before.to_dict()
    operation_times = {}
    for name, operation in (
        ('observe_seconds', engine.observation_nodes),
        ('save_seconds', engine.capture_state),
        ('restore_seconds', lambda: descriptor.create(state=before, backend=backend)),
    ):
        samples = []
        for _ in range(5):
            gc.collect()
            start = time.perf_counter(); result = operation(); samples.append(time.perf_counter()-start)
            if name == 'restore_seconds':
                assert result.capture_state().digest == before.digest
            result = None
        operation_times[name] = samples
    assert engine.capture_state().digest == before.digest, 'observation or storage mutated state'
    output = WORK / q['state_file']
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f: f.write(gzip.compress(before.payload, mtime=0))
    return q | {key: statistics.mean(r[key] for r in times) for key in times[0]} | {
        key: statistics.median(values) for key, values in operation_times.items()
    } | {'raw_timings': times, 'operation_timings': operation_times, 'input_sha256': input_hash,
         'numerical_sha256': numerical(d), 'state_sha256': before.digest,
         'snapshot_bytes': len(before.payload), 'baseline_commit_bytes': baseline_commit,
         'advance_peak_commit_bytes': advancement_memory.peak_pagefile,
         'total_peak_commit_bytes': process.memory_info().peak_pagefile,
         'nodes': len(d['nodes']), 'edges': len(d['edges']), 'sequence': d['sequence'],
         'time_us': d['time_us'], 'life': d['life'], 'audit': d['audit'],
         'transport': d['transport'], 'timer_count': len(d['timers'])}


def guarded(q):
    resources()
    inflight = WORK / 'in-flight.json'
    if inflight.exists(): raise RuntimeError('previous incomplete engineering worker; inspect before continuing')
    inflight.write_text(json.dumps(q, indent=2), 'utf8')
    start = time.monotonic()
    p = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), '--worker', json.dumps(q)],
                         cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf8')
    checks, pressure = [], None
    while True:
        try:
            out, err = p.communicate(timeout=1)
            break
        except subprocess.TimeoutExpired:
            try: checks.append(resources())
            except Exception as exc: pressure = str(exc)
            if time.monotonic()-start > 180:
                p.kill(); out, err = p.communicate()
                (WORK/'worker-timeout.txt').write_text(err+'\n'+out, 'utf8')
                raise TimeoutError(q)
    if p.returncode:
        (WORK/'worker-error.txt').write_text(err+'\n'+out, 'utf8')
        raise RuntimeError(f'worker failed: {q}; {err[-1800:]}')
    row = json.loads(out)
    row['resource_checks'] = checks
    with (WORK/'rows.jsonl').open('a', encoding='utf8') as f: f.write(json.dumps(row)+'\n')
    inflight.unlink()  # A complete result and complete state have both been saved.
    if pressure: raise RuntimeError('Complete boundary resource pause: '+pressure)
    return row


def interval(rows, case, metric, numerator='63', denominator='61', phase=None):
    pairs = {}
    for row in rows:
        if row['case'] == case and row['phase'] in ('main', 'confirmation') and row['trial'] > 0 and (phase is None or row['phase'] == phase):
            pairs.setdefault((row['phase'], row['trial']), {})[row['variant']] = row[metric]
    ratios = [v[numerator]/v[denominator] for v in pairs.values() if numerator in v and denominator in v]
    logs = [math.log(v) for v in ratios]
    rng = random.Random(6331061)
    boot = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(2000))
    return {'ratio': math.exp(statistics.mean(logs)), 'low': boot[49], 'high': boot[1949],
            'rounds': len(logs), 'paired_ratios': ratios}


def rows():
    return [json.loads(line) for line in (WORK/'rows.jsonl').read_text('utf8').splitlines()]


def freeze():
    import _threemind_native
    WORK.mkdir(exist_ok=False)
    paths = [HERE/'protocol.zh.md', HERE/'protocol.en.md', Path(__file__), Path(_threemind_native.__file__)]
    for version in ('61', '63'):
        paths.extend((ROOT/'src/threemind_kernels').glob(f'local{version}*.py'))
        paths.extend((ROOT/'crates/threemind-core/src').glob(f'local{version}*'))
    manifest = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}
    (WORK/'manifest.json').write_text(json.dumps(manifest, indent=2), 'utf8')


def run(phase):
    if phase == 'main':
        freeze()
        cases = list(CASES)
        counts = {}
        for case in cases:
            q = {'case': case, 'variant': '61', 'phase': 'calibration', 'trial': 0, 'repeats': 1,
                 'state_file': f'states/calibration-{case}.json.gz'}
            measured = guarded(q)
            counts[case] = min(20, max(1, math.ceil(.75/measured['advance_seconds'])))
        (WORK/'repeat-counts.json').write_text(json.dumps(counts, indent=2), 'utf8')
    else:
        for path, expected in json.loads((WORK/'manifest.json').read_text('utf8')).items():
            assert sha((ROOT/path).read_bytes()) == expected, path
        counts = json.loads((WORK/'repeat-counts.json').read_text('utf8'))
        cases = json.loads((WORK/'confirmation-cases.json').read_text('utf8'))
        if any(r['phase'] == 'confirmation' for r in rows()): raise RuntimeError('confirmation already started')
    start = time.monotonic()
    for case in cases:
        for trial, order in enumerate([VARIANTS]+list(itertools.permutations(VARIANTS))):
            result = {}
            for variant in order:
                q = {'case': case, 'variant': variant, 'phase': phase, 'trial': trial, 'repeats': counts[case],
                     'state_file': f'states/{phase}-{case}-{trial}-{variant}.json.gz'}
                result[variant] = guarded(q)
                if time.monotonic()-start > 1200: raise RuntimeError('Complete-boundary time budget reached')
            assert len({r['input_sha256'] for r in result.values()}) == 1
            assert result['61']['numerical_sha256'] == result['63-compatible']['numerical_sha256'], ('compatibility mismatch', case, trial)
            print(json.dumps({'phase': phase, 'case': case, 'trial': trial,
                              'advance_seconds': {k: round(r['advance_seconds'], 6) for k, r in result.items()}}), flush=True)
    if phase == 'main':
        data = rows()
        need = []
        for case in cases:
            reasons = {}
            for metric in METRICS:
                estimate = interval(data, case, metric)
                if estimate['high'] >= 1.1: reasons[metric] = estimate
            for metric, absolute in (('advance_peak_commit_bytes', 2**20), ('snapshot_bytes', 4096)):
                a = statistics.median(r[metric] for r in data if r['case']==case and r['variant']=='61' and r['phase']=='main' and r['trial']>0)
                b = statistics.median(r[metric] for r in data if r['case']==case and r['variant']=='63' and r['phase']=='main' and r['trial']>0)
                if b/a >= 1.1 and b-a >= absolute: reasons[metric] = {'ratio': b/a, 'difference': b-a}
            if reasons:
                need.append(case)
                print(json.dumps({'confirmation_needed': case, 'reasons': reasons}), flush=True)
        (WORK/'confirmation-cases.json').write_text(json.dumps(need, indent=2), 'utf8')
    print(json.dumps({'completed': phase, 'cases': cases}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker'); parser.add_argument('--phase', choices=('main', 'confirmation'))
    args = parser.parse_args()
    if args.worker: print(json.dumps(worker(json.loads(args.worker))))
    else: run(args.phase)
