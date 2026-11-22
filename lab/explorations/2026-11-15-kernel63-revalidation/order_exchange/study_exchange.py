"""R63l: registered state exchanges on complete R63k-derived research copies."""
import argparse
import copy
import gc
import gzip
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
import materials
import intervention
import compact_run as previous
import measurement
from allocation import disk_allocation
base = previous.base
s = base.s
base.save = previous.save
assert Path(base.__file__).resolve() == HERE.parent / 'order_recall/study.py'
NS = UUID('668ea693-6a06-5835-bf83-f266279e6177')
PROJECT = base.PROJECT
CAP = 512 * 2**20


def read(path): return json.loads(Path(path).read_bytes())
def gz(path): return json.loads(gzip.decompress(Path(path).read_bytes()))


def differences(a, b, path=()):
    if isinstance(a, dict) and isinstance(b, dict):
        assert a.keys() == b.keys()
        return [row for k in a for row in differences(a[k], b[k], path+(k,))]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [row for i, (x, y) in enumerate(zip(a, b)) for row in differences(x, y, path+(i,))]
    return [] if a == b else [{'path': list(path), 'before': a, 'after': b}]


def settled(image):
    engine = base.engine(state=image)
    assert engine.capture_state().digest == image.digest
    before = engine.capture_state().to_dict()
    engine.reconfigure(engine.config)
    result = engine.capture_state()
    after = result.to_dict()
    for key in ('time_us', 'sequence', 'next_event', 'queue', 'config', 'definition', 'definition_hash'):
        assert before[key] == after[key], key
    assert not after['queue'] and after['life'] == 'active'
    return result, {'operation': 'public same-time reconfigure with identical configuration on a research copy',
                    'before_sha256': image.digest, 'after_sha256': result.digest,
                    'advanced_us': 0, 'changes': differences(before, after)}


def trajectory_error(a, b):
    left = {p['time_us']: p for p in a['points']}
    right = {p['time_us']: p for p in b['points']}
    assert left.keys() == right.keys() and len(left) == 251
    error = 0.
    for t in left:
        an, bn = ({n['channel']: n for n in row[t]['nodes']} for row in (left, right))
        assert an.keys() == bn.keys()
        for channel in an:
            for field in materials.recall.FIELDS:
                error = max(error, abs(an[channel][field]-bn[channel][field]))
    assert error <= 1e-12, error
    return error


def frozen_check(work):
    previous.check(work.parent / 'order-recall-63-rerun-v1')
    base.frozen_check(work.parent / 'order-recall-63-rerun-v1')
    f = read(work / 'frozen.json')
    for relative, digest in f['sources'].items(): assert s.sha(ROOT / relative) == digest
    for relative, digest in f['parent_sources'].items(): assert s.sha(work.parent / 'order-recall-63-rerun-v1' / relative) == digest
    assert s.sha(work / 'cases.json') == f['cases_sha256']
    assert read(work / 'registration.json')['pending'] == 0


