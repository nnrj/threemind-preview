"""Explicit instrument copies; exact whole-state equivalence gates dense readings."""
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_m2 as m

WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-sampling-calibration-v1')
NS = UUID('bfc33172-0532-432a-93be-01700923d90a')


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def dense_replay(pre, final_time):
    subject = m.Subject(pre['case'], pre)
    dense = []
    # Inject at the same outer boundary as the frozen host; no input from observer.
    for target in range(subject.engine.time_us+50_000, final_time+1, 50_000):
        while subject.cursor < len(subject.events) and int(subject.events[subject.cursor]['stimulus']['time_us']) <= target:
            subject.engine.inject(m.Stimulus.from_dict(subject.events[subject.cursor]['stimulus']))
            subject.cursor += 1
        for t in range(subject.engine.time_us+1000, target+1, 1000):
            subject.engine.advance_to(t)  # Declared replay advancement, not an observation side effect.
            projected = m.project(subject.engine.observation_nodes(), subject.channels)
            response = projected['activation'][0]-projected['activation'][1]
            dense.append({'time_us': t, 'response': response, **projected})
        subject.actuator = response
        subject.rows.append({'time_us': target, 'response': response, **projected})
    return subject.save(), dense


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered')
        source = m.DEFAULT_WORK
        verified = m.read(source/'publication/final-verification.json')
        if verified['coverage'] != 'verified' or verified['execution_status'] != 'completed':
            raise RuntimeError('source publication not verified')
        analysis = m.read(source/'analysis-v1.json')
        selected = [r['case'] for r in analysis['observations'] if r['peak_abs'] <= 1e-9 and r['peak_assoc'] > 0]
        selected += [next(r['case'] for r in analysis['observations'] if r['case']['id'] == 'd1-o0-H-h0-strong')]
        source_manifest = {r['path']: r for r in m.read(source/'originals-manifest-v1.json')['members']}
        index = []
        for case in selected:
            folder = source/'cases'/case['id']
            current = m.read(folder/'current.json')
            final_path = folder/current['path']
            final = load(final_path)
            start = (17+case['delay'])*1_000_000
            candidates = [(p, load(p)) for p in folder.glob('whole-*.json.gz')]
            pre_path, pre = next((p, w) for p, w in candidates if int(w['core']['time_us']) == start)
            source_files = []
            for path, value, role in [(pre_path, pre, 'pre'), (final_path, final, 'original-final')]:
                sha = hashlib.sha256(path.read_bytes()).hexdigest()
                if sha != source_manifest[path.relative_to(source).as_posix()]['sha256']:
                    raise RuntimeError('source hash differs from verified original')
                receipt = m.original(work/'cases'/case['id']/f'{role}.json.gz', value, compressed=True)
                if receipt['sha256'] != sha:
                    raise RuntimeError('copied encoding differs')
                source_files.append({'role': role, 'path': str(path), 'sha256': sha})
            index.append({'case': case, 'files': source_files, 'new_independent_origin': False})
        m.original(work/'source-index.json', index)
        m.original(work/'cases.json', selected)
        name = '2026-10-16 机制发现 · M2 采样仪器校准'
        found = [p for p in client.call('projects.list', {}) if p['name'] == name]
        if len(found) > 1:
            raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': name})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-m2-sampling-20261016'}
        m.original(work/'platform.json', platform)
        paths = [Path(__file__), m.HERE/'pilot_m2.py', m.HERE/'sampling-calibration.zh.md', m.HERE/'sampling-calibration.en.md',
                 m.ROOT/'lab/tools/study_lock.py', m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        for p in paths:
            m.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:M2:sampling-calibration-v1:20261016', 'title': name,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (m.HERE/'sampling-calibration.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'instrument_replay_copies': len(selected), 'new_origins': 0,
                                 'student_scores_changed': False}}, request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={
            'resource_id': platform['resource_id'], 'target_id': 'managed-research-experiments',
            'relative_path': '2026-10-16-mechanism-discovery/m2-sampling-calibration-v1',
            'registered_work_path': str(work), 'writer_mode': 'cooperative', 'expected_revision': 0},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={
            'project_id': project['id'], 'resource_id': platform['resource_id']},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M2 sampling calibration '+lang,
                    'markdown': (m.HERE/f'sampling-calibration.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps(platform | {'record': r.experiment, 'copies': len(selected), 'status': r.status}), flush=True)


def run(work):
    import psutil
    with m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if any((work/n).exists() for n in ['STOP', 'in-flight.json']):
            raise RuntimeError('STOP or orphan marker; preserve')
        r = m.recorder(work, client)
        m.atomic_json(work/'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(),
                      'command': sys.argv, 'epoch': time.time()})
        cases = m.read(work/'cases.json')
        source_index = {r['case']['id']: r['files'] for r in m.read(work/'source-index.json')}
        with m.Guard(work) as guard:
            for case in cases:
                folder = work/'cases'/case['id']
                request = uuid5(NS, 'result:'+case['id'])
                if (folder/'result.json').exists():
                    if not (r.control/'receipts'/f'{request}.json').exists():
                        r.append('result', case['id'], m.read(folder/'result.json'), request_id=request)
                    continue
                if (work/'STOP').exists():
                    break
                if not guard.thread.is_alive():
                    raise RuntimeError('guard died')
                for entry in source_index[case['id']]:
                    path = folder/(entry['role']+'.json.gz')
                    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                        raise RuntimeError('copied calibration parent changed')
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) >= 4*2**30:
                    m.original(work/'STOP', {'reason': '4GiB original budget'})
                    break
                pre, expected = load(folder/'pre.json.gz'), load(folder/'original-final.json.gz')
                m.original(work/'in-flight.json', {'case': case, 'operation': 'instrument-replay', 'parent_time_us': pre['core']['time_us']})
                actual, dense = dense_replay(pre, int(expected['core']['time_us']))
                m.original(folder/'dense-final.json.gz', actual, compressed=True)
                m.original(folder/'dense-rows.json.gz', dense, compressed=True)
                same = m.digest(actual) == m.digest(expected)
                result = {'case': case, 'exact_original_final_whole': same,
                          'original_peak_abs': max(abs(r['response']) for r in expected['recent_activity']),
                          'dense_peak_abs': max(abs(r['response']) for r in dense), 'frames': len(dense),
                          'original_sha256': m.digest(expected), 'dense_sha256': m.digest(actual),
                          'energy_simulation_enabled': expected['core']['config']['energy_simulation_enabled']}
                m.original(folder/'result.json', result)
                r.append('result', case['id'], result, request_id=request)
                r.synchronize()
                if not same:
                    m.original(work/'STOP', {'reason': 'instrument whole-state mismatch', 'case': case['id']})
                    raise RuntimeError('dense observation changed final state; preserve in-flight; do not use readings')
                (work/'in-flight.json').unlink()
                completed = sum((work/'cases'/c['id']/'result.json').exists() for c in cases)
                m.atomic_json(work/'progress.json', {'completed': completed, 'total': len(cases), 'last': case['id'], 'pending': r.status['pending']})
                print(json.dumps(result), flush=True)
            r.synchronize()
        count = sum((work/'cases'/c['id']/'result.json').exists() for c in cases)
        m.atomic_json(work/'status.json', {'state': 'awaiting-analysis' if count == len(cases) else 'paused',
                      'completed': count, 'total': len(cases), 'recorder': r.status})


