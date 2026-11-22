"""R63t4: original-scale continuous delayed choice, with fixed historical profiles."""
import argparse
from copy import deepcopy
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanism as h
import decision_design as d
import decision_execute as x
s = h.s
e = h.e
ROOT = h.ROOT
read = s.base.read
allocated = h.allocated
NS = UUID('a949984c-44bb-577c-9894-15322d3aee70')
CAP = 2 * 2**30
HISTORY = Path('E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/delayed-choice61-v1')


def check(work):
    f = read(work / 'frozen.json')
    for rel, sha in f['sources'].items():
        assert s.sha(ROOT / rel) == sha, rel
    for rel, sha in f['materials'].items():
        assert s.sha(work / rel) == sha, rel
    for rel, sha in f['references'].items():
        assert s.sha(work.parent / rel) == sha, rel
    for rel, sha in f['historical'].items():
        assert s.sha(HISTORY / rel) == sha, rel
    assert s.sha(h.previous.native()) == f['native_sha256']
    assert read(work / 'registration.json')['pending'] == 0
    assert s.sha(work / 'cases.json') == f['cases_sha256']
    assert s.sha(work / 'measurement-validation.json') == f['measurement_validation_sha256']
    return f


def register(work):
    assert not work.exists()
    prior = work.parent / 'dynamics-function-63-rerun-v1'
    h.check(prior)
    for src in (prior, work.parent / 'persistent-activity-63-rerun-v1'):
        completion = read(src / 'publication/completion.json')
        assert completion['coverage'] == 'verified' and completion['pending'] == 0 and not completion['scientific_stop']
    import verify_decision
    proof = verify_decision.verify()
    assert proof['passed']
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free > 31.125 * 2**30
    cases = d.table()
    for c in cases:
        e.base.resolve_kernel('threemind.continuous-memory/6.3').configuration(
            {'seed': c['seed'], 'depletion_enabled': c['task'] == 'prefix',
             'stp_facilitation_tau_s': 1. if c['task'] == 'pair' else 0.,
             'edge_consolidation_enabled': True, **c['patch']})
    work.mkdir()
    s.base.original(work / 'measurement-validation.json', proof)
    s.base.original(work / 'cases.json', cases)
    old = work.parent / 'persistent-activity-63-rerun-v1'
    oldcases = read(old / 'cases.json')
    materials = {}
    for task in ('pair', 'prefix'):
        for swap in (0, 1):
            key = f'retention/s{swap}/011/paired/train' if task == 'pair' else f'short/train-{swap}'
            c = next(c for c in oldcases if c['variant'] == 'v63' and c['material_key'] == key)
            rows = e.material_frames(c, old / 'materials')
            assert all(r['enqueue_us'] <= int(r['stimulus']['time_us']) for r in rows)
            dest = work / 'materials' / f'{task}-s{swap}.json'
            s.base.original(dest, {'source_work': str(old), 'source_case': c, 'frames': rows,
                'end_us': c['end_us'], 'original_sha256': s.sha(old / 'materials' / key / 'frames.jsonl')})
            materials[dest.relative_to(work).as_posix()] = s.sha(dest)
    # Replicate the same four historical configurations; a newly preferred candidate is not silently substituted.
    selection = {'selected': d.PROFILES, 'selection': 'original R51t4 four profiles frozen for direct replication',
        'current_mechanism_selection': read(prior / 'candidate-selection.json'),
        'source_analysis_sha256': s.sha(prior / 'analysis.json'), 'formal_new_material_used': False}
    s.base.original(work / 'candidate-selection.json', selection)
    materials['candidate-selection.json'] = s.sha(work / 'candidate-selection.json')
    paths = [HERE / n for n in ('decision.py', 'decision_execute.py', 'decision_design.py', 'decision_analysis.py',
        'verify_decision.py', 'decision_protocol.zh.md', 'decision_protocol.en.md', 'mechanism.py', 'mechanism_design.py')]
    for sub in ('persistent_cause', 'memory_timescales', 'body_recovery'):
        paths += list((HERE.parent / sub).glob('*.py'))
    paths += list((ROOT / 'src/threemind_kernels').glob('*.py')) + [Path(s.__file__), Path(s.base.__file__)]
    sources = {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths}
    refs = {p.relative_to(work.parent).as_posix(): s.sha(p)
            for src in (prior, old) for p in (src / 'analysis.json', src / 'audit.json', src / 'publication/completion.json')}
    selection_path = prior / 'candidate-selection.json'
    refs[selection_path.relative_to(work.parent).as_posix()] = s.sha(selection_path)
    s.base.original(work / 'frozen.json', {'sources': sources, 'materials': materials, 'references': refs,
        'native_sha256': s.sha(h.previous.native()), 'cases_sha256': s.sha(work / 'cases.json'),
        'measurement_validation_sha256': s.sha(work / 'measurement-validation.json'),
        'historical': {n: s.sha(HISTORY / n) for n in ('cases.json', 'analysis.json', 'publication/completion.json')},
        'old_allocated_bytes': {c['key']: allocated(HISTORY / 'cases' / c['key']) for c in cases},
        'systems': 64, 'independent_blocks': 4, 'originals_cap_bytes': CAP})
    for rel in sources:
        dst = work / 'frozen-source' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    s.base.load_env()
    import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False), require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, e.base.PROJECT, client=client)
        rec.register({'source_key': 'r63t4:delayed-choice:20261116:v1', 'title': 'R63t4：持续活动、延迟选择与前缀信息',
            'classification': 'formal', 'execution_status': 'running', 'executor': 'ai',
            'kernels': ['threemind.continuous-memory/6.3'], 'protocol': (HERE / 'decision_protocol.zh.md').read_text('utf8'),
            'protocol_version': s.sha(HERE / 'decision_protocol.zh.md'), 'required_roles': ['protocol', 'report', 'note', 'original'],
            'metadata': {'blocks': 4, 'systems': 64, 'prospective_replication': True}}, request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                'expected_revision': 0, 'kind': 'protocol', 'title': 'R63t4 protocol ' + lang,
                'markdown': (HERE / f'decision_protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True)
        result = {'project': e.base.PROJECT, 'record': rec.experiment, 'pending': rec.status['pending'], 'registered_before_run': True}
        s.base.original(work / 'registration.json', result)
    print(json.dumps(result), flush=True)


def apparatus(work):
    frozen = check(work)
    assert not any((work / n).exists() for n in ('apparatus', 'apparatus.json', 'in-flight.json', 'STOP'))
    import psutil
    c = deepcopy(d.table()[0])
    c.update(seed=941199, key='apparatus', patch=d.PROFILES['short-inhibition'])
    hashes = {}
    observers = []
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        s.base.original(work / 'in-flight.json', {'phase': 'apparatus', 'pid': os.getpid(), 'created': psutil.Process().create_time()})
        for mode in ('observed', 'dense', 'plain', 'restored', 'paused'):
            _, image, observer = x.execute(c, work / 'apparatus' / mode, work, mode=mode, calibration=True)
            hashes[mode] = image.digest
            observers.append(observer)
            assert guard.thread.is_alive() and not (work / 'STOP').exists()
        assert len(set(hashes.values())) == 1 and all(v == observers[0] for v in observers)
        old_app = allocated(HISTORY / 'apparatus/observed')
        ratio = allocated(work / 'apparatus/observed') / old_app
        factor = max(1.1, ratio) * 1.25
        estimate = allocated(work) + sum(frozen['old_allocated_bytes'].values()) * factor + 128 * 2**20
        budget = ratio < 2 and estimate < CAP
        s.base.original(work / 'apparatus.json', {'passed': True, 'budget_passed': budget,
            'hashes': hashes, 'same_observers': True, 'separate_encoding': True,
            'allocation_ratio': ratio, 'estimate_factor': factor, 'estimated_full_bytes': estimate,
            'formal_individuals_created': 0})
        (work / 'in-flight.json').unlink()
    shutil.copyfile(work / 'resource-summary.json', work / 'apparatus-resources.json')
    print(json.dumps({'passed': True, 'budget_passed': budget, 'hashes': hashes}), flush=True)


def run(work):
    frozen = check(work)
    app = read(work / 'apparatus.json')
    assert app['passed'] and app['budget_passed']
    assert not any((work / n).exists() for n in ('cases', 'summary.json', 'in-flight.json', 'STOP'))
    assert shutil.disk_usage(work).free > 31.125 * 2**30
    import psutil
    table = read(work / 'cases.json')
    n = 0
    started = time.monotonic()
    accounted = allocated(work) + 128 * 2**20
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        for c in table:
            if (work / 'STOP').exists():
                break
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            try:
                r, state, observer = x.execute(c, work / 'cases' / c['key'], work)
            except x.SafePause:
                break
            n += 1
            size = allocated(work / 'cases' / c['key'])
            old_size = frozen['old_allocated_bytes'][c['key']]
            cost = work / 'costs' / f'{n:03d}.json'
            s.base.original(cost, {'key': c['key'], 'bytes': size, 'historical_bytes': old_size,
                'wall_seconds': r['wall_seconds'], 'allocation_method': 'FileStandardInfo'})
            accounted += size + h.previous.disk_allocation(cost)['allocated_bytes']
            s.base.atomic_json(work / 'current.json', {'complete': n, 'total': 64, 'last': c['key'], 'elapsed_seconds': time.monotonic() - started})
            reason = ('matched allocation at least twice historical' if size >= 2 * old_size else
                'unit exceeds frozen estimate by 50%' if size > 1.5 * app['estimate_factor'] * old_size else
                'originals budget' if accounted > CAP else 'two-hour host budget' if time.monotonic() - started > 7200 else None)
            print(json.dumps({'complete': n, 'key': c['key'], 'seconds': r['wall_seconds']}), flush=True)
            del state, observer
            gc.collect()
            if reason:
                s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': c['key']})
                break
        if n == 64:
            assert allocated(work) <= accounted < CAP
            s.base.original(work / 'summary.json', {'complete': n, 'wall_seconds': time.monotonic() - started})
    print(json.dumps({'complete': n, 'total': 64}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('register', 'check', 'apparatus', 'run'))
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    globals()[args.action](args.work)