def register(work):
    assert not work.exists()
    parent = work.parent / 'order-recall-63-rerun-v1'
    completion = read(parent / 'publication/completion.json')
    assert completion['coverage'] == 'verified' and completion['pending'] == 0 and not completion['scientific_stop']
    assert read(parent / '.research-records/status.json')['pending'] == 0
    previous.check(parent); base.frozen_check(parent)
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > 26.625 * 2**30
    historical = materials.historical_check()
    work.mkdir()
    s.base.original(work / 'historical-check.json', historical)
    s.base.original(work / 'cases.json', materials.parents())
    s.base.original(work / 'measurement-check.json', measurement.synthetic_check())
    parent_sources = {}
    for p in materials.parents():
        for tail in ('train/final.tmind', 'train/observer.json', 'train/result.json', 'wait30/cue0/pre-probe.tmind', 'wait30/cue0.5/pre-probe.tmind'):
            name = f"cases/{p['key']}/{tail}"
            parent_sources[name] = s.sha(parent / name)
    for name in ('publication/completion.json', 'frozen.json', 'audit.json', 'analysis.json'):
        parent_sources[name] = s.sha(parent / name)
    paths = sorted(p for p in HERE.iterdir() if p.suffix in ('.py', '.md'))
    old_costs = {}
    for seed, tau in itertools.product(materials.recall.SEEDS, (0, 1)):
        files = [p for p in (materials.OLD / f'cases/swap/{seed}/f{tau}').rglob('*') if p.is_file()]
        old_costs[f'{seed}/f{tau}'] = sum(disk_allocation(p)['allocated_bytes'] for p in files)
    frozen = {'kernel': materials.recall.KERNEL, 'parent_record': completion['record'],
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'parent_sources': parent_sources, 'cases_sha256': s.sha(work / 'cases.json'),
              'historical_unit_bytes': old_costs, 'estimated_multiplier': 1.5,
              'historical_multiplier_stop': 2., 'budget_multiplier_stop': 1.5}
    s.base.original(work / 'frozen.json', frozen)
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
        rec.register({'source_key': 'r63l:order-state-exchange:20261115:v1', 'title': 'R63l：6.3事件顺序的内部状态定位',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai',
                      'kernels': [materials.recall.KERNEL], 'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'),
                      'protocol_version': s.sha(HERE / 'protocol.zh.md'), 'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'material_blocks': 4, 'held_references': 16, 'diagnostic_copies': 512, 'parent_record': completion['record']}},
                     request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-'+lang)), 'request_id': str(uuid5(NS, 'protocol-'+lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R63l protocol '+lang,
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
        proofs = []
        for tau in (0., 1.):
            entries = {}
            for p in [p for p in materials.parents((100198,)) if p['tau'] == tau]:
                folder = work / 'apparatus' / p['key']
                train = materials.recall.stages(p)[0]
                _, taught, observer = base.execute(p, train, folder=folder / 'train')
                _, held, observer = base.execute(p, materials.hold_stage(p), taught, folder / 'hold', observer_state=observer)
                aligned, prep = settled(held)
                base.save(folder / 'settled.tmind', aligned)
                s.base.original(folder / 'preparation.json', prep)
                for name, image in (('original', held), ('aligned', aligned)):
                    stage = dict(materials.probe_stage(p, .5), name=name)
                    base.execute(p, stage, image, folder / name, observer_state=observer)
                error = trajectory_error(gz(folder / 'original/trajectory.json.gz'), gz(folder / 'aligned/trajectory.json.gz'))
                entries[p['order']] = aligned
                proofs.append({'tau': tau, 'order': p['order'], 'preparation_response_error': error})
            for order in ('AB', 'BA'):
                for groups in materials.groups():
                    result, receipt = intervention.exchange(entries[order], entries[order[::-1]], groups)
                    restored = base.engine(state=result).capture_state()
                    assert restored.digest == result.digest
                    assert intervention.exchange(entries[order], entries[order], groups)[0].digest == entries[order].digest
                    destination = work / 'apparatus/exchanges' / f'f{tau:g}' / order
                    label = ''.join(groups) or 'none'
                    base.save(destination / (label+'.tmind'), result)
                    s.base.original(destination / (label+'.json'), receipt)
        s.base.original(work / 'apparatus.json', {'passed': True, 'calibration_seed': 100198,
                                                'native_combinations': 64, 'exact_self_exchanges': 64,
                                                'preparation_response_checks': proofs, 'formal_individuals_created': 0})
        (work / 'in-flight.json').unlink()
    shutil.copyfile(work / 'resource-summary.json', work / 'apparatus-resources.json')
    print(json.dumps(read(work / 'apparatus.json')), flush=True)


def run(work):
    import psutil
    frozen_check(work)
    assert read(work / 'apparatus.json')['passed']
    assert not any((work / name).exists() for name in ('summary.json', 'in-flight.json', 'STOP', 'cases'))
    parent_work = work.parent / 'order-recall-63-rerun-v1'
    start, completed = time.monotonic(), 0
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        for seed, tau in itertools.product(materials.recall.SEEDS, (0, 1)):
            if (work / 'STOP').exists(): break
            assert guard.thread.is_alive()
            s.base.resource_check(work)
            key, began = f'{seed}/f{tau}', time.monotonic()
            unit = work / 'cases' / key
            s.base.original(work / 'in-flight.json', {'unit': key, 'pid': os.getpid(), 'created': psutil.Process().create_time()})
            entries = {}
            for p in [p for p in materials.parents() if p['seed'] == seed and p['tau'] == tau]:
                parent = parent_work / 'cases' / p['key']
                _, held, observer = base.execute(p, materials.hold_stage(p), base.image(parent / 'train/final.tmind'),
                                                unit / p['order'] / 'hold', observer_state=read(parent / 'train/observer.json'))
                assert all(held.digest == base.image(parent / f'wait30/cue{cue}/pre-probe.tmind').digest for cue in ('0', '0.5'))
                aligned, preparation = settled(held)
                base.save(unit / p['order'] / 'settled.tmind', aligned)
                s.base.original(unit / p['order'] / 'preparation.json', preparation)
                entries[p['order']] = p, aligned, observer
            for order, groups in itertools.product(('AB', 'BA'), materials.groups()):
                p, aligned, observer = entries[order]
                image, receipt = intervention.exchange(aligned, entries[order[::-1]][1], groups)
                assert base.engine(state=image).capture_state().digest == image.digest
                label = ''.join(groups) or 'none'
                folder = unit / order / label
                base.save(folder / 'intervened.tmind', image)
                s.base.original(folder / 'intervention.json', receipt)
                for cue in (0., .5):
                    stage = dict(materials.probe_stage(p, cue), name=f'{label}/cue{cue:g}')
                    base.execute(p, stage, image, folder / f'cue{cue:g}', observer_state=observer)
            completed += 1
            s.base.atomic_json(work / 'current.json', {'completed': completed, 'total': 8, 'last': key})
            (work / 'in-flight.json').unlink()
            files = [p for p in unit.rglob('*') if p.is_file()]
            size = sum(disk_allocation(p)['allocated_bytes'] for p in files)
            old = read(work / 'frozen.json')['historical_unit_bytes'][key]
            seconds = time.monotonic()-began
            s.base.original(work / 'costs' / f'{completed}.json', {'unit': key, 'bytes': size, 'historical_bytes': old,
                                                                'expected_bytes': old*1.5, 'wall_seconds': seconds})
            print(key, flush=True)
            reason = ('unit storage at least twice historical' if size >= 2*old else
                      'unit exceeds estimate by 50%' if size > 2.25*old else
                      'unit exceeds ten minutes' if seconds > 600 else
                      'two-hour budget' if time.monotonic()-start > 7200 else
                      'originals budget' if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > CAP else None)
            if reason:
                s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': key})
                break
            gc.collect()
        if completed == 8:
            s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'units': 8, 'references': 16,
                                                  'probes': 512, 'independent_blocks': 4, 'wall_seconds': time.monotonic()-start})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('register', 'apparatus', 'run'))
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    {'register': register, 'apparatus': apparatus, 'run': run}[args.action](args.work.resolve())
