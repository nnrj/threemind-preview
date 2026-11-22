"""R51t12: six registered separation conditions, unchanged prefix materials."""
import argparse
from copy import deepcopy
import gc
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
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location('r51t12_material_helpers', HERE.parent / 'prefix_solution/study.py')
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
s, h, recorder, pre = t.s, t.h, t.recorder, t.pre
from threemind_kernels.local62 import KERNEL_ID, Local62Config
from threemind_kernels.registry import resolve_kernel

NS = UUID('17129b4a-5ae9-4a01-bfc1-0cba501d7287')
OLD = t.DATA / 'prefix-solution62-v1'
GROUPS = {'shared': (False, False, False), 'resources': (False, True, False),
          'weights': (True, False, False), 'weights-resources': (True, True, False),
          'learning': (True, False, True), 'all': (True, True, True)}


def engine(config=None, state=None, backend='native'):
    return resolve_kernel(KERNEL_ID).create(None if state is not None else Local62Config(**config), state, backend=backend)


def patch(profile, name):
    w, r, l = GROUPS[name]
    return {'separate_inhibition_weights': w, 'separate_inhibition_resources': r,
            'separate_inhibition_learning': l, 'inhibitory_learning_enabled': True,
            'activation_weight_reinforcement_enabled': True, 'inhibition_weight_reinforcement_enabled': True,
            'consolidation_mode': 'adaptive-half-life' if profile == 'P' else 'stability',
            'novelty_mode': 'arrival-window' if profile == 'P' else 'immediate',
            'activation_signal_threshold': .0004 if profile == 'P' else .004,
            'inhibition_signal_threshold': .0004, 'resource_precheck_enabled': True,
            'subthreshold_expiry_enabled': True}


def stages(cases, phase, profile, name, fresh=False):
    rows = []
    for block in (0, 1):
        parent = f'{phase}/{profile}/{name}/{block}/train'
        for cue in ('train', 'AB', 'DB'):
            key = f'short/train-{block}' if cue == 'train' else f'history/s{block}/101/d1/{cue}'
            case = deepcopy(cases['prefix-resources62-v1/' + key])
            rows.append({'key': f'{phase}/{profile}/{name}/{block}/{cue}', 'group': 'prefix',
                         'profile': profile, 'variant': name, 'block': block, 'cue': cue,
                         'case': case, 'patch': patch(profile, name),
                         'mask': (0x02000000 if block == 0 else 0x01000000) if fresh else 0,
                         'seed': 9291251 + block if fresh else 9291000,
                         'parent': None if cue == 'train' else parent})
    return rows


def prepare(work):
    assert not work.exists()
    assert s.read(OLD / 'publication/completion.json')['pending'] == 0
    assert s.base.resource_check(OLD)['safe'] and shutil.disk_usage(OLD).free > 27 * 2**30
    work.mkdir()
    shutil.copytree(OLD / 'materials', work / 'materials')
    shutil.copyfile(OLD / 'materials.json', work / 'materials.json')
    shutil.copyfile(OLD / 'publication/completion.json', work / 'prior-delivery.json')
    refs = {p.relative_to(work).as_posix(): s.sha(p) for p in (work / 'materials').rglob('*') if p.is_file()}
    s.write(work / 'reference-manifest.json', refs)
    cases = s.read(work / 'materials.json')
    plan = [q for profile in ('P', 'S') for name in GROUPS for q in stages(cases, 'A', profile, name)]
    assert len(plan) == 72
    s.write(work / 'phase-A.json', plan)
    s.write(work / 'initial-resources.json', s.base.resource_check(work))
    print(json.dumps({'prepared': str(work), 'stages': len(plan)}), flush=True)


def apparatus(work):
    assert not (work / 'apparatus.json').exists()
    plan = s.read(work / 'phase-A.json'); checks = []
    recorder.s.engine = engine
    recorder.s.TARGETS = {x ^ 0x10000000 for x in s.measure.TOKENS.values()}
    with s.base.worker_lock(work), pre.Guard(work):
        for profile in ('P', 'S'):
            for name in GROUPS:
                case = deepcopy(plan[0]['case']); case['end_us'] = 6000000
                inputs = t.inputs(work, case, 0x10000000, case['end_us'])
                hashes = {}
                for mode in ('plain', 'observed', 'restored', 'partitioned', 'paused'):
                    e = engine({'seed': 9291249} | case['initial_config'] | patch(profile, name))
                    e, _, _ = recorder.drive(e, case, deepcopy(inputs), mode=mode)
                    hashes[mode] = e.capture_state().digest
                assert len(set(hashes.values())) == 1, (profile, name)
                checks.append({'profile': profile, 'variant': name, 'same_complete_state': True, 'hashes': hashes})
    s.write(work / 'apparatus.json', {'passed': True, 'checks': checks})
    shutil.copyfile(work / 'resource-summary.json', work / 'apparatus-resources.json')
    print(json.dumps({'apparatus_passed': True, 'conditions': len(checks)}), flush=True)


