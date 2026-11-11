"""Post-computation E68 comparison and delivery snapshot; never load a subject."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
ARMS = ('2', '3.1')


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def size(path):
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())


def review(work, ffprobe):
    audit = read(work / 'analysis/verified-results.json')
    completed = read(work / 'computation-complete.json')
    assert all(not (work / 'arms' / a / 'in-flight.json').exists() for a in ARMS)
    manifest = read(work / 'source-reference/manifest.json')
    for name, expected in manifest.items():
        assert sha(ROOT / name) == expected, name
        assert sha(work / 'source-reference' / name) == expected, name
    results = {}
    finals = {}
    for arm in ARMS:
        base = work / 'arms' / arm
        a = audit['arms'][arm]
        pointer = read(base / 'latest.json')
        assert pointer['boundary_sha256'] == completed['final_boundaries'][arm] == a['last_boundary']
        assert pointer['end_us'] == 1555000000 and pointer['committed_updates'] == 4800
        for name, member in pointer['files'].items():
            p = base / pointer['checkpoint'] / name
            assert sha(p) == member['sha256'] and p.stat().st_size == member['bytes']
        development = [read(base / f'development-{i}/predictions.json') for i in range(4)]
        transitions = []
        for i in range(1, 4):
            old = {x['question_id']: x['correct'] for x in development[i-1]}
            transitions.append(dict(round=i,
                corrected=sum(not old[x['question_id']] and x['correct'] for x in development[i]),
                regressed=sum(old[x['question_id']] and not x['correct'] for x in development[i])))
        finals[arm] = read(base / 'final/predictions.json')
        receipt = read(work / 'replays' / arm / 'export.json')
        video = work / receipt['video']
        assert receipt['activity_curves'] == ['activation', 'inhibition', 'direct', 'associative']
        assert receipt['core_advanced'] is False and sha(video) == receipt['sha256']
        for source in receipt['sources']:
            assert sha(work / source['path']) == source['sha256']
        info = json.loads(subprocess.check_output([str(ffprobe), '-v', 'error', '-show_streams',
                                                  '-show_format', '-of', 'json', str(video)]))
        stream = next(x for x in info['streams'] if x['codec_type'] == 'video')
        assert (stream['width'], stream['height'], stream['codec_name']) == (1280, 1024, 'h264')
        assert abs(float(info['format']['duration']) - receipt['duration_s']) < .15
        assert int(stream['nb_frames']) == receipt['video_frames']
        results[arm] = dict(scores=a['scores'], transitions=transitions,
            final_wrong=[x for x in finals[arm] if not x['correct']],
            final_by_position={str(side): sum(x['correct'] for x in finals[arm] if x['side'] == side) for side in (0, 1)},
            teaching_lessons={s: a['stages'][s]['lessons'] for s in ('initial-teaching', 'correction-1', 'correction-2', 'correction-3')},
            stage_wall_s=sum(s['wall_seconds'] for s in a['stages'].values()),
            timing=a['timing'], nodes=a['nodes'], edges=a['edges'],
            storage=dict(a['storage'], replay_bytes=size(work / 'replays' / arm), video_bytes=video.stat().st_size),
            video=dict(path=receipt['video'], sha256=receipt['sha256'], seconds=receipt['duration_s'],
                       frames=receipt['video_frames'], source_frames=receipt['original_frames'],
                       chapters=len(receipt['chapters']), curves=receipt['activity_curves']))
    b = {x['question_id']: x for x in finals['3.1']}
    pairs = Counter(f"{int(x['correct'])}:{int(b[x['question_id']]['correct'])}" for x in finals['2'])
    for x in finals['2']:
        y = b[x['question_id']]
        assert all(x[k] == y[k] for k in ('shape', 'color', 'label', 'offset', 'text', 'start_us', 'end_us'))
    return dict(schema='threemind.e68-delivery-review/1', measured_at=datetime.now(timezone.utc).isoformat(),
        basis_sha256=sha(work / 'analysis/verified-results.json'), frozen_source_files_verified=len(manifest),
        model_advanced=False, restore_performed=False, arms=results, paired_final_correctness=dict(pairs),
        physical_file_bytes_before_this_receipt=size(work),
        file_size_scope='All files under this experiment root at measurement time; logical file lengths, not allocated sectors. '
                        'Includes boundary snapshots, trajectories, replays, frozen sources and recorder receipts. '
                        'Excludes shared software, database pages, and this receipt or subsequent publication bookkeeping.',
        resource_subtotals={n:size(work/n) for n in ('arms', 'analysis', 'replays', 'source-reference', '.research-records')},
        limitations=['One individual per kernel; questions in a continuous history are not independent replicates.',
                     'Final questions change held-out positions, order and internal history together.',
                     'Teaching and supervised personal-reader calibration were not independently ablated.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ffprobe', type=Path, default=Path('D:/DevTools/ffmpeg/bin/ffprobe.exe'))
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('Review receipt exists; retain it and use a distinct revision path')
    result = review(args.work.resolve(), args.ffprobe)
    with args.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({a: result['arms'][a]['video'] for a in ARMS}, ensure_ascii=False))


if __name__ == '__main__':
    main()
