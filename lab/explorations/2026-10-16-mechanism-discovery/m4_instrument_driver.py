"""Bounded N=0 physical apparatus acceptance; no formal M4 cohort is launched."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5

import numpy as np
import psutil
import torch

import pilot_m2 as m
from m4_instrument import Whole, calibrate_instrument, digest

HERE = Path(__file__).resolve().parent
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m4-instrument-v1')
NS = UUID('67f7f923-7bb3-4efd-856a-93478074d77c')
MODES = ('plain', 'observed', 'restored', 'paused')
SEED = 1106002


class InstrumentGuard(m.Guard):
    """Same system reserves; separate preregistered apparatus host budget."""
    def watch(self):
        while not self.stop.is_set():
            try:
                self.last = m.resource_check(self.work)
                private = psutil.Process().memory_info().private
                self.peak_private = max(self.peak_private, private)
                for k, v in self.last['available_bytes'].items():
                    self.minimum[k] = min(v, self.minimum.get(k, v))
                if private > 3*2**30:
                    raise RuntimeError('registered instrument private memory exceeds 3 GiB')
                if time.monotonic()-self.started > 600:
                    raise RuntimeError('registered instrument 10 minute budget reached')
            except Exception as exc:
                try:
                    with (self.work/'STOP').open('x', encoding='utf-8') as out:
                        json.dump({'reason': str(exc), 'epoch': time.time(), 'last': self.last}, out)
                except FileExistsError:
                    pass
                return
            self.stop.wait(1)


def source_paths():
    paths = {Path(__file__), HERE/'m4_instrument.py', HERE/'test_m4_instrument.py',
             HERE/'test_m4_instrument_guard.py', HERE/'m4_instrument_audit.py',
             HERE/'m4-instrument-protocol.zh.md', HERE/'m4-instrument-protocol.en.md',
             HERE/'pilot_m2.py', m.ROOT/'lab/tools/study_lock.py',
             m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/system.py',
             m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py'}
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, '__file__', None)
        if name.startswith('lab.') and file and Path(file).suffix == '.py':
            paths.add(Path(file).resolve())
    return sorted(paths)


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered; do not repeat')
        title = '2026-10-16 机制发现 · M4真实眼手装置完整性验收v1'
        matches = [p for p in client.call('projects.list', {}) if p['name'] == title]
        if len(matches) > 1:
            raise RuntimeError('ambiguous project')
        project = matches[0] if matches else client.request('POST', '/api/v2/projects', body={'name': title})
        resource = 'mechanism-m4-instrument-v1-20261016'
        m.original(work/'platform.json', {'project_id': project['id'], 'resource_id': resource})
        paths = source_paths()
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        for p in paths:
            m.original(work/'frozen'/p.relative_to(m.ROOT), {'utf8': p.read_text(encoding='utf-8')})
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:m4-instrument-v1:20261016', 'title': title,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (HERE/'m4-instrument-protocol.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'scientific_origins': 0, 'instrument_seed': SEED,
                                 'paths': list(MODES), 'Core_changed': False, 'E69_resumed': False}},
                   request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={'resource_id': resource,
            'target_id': 'managed-research-experiments', 'relative_path': '2026-10-16-mechanism-discovery/m4-instrument-v1',
            'registered_work_path': str(work), 'writer_mode': 'cooperative', 'expected_revision': 0},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants',
                       body={'project_id': project['id'], 'resource_id': resource},
                       headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M4 instrument acceptance '+lang,
                    'markdown': (HERE/f'm4-instrument-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps({'project': project['id'], 'record': r.experiment, 'status': r.status}), flush=True)


def physical_state(a):
    w = a.session.world
    return {'eye': w.eye_angle.tolist(), 'hand': [w.pointer.x, w.pointer.y], 'time_us': a.session.engine.time_us}


def path_unit(work, mode):
    folder = work/'paths'/mode
    a = Whole.restore(work/'birth')
    rows = []
    transitions = [physical_state(a)]
    observer_checks = []
    learning = []
    texts = ('看', '指', '看指')
    forces = (((.20, -.10), (0., 0.)), ((0., 0.), (.20, .10)), ((-.15, .12), (-.15, .18)))
    started = time.perf_counter()
    for step in range(60):
        phase = step//20
        a.phase = ('eye-command', 'hand-command', 'joint-command')[phase]
        frames = list(a.session.sensor.frames(texts[phase]))
        text_frame = frames[step % 20] if step % 20 < len(frames) else None
        eye, hand = forces[phase]
        rows.append(a.session.tick(text_frame, eye=eye, hand=hand))
        a.cursor += 1
        if mode == 'observed':
            before = digest(a.canonical())
            a.session.engine.graph(); a.session.engine.metrics()
            a.session.engine.activations(); a.session.engine.capture_state()
            after = digest(a.canonical())
            observer_checks.append({'step': step+1, 'before': before, 'after': after, 'equal': before == after})
            if before != after:
                raise RuntimeError('observation changed complete instrument state')
        if step+1 in (30, 60):
            learning.append({'step': step+1, 'result': calibrate_instrument(a, rows[-8:])})
        if step+1 == 30:
            a.save(folder/'middle')
            if mode == 'restored':
                del a
                gc.collect()
                a = Whole.restore(folder/'middle')
            elif mode == 'paused':
                before = digest(a.canonical())
                time.sleep(.2)
                if before != digest(a.canonical()):
                    raise RuntimeError('wall-clock pause changed complete state')
        if step+1 in (20, 40, 60):
            transitions.append(physical_state(a))
    a.save(folder/'final')
    m.original(folder/'trajectory.json.gz', rows, compressed=True)
    m.original(folder/'observer-checks.json', observer_checks)
    m.original(folder/'calibration.json', learning)
    displacements = [{'eye': float(np.linalg.norm(np.subtract(b['eye'], p['eye']))),
                      'hand': float(np.linalg.norm(np.subtract(b['hand'], p['hand'])))}
                     for p, b in zip(transitions, transitions[1:])]
    image = a.session.engine.capture_state().to_dict()
    result = {'mode': mode, 'canonical_sha256': digest(a.canonical()), 'time_us': a.session.engine.time_us,
              'motor_updates': a.motor.committed_updates, 'word_updates': a.words.committed_updates,
              'observer_count': len(observer_checks), 'observer_unchanged': all(x['equal'] for x in observer_checks),
              'body_transitions': transitions, 'displacements': displacements,
              'command_reached_body': displacements[0]['eye'] > 1e-8 and displacements[1]['hand'] > 1e-8
                  and displacements[2]['eye'] > 1e-8 and displacements[2]['hand'] > 1e-8,
              'nodes': len(image['nodes']), 'edges': len(image['edges']),
              'wall_seconds': time.perf_counter()-started, 'scientific_origins': 0}
    del a, image, rows
    gc.collect()
    return result


def run(work):
    torch.set_num_threads(1)
    # This is an N=0 instrument test, not another scientific host. Its own lock
    # prevents duplication; the preregistered extra reserve permits concurrency.
    with m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if any((work/n).exists() for n in ('host.json', 'STOP', 'in-flight.json', 'status.json')):
            raise RuntimeError('prior attempt or unresolved marker; preserve it')
        resources = m.resource_check(work)
        for name in ('commit', 'ram'):
            if resources['available_bytes'][name] < resources['limits_bytes'][name]+3*2**30:
                raise RuntimeError('insufficient additional 3GiB apparatus headroom')
        m.original(work/'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(), 'command': sys.argv})
        r = m.recorder(work, client)
        results = []
        with InstrumentGuard(work) as guard:
            m.original(work/'in-flight.json', {'unit': 'birth', 'pid': os.getpid(), 'epoch': time.time()})
            a = Whole(SEED, identity='m4-instrument-v1')
            a.session.world.set_scene([(0, 0)], positions=[[.4, .3]])
            a.session.world.marker = [.4, .3]
            a.session.world._refresh_directions()
            a.save(work/'birth')
            del a
            gc.collect()
            (work/'in-flight.json').unlink()
            for mode in MODES:
                if (work/'STOP').exists():
                    break
                if not guard.thread.is_alive():
                    raise RuntimeError('instrument resource guard absent')
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > 512*2**20:
                    m.original(work/'STOP', {'reason': '512MiB instrument original cap'})
                    break
                m.original(work/'in-flight.json', {'unit': mode, 'pid': os.getpid(), 'epoch': time.time()})
                result = path_unit(work, mode)
                m.original(work/'paths'/mode/'result.json', result)
                results.append(result)
                (work/'in-flight.json').unlink()
                m.atomic_json(work/'progress.json', {'completed': len(results), 'total': len(MODES), 'last': mode, 'epoch': time.time()})
                r.append('result', mode, result, request_id=uuid5(NS, 'path:'+mode))
                r.synchronize()
                print(json.dumps({'completed': len(results), 'total': len(MODES), 'mode': mode, 'pending': r.status['pending']}), flush=True)
        if len(results) == len(MODES):
            m.original(work/'apparatus.json', {'passed': len({x['canonical_sha256'] for x in results}) == 1
                       and all(x['time_us'] == 3_000_000 and x['motor_updates'] == 4 and x['word_updates'] == 0
                               and x['observer_unchanged'] and x['command_reached_body'] for x in results),
                       'paths': results, 'scientific_origins': 0})
        m.atomic_json(work/'status.json', {'state': 'awaiting-analysis' if len(results) == len(MODES) and not (work/'STOP').exists()
                                        else 'resource-paused', 'completed': len(results), 'total': len(MODES)})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=('register', 'run', 'status', 'check'))
    p.add_argument('--work', type=Path, default=WORK)
    a = p.parse_args(); work = a.work.resolve()
    if a.command == 'check':
        print(json.dumps(m.resource_check(work)))
    elif a.command == 'status':
        print(json.dumps({n: m.read(work/n) if (work/n).exists() else None for n in
              ('platform.json', 'host.json', 'progress.json', 'status.json', 'STOP', 'in-flight.json', 'resource-summary.json', 'apparatus.json')}))
    else:
        {'register': register, 'run': run}[a.command](work)
