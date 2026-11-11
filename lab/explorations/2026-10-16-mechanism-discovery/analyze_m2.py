"""Read-only analysis of committed M2 originals. Never imports or advances Core."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path


def read(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith('.gz') else raw)


def paired_values(rows, field):
    origins = defaultdict(dict)
    for row in rows:
        case = row['case']
        if case['history'] in origins[case['origin']]:
            raise ValueError('duplicate history in origin')
        origins[case['origin']][case['history']] = row[field]
    if len(origins) != 8 or any(set(v) != {0, 1} for v in origins.values()):
        raise ValueError('expected eight independent origins, each with both matched histories')
    return [(v[0]-v[1])/2 for _, v in sorted(origins.items()) if None not in v.values()]


def describe(values, seed):
    if not values:
        return {'n': 0, 'mean': None, 'range': None, 'bootstrap_95': None}
    rng = random.Random(seed)
    draws = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(4000))
    return {'n': len(values), 'mean': statistics.mean(values), 'range': [min(values), max(values)],
            'bootstrap_95': [draws[99], draws[3899]]}


def analyze(work):
    case_list = read(work/'cases.json')
    if len(case_list) != 640:
        raise ValueError('frozen case count differs')
    observations = []
    files_checked = 0
    node_counts, edge_counts, current_sizes = [], [], []
    for case in case_list:
        folder = work/'cases'/case['id']
        result = read(folder/'result.json')
        if result['case'] != case:
            raise ValueError('result identity mismatch')
        current = read(folder/'current.json')
        p = folder/current['path']
        current_sizes.append(p.stat().st_size)
        if hashlib.sha256(p.read_bytes()).hexdigest() != current['sha256']:
            raise ValueError('current whole-state file hash mismatch')
        whole = read(p)
        canonical = json.dumps(whole, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if hashlib.sha256(canonical).hexdigest() != result['whole_state_sha256']:
            raise ValueError('result does not describe current complete state')
        if whole['core']['dynamics'] != 'threemind.continuous-memory/5.1':
            raise ValueError('wrong kernel')
        frames = whole['recent_activity']
        start = (17+case['delay'])*1_000_000
        window = [r for r in frames if 500_000 <= r['time_us']-start <= 1_500_000]
        mean = statistics.mean(r['response'] for r in window) if window else None
        if mean is not None and abs(mean-result['mean_response']) > 1e-15:
            raise ValueError('primary endpoint recomputation differs')
        first = next((r['response'] for r in frames if r['time_us']-start == 500_000), None)
        if first != result['first_response']:
            raise ValueError('first output recomputation differs')
        if whole['core']['life'] != 'dead' and (len(frames) != 41 or len(window) != 21):
            raise ValueError('incomplete observation window')
        early = [r for r in frames if 0 < r['time_us']-start < 500_000]
        # Additional, explicitly post-hoc timing diagnostics; never replace main_window.
        result = result | {
            'early_diagnostic': statistics.mean(r['response'] for r in early) if early else None,
            'peak_abs': max((abs(r['response']) for r in frames), default=0),
            'peak_assoc': max((max(r['associative']) for r in frames), default=0),
            'preprobe_trace': {k: v for k, v in read(folder/f'traces-{start}.json.gz').items()
                              if k in ('target_edge_count', 'surviving', 'effective_weight_sum')},
        }
        prior = None
        for checkpoint in sorted(folder.glob('whole-*.json.gz')):
            state = read(checkpoint)
            now = int(state['core']['time_us'])
            if state['case'] != case or (prior is not None and not 0 < now-prior <= 10_000_000):
                raise ValueError('noncontinuous committed unit chain')
            prior = now
            files_checked += 1
            node_counts.append(len(state['core']['nodes']))
            edge_counts.append(len(state['core']['edges']))
        if prior != result['final_time_us']:
            raise ValueError('latest boundary mismatch')
        observations.append(result)
    groups = defaultdict(list)
    for row in observations:
        c = row['case']
        groups[(c['delay'], c['mode'], c['cue'])].append(row)
    summaries = []
    for i, (key, rows) in enumerate(sorted(groups.items())):
        summaries.append({'delay': key[0], 'mode': key[1], 'cue': key[2],
                          'independent_origins': 8, 'matched_lives': len(rows),
                          'main_history_contrast': describe(paired_values(rows, 'mean_response'), 8100+i),
                          'posthoc_early_history_contrast': describe(paired_values(rows, 'early_diagnostic'), 9100+i),
                          'first_correct': sum(r['first_correct'] is True for r in rows),
                          'first_no_expression': sum(r['first_correct'] is None for r in rows),
                          'first_denominator': len(rows),
                          'early_detectable_lives': sum(r['peak_abs'] > 1e-9 for r in rows),
                          'max_peak_abs': max(r['peak_abs'] for r in rows),
                          'max_peak_associative': max(r['peak_assoc'] for r in rows),
                          'trace_count_range': [min(r['preprobe_trace']['surviving'] for r in rows),
                                                max(r['preprobe_trace']['surviving'] for r in rows)],
                          'mean_preprobe_weight': statistics.mean(r['preprobe_trace']['effective_weight_sum'] for r in rows)})
    return {'schema': 'threemind.m2-pilot-analysis/1', 'complete_lives': len(observations),
            'independent_origins': len({r['case']['origin'] for r in observations}),
            'complete_snapshots_checked': files_checked, 'deaths': sum(r['life'] == 'dead' for r in observations),
            'total_simulated_seconds': sum(r['final_time_us'] for r in observations)/1e6,
            'checkpoint_node_range': [min(node_counts), max(node_counts)],
            'checkpoint_edge_range': [min(edge_counts), max(edge_counts)],
            'compressed_current_whole_state_bytes': {'min': min(current_sizes), 'max': max(current_sizes),
                                                     'mean': statistics.mean(current_sizes)},
            'primary_first_correct': sum(r['first_correct'] is True for r in observations),
            'primary_first_no_expression': sum(r['first_correct'] is None for r in observations),
            'primary_mean_nonzero': sum(r['mean_response'] is not None and abs(r['mean_response']) > 1e-9 for r in observations),
            'early_nonzero': sum(r['peak_abs'] > 1e-9 for r in observations),
            'groups': summaries, 'observations': observations,
            'interval_scope': 'exploratory percentile bootstrap by eight independent origins per condition; no simultaneous coverage; degenerate intervals are not proof of no population effect',
            'extra_analysis': 'early 0<t<0.5s contrast and peaks are post-hoc diagnostics after seeing initial late-window zeros; not replacement endpoints or confirmation'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = analyze(args.work)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in value.items() if k not in ('groups', 'observations')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
