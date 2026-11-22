"""Serial, whole-system eight-source replication of the frozen X3 measurements."""
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
import rig as g
import measurement as measure

PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS = UUID('797f4fd7-2ac8-5770-b399-fd69000419d1')
INSTRUMENT_SEED = 1036002
RAW_CAP = 768 * 2**20


def read(p):
    return json.loads(Path(p).read_bytes())


def frozen_check(work):
    value = read(work / 'frozen.json')
    for rel, digest in value['sources'].items() | value['production_sources'].items():
        assert s.sha(ROOT / rel) == digest, rel
    from _threemind_native import _threemind_native as native
    assert s.sha(native.__file__) == value['native_sha256']
    assert s.sha(work / 'cases.json') == value['cases_sha256']
    assert read(work / 'registration.json')['pending'] == 0


def register(work):
    assert not work.exists()
    assert read(work.parent/'body-memory-63-rerun-v1/publication/completion.json')['pending']==0
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > (25 + 2.375) * 2**30
    work.mkdir()
    cases = [{'origin': i, 'seed': g.case_seed('X3', i), 'kind': kind}
             for i in range(8) for kind in g.KINDS]
    s.base.original(work / 'cases.json', cases)
    old = ROOT / 'lab/explorations/2026-10-16-mechanism-discovery'
    paths = [HERE / n for n in ('study.py', 'rig.py', 'measurement.py', 'check_port.py', 'analyze.py', 'protocol.zh.md', 'protocol.en.md')]
    paths += [old / n for n in ('pilot_m1.py', 'pilot_m2.py', 'pilot_m3.py', 'closure_rig.py', 'closure_driver.py', 'closure_analyze.py')]
    paths += [HERE.parent / 'support.py', HERE.parent / 'allocation.py', ROOT / 'lab/tools/study_lock.py',
              ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
    from _threemind_native import _threemind_native as native
    production = read(work.parent / 'stimulus-63-rerun-v1/frozen.json')
    frozen = {'kernel': g.KERNEL, 'native_sha256': s.sha(native.__file__),
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'production_sources': {k: v for k, v in production['sources'].items() if k.startswith(('src/', 'crates/'))},
              'cases_sha256': s.sha(work / 'cases.json'), 'instrument_seed': INSTRUMENT_SEED}
    s.base.original(work / 'frozen.json', frozen)
    from check_port import check
    s.base.original(work / 'measurement-port-check.json', check())
    for p in paths + [ROOT/rel for rel in frozen['production_sources']]:
        dest = work / 'frozen-source' / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, PROJECT, client=client)
        rec.register({'source_key': 'r63d:criteria:6.3:20261115:v1', 'title': 'R63d：6.3四项自主活动判据八来源复验',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai', 'kernels': [g.KERNEL],
                      'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'independent_origins': 8, 'system_implementations': 5, 'criteria': 'cross-system-criteria/2',
                                   'additional_validity_check': 'teaching-only Core matching', 'confirmation_origins': 0}},
                     request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R63d protocol ' + lang,
                      'markdown': (HERE / f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result = {'project': PROJECT, 'record': rec.experiment, 'pending': rec.status['pending'], 'registered_before_run': True}
        s.base.original(work / 'registration.json', result)
        print(json.dumps(result), flush=True)


def apparatus(work):
    import psutil
    frozen_check(work)
    assert not any((work / n).exists() for n in ('apparatus.json', 'in-flight.json', 'STOP'))
    with s.base.worker_lock(work), s.base.Guard(work):
        s.base.original(work / 'in-flight.json', {'phase': 'apparatus', 'pid': os.getpid(), 'created': psutil.Process().create_time()})
        systems = {}
        for kind in g.KINDS:
            parent = g.Rig(kind, INSTRUMENT_SEED)
            records = g.teaching(parent, 0)
            selection = (g.rnn_selection(parent, records) if kind == 'fixed-rnn-reader' else
                         g.matching(parent, records) if kind == 'threemind' else None)
            measure.save(work / 'apparatus', kind + '-parent', parent)
            hashes = {}
            for mode in ('plain', 'observed', 'restored', 'paused'):
                child = g.Rig.restore(parent.save())
                g.probe(child, 'X', second='Y', frequent=mode == 'observed', restore_mid=mode == 'restored', pause_mid=mode == 'paused')
                hashes[mode] = g.m.digest(child.save())
                measure.save(work / 'apparatus', kind + '-' + mode, child)
            restored, _ = g.intervene(parent, 'restored', selection)
            sham, _ = g.intervene(parent, 'sham', selection)
            expected = parent.save()
            expected['branch'] = {'parent_sha256': g.m.digest(parent.save()), 'label': 'sham', 'time_us': parent.time}
            valid = (len(set(hashes.values())) == 1 and restored.save() == parent.save() and sham.save() == expected
                     and (selection is None or selection['passed']))
            systems[kind] = {'hashes': hashes, 'selection': selection, 'sham_only_declared_lineage': sham.save() == expected,
                             'restoration_exact': restored.save() == parent.save(), 'passed': valid}
        result = {'passed': all(v['passed'] for v in systems.values()), 'systems': systems,
                  'scientific_origins': 0, 'seed': INSTRUMENT_SEED}
        s.base.original(work / 'apparatus.json', result)
        # A failed observation check preserves its in-flight witness for review.
        assert result['passed'], 'Apparatus invalid; preserve evidence and marker'
        (work / 'in-flight.json').unlink()
    s.base.original(work / 'apparatus-resources.json', read(work / 'resource-summary.json'))
    print(json.dumps(result), flush=True)


def run(work):
    import psutil
    frozen_check(work)
    assert read(work / 'apparatus.json')['passed']
    assert not any((work / n).exists() for n in ('summary.json', 'in-flight.json', 'STOP'))
    start = time.monotonic()
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        completed = []
        for case in read(work / 'cases.json'):
            if (work / 'STOP').exists(): break
            assert guard.thread.is_alive(), 'Resource guard absent'
            s.base.resource_check(work)
            name = f"o{case['origin']}-{case['kind']}"
            folder = work / 'units' / name
            path = folder / 'result.json'
            if path.exists():
                result = read(path)
                assert result['origin'] == case['origin'] and result['kind'] == case['kind']
                assert all(p.exists() for p in (folder / 'h0-parent.json.gz', folder / 'h1-parent.json.gz'))
            else:
                assert g.case_seed('X3', case['origin']) == case['seed']
                s.base.original(work / 'in-flight.json', {'unit': name, 'pid': os.getpid(), 'created': psutil.Process().create_time()})
                result = measure.x3(folder, case['origin'], case['kind'])
                result['valid'] = all(r['selection'] is None or r['selection']['passed'] for r in result['histories'])
                s.base.original(path, result)
                (work / 'in-flight.json').unlink()
            completed.append(name)
            s.base.atomic_json(work / 'current.json', {'completed': len(completed), 'total': 40, 'last': name})
            print(name, flush=True)
            reason = ('invalid matching' if not result['valid'] else
                      'originals budget' if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > RAW_CAP else
                      'two-hour budget' if time.monotonic() - start > 7200 else None)
            if reason:
                s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': name})
                break
        if len(completed) == 40:
            s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'origins': 8, 'systems': 40,
                                                  'wall_seconds': time.monotonic() - start})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['register', 'apparatus', 'run'])
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    {'register': register, 'apparatus': apparatus, 'run': run}[args.action](args.work.resolve())
