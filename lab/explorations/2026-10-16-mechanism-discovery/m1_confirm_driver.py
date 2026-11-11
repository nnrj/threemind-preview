"""Independent 48-origin M1 confirmation. Old exploration code and originals are immutable."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid5

import closure_rig as g
import m1_confirm_probe as probe
import copy
import m1_confirm_spec as spec
import pilot_m2 as m

HERE = Path(__file__).resolve().parent
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m1-confirmation-v1')
NS = UUID('3bf3bbca-3b8e-4500-a84b-d7bffb842bf5')
ARMS = spec.ARMS


def save(folder, name, subject):
    path = folder/(name+'.json.gz')
    return {'path': path.name, **m.original(path, subject.save(), compressed=True)}


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered; inspect, do not retry blindly')
        title = '2026-10-16 机制发现 · M1 局部经历与选择转移独立确认'
        found = [p for p in client.call('projects.list', {}) if p['name'] == title]
        if len(found) > 1:
            raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': title})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-m1-confirmation-v1-20261016'}
        m.original(work/'platform.json', platform)
        paths = [Path(__file__), HERE/'m1_confirm_spec.py', HERE/'m1_confirm_probe.py',
                 HERE/'m1_confirm_analyze.py', HERE/'m1_confirm_audit.py', HERE/'m1-confirmation-power.json',
                 HERE/'m1-confirmation-protocol.zh.md', HERE/'m1-confirmation-protocol.en.md',
                 HERE/'closure_rig.py', HERE/'closure_audit.py', HERE/'pilot_m3.py',
                 HERE/'m5_confirm_analyze.py', HERE/'m5_confirm_spec.py', HERE/'m5_analyze.py',
                 HERE/'pilot_m2.py', HERE/'pilot_m1.py', m.ROOT/'lab/tools/study_lock.py',
                 m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        for p in paths:
            m.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        m.original(work/'cases.json', spec.cases())
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:m1-confirmation-v1:20261016', 'title': title,
                    'classification': 'formal', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (HERE/'m1-confirmation-protocol.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'independent_origins': spec.N, 'study_phase': 'confirmation', 'Core_changed': False,
                                 'E69_resumed': False, 'reader': 'fixed personal output-port difference; no refitting'}},
                   request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={'resource_id': platform['resource_id'],
            'target_id': 'managed-research-experiments', 'relative_path': '2026-10-16-mechanism-discovery/m1-confirmation-v1',
            'registered_work_path': str(work), 'writer_mode': 'cooperative', 'expected_revision': 0},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={'project_id': project['id'],
            'resource_id': platform['resource_id']}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M1 independent confirmation v1 '+lang,
                    'markdown': (HERE/f'm1-confirmation-protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps(platform | {'record': r.experiment, 'status': r.status}), flush=True)


def unit(folder, origin):
    case = spec.cases()[origin]
    parents, matches = {}, {}
    for history in (0, 1):
        parent = g.Rig('threemind', case['seed'])
        save(folder, f'birth-h{history}', parent)
        records = g.teaching(parent, history, case['teaching_dose'], delay=case['delay_s'])
        save(folder, f'parent-h{history}-before-settlement', parent)
        g.settle(parent)
        save(folder, f'parent-h{history}', parent)
        parents[history] = parent
        matches[history] = g.matching(parent, records)
        m.original(folder/f'teaching-observation-h{history}.json', records)
    m.original(folder/'matching.json', matches)
    valid = all(x['passed'] for x in matches.values())
    result = {'package': 'M1-confirmation', 'origin': origin, 'seed': case['seed'], 'case': case,
              'valid': valid, 'matching': matches, 'trials': []}
    if not valid:
        return result
    for history in (0, 1):
        parent, donor = parents[history], parents[1-history]
        for arm in spec.ARMS:
            if arm == 'intact': child, receipt = parent.fork(arm), {'arm': arm}
            elif arm == 'sham': child, receipt = g.transfer(parent, parent)
            elif arm == 'matched-bundle': child, receipt = g.transfer(parent, donor, 'ZW')
            else:
                child, receipt = g.transfer(parent, donor, mode=arm if arm in ('persistent', 'fast') else 'bundle')
                if arm == 'restored': child, _ = g.transfer(child, parent)
            comparable = copy.deepcopy(child.save()); comparable['branch'] = parent.branch
            if arm in ('intact', 'sham', 'restored') and comparable != parent.save():
                raise RuntimeError('sham/reversal differs from intact whole state')
            m.original(folder/f'h{history}-{arm}-intervention.json', receipt)
            save(folder, f'h{history}-{arm}-initial', child)
            for cue in spec.CUES:
                # Preregistered causal diagnostic copies at a common intervention boundary.
                # These are not ordinary per-question student restorations.
                subject = child.fork(cue)
                outcome = probe.probe(subject, cue)
                checkpoint = save(folder, f'h{history}-{arm}-{cue}-final', subject)
                goal = -1 if history == 0 else 1
                result['trials'].append({'history': history, 'arm': arm, 'cue': cue, 'goal': goal,
                                        'success': outcome['choice'] == goal,
                                        'final_success': outcome['final_gate'] == goal,
                                        'result': outcome, 'checkpoint': checkpoint})
    return result


def apparatus(work):
    with m.worker_lock(work):
        m.frozen_check(work); m.resource_check(work)
        if any((work/x).exists() for x in ('apparatus.json', 'apparatus-in-flight.json')):
            raise RuntimeError('apparatus already attempted; preserve originals')
        m.original(work/'apparatus-in-flight.json', {'pid': os.getpid(), 'epoch': time.time()})
        root = work/'apparatus'
        parents, matches = {}, {}
        for history in (0, 1):
            parent = g.Rig('threemind', spec.APPARATUS_SEED)
            records = g.teaching(parent, history, .42, delay=2)
            g.settle(parent); save(root, f'parent-h{history}', parent)
            parents[history] = parent; matches[history] = g.matching(parent, records)
        hashes = {}
        for mode in ('plain', 'observed', 'restored', 'paused'):
            child = g.Rig.restore(parents[0].save())
            probe.probe(child, 'XN', observed=mode == 'observed', restore_mid=mode == 'restored',
                        pause_mid=mode == 'paused')
            hashes[mode] = m.digest(child.save()); save(root, mode, child)
        sham, _ = g.transfer(parents[0], parents[0])
        changed, receipt = g.transfer(parents[0], parents[1])
        reversed_subject, _ = g.transfer(changed, parents[0])
        valid = (len(set(hashes.values())) == 1 and all(x['passed'] for x in matches.values())
                 and sham.save() == parents[0].save() and reversed_subject.save() == parents[0].save()
                 and set(receipt['changed_paths']) <= {'model.edges', 'model.timers'})
        report = {'schema': 'threemind.m1-confirmation-apparatus/1', 'scientific_N': 0,
                  'seed': spec.APPARATUS_SEED, 'hashes': hashes, 'matching': matches, 'passed': valid,
                  'transfer_changed_paths': receipt['changed_paths']}
        m.original(work/'apparatus.json', report)
        if not valid: raise RuntimeError('apparatus failed; preserve marker')
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
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > 4*2**30:
                    m.original(work/'STOP', {'reason': '4GiB original cap'}); break
                name = f'o{origin}'
                m.original(work/'in-flight.json', {'unit': name, 'pid': os.getpid(), 'epoch': time.time()})
                folder = work/'units'/name
                result = unit(folder, origin)
                m.original(folder/'result.json', result)
                (work/'in-flight.json').unlink()
                done += 1
                m.atomic_json(work/'progress.json', {'completed': done, 'total': spec.N, 'last': name, 'epoch': time.time()})
                recorder.append('result', name, {'unit': name, 'package': 'M1-confirmation', 'valid': result['valid'],
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
