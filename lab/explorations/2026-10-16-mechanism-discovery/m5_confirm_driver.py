"""Independent 48-origin M5 confirmation. Old exploration code and originals are immutable."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid5

import m5_rig as g
import m5_confirm_spec as spec
import pilot_m2 as m

HERE = Path(__file__).resolve().parent
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m5-confirmation-v1')
NS = UUID('8d2e6fe0-3344-4711-b6f1-f14c5ce8a1b0')
ARMS = ('sham', 'target', 'matched', 'restored', 'plasticity-off')


def save(folder, name, subject):
    path = folder/(name+'.json.gz')
    return {'path': path.name, **m.original(path, subject.save(), compressed=True)}


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered; inspect, do not retry blindly')
        title = '2026-10-16 机制发现 · M5 新来源新条件机制确认'
        found = [p for p in client.call('projects.list', {}) if p['name'] == title]
        if len(found) > 1:
            raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': title})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-m5-confirmation-v1-20261016'}
        m.original(work/'platform.json', platform)
        paths = [Path(__file__), HERE/'m5_rig.py', HERE/'m5_analyze.py', HERE/'m5_confirm_spec.py', HERE/'m5_confirm_analyze.py',
                 HERE/'m5_confirm_audit.py', HERE/'m5-confirmation-power.json', HERE/'m5-confirmation-protocol.zh.md',
                 HERE/'m5-confirmation-protocol.en.md', HERE/'pilot_m2.py', HERE/'pilot_m1.py', m.ROOT/'lab/tools/study_lock.py',
                 m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        for p in paths:
            m.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        m.original(work/'cases.json', spec.cases())
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:m5-confirmation-v1:20261016', 'title': title,
                    'classification': 'formal', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (HERE/'m5-confirmation-protocol.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'independent_origins': spec.N, 'study_phase': 'confirmation', 'Core_changed': False,
                                 'E69_resumed': False, 'reader_comparison': 'all-activity versus declared output ports'}},
                   request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={'resource_id': platform['resource_id'],
            'target_id': 'managed-research-experiments', 'relative_path': '2026-10-16-mechanism-discovery/m5-confirmation-v1',
            'registered_work_path': str(work), 'writer_mode': 'cooperative', 'expected_revision': 0},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={'project_id': project['id'],
            'resource_id': platform['resource_id']}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M5 independent confirmation v1 '+lang,
                    'markdown': (HERE/f'm5-confirmation-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps(platform | {'record': r.experiment, 'status': r.status}), flush=True)


def measured_exam(subject, folder, prefix, history, dose=.8, observed=False):
    rows = []
    cues = list(zip(g.NEW, g.OLD))
    if subject.seed % 2:
        cues = cues[::-1]
    for pair in cues:
        for cue in pair:
            row = g.question(subject, cue, dose, observed)
            row.update(label=g.label(cue, history), group='new' if cue in g.NEW else 'old')
            row['checkpoint'] = save(folder, f'{prefix}-q{len(rows):02d}', subject)
            rows.append(row)
    return rows


def unit(folder, origin):
    case = spec.cases()[origin]
    p = g.Subject(case['seed'])
    p.tick(0, [{'K': .2}])
    save(folder, 'birth', p)
    calibration = g.calibrate(p)
    save(folder, 'old-calibrated', p)
    early = measured_exam(p, folder, 'early', 0, case['dose'])
    save(folder, 'parent-before-new-teaching', p)
    histories = []
    for history in (0, 1):
        cases = {}
        for enabled in (True, False):
            learner = p.fork(f'h{history}-plasticity-{enabled}')
            config_receipt = g.plasticity(learner, enabled)
            save(folder, f'h{history}-plasticity-{enabled}-start', learner)
            teaching = g.teach(learner, history)
            learner.advance(learner.time+case['delay_s']*1_000_000)
            teaching['registered_post_teaching_delay_s'] = case['delay_s']
            save(folder, f'h{history}-plasticity-{enabled}-taught', learner)
            for arm in ('sham', 'target', 'matched', 'restored') if enabled else ('plasticity-off',):
                child = learner.fork(arm)
                receipt = g.mask(child, arm)
                save(folder, f'h{history}-{arm}-initial', child)
                rows = measured_exam(child, folder, f'h{history}-{arm}', history, case['dose'])
                cases[arm] = {'rows': rows, 'mask': receipt, 'teaching': teaching, 'configuration': config_receipt}
                if arm == 'sham':
                    # Registered research copies: same final Core, original normal equations retained.
                    r0 = {'full': child.reader.save(), 'ports': child.port_reader.save()}
                    training = [r for r in rows if r['group'] == 'new']
                    fitted = child.fork('continued-personal-reader')
                    fitted.reader.learn([{'features': r['features'], 'label': r['label']} for r in training])
                    fitted.port_reader.learn([{'features': r['port_features'], 'label': r['label']} for r in training])
                    r1 = {'full': fitted.reader.save(), 'ports': fitted.port_reader.save()}
                    save(folder, f'h{history}-continued-reader-start', fitted)
                    fixed = child.fork('fixed-reader-heldout')
                    save(folder, f'h{history}-fixed-heldout-start', fixed)
                    heldout = {}
                    for name, life in (('fixed', fixed), ('continued', fitted)):
                        heldout[name] = []
                        for dose in spec.HELDOUT_DOSES:
                            heldout[name] += measured_exam(life, folder, f'h{history}-heldout-{name}-{dose}', history, dose)
                    cases[arm].update(readers_before=r0, readers_after=r1, heldout=heldout,
                                      heldout_core_equal=fixed.save()['core'] == fitted.save()['core'])
        histories.append({'history': history, 'cases': cases})
    result = {'package': 'M5-confirmation', 'case': case, 'origin': origin, 'seed': p.seed, 'calibration': calibration,
              'early': early, 'histories': histories}
    result['integrity_valid'] = all(h['cases']['sham']['heldout_core_equal'] for h in histories)
    result['matching_valid'] = all(h['cases']['sham']['mask']['matching_valid']
                                  and h['cases']['sham']['teaching']['old_new_activity_residual'] <= .02 for h in histories)
    result['valid'] = result['integrity_valid'] and result['matching_valid']
    return result


def apparatus(work):
    with m.worker_lock(work):
        m.frozen_check(work); m.resource_check(work)
        if any((work/x).exists() for x in ('apparatus.json', 'apparatus-in-flight.json')):
            raise RuntimeError('apparatus already attempted')
        m.original(work/'apparatus-in-flight.json', {'pid': os.getpid(), 'epoch': time.time()})
        root = work/'apparatus'
        p = g.Subject(spec.APPARATUS_SEED); p.tick(0, [{'K': .2}]); g.calibrate(p)
        before = p.save(); save(root, 'parent', p)
        hashes = {}
        for mode in ('plain', 'observed', 'restored', 'paused'):
            c = g.Subject.restore(before)
            g.question(c, 'UV', .74, observed=mode == 'observed')
            c.advance(c.time+5_000_000, observed=mode == 'observed')
            if mode == 'restored':
                c = g.Subject.restore(c.save())
            if mode == 'paused':
                state = c.save(); time.sleep(.03)
                if state != c.save():
                    raise RuntimeError('wall-clock mutation')
            g.question(c, 'ZW', .94, observed=mode == 'observed')
            hashes[mode] = m.digest(c.save()); save(root, mode, c)
        c = g.Subject.restore(before)
        early = g.exam(c, 0); g.plasticity(c, True)
        stats = g.teach(c, 0); save(root, 'taught', c)
        masks = {}
        for arm in ('sham', 'target', 'matched', 'restored'):
            d = c.fork(arm); masks[arm] = g.mask(d, arm); save(root, 'mask-'+arm, d)
        # No scientific source participates; response signs do not gate apparatus acceptance.
        report = {'schema': 'threemind.m5-confirmation-apparatus/1', 'scientific_N': 0, 'seed': spec.APPARATUS_SEED,
                  'hashes': hashes, 'masks': masks, 'old_new_activity_residual': stats['old_new_activity_residual'],
                  'old_calibration_counts': {key: sum(r[key]['answer'] == r['label'] for r in early if r['group'] == 'old')
                                             for key in ('response', 'port_response')},
                  'passed': len(set(hashes.values())) == 1 and all(r['matching_valid'] for r in masks.values())
                            and stats['old_new_activity_residual'] <= .02}
        m.original(work/'apparatus.json', report)
        if not report['passed']:
            raise RuntimeError('apparatus failed; preserve marker')
        (work/'apparatus-in-flight.json').unlink()
        print(json.dumps(report), flush=True)


def run(work):
    import psutil
    with m.worker_lock(m.DEFAULT_WORK), m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if any((work/x).exists() for x in ('STOP', 'in-flight.json', 'apparatus-in-flight.json')):
            raise RuntimeError('unresolved marker; do not restart')
        if not m.read(work/'apparatus.json')['passed']:
            raise RuntimeError('apparatus not passed')
        if (work/'status.json').exists():
            raise RuntimeError('already attempted; use explicit current-boundary review')
        m.atomic_json(work/'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(), 'command': sys.argv})
        recorder = m.recorder(work, client)
        done = 0
        with m.Guard(work) as guard:
            for origin in range(spec.N):
                if (work/'STOP').exists():
                    break
                if not guard.thread.is_alive():
                    raise RuntimeError('resource guard absent')
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > 8*2**30:
                    m.original(work/'STOP', {'reason': '8GiB original cap'}); break
                name = f'o{origin}'
                m.original(work/'in-flight.json', {'unit': name, 'pid': os.getpid(), 'epoch': time.time()})
                folder = work/'units'/name
                result = unit(folder, origin)
                m.original(folder/'result.json', result)
                (work/'in-flight.json').unlink()
                done += 1
                m.atomic_json(work/'progress.json', {'completed': done, 'total': spec.N, 'last': name, 'epoch': time.time()})
                recorder.append('result', name, {'unit': name, 'package': 'M5-confirmation', 'valid': result['valid'],
                    'sha256': hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()}, request_id=uuid5(NS, 'result:'+name))
                recorder.synchronize()
                print(json.dumps({'completed': done, 'total': spec.N, 'pending': recorder.status['pending']}), flush=True)
                if not result['valid']:
                    m.original(work/'STOP', {'reason': 'measurement validity failure', 'unit': name})
                    break
        m.atomic_json(work/'status.json', {'state': 'awaiting-analysis' if done == spec.N else 'resource-paused', 'completed': done, 'total': spec.N})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('register', 'apparatus', 'run', 'check', 'status'))
    parser.add_argument('--work', type=Path, default=WORK)
    args = parser.parse_args(); work = args.work.resolve()
    if args.command == 'check':
        print(json.dumps(m.resource_check(work)))
    elif args.command == 'status':
        print(json.dumps({n: m.read(work/n) if (work/n).exists() else None for n in
                          ('platform.json', 'host.json', 'progress.json', 'status.json', 'STOP', 'in-flight.json', 'resource-summary.json')}))
    else:
        {'register': register, 'apparatus': apparatus, 'run': run}[args.command](work)
