"""Bounded engineering gate; no old specimen or scientific course is resumed."""
import argparse
import ctypes
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / '.work/native60-birth/python'), str(ROOT / 'src'),
                str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import pilot_m2 as base
import psutil

from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.inheritance import birth

KERNELS = ('threemind.continuous-memory/5.1', 'threemind.continuous-memory/6.0')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def allocated(path):
    high = ctypes.c_ulong(0)
    fn = ctypes.WinDLL('kernel32', use_last_error=True).GetCompressedFileSizeW
    fn.argtypes = (ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong))
    fn.restype = ctypes.c_ulong
    ctypes.set_last_error(0)
    low = fn(str(path), ctypes.byref(high))
    if low == 0xffffffff and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    return (high.value << 32) | low


def blob(path, data):
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return {'sha256': sha(path), 'logical_bytes': len(data), 'allocated_bytes': allocated(path)}


def boundary(work):
    if (work / 'STOP').exists():
        raise InterruptedError('complete-boundary stop')
    base.resource_check(work)


def measure(fn):
    wall, cpu = time.perf_counter_ns(), time.process_time_ns()
    result = fn()
    return result, {'wall_s': (time.perf_counter_ns()-wall)/1e9, 'cpu_s': (time.process_time_ns()-cpu)/1e9}


def trial(work, key, kernel, pairs, passive, seconds):
    boundary(work)
    folder = work / key
    folder.mkdir(parents=True, exist_ok=False)
    proc = psutil.Process()
    base.original(work / 'in-flight.json', {'key': key, 'pid': proc.pid, 'created': proc.create_time()})
    descriptor = resolve_kernel(kernel)
    cfg = descriptor.configuration({'quiescence_death_us': 10**12})
    e = descriptor.create(cfg, backend='native')
    def setup():
        for i in range(pairs):
            e.inject(Stimulus(0, ((2*i+1, .8), (2*i+2, .8))))
        e.advance_to(0)
        if passive:
            e.intervene(nodes=list(range(1, 2*pairs+1)), action='silence')
    _, construction = measure(setup)
    before = e.capture_state()
    first = before.to_dict()
    files = {'initial': blob(folder / 'initial.tmind', ArtifactCodec.encode(before, 'tmind'))}
    host_before = base.resource_check(work)
    busy_before = psutil.cpu_times()._asdict()
    _, advance = measure(lambda: e.advance_to(seconds*1000000))
    busy_after = psutil.cpu_times()._asdict()
    state, capture = measure(e.capture_state)
    data, serialization = measure(lambda: ArtifactCodec.encode(state, 'tmind'))
    files['final'] = blob(folder / 'final.tmind', data)
    assert ArtifactCodec.decode(data).digest == state.digest == e.capture_state().digest
    last = state.to_dict()
    result = {'key': key, 'kernel': kernel, 'pairs': pairs, 'silenced': passive, 'internal_seconds': seconds,
                  'construction': construction, 'advance': advance, 'capture': capture, 'serialization': serialization,
                  'config': cfg.to_dict(), 'start_counts': [len(first['nodes']), len(first['edges'])],
                  'final_counts': [len(last['nodes']), len(last['edges'])], 'end_us': last['time_us'],
                  'initial_state': before.digest, 'final_state': state.digest, 'files': files,
                  'private_bytes': proc.memory_info().private, 'host_before': host_before,
                  'host_after': base.resource_check(work), 'cpu_before': busy_before, 'cpu_after': busy_after}
    base.original(folder / 'result.json', result)
    (work / 'in-flight.json').unlink()
    base.atomic_json(work / 'current.json', {'complete': key, 'final_state': state.digest})
    print(json.dumps({'key': key, 'advance': advance, 'counts': result['final_counts']}), flush=True)
    return result


def comparison(rows):
    groups = [[r for r in rows if r['kernel'] == k] for k in KERNELS]
    out = {}
    for dimension in ('advance', 'capture', 'serialization'):
        out[dimension] = {}
        for clock in ('wall_s', 'cpu_s'):
            med = [statistics.median(r[dimension][clock] for r in group) for group in groups]
            out[dimension][clock] = {'medians': med, 'ratio': med[1]/med[0] if med[0] else None}
    out['comparable_graphs'] = len({tuple(r['start_counts']+r['final_counts']) for r in rows}) == 1
    out['disk_ratio'] = statistics.median(r['files']['final']['allocated_bytes'] for r in groups[1]) / max(
        1, statistics.median(r['files']['final']['allocated_bytes'] for r in groups[0]))
    return out


