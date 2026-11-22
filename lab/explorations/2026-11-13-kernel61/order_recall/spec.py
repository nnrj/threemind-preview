"""E20 material and command schedules, without constructing a kernel."""
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

SEEDS = (100121, 100122, 100123, 100124)
APPARATUS_SEED = 100199
OLD = ROOT / '.work/priority-memory-20261001'
KERNEL = 'threemind.continuous-memory/6.1'
FIELDS = ('activation', 'inhibition', 'direct', 'associative')


def ids(seed):
    return ({name: channel_id(seed, 'priority-memory/1', i) for i, name in enumerate('ABCDEFGHK')}
            | {name: channel_id(seed, 'priority-sequence/1', i) for i, name in enumerate('XY')})


def parents(seeds=SEEDS):
    return [{'key': f'{seed}/f{tau:g}/shared{int(shared)}/gap{gap:g}/{order}',
             'seed': seed, 'tau': tau, 'shared': shared, 'gap_s': gap, 'order': order,
             'reference_us': 12 * (round(gap * 1e6) + 500000) + 200000}
            for seed, tau, shared, gap, order in itertools.product(seeds, (0., 1.), (False, True), (.05, .5, 2.), ('AB', 'BA'))]


def stages(parent):
    return [{'name': 'train', 'kind': 'train', 'begin_us': 0, 'end_us': parent['reference_us']}]+[
        {'name': f'wait{delay}/cue{cue:g}', 'kind': 'probe', 'begin_us': parent['reference_us'],
         'probe_us': parent['reference_us'] + delay * 1000000,
         'end_us': parent['reference_us'] + delay * 1000000 + 5000000,
         'delay_s': delay, 'cue': cue}
        for delay, cue in itertools.product((1, 30, 300), (0., .5))]


def commands(parent, stage):
    """Keep same-time processing and maintenance enqueue order from sequence.py."""
    out, mapping = [], ids(parent['seed'])
    clock = stage['begin_us']
    next_keep = ((clock + 499999) // 500000) * 500000

    def send(letters, dose, at=None, source='controlled-order-course'):
        out.append({'op': 'input', 'enqueue_us': clock, 'source': source,
                    'stimulus': Stimulus(clock if at is None else at, tuple((mapping[x], 1.) for x in letters), dose).to_dict()})

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
        for i in range(12):
            for j, letter in enumerate(parent['order']):
                out.append({'op': 'snapshot', 'name': f'lesson-{2*i+j:02d}-before'})
                send(letter + ('X' if parent['shared'] else ''), .4)
                advance(clock)
                out.append({'op': 'snapshot', 'name': f'lesson-{2*i+j:02d}-after'})
                wait(clock + (round(parent['gap_s'] * 1e6) if j == 0 else 500000))
        wait(clock + 200000)
        send('Y', .2, source='common-final-input')
        advance(clock)
    else:
        wait(stage['probe_us'])
        out.append({'op': 'snapshot', 'name': 'pre-probe'})
        out.append({'op': 'begin_observation'})
        if stage['cue']:
            send('X', stage['cue'], source='manual-research-probe')
        wait(stage['end_us'])
    assert clock == stage['end_us']
    return out


def history_check():
    """Verify every material against the preserved, actually scheduled E20 input."""
    hashes, total_inputs = {}, 0
    for p in parents():
        for stage in stages(p):
            folder = OLD / 'cases/sequence' / p['key'] / stage['name']
            path = folder / 'inputs-frames.jsonl.gz'
            rows = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()][1:]
            rows.sort(key=lambda r: r['core_event_id'])
            actual = [{'enqueue_us': int(r['source_policy']['resolved_at_us']),
                       'source': r['source'], 'stimulus': r['stimulus']} for r in rows]
            expected = [{k: c[k] for k in ('enqueue_us', 'source', 'stimulus')}
                        for c in commands(p, stage) if c['op'] == 'input']
            assert all(r['status'] == 'delivered' and r['labels'] == {} for r in rows)
            assert expected == actual, (p['key'], stage['name'], 'input schedule differs')
            result_path = folder / 'result.json'
            result = json.loads(result_path.read_bytes())
            assert result['kernel'] == 'threemind.continuous-memory/2'
            assert int(result['time_us']) == stage['end_us'] and result['life'] == 'active'
            for file in (path, result_path):
                hashes[file.relative_to(OLD).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
            total_inputs += len(rows)
    return {'passed': True, 'blocks': 4, 'parents': 96, 'stages': 672,
            'inputs': total_inputs, 'historical_root': str(OLD), 'historical_sha256': hashes}


if __name__ == '__main__':
    r = history_check()
    print(json.dumps({k: v for k, v in r.items() if k != 'historical_sha256'}))