def analyze(work):
    if (work/'STOP').exists() or (work/'in-flight.json').exists():
        raise RuntimeError('unresolved calibration')
    cases, rows = m.read(work/'cases.json'), []
    for case in cases:
        folder = work/'cases'/case['id']
        original, actual = load(folder/'original-final.json.gz'), load(folder/'dense-final.json.gz')
        dense = load(folder/'dense-rows.json.gz')
        if m.digest(original) != m.digest(actual) or len(dense) != 2000:
            raise ValueError('whole equivalence or measurement grid failed')
        start = (17+case['delay'])*1_000_000
        peak = max(dense, key=lambda r: abs(r['response']))
        positive = [r['time_us']-start for r in dense if abs(r['response']) > 1e-9]
        cfg = original['core']['config']
        height = abs(peak['response'])
        rows.append({'case': case, 'peak': height, 'peak_relative_us': peak['time_us']-start,
                     'original_peak': max(abs(r['response']) for r in original['recent_activity']),
                     'first_nonzero_us': min(positive) if positive else None,
                     'last_nonzero_us': max(positive) if positive else None,
                     'nonzero_grid_points': len(positive),
                     'isolated_peak_decay_to_floor_s': cfg['activation_tau']*math.log(height/cfg['activation_floor']) if height > 0 else None,
                     'whole_state_exact': True, 'energy_simulation_enabled': cfg['energy_simulation_enabled']})
    result = {'schema': 'threemind.sampling-calibration/1', 'instrument_copies': len(cases), 'new_independent_origins': 0,
              'whole_final_exact_count': len(rows), 'missed_original_zero_cases': sum(r['original_peak'] <= 1e-9 and r['peak'] > 1e-9 for r in rows),
              'rows': rows, 'interpretation': 'Additional instrument readings do not replace registered endpoints or turn unread original answers into correct scores.'}
    m.original(work/'analysis-v1.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['register', 'run', 'analyze'])
    parser.add_argument('--work', type=Path, default=WORK)
    args = parser.parse_args()
    {'register': register, 'run': run, 'analyze': analyze}[args.command](args.work.resolve())
