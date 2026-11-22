"""Read-only arithmetic and cross-backend audit of the bounded 6.2 check."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path

from threemind_core import StateImage
from threemind_core.engine import canonical_bytes


def read(path):
    with gzip.open(path, 'rb') as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    args = parser.parse_args()
    results = json.loads((args.work / 'results.json').read_bytes())
    contract = json.loads((args.work / 'contract.json').read_bytes())
    cases = {row['material_key']: row for row in json.loads((args.materials / 'cases.json').read_bytes())
             if row['variant'] == 'v5.1-legacy-edges-immediate'}
    channels = {'C': 6969, 'E': 1925}
    groups = defaultdict(list)
    series = {}
    materials = {}
    maximum_difference = 0.0
    for row in results['results']:
        backend, mode, novelty, block, cue = (row[k] for k in ('backend', 'retention', 'novelty', 'block', 'cue'))
        folder = args.work / backend / mode / novelty / str(block)
        case = cases[f'history/s{block}/101/d1/{cue}']
        points = read(folder / f'{cue}-process.json.gz')
        relative = [p['time_us'] - case['probe_start_us'] for p in points]
        assert relative == [0] + list(range(0, 15000001, 10000))
        peaks = {}
        for symbol, channel in channels.items():
            peaks[symbol] = max(
                (next((n['activation'] for n in p['nodes'] if n['channel'] == channel), 0.0)
                 for t, p in zip(relative, points) if t >= round(case['gap_s'] * 1e6)), default=0.0)
        target = 'C' if cue == 'AB' else 'E'
        if case['swap']:
            target = 'E' if target == 'C' else 'C'
        other = 'E' if target == 'C' else 'C'
        assert (row['target'], row['other']) == (target, other)
        margin = peaks[target] - peaks[other]
        assert abs(margin - row['signed_peak']) < 1e-14
        for filename, expected in (('parent.json.gz', row['parent_sha256']),
                                   (f'{cue}-final.json.gz', row['final_sha256'])):
            state = StateImage(canonical_bytes(read(folder / filename)))
            assert state.digest == expected
            assert state.to_dict()['dynamics'] == contract['kernel']
        for key in (f'short/train-{block}', case['material_key']):
            file = args.materials / 'materials' / key / 'frames.jsonl'
            materials[key] = hashlib.sha256(file.read_bytes()).hexdigest()
        assert materials[case['material_key']] == row['input_sha256']
        groups[backend, mode, novelty, block].append(margin)
        key = mode, novelty, block, cue
        values = [(p['time_us'], sorted((n['channel'], *(n[field] for field in
                   ('activation', 'inhibition', 'direct', 'associative'))) for n in p['nodes'])) for p in points]
        if backend == 'reference':
            series[key] = values
        else:
            for left, right in zip(series[key], values, strict=True):
                assert left[0] == right[0]
                for x, y in zip(left[1], right[1], strict=True):
                    assert x[0] == y[0]
                    maximum_difference = max(maximum_difference, *(abs(a-b) for a, b in zip(x[1:], y[1:])))
    assert maximum_difference < 1e-12
    counts = []
    for mode in contract['conditions']:
        for novelty in contract['novelty']:
            backend_counts = {}
            for backend in ('reference', 'native'):
                backend_counts[backend] = sum(all(x > 1e-6 for x in groups[backend, mode, novelty, block])
                                              for block in (0, 1))
                assert all(len(groups[backend, mode, novelty, block]) == 2 for block in (0, 1))
            counts.append({'retention': mode, 'novelty': novelty, 'blocks': 2, **backend_counts})
    summary = {'kernel': contract['kernel'], 'material_blocks': 2, 'configurations_per_backend': 4,
               'stages_per_backend': 24, 'saved_states': 48, 'processes': 32,
               'frame_count_per_process': 1502, 'maximum_process_backend_difference': maximum_difference,
               'results': counts, 'materials_sha256': materials,
               'contract_sha256': hashlib.sha256((args.work / 'contract.json').read_bytes()).hexdigest(),
               'results_sha256': hashlib.sha256((args.work / 'results.json').read_bytes()).hexdigest(),
               'wall_seconds_including_observation_and_saving': results['wall_seconds']}
    with args.summary.open('x', encoding='utf8') as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps({'counts': counts, 'maximum_process_backend_difference': maximum_difference}))


if __name__ == '__main__':
    main()
