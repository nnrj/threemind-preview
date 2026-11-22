"""R63m timing replication with the established passive R63k executor."""
import argparse
import gc
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent / 'order_recall'), str(HERE.parent), str(ROOT / 'src')]
import materials_timing as spec
import measurement_timing as measurement
from allocation import disk_allocation
import compact_run as storage
base = storage.base
assert Path(base.__file__).resolve() == HERE.parent / 'order_recall/study.py'
# This research executor receives the newly registered schedule. Production
# kernels and the frozen R63k files are unchanged.
base.spec = spec
base.save = storage.save
s = base.s
PROJECT = base.PROJECT
NS = UUID('3ff9fcf1-9a6e-5c4b-8639-0a42b8c0a85f')
CAP = 1024 * 2**20


def read(path): return json.loads(Path(path).read_bytes())


def frozen_check(work):
    storage.check(work.parent / 'order-recall-63-rerun-v1')
    base.frozen_check(work.parent / 'order-recall-63-rerun-v1')
    f = read(work / 'frozen.json')
    for name, digest in f['sources'].items(): assert s.sha(ROOT / name) == digest
    assert s.sha(work / 'cases.json') == f['cases_sha256']
    assert read(work / 'registration.json')['pending'] == 0


def register(work):
    assert not work.exists()
    previous = read(work.parent / 'order-exchange-63-rerun-v1/publication/completion.json')
    assert previous['coverage'] == 'verified' and previous['pending'] == 0 and not previous['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > 28.125 * 2**30
    historical = spec.historical_check()
    work.mkdir()
    s.base.original(work / 'historical-check.json', historical)
    s.base.original(work / 'measurement-check.json', measurement.synthetic_check())
    s.base.original(work / 'cases.json', spec.parents())
    paths = sorted(p for p in HERE.iterdir() if p.suffix in ('.py', '.md'))
    old_costs = {p['key']: sum(s.allocated(f) for f in (spec.OLD / 'cases' / p['key']).rglob('*') if f.is_file())
                 for p in spec.parents()}
    f = {'kernel': spec.KERNEL, 'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
         'cases_sha256': s.sha(work / 'cases.json'), 'historical_parent_bytes': old_costs,
         'historical_estimate_multiplier': 1.5, 'historical_cost_stop': 2., 'estimate_cost_stop': 1.5,
         'previous_completion_sha256': s.sha(work.parent / 'order-exchange-63-rerun-v1/publication/completion.json')}
    s.base.original(work / 'frozen.json', f)
    for p in paths:
        dest = work / 'frozen-source' / p.name
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(p, dest)
    s.base.load_env()
    import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, PROJECT, client=client)
        rec.register({'source_key': 'r63m:order-timing:20261115:v1', 'title': 'R63m：重复节奏、教学时机与顺序表达',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai', 'kernels': [spec.KERNEL],
                      'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'material_blocks': 4, 'teaching_references': 352, 'diagnostic_copies': 1472}},
                     request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-'+lang)), 'request_id': str(uuid5(NS, 'protocol-'+lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R63m protocol '+lang,
                      'markdown': (HERE / f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result = {'project': PROJECT, 'record': rec.experiment, 'pending': rec.status['pending'], 'registered_before_run': True}
        s.base.original(work / 'registration.json', result)
        print(json.dumps(result), flush=True)


def apparatus(work):
    import psutil
    frozen_check(work)
    assert not any((work / name).exists() for name in ('apparatus.json', 'in-flight.json', 'STOP'))
    with s.base.worker_lock(work), s.base.Guard(work):
        s.base.original(work / 'in-flight.json', {'phase': 'apparatus', 'pid': os.getpid(), 'created': psutil.Process().create_time()})
        checks = []
        for family in ('cadence', 'phase', 'reference'):
            p = next(p for p in spec.parents((100197,)) if p['family'] == family and p['tau'] == 0
                     and p['phase_us'] == 40000 and p['gap_us'] == 50000 and p['order'] == 'AB')
            train, probe = spec.stages(p)[0], spec.stages(p)[-1]
            folder = work / 'apparatus' / family
            _, taught, observer = base.execute(p, train, folder=folder / 'train')
            hashes = {}
            for mode in ('observed', 'plain', 'sparse', 'restored', 'paused'):
                _, final, _ = base.execute(p, probe, taught, folder / mode, mode=mode, observer_state=observer)
                hashes[mode] = final.digest
            assert len(set(hashes.values())) == 1, hashes
            checks.append({'family': family, 'hashes': hashes})
        s.base.original(work / 'apparatus.json', {'passed': True, 'calibration_seed': 100197,
                                                'checks': checks, 'formal_individuals_created': 0})
        (work / 'in-flight.json').unlink()
    shutil.copyfile(work / 'resource-summary.json', work / 'apparatus-resources.json')
    print(json.dumps(read(work / 'apparatus.json')), flush=True)


def run(work):
    import psutil
    frozen_check(work)
    assert read(work / 'apparatus.json')['passed']
    assert not any((work / name).exists() for name in ('summary.json', 'cases', 'in-flight.json', 'STOP'))
    started, completed = time.monotonic(), 0
    costs = read(work / 'frozen.json')['historical_parent_bytes']
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        for parent in spec.parents():
            if (work / 'STOP').exists(): break
            assert guard.thread.is_alive()
            s.base.resource_check(work)
            begin = time.monotonic()
            s.base.original(work / 'in-flight.json', {'unit': parent['key'], 'pid': os.getpid(), 'created': psutil.Process().create_time()})
            folder = work / 'cases' / parent['key']
            train = spec.stages(parent)[0]
            _, taught, observer = base.execute(parent, train, folder=folder / 'train')
            for stage in spec.stages(parent)[1:]:
                base.execute(parent, stage, taught, folder / stage['name'], observer_state=observer)
            completed += 1
            s.base.atomic_json(work / 'current.json', {'completed': completed, 'total': 352, 'last': parent['key']})
            (work / 'in-flight.json').unlink()
            files = [p for p in folder.rglob('*') if p.is_file()]
            size, seconds = sum(disk_allocation(p)['allocated_bytes'] for p in files), time.monotonic()-begin
            old = costs[parent['key']]
            s.base.original(work / 'costs' / f'{completed:03d}.json', {'unit': parent['key'], 'bytes': size,
                              'historical_bytes': old, 'expected_bytes': old*1.5, 'wall_seconds': seconds})
            print(completed, parent['key'], flush=True)
            reason = ('unit storage at least twice historical' if size >= old*2 else
                      'unit exceeds estimate by 50%' if size > old*2.25 else
                      'unit exceeds ten minutes' if seconds > 600 else
                      'two-hour budget' if time.monotonic()-started > 7200 else None)
            if completed % 16 == 0 and sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > CAP:
                reason = 'originals budget'
            if reason:
                s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': parent['key']})
                break
            del taught, observer
            gc.collect()
        if completed == 352:
            s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'references': 352,
                            'probes': 1472, 'stages': 1824, 'independent_blocks': 4, 'wall_seconds': time.monotonic()-started})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('register', 'apparatus', 'run'))
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    {'register': register, 'apparatus': apparatus, 'run': run}[args.action](args.work.resolve())