def register(work):
    assert s.read(work / 'apparatus.json')['passed'] and not (work / 'frozen.json').exists()
    import _threemind_native
    paths = list((ROOT / 'src').rglob('*.py')) + list((ROOT / 'crates').rglob('*.rs'))
    paths += list((ROOT / 'crates/threemind-core/src').glob('*defaults.json'))
    paths += list(HERE.glob('*.py')) + list(HERE.glob('protocol.*.md'))
    paths += [Path(m.__file__) for m in tuple(sys.modules.values()) if getattr(m, '__file__', None)
              and str(m.__file__).endswith('.py') and Path(m.__file__).is_relative_to(ROOT / 'lab')]
    sources = {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths}
    for rel in sources:
        out = work / 'frozen-source' / rel; out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, out)
    with pre.client_context() as client:
        rec = s.base.ResearchRecorder(work, s.PROJECT, client=client)
        rec.register({'source_key': 'r51t12:separated-signals62:20261115:v1',
            'title': 'R51t12：激活与抑制的权重、资源和学习记录分离', 'classification': 'formal',
            'execution_status': 'running', 'executor': 'ai', 'kernels': [KERNEL_ID],
            'protocol': (HERE / 'protocol.zh.md').read_text('utf8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
            'required_roles': ['protocol', 'report', 'note', 'original'],
            'metadata': {'material_blocks': 2, 'stage_cap': 84, 'phase_a_stages': 72,
                         'inhibitory_learning': True, 'defaults_unchanged': True}}, request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-doc-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R51t12 protocol ' + lang,
                      'markdown': (HERE / f'protocol.{lang}.md').read_text('utf8')})
        rec.append('stage', 'r51t12:phase-a', {'stages': s.read(work / 'phase-A.json')}, request_id=uuid5(NS, 'phase-a'))
        rec.synchronize(strict=True); assert rec.status['pending'] == 0
        s.write(work / 'registration.json', {'project': s.PROJECT, 'record': rec.experiment, 'pending': 0})
    s.write(work / 'frozen.json', {'sources': sources, 'native_sha256': s.sha(Path(_threemind_native._threemind_native.__file__)),
                                  'plan_sha256': s.sha(work / 'phase-A.json'),
                                  'references_sha256': s.sha(work / 'reference-manifest.json')})
    print(json.dumps(s.read(work / 'registration.json')), flush=True)


def check(work):
    import _threemind_native
    f = s.read(work / 'frozen.json')
    assert s.sha(Path(_threemind_native._threemind_native.__file__)) == f['native_sha256']
    for rel, sha in f['sources'].items():
        assert s.sha(ROOT / rel) == sha, rel
    assert s.sha(work / 'phase-A.json') == f['plan_sha256']
    assert s.sha(work / 'reference-manifest.json') == f['references_sha256']
    for rel, sha in s.read(work / 'reference-manifest.json').items():
        assert s.sha(work / rel) == sha, rel


