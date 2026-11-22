"""R51t9: resource-first transmission, thresholds and prefix discrimination.

Only declared research individuals are run. No production source is modified.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
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
sys.path.insert(0, str(HERE.parent / 'prefix_precheck'))
_spec = importlib.util.spec_from_file_location('r51t8_driver', HERE.parent / 'prefix_precheck/run.py')
previous = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(previous)
s, c, r = previous.s, previous.c, previous.r
from threemind_core import Stimulus, StateImage
from threemind_kernels.registry import resolve_kernel

NS = UUID('b2375ed6-9b23-4ce5-8e83-2db99b088b61')
OLD = previous.OLD
PRE = OLD.parent / 'prefix-precheck62-v1'
CONTROLS = {
    'stable-g4-r8': (OLD, 'cases/stability-immediate'),
    'default-g4-r8': (OLD, 'cases/compatible62'),
    'old-g4-r8': (OLD, 'transport/cases/old-inhibition'),
    'pre-old-high': (PRE, 'cases/pre-old-high'),
}
THRESHOLDS = {'g4': .0004, 'g04': .00004, 'g0': 0.0}
RESOURCES = {'r8': {}, 'r08': {'stp_recovery_tau_s': .08}, 'full': {'depletion_enabled': False}}
VARIANTS = {}
for mode in ('stable', 'default'):
    for gate, threshold in THRESHOLDS.items():
        for resource, patch in RESOURCES.items():
            key = f'{mode}-{gate}-{resource}'
            if key in CONTROLS:
                continue
            VARIANTS[key] = {'mode': mode, 'patch': {'signal_threshold': threshold} | patch}
# Source thresholds are a separate axis; activation_floor is unchanged.
for mode, gates in (('stable', ('g4', 'g0')), ('default', ('g0',))):
    for gate in gates:
        for resource in ('r8', 'r08'):
            key = f'{mode}-{gate}-{resource}-sources0'
            VARIANTS[key] = {'mode': mode, 'patch': {
                'signal_threshold': THRESHOLDS[gate], 'activation_send_threshold': 0.0,
                'inhibition_send_threshold': 0.0} | RESOURCES[resource]}
for name, field in (('exc0', 'activation_send_threshold'), ('inh0', 'inhibition_send_threshold')):
    VARIANTS[f'stable-g0-r8-{name}'] = {'mode': 'stable', 'patch': {'signal_threshold': 0.0, field: 0.0}}
assert len(VARIANTS) == 24
# Only if every modern route fails: determine whether the inhibition route still matters.
FALLBACK = {
    'old-g0-r8': {'mode': 'old', 'patch': {'signal_threshold': 0.0}},
    'old-g4-r08': {'mode': 'old', 'patch': {'stp_recovery_tau_s': .08}},
    'old-g0-r08': {'mode': 'old', 'patch': {'signal_threshold': 0.0, 'stp_recovery_tau_s': .08}},
}


def condition(name):
    if name in VARIANTS:
        return VARIANTS[name]
    if name in FALLBACK:
        return FALLBACK[name]
    return {'mode': name.split('-')[0], 'patch': {}}


def create(name, case=None, state=None, backend='native', calibration=False):
    item = condition(name)
    if state is not None:
        if item['mode'] == 'old':
            return r.ResearchEngine(state=state)
        return resolve_kernel('threemind.continuous-memory/6.2').create(state=state, backend=backend)
    config = {'seed': 9291199 if calibration else 9291000} | case['initial_config']
    if item['mode'] in ('stable', 'old'):
        config |= s.STABLE
    config |= item['patch']
    if item['mode'] == 'old':
        return r.ResearchEngine(r.ResearchConfig(**config, research_transport='old-inhibition', resource_precheck=False))
    return resolve_kernel('threemind.continuous-memory/6.2').create(config, backend=backend)


def state_at(folder, name):
    if (folder / (name + '.tmind')).exists():
        return s.ArtifactCodec.decode((folder / (name + '.tmind')).read_bytes())
    return previous.get(folder / (name + '.rstate.gz'))


def folder(work, name, block, cue):
    return work / ('controls' if name in CONTROLS else 'cases') / name / str(block) / cue


def prepare(work):
    assert not work.exists(), 'new batch only'
    assert s.base.resource_check(work.parent)['safe']
    assert shutil.disk_usage(work.parent).free > 29 * 2**30
    for root in (OLD, PRE):
        receipt = s.read(root / 'publication/completion.json')
        assert receipt['coverage'] == 'verified' and receipt['pending'] == 0
        assert not (root / 'in-flight.json').exists()
    work.mkdir()
    shutil.copyfile(OLD / 'cases.json', work / 'cases.json')
    shutil.copytree(OLD / 'materials', work / 'materials')
    for name, (root, rel) in CONTROLS.items():
        shutil.copytree(root / rel, work / 'controls' / name)
    manifest = {p.relative_to(work).as_posix(): s.sha(p) for name in ('materials', 'controls')
                for p in (work / name).rglob('*') if p.is_file()}
    s.write(work / 'reference-manifest.json', manifest)
    s.write(work / 'initial-resources.json', s.base.resource_check(work))
    print(json.dumps({'prepared': str(work), 'references': len(manifest)}), flush=True)


def apparatus(work):
    assert not (work / 'apparatus.json').exists()
    case = deepcopy(s.read(work / 'cases.json')['short/train-0'])
    case['end_us'] = 5_000_000
    rows = [q for q in s.inputs(work, case, True) if int(q['source_policy']['resolved_at_us']) <= case['end_us']]
    def drive(name, mode, backend='native'):
        e = create(name, case, backend=backend, calibration=True)
        index = 0; altered = False
        while True:
            while index < len(rows) and int(rows[index]['source_policy']['resolved_at_us']) == e.time_us:
                e.inject(Stimulus.from_dict(rows[index]['stimulus'])); index += 1
            e.advance_to(e.time_us)
            if mode != 'plain':
                before = e.capture_state().digest; e.observation_nodes(); e.capture_state()
                assert before == e.capture_state().digest
            if not altered and e.time_us >= 2_000_000:
                if mode == 'restored':
                    before = e.capture_state(); e = create(name, state=StateImage.from_dict(before.to_dict()), backend=backend)
                    assert e.capture_state().digest == before.digest
                if mode == 'paused':
                    before = e.capture_state().digest; time.sleep(.01)
                    assert e.capture_state().digest == before
                altered = True
            if e.time_us == case['end_us']:
                break
            times = [case['end_us'], e.time_us + (37000 if mode == 'partitioned' else 100000)]
            if index < len(rows):
                times.append(int(rows[index]['source_policy']['resolved_at_us']))
            e.advance_to(min(times))
        return e.capture_state()
    checks = []
    with s.base.worker_lock(work), previous.Guard(work):
        for name in list(VARIANTS) + list(FALLBACK):
            hashes = {mode: drive(name, mode).digest for mode in ('plain', 'observed', 'restored', 'partitioned', 'paused')}
            assert len(set(hashes.values())) == 1, (name, hashes)
            # Python/Rust versions of the configuration agree to numerical precision.
            native = drive(name, 'plain').to_dict()
            python = drive(name, 'plain', 'reference').to_dict()
            differences = []
            def compare(a, b, path=''):
                if isinstance(a, dict):
                    assert a.keys() == b.keys(), path
                    for k in a: compare(a[k], b[k], path + '/' + k)
                elif isinstance(a, list):
                    assert len(a) == len(b), path
                    for i, (x, y) in enumerate(zip(a, b)): compare(x, y, path + '/' + str(i))
                elif isinstance(a, (int, float)) and not isinstance(a, bool):
                    if a != b: differences.append(abs(a-b))
                else: assert a == b, (path, a, b)
            compare(native, python)
            error = max(differences, default=0)
            assert error < 1e-10, (name, error)
            checks.append({'variant': name, 'hashes': hashes, 'python_native_max_error': error})
            assert not (work / 'STOP').exists()
    s.write(work / 'apparatus.json', {'passed': True, 'separate_encoding': True, 'checks': checks})
    print(json.dumps({'apparatus': True, 'configurations': len(checks)}), flush=True)


def register(work):
    assert s.read(work / 'apparatus.json')['passed']
    assert not (work / 'frozen.json').exists()
    files = list(HERE.glob('*.py')) + list(HERE.glob('protocol.*.md'))
    files += list((ROOT / 'src/threemind_kernels').glob('*.py'))
    for module in tuple(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and Path(path).suffix == '.py' and Path(path).resolve().is_relative_to(ROOT):
            if '.work' not in Path(path).resolve().relative_to(ROOT).parts:
                files.append(Path(path).resolve())
    sources = {p.resolve().relative_to(ROOT).as_posix(): s.sha(p) for p in files}
    for rel in sources:
        target = work / 'frozen-source' / rel; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    import _threemind_native
    dll = next(Path(_threemind_native.__file__).parent.glob('*.pyd'))
    with previous.client_context() as client:
        rec = s.base.ResearchRecorder(work, s.PROJECT, client=client)
        rec.register({'source_key': 'r51t9:prefix-resources62:20261115:v1',
            'title': 'R51t9：资源释放后的门槛、节点发送与前缀区分', 'classification': 'formal',
            'execution_status': 'running', 'executor': 'ai', 'kernels': ['threemind.continuous-memory/6.2'],
            'protocol': (HERE / 'protocol.zh.md').read_text('utf8'),
            'protocol_version': s.sha(HERE / 'protocol.zh.md'), 'required_roles': ['protocol', 'report', 'note', 'original'],
            'metadata': {'blocks': 2, 'primary_stages': 144, 'conditional_stages': 18,
                         'tail_stages': 8, 'production_changed': False}}, request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-doc-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                'expected_revision': 0, 'kind': 'protocol', 'title': 'R51t9 protocol ' + lang,
                'markdown': (HERE / f'protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True); assert rec.status['pending'] == 0
        s.write(work / 'registration.json', {'project': s.PROJECT, 'record': rec.experiment, 'pending': 0})
    s.write(work / 'frozen.json', {'sources': sources, 'native_path': str(dll), 'native_sha256': s.sha(dll),
        'variants': VARIANTS, 'fallback': FALLBACK, 'cases_sha256': s.sha(work / 'cases.json'),
        'references_sha256': s.sha(work / 'reference-manifest.json'), 'originals_cap': 2**30, 'peak_bytes': 4*2**30})
    print(json.dumps(s.read(work / 'registration.json')), flush=True)


def check(work):
    f = s.read(work / 'frozen.json')
    for rel, sha in f['sources'].items(): assert s.sha(ROOT / rel) == sha, rel
    assert s.sha(Path(f['native_path'])) == f['native_sha256']
    assert s.sha(work / 'cases.json') == f['cases_sha256']
    assert s.sha(work / 'reference-manifest.json') == f['references_sha256']
    for rel, sha in s.read(work / 'reference-manifest.json').items(): assert s.sha(work / rel) == sha, rel


def passes(work, name):
    return all(s.read(folder(work, name, b, cue) / 'result.json')['signed_peak'] > 1e-6
               for b in (0, 1) for cue in ('AB', 'DB'))


def run(work):
    check(work)
    assert not any((work / p).exists() for p in ('in-flight.json', 'STOP', 'summary.json'))
    import psutil
    index = s.read(work / 'cases.json'); results = []; began = time.monotonic()
    def execute(name, block, cue, guard):
        key = f'{name}/{block}/{cue}'; out = folder(work, name, block, cue)
        if (out / 'result.json').exists():
            q = s.read(out / 'result.json'); assert state_at(out, 'final').digest == q['final_sha256']
            results.append(q); return
        assert not (work / 'STOP').exists() and guard.thread.is_alive() and s.base.resource_check(work)['safe']
        out.mkdir(parents=True, exist_ok=False)
        s.write(work / 'in-flight.json', {'key': key, 'pid': os.getpid(), 'created': psutil.Process().create_time()})
        case = index[f'short/train-{block}' if cue == 'train' else f'history/s{block}/101/d1/{cue}']
        parent = None if cue == 'train' else state_at(folder(work, name, block, 'train'), 'final')
        e = create(name, case, state=parent)
        if parent is not None:
            # Keep the experimental resource condition through the diagnostic branches.
            e.reconfigure(replace(e.config, **(case['patch'] | condition(name)['patch'])))
        initial = e.capture_state(); previous.put(out / 'initial.rstate.gz', initial)
        trace = c.Trace(out / 'teaching.jsonl.gz') if cue == 'train' else None
        t = time.monotonic(); points = c.execute(e, case, s.inputs(work, case), trace)
        if trace: trace.close()
        final = e.capture_state(); previous.put(out / 'final.rstate.gz', final)
        assert state_at(out, 'final').digest == final.digest
        if cue != 'train': s.packed(out / 'process.json.gz', points)
        q = {} if cue == 'train' else s.measure.process(case, points)
        q.update(key=key, variant=name, block=block, cue=cue, kernel=final.to_dict()['dynamics'],
            initial_sha256=initial.digest, final_sha256=final.digest, parent_sha256=parent.digest if parent else None,
            time_us=e.time_us, wall_seconds=time.monotonic()-t, transport=final.to_dict().get('transport', {}))
        s.write(out / 'result.json', q); results.append(q)
        s.base.atomic_json(work / 'current.json', {'complete': len(results), 'primary_total': 144, 'last': key})
        (work / 'in-flight.json').unlink()
        print(json.dumps({'complete': len(results), 'key': key, 'margin': q.get('signed_peak'), 'seconds': q['wall_seconds']}), flush=True)
        del e, points; gc.collect()
    with s.base.worker_lock(work), previous.Guard(work) as guard:
        receipt = {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv}
        s.write(work / f'host-{time.time_ns()}.json', receipt); s.base.atomic_json(work / 'host.json', receipt)
        for name in VARIANTS:
            for block in (0, 1):
                for cue in ('train', 'AB', 'DB'):
                    if (work / 'STOP').exists(): return
                    execute(name, block, cue, guard)
            assert sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) < 2**30
        any_pass = any(passes(work, name) for name in VARIANTS)
        decision = {'modern_route_recovered': any_pass, 'run_old_inhibition_controls': not any_pass}
        if not (work / 'conditional-decision.json').exists(): s.write(work / 'conditional-decision.json', decision)
        else: assert s.read(work / 'conditional-decision.json') == decision
        if not any_pass:
            for name in FALLBACK:
                for block in (0, 1):
                    for cue in ('train', 'AB', 'DB'):
                        if (work / 'STOP').exists(): return
                        execute(name, block, cue, guard)
        s.write(work / 'summary.json', {'stages': len(results), 'results': results, 'wall_seconds': time.monotonic()-began,
            'conditional': decision})


def tails(work):
    check(work)
    assert (work / 'summary.json').exists() and not any((work / p).exists() for p in ('in-flight.json', 'STOP', 'tails.json'))
    # Predeclared comparison, not a selection based on measured prefix scores.
    names = ('stable-g4-r8', 'stable-g0-r08-sources0', 'default-g4-r8', 'default-g0-r08-sources0')
    results = []
    with s.base.worker_lock(work), previous.Guard(work):
        for name in names:
            for block in (0, 1):
                out = work / 'tails' / name / str(block); out.mkdir(parents=True, exist_ok=False)
                parent = state_at(folder(work, name, block, 'train'), 'final')
                e = create(name, state=parent)
                s.write(work / 'in-flight.json', {'tail': f'{name}/{block}', 'pid': os.getpid()})
                previous.put(out / 'initial.rstate.gz', e.capture_state())
                rows = []; t = time.monotonic(); begin = e.time_us
                for delay in (0, 1, 5, 10, 30, 60, 120, 300):
                    a = time.monotonic(); e.advance_to(begin + delay*1_000_000)
                    image = e.capture_state(); d = image.to_dict()
                    rows.append({'seconds': delay, 'time_us': e.time_us, 'life': e.life, 'wall_seconds': time.monotonic()-a,
                        'nodes': e.observation_nodes(), 'transport': d.get('transport', {}),
                        'edges': len(d['edges']), 'timer_count': len(d.get('timers', [])), 'state_sha256': image.digest})
                    assert time.monotonic()-t < 300, 'tail cost bound'
                    if e.life == 'dead': break
                final = e.capture_state(); previous.put(out / 'final.rstate.gz', final)
                s.write(out / 'result.json', {'variant': name, 'block': block, 'parent_sha256': parent.digest,
                    'final_sha256': final.digest, 'rows': rows, 'wall_seconds': time.monotonic()-t})
                results.append(s.read(out / 'result.json')); (work / 'in-flight.json').unlink()
                print(json.dumps({'tail': name, 'block': block, 'end_seconds': rows[-1]['seconds'], 'life': e.life}), flush=True)
                assert not (work / 'STOP').exists()
    s.write(work / 'tails.json', {'stages': len(results), 'results': results})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=('prepare', 'apparatus', 'register', 'check', 'run', 'tails'))
    p.add_argument('--work', type=Path, required=True); args = p.parse_args(); globals()[args.action](args.work)
