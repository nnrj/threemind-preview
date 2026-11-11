"""Read-only recomputation of frozen C1 replay; no controller or Core creation."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(Path(path).read_bytes())


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load(path, expected=None):
    raw = Path(path).read_bytes()
    if expected and hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('whole-state hash mismatch: '+str(path))
    return json.loads(gzip.decompress(raw))


def means(rows):
    out = {}
    for name, start, end, count in [('early', 100_000, 300_000, 5), ('late', 500_000, 1_500_000, 21)]:
        data = [r['response'] for r in rows if start <= r['time_us']-18_000_000 <= end]
        if len(data) != count:
            raise ValueError('incomplete endpoint samples')
        out[name] = float(np.mean(data))
    return out


def summarize(values):
    data = np.array(values)
    rng = np.random.default_rng(202610163)
    boot = rng.choice(data, (10_000, len(data))).mean(axis=1)
    return {'n': len(data), 'mean': float(data.mean()), 'range': [float(data.min()), float(data.max())],
            'bootstrap_95': np.quantile(boot, [.025, .975]).tolist(),
            'above_registered_threshold': int(np.sum(data > 1e-4)), 'values': values}


def analyze(work):
    if (work/'in-flight.json').exists() or (work/'STOP').exists() or read(work/'status.json')['completed'] != 128:
        raise ValueError('batch not complete')
    entries, whole_files, input_witnesses = [], 0, {}
    sources = {r['source_id']: r for r in read(work/'source-index.json')}
    for source_id, reference in sources.items():
        whole = load(work/'source-copies'/source_id/'whole.json.gz', reference['sha256'])
        case = whole['case']
        entries.append({'system': 'ThreeMind-5.1', 'origin': case['origin'], 'history': case['history'],
                        'cue': case['cue'], **means(whole['recent_activity']), 'reused_source': True})
    for case in read(work/'cases.json'):
        folder = work/'cases'/case['id']
        current = read(folder/'current.json')
        final = load(folder/current['path'], current['sha256'])
        result = read(folder/'result.json')
        if digest(final) != result['whole_sha256'] or final['case'] != case or final['next_frame_us'] != 20_050_000:
            raise ValueError('result/current identity mismatch')
        source = load(work/'source-copies'/case['source_id']/'whole.json.gz', sources[case['source_id']]['sha256'])
        if final['source_sha256'] != digest(source) or final['input_cursor'] != len(source['environment']['schedule']):
            raise ValueError('source/cursor mismatch')
        expected_times = [0, 10_050_000, 18_050_000, 20_050_000]
        if current['index'] != 3:
            raise ValueError('unexpected checkpoint count')
        for i, t in enumerate(expected_times):
            state = load(folder/f'whole-{i:04d}.json.gz')
            whole_files += 1
            if state['next_frame_us'] != t or state['source_sha256'] != digest(source) or state['case'] != case:
                raise ValueError('continuity/source identity mismatch')
            if i == 0:
                initial = state['controller']
        if case['kind'] == 'fixed-rnn-reader':
            for key in ['R', 'U', 'rng']:
                if initial[key] != final['controller'][key]:
                    raise ValueError('fixed reservoir changed')
        calculated = means(final['recent_activity'])
        if any(calculated[k] != result[k] for k in calculated):
            raise ValueError('recorded endpoint differs from raw rows')
        witness = digest([{k: row[k] for k in ['time_us', 'input', 'delivered_event_indices']}
                          for row in final['recent_activity']])
        if case['source_id'] in input_witnesses and witness != input_witnesses[case['source_id']]:
            raise ValueError('controls did not receive identical probe inputs')
        input_witnesses[case['source_id']] = witness
        entries.append({'system': case['kind'], 'origin': case['origin'], 'history': case['history'],
                        'cue': case['cue'], **calculated, 'updates': result['learning_updates'], 'reused_source': False})
    systems = []
    for system in ['reactive', 'finite-state', 'hebbian', 'fixed-rnn-reader', 'ThreeMind-5.1']:
        selected = [e for e in entries if e['system'] == system]
        origins = sorted({e['origin'] for e in selected})
        per_origin = []
        for origin in origins:
            rows = {(e['history'], e['cue']): e for e in selected if e['origin'] == origin}
            outcomes = {'origin': origin}
            for window in ['early', 'late']:
                corrected = [rows[h, 'strong'][window]-rows[h, 'none'][window] for h in [0, 1]]
                outcomes[window] = (corrected[0]-corrected[1])/2
                outcomes[window+'_history_corrected'] = corrected
                outcomes[window+'_both_directions'] = corrected[0] > 1e-4 and corrected[1] < -1e-4
            per_origin.append(outcomes)
        systems.append({'system': system, 'origins': len(origins), 'lives': len(selected),
                        'early': summarize([r['early'] for r in per_origin]),
                        'late': summarize([r['late'] for r in per_origin]),
                        'both_history_directions_early': sum(r['early_both_directions'] for r in per_origin),
                        'both_history_directions_late': sum(r['late_both_directions'] for r in per_origin),
                        'updates_per_life': sorted({r['updates'] for r in selected if 'updates' in r}),
                        'by_origin': per_origin})
    return {'schema': 'threemind.m3-c1-analysis/1', 'reused_independent_origins': 8,
            'new_ThreeMind_origins': 0, 'new_control_lives': 128, 'read_only_ThreeMind_lives': 32,
            'checked_baseline_whole_snapshots': whole_files, 'identical_probe_input_witnesses': len(input_witnesses),
            'systems': systems, 'entries': entries, 'other_criteria': 'not-tested',
            'limits': 'Development source reuse, unequal capacity/time constants; no raw-magnitude ability ranking or four-criterion verdict.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.work)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != 'entries'}, ensure_ascii=False))
