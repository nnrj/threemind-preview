"""R63g: serial, preregistered eight-source local transfer replication."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT / 'src')]
import support as s
import transfer_rig as g
# The shared rig adds its own directory; select this batch's measurement module.
sys.path.insert(0, str(HERE))
import measurement as measure
assert Path(measure.__file__).resolve() == HERE / 'measurement.py'

PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS = UUID('413a65a7-de91-522f-94bd-2c82fbed89b2')
INSTRUMENT_SEED = 1016002
RAW_CAP = 256 * 2**20


def read(path): return json.loads(Path(path).read_bytes())


def frozen_check(work):
    frozen = read(work / 'frozen.json')
    for rel, digest in frozen['sources'].items() | frozen['production_sources'].items():
        assert s.sha(ROOT / rel) == digest, rel
    from _threemind_native import _threemind_native as native
    assert s.sha(native.__file__) == frozen['native_sha256']
    assert s.sha(work / 'cases.json') == frozen['cases_sha256']
    assert read(work / 'registration.json')['pending'] == 0


def register(work):
    assert not work.exists()
    for batch in ('criteria-confirmation-63-rerun-v1', 'body-transfer-63-rerun-v1'):
        done = read(work.parent / batch / 'publication/completion.json')
        assert done['coverage'] == 'verified' and done['pending'] == 0 and not done['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > 25.875 * 2**30
    work.mkdir()
    s.base.original(work / 'cases.json', [{'origin': i, 'seed': g.case_seed('X1', i)} for i in range(8)])
    old = ROOT / 'lab/explorations/2026-10-16-mechanism-discovery'
    paths = [HERE / name for name in ('study.py', 'transfer_rig.py', 'measurement.py', 'analyze.py',
                                     'check_port.py', 'protocol.zh.md', 'protocol.en.md')]
    paths += [HERE.parent / 'criteria/rig.py', HERE.parent / 'support.py', HERE.parent / 'allocation.py',
              ROOT / 'lab/tools/study_lock.py',
              ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
    paths += [old / name for name in ('pilot_m1.py', 'pilot_m2.py', 'pilot_m3.py', 'closure_rig.py',
                                    'closure_driver.py', 'closure_analyze.py')]
    from _threemind_native import _threemind_native as native
    frozen = {'kernel': g.base.KERNEL, 'native_sha256': s.sha(native.__file__),
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'production_sources': read(work.parent / 'criteria-63-rerun-v1/frozen.json')['production_sources'],
              'cases_sha256': s.sha(work / 'cases.json'), 'instrument_seed': INSTRUMENT_SEED}
    s.base.original(work / 'frozen.json', frozen)
    from check_port import check
    s.base.original(work / 'measurement-port-check.json', check())
    for p in paths:
        dest = work / 'frozen-source' / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, PROJECT, client=client)
        rec.register({'source_key': 'r63g:local-transfer:6.3:20261115:v1', 'title': 'R63g：6.3局部连接移植与二门选择',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai', 'kernels': [g.base.KERNEL],
                      'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'independent_origins': 8, 'parents': 16, 'arms': 7, 'probes': 672}},
                     request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R63g protocol ' + lang,
                      'markdown': (HERE / f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result = {'project': PROJECT, 'record': rec.experiment, 'pending': rec.status['pending'], 'registered_before_run': True}
        s.base.original(work / 'registration.json', result)
        print(json.dumps(result), flush=True)


def numerical_equal(a, b):
    if type(a) is not type(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(numerical_equal(a[k], b[k]) for k in a)
    if isinstance(a, list): return len(a) == len(b) and all(numerical_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float): return abs(a - b) <= 1e-12
    return a == b


def settlement_comparison(lazy, settled, before, after):
    """Account for the two visit counters added by an explicit same-time operation."""
    import copy
    left, right = copy.deepcopy(lazy), copy.deepcopy(settled)
    deltas = {}
    for key in ('node_visits', 'edge_visits'):
        expected = after['model']['audit'][key] - before['model']['audit'][key]
        actual = right['model']['audit'][key] - left['model']['audit'][key]
        deltas[key] = {'declared_preparation': expected, 'after_continuation': actual}
        if actual != expected:
            return False, deltas
        right['model']['audit'][key] = left['model']['audit'][key]
    return numerical_equal(left, right), deltas


def apparatus(work):
    import psutil
    frozen_check(work)
    assert not any((work / n).exists() for n in ('apparatus.json', 'in-flight.json', 'STOP'))
    with s.base.worker_lock(work), s.base.Guard(work):
        s.base.original(work / 'in-flight.json', {'phase': 'apparatus', 'pid': os.getpid(), 'created': psutil.Process().create_time()})
        parents, matches = {}, {}
        for h in (0, 1):
            p = g.Rig('threemind', INSTRUMENT_SEED)
            teaching = g.teaching(p, h)
            measure.save(work / 'apparatus', f'h{h}-before-settlement', p)
            original = p.save(); g.settle(p)
            assert p.time == original['time_us']
            measure.save(work / 'apparatus', f'h{h}-settled', p)
            # Explicit intervention preparation: compare continuation from lazy and settled states.
            lazy, settled = g.Rig.restore(original), g.Rig.restore(p.save())
            g.probe(lazy, 'X', gate=True); g.probe(settled, 'X', gate=True)
            trace_equal = numerical_equal(lazy.rows, settled.rows)
            g.settle(lazy); g.settle(settled)
            settlement_equal, visit_deltas = settlement_comparison(lazy.save(), settled.save(), original, p.save())
            measure.save(work / 'apparatus', f'h{h}-lazy-continued', lazy)
            measure.save(work / 'apparatus', f'h{h}-settled-continued', settled)
            parents[h] = p
            matches[h] = {'matching': g.matching(p, teaching), 'settlement_trace_equal': trace_equal,
                          'settlement_continuation_equal': settlement_equal,
                          'declared_preparation_visit_counts': visit_deltas,
                          'settlement_changed_paths': g.differences(original, p.save())}
        hashes = {}
        for mode in ('plain', 'observed', 'restored', 'paused'):
            c = g.Rig.restore(parents[0].save())
            g.probe(c, 'X', gate=True, frequent=mode == 'observed', restore_mid=mode == 'restored', pause_mid=mode == 'paused')
            hashes[mode] = g.m.digest(c.save()); measure.save(work / 'apparatus', mode, c)
        receipts = {}
        for sources, mode in (('XY', 'bundle'), ('ZW', 'bundle'), ('XY', 'persistent'), ('XY', 'fast')):
            child, receipt = g.transfer(parents[0], parents[1], sources, mode)
            receipts[sources + '-' + mode] = receipt
            measure.save(work / 'apparatus', sources + '-' + mode, child)
        sham, _ = g.transfer(parents[0], parents[0])
        changed, _ = g.transfer(parents[0], parents[1])
        restored, _ = g.transfer(changed, parents[0])
        result = {'scientific_origins': 0, 'seed': INSTRUMENT_SEED, 'hashes': hashes, 'matches': matches,
                  'receipts': receipts, 'sham_exact': sham.save() == parents[0].save(),
                  'restoration_exact': restored.save() == parents[0].save(), 'settlement_float_tolerance': 1e-12}
        result['passed'] = (len(set(hashes.values())) == 1 and result['sham_exact'] and result['restoration_exact']
                            and all(v['matching']['passed'] and v['settlement_trace_equal'] and v['settlement_continuation_equal']
                                    for v in matches.values()))
        s.base.original(work / 'apparatus.json', result)
        assert result['passed'], 'Invalid apparatus; keep evidence and marker'
        (work / 'in-flight.json').unlink()
    s.base.original(work / 'apparatus-resources.json', read(work / 'resource-summary.json'))
    print(json.dumps(result), flush=True)


def run(work):
    import psutil
    frozen_check(work)
    assert read(work / 'apparatus.json')['passed']
    assert not any((work / n).exists() for n in ('summary.json', 'in-flight.json', 'STOP'))
    start = time.monotonic(); completed = []
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        for case in read(work / 'cases.json'):
            if (work / 'STOP').exists(): break
            assert guard.thread.is_alive()
            s.base.resource_check(work)
            name = f"o{case['origin']}"; folder = work / 'units' / name
            assert not (folder / 'result.json').exists(), 'Inspect complete boundary before any resume'
            assert g.case_seed('X1', case['origin']) == case['seed']
            s.base.original(work / 'in-flight.json', {'unit': name, 'pid': os.getpid(), 'created': psutil.Process().create_time()})
            result = measure.x1(folder, case['origin'])
            s.base.original(folder / 'result.json', result)
            (work / 'in-flight.json').unlink()
            completed.append(name)
            s.base.atomic_json(work / 'current.json', {'completed': len(completed), 'total': 8, 'last': name})
            print(name, flush=True)
            reason = ('invalid matching' if not result['valid'] else
                      'originals budget' if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > RAW_CAP else
                      'two-hour budget' if time.monotonic() - start > 7200 else None)
            if reason:
                s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': name}); break
        if len(completed) == 8:
            s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'origins': 8, 'probes': 672,
                                                  'wall_seconds': time.monotonic() - start})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['register', 'apparatus', 'run'])
    p.add_argument('--work', type=Path, required=True); a = p.parse_args()
    {'register': register, 'apparatus': apparatus, 'run': run}[a.action](a.work.resolve())
