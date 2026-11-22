"""R63h: eight complete individuals with temporal and endpoint readouts."""
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
import readout_rig as g
sys.path.insert(0, str(HERE))
import measurement as measure
assert Path(measure.__file__).resolve() == HERE / 'measurement.py'

PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS = UUID('54f6318c-74c0-5073-b30a-114c70428c31')
INSTRUMENT_SEED = 1056002
RAW_CAP = 4 * 2**30


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
    for batch in ('criteria-confirmation-63-rerun-v1', 'body-transfer-63-rerun-v1', 'transfer-63-rerun-v1'):
        done = read(work.parent / batch / 'publication/completion.json')
        assert done['coverage'] == 'verified' and done['pending'] == 0 and not done['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > 37.125 * 2**30
    work.mkdir()
    s.base.original(work / 'cases.json', [{'origin': i, 'seed': 1056100 + i} for i in range(8)])
    old = ROOT / 'lab/explorations/2026-10-16-mechanism-discovery'
    paths = [HERE / name for name in ('study.py', 'hosts.py', 'readout_rig.py', 'measurement.py', 'analyze.py', 'scoring.py', 'audit_readout.py',
                                     'check_features.py', 'protocol.zh.md', 'protocol.en.md', 'implementation-note.zh.md', 'implementation-note.en.md')]
    paths += [HERE.parent / 'support.py', HERE.parent / 'allocation.py',
              ROOT / 'lab/tools/study_lock.py',
              ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
    paths += [old / name for name in ('pilot_m1.py', 'pilot_m2.py', 'pilot_m3.py', 'closure_rig.py',
                                    'closure_driver.py', 'closure_analyze.py', 'm5_rig.py', 'm5_driver.py', 'm5_analyze.py')]
    from _threemind_native import _threemind_native as native
    frozen = {'kernel': g.KERNEL, 'native_sha256': s.sha(native.__file__),
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'production_sources': read(work.parent / 'criteria-63-rerun-v1/frozen.json')['production_sources'],
              'cases_sha256': s.sha(work / 'cases.json'), 'instrument_seed': INSTRUMENT_SEED}
    s.base.original(work / 'frozen.json', frozen)
    from check_features import check
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
        rec.register({'source_key': 'r63h:fixed-temporal-readout:6.3:20261115:v1', 'title': 'R63h：6.3固定过程读出器表达新关系',
                      'classification': 'development', 'execution_status': 'running', 'executor': 'ai', 'kernels': [g.KERNEL],
                      'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'independent_origins': 8, 'temporal_dimension': 240, 'endpoint_dimension': 12,
                                   'old_task_correction_maximum': 2, 'paired_readout_conditions': True}},
                     request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R63h protocol ' + lang,
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
        parent = g.Subject(INSTRUMENT_SEED); parent.tick(0, [{'K': .2}])
        calibration = g.calibrate(parent)
        measure.save(work / 'apparatus', 'parent', parent)
        s.base.original(work / 'apparatus/calibration.json', calibration)
        hashes = {}
        for mode in ('plain', 'observed', 'restored', 'paused'):
            child = g.Subject.restore(parent.save())
            g.question(child, 'U', observed=mode == 'observed')
            if mode == 'restored': child = g.Subject.restore(child.save())
            if mode == 'paused':
                state = child.save(); time.sleep(.03)
                assert child.save() == state
            g.question(child, 'Z', observed=mode == 'observed')
            hashes[mode] = g.m.digest(child.save())
            measure.save(work / 'apparatus', mode, child)
        child = g.Subject.restore(parent.save())
        g.exam(child, 0); g.plasticity(child, True)
        teaching = g.teach(child, 0)
        measure.save(work / 'apparatus', 'taught', child)
        masks = {}
        for arm in ('sham', 'target', 'matched', 'restored'):
            branch = child.fork(arm); masks[arm] = g.mask(branch, arm)
            measure.save(work / 'apparatus', 'mask-' + arm, branch)
        result = {'scientific_origins': 0, 'seed': INSTRUMENT_SEED, 'hashes': hashes, 'masks': masks,
                  'old_new_activity_residual': teaching['old_new_activity_residual'],
                  'development_correction_rounds': len(calibration['corrections']),
                  'answers_not_used_to_select_features_or_thresholds': True,
                  'passed': len(set(hashes.values())) == 1 and all(v['matching_valid'] for v in masks.values())
                            and teaching['old_new_activity_residual'] <= .02}
        s.base.original(work / 'apparatus.json', result)
        assert result['passed'], 'Invalid apparatus; retain all originals and marker'
        (work / 'in-flight.json').unlink()
    s.base.original(work / 'apparatus-resources.json', read(work / 'resource-summary.json'))
    print(json.dumps(result), flush=True)


def run(work):
    from hosts import run as serial_hosts
    serial_hosts(work)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['register', 'apparatus', 'run'])
    p.add_argument('--work', type=Path, required=True); a = p.parse_args()
    {'register': register, 'apparatus': apparatus, 'run': run}[a.action](a.work.resolve())
