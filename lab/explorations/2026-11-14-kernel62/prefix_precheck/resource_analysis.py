"""Read-only same-time resource projection from saved teaching traces.

Added after registration as analysis only. No engine is created or advanced.
Lazy resource timestamps are projected to the same recorded internal time.
"""
import argparse
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src'))
from threemind_kernels.local62_config import Local62Config
from threemind_kernels.mechanisms import ShortTermState


def read(path):
    with gzip.open(path, 'rt', encoding='utf8') as f:
        for line in f:
            yield json.loads(line)


def run(work):
    index = json.loads((work / 'cases.json').read_text('utf8'))
    cfg = Local62Config(**index['short/train-0']['initial_config'])
    rows = []
    for block in (0, 1):
        paths = {'screened': work / f'cases/pre-old-high/{block}/train/teaching.jsonl.gz',
                 'unscreened': work / f'controls/old-high/{block}/train/teaching.jsonl.gz'}
        for label, path in paths.items():
            point = next(p for p in read(path) if p['time_us'] == 3900000)
            edges = []
            for edge in point['edges']:
                raw = edge['short_term']
                state = ShortTermState(**(raw | {'time_us': int(raw['time_us'])}))
                at_time = state.recovered(point['time_us'], cfg.short_term())
                edges.append({'source': edge['source'], 'target': edge['target'],
                              'stored': raw, 'at_recorded_time': asdict(at_time),
                              'weight': edge['weight'], 'stability': edge['stability']})
            rows.append({'block': block, 'condition': label, 'time_us': point['time_us'], 'edges': edges})
    output = {'kind': 'read-only-same-time-resource-projection', 'rules': 'existing ShortTermState.recovered', 'rows': rows}
    target = work / 'resource-analysis.json'
    with target.open('x', encoding='utf8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(json.dumps(output), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    args = p.parse_args(); run(args.work)
