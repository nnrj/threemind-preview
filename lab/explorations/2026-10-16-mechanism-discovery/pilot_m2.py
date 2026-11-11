"""Bounded native /5.1 research driver; never edits a kernel or old subject.

Registration and original-file publication use the existing ResearchRecorder.
Ordinary units resume only their complete current state. Orphaned units fail closed.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import random
import sys
import threading
import time
from pathlib import Path
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.study_lock import worker_lock
from threemind_core import StateImage, Stimulus
from threemind_kernels.local51 import Local51Config
from threemind_lab.config import load_env
from threemind_lab.operations_client import OperationsClient
from threemind_lab.provenance import capture_implementation
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.storage_files import atomic_json
from threemind_runtime import create_engine

HERE = Path(__file__).resolve().parent
DEFAULT_WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-pilot-v1')
KERNEL = 'threemind.continuous-memory/5.1'
NAMESPACE = UUID('9ee2497d-aa29-4a88-b09b-5316c168b733')
SYMBOLS = 'ABXYZWKN'
DELAY = (1, 30, 60, 300)
CUES = ('none', 'weak', 'strong', 'joint-total', 'joint-per')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def original(path, value, *, compressed=False):
    """Exclusive publication; an existing different original is an error."""
    raw = encoded(value)
    if compressed:
        raw = gzip.compress(raw, mtime=0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise RuntimeError('original differs: ' + str(path))
    else:
        part = path.with_suffix(path.suffix + '.partial')
        with part.open('xb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.link(part, path)
        part.unlink()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'byte_count': len(raw)}


def resource_module():
    # Reuse only the external read-only probe. Never load the E69 host.
    path = ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py'
    spec = importlib.util.spec_from_file_location('mechanism_host_resources', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def resource_check(work):
    g = resource_module()
    return g.check_resources(work, limits=g.Limits(5, 4, 5, 25))


def mapping(seed):
    rng = random.Random(seed)
    values = rng.sample(range(1, 2**32), len(SYMBOLS))
    return dict(zip(SYMBOLS, values)), rng.getstate()


def cases():
    # Delay cohorts have different origins; matched arms share an origin, not N.
    return [{'id': f'd{delay}-o{o}-{mode}-h{history}-{cue}',
             'origin': f'd{delay}-o{o}', 'seed': 716100 + 100*d + o,
             'delay': delay, 'mode': mode, 'history': history, 'cue': cue}
            for d, delay in enumerate(DELAY) for o in range(8)
            for mode in ('H', 'S') for history in (0, 1) for cue in CUES]


def schedule(case, channels):
    end = (17 + case['delay'] + 2) * 1_000_000
    rows = []

    def add(t, symbols, intensity, amplitudes=None, kind='teaching'):
        amplitudes = amplitudes or [1.0]*len(symbols)
        stimulus = Stimulus(t, tuple((channels[s], a) for s, a in zip(symbols, amplitudes)), intensity)
        rows.append({'kind': kind, 'stimulus': stimulus.to_dict()})

    for t in range(0, end + 1, 500_000):
        add(t, 'K', .2, kind='maintenance')
    groups = ('XYA', 'ZWB') if case['history'] == 0 else ('XYB', 'ZWA')
    if case['seed'] % 2:
        groups = groups[::-1]
    for r in range(16):
        for j, group in enumerate(groups):
            add(1_000_000 + r*1_000_000 + j*250_000, group, .4)
    add(17_000_000, 'N', .2, kind='common-final')
    start = (17 + case['delay'])*1_000_000
    cue = case['cue']
    if cue in ('weak', 'strong'):
        add(start, 'X', .4 if cue == 'weak' else .8, kind='probe')
    elif cue.startswith('joint'):
        add(start, 'XY', .4, [0.5, 0.5] if cue == 'joint-total' else [1., 1.], kind='probe')
    priority = {'maintenance': 0, 'teaching': 1, 'common-final': 2, 'probe': 3}
    return sorted(rows, key=lambda row: (int(row['stimulus']['time_us']), priority[row['kind']]))


def project(nodes, channels):
    # No history, expected response, seed, case ID, time or filename arguments.
    by_channel = {n['channel']: n for n in nodes}
    return {k: [by_channel.get(channels[s], {}).get(k, 0.) for s in 'AB']
            for k in ('activation', 'direct', 'associative', 'inhibition')}


class Subject:
    def __init__(self, case, saved=None):
        self.case = dict(case)
        if saved is None:
            self.channels, self.rng = mapping(case['seed'])
            config = Local51Config(seed=case['seed'], energy_seed=case['seed'] ^ 0x1634AB,
                                  consolidation_mode='adaptive-half-life' if case['mode'] == 'H' else 'legacy-stability')
            self.engine = create_engine(config, kernel_id=KERNEL, backend='native')
            self.events = schedule(case, self.channels)
            self.cursor, self.rows, self.actuator = 0, [], None
        else:
            if saved['case'] != case or saved['schema'] != 'threemind.m2-whole-subject/1':
                raise ValueError('whole subject identity mismatch')
            self.channels, self.rng = saved['mappings'], saved['random_state']
            self.events, self.cursor = saved['environment']['schedule'], saved['input_cursor']
            if self.events != schedule(case, self.channels):
                raise ValueError('saved input schedule differs')
            self.rows, self.actuator = saved['recent_activity'], saved['actuators']
            self.engine = create_engine(state=StateImage.from_dict(saved['core']), backend='native', kernel_id=KERNEL)
        if self.engine.dynamics != KERNEL:
            raise ValueError('genuine /5.1 required')
        if saved is not None and digest(self.save()) != digest(saved):
            raise ValueError('complete restore changed a saved component')

    @property
    def probe_start(self):
        return (17+self.case['delay'])*1_000_000

    def save(self):
        return {'schema': 'threemind.m2-whole-subject/1', 'case': self.case,
                'core': self.engine.capture_state().to_dict(),
                'peripheral_weights': {'kind': 'fixed-A-minus-B/1', 'trainable': False},
                'optimizer': None, 'body': None, 'mappings': self.channels,
                'random_state': self.rng, 'recent_activity': self.rows, 'actuators': self.actuator,
                'environment': {'kind': 'fixed-external-schedule/1', 'schedule': self.events},
                'input_cursor': self.cursor}

    def advance(self, target, *, observation='normal'):
        if target < self.engine.time_us:
            raise ValueError('no reversal')
        # The sampling lattice and external events, not host time, determine advancement.
        times = range(self.engine.time_us if self.cursor == 0 else self.engine.time_us+50_000,
                      target+1, 50_000)
        for t in times:
            while self.cursor < len(self.events) and int(self.events[self.cursor]['stimulus']['time_us']) <= t:
                # Save the pre-probe boundary before injecting its task cue.
                # Maintenance at this timestamp precedes the cue by protocol.
                if t == target == self.probe_start and self.events[self.cursor]['kind'] == 'probe':
                    break
                self.engine.inject(Stimulus.from_dict(self.events[self.cursor]['stimulus']))
                self.cursor += 1
            self.engine.advance_to(t)
            if observation == 'frequent':
                self.engine.metrics()
                self.engine.graph()
                self.engine.activations()
                self.engine.capture_state()
            if self.probe_start <= t <= self.probe_start+2_000_000:
                p = project(self.engine.observation_nodes(), self.channels)
                self.actuator = p['activation'][0]-p['activation'][1]
                self.rows.append({'time_us': t, 'response': self.actuator, **p})
            if self.engine.life == 'dead':
                break

    def traces(self):
        graph = self.engine.graph()
        id_channel = {n['id']: n['channel'] for n in graph['nodes']}
        groups = ('XYA', 'ZWB') if self.case['history'] == 0 else ('XYB', 'ZWA')
        wanted = {(self.channels[a], self.channels[b]) for group in groups for a in group for b in group if a != b}
        selected = [e for e in graph['edges'] if (id_channel[e['source']], id_channel[e['target']]) in wanted]
        return {'target_edge_count': 12, 'surviving': len(selected),
                'effective_weight_sum': sum(e['weight'] for e in selected),
                'edges': selected, 'same_time_graph': graph}

    def result(self):
        window = [r for r in self.rows if 500_000 <= r['time_us']-self.probe_start <= 1_500_000]
        first = next((r['response'] for r in self.rows if r['time_us'] == self.probe_start+500_000), None)
        mean = sum(r['response'] for r in window)/len(window) if window else None
        sign = 1 if self.case['history'] == 0 else -1
        return {'case': self.case, 'life': self.engine.life, 'final_time_us': self.engine.time_us,
                'sample_count': len(self.rows), 'window_count': len(window), 'first_response': first,
                'mean_response': mean, 'history_signed_mean': None if mean is None else sign*mean,
                'first_correct': None if first is None or abs(first) <= 1e-9 else sign*first > 0,
                'whole_state_sha256': digest(self.save())}


class Guard:
    def __init__(self, work):
        self.work, self.started = work, time.monotonic()
        self.stop = threading.Event()
        self.last = None
        self.peak_private = 0
        self.minimum = {}
        self.thread = threading.Thread(target=self.watch, daemon=True)

    def watch(self):
        import psutil
        while not self.stop.is_set():
            try:
                self.last = resource_check(self.work)
                private = psutil.Process().memory_info().private
                self.peak_private = max(self.peak_private, private)
                for k, v in self.last['available_bytes'].items():
                    self.minimum[k] = min(v, self.minimum.get(k, v))
                if private > 2**30:
                    raise RuntimeError('pilot process private memory exceeds 1 GiB')
                if time.monotonic()-self.started > 7200:
                    raise RuntimeError('registered 2 hour host budget reached')
            except Exception as exc:  # noqa: BLE001 -- monitoring failures request a boundary stop
                try:
                    with (self.work/'STOP').open('x', encoding='utf-8') as out:
                        json.dump({'reason': str(exc), 'epoch': time.time(), 'last': self.last}, out)
                except FileExistsError:
                    pass
                return
            self.stop.wait(1)

    def __enter__(self):
        resource_check(self.work)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(3)
        atomic_json(self.work/'resource-summary.json', {'peak_private_bytes': self.peak_private,
                    'minimum_available_bytes': self.minimum, 'wall_seconds': time.monotonic()-self.started})


def connection():
    load_env()
    return OperationsClient.from_environment(source='ai')


def recorder(work, client):
    platform = read(work/'platform.json')
    r = ResearchRecorder(work, platform['project_id'], client=client)
    r.resume_recording()
    return r


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with worker_lock(work), connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered; inspect status, do not re-register')
        name = '2026-10-16 机制发现 · M2 首批装置与探索'
        candidates = [p for p in client.call('projects.list', {}) if p['name'] == name]
        if len(candidates) > 1:
            raise RuntimeError('ambiguous registration projects')
        # This canonical project endpoint has no operation receipt. Reconcile by unique name before retry.
        project = candidates[0] if candidates else client.request('POST', '/api/v2/projects', body={'name': name})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-m2-pilot-20261016'}
        original(work/'platform.json', platform)
        implementation = capture_implementation('native')
        original(work/'implementation.json', implementation)
        files = [Path(__file__), HERE/'pilot-m2.zh.md', HERE/'pilot-m2.en.md',
                 ROOT/'lab/tools/study_lock.py',
                 ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        for p in files:
            original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        original(work/'runner-manifest.json', manifest)
        original(work/'cases.json', cases())
        r = ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:M2:pilot-v1:20261016', 'title': name,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [KERNEL], 'protocol': (HERE/'pilot-m2.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'independent_origins': 32, 'arms': 640,
                                 'authorization': '2026-10-16 direct overnight execution request',
                                 'E69_resumed': False}}, request_id=uuid5(NAMESPACE, 'register'))
        r.synchronize(strict=True)
        # Existing managed evidence root and canonical storage API, not a new store.
        resource_body = {'resource_id': platform['resource_id'], 'target_id': 'managed-research-experiments',
                         'relative_path': '2026-10-16-mechanism-discovery/m2-pilot-v1',
                         'registered_work_path': str(work), 'writer_mode': 'cooperative', 'expected_revision': 0}
        client.request('POST', '/api/v2/storage/resources', body=resource_body,
                       headers={'X-ThreeMind-Request-ID': str(uuid5(NAMESPACE, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={
                       'project_id': project['id'], 'resource_id': platform['resource_id']},
                       headers={'X-ThreeMind-Request-ID': str(uuid5(NAMESPACE, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NAMESPACE, 'protocol:'+lang)),
                    'identity': str(uuid5(NAMESPACE, 'protocol-document:'+lang)), 'expected_revision': 0,
                    'kind': 'protocol', 'title': 'M2 pilot v1 '+lang,
                    'markdown': (HERE/f'pilot-m2.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps(platform | {'experiment': r.experiment, 'status': r.status}), flush=True)


def frozen_check(work):
    manifest = read(work/'runner-manifest.json')
    for name, expected in manifest.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('runner/protocol changed after registration: '+name)
    implementation = capture_implementation('native')
    if implementation != read(work/'implementation.json'):
        raise RuntimeError('implementation identity changed; review before continuing')


def apparatus(work):
    with worker_lock(work), connection() as client:
        frozen_check(work)
        if (work/'apparatus.json').exists() or (work/'apparatus-in-flight.json').exists():
            raise RuntimeError('apparatus exists/incomplete; no blind rerun')
        resource_check(work)
        r = recorder(work, client)
        original(work/'apparatus-in-flight.json', {'pid': os.getpid(), 'epoch': time.time()})
        case = {'id': 'apparatus', 'origin': 'apparatus', 'seed': 716001,
                'delay': 1, 'mode': 'H', 'history': 0, 'cue': 'weak'}
        states = {}
        for mode in ('plain', 'observed', 'restored', 'paused'):
            subject = Subject(case)
            subject.advance(10_000_000, observation='frequent' if mode == 'observed' else 'normal')
            before = subject.save()
            original(work/'apparatus'/f'{mode}-10s.json.gz', before, compressed=True)
            if mode == 'restored':
                saved = json.loads(gzip.decompress((work/'apparatus'/f'{mode}-10s.json.gz').read_bytes()))
                subject = Subject(case, saved)
                if digest(subject.save()) != digest(before):
                    raise RuntimeError('restoration changed complete state')
            if mode == 'paused':
                time.sleep(.25)
                if digest(subject.save()) != digest(before):
                    raise RuntimeError('wall clock changed state')
            subject.advance(20_000_000, observation='frequent' if mode == 'observed' else 'normal')
            states[mode] = digest(subject.save())
            original(work/'apparatus'/f'{mode}-20s.json.gz', subject.save(), compressed=True)
        report = {'schema': 'threemind.m2-apparatus/1', 'passed': len(set(states.values())) == 1,
                  'whole_state_hashes': states, 'subject_seed': 716001, 'pilot_included': False}
        original(work/'apparatus.json', report)
        r.append('result', 'apparatus-v1', report, request_id=uuid5(NAMESPACE, 'apparatus'))
        r.synchronize()
        (work/'apparatus-in-flight.json').unlink()
        print(json.dumps(report), flush=True)
        if not report['passed']:
            raise RuntimeError('apparatus mismatch; retain evidence and block pilot')


def run(work):
    import psutil
    with worker_lock(work), connection() as client:
        frozen_check(work)
        if not read(work/'apparatus.json')['passed']:
            raise RuntimeError('apparatus has not passed')
        if (work/'in-flight.json').exists() or (work/'STOP').exists():
            raise RuntimeError('STOP or orphan in-flight; explicit review required')
        r = recorder(work, client)
        atomic_json(work/'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(),
                    'command': sys.argv, 'epoch': time.time()})
        with Guard(work) as guard:
            for case in read(work/'cases.json'):
                folder = work/'cases'/case['id']
                if (folder/'result.json').exists():
                    request_id = uuid5(NAMESPACE, 'result:'+case['id'])
                    if not (r.control/'receipts'/f'{request_id}.json').exists():
                        r.append('result', case['id'], read(folder/'result.json'), request_id=request_id)
                    continue
                if (work/'STOP').exists():
                    break
                current_path = folder/'current.json'
                if current_path.exists():
                    current = read(current_path)
                    path = folder/current['path']
                    raw = path.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != current['sha256']:
                        raise RuntimeError('current state hash differs')
                    subject = Subject(case, json.loads(gzip.decompress(raw)))
                    index = current['index']+1
                else:
                    original(work/'in-flight.json', {'case': case, 'operation': 'birth', 'pid': os.getpid()})
                    subject = Subject(case)
                    index = 0
                    folder.mkdir(parents=True, exist_ok=True)
                    commit_subject(folder, subject, index)
                    (work/'in-flight.json').unlink()
                    index += 1
                end = (17+case['delay']+2)*1_000_000
                while subject.engine.time_us < end and subject.engine.life != 'dead':
                    if (work/'STOP').exists():
                        break
                    if not guard.thread.is_alive():
                        raise RuntimeError('resource monitor died without a STOP')
                    now = subject.engine.time_us
                    target = min(end, now+10_000_000,
                                 next(t for t in [17_000_000, subject.probe_start, end] if t > now))
                    original(work/'in-flight.json', {'case': case, 'from_us': now, 'to_us': target,
                             'index': index, 'pid': os.getpid()})
                    subject.advance(target)
                    commit_subject(folder, subject, index)
                    if subject.engine.time_us in (17_000_000, subject.probe_start):
                        original(folder/f'traces-{subject.engine.time_us}.json.gz', subject.traces(), compressed=True)
                    (work/'in-flight.json').unlink()
                    index += 1
                if subject.engine.time_us < end and subject.engine.life != 'dead':
                    break
                result = subject.result()
                original(folder/'result.json', result)
                r.append('result', case['id'], result, request_id=uuid5(NAMESPACE, 'result:'+case['id']))
                r.synchronize()
                atomic_json(work/'progress.json', {'last_completed': case['id'], 'epoch': time.time(),
                            'completed': sum((work/'cases'/c['id']/'result.json').exists() for c in cases()),
                            'total': len(cases()), 'recorder': r.status})
                print(json.dumps({'completed': case['id'], 'time_us': subject.engine.time_us,
                                  'mean': result['mean_response'], 'life': subject.engine.life}), flush=True)
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) >= 4*2**30:
                    original(work/'STOP', {'reason': '4 GiB original budget reached', 'epoch': time.time()})
                    break
            r.synchronize()
        completed = sum((work/'cases'/c['id']/'result.json').exists() for c in cases())
        atomic_json(work/'status.json', {'state': 'awaiting-analysis' if completed == len(cases()) else 'paused',
                    'completed': completed, 'total': len(cases()), 'epoch': time.time(), 'recorder': r.status})


def commit_subject(folder, subject, index):
    name = f'whole-{index:04d}.json.gz'
    receipt = original(folder/name, subject.save(), compressed=True)
    atomic_json(folder/'current.json', {'path': name, 'index': index, 'time_us': subject.engine.time_us, **receipt})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('register', 'apparatus', 'run', 'status', 'check'))
    parser.add_argument('--work', type=Path, default=DEFAULT_WORK)
    args = parser.parse_args()
    work = args.work.resolve()
    if args.command == 'check':
        print(json.dumps(resource_check(work)))
    elif args.command == 'status':
        print(json.dumps({name: read(work/name) if (work/name).exists() else None
                          for name in ['platform.json', 'apparatus.json', 'host.json', 'progress.json',
                                       'status.json', 'STOP', 'in-flight.json', 'resource-summary.json']}, ensure_ascii=False))
    else:
        {'register': register, 'apparatus': apparatus, 'run': run}[args.command](work)


if __name__ == '__main__':
    main()
