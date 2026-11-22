"""R63f: declared bodily-transfer copies of the completed R63c parents."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE.parent), str(ROOT / 'src')]
import support as s
spec = importlib.util.spec_from_file_location('r63f_body_memory', HERE.parent / 'body_memory/study.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
PROJECT = f.PROJECT
NS = UUID('3f368dcb-a79b-50b5-8834-7121d2619bbc')
RAW_CAP = 256 * 2**20


def physical_inputs(c, material_path, intensity):
    units = f.read(material_path)['units']
    transformed = f.material.transform(units, 'full' if c['mode'] == 'untrained' else c['mode'], c['seed'])
    for i, u in enumerate(transformed):
        u['time_us'] = str(c['begin_us'] + int(u['time_us']))
        u['intensity'] = intensity
        assert not any(int(e['channel']) in (c['mappings']['A'], c['mappings']['B']) for e in u['elements'])
        c['inputs'].append({'kind': 'probe' if i == len(transformed) - 1 else 'physical',
                            'unit': u, 'stimulus': f.material.frame(u).to_dict()})


def cases(work, parents, intensity):
    rows = []
    for parent in parents:
        seed, preset, mode = parent['seed'], parent['preset'], parent['mode']
        for domain in ('none', 'original', 'angle', 'gravity'):
            for sign in ((0,) if domain == 'none' else (1, -1)):
                key = f"transfer-{seed}-{preset}-{mode}-{domain}-{sign}"
                c = f.case(key, seed, preset, mode, 'probe', parent=parent['key'],
                           begin=parent['clock_us'], end=parent['clock_us'] + 5600000)
                c.update(domain=domain, sign=sign, expected=None if sign == 0 else int(sign < 0),
                         targets=[c['mappings']['A'], c['mappings']['B']], parent_sha256=parent['final_sha256'])
                if sign:
                    physical_inputs(c, work / 'materials' / f'pendulum-{seed}-{sign}-{domain}.json', intensity)
                f.maintenance(c)
                rows.append(c)
    assert len(rows) == 280 and len({c['key'] for c in rows}) == 280
    return rows


def frozen_check(work):
    frozen = f.read(work / 'frozen.json')
    for rel, digest in frozen['sources'].items() | frozen['production_sources'].items():
        assert s.sha(ROOT / rel) == digest, rel
    from _threemind_native import _threemind_native as native
    assert s.sha(native.__file__) == frozen['native_sha256']
    assert s.sha(work / 'cases.json') == frozen['cases_sha256']
    for rel, value in frozen['copied_evidence'].items(): assert s.sha(work / rel) == value['sha256']
    assert f.read(work / 'registration.json')['pending'] == 0


def register(work):
    assert not work.exists()
    source = work.parent / 'body-memory-63-rerun-v1'
    finished = f.read(source / 'publication/completion.json')
    assert finished['coverage'] == 'verified' and finished['pending'] == 0 and not finished['scientific_stop']
    latest = f.read(work.parent / 'criteria-confirmation-63-rerun-v1/publication/completion.json')
    assert latest['pending'] == 0 and not latest['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > (25 + .875) * 2**30
    work.mkdir()
    copied = {}
    def copy(src, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        assert s.sha(src) == s.sha(dest)
        copied[dest.relative_to(work).as_posix()] = {'source': str(src), 'sha256': s.sha(src), 'bytes': src.stat().st_size}
    old_material = ROOT / '.work/memory-transfer-20260930/materials'
    for seed in (930101, 930102, 930103, 930104):
        for domain in ('original', 'angle', 'gravity'):
            for sign in (1, -1):
                name = f'pendulum-{seed}-{sign}-{domain}.json'
                copy(old_material / name, work / 'materials' / name)
    copy(old_material / 'pendulum-930199-1-original.json', work / 'materials/pendulum-930199-1-original.json')
    parents = []
    for c in f.read(source / 'cases.json'):
        if c['stage'] != 'retention' or c['delay'] != 1: continue
        folder = source / 'cases' / c['key']
        result = f.read(folder / 'result.json')
        assert result['status'] == 'complete' and result['life'] == 'active'
        for p in folder.iterdir():
            if p.is_file(): copy(p, work / 'cases' / c['key'] / p.name)
        assert f.image(work / 'cases' / c['key'] / 'final.tmind').digest == result['final_sha256']
        parents.append(result)
    assert len(parents) == 40
    intensity = f.read(source / 'calibration.json')['selected']['intensity']
    table = cases(work, parents, intensity)
    s.base.original(work / 'cases.json', table)
    s.base.original(work / 'parents.json', parents)
    paths = [HERE / n for n in ('study.py', 'analyze.py', 'check_measurement.py', 'protocol.zh.md', 'protocol.en.md')]
    paths += [HERE.parent / 'body_memory/study.py', HERE.parent / 'support.py', HERE.parent / 'allocation.py',
              f.OLD / 'materials.py', f.OLD / 'common.py', ROOT / 'lab/tools/study_lock.py',
              ROOT / 'lab/explorations/2026-10-16-mechanism-discovery/pilot_m2.py',
              ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
    from _threemind_native import _threemind_native as native
    frozen = {'kernel': f.KERNEL, 'native_sha256': s.sha(native.__file__),
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'production_sources': f.read(source / 'frozen.json')['production_sources'],
              'copied_evidence': copied, 'cases_sha256': s.sha(work / 'cases.json'), 'intensity': intensity}
    s.base.original(work / 'frozen.json', frozen)
    for p in paths:
        dest = work / 'frozen-source' / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, PROJECT, client=client)
        rec.register({'source_key': 'r63f:body-transfer:6.3:20261115:v1', 'title': 'R63f：6.3身体关联在角度及重力变化中的迁移',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai', 'kernels': [f.KERNEL],
                      'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'independent_blocks': 4, 'parents': 40, 'research_copies': 280, 'new_teaching': False}},
                     request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R63f protocol ' + lang,
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
        c = f.case('apparatus-observation', 930199, 'ordinary', 'full', 'probe', end=5600000)
        c['targets'] = [c['mappings']['A'], c['mappings']['B']]
        physical_inputs(c, work / 'materials/pendulum-930199-1-original.json', f.read(work / 'frozen.json')['intensity'])
        f.maintenance(c)
        measured = f.trial(work / 'apparatus', c)
        plain = f.engine(c['config'])
        for row in c['inputs']: plain.inject(f.Stimulus.from_dict(row['stimulus']))
        plain.advance_to(c['end_us'])
        assert plain.capture_state().digest == measured['final_sha256']
        source = work / 'apparatus/cases/apparatus-observation'
        restored = f.engine(state=f.image(source / 'final.tmind'))
        observer = f.ReadoutSession(restored, record=lambda _: None, state=f.read(source / 'observer.json'))
        plain.advance_to(c['end_us'] + 100000); observer.advance_to(c['end_us'] + 100000)
        assert plain.capture_state().digest == restored.capture_state().digest
        result = {'passed': True, 'observation_preserves_core': True, 'whole_restore_preserves_continuation': True,
                  'scientific_blocks': 0, 'seed': 930199}
        s.base.original(work / 'apparatus.json', result)
        (work / 'in-flight.json').unlink()
    s.base.original(work / 'apparatus-resources.json', f.read(work / 'resource-summary.json'))
    print(json.dumps(result), flush=True)


def run(work):
    import psutil
    frozen_check(work)
    assert f.read(work / 'apparatus.json')['passed']
    assert not any((work / n).exists() for n in ('summary.json', 'in-flight.json', 'STOP'))
    started = time.monotonic(); completed = []
    with s.base.worker_lock(work), s.base.Guard(work) as guard:
        s.base.atomic_json(work / 'host.json', {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv})
        for c in f.read(work / 'cases.json'):
            if (work / 'STOP').exists(): break
            assert guard.thread.is_alive()
            s.base.resource_check(work)
            path = work / 'cases' / c['key'] / 'result.json'
            if path.exists():
                result = f.read(path)
                assert result['initial_sha256'] == c['parent_sha256'] and result['status'] == 'complete'
            else:
                s.base.original(work / 'in-flight.json', {'case': c['key'], 'pid': os.getpid(), 'created': psutil.Process().create_time()})
                result = f.trial(work, c)
                assert result['initial_sha256'] == c['parent_sha256']
                (work / 'in-flight.json').unlink()
            completed.append(c['key'])
            s.base.atomic_json(work / 'current.json', {'completed': len(completed), 'total': 280, 'last': c['key']})
            print(c['key'], flush=True)
            reason = (result['pause_reason'] if result['status'] != 'complete' else
                      'originals budget' if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > RAW_CAP else
                      'two-hour budget' if time.monotonic() - started > 7200 else None)
            if reason:
                s.base.original(work / 'STOP', {'reason': reason, 'complete_boundary': c['key']}); break
        if len(completed) == 280:
            s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'conditions': 280, 'independent_blocks': 4,
                                                   'wall_seconds': time.monotonic() - started})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['register', 'apparatus', 'run'])
    p.add_argument('--work', type=Path, required=True); args = p.parse_args()
    {'register': register, 'apparatus': apparatus, 'run': run}[args.action](args.work.resolve())