def run(work):
    if work.exists():
        raise RuntimeError('fresh engineering directory required; inspect existing boundaries, never replay')
    base.resource_check(work)
    work.mkdir(parents=True)
    with base.worker_lock(work), base.Guard(work) as guard:
        import _threemind_native as native
        assert Path(native.__file__).parent == ROOT / '.work/native60-birth/python'
        implementation = base.capture_implementation('reference')
        implementation.update(backend='native', native_binary_sha256=sha(native.__file__), native_path=native.__file__)
        base.original(work/'implementation.json', implementation)
        manifest = {p.name: sha(p) for p in (Path(__file__), HERE/'foundation-protocol.zh.md', HERE/'foundation-protocol.en.md')}
        base.original(work/'frozen.json', {'manifest': manifest, 'native_path': native.__file__, 'native_sha256': sha(native.__file__),
                     'git_head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                     'engineering_only': True, 'runtime_sha256': sha(ROOT/'.work/native60-birth/release/threemind-runtime.exe')})
        for path in (Path(__file__), HERE/'foundation-protocol.zh.md', HERE/'foundation-protocol.en.md'):
            blob(work/path.name, path.read_bytes())
        results = []
        stop = False
        for pairs in (512, 4096):
            for passive in (False, True):
                name = f'n{pairs*2}-'+('quiet' if passive else 'active')
                for k in KERNELS:
                    trial(work, name+'/warmup/'+k.rsplit('/',1)[1], k, pairs, passive, 1)
                rows = []
                for repeat in range(5):
                    for k in KERNELS[::1 if repeat%2 == 0 else -1]:
                        rows.append(trial(work, f'{name}/r{repeat}/'+k.rsplit('/',1)[1], k, pairs, passive, 10))
                summary = comparison(rows)
                ratios = [summary['advance'][clock]['ratio'] for clock in ('wall_s', 'cpu_s')]
                suspicious = any(r is not None and r >= 2 for r in ratios) or summary['disk_ratio'] >= 2
                confirmation = None
                if suspicious:
                    seconds = 100 if min(summary['advance']['wall_s']['medians']) < .01 else 10
                    again = []
                    for repeat in range(5):
                        for k in KERNELS[::-1 if repeat%2 == 0 else 1]:
                            again.append(trial(work, f'{name}/confirm{repeat}/'+k.rsplit('/',1)[1], k, pairs, passive, seconds))
                    confirmation = comparison(again)
                    stop = confirmation['comparable_graphs'] and (
                        all(confirmation['advance'][c]['ratio'] is not None and confirmation['advance'][c]['ratio'] >= 2
                            for c in ('wall_s','cpu_s')) or confirmation['disk_ratio'] >= 2)
                results.append({'condition': name, 'initial': summary, 'confirmation': confirmation, 'stop': stop})
                base.original(work/(name+'-comparison.json'), results[-1])
                if stop:
                    break
            if stop:
                break
        output = {'engineering_only': True, 'state': 'paused-performance' if stop else 'foundation-cost-passed',
                      'comparisons': results, 'peak_private': guard.peak_private, 'minimum_resources': guard.minimum}
        base.original(work/'summary.json', output)
        if stop:
            base.original(work/'STOP', {'reason': 'registered comparable performance/storage gate', 'summary': 'summary.json'})
        print(json.dumps(output), flush=True)


def history_witness(output):
    """Execute both birth functions on new fixtures; never open historical individuals."""
    source = subprocess.check_output(['git','show','a84bafda:src/threemind_runtime/inheritance.py'], cwd=ROOT)
    old = types.ModuleType('frozen_birth_before_60')
    exec(compile(source, 'a84bafda:inheritance.py', 'exec'), old.__dict__)
    rows = []
    for version in ('1', '2', '3', '3.1', '4', '5', '5.1'):
        k = 'threemind.continuous-memory/'+version
        try:
            descriptor = resolve_kernel(k)
        except ValueError:
            continue
        for backend in ('reference','native'):
            engine = descriptor.create(backend=backend)
            engine.inject(Stimulus(0, ((19,.8),(62,.7))))
            engine.advance_to(211337)
            saved = engine.capture_state()
            before, after = old.birth(saved), birth(saved)
            assert before.digest == after.digest
            assert engine.capture_state().digest == saved.digest
            rows.append({'kernel': k,'backend': backend,'birth_digest': after.digest,'parent_unchanged': True})
    base.original(output, {'frozen_commit': 'a84bafda', 'source_sha256': hashlib.sha256(source).hexdigest(), 'rows': rows})
    print(json.dumps({'historical_birth_comparisons': len(rows), 'passed': True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('benchmark','historical'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    (run if args.command == 'benchmark' else history_witness)(args.output.resolve())
