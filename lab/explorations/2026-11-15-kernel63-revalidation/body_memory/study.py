"""R63c: new 6.3 subjects, frozen E18 sensory recordings, and complete causal copies."""
import argparse
import copy
import gzip
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import statistics as st
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / 'src'), str(HERE.parent)]
import support as s
from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.readout_config import ActivityReadoutConfig, TemporalReadoutConfig
from dataclasses import asdict

OLD = ROOT / 'lab/explorations/2026-09-30-memory-transfer'
sys.path.insert(0, str(OLD))
spec = importlib.util.spec_from_file_location('r63c_old_material_functions', OLD / 'materials.py')
material = importlib.util.module_from_spec(spec)
spec.loader.exec_module(material)
KERNEL = 'threemind.continuous-memory/6.3'
PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
NS = UUID('2ecdccc7-5639-5249-96ac-6367eb4cbfe9')
READERS = {'structural_readout': {'enabled': False},
           'temporal_readout': asdict(TemporalReadoutConfig(max_response_us=5000000, baseline_us=0, max_active_windows=256)),
           'activity_readout': asdict(ActivityReadoutConfig(max_response_us=5000000, interval_us=100000, baseline_us=0))}


def read(p): return json.loads(Path(p).read_bytes())
def image(p): return ArtifactCodec.decode(Path(p).read_bytes())
def engine(config=None, state=None): return resolve_kernel(KERNEL).create(config, state, backend='native')


def save_state(p, state):
    raw = ArtifactCodec.encode(state)
    assert ArtifactCodec.decode(raw).digest == state.digest
    return s.blob(p, raw)


def case(key, seed, preset, mode, stage, parent=None, begin=0, end=0):
    ids = material.identities(seed)
    return {'key': key, 'seed': seed, 'preset': preset, 'mode': mode, 'stage': stage,
            'parent': parent, 'begin_us': begin, 'end_us': end, 'inputs': [],
            'config': {'seed': seed, **material.config(preset)}, 'mappings': ids,
            'targets': [ids['position_positive'], ids['position_negative']]}


