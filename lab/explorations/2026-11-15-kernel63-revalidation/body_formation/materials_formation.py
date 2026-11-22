"""Read-only E21C material inventory; no kernels or scientific subjects."""
import gzip
import hashlib
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OLD = ROOT / '.work/order-mechanisms-20261001/cases/sensory'
SEEDS = (930101, 930102, 930103, 930104)
KERNEL = 'threemind.continuous-memory/6.3'


def parents():
    return [{'key': f'{seed}/{mode}/learn{d}{c}', 'seed': seed, 'mode': mode,
             'teaching_depletion': bool(d), 'teaching_competition': bool(c)}
            for seed, mode, d, c in itertools.product(SEEDS, ('full', 'no_imu'), (0, 1), (0, 1))]


def stages(parent):
    return [{'name': 'train', 'kind': 'train', 'begin_us': 0, 'end_us': 20200000}] + [
        {'name': f'test{d}{c}/sign{sign}/physical{physical}', 'kind': 'probe',
         'begin_us': 20200000, 'end_us': 25800000, 'sign': sign, 'physical': bool(physical),
         'test_depletion': bool(d), 'test_competition': bool(c)}
        for d, c, sign, physical in itertools.product((0, 1), (0, 1), (1, -1), (0, 1))]


def frames(parent, stage, root=OLD):
    path = root / parent['key'] / stage['name'] / 'inputs-frames.jsonl.gz'
    original = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
    original = [r for r in original if 'stimulus' in r]
    assert original and all(r['status'] == 'delivered' and not r['labels'] for r in original)
    original.sort(key=lambda r: r['core_event_id'])
    result = [{'enqueue_us': int(r['source_policy']['resolved_at_us']), 'source': r['source'],
               'stimulus': r['stimulus'], 'old_event_id': r['core_event_id']} for r in original]
    assert all(stage['begin_us'] <= r['enqueue_us'] <= int(r['stimulus']['time_us']) <= stage['end_us'] for r in result)
    assert all(a['enqueue_us'] <= b['enqueue_us'] for a, b in itertools.pairwise(result))
    assert all(int(r['stimulus']['time_us']) == int(r['delivered_time_us']) for r in original)
    return result


def check():
    count = total = size = 0
    hashes = {}
    input_patterns = {}
    for parent in parents():
        for stage in stages(parent):
            folder = OLD / parent['key'] / stage['name']
            values = frames(parent, stage)
            result = json.loads((folder / 'result.json').read_bytes())
            assert result['kernel'] == 'threemind.continuous-memory/2'
            assert int(result['time_us']) == stage['end_us']
            if stage['kind'] == 'probe':
                targets = result['extra']['targets']
                assert not any(ch in targets for r in values for ch, amplitude in r['stimulus']['channels'])
            normalized = [{k: r[k] for k in ('enqueue_us', 'source', 'stimulus')} for r in values]
            key = (parent['seed'], parent['mode'], stage['kind'], stage.get('sign'), stage.get('physical'))
            if key in input_patterns: assert normalized == input_patterns[key], key
            else: input_patterns[key] = normalized
            for name in ('result.json', 'inputs-frames.jsonl.gz'):
                p = folder / name
                hashes[p.relative_to(OLD).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
            size += sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
            total += len(values); count += 1
    assert len(parents()) == 32 and count == 544 and total == 32544
    return {'passed': True, 'material_blocks': 4, 'teaching_references': 32,
            'diagnostics': 512, 'stages': count, 'inputs': total,
            'historical_logical_bytes': size, 'created_engines': 0, 'hashes': hashes}


if __name__ == '__main__':
    print(json.dumps({k: v for k, v in check().items() if k != 'hashes'}))
