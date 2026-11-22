"""Independent 64-source confirmation; reuse the frozen R51g apparatus unchanged."""
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
PILOT = HERE.parent / 'criteria'
OLD = ROOT / 'lab/explorations/2026-10-16-mechanism-discovery'
sys.path[:0] = [str(PILOT), str(HERE.parent), str(ROOT / 'src')]
import support as s
import rig as g
import measurement as measure
from check_port import check

PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS = UUID('476553c4-7a50-530a-a64e-861f11bc5fa3')
N = 64
OFFSET = 60000
INSTRUMENT_SEED = 1096002
RAW_CAP = 4 * 2**30


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
    previous = read(work.parent / 'criteria61-v1/publication/completion.json')
    assert previous['coverage'] == 'verified' and previous['pending'] == 0 and not previous['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > (25 + 12.125) * 2**30
    work.mkdir()
    cases = [{'origin': i, 'rig_origin': OFFSET + i, 'seed': 1096100 + i, 'systems': list(g.KINDS)} for i in range(N)]
    s.base.original(work / 'cases.json', cases)
    paths = [HERE / n for n in ('study.py', 'analyze.py', 'check_statistics.py', 'protocol.zh.md', 'protocol.en.md')]
    paths += [PILOT / n for n in ('rig.py', 'measurement.py', 'check_port.py')]
    paths += [OLD / n for n in ('pilot_m1.py', 'pilot_m2.py', 'pilot_m3.py', 'closure_rig.py', 'closure_driver.py',
                               'closure_analyze.py', 'closure_audit.py', 'm3_confirm_spec.py', 'm3_confirm_analyze.py',
                               'm3_confirm_audit.py', 'm3-confirmation-power.json')]
    paths += [HERE.parent / 'support.py', HERE.parent / 'audit.py', ROOT / 'lab/tools/study_lock.py',
              ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
    from _threemind_native import _threemind_native as native
    production = read(work.parent / 'criteria61-v1/frozen.json')
    pilot_units = work.parent / 'criteria61-v1/units'
    expected_source_bytes = sum(p.stat().st_size for p in pilot_units.rglob('*') if p.is_file()) / 8
    frozen = {'kernel': g.KERNEL, 'native_sha256': s.sha(native.__file__),
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'production_sources': production['production_sources'],
              'cases_sha256': s.sha(work / 'cases.json'), 'instrument_seed': INSTRUMENT_SEED,
              'expected_source_bytes': expected_source_bytes, 'source_cost_multiplier_stop': 1.5}
    s.base.original(work / 'frozen.json', frozen)
    s.base.original(work / 'measurement-port-check.json', check())
    for p in paths:
        dest = work / 'frozen-source' / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, PROJECT, client=client)
        rec.register({'source_key': 'r51i:criteria-confirmation:6.1:20261113:v1', 'title': 'R51i：6.1四项自主活动判据64来源独立确认',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai', 'kernels': [g.KERNEL],
                      'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'independent_origins': N, 'system_implementations': 5, 'criteria': 'cross-system-criteria/2',
                                   'additional_validity_check': 'teaching-only Core matching', 'pilot_origins_excluded': True}},
                     request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R51i protocol ' + lang,
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
        result = {'passed': all(v['passed'] for v in systems.values()), 'systems': systems, 'scientific_origins': 0, 'seed': INSTRUMENT_SEED}
        s.base.original(work / 'apparatus.json', result)
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
            for kind in case['systems']:
                if (work / 'STOP').exists(): break
                assert guard.thread.is_alive(), 'Resource guard absent'
                s.base.resource_check(work)
                name = f"o{case['rig_origin']}-{kind}"
                folder = work / 'units' / name
                path = folder / 'result.json'
                if path.exists():
                    result = read(path)
                    assert result['origin'] == case['rig_origin'] and result['kind'] == kind
                    assert all(p.exists() for p in (folder / 'h0-parent.json.gz', folder / 'h1-parent.json.gz'))
                else:
                    assert g.case_seed('X3', case['rig_origin']) == case['seed']
                    s.base.original(work / 'in-flight.json', {'unit': name, 'pid': os.getpid(), 'created': psutil.Process().create_time()})
                    result = measure.x3(folder, case['rig_origin'], kind)
                    result['valid'] = all(r['selection'] is None or r['selection']['passed'] for r in result['histories'])
                    s.base.original(path, result)
                    (work / 'in-flight.json').unlink()
                completed.append(name)
                s.base.atomic_json(work / 'current.json', {'completed': len(completed), 'total': N * 5, 'last': name})
                print(name, flush=True)
                reason = ('invalid matching' if not result['valid'] else
                          'originals budget' if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > RAW_CAP else
                          'two-hour budget' if time.monotonic() - start > 7200 else None)
                if reason:
                    s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': name})
                    break
            if (work / 'STOP').exists(): break
            original_bytes = sum(p.stat().st_size for kind in case['systems']
                                 for p in (work / 'units' / f"o{case['rig_origin']}-{kind}").rglob('*') if p.is_file())
            budget = read(work / 'frozen.json')
            cost = {'origin': case['origin'], 'bytes': original_bytes,
                    'pilot_expected_bytes': budget['expected_source_bytes'],
                    'ratio': original_bytes / budget['expected_source_bytes']}
            cost_path = work / 'costs' / f"o{case['origin']}.json"
            if cost_path.exists(): assert read(cost_path) == cost
            else: s.base.original(cost_path, cost)
            if cost['ratio'] > budget['source_cost_multiplier_stop']:
                s.base.original(work / 'STOP', {'reason': 'source cost exceeds frozen estimate by 50%',
                                              'complete_boundary': case['origin'], 'cost': cost})
                break
        if len(completed) == N * 5:
            s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'origins': N, 'systems': N * 5,
                                                  'wall_seconds': time.monotonic() - start})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['register', 'apparatus', 'run'])
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    {'register': register, 'apparatus': apparatus, 'run': run}[args.action](args.work.resolve())
