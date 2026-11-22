"""E21 exchange materials and schedules; does not construct or advance a Core."""
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'order_recall'))
import spec as recall
assert Path(recall.__file__).resolve() == HERE.parent / 'order_recall/spec.py'
from intervention import GROUPS

OLD = ROOT / '.work/order-mechanisms-20261001'


def parents(seeds=recall.SEEDS):
    return [p for p in recall.parents(seeds) if p['shared'] and p['gap_s'] == .05]


def groups():
    return [tuple(g for g, on in zip(GROUPS, bits) if on) for bits in itertools.product((0, 1), repeat=4)]


def hold_stage(parent):
    stop = parent['reference_us'] + 30000000
    return {'name': 'wait30', 'kind': 'probe', 'begin_us': parent['reference_us'],
            'probe_us': stop, 'end_us': stop, 'delay_s': 30, 'cue': 0.}


def probe_stage(parent, cue):
    start = parent['reference_us'] + 30000000
    return {'name': f'cue{cue:g}', 'kind': 'probe', 'begin_us': start,
            'probe_us': start, 'end_us': start + 5000000, 'delay_s': 30, 'cue': cue}


def historical_check():
    hashes, inputs, cases, logical = {}, 0, 0, 0
    for parent, selected, cue in itertools.product(parents(), groups(), (0., .5)):
        label = ''.join(selected) or 'none'
        key = f"{parent['seed']}/f{parent['tau']:g}/{parent['order']}/{label}/cue{cue:g}"
        folder = OLD / 'cases/swap' / key
        frames = folder / 'inputs-frames.jsonl.gz'
        result = folder / 'result.json'
        delivered = [json.loads(line) for line in gzip.decompress(frames.read_bytes()).splitlines()][1:]
        delivered.sort(key=lambda row: row['core_event_id'])
        expected = [{k: c[k] for k in ('enqueue_us', 'source', 'stimulus')}
                    for c in recall.commands(parent, probe_stage(parent, cue)) if c['op'] == 'input']
        actual = [{'enqueue_us': int(row['source_policy']['resolved_at_us']),
                   'source': row['source'], 'stimulus': row['stimulus']} for row in delivered]
        assert expected == actual, key
        row = json.loads(result.read_bytes())
        assert row['kernel'] == 'threemind.continuous-memory/2'
        assert int(row['time_us']) == probe_stage(parent, cue)['end_us']
        assert row['extra']['groups'] == label
        assert all(frame['status'] == 'delivered' and not frame['labels'] for frame in delivered)
        for file in (frames, result):
            hashes[file.relative_to(OLD).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
        inputs += len(delivered)
        cases += 1
        logical += sum(file.stat().st_size for file in folder.iterdir() if file.is_file())
    assert cases == 512
    return {'passed': True, 'cases': cases, 'inputs': inputs, 'independent_material_blocks': 4,
            'historical_logical_bytes': logical, 'historical_root': str(OLD), 'hashes': hashes,
            'created_engines': 0}


if __name__ == '__main__':
    print(json.dumps({k: v for k, v in historical_check().items() if k != 'hashes'}))
