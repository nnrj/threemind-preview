"""Read-only E69 evidence audit and derived summaries; never imports Core."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

from journal import encoded, fixed_json, read, sha

FIELDS = ('activation', 'inhibition', 'direct', 'associative')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def load_clip(path):
    with gzip.open(path, 'rt', encoding='utf-8') as source:
        return json.load(source)


def score_path(path):
    name = path.name.removesuffix('.json.gz')
    if name.startswith('reanswer-'):
        return path.parents[1] / 'reanswers' / (name.removeprefix('reanswer-') + '.json')
    return path.parents[1] / 'units' / (name + '.json')


def ordered_clips(work):
    """Order by recorded time, never by an alphabetical curriculum guess."""
    work = Path(work)
    starts = {}
    for path in (work / 'subject/chain').glob('*.json'):
        boundary = read(path)
        parts = boundary['key'].split(':')
        if len(parts) == 2 and parts[1].isdigit():
            starts[f'{parts[0]}/clips/{parts[1]}.json.gz'] = boundary['start_us']
        elif len(parts) == 3 and parts[1] in ('gap', 'reanswer'):
            starts[f'{parts[0]}/clips/{parts[1]}-{parts[2]}.json.gz'] = boundary['start_us']
    entries = []
    for path in (work / 'stages').glob('*/clips/*.json.gz'):
        key = path.relative_to(work / 'stages').as_posix()
        if key in starts:
            entries.append((starts[key], path))
        else:
            raise ValueError('recorded clip has no committed current boundary: ' + key)
    return [path for _, path in sorted(entries)]


def byte_count(folder):
    return sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()) if folder.exists() else 0


def summarize_results(rows):
    result = {'trials': len(rows)}
    for field in ('success', 'autonomous_success', 'eye_success', 'hand_success', 'eye_before_hand', 'word_correct',
                  'eye_entered_from_outside', 'hand_entered_from_outside'):
        measured = [r[field] for r in rows if r.get(field) is not None]
        if measured:
            result[field] = {'correct': sum(bool(v) for v in measured), 'n': len(measured)}
    result['score_scope'] = 'Teaching successes are assisted apparatus results, not autonomous learned ability; null order measures are excluded.'
    return result


def audit(work):
    work = Path(work).resolve()
    require((work / 'computation-complete.json').exists(), 'formal computation is not complete')
    subject = work / 'subject'
    require(not (subject / 'in-flight.json').exists(), 'uncommitted experience remains')
    completion = read(work / 'computation-complete.json')
    chain = [read(p) for p in sorted((subject / 'chain').glob('*.json'))]
    require(bool(chain), 'missing continuous-state chain')
    identity = chain[0]['identity']
    previous = None
    members = 0
    dependencies = {}
    clocks = set()
    for sequence, boundary in enumerate(chain):
        original = {k: v for k, v in boundary.items() if k != 'boundary_sha256'}
        require(hashlib.sha256(encoded(original)).hexdigest() == boundary['boundary_sha256'],
                f'boundary {sequence}: broken digest')
        require(boundary['sequence'] == sequence and boundary['identity'] == identity,
                f'boundary {sequence}: identity or cursor mismatch')
        description = boundary['description']
        require(description['identity'] == identity and description['time_us'] == boundary['end_us'],
                f'boundary {sequence}: inconsistent description')
        if previous is None:
            require(boundary['key'] == 'birth' and boundary['parent'] is None and boundary['end_us'] == 0,
                    'the current individual must start from a blank birth')
        else:
            require(boundary['parent'] == previous['boundary_sha256'] and
                    boundary['start_us'] == previous['end_us'] and boundary['end_us'] >= boundary['start_us'],
                    f'boundary {sequence}: noncontinuous internal time or ancestry')
            require(description['learning'].keys() == previous['description']['learning'].keys(),
                    'personal peripheral set changed')
        for name, state in description['learning'].items():
            require(state['computed_updates'] == state['committed_updates'], 'peripheral rollback: ' + name)
            if previous is None:
                require(state['computed_updates'] == 0, 'nonblank peripheral birth: ' + name)
            else:
                require(state['committed_updates'] >= previous['description']['learning'][name]['committed_updates'],
                        'peripheral learning moved backwards: ' + name)
        folder = (subject / boundary['checkpoint']).resolve()
        require(folder.is_relative_to(subject), 'unsafe checkpoint path')
        actual_names = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
        require(actual_names == set(boundary['files']), 'missing or extra complete-state members')
        for name, meta in boundary['files'].items():
            path = (folder / name).resolve()
            require(path.is_relative_to(folder) and path.is_file() and path.stat().st_size == meta['bytes']
                    and sha(path) == meta['sha256'], 'corrupt complete-state member: ' + str(path))
            members += 1
        manifest = read(folder / 'complete.json')
        require(all(manifest[k] == description[k] for k in ('identity', 'time_us', 'learning')),
                'snapshot manifest differs from its continuity boundary')
        if (folder / 'dependencies.json').exists():
            refs = read(folder / 'dependencies.json').get('corpora', [])
        else:
            with gzip.open(folder / 'system.json.gz', 'rt', encoding='utf-8') as stream:
                refs = json.load(stream).get('corpora', [])
        for reference in refs:
            name, expected = reference['path'], reference['sha256']
            path = (work / name).resolve()
            require(path.is_relative_to(work) and path.is_file(), 'missing or unsafe dependency: ' + name)
            if name in dependencies:
                require(dependencies[name]['sha256'] == expected, 'dependency identity changed: ' + name)
            else:
                require(sha(path) == expected, 'dependency hash mismatch: ' + name)
                dependencies[name] = {'sha256': expected, 'bytes': path.stat().st_size}
        clocks.update((boundary['start_us'], boundary['end_us']))
        previous = boundary
    require(read(subject / 'latest.json') == chain[-1], 'latest pointer differs from final complete state')
    require(completion.get('latest') == chain[-1] and completion.get('time_us') == chain[-1]['end_us'],
            'completion receipt differs from final complete state')
    final_folder = subject / chain[-1]['checkpoint']
    with gzip.open(final_folder / 'system.json.gz', 'rt', encoding='utf-8') as stream:
        final = json.load(stream)
    with gzip.open(subject / chain[0]['checkpoint'] / 'system.json.gz', 'rt', encoding='utf-8') as stream:
        birth = json.load(stream)
    require(len(birth['session']['core']['nodes']) == len(birth['session']['core']['edges']) == 0,
            'Core did not start from an empty graph')
    require(not birth['history'] and birth['current'] is None, 'recent activity must start empty')
    dt_us = int(final['session']['dt_us'])
    end_us = chain[-1]['end_us']
    require(int(final['session']['core']['time_us']) == end_us and final['identity'] == identity,
            'final Core or identity differs from complete boundary')
    require(abs(final['session']['world']['time_s'] - end_us / 1e6) < 1e-6,
            'physical world and internal time diverge')
    analysis = work / 'analysis'
    analysis.mkdir(exist_ok=True)
    trace_path = analysis / 'activity.csv'
    temporary = analysis / 'activity.csv.partial'
    require(not temporary.exists(), 'interrupted activity export exists; inspect before retry')
    sources, frame_count, last_us, clip_bounds = [], 0, 0, {}
    with temporary.open('x', encoding='utf-8', newline='') as output:
        writer = csv.writer(output)
        writer.writerow(['time_us', 'stage', 'clip', *FIELDS])
        for path in ordered_clips(work):
            record = load_clip(path)
            stage = path.parents[1].name
            rows = record['process']
            require(bool(rows), 'empty physical clip: ' + str(path))
            start = last_us
            for row in rows:
                now = int(row['activity']['time_us'])
                require(now == last_us + dt_us, 'missing, duplicate or backwards sample: ' + str(path))
                require(abs(row['observation']['time_s'] - last_us / 1e6) < 1e-6,
                        'physical observation timestamp mismatch: ' + str(path))
                writer.writerow([now, stage, path.name,
                                 *[sum(float(n[key]) for n in row['activity']['nodes']) for key in FIELDS]])
                last_us = now
                frame_count += 1
            require(start in clocks and last_us in clocks, 'clip does not align with complete operation boundaries')
            unit_path = score_path(path)
            if unit_path.exists():
                score = read(unit_path)
                require(score.get('start_us', start) == start and score.get('end_us', last_us) == last_us,
                        'score window differs from actual experience')
                expression = rows[-1].get('expression')
                if expression and 'answer' in score:
                    require(expression['selected'] == score['answer'], 'score differs from recorded expression')
            clip_bounds[path.relative_to(work).as_posix()] = {'start_us': start, 'end_us': last_us, 'frames': len(rows)}
            sources.append({'path': path.relative_to(work).as_posix(), 'sha256': sha(path)})
    require(last_us == end_us, 'sampled physical experience does not reach current complete boundary')
    if trace_path.exists():
        require(sha(trace_path) == sha(temporary), 'derived activity trace content conflict')
        temporary.unlink()
    else:
        temporary.rename(trace_path)
    stages = []
    for path in (work / 'stages').glob('*/result.json'):
        result = read(path)
        rows = result.get('results', [])
        if not rows:
            rows = [read(p) for p in sorted((path.parent / 'units').glob('*.json')) if 'success' in read(p)]
        reanswers = [{'path': p.relative_to(work).as_posix(), 'score': read(p)}
                     for p in sorted((path.parent / 'reanswers').glob('*.json'))]
        stages.append({'stage': path.parent.name, 'kind': result.get('kind'), 'path': path.relative_to(work).as_posix(),
                       'summary': summarize_results(rows), 'reported_summary': result.get('summary'),
                       'reanswer_summary': summarize_results([r['score'] for r in reanswers]), 'reanswers': reanswers,
                       'start_us': result.get('start_us'), 'end_us': result.get('end_us'), 'result': result})
    stages.sort(key=lambda s: (s['result'].get('start_sequence', 0), s['start_us'] or 0, s['stage']))
    final_refs = {r['path'] for r in final.get('corpora', [])}
    final_dependency_bytes = sum(dependencies[p]['bytes'] for p in final_refs)
    result = {
        'study': 'E69', 'identity': identity, 'kernel': final['session']['core']['dynamics'],
        'continuous': True, 'rollback_count': 0, 'sim_seconds': end_us / 1e6, 'frames': frame_count,
        'boundaries': len(chain), 'verified_checkpoint_members': members, 'learning': chain[-1]['description']['learning'],
        'last_boundary': chain[-1]['boundary_sha256'], 'completion': completion,
        'activity_sha256': sha(trace_path),
        'nodes': len(final['session']['core']['nodes']), 'edges': len(final['session']['core']['edges']),
        'timing': final.get('meter', {}), 'timing_caveat': 'Nested timers cannot be summed; sensor_core_body is not Core-only.',
        'stages': stages, 'clip_bounds': clip_bounds, 'sources': sources, 'dependencies': dependencies,
        'storage': {'all_experiment_bytes_before_this_report': byte_count(work),
                    'boundary_snapshots_bytes': byte_count(subject / 'boundaries'),
                    'current_checkpoint_bytes': byte_count(final_folder),
                    'current_external_corpora_bytes': final_dependency_bytes,
                    'complete_current_individual_bytes': byte_count(final_folder) + final_dependency_bytes,
                    'all_unique_dependency_bytes': sum(v['bytes'] for v in dependencies.values()),
                    'replay_bytes_at_audit': byte_count(work / 'replays'),
                    'measurement': 'File lengths, not allocated blocks; shared runtimes/database not attributed.'},
        'scope': 'Complete-state bytes, dependency hashes and every recorded physical frame verified. No Core instantiated.'}
    fixed_json(analysis / 'verified-results.json', result)
    # This is evidence verification, not human/video/report approval.
    fixed_json(analysis / 'audit-receipt.json', {'continuity_verified': True, 'video_verified': False,
                                              'reports_reviewed': False, 'result_sha256': sha(analysis / 'verified-results.json')})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.work)
    print(json.dumps({key: result[key] for key in ('identity', 'sim_seconds', 'frames', 'boundaries', 'nodes', 'edges')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
