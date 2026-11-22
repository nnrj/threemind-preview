"""RT63-01: frozen small mechanistic study; production dynamics are untouched."""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from threemind_core import StateImage, Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.adapters import channel_id
from lab.tools.study_lock import worker_lock

WORK = ROOT / '.work/repeat-timing63-20261118'
KERNEL = 'threemind.continuous-memory/6.3'
TAG = 'RT63-01'
PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS = UUID('b7a2a95c-cdb8-4571-b01b-8bf769e3a762')
SEEDS = (181801, 181802, 181803, 181804)
DOSES = (.05, .2)
PATTERNS = ('continuous', 'short', 'long')
FIELDS = ('activation', 'inhibition', 'direct', 'associative')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    data = encoded(value)
    if path.suffix == '.gz':
        data = gzip.compress(data, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == data, f'immutable evidence differs: {path}'
    else:
        with path.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def state_save(path, state):
    raw = ArtifactCodec.encode(state)
    assert ArtifactCodec.decode(raw).digest == state.digest
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def state_read(path):
    return ArtifactCodec.decode(Path(path).read_bytes())


def mapping(seed):
    values = {name: channel_id(seed, 'repeat-timing63-v1', i) for i, name in enumerate(('x1', 'x2', 'x3', 'k'))}
    assert len(set(values.values())) == 4
    return values


def engine(seed=None, state=None, backend='native'):
    return resolve_kernel(KERNEL).create({'seed': seed} if state is None else None, state, backend=backend)


def guard():
    import psutil
    assert not (WORK / 'STOP').exists(), 'operator STOP'
    assert shutil.disk_usage(ROOT).free > 25 * 2**30, 'E reserve'
    assert psutil.virtual_memory().available > 4 * 2**30, 'RAM reserve'
    assert psutil.Process().memory_info().rss < 2**30, 'process memory cap'


def inputs(seed, dose=None, pattern=None, begin=0, end=34_000_000, probe=False):
    ids = mapping(seed)
    rows = [{'kind': 'maintenance', 'stimulus': Stimulus(t, ((ids['k'], 1.),), .2).to_dict()}
            for t in range(((begin + 499999) // 500000) * 500000, end, 500000)]
    if pattern is not None:
        starts = {'continuous': (3_600_000, 3_800_000), 'short': (3_400_000, 3_800_000),
                  'long': (2_600_000, 3_800_000)}[pattern]
        for start in starts:
            for t in range(start, start + 200000, 20000):
                rows.append({'kind': 'presentation', 'stimulus': Stimulus(
                    t, ((ids['x1'], 1.), (ids['x2'], .8), (ids['x3'], .6)), dose).to_dict()})
    if probe:
        rows.append({'kind': 'probe', 'stimulus': Stimulus(begin, ((ids['x1'], 1.),), .2).to_dict()})
    return sorted(rows, key=lambda row: (int(row['stimulus']['time_us']), row['kind']))


def observe(e, ids):
    before = e.capture_state().digest
    nodes = e.observation_nodes()
    assert before == e.capture_state().digest, 'observation altered Core'
    lookup = {row['id']: row for row in nodes}
    return {'time_us': e.time_us,
            'values': [[lookup.get(ids[k], {}).get(f, 0.) for f in FIELDS] for k in ('x1', 'x2', 'x3', 'k')],
            'nodes': nodes}


def cross_edges(doc, ids):
    task = {ids[k] for k in ('x1', 'x2', 'x3')}
    return [r for r in doc['edges'] if (r['source'] in task) != (r['target'] in task)]


def execute(folder, seed, rows, end, sample_times, state=None, backend='native', restoration=False, pause=False):
    if folder and (folder / 'result.json').exists():
        result = read(folder / 'result.json')
        final = state_read(folder / 'final.tmind')
        assert final.digest == result['final_sha256']
        return result, final, read(folder / 'trajectory.json.gz')
    if folder:
        folder.mkdir(parents=True, exist_ok=False)
    e = engine(seed, state, backend)
    start = e.capture_state()
    assert state is None or start.digest == state.digest
    ids = mapping(seed)
    if folder:
        state_save(folder / 'initial.tmind', start)
        save(folder / 'controller-initial.json', {'mapping': ids, 'rows': rows, 'next_input': 0,
                                                 'begin_us': e.time_us, 'end_us': end, 'readout': FIELDS})
    receipts = [e.inject(Stimulus.from_dict(row['stimulus'])) for row in rows]
    queued = e.capture_state()
    if folder:
        state_save(folder / 'queued.tmind', queued)
        save(folder / 'receipts.json', receipts)
    samples = []
    started = time.monotonic()
    events = []
    delivered_inputs = []
    def observer(event):
        events.append(event)
        if event.get('kind') == 'stimulus':
            delivered_inputs.append(event)
    for j, target in enumerate(sorted(set(sample_times) | {end})):
        assert time.monotonic() - started < 120, 'stage wall-clock limit'
        e.advance_to(target, observer=observer)
        assert e.time_us == target and e.life != 'dead', 'unexpected stopped subject'
        samples.append(observe(e, ids))
        if j == len(sample_times) // 2:
            if pause:
                checkpoint = e.capture_state()
                time.sleep(.01)
                assert checkpoint.digest == e.capture_state().digest
            if restoration:
                checkpoint = e.capture_state()
                e = engine(state=ArtifactCodec.decode(ArtifactCodec.encode(checkpoint)), backend=backend)
                assert checkpoint.digest == e.capture_state().digest
    final = e.capture_state()
    graph = e.graph()
    assert final.digest == e.capture_state().digest
    assert not cross_edges(final.to_dict(), ids), 'K is not isolated'
    result = {'seed': seed, 'kernel': KERNEL, 'begin_us': int(start.to_dict()['time_us']), 'end_us': end,
              'initial_sha256': start.digest, 'queued_sha256': queued.digest, 'final_sha256': final.digest,
              'inputs': len(rows), 'life': e.life, 'nodes': len(final.to_dict()['nodes']),
              'edges': len(final.to_dict()['edges']), 'wall_seconds': time.monotonic() - started,
              'config': e.config.to_dict(), 'backend': backend}
    if folder:
        state_save(folder / 'final.tmind', final)
        save(folder / 'graph-final.json', graph)
        save(folder / 'trajectory.json.gz', samples)
        save(folder / 'events.json.gz', events)
        save(folder / 'controller-final.json', {'mapping': ids, 'rows': rows, 'next_input': len(rows),
                                               'time_us': e.time_us, 'readout': FIELDS})
        save(folder / 'result.json', result)
    return result, final, samples


def numeric_error(a, b):
    if isinstance(a, dict):
        assert set(a) == set(b)
        return max((numeric_error(a[k], b[k]) for k in a), default=0.)
    if isinstance(a, list):
        assert len(a) == len(b)
        return max((numeric_error(x, y) for x, y in zip(a, b)), default=0.)
    if type(a) in (int, float) and type(b) in (int, float):
        return abs(a-b)
    assert a == b, (a, b)
    return 0.


def preflight():
    guard()
    folder = WORK / 'apparatus-v1'
    folder.mkdir(parents=True, exist_ok=False)
    seed = 181899
    ids = mapping(seed)
    rows = inputs(seed, end=2_000_000)
    rows += [{'kind': 'presentation', 'stimulus': Stimulus(t, ((ids['x1'], 1.), (ids['x2'], .8),
              (ids['x3'], .6)), .1).to_dict()} for t in list(range(200000, 300000, 20000)) + list(range(600000, 700000, 20000))]
    rows.sort(key=lambda r: (int(r['stimulus']['time_us']), r['kind']))
    times = list(range(0, 2_000_001, 20000))
    _, n, nt = execute(folder / 'native', seed, rows, 2_000_000, times)
    _, r, rt = execute(folder / 'reference', seed, rows, 2_000_000, times, backend='reference')
    _, coarse, _ = execute(folder / 'coarse', seed, rows, 2_000_000, [])
    _, resumed, _ = execute(folder / 'restored', seed, rows, 2_000_000, times, restoration=True, pause=True)
    error = numeric_error(nt, rt)
    assert error < 1e-10
    assert n.digest == coarse.digest == resumed.digest
    for s in SEEDS:
        for dose in DOSES:
            sets = [[r['stimulus'] for r in inputs(s, dose, p) if r['kind'] == 'presentation'] for p in PATTERNS]
            sums = [tuple(math.fsum(dict(x['channels'])[mapping(s)[key]] * x['intensity'] for x in rows)
                          for key in ('x1', 'x2', 'x3')) for rows in sets]
            assert sums[0] == sums[1] == sums[2]
            assert all(len(r) == 20 and r[-1]['time_us'] == '3980000' for r in sets)
            assert sets[0][-10:] == sets[1][-10:] == sets[2][-10:]
    save(WORK / 'apparatus.json', {'passed': True, 'native_reference_max_error': error,
         'coarse_fine_final_equal': True, 'pause_restore_equal': True, 'dose_and_final_segment_equal': True})
    print(read(WORK / 'apparatus.json'), flush=True)


@contextmanager
def client_context():
    import httpx
    from threemind_lab.config import load_env
    from threemind_lab.operations_client import OperationsClient
    load_env()
    with OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        yield client


def register():
    assert read(WORK / 'apparatus.json')['passed']
    assert not (WORK / 'science').exists()
    from _threemind_native import _threemind_native as native
    paths = [HERE / name for name in ('study.py', 'protocol.zh.md', 'protocol.en.md')]
    production = [p for package in ('threemind_core', 'threemind_kernels', 'threemind_runtime')
                  for p in (ROOT / 'src' / package).rglob('*.py')]
    frozen = {'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'sources': {p.relative_to(ROOT).as_posix(): sha(p) for p in paths + production},
              'native': {'path': str(native.__file__), 'sha256': sha(native.__file__)},
              'default_config': resolve_kernel(KERNEL).configuration().to_dict(),
              'planned_main_subjects': 24, 'planned_diagnostics': 120}
    save(WORK / 'frozen.json', frozen)
    for p in paths + production:
        target = WORK / 'frozen-source' / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(p, target)
        assert sha(target) == sha(p)
    from threemind_lab.research_recorder import ResearchRecorder
    with client_context() as client:
        rec = ResearchRecorder(WORK, PROJECT, client=client)
        protocol = (HERE / 'protocol.zh.md').read_text('utf8')
        rec.register({'source_key': 'rt63-01:repeat-timing:20261118', 'title': 'RT63-01：重复刺激、间隔与连接保持',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai',
                      'kernels': [KERNEL], 'protocol': protocol, 'protocol_version': digest(protocol),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'blocks': 4, 'main_subjects': 24, 'diagnostic_copies': 120,
                                   'no_kernel_or_default_change': True}}, request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)),
                      'request_id': str(uuid5(NS, 'protocol-' + lang)), 'expected_revision': 0,
                      'kind': 'protocol', 'title': TAG + ' protocol ' + lang,
                      'markdown': (HERE / f'protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True)
        save(WORK / 'registration.json', {'project': PROJECT, 'record': rec.experiment,
                                         'pending': rec.status['pending'], 'registered_before_science': True})
    print(read(WORK / 'registration.json'), flush=True)


def frozen_check():
    frozen = read(WORK / 'frozen.json')
    for rel, expected in frozen['sources'].items():
        assert sha(ROOT / rel) == expected, rel
    assert sha(frozen['native']['path']) == frozen['native']['sha256']


def exchanged(recipient, donor, seed):
    """Declared copy intervention; only weights plus derived edge deadlines change."""
    r = engine(state=recipient)
    r.reconfigure(r.config)
    settled = r.capture_state()
    d = engine(state=donor)
    d.reconfigure(d.config)
    donor_settled = d.capture_state()
    r = engine(state=settled, backend='reference')
    ddoc = donor_settled.to_dict()
    ids = mapping(seed)
    wanted = {ids[k] for k in ('x1', 'x2', 'x3')}
    weights = {(row['source'], row['target']): row['weight'] for row in ddoc['edges']
               if row['source'] in wanted and row['target'] in wanted}
    keys = {key for key in r.edges if key[0] in wanted and key[1] in wanted}
    if keys != set(weights):
        return None, {'reason': 'unequal task topology'}
    changed = []
    for key in sorted(keys):
        edge = r.edges[key]
        old = edge.weight
        # Assignment must not trigger the normal learning setter's age reset.
        object.__setattr__(edge, 'weight', weights[key])
        r._edge_timer(edge)
        changed.append({'edge': list(key), 'old': old, 'new': weights[key]})
    result = r.capture_state()
    before, after = settled.to_dict(), result.to_dict()
    assert before['nodes'] == after['nodes']
    for b, a in zip(before['edges'], after['edges']):
        assert {k:v for k,v in b.items() if k != 'weight'} == {k:v for k,v in a.items() if k != 'weight'}
    for key in before:
        if key not in ('edges', 'timers'):
            assert before[key] == after[key], key
    restored = engine(state=result)
    assert restored.capture_state().digest == result.digest
    return result, {'recipient_sha256': recipient.digest, 'donor_sha256': donor.digest,
                    'settled_sha256': settled.digest, 'donor_settled_sha256': donor_settled.digest,
                    'changed_weights': changed, 'timers_before': before['timers'], 'timers_after': after['timers'],
                    'state_sha256': result.digest}


def run():
    assert read(WORK / 'registration.json')['pending'] == 0
    frozen_check()
    start_wall = time.monotonic()
    with worker_lock(WORK):
        for seed in SEEDS:
            for dose in DOSES:
                guard()
                assert time.monotonic() - start_wall < 1800
                base = WORK / 'science' / f'{seed}' / f'{dose:g}'
                parents = {}
                for pattern in PATTERNS:
                    folder = base / pattern / 'main'
                    result, parents[pattern], _ = execute(folder, seed, inputs(seed, dose, pattern),
                        34_000_000, list(range(4_000_000, 5_000_001, 20000)) + [34_000_000])
                    print(f'{seed} {dose:g} {pattern} main complete; {result["edges"]} edges', flush=True)
                for pattern in PATTERNS:
                    parent = parents[pattern]
                    save(base / pattern / 'quiet-check.json', {'observation': observe(engine(state=parent), mapping(seed)),
                         'queue': parent.to_dict()['queue'], 'parent_sha256': parent.digest})
                    conditions = [('cue', None, True), ('no-cue', None, False), ('sham', pattern, True)]
                    conditions += [('weights-from-' + other, other, True) for other in PATTERNS if other != pattern]
                    for name, donor, cue in conditions:
                        guard()
                        source = parent
                        if donor is not None:
                            source, intervention = exchanged(parent, parents[donor], seed)
                            save(base / pattern / (name + '-intervention.json'), intervention)
                            if source is None:
                                continue
                        execute(base / pattern / name, seed, inputs(seed, begin=34_000_000,
                            end=39_000_000, probe=cue), 39_000_000, list(range(34_000_000, 39_000_001, 20000)), source)
                    print(f'{seed} {dose:g} {pattern} diagnostics complete', flush=True)
                frozen_check()
        results = list((WORK / 'science').rglob('result.json'))
        assert len(results) == 144, ('unexpected incomplete diagnostics', len(results))
        size = sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file())
        assert size < 256 * 2**20
        save(WORK / 'science-complete.json', {'stages': len(results), 'main_subjects': 24, 'diagnostic_copies': 120,
             'wall_seconds': time.monotonic()-start_wall, 'raw_bytes_before_delivery': size,
             'finished_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        print(read(WORK / 'science-complete.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('preflight', 'register', 'run'))
    args = parser.parse_args()
    {'preflight': preflight, 'register': register, 'run': run}[args.command]()
