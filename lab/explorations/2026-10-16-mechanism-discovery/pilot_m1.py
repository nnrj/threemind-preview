"""Bounded /5.1 edge-mask experiment; explicit causal copies, no kernel edits."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from uuid import UUID, uuid5

import pilot_m2 as base

HERE = Path(__file__).resolve().parent
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m1-silence-v1')
NS = UUID('10deff8a-e411-44d7-ac9b-189122dd9365')
ARMS = ('intact', 'sham', 'target', 'matched', 'restored')


def parents():
    return [{'id': f'o{o}-h{h}', 'origin': f'm1-o{o}', 'seed': 817100+o,
             'delay': 1, 'mode': 'H', 'history': h, 'cue': 'strong'}
            for o in range(8) for h in (0, 1)]


def differences(a, b, prefix=''):
    if isinstance(a, dict) and isinstance(b, dict):
        result = []
        for key in sorted(set(a) | set(b)):
            path = prefix+'.'+key if prefix else key
            if key not in a or key not in b:
                result.append(path)
            else:
                result.extend(differences(a[key], b[key], path))
        return result
    return [] if a == b else [prefix]


def new_stats():
    return {'n': 0, 'sums': dict.fromkeys(base.SYMBOLS, 0.), 'unrelated': []}


def advance(subject, stats, target, *, teaching):
    for t in range(subject.engine.time_us+50_000, target+1, 50_000):
        subject.advance(t)
        nodes = {n['channel']: n for n in subject.engine.observation_nodes()}
        if teaching and 1_000_000 <= t <= 17_000_000:
            stats['n'] += 1
            for symbol, channel in subject.channels.items():
                stats['sums'][symbol] += nodes.get(channel, {}).get('activation', 0.)
        if not teaching:
            stats['unrelated'].append({'time_us': t, 'activation': [
                nodes.get(subject.channels[s], {}).get('activation', 0.) for s in 'ZW']})
        if subject.engine.life == 'dead':
            break


def select_edges(graph, channels, history, stats):
    nodes = {n['channel']: n for n in graph['nodes']}
    by_pair = {(e['source'], e['target']): e for e in graph['edges']}
    expected = 'A' if history == 0 else 'B'
    other = 'B' if history == 0 else 'A'
    summaries = {}
    for name, sources, target in [('target', 'XY', expected), ('matched', 'ZW', other)]:
        rows = []
        for symbol in sources:
            source_id, target_id = nodes[channels[symbol]]['id'], nodes[channels[target]]['id']
            edge = by_pair.get((source_id, target_id))
            if edge is None:
                continue
            degrees = [[sum(e['target'] == n for e in graph['edges']),
                        sum(e['source'] == n for e in graph['edges'])] for n in (source_id, target_id)]
            rows.append({'edge': [source_id, target_id], 'weight': edge['weight'], 'degrees': degrees,
                         'teaching_activity': [stats['sums'][s]/stats['n'] for s in (symbol, target)],
                         'last_activity': [nodes[channels[s]].get('activation', 0.) for s in (symbol, target)]})
        summaries[name] = rows
    a, b = summaries['target'], summaries['matched']
    residuals = {'counts': [len(a), len(b)]}
    valid = len(a) == len(b) == 2
    if valid:
        residuals.update(weight_mean_difference=statistics.mean(r['weight'] for r in a)-statistics.mean(r['weight'] for r in b),
                         teaching_mean_differences=[statistics.mean(r['teaching_activity'][i] for r in a)-statistics.mean(r['teaching_activity'][i] for r in b) for i in (0, 1)],
                         corresponding_degrees_equal=all(x['degrees'] == y['degrees'] for x, y in zip(a, b)))
        valid = (residuals['corresponding_degrees_equal'] and abs(residuals['weight_mean_difference']) <= .02
                 and all(abs(v) <= .02 for v in residuals['teaching_mean_differences']))
    return {'groups': summaries, 'residuals': residuals, 'matching_passed': valid}


def apply_mask(subject, selection, arm):
    before = subject.save()
    edges = [r['edge'] for r in selection['groups']['matched' if arm == 'matched' else 'target']]
    if arm != 'intact':
        subject.engine.intervene(edges=[] if arm == 'sham' else edges, action='silence')
    masked = subject.save()
    if arm == 'restored':
        subject.engine.intervene(edges=edges, action='restore')
    after = subject.save()
    allowed = {'core.silenced_edges'} if arm in ('target', 'matched', 'restored') else set()
    changed = set(differences(before, masked))
    if not changed <= allowed or (arm == 'restored' and base.digest(before) != base.digest(after)):
        raise RuntimeError('intervention changed non-mask state or reversal was not exact')
    if arm in ('target', 'matched', 'restored') and len(edges) == 2 and changed != allowed:
        raise RuntimeError('requested edge mask was ineffective')
    return {'arm': arm, 'edges': edges, 'before_sha256': base.digest(before),
            'masked_sha256': base.digest(masked), 'after_sha256': base.digest(after),
            'changed_immediate_fields': sorted(changed), 'immediate_reversal': arm == 'restored'}


def commit(folder, subject, stats, index):
    name = f'whole-{index:04d}.json.gz'
    value = {'schema': 'threemind.m1-whole-with-observation/1', 'subject': subject.save(), 'observation': stats}
    receipt = base.original(folder/name, value, compressed=True)
    base.atomic_json(folder/'current.json', {'path': name, 'index': index, 'time_us': subject.engine.time_us, **receipt})


def load_current(folder):
    current = base.read(folder/'current.json')
    raw = (folder/current['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != current['sha256']:
        raise RuntimeError('complete current state hash mismatch')
    value = json.loads(gzip.decompress(raw))
    return base.Subject(value['subject']['case'], value['subject']), value['observation'], current['index']


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with base.worker_lock(work), base.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered; do not repeat')
        name = '2026-10-16 机制发现 · M1 选择性连接静默探索'
        projects = [p for p in client.call('projects.list', {}) if p['name'] == name]
        if len(projects) > 1:
            raise RuntimeError('ambiguous project')
        project = projects[0] if projects else client.request('POST', '/api/v2/projects', body={'name': name})
        resource = 'mechanism-m1-silence-20261016'
        base.original(work/'platform.json', {'project_id': project['id'], 'resource_id': resource})
        base.original(work/'implementation.json', base.capture_implementation('native'))
        files = [Path(__file__), HERE/'pilot_m2.py', HERE/'pilot-m1-silence.zh.md', HERE/'pilot-m1-silence.en.md',
                 base.ROOT/'lab/tools/study_lock.py',
                 base.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(base.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        base.original(work/'runner-manifest.json', manifest)
        for p in files:
            base.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        base.original(work/'parents.json', parents())
        r = base.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:M1:silence-v1:20261016', 'title': name,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [base.KERNEL], 'protocol': (HERE/'pilot-m1-silence.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': base.digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                    'metadata': {'work': str(work), 'independent_origins': 8, 'parents': 16, 'causal_copies': 80}},
                   request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={
            'resource_id': resource, 'target_id': 'managed-research-experiments',
            'relative_path': '2026-10-16-mechanism-discovery/m1-silence-v1', 'registered_work_path': str(work),
            'writer_mode': 'cooperative', 'expected_revision': 0}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={
            'project_id': project['id'], 'resource_id': resource}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'document:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M1 silence pilot v1 '+lang,
                    'markdown': (HERE/f'pilot-m1-silence.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(json.dumps({'project': project['id'], 'record': r.experiment, 'status': r.status}), flush=True)


def apparatus(work):
    with base.worker_lock(work), base.connection() as client:
        base.frozen_check(work)
        if (work/'apparatus.json').exists() or (work/'in-flight.json').exists():
            raise RuntimeError('existing/incomplete apparatus; inspect without rerun')
        base.resource_check(work)
        base.original(work/'in-flight.json', {'operation': 'apparatus', 'pid': os.getpid()})
        case = parents()[0] | {'id': 'apparatus', 'origin': 'apparatus', 'seed': 817001}
        subject, stats = base.Subject(case), new_stats()
        advance(subject, stats, 18_000_000, teaching=True)
        selection = select_edges(subject.engine.graph(), subject.channels, 0, stats)
        base.original(work/'apparatus-parent.json.gz', {'subject': subject.save(), 'stats': stats}, compressed=True)
        reports = {}
        for arm in ARMS:
            child = base.Subject(case, copy.deepcopy(subject.save()))
            reports[arm] = apply_mask(child, selection, arm)
            base.original(work/'apparatus'/f'{arm}.json.gz', child.save(), compressed=True)
        report = {'passed': True, 'selection': selection, 'arms': reports, 'seed': 817001,
                  'pilot_included': False, 'same_time_only': True}
        base.original(work/'apparatus.json', report)
        r = base.recorder(work, client)
        r.append('result', 'apparatus-v1', report, request_id=uuid5(NS, 'apparatus'))
        r.synchronize()
        (work/'in-flight.json').unlink()
        print(json.dumps(report), flush=True)


def ensure_monitor(work, guard):
    if (work/'STOP').exists():
        return False
    if not guard.thread.is_alive():
        raise RuntimeError('resource monitor absent')
    if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) >= 4*2**30:
        base.original(work/'STOP', {'reason': '4 GiB original budget', 'epoch': time.time()})
        return False
    return True


def run(work):
    import psutil
    # Single execution lane shared with M2; do not compete with a live pilot host.
    with base.worker_lock(base.DEFAULT_WORK), base.worker_lock(work), base.connection() as client:
        base.frozen_check(work)
        if not base.read(work/'apparatus.json')['passed']:
            raise RuntimeError('apparatus not passed')
        if (work/'in-flight.json').exists() or (work/'STOP').exists():
            raise RuntimeError('STOP or orphan in-flight; explicit review required')
        r = base.recorder(work, client)
        base.atomic_json(work/'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(),
                                          'command': sys.argv, 'epoch': time.time()})
        with base.Guard(work) as guard:
            for case in base.read(work/'parents.json'):
                parent_folder = work/'parents'/case['id']
                if not ensure_monitor(work, guard):
                    break
                if (parent_folder/'current.json').exists():
                    parent, stats, index = load_current(parent_folder)
                else:
                    base.original(work/'in-flight.json', {'operation': 'parent-birth', 'case': case, 'pid': os.getpid()})
                    parent, stats, index = base.Subject(case), new_stats(), 0
                    commit(parent_folder, parent, stats, index)
                    (work/'in-flight.json').unlink()
                while parent.engine.time_us < 18_000_000 and parent.engine.life != 'dead':
                    if not ensure_monitor(work, guard):
                        break
                    target = min(18_000_000, parent.engine.time_us+10_000_000)
                    base.original(work/'in-flight.json', {'operation': 'parent-advance', 'case': case,
                                  'from_us': parent.engine.time_us, 'to_us': target, 'pid': os.getpid()})
                    advance(parent, stats, target, teaching=True)
                    index += 1
                    commit(parent_folder, parent, stats, index)
                    (work/'in-flight.json').unlink()
                if (work/'STOP').exists():
                    break
                if parent.engine.life == 'dead':
                    base.original(parent_folder/'death.json', {'life': 'dead', 'time_us': parent.engine.time_us,
                                                             'case': case, 'no_replacement': True})
                    continue
                selection = select_edges(parent.engine.graph(), parent.channels, case['history'], stats)
                base.original(parent_folder/'selection.json', selection)
                for arm in ARMS:
                    if not ensure_monitor(work, guard):
                        break
                    folder = work/'copies'/(case['id']+'-'+arm)
                    if (folder/'result.json').exists():
                        result = base.read(folder/'result.json')
                    else:
                        base.original(work/'in-flight.json', {'operation': 'declared-causal-probe', 'parent': case,
                                      'arm': arm, 'from_us': 18_000_000, 'to_us': 20_000_000, 'pid': os.getpid()})
                        saved = copy.deepcopy(parent.save())
                        child_case = case | {'id': case['id']+'-'+arm}
                        saved['case'] = child_case
                        child = base.Subject(child_case, saved)
                        lineage = {'parent_case': case['id'], 'parent_current': base.read(parent_folder/'current.json'),
                                   'parent_subject_sha256': base.digest(parent.save()), 'changed_identity_fields': ['case.id'],
                                   'reason': 'pre-registered causal research copy', 'arm': arm}
                        base.original(folder/'lineage.json', lineage)
                        probe_stats = new_stats()
                        commit(folder, child, probe_stats, 0)
                        intervention = apply_mask(child, selection, arm)
                        base.original(folder/'intervention.json', intervention)
                        base.original(folder/'after-intervention.json.gz', child.save(), compressed=True)
                        advance(child, probe_stats, 20_000_000, teaching=False)
                        commit(folder, child, probe_stats, 1)
                        early = [row['response'] for row in child.rows if 100_000 <= row['time_us']-18_000_000 <= 300_000]
                        result = child.result() | {'arm': arm, 'early_primary': statistics.mean(early) if early else None,
                                                  'early_count': len(early), 'matching_passed': selection['matching_passed'],
                                                  'unrelated_activity_sum': sum(sum(x['activation']) for x in probe_stats['unrelated'])}
                        base.original(folder/'result.json', result)
                        (work/'in-flight.json').unlink()
                    request = uuid5(NS, 'result:'+result['case']['id'])
                    if not (r.control/'receipts'/f'{request}.json').exists():
                        r.append('result', result['case']['id'], result, request_id=request)
                    r.synchronize()
                    count = len(list((work/'copies').glob('*/result.json')))
                    base.atomic_json(work/'progress.json', {'completed_copies': count, 'planned': 80, 'last': result['case']['id'],
                                                          'epoch': time.time(), 'recorder': r.status})
                    print(json.dumps({'copy': result['case']['id'], 'primary': result['early_primary'],
                                      'matched': selection['matching_passed']}), flush=True)
            r.synchronize()
        count = len(list((work/'copies').glob('*/result.json')))
        deaths = len(list((work/'parents').glob('*/death.json')))
        base.atomic_json(work/'status.json', {'state': 'awaiting-analysis' if count+5*deaths == 80 else 'paused',
                                            'completed_copies': count, 'dead_parents': deaths, 'recorder': r.status})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('register', 'apparatus', 'run', 'status', 'check'))
    parser.add_argument('--work', type=Path, default=WORK)
    args = parser.parse_args()
    work = args.work.resolve()
    if args.command == 'status':
        print(json.dumps({name: base.read(work/name) if (work/name).exists() else None
                          for name in ('host.json', 'progress.json', 'status.json', 'STOP', 'in-flight.json', 'resource-summary.json')}))
    elif args.command == 'check':
        print(json.dumps(base.resource_check(work)))
    else:
        {'register': register, 'apparatus': apparatus, 'run': run}[args.command](work)


if __name__ == '__main__':
    main()
