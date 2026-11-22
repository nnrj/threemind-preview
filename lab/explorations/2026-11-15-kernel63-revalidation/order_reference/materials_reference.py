"""E22 timing, bounded jitter and dose-matched reference inputs; no engine."""
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / 'order_timing'))
from materials_timing import ids, KERNEL, SEEDS, FIELDS
from threemind_core import Stimulus

OLD = ROOT / '.work/recovery-reference-20261001'


def lesson_frames(p):
    frames = []
    if p['family'] in ('timing', 'jitter'):
        rng = random.Random(22001)
        offsets = ([40000 + rng.randint(-40, 40)*1000 for _ in range(12)]
                   if p.get('variant') == 'jitter' else [p['phase_us']]*12)
        period = 2500000 if p['family'] == 'timing' else 550000
        for i, offset in enumerate(offsets):
            for j, obj in enumerate(p['order']):
                frames.append({'at': i*period + offset + j*50000, 'symbols': obj+'X'})
    else:
        period, slots = ((1100000, (0, 50000, 550000, 600000)) if p['cadence'] == 'dense'
                         else (5000000, (0, 50000, 2500000, 2550000)))
        refs = dict(zip('ABCD', 'XXZZ' if p['layout'] == 'shared' else 'XZZX'))
        for i in range(12):
            for obj, slot in zip(p['order']+'CD', slots):
                frames.append({'at': i*period + slot, 'symbols': obj+refs[obj]})
    return frames


def parents(seeds=SEEDS):
    result = []
    for seed in seeds:
        for tau, phase, maintenance, order in itertools.product((0., 1.), (0, 40000, 60000), (0, 40000, 60000), ('AB', 'BA')):
            result.append({'key': f'timing/{seed}/f{tau:g}/p{phase}/k{maintenance}/{order}',
                           'family': 'timing', 'seed': seed, 'tau': tau, 'phase_us': phase,
                           'maintenance_phase_us': maintenance, 'order': order, 'reference_us': 32200000})
        for variant, order in itertools.product(('fixed', 'jitter'), ('AB', 'BA')):
            result.append({'key': f'jitter/{seed}/{variant}/{order}', 'family': 'jitter',
                           'seed': seed, 'tau': 0., 'phase_us': 40000, 'maintenance_phase_us': 0,
                           'variant': variant, 'order': order, 'reference_us': 7000000})
        for cadence, layout, order in itertools.product(('dense', 'sparse'), ('shared', 'separate'), ('AB', 'BA')):
            result.append({'key': f'reference/{seed}/{cadence}/{layout}/{order}', 'family': 'reference',
                           'seed': seed, 'tau': 0., 'maintenance_phase_us': 0, 'cadence': cadence,
                           'layout': layout, 'order': order, 'reference_us': 13200000 if cadence == 'dense' else 60000000})
    return result


def stages(parent):
    return [{'name': 'train', 'kind': 'train', 'begin_us': 0, 'end_us': parent['reference_us']}] + [
        {'name': f'wait{delay}/cue{cue}', 'kind': 'probe', 'begin_us': parent['reference_us'],
         'probe_us': parent['reference_us'] + delay*1000000,
         'end_us': parent['reference_us'] + delay*1000000 + 5000000, 'delay_s': delay, 'cue': cue}
        for delay, cue in itertools.product((1, 30) if parent['family'] == 'reference' else (30,),
                   ('none', 'X', 'Z', 'XZ') if parent['family'] == 'reference' else ('none', 'X'))]


def commands(parent, stage):
    out, mapping = [], ids(parent['seed'])
    clock = stage['begin_us']
    next_keep = ((clock+499999)//500000)*500000

    def send(letters, dose, at=None, source='registered-course', amplitudes=None):
        amplitudes = amplitudes or [1.]*len(letters)
        out.append({'op': 'input', 'enqueue_us': clock, 'source': source,
                    'stimulus': Stimulus(clock if at is None else at,
                        tuple((mapping[c], v) for c, v in zip(letters, amplitudes)), dose).to_dict()})

    def advance(until):
        nonlocal clock
        assert until >= clock
        out.append({'op': 'advance', 'until_us': until}); clock = until

    def wait(until):
        nonlocal next_keep
        while next_keep < until:
            send('K', .2, next_keep, 'maintenance-control'); next_keep += 500000
        advance(until)

    if stage['kind'] == 'train':
        send('K', .2, 0, 'maintenance-control'); advance(0)
        next_keep = 500000 + parent['maintenance_phase_us']
        for index, frame in enumerate(lesson_frames(parent)):
            wait(frame['at'])
            out.append({'op': 'snapshot', 'name': f'lesson-{index:02d}-before'})
            send(frame['symbols'], .4); advance(frame['at'])
            out.append({'op': 'snapshot', 'name': f'lesson-{index:02d}-after'})
        wait(stage['end_us'])
        send('Y', .2, source='common-final-input'); advance(clock)
    else:
        wait(stage['probe_us'])
        out.append({'op': 'snapshot', 'name': 'pre-probe'})
        out.append({'op': 'begin_observation'})
        if stage['cue'] != 'none':
            send(stage['cue'], .5, source='manual-research-probe',
                 amplitudes=[.5, .5] if stage['cue'] == 'XZ' else None)
        wait(stage['end_us'])
    return out


def historical_check():
    hashes, inputs, count, logical = {}, 0, 0, 0
    for p in parents():
        for stage in stages(p):
            folder = OLD / 'cases' / p['key'] / stage['name']
            frames, result = folder / 'inputs-frames.jsonl.gz', folder / 'result.json'
            rows = [json.loads(line) for line in gzip.decompress(frames.read_bytes()).splitlines()][1:]
            rows.sort(key=lambda r: r['core_event_id'])
            actual = [{'enqueue_us': int(r['source_policy']['resolved_at_us']), 'source': r['source'], 'stimulus': r['stimulus']} for r in rows]
            expected = [{k: c[k] for k in ('enqueue_us', 'source', 'stimulus')} for c in commands(p, stage) if c['op'] == 'input']
            assert actual == expected, (p['key'], stage['name'])
            assert all(r['status'] == 'delivered' and not r['labels'] for r in rows)
            row = json.loads(result.read_bytes())
            assert row['kernel'] == 'threemind.continuous-memory/2' and int(row['time_us']) == stage['end_us']
            for f in (frames, result): hashes[f.relative_to(OLD).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
            inputs += len(rows); count += 1
            logical += sum(f.stat().st_size for f in folder.iterdir() if f.is_file())
    assert len(parents()) == 192 and count == 768
    offsets = [r['at']-i*550000 for i, r in enumerate(lesson_frames(next(p for p in parents() if p['family']=='jitter' and p['variant']=='jitter'))[::2])]
    assert offsets == [12000,52000,48000,30000,43000,67000,7000,10000,28000,11000,38000,10000]
    return {'passed': True, 'parents': 192, 'probes': 576, 'stages': count, 'inputs': inputs,
            'historical_logical_bytes': logical, 'jitter_offsets_us': offsets, 'hashes': hashes,
            'created_engines': 0}


if __name__ == '__main__':
    print(json.dumps({k: v for k, v in historical_check().items() if k != 'hashes'}))
