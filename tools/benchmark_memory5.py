"""Bounded kernel engineering costs, not a consciousness learning experiment.

Build first: cargo build -p threemind-core --example memory5_costs --release --offline
All generated states/summaries stay in a fresh ignored .work directory.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import statistics
import subprocess
from pathlib import Path

from threemind_kernels.registry import resolve_kernel

ROOT = Path(__file__).resolve().parents[1]


def execute(command):
    """Measure process resources after exit; never poll or instrument Core."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
    row = json.loads(stdout)
    if os.name == 'nt':
        from ctypes import wintypes

        class MemoryCounters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    'peak_working_set', 'working_set', 'peak_paged_pool', 'paged_pool',
                    'peak_nonpaged_pool', 'nonpaged_pool', 'pagefile', 'peak_pagefile')]

        handle = wintypes.HANDLE(int(process._handle))
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
        get_memory.restype = wintypes.BOOL
        if not get_memory(handle, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError()
        clocks = [wintypes.FILETIME() for _ in range(4)]
        get_times = ctypes.windll.kernel32.GetProcessTimes
        get_times.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        get_times.restype = wintypes.BOOL
        if not get_times(handle, *(ctypes.byref(clock) for clock in clocks)):
            raise ctypes.WinError()
        row['process_cpu_s'] = sum((v.dwHighDateTime << 32) | v.dwLowDateTime for v in clocks[2:]) / 1e7
        row['process_peak_working_set_bytes'] = counters.peak_working_set
        row['process_peak_commit_bytes'] = counters.peak_pagefile
        # Includes construction, capture/encoding and validation; not Core-only RAM or CPU.
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--seconds', type=int, default=2)
    p.add_argument('--channels', type=int, nargs='+', default=[16, 32, 64])
    default_arms = ['2', '3.1', '4-h', '4-s', '5-h', '5-s']
    p.add_argument('--arms', nargs='+', choices=default_arms + ['5-h-manual', '5-no-h', '5.1-h', '5.1-s'])
    p.add_argument('--warmups', type=int, default=0,
                   help='Untimed fresh-fixture rounds before measured repetitions')
    p.add_argument('--executable', type=Path, default=ROOT / 'target/release/examples/memory5_costs.exe')
    p.add_argument('--pattern', choices=['dense', 'pairs', 'chain', 'burst'], default='dense',
                   help='Dense frames, disjoint pairs, overlapping ring pairs, or dense bursts with continuous empty frames')
    args = p.parse_args()
    if args.repeats < 1 or args.seconds < 1 or min(args.channels) < 1 or args.warmups < 0:
        p.error('repeats, seconds and channels must be positive; warmups must be nonnegative')
    if args.pattern == 'pairs' and any(n % 2 for n in args.channels):
        p.error('pairs requires even channel counts')
    if args.pattern == 'chain' and min(args.channels) < 2:
        p.error('chain requires at least two channels')
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / '.work'):
        raise ValueError('Use a fresh ignored .work directory')
    output.mkdir(parents=True, exist_ok=False)
    config = {}
    for arm, version, mode in [('2', '2', None), ('3.1', '3.1', None),
                               ('4-h', '4', 'adaptive-half-life'), ('4-s', '4', 'legacy-stability'),
                               ('5-h', '5', 'adaptive-half-life'), ('5-s', '5', 'legacy-stability'),
                               ('5-h-manual', '5', 'adaptive-half-life'), ('5-no-h', '5', 'legacy-stability'),
                               ('5.1-h', '5.1', 'adaptive-half-life'), ('5.1-s', '5.1', 'legacy-stability')]:
        if arm not in (args.arms or default_arms):
            continue
        identity = f'threemind.continuous-memory/{version}'
        options = {'seed': 223} | ({'consolidation_mode': mode} if mode else {})
        if arm in ('5-h-manual', '5-no-h'):
            options['node_retention_mode'] = 'manual'
        config[arm] = {'kernel': identity, 'config': resolve_kernel(identity).configuration(options).to_dict()}
    config = {arm: config[arm] for arm in dict.fromkeys(args.arms or default_arms)}
    configs = output / 'configs.json'
    configs.write_text(json.dumps(config, indent=2), encoding='utf-8')
    executable = args.executable.resolve(strict=True)
    results = []
    for n in args.channels:
        for repeat in range(-args.warmups, args.repeats):
            for arm in list(config)[::1 if repeat % 2 == 0 else -1]:
                row = execute([str(executable), str(configs), arm, str(n), str(args.seconds), args.pattern])
                row['repeat'] = repeat
                (output / f'{arm}-{n}-{repeat}.json').write_text(json.dumps(row, indent=2), encoding='utf-8')
                if repeat >= 0:
                    results.append(row)
            print(f'Completed channels={n}, repetition={repeat}', flush=True)
    summary = []
    for n in args.channels:
        for arm in config:
            rows = [row for row in results if row['channels'] == n and row['arm'] == arm]
            assert len({row['state_hash'] for row in rows}) == 1
            summary.append({'arm': arm, 'channels': n,
                **{key: statistics.median(row[key] for row in rows) for key in
                   ('advance_s', 'injection_s', 'capture_s', 'encoding_s', 'observation_s', 'state_bytes')},
                'nodes': rows[0]['metrics']['nodes'], 'edges': rows[0]['metrics']['edges'],
                'audit': rows[0]['metrics'].get('local_audit'),
                'advance_samples_s': [row['advance_s'] for row in rows],
                'advance_min_s': min(row['advance_s'] for row in rows),
                'advance_max_s': max(row['advance_s'] for row in rows),
                'state_hash': rows[0]['state_hash'],
                'comparison_hash': rows[0].get('comparison_hash')})
            for key in ('process_cpu_s', 'process_peak_working_set_bytes', 'process_peak_commit_bytes'):
                if key in rows[0]:
                    summary[-1][key] = statistics.median(row[key] for row in rows)
        for mode in ('h', 's'):
            pair = [row for row in summary if row['channels'] == n and row['arm'] in (f'5-{mode}', f'5.1-{mode}')]
            if len(pair) == 2:
                assert pair[0]['comparison_hash'] and pair[0]['comparison_hash'] == pair[1]['comparison_hash'], \
                    f'Version-normalized full-state mismatch: {n}/{mode}'
    sources = [ROOT / 'crates/threemind-core/src/local.rs', ROOT / 'crates/threemind-core/src/kernel.rs',
               ROOT / 'crates/threemind-core/examples/memory5_costs.rs', Path(__file__), configs, executable]
    sources += sorted((ROOT / 'crates/threemind-core/src').glob('local*.rs'))
    report = {'scope': 'Fresh fixed-input synthetic engineering fixtures; no learning success inference',
              'repeats': args.repeats, 'seconds': args.seconds, 'summary': summary,
              'warmups': args.warmups, 'platform': platform.platform(),
              'pattern': args.pattern,
              'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'provenance': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}}
    (output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