def maintenance(c):
    for t in range(((c['begin_us'] + 499999) // 500000) * 500000, c['end_us'], 500000):
        c['inputs'].append({'kind': 'maintenance', 'stimulus': Stimulus(t, ((c['mappings']['keep'], 1.),), .2).to_dict()})


def clips(work, c, order, intensity):
    if c['mode'] == 'untrained': return
    for i, sign in enumerate(order):
        units = read(work / 'materials' / f"pendulum-{c['seed']}-{sign}-original.json")['units']
        transformed = material.transform(units, c['mode'], c['seed'])
        for u in transformed:
            u['time_us'] = str(i * 600000 + int(u['time_us']))
            u['intensity'] = intensity
            u['elements'].append({'channel': c['mappings']['A' if sign > 0 else 'B'], 'value': .5})
            u['measurements'].append({'controlled_marker': 'anonymous-posture-pair', 'physical_measurement': False})
            c['inputs'].append({'kind': 'teaching', 'unit': u, 'stimulus': material.frame(u).to_dict()})


def calibration_cases(work):
    rows = []
    for intensity in (.03, .1, .3, 1.):
        for preset in ('ordinary', 'facilitation'):
            for mode in ('full', 'no_imu'):
                c = case(f'cal-{intensity}-{preset}-{mode}', 930199, preset, mode, 'calibration', end=7200000)
                c['intensity'] = intensity
                clips(work, c, [1] * 12, intensity); maintenance(c); rows.append(c)
    return rows


def formal_cases(work, intensity):
    rows = []
    for seed in (930101, 930102, 930103, 930104):
        for preset in ('ordinary', 'facilitation'):
            for mode in ('full', 'no_imu', 'dose_matched', 'shuffled_imu', 'untrained'):
                prefix = f'{seed}-{preset}-{mode}'
                c = case(prefix + '-teaching', seed, preset, mode, 'teaching', end=19200000)
                order = [1, -1] if seed % 2 else [-1, 1]
                course = [order[0]] * 12 + [order[1]] * 12 + order * 4
                c['course'] = course; c['intensity'] = intensity
                clips(work, c, course, intensity); maintenance(c); rows.append(c)
                for delay in (1, 60, 300):
                    hold = case(prefix + f'-wait{delay}', seed, preset, mode, 'retention', parent=c['key'], begin=19200000, end=19200000 + delay * 1000000)
                    hold['delay'] = delay; maintenance(hold); rows.append(hold)
                    for cue in ('none', 'A', 'B'):
                        arms = ['intact'] + (['target', 'matched', 'restored'] if delay == 300 and mode in ('full', 'no_imu') and cue != 'none' else [])
                        for arm in arms:
                            p = case(hold['key'] + f'-{cue}-{arm}', seed, preset, mode, 'probe', parent=hold['key'], begin=hold['end_us'], end=hold['end_us'] + 5000000)
                            p.update(delay=delay, cue=cue, arm=arm, expected=None if cue == 'none' else int(cue == 'B'))
                            maintenance(p)
                            if cue != 'none':
                                p['inputs'].append({'kind': 'probe', 'stimulus': Stimulus(p['begin_us'], ((p['mappings'][cue], 1.),), .45).to_dict()})
                            rows.append(p)
    assert len(rows) == 616 and len({c['key'] for c in rows}) == 616
    return rows


def select_mask(graph, cue, targets):
    edges = {(e['source'], e['target']): e for e in graph['edges']}
    chosen = sorted(k for k in edges if k[0] == cue)
    excluded = {cue, *targets}
    pool = {k for k in edges if not set(k) & excluded}
    matched, errors = [], []
    if not chosen or len(pool) < len(chosen):
        return {'valid': False, 'reason': 'missing target or insufficient non-target edges', 'target': chosen, 'matched': [], 'errors': []}
    for edge in chosen:
        def distance(k):
            return abs(edges[k]['weight'] - edges[edge]['weight']) + abs(edges[k]['stability'] - edges[edge]['stability'])
        best = min(pool, key=lambda k: (distance(k), k))
        errors.append(distance(best)); matched.append(best); pool.remove(best)
    return {'valid': True, 'target': chosen, 'matched': matched, 'errors': errors}


def trial(work, c):
    folder = work / 'cases' / c['key']; folder.mkdir(parents=True, exist_ok=False)
    parent = image(work / 'cases' / c['parent'] / 'final.tmind') if c['parent'] else None
    e = engine(None if parent else c['config'], parent)
    initial = e.capture_state(); save_state(folder / 'initial.tmind', initial)
    assert parent is None or parent.digest == initial.digest
    intervention = None
    if c.get('arm', 'intact') != 'intact':
        selected = select_mask(e.graph(), c['mappings'][c['cue']], c['targets'])
        if selected['valid']:
            chosen = selected['matched' if c['arm'] == 'matched' else 'target']
            e.intervene(edges=chosen, action='silence')
            masked = e.capture_state()
            before_doc, after_doc = initial.to_dict(), masked.to_dict()
            before_doc.pop('silenced_edges'); after_doc.pop('silenced_edges')
            assert before_doc == after_doc
            if c['arm'] == 'restored':
                e.intervene(edges=chosen, action='restore')
                assert e.capture_state().digest == initial.digest
            intervention = selected | {'masked_sha256': masked.digest, 'after_sha256': e.capture_state().digest, 'arm': c['arm']}
        else:
            intervention = selected | {'arm': c['arm']}
    events = []
    cfg = READERS if c['stage'] == 'probe' else {k: {'enabled': False} for k in READERS}
    observer_start = e.capture_state().digest
    session = ReadoutSession(e, record=events.append, config=cfg)
    assert e.capture_state().digest == observer_start
    for i, row in enumerate(c['inputs']):
        session.schedule([{'stimulus': Stimulus.from_dict(row['stimulus'])}],
                         source='manual-registered-probe' if row['kind'] == 'probe' else 'background-registered-teaching',
                         adapter_id='registered-physical-replay', at=0, envelope_id=uuid5(NS, c['key'] + f':{i}'))
    s.base.original(folder / 'initial-observer.json', session.capture())
    points = []; start = time.monotonic(); paused = None
    def guard():
        if time.monotonic() - start > 300: raise TimeoutError('condition budget')
    try:
        while True:
            before = e.capture_state().digest
            nodes, metrics = e.observation_nodes(), e.metrics()
            assert before == e.capture_state().digest
            points.append({'time_us': e.time_us, 'nodes': nodes, 'metrics': metrics})
            if len(nodes) > 2000 or metrics['edges'] > 20000: raise TimeoutError('network budget')
            if e.time_us >= c['end_us'] or e.life == 'dead': break
            session.advance_to(min(c['end_us'], e.time_us + 100000), guard=guard)
    except TimeoutError as exc:
        paused = str(exc)
    if c['stage'] == 'probe': session.host.close(e.time_us, 'run_ended' if not paused else 'budget_paused')
    final = e.capture_state(); final_file = save_state(folder / 'final.tmind', final)
    s.base.original(folder / 'observer.json', session.capture())
    s.base.original(folder / 'input.json', c)
    s.base.original(folder / 'trajectory.json.gz', {'points': points, 'events': events}, compressed=True)
    result = {k: v for k, v in c.items() if k not in ('inputs', 'course')}
    result.update(status='paused-budget' if paused else 'complete', pause_reason=paused,
                  initial_sha256=initial.digest, final_sha256=final.digest, final_file=final_file,
                  clock_us=e.time_us, life=e.life, nodes=metrics['nodes'], edges=metrics['edges'],
                  intervention=intervention, wall_seconds=time.monotonic() - start)
    if c['stage'] == 'calibration':
        result['joint_responses'] = [next((n['activation'] for n in p['nodes'] if n['channel'] == c['targets'][0]), 0.)
                                      for p in points if p['time_us'] > 0 and p['time_us'] % 600000 == 0]
    s.base.original(folder / 'result.json', result)
    return result


def instrument(work):
    dest = ROOT / '.work/kernel63-rerun-body-instrument'
    dest.mkdir(exist_ok=False)
    c = case('observation', 930199, 'ordinary', 'full', 'probe', end=1000000)
    c['inputs'] = [{'kind': 'probe', 'stimulus': Stimulus(i * 100000, ((5111, 1.), (8111, .7)), .2).to_dict()} for i in range(3)]
    result = trial(dest, c)
    plain = engine(c['config'])
    for row in c['inputs']: plain.inject(Stimulus.from_dict(row['stimulus']))
    plain.advance_to(c['end_us'])
    assert plain.capture_state().digest == result['final_sha256']
    full = image(dest / 'cases/observation/final.tmind')
    restored = engine(state=full)
    session = ReadoutSession(restored, record=lambda _: None, state=read(dest / 'cases/observation/observer.json'))
    plain.advance_to(2000000); session.advance_to(2000000)
    assert plain.capture_state().digest == restored.capture_state().digest
    s.base.original(work / 'instrument-check.json', {'passed': True, 'scientific_blocks': 0,
                         'observation_preserves_core': True, 'whole_restore_preserves_continuation': True})


def prepare(work):
    assert not work.exists()
    assert read(work.parent/'causal-63-rerun-v1/publication/completion.json')['pending']==0
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free > (25 + 3.125) * 2**30
    work.mkdir(); (work / 'materials').mkdir()
    material_manifest = {}
    old_dir = ROOT / '.work/memory-transfer-20260930/materials'
    names = [f'pendulum-{seed}-{sign}-original.json' for seed in (930101, 930102, 930103, 930104) for sign in (-1, 1)] + ['pendulum-930199-1-original.json']
    for name in names:
        src = old_dir / name; target = work / 'materials' / name
        shutil.copyfile(src, target); assert s.sha(src) == s.sha(target)
        material_manifest[name] = {'source': str(src), 'sha256': s.sha(src)}
    calibration = calibration_cases(work)
    s.base.original(work / 'calibration-cases.json', calibration)
    instrument(work)
    from _threemind_native import _threemind_native as native
    paths = [HERE/'analyze.py', HERE/'verify.py', Path(__file__), HERE / 'protocol.zh.md', HERE / 'protocol.en.md', OLD / 'materials.py', OLD / 'common.py', HERE.parent / 'support.py', HERE.parent / 'allocation.py']
    production = read(work.parent / 'stimulus-63-rerun-v1/frozen.json')
    frozen = {'kernel': KERNEL, 'native_sha256': s.sha(native.__file__), 'materials': material_manifest,
              'sources': {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths},
              'production_sources': {k: v for k, v in production['sources'].items() if k.startswith(('src/', 'crates/'))},
              'calibration_sha256': s.sha(work / 'calibration-cases.json')}
    s.base.original(work / 'frozen.json', frozen)
    for p in paths + [ROOT/rel for rel in frozen['production_sources']]:
        dest = work / 'frozen-source' / p.relative_to(ROOT); dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dest)
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'), password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'), transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, PROJECT, client=client)
        rec.register({'source_key': 'r63c:body-memory:6.3:20261115:v1', 'title': 'R63c：6.3身体经历的过程保持与连接依赖',
                      'classification': 'formal', 'execution_status': 'running', 'executor': 'ai', 'kernels': [KERNEL],
                      'protocol': (HERE / 'protocol.zh.md').read_text('utf-8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
                      'required_roles': ['protocol', 'report', 'note', 'original'],
                      'metadata': {'formal_encoding_blocks': 4, 'calibration_seeds': 1, 'formal_conditions': 616, 'calibration_conditions': 16}}, request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-document-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)), 'expected_revision': 0,
                      'kind': 'protocol', 'title': 'R63c protocol ' + lang, 'markdown': (HERE / f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        value = {'project': PROJECT, 'record': rec.experiment, 'pending': rec.status['pending'], 'registered_before_run': True}
        s.base.original(work / 'registration.json', value); print(json.dumps(value))


def verify_frozen(work):
    frozen = read(work / 'frozen.json')
    for rel, h in frozen['sources'].items() | frozen['production_sources'].items(): assert s.sha(ROOT / rel) == h, rel
    for name, row in frozen['materials'].items(): assert s.sha(work / 'materials' / name) == row['sha256']
    from _threemind_native import _threemind_native as native
    assert s.sha(native.__file__) == frozen['native_sha256']
    assert read(work / 'registration.json')['pending'] == 0
    assert read(work / 'instrument-check.json')['passed']


def execute(work, rows, phase):
    import psutil
    verify_frozen(work)
    with s.base.worker_lock(work), s.base.Guard(work):
        assert not (work / 'in-flight.json').exists(), 'Preserve orphaned in-flight'
        start = time.monotonic(); out = []
        for c in rows:
            result_path = work / 'cases' / c['key'] / 'result.json'
            if result_path.exists():
                result = read(result_path)
                assert result['status'] == 'complete'
                assert image(result_path.with_name('final.tmind')).digest == result['final_sha256']
            else:
                assert not (work / 'STOP').exists(); s.base.resource_check(work)
                s.base.original(work / 'in-flight.json', {'phase': phase, 'case': c['key'], 'pid': psutil.Process().pid, 'created': psutil.Process().create_time()})
                result = trial(work, c)
                (work / 'in-flight.json').unlink()
                if result['status'] != 'complete':
                    s.base.original(work / 'STOP', {'reason': result['pause_reason'], 'complete_case': c['key']})
                    raise RuntimeError('Complete-boundary resource stop')
            out.append(result)
            s.base.atomic_json(work / 'current.json', {'phase': phase, 'completed': len(out), 'total': len(rows), 'last': c['key']})
            print(c['key'], flush=True)
            if time.monotonic() - start > 14400 or sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > 2**30:
                s.base.original(work / 'STOP', {'reason': 'batch budget', 'complete_case': c['key']})
                raise RuntimeError('Complete-boundary budget stop')
        s.base.original(work / (phase + '-complete.json'), {'conditions': len(out), 'wall_seconds': time.monotonic() - start})
    return out


def calibrate(work):
    assert not (work / 'calibration.json').exists()
    assert s.sha(work / 'calibration-cases.json') == read(work / 'frozen.json')['calibration_sha256']
    results = execute(work, read(work / 'calibration-cases.json'), 'calibration')
    s.base.original(work / 'calibration-resources.json', read(work / 'resource-summary.json'))
    scores = []
    for intensity in (.03, .1, .3, 1.):
        chosen = [r for r in results if r['intensity'] == intensity]
        vals = [v for r in chosen for v in r['joint_responses'][-6:]]
        complete = all(len(r['joint_responses']) == 12 for r in chosen)
        sat = sum(v >= .98 for v in vals) / len(vals) if vals else 1.
        avg = st.mean(vals) if vals else 0.
        scores.append({'intensity': intensity, 'valid': complete and all(r['life'] == 'active' for r in chosen) and min(vals) > .02,
                       'complete_samples': complete, 'mean': avg, 'saturation': sat, 'score': abs(avg - .45) + 2 * sat})
    valid = [r for r in scores if r['valid'] and r['saturation'] < .5]
    if not valid:
        s.base.original(work / 'calibration-failed.json', scores)
        s.base.original(work / 'STOP', {'reason': 'no measurable nonsaturated common dose', 'complete_conditions': 16})
        raise RuntimeError('Calibration has no eligible dose; formal subjects not started')
    selected = min(valid, key=lambda r: (r['score'], r['intensity']))
    rows = formal_cases(work, selected['intensity'])
    s.base.original(work / 'cases.json', rows)
    value = {'selected': selected, 'scores': scores, 'cases_sha256': s.sha(work / 'cases.json'), 'formal_material_results_unseen': True}
    s.base.original(work / 'calibration.json', value); print(json.dumps(value))


def run(work):
    assert not (work / 'summary.json').exists()
    chosen = read(work / 'calibration.json')
    assert s.sha(work / 'cases.json') == chosen['cases_sha256']
    rows = read(work / 'cases.json')
    assert len(rows) == 616
    execute(work, rows, 'formal')
    s.base.original(work / 'summary.json', {'status': 'awaiting-analysis', 'formal_conditions': 616, 'calibration_conditions': 16, 'formal_encoding_blocks': 4})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['prepare', 'calibrate', 'run']); p.add_argument('--work', type=Path, required=True)
    args = p.parse_args(); {'prepare': prepare, 'calibrate': calibrate, 'run': run}[args.action](args.work.resolve())
