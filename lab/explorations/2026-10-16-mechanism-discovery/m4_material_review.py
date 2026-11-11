"""Read-only E69 material audit. Standard library only; no Core/runner imports."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path

SOURCE = Path('E:/ThreeMindData/experiments/2026-10-13-eye-hand-shape-color/continuations/r1')
STAGES = tuple(f'{task}-dev-{round}' for task in ('gaze', 'coordination') for round in range(4))
THRESHOLDS = tuple((eye, hand) for eye in (.04, .08, .16) for hand in (.005, .01, .02))
MIN_RUN = 6


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_once(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')


def freeze(work):
    latest = read(SOURCE/'subject/latest.json')
    assert latest['identity'] == 'e69-5.1-223'
    assert (SOURCE/'STOP').is_file(), 'E69 is expected to remain paused'
    assert not any((SOURCE/path).exists() for path in ('subject/in-flight.json', 'in-flight.json'))
    chain = {}
    for path in (SOURCE/'subject/chain').glob('*.json'):
        entry = read(path)
        chain[entry['key']] = (path, entry)
    members, clips = {}, []
    def include(path):
        rel = path.relative_to(SOURCE).as_posix()
        members[rel] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    include(SOURCE/'subject/latest.json'); include(SOURCE/'STOP')
    for stage in STAGES:
        folder = SOURCE/'stages'/stage
        result = read(folder/'result.json')
        assert result['identity'] == latest['identity'] and result['end_us'] <= latest['end_us']
        include(folder/'result.json'); include(folder/'tasks.json')
        paths = sorted((folder/'units').glob('*.json'))
        assert len(paths) == len(result['results']) == 24, 'complete preregistered development stage required'
        for unit_path in paths:
            unit = read(unit_path)
            key = stage+':'+unit_path.stem
            chain_path, boundary = chain[key]
            assert (unit['start_us'], unit['end_us']) == (boundary['start_us'], boundary['end_us'])
            clip = folder/'clips'/(unit_path.stem+'.json.gz')
            include(unit_path); include(chain_path); include(clip)
            clips.append({'stage': stage, 'unit': unit_path.relative_to(SOURCE).as_posix(),
                          'clip': clip.relative_to(SOURCE).as_posix(), 'key': key,
                          'boundary_sha256': boundary['boundary_sha256'],
                          'start_us': unit['start_us'], 'end_us': unit['end_us']})
    manifest = {'schema': 'threemind.m4-materials/1', 'source_root': str(SOURCE),
                'identity': latest['identity'], 'latest_sequence': latest['sequence'],
                'latest_boundary_sha256': latest['boundary_sha256'], 'members': members, 'clips': clips,
                'thresholds': [list(v) for v in THRESHOLDS], 'minimum_consecutive_frames': MIN_RUN,
                'independent_individuals': 1, 'conditions': ['gaze-only curriculum', 'combined curriculum'],
                'isolated_hand_condition_exists': False, 'status': 'frozen-before-stratification'}
    write_once(work/'materials.json', manifest)
    return {'clips': len(clips), 'members': len(members), 'bytes_referenced': sum(v['bytes'] for v in members.values())}


def runs(labels):
    lengths, previous, count = defaultdict(list), None, 0
    for label in labels+[None]:
        if label != previous:
            if previous is not None:
                lengths[previous].append(count)
            previous, count = label, 1
        else:
            count += 1
    return {key: [v for v in values if v >= MIN_RUN] for key, values in lengths.items()}


def analyze(work, boundary_check=None):
    manifest = read(work/'materials.json')
    assert manifest['thresholds'] == [list(v) for v in THRESHOLDS]
    for rel, record in manifest['members'].items():
        assert sha(SOURCE/rel) == record['sha256'], 'source changed: '+rel
    counts, rows = {}, []
    for item in manifest['clips']:
        if boundary_check:
            boundary_check()
        with gzip.open(SOURCE/item['clip'], 'rt', encoding='utf-8') as stream:
            clip = json.load(stream)
        unit = read(SOURCE/item['unit']); frames = clip['process']
        assert clip['kind'] == 'test' and len(frames) == 120
        assert unit['identity'] == manifest['identity'] and not unit['teaching']
        assert all(not f['assistance'] for f in frames), 'assisted clip in autonomous denominator'
        node_identity = set()
        for frame in frames:
            for node in frame['activity']['nodes']:
                node_identity.add((node['id'], node['channel'], node['birth_us']))
                assert all(key in node for key in ('activation', 'inhibition', 'direct', 'associative'))
        summary = {'stage': item['stage'], 'key': item['key'], 'start_us': item['start_us'],
                   'end_us': item['end_us'], 'frames': len(frames), 'node_identities': len(node_identity),
                   'new_move_decisions': unit['move_decisions'], 'new_wait_decisions': unit['wait_decisions'],
                   'inherited_move': unit['inherited_move'], 'strata': {}}
        for eye, hand in THRESHOLDS:
            name = f'{eye:g}/{hand:g}'
            labels = []
            for frame in frames:
                observation = frame['observation']; pointer = observation['pointer']
                eye_moving = math.hypot(*observation['eye_velocity_rad_s']) >= eye
                hand_moving = math.hypot(pointer['vx'], pointer['vy']) >= hand
                labels.append('joint' if eye_moving and hand_moving else 'eye-only' if eye_moving else
                              'hand-only' if hand_moving else 'neither')
            segments = runs(labels)
            summary['strata'][name] = {'frames': dict(Counter(labels)), 'qualified_runs': segments}
            bucket = counts.setdefault(name, {}).setdefault(item['stage'], {'clips': 0, 'frames': Counter(),
                        'qualified_clips': Counter(), 'qualified_frames': Counter()})
            bucket['clips'] += 1; bucket['frames'].update(labels)
            bucket['qualified_clips'].update({key: 1 for key, seq in segments.items() if seq})
            bucket['qualified_frames'].update({key: sum(seq) for key, seq in segments.items()})
        rows.append(summary)
        del clip, frames
    primary = counts['0.08/0.01']
    enough = all(sum(primary[f'{task}-dev-{round}']['qualified_clips'][category]
                     for task in ('gaze', 'coordination') for round in rounds) >= 8
                 for rounds in ((0, 1), (2, 3)) for category in ('eye-only', 'hand-only', 'joint'))
    result = {'schema': 'threemind.m4-material-review/1', 'independent_individuals': 1, 'clips': len(rows),
              'frames': sum(r['frames'] for r in rows), 'all_current_sources_verified': True,
              'new_move_decisions': sum(r['new_move_decisions'] for r in rows),
              'new_wait_decisions': sum(r['new_wait_decisions'] for r in rows),
              'eligible_three_behavior_strata': enough, 'isolated_hand_condition_exists': False,
              'simultaneous_randomized_task_conditions_exist': False, 'final_test_available': False,
              'functional_region_hypothesis_testable_in_these_materials': False,
              'decision': 'Dedicated balanced prospective M4 is required for the registered functional-dissociation question.',
              'movement_is_not_isolated_training': True, 'source_files_modified': 0,
              'counts': counts, 'rows': rows, 'materials_sha256': sha(work/'materials.json')}
    for rel in ('subject/latest.json', 'STOP'):
        assert sha(SOURCE/rel) == manifest['members'][rel]['sha256'], 'paused source changed during analysis'
    write_once(work/'analysis-v1.json', result)
    return {k:v for k,v in result.items() if k not in ('counts', 'rows')}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('command', choices=('freeze', 'analyze'))
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args(); print(json.dumps({'freeze': freeze, 'analyze': analyze}[args.command](args.work), ensure_ascii=False))
