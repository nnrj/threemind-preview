"""Declared baseline replay; ThreeMind originals are never loaded into an engine."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid5

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_m2 as m

HERE, ROOT = m.HERE, m.ROOT
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m3-c1-replay-v1')
SOURCE = m.DEFAULT_WORK
NS = UUID('b447f93a-ed62-4ce6-b12b-ef133210d058')
KINDS = ('reactive', 'finite-state', 'hebbian', 'fixed-rnn-reader')


def cases():
    return [{'id': f'o{o}-h{h}-{cue}-{kind}', 'source_id': f'd1-o{o}-H-h{h}-{cue}',
             'origin': f'd1-o{o}', 'seed': 716100+o, 'history': h, 'cue': cue, 'kind': kind}
            for o in range(8) for h in (0, 1) for cue in ('none', 'strong') for kind in KINDS]


class Controller:
    """No access to case identity, history, expected answer or phase."""
    def __init__(self, kind, seed, a, b, saved=None):
        self.kind, self.a, self.b = kind, int(a), int(b)
        if saved is None:
            rng = np.random.Generator(np.random.PCG64(seed+991716))
            self.rng = rng.bit_generator.state
            self.y, self.updates = 0., 0
            self.memory = np.zeros(8)
            self.W = np.zeros((8, 8))
            self.h, self.w = np.zeros(64), np.zeros(64)
            self.P = np.eye(64)*1000
            if kind == 'fixed-rnn-reader':
                self.U = rng.normal(size=(64, 8))/math.sqrt(8)
                self.R = rng.normal(size=(64, 64))/math.sqrt(64)
                self.R *= .9/max(abs(np.linalg.eigvals(self.R)))
                self.rng = rng.bit_generator.state
            else:
                self.U, self.R = np.zeros((64, 8)), np.zeros((64, 64))
        else:
            if (saved['kind'], saved['a'], saved['b']) != (kind, a, b):
                raise ValueError('controller identity mismatch')
            self.y, self.updates, self.rng = saved['y'], saved['updates'], saved['rng']
            for name in ('memory', 'W', 'h', 'w', 'P', 'U', 'R'):
                setattr(self, name, np.array(saved[name], dtype=float))

    def observe(self):
        return float(self.y)

    def save(self):
        return {'kind': self.kind, 'a': self.a, 'b': self.b, 'y': self.y,
                'updates': self.updates, 'rng': self.rng,
                **{n: getattr(self, n).tolist() for n in ('memory', 'W', 'h', 'w', 'P', 'U', 'R')}}

    def step(self, x):
        x = np.asarray(x, dtype=float)
        if x.shape != (8,) or not np.isfinite(x).all():
            raise ValueError('invalid public input')
        a, b = self.a, self.b
        label = float(x[a]-x[b])
        decision = label
        if self.kind == 'finite-state':
            if label:
                for j in range(8):
                    if j not in (a, b) and x[j] != 0:
                        self.memory[j] = np.sign(label)
                self.updates += 1
            decision += float(self.memory @ x)
        elif self.kind == 'hebbian':
            if np.count_nonzero(x) > 1:
                self.W += .1*np.outer(x, x)
                np.fill_diagonal(self.W, 0.)
                self.updates += 1
            propagated = self.W.T @ x
            decision += float(propagated[a]-propagated[b])
        elif self.kind == 'fixed-rnn-reader':
            self.h = .8*self.h+.2*np.tanh(self.R@self.h+self.U@x)
            if label:
                ph = self.P@self.h
                k = ph/(1.+self.h@ph)
                self.w += k*(label-self.w@self.h)
                self.P -= np.outer(k, self.h@self.P)
                self.updates += 1
            self.y = float(self.w@self.h)
            return self.y
        elif self.kind != 'reactive':
            raise ValueError('unknown controller')
        self.y = math.exp(-.05/.25)*self.y+decision
        return self.y


class Replay:
    def __init__(self, case, source, saved=None):
        self.case, self.source = case, source
        self.channels = source['mappings']
        ordered = sorted(self.channels.values())
        self.indices = {c: i for i, c in enumerate(ordered)}
        a, b = self.indices[self.channels['A']], self.indices[self.channels['B']]
        if saved is None:
            self.model = Controller(case['kind'], case['seed'], a, b)
            self.next_frame, self.cursor, self.rows = 0, 0, []
        else:
            if saved['case'] != case or saved['source_sha256'] != m.digest(source):
                raise ValueError('replay source/identity changed')
            self.model = Controller(case['kind'], case['seed'], a, b, saved['controller'])
            self.next_frame, self.cursor, self.rows = saved['next_frame_us'], saved['input_cursor'], saved['recent_activity']
            if m.digest(saved) != m.digest(self.save()):
                raise ValueError('whole replay restoration mismatch')

    def save(self):
        return {'schema': 'threemind.m3-baseline-whole/1', 'case': self.case,
                'source_sha256': m.digest(self.source), 'controller': self.model.save(),
                'environment': self.source['environment'], 'mappings': self.channels,
                'next_frame_us': self.next_frame, 'input_cursor': self.cursor,
                'recent_activity': self.rows, 'actuator': self.model.observe(), 'body': None}

    def advance(self, until, frequent=False):
        if until < self.next_frame-50_000:
            raise ValueError('no time reversal')
        events = self.source['environment']['schedule']
        while self.next_frame <= until:
            t, x = self.next_frame, np.zeros(8)
            delivered = []
            while self.cursor < len(events):
                event = events[self.cursor]
                st = event['stimulus']
                delivery = int(st['time_us'])+(50_000 if event['kind'] == 'probe' else 0)
                if delivery > t:
                    break
                for channel, amplitude in st['channels']:
                    x[self.indices[int(channel)]] += float(amplitude)*float(st['intensity'])
                delivered.append(self.cursor)
                self.cursor += 1
            self.model.step(x)
            if t >= 18_000_000:
                self.rows.append({'time_us': t, 'response': self.model.observe(),
                                  'input': x.tolist(), 'delivered_event_indices': delivered})
            self.next_frame += 50_000
            if frequent:
                self.model.observe()
                self.model.save()
                self.save()


def source_for(work, case):
    return json.loads(gzip.decompress((work/'source-copies'/case['source_id']/'whole.json.gz').read_bytes()))


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered; do not blindly register')
        verification = m.read(SOURCE/'publication/final-verification.json')
        if verification['execution_status'] != 'completed' or verification['coverage'] != 'verified':
            raise RuntimeError('source has no verified completion')
        name = '2026-10-16 机制发现 · M3 C1 五系统开发重放'
        found = [p for p in client.call('projects.list', {}) if p['name'] == name]
        if len(found) > 1:
            raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': name})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-m3-c1-20261016'}
        m.original(work/'platform.json', platform)
        files = [Path(__file__), HERE/'pilot_m2.py', HERE/'pilot-m3-c1.zh.md', HERE/'pilot-m3-c1.en.md',
                 ROOT/'lab/tools/study_lock.py', ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        for p in files:
            m.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        m.original(work/'cases.json', cases())
        originals = {r['path']: r for r in m.read(SOURCE/'originals-manifest-v1.json')['members']}
        source_index = []
        for source_id in dict.fromkeys(c['source_id'] for c in cases()):
            folder = SOURCE/'cases'/source_id
            current = m.read(folder/'current.json')
            path = folder/current['path']
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != current['sha256'] or digest != originals[path.relative_to(SOURCE).as_posix()]['sha256']:
                raise RuntimeError('source whole state is not the verified original')
            whole = json.loads(gzip.decompress(path.read_bytes()))
            copied = m.original(work/'source-copies'/source_id/'whole.json.gz', whole, compressed=True)
            if copied['sha256'] != digest:
                raise RuntimeError('source copy altered original encoding')
            source_index.append({'source_id': source_id, 'path': str(path), 'sha256': digest,
                                 'record': '9c3fa55f-5c9c-5afc-a20c-a809afd16b38', 'new_origin': False})
        m.original(work/'source-index.json', source_index)
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:M3:C1-replay-v1:20261016', 'title': name,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (HERE/'pilot-m3-c1.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'reused_origins': 8, 'new_control_lives': 128,
                                 'new_ThreeMind_subjects': 0, 'other_autonomy_criteria': 'not-tested'}},
                   request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={
            'resource_id': platform['resource_id'], 'target_id': 'managed-research-experiments',
            'relative_path': '2026-10-16-mechanism-discovery/m3-c1-replay-v1',
            'registered_work_path': str(work), 'writer_mode': 'cooperative', 'expected_revision': 0},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={
            'project_id': project['id'], 'resource_id': platform['resource_id']},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M3 C1 replay v1 '+lang,
                    'markdown': (HERE/f'pilot-m3-c1.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps(platform | {'record': r.experiment, 'status': r.status}), flush=True)


def apparatus(work):
    with m.worker_lock(work), m.connection() as client, m.Guard(work):
        m.frozen_check(work)
        if (work/'apparatus.json').exists() or (work/'apparatus-in-flight.json').exists():
            raise RuntimeError('existing apparatus evidence; do not rerun')
        if not m.resource_check(work)['safe']:
            raise RuntimeError('resources insufficient')
        m.original(work/'apparatus-in-flight.json', {'pid': os.getpid(), 'epoch': time.time()})
        case = {'id': 'apparatus', 'seed': 716901, 'history': 0, 'mode': 'H', 'delay': 1, 'cue': 'strong'}
        channels, _ = m.mapping(case['seed'])
        source = {'mappings': channels, 'environment': {'schedule': m.schedule(case, channels)}}
        hashes = {}
        for kind in KINDS:
            hashes[kind] = {}
            for variant in ('plain', 'observed', 'restored', 'paused'):
                if (work/'STOP').exists():
                    raise RuntimeError('apparatus resource STOP; preserve partial evidence')
                c = case | {'kind': kind}
                replay = Replay(c, source)
                replay.advance(10_000_000, frequent=variant == 'observed')
                saved = replay.save()
                m.original(work/'apparatus'/f'{kind}-{variant}-10s.json.gz', saved, compressed=True)
                if variant == 'restored':
                    replay = Replay(c, source, json.loads(m.encoded(saved)))
                if variant == 'paused':
                    time.sleep(.1)
                    if m.digest(replay.save()) != m.digest(saved):
                        raise RuntimeError('wall clock changed baseline state')
                replay.advance(20_000_000, frequent=variant == 'observed')
                final = replay.save()
                m.original(work/'apparatus'/f'{kind}-{variant}-20s.json.gz', final, compressed=True)
                hashes[kind][variant] = m.digest(final)
        report = {'passed': all(len(set(v.values())) == 1 for v in hashes.values()),
                  'whole_state_hashes': hashes, 'included_in_N': False, 'origin': 716901}
        m.original(work/'apparatus.json', report)
        r = m.recorder(work, client)
        r.append('result', 'apparatus', report, request_id=uuid5(NS, 'apparatus'))
        r.synchronize()
        (work/'apparatus-in-flight.json').unlink()
        print(json.dumps(report), flush=True)
        if not report['passed']:
            raise RuntimeError('apparatus failed; preserve evidence')
    m.original(work/'apparatus-resource-summary.json', m.read(work/'resource-summary.json'))


def metrics(rows):
    out = {}
    for name, lower, upper in [('early', 100_000, 300_000), ('late', 500_000, 1_500_000)]:
        values = [r['response'] for r in rows if lower <= r['time_us']-18_000_000 <= upper]
        if len(values) != (5 if name == 'early' else 21):
            raise ValueError('endpoint lattice incomplete')
        out[name] = float(np.mean(values))
    return out


def run(work):
    import psutil
    with m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if not m.read(work/'apparatus.json')['passed']:
            raise RuntimeError('apparatus not accepted')
        if (work/'in-flight.json').exists() or (work/'STOP').exists():
            raise RuntimeError('STOP/orphan marker: preserve; no blind replay')
        r = m.recorder(work, client)
        m.atomic_json(work/'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(),
                      'command': sys.argv, 'epoch': time.time()})
        with m.Guard(work) as guard:
            for case in m.read(work/'cases.json'):
                folder = work/'cases'/case['id']
                if (folder/'result.json').exists():
                    request = uuid5(NS, 'result:'+case['id'])
                    if not (r.control/'receipts'/f'{request}.json').exists():
                        r.append('result', case['id'], m.read(folder/'result.json'), request_id=request)
                    continue
                if (work/'STOP').exists():
                    break
                source = source_for(work, case)
                if (folder/'current.json').exists():
                    current = m.read(folder/'current.json')
                    raw = (folder/current['path']).read_bytes()
                    if hashlib.sha256(raw).hexdigest() != current['sha256']:
                        raise RuntimeError('current full state corrupted')
                    replay = Replay(case, source, json.loads(gzip.decompress(raw)))
                    index = current['index']+1
                else:
                    m.original(work/'in-flight.json', {'case': case, 'operation': 'baseline-init'})
                    replay = Replay(case, source)
                    commit(folder, replay, 0)
                    (work/'in-flight.json').unlink()
                    index = 1
                for target in (10_000_000, 18_000_000, 20_000_000):
                    if replay.next_frame > target:
                        continue
                    if (work/'STOP').exists():
                        break
                    if not guard.thread.is_alive():
                        raise RuntimeError('guard died')
                    m.original(work/'in-flight.json', {'case': case, 'from_frame': replay.next_frame, 'until': target})
                    replay.advance(target)
                    commit(folder, replay, index)
                    (work/'in-flight.json').unlink()
                    index += 1
                if replay.next_frame <= 20_000_000:
                    break
                result = {'case': case, **metrics(replay.rows), 'learning_updates': replay.model.updates,
                          'whole_sha256': m.digest(replay.save())}
                m.original(folder/'result.json', result)
                r.append('result', case['id'], result, request_id=uuid5(NS, 'result:'+case['id']))
                r.synchronize()
                completed = sum((work/'cases'/c['id']/'result.json').exists() for c in cases())
                m.atomic_json(work/'progress.json', {'completed': completed, 'total': 128, 'last': case['id'], 'pending': r.status['pending']})
                print(json.dumps({'completed': completed, 'case': case['id']}), flush=True)
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) >= 4*2**30:
                    m.original(work/'STOP', {'reason': '4GiB original budget'})
                    break
            r.synchronize()
        completed = sum((work/'cases'/c['id']/'result.json').exists() for c in cases())
        m.atomic_json(work/'status.json', {'state': 'awaiting-analysis' if completed == 128 else 'paused',
                      'completed': completed, 'total': 128, 'recorder': r.status})


def commit(folder, replay, index):
    name = f'whole-{index:04d}.json.gz'
    receipt = m.original(folder/name, replay.save(), compressed=True)
    m.atomic_json(folder/'current.json', {'path': name, 'index': index, 'next_frame_us': replay.next_frame, **receipt})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['register', 'apparatus', 'run', 'status', 'check'])
    parser.add_argument('--work', type=Path, default=WORK)
    args = parser.parse_args()
    work = args.work.resolve()
    if args.command == 'status':
        print(json.dumps({n: m.read(work/n) if (work/n).exists() else None for n in
                          ['platform.json', 'apparatus.json', 'host.json', 'progress.json', 'status.json', 'STOP', 'in-flight.json']}))
    elif args.command == 'check':
        print(json.dumps(m.resource_check(work)))
    else:
        {'register': register, 'apparatus': apparatus, 'run': run}[args.command](work)
