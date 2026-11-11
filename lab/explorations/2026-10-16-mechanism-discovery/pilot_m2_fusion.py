"""Prospective receiver-fusion experiment with declared complete causal copies.

Uses existing /5.1 configuration only. No change to production kernels/defaults.
The predictor is deliberately reduced, reads pre-cue evidence and never drives Core.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_m2 as m
from pilot_m1 import differences

WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-fusion-v1')
NS = UUID('3903210b-909f-41f8-bca7-68f53202b6cf')
ARMS = {'normalized': (1.,), 'summed': (0.,), 'double-sham': (1., 1.), 'restored': (0., 1.)}
CUES = {'none': (), 'X-low': (('X', .25),), 'X': (('X', .5),), 'Y': (('Y', .5),),
        'XY-total': (('X', .25), ('Y', .25)), 'XY-per': (('X', .5), ('Y', .5)), 'X-total': (('X', 1.),)}


def parents():
    return [{'id': f'o{o}-h{h}', 'origin': f'fusion-o{o}', 'seed': 917100+o,
             'delay': 15, 'mode': 'S', 'history': h, 'cue': 'none',
             'teaching_intensity': (.25, .35, .45, .55)[o//2]}
            for o in range(8) for h in (0, 1)]


def schedule(case, channels):
    result = m.schedule(case, channels)
    for event in result:
        if event['kind'] == 'teaching':
            event['stimulus']['intensity'] = case['teaching_intensity']
    return result


class Subject(m.Subject):
    def __init__(self, case, saved=None):
        self.case = dict(case)
        if saved is None:
            self.channels, self.rng = m.mapping(case['seed'])
            config = m.Local51Config(seed=case['seed'], energy_seed=case['seed'] ^ 0x1634AB,
                                    consolidation_mode='legacy-stability')
            self.engine = m.create_engine(config, kernel_id=m.KERNEL, backend='native')
            self.events, self.cursor = schedule(case, self.channels), 0
            self.rows, self.actuator, self.branch = [], None, None
        else:
            if saved['schema'] != 'threemind.m2-fusion-whole/1' or saved['case'] != case:
                raise ValueError('whole identity mismatch')
            self.channels, self.rng = saved['mappings'], saved['random_state']
            self.events, self.cursor = saved['environment']['schedule'], saved['input_cursor']
            self.rows, self.actuator, self.branch = saved['recent_activity'], saved['actuators'], saved['branch']
            self.engine = m.create_engine(state=m.StateImage.from_dict(saved['core']), backend='native', kernel_id=m.KERNEL)
        if self.engine.dynamics != m.KERNEL:
            raise RuntimeError('genuine /5.1 required')
        if saved is not None and m.digest(self.save()) != m.digest(saved):
            raise RuntimeError('complete restoration mismatch')

    def save(self):
        result = super().save()
        result['schema'] = 'threemind.m2-fusion-whole/1'
        result['branch'] = self.branch
        return result

    def advance_probe(self, target, *, dense=True, frequent=False):
        for outer in range(self.engine.time_us+50_000, target+1, 50_000):
            while self.cursor < len(self.events) and int(self.events[self.cursor]['stimulus']['time_us']) <= outer:
                self.engine.inject(m.Stimulus.from_dict(self.events[self.cursor]['stimulus']))
                self.cursor += 1
            for t in range(self.engine.time_us+(1000 if dense else 50_000), outer+1, 1000 if dense else 50_000):
                self.engine.advance_to(t)
                if frequent:
                    self.engine.graph()
                    self.engine.metrics()
                    self.engine.capture_state()
                p = m.project(self.engine.observation_nodes(), self.channels)
                self.actuator = p['activation'][0]-p['activation'][1]
                self.rows.append({'time_us': t, 'response': self.actuator, **p})
            if self.engine.life == 'dead':
                raise RuntimeError('new subject death; preserve in-flight and stop')


def fork(parent, cue, arm):
    before = parent.save()
    subject = Subject(parent.case, copy.deepcopy(before))
    # All future stimuli are external, declared interventions, not observations.
    original_prefix = subject.events[:subject.cursor]
    if CUES[cue]:
        payload = m.Stimulus(subject.probe_start, tuple((subject.channels[s], v) for s, v in CUES[cue]), 1.)
        event = {'kind': 'probe', 'stimulus': payload.to_dict()}
        subject.events = subject.events[:subject.cursor]+[event]+subject.events[subject.cursor:]
    if subject.events[:subject.cursor] != original_prefix:
        raise RuntimeError('fork changes past inputs')
    for mix in ARMS[arm]:
        subject.engine.reconfigure(replace(subject.engine.config, context_mix=mix))
    if subject.engine.time_us != parent.engine.time_us:
        raise RuntimeError('configuration changed internal time')
    subject.branch = {'parent_sha256': m.digest(before), 'cue': cue, 'arm': arm,
                      'declared_reconfiguration': list(ARMS[arm])}
    after = subject.save()
    return subject, {'parent_sha256': m.digest(before), 'branch_initial_sha256': m.digest(after),
                     'changed_paths': differences(before, after), 'parent_time_us': parent.engine.time_us,
                     'new_independent_origin': False}


def forecast(graph, channels, cfg, cue, mix):
    """Unfitted long-rest first-arrival approximation, not a second Core engine.

    At 15s rest, fast traces, residual activation/inhibition and depletion are
    approximated by zero/full recovery. Current slow weights are not fitted.
    Per-edge clipping precedes receiver fusion in the mechanistic candidate.
    The alternative sums all predicted arrivals then clips their total.
    """
    nodes = {n['channel']: n['id'] for n in graph['nodes']}
    edges = {(e['source'], e['target']): e['weight'] for e in graph['edges']}
    tau, floor = cfg['activation_tau'], cfg['activation_floor']
    coefficient = cfg['direct_gain']*math.exp(-.1/tau)*cfg['propagation_rate']*.1*cfg['stp_utilization']
    predicted = {'receiver': [], 'total-dose': []}
    for output in 'AB':
        values = [coefficient*v*edges.get((nodes.get(channels[s]), nodes.get(channels[output])), 0.) for s, v in CUES[cue]]
        viable = [a for a in values if a >= floor]
        value = (1.-mix)*sum(viable)+mix*sum(viable)/len(viable) if viable else 0.
        total = sum(values)
        predicted['receiver'].append(value if value >= floor else 0.)
        predicted['total-dose'].append(total if total >= floor else 0.)
    return {'source': 'pre-cue-graph-only', 'coefficient': coefficient,
            'response_at_110ms': {k: v[0]-v[1] for k, v in predicted.items()},
            'isolated_duration_ms': {k: max(0., tau*math.log(max(v)/floor)*1000) if max(v) > 0 else 0.
                                     for k, v in predicted.items()},
            'assumptions': 'long rest; symmetric equal-strength arrivals; first aligned emission; no second pulse; unchanged slow weight over first 100ms'}


def endpoint(saved, prediction):
    start = (17+saved['case']['delay'])*1_000_000
    rows = [r for r in saved['recent_activity'] if r['time_us'] > start]
    first = next(r['response'] for r in rows if r['time_us'] == start+110_000)
    late = [r['response'] for r in rows if 500_000 <= r['time_us']-start <= 1_500_000]
    sign = 1 if saved['case']['history'] == 0 else -1
    return {'case': saved['case'], 'branch': saved['branch'], 'response_110ms': first,
            'history_signed_110ms': sign*first, 'late_mean': sum(late)/len(late),
            'peak_abs': max(abs(r['response']) for r in rows),
            'nonzero_grid_ms': sum(abs(r['response']) > 1e-9 for r in rows),
            'integral_0_500ms': sum(r['response']*.001 for r in rows if r['time_us']-start <= 500_000),
            'grid_frames': len(rows), 'forecast': prediction, 'final_whole_sha256': m.digest(saved)}


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered')
        name = '2026-10-16 机制发现 · M2 接收汇合与门限预测'
        found = [p for p in client.call('projects.list', {}) if p['name'] == name]
        if len(found) > 1:
            raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': name})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-m2-fusion-20261016'}
        m.original(work/'platform.json', platform)
        paths = [Path(__file__), m.HERE/'pilot_m1.py', m.HERE/'pilot_m2.py', m.HERE/'pilot-m2-fusion.zh.md',
                 m.HERE/'pilot-m2-fusion.en.md', m.ROOT/'lab/tools/study_lock.py',
                 m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        m.original(work/'parents.json', parents())
        for p in paths:
            m.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:M2:fusion-v1:20261016', 'title': name,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (m.HERE/'pilot-m2-fusion.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'new_independent_origins': 8, 'parents': 16,
                                 'causal_copies': 448, 'core_code_changed': False, 'E69_resumed': False}}, request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={
            'resource_id': platform['resource_id'], 'target_id': 'managed-research-experiments',
            'relative_path': '2026-10-16-mechanism-discovery/m2-fusion-v1', 'registered_work_path': str(work),
            'writer_mode': 'cooperative', 'expected_revision': 0}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={
            'project_id': project['id'], 'resource_id': platform['resource_id']}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M2 receiver fusion pilot '+lang,
                    'markdown': (m.HERE/f'pilot-m2-fusion.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(m.encoded(platform | {'record': r.experiment, 'status': r.status}).decode(), flush=True)


def apparatus(work):
    with m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if (work/'apparatus.json').exists() or (work/'apparatus-in-flight.json').exists():
            raise RuntimeError('apparatus exists/incomplete; no blind rerun')
        m.resource_check(work)
        m.original(work/'apparatus-in-flight.json', {'time': time.time(), 'pid': os.getpid()})
        r = m.recorder(work, client)
        case = dict(parents()[0], id='apparatus', origin='apparatus', seed=917001, delay=1, teaching_intensity=.4)
        parent = Subject(case)
        parent.advance(parent.probe_start)
        pre = parent.save()
        m.original(work/'apparatus/parent.json.gz', pre, compressed=True)
        hashes, audits = {}, {}
        for arm in ARMS:
            for mode in ('plain', 'observed', 'restored', 'paused'):
                branch, audit = fork(parent, 'XY-per', arm)
                branch.advance_probe(branch.probe_start+1_000_000, frequent=mode == 'observed')
                mid = branch.save()
                m.original(work/'apparatus'/f'{arm}-{mode}-mid.json.gz', mid, compressed=True)
                if mode == 'restored':
                    branch = Subject(case, json.loads(gzip.decompress((work/'apparatus'/f'{arm}-{mode}-mid.json.gz').read_bytes())))
                if mode == 'paused':
                    time.sleep(.1)
                    if m.digest(branch.save()) != m.digest(mid):
                        raise RuntimeError('wall clock changed state')
                branch.advance_probe(branch.probe_start+2_000_000, frequent=mode == 'observed')
                final = branch.save()
                m.original(work/'apparatus'/f'{arm}-{mode}-final.json.gz', final, compressed=True)
                hashes.setdefault(arm, {})[mode] = m.digest(final)
                audits[arm] = audit
        normalized, _ = fork(parent, 'XY-per', 'normalized')
        summed, _ = fork(parent, 'XY-per', 'summed')
        a, b = normalized.save(), summed.save()
        a.pop('branch'); b.pop('branch')
        delta = differences(a, b)
        restored, _ = fork(parent, 'XY-per', 'restored')
        sham, _ = fork(parent, 'XY-per', 'double-sham')
        a, b = restored.save(), sham.save()
        a.pop('branch'); b.pop('branch')
        reversed_exact = m.digest(a) == m.digest(b)
        report = {'schema': 'threemind.m2-fusion-apparatus/1', 'passed': all(len(set(v.values())) == 1 for v in hashes.values())
                  and delta == ['core.config.context_mix'] and reversed_exact,
                  'whole_state_hashes': hashes, 'between_arms_initial_changes': delta,
                  'restore_double_sham_exact_except_branch': reversed_exact, 'reconfigure_audits': audits,
                  'new_scientific_origin': False, 'seed': 917001}
        m.original(work/'apparatus.json', report)
        r.append('result', 'apparatus', report, request_id=uuid5(NS, 'apparatus'))
        r.synchronize()
        if not report['passed']:
            raise RuntimeError('apparatus mismatch; preserve marker')
        (work/'apparatus-in-flight.json').unlink()
        print(m.encoded(report).decode(), flush=True)


def load(path):
    return m.read(path) if path.suffix != '.gz' else json.loads(gzip.decompress(path.read_bytes()))


def run(work):
    import psutil
    with m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if not m.read(work/'apparatus.json')['passed'] or any((work/n).exists() for n in ['STOP', 'in-flight.json', 'apparatus-in-flight.json']):
            raise RuntimeError('unresolved stop or apparatus')
        r = m.recorder(work, client)
        m.atomic_json(work/'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(), 'command': sys.argv})
        completed = 0
        with m.Guard(work) as guard:
            for case in m.read(work/'parents.json'):
                folder = work/'parents'/case['id']
                if (work/'STOP').exists():
                    break
                if (folder/'current.json').exists():
                    current = m.read(folder/'current.json')
                    path = folder/current['path']
                    if hashlib.sha256(path.read_bytes()).hexdigest() != current['sha256']:
                        raise RuntimeError('current parent hash mismatch')
                    parent, index = Subject(case, load(path)), current['index']+1
                else:
                    m.original(work/'in-flight.json', {'case': case, 'operation': 'birth'})
                    parent, index = Subject(case), 0
                    m.commit_subject(folder, parent, index)
                    (work/'in-flight.json').unlink()
                    index += 1
                while parent.engine.time_us < parent.probe_start:
                    if (work/'STOP').exists():
                        break
                    if not guard.thread.is_alive():
                        raise RuntimeError('resource guard died')
                    target = min(parent.probe_start, parent.engine.time_us+10_000_000)
                    m.original(work/'in-flight.json', {'case': case, 'operation': 'continuous-parent', 'from_us': parent.engine.time_us, 'to_us': target})
                    parent.advance(target)
                    if parent.engine.life == 'dead':
                        raise RuntimeError('new parent death; preserve incomplete state')
                    m.commit_subject(folder, parent, index)
                    (work/'in-flight.json').unlink()
                    index += 1
                if parent.engine.time_us != parent.probe_start:
                    break
                graph, cfg = parent.engine.graph(), parent.engine.config.to_dict()
                m.original(folder/'pre-cue-graph.json.gz', graph, compressed=True)
                # Every forecast is saved before any child cue is delivered.
                forecasts = {cue: {arm: forecast(graph, parent.channels, cfg, cue, ARMS[arm][-1]) for arm in ARMS} for cue in CUES}
                m.original(folder/'forecasts.json', forecasts)
                for cue in CUES:
                    for arm in ARMS:
                        out = work/'cases'/f'{case["id"]}-{cue}-{arm}'
                        request = uuid5(NS, 'result:'+out.name)
                        if (out/'result.json').exists():
                            if not (r.control/'receipts'/f'{request}.json').exists():
                                r.append('result', out.name, m.read(out/'result.json'), request_id=request)
                            completed += 1
                            continue
                        if (work/'STOP').exists():
                            break
                        if not guard.thread.is_alive():
                            raise RuntimeError('resource guard died')
                        m.original(work/'in-flight.json', {'case': case, 'cue': cue, 'arm': arm, 'operation': 'registered-causal-copy', 'parent_sha256': m.digest(parent.save())})
                        child, audit = fork(parent, cue, arm)
                        m.original(out/'initial-whole.json.gz', child.save(), compressed=True)
                        m.original(out/'lineage.json', audit)
                        child.advance_probe(child.probe_start+2_000_000)
                        final = child.save()
                        m.original(out/'final-whole.json.gz', final, compressed=True)
                        result = endpoint(final, forecasts[cue][arm])
                        m.original(out/'result.json', result)
                        r.append('result', out.name, result, request_id=request)
                        r.synchronize()
                        (work/'in-flight.json').unlink()
                        completed += 1
                        m.atomic_json(work/'progress.json', {'completed': completed, 'total': 448, 'last': out.name, 'pending': r.status['pending']})
                        print(m.encoded({'completed': completed, 'case': out.name, 'at110': result['response_110ms']}).decode(), flush=True)
                        if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) >= 4*2**30:
                            m.original(work/'STOP', {'reason': '4GiB original budget'})
                            break
                    if (work/'STOP').exists():
                        break
            r.synchronize()
        m.atomic_json(work/'status.json', {'state': 'awaiting-analysis' if completed == 448 else 'paused',
                      'completed': completed, 'total': 448, 'recorder': r.status})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['register', 'apparatus', 'run', 'status', 'check'])
    parser.add_argument('--work', type=Path, default=WORK)
    args = parser.parse_args()
    work = args.work.resolve()
    if args.command == 'status':
        print(m.encoded({n: m.read(work/n) if (work/n).exists() else None for n in
                        ['platform.json', 'apparatus.json', 'host.json', 'progress.json', 'status.json', 'STOP', 'in-flight.json']}).decode())
    elif args.command == 'check':
        print(m.encoded(m.resource_check(work)).decode())
    else:
        {'register': register, 'apparatus': apparatus, 'run': run}[args.command](work)