def run(work, phase):
    import psutil
    check(work)
    plan = s.read(work / f'phase-{phase}.json')
    if phase != 'A':
        assert s.sha(work / f'phase-{phase}.json') == s.read(work / f'phase-{phase}-frozen.json')['sha256']
    assert not any((work / n).exists() for n in ('STOP', 'in-flight.json', f'phase-{phase}-summary.json'))
    started = time.monotonic(); results = []; recorder.ACTIVE_WORK = work; recorder.s.engine = engine
    with s.base.worker_lock(work), pre.Guard(work) as guard:
        host = {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv}
        s.write(work / f'host-{phase}.json', host); s.base.atomic_json(work / 'host.json', host)
        for stage in plan:
            out = work / 'cases' / stage['key']
            if (out / 'result.json').exists():
                q = s.read(out / 'result.json'); assert h.get(out / 'final.rstate.gz').digest == q['final_sha256']
                results.append(q); continue
            if (work / 'STOP').exists(): return
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > 512 * 2**20:
                s.write(work / 'STOP', {'reason': 'registered originals cap'}); return
            out.mkdir(parents=True, exist_ok=False); s.write(work / 'in-flight.json', host | {'key': stage['key']})
            parent = h.get(work / 'cases' / stage['parent'] / 'final.rstate.gz') if stage['parent'] else None
            e = engine(state=parent) if parent else engine({'seed': stage['seed']} | stage['case']['initial_config'] | stage['patch'])
            initial = e.capture_state(); h.put(out / 'initial.rstate.gz', initial)
            # Historical resource fields already match the declared complete configuration.
            assert all(getattr(e.config, k) == v for k, v in stage['case'].get('patch', {}).items())
            assert e.config.inhibitory_learning_enabled and e.config.inhibition_weight_reinforcement_enabled
            inputs = t.inputs(work, stage['case'], stage['mask']); s.packed(out / 'inputs.json.gz', inputs)
            recorder.s.TARGETS = {v ^ stage['mask'] for v in s.measure.TOKENS.values()}
            wall, cpu = time.perf_counter(), time.process_time()
            e, points, injected = recorder.drive(e, stage['case'], inputs, out)
            elapsed, cpu_elapsed = time.perf_counter() - wall, time.process_time() - cpu
            final = e.capture_state(); h.put(out / 'final.rstate.gz', final)
            assert h.get(out / 'final.rstate.gz').digest == final.digest
            if points: s.packed(out / 'process.json.gz', points)
            result = {k: stage[k] for k in ('key', 'group', 'profile', 'variant', 'block', 'cue')}
            result.update(parent_sha256=parent.digest if parent else None, initial_sha256=initial.digest,
                final_sha256=final.digest, time_us=e.time_us, life=e.life, injected=injected, scheduled=len(inputs),
                wall_seconds=elapsed, cpu_seconds=cpu_elapsed, snapshot_bytes=len(final.payload),
                process=t.measure(stage['case'], points, stage['mask']) if points else None)
            s.write(out / 'result.json', result); results.append(result); (work / 'in-flight.json').unlink()
            s.base.atomic_json(work / 'current.json', {'phase': phase, 'complete': len(results), 'total': len(plan), 'last': stage['key']})
            print(json.dumps({'complete': len(results), 'total': len(plan), 'key': stage['key'],
                              'seconds': round(elapsed, 2), 'process': result['process']}), flush=True)
            del e, points, inputs; gc.collect()
        s.write(work / f'phase-{phase}-summary.json', {'stages': len(results), 'wall_seconds': time.monotonic() - started})
    shutil.copyfile(work / 'resource-summary.json', work / f'phase-{phase}-resources.json')


def select(work):
    check(work); assert s.read(work / 'phase-A-summary.json')['stages'] == 72
    candidates = []
    for profile in ('P', 'S'):
        for name in GROUPS:
            rows = [s.read(work / 'cases' / f'A/{profile}/{name}/{b}/{cue}/result.json') for b in (0, 1) for cue in ('AB', 'DB')]
            if all(q['process'] and q['process']['complete'] and q['process']['margin'] > 1e-6 for q in rows):
                candidates.append((sum(GROUPS[name]), list(GROUPS).index(name), profile, name))
    chosen = min(candidates) if candidates else None
    s.write(work / 'selection.json', {'candidates': candidates, 'chosen': chosen})
    if not chosen: return
    _, _, profile, name = chosen
    cases = s.read(work / 'materials.json')
    plan = [q for group in dict.fromkeys((name, 'shared')) for q in stages(cases, 'B', profile, group, True)]
    s.write(work / 'phase-B.json', plan)
    with pre.client_context() as client:
        rec = s.base.ResearchRecorder(work, s.PROJECT, client=client); rec.resume_recording()
        rec.append('stage', 'r51t12:fresh-encoding', {'selection': chosen, 'stages': plan}, request_id=uuid5(NS, 'phase-b'))
        rec.synchronize(strict=True); assert rec.status['pending'] == 0
    s.write(work / 'phase-B-frozen.json', {'sha256': s.sha(work / 'phase-B.json')})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=('prepare', 'apparatus', 'register', 'check', 'run', 'select'))
    p.add_argument('--work', type=Path, required=True); p.add_argument('--phase', default='A'); a = p.parse_args()
    run(a.work, a.phase) if a.action == 'run' else globals()[a.action](a.work)
