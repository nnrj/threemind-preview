"""Historical E21 timing and reference schedules; no Core construction."""
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from threemind_core import Stimulus
from threemind_runtime.adapters import channel_id

KERNEL = 'threemind.continuous-memory/6.1'
SEEDS = (100121, 100122, 100123, 100124)
FIELDS = ('activation', 'inhibition', 'direct', 'associative')
OLD = ROOT / '.work/order-mechanisms-20261001'


def ids(seed):
    return ({c: channel_id(seed, 'priority-memory/1', i) for i, c in enumerate('ABCDEFGHK')}
            | {c: channel_id(seed, 'priority-sequence/1', i) for i, c in enumerate('XYZ')})


def parents(seeds=SEEDS):
    result = []
    for family in ('cadence', 'phase', 'reference'):
        gaps = (50000, 500000, 2000000) if family == 'phase' else (50000,)
        phases = (0, 40000) if family == 'reference' else (0, 20000, 40000, 60000, 80000)
        for seed, tau, gap, phase, order in itertools.product(seeds, (0., 1.), gaps, phases, ('AB', 'BA')):
            result.append({'key': f'{family}/{seed}/f{tau:g}/g{gap}/p{phase}/{order}',
                           'family': family, 'seed': seed, 'tau': tau, 'gap_us': gap,
                           'phase_us': phase, 'order': order, 'separate': family == 'reference',
                           'stride_us': 550000 if family == 'cadence' else 2500000,
                           'reference_us': 7000000 if family == 'cadence' else 32200000})
    return result


def stages(parent):
    return [{'name': 'train', 'kind': 'train', 'begin_us': 0, 'end_us': parent['reference_us']}] + [
        {'name': f'wait{delay}/cue{cue}', 'kind': 'probe', 'begin_us': parent['reference_us'],
         'probe_us': parent['reference_us'] + delay * 1000000,
         'end_us': parent['reference_us'] + delay * 1000000 + 5000000,
         'delay_s': delay, 'cue': cue}
        for delay, cue in itertools.product((1, 30), ('none', 'X', 'Z') if parent['separate'] else ('none', 'X'))]


def commands(parent, stage):
    out, mapping = [], ids(parent['seed'])
    clock = stage['begin_us']
    next_keep = ((clock + 499999) // 500000) * 500000

    def send(letters, dose, at=None, source='controlled-order-course'):
        out.append({'op': 'input', 'enqueue_us': clock, 'source': source,
                    'stimulus': Stimulus(clock if at is None else at,
                                        tuple((mapping[c], 1.) for c in letters), dose).to_dict()})

    def advance(until):
        nonlocal clock
        assert until >= clock
        out.append({'op': 'advance', 'until_us': until})
        clock = until

    def wait(until):
        nonlocal next_keep
        while next_keep < until:
            send('K', .2, next_keep, 'maintenance-control')
            next_keep += 500000
        advance(until)

    if stage['kind'] == 'train':
        send('K', .2, 0, 'maintenance-control')
        advance(0)
        next_keep = 500000
        for i in range(12):
            for j, letter in enumerate(parent['order']):
                at = parent['phase_us'] + i * parent['stride_us'] + j * parent['gap_us']
                wait(at)
                reference = 'Z' if parent['separate'] and letter == 'B' else 'X'
                send(letter + reference, .4)
                advance(at)
        wait(stage['end_us'])
        send('Y', .2, source='common-final-input')
        advance(clock)
    else:
        wait(stage['probe_us'])
        out.append({'op': 'snapshot', 'name': 'pre-probe'})
        out.append({'op': 'begin_observation'})
        if stage['cue'] != 'none':
            send(stage['cue'], .5, source='manual-research-probe')
        wait(stage['end_us'])
    assert clock == stage['end_us']
    return out


def historical_check():
    hashes, inputs, stages_count, logical = {}, 0, 0, 0
    family_counts = {}
    for parent in parents():
        family_counts[parent['family']] = family_counts.get(parent['family'], 0) + 1
        for stage in stages(parent):
            folder = OLD / 'cases' / parent['key'] / stage['name']
            frames, result = folder / 'inputs-frames.jsonl.gz', folder / 'result.json'
            rows = [json.loads(line) for line in gzip.decompress(frames.read_bytes()).splitlines()][1:]
            rows.sort(key=lambda row: row['core_event_id'])
            actual = [{'enqueue_us': int(r['source_policy']['resolved_at_us']),
                       'source': r['source'], 'stimulus': r['stimulus']} for r in rows]
            expected = [{k: c[k] for k in ('enqueue_us', 'source', 'stimulus')}
                        for c in commands(parent, stage) if c['op'] == 'input']
            assert actual == expected, (parent['key'], stage['name'])
            assert all(r['status'] == 'delivered' and not r['labels'] for r in rows)
            value = json.loads(result.read_bytes())
            assert value['kernel'] == 'threemind.continuous-memory/2'
            assert int(value['time_us']) == stage['end_us']
            for path in (frames, result):
                hashes[path.relative_to(OLD).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            inputs += len(rows)
            stages_count += 1
            logical += sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
    assert len(parents()) == 352 and stages_count == 1824
    return {'passed': True, 'parents': 352, 'probes': 1472, 'stages': stages_count,
            'inputs': inputs, 'historical_logical_bytes': logical, 'families': family_counts,
            'hashes': hashes, 'historical_root': str(OLD), 'created_engines': 0}


if __name__ == '__main__':
    print(json.dumps({k: v for k, v in historical_check().items() if k != 'hashes'}))
