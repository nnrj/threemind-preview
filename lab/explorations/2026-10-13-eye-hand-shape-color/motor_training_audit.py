"""Read-only E69 corpus/scoring/geometry audit. No Core, model or world loading."""
import argparse
import collections
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def audit(work):
    sources = {}

    def read(relative):
        path = (work / relative).resolve()
        if not path.is_relative_to(work):
            raise ValueError('source outside this work directory')
        sources[relative] = digest(path)
        return json.loads(path.read_text(encoding='utf-8'))

    plans = {}
    for stage in ('coordination-fit-0', 'coordination-fit-1'):
        plan = read(f'stages/{stage}/motor-plan.json')
        groups = collections.defaultdict(collections.Counter)
        for ref in plan['inputs']:
            path = (work / ref['path']).resolve()
            if not path.is_relative_to(work) or digest(path) != ref['sha256']:
                raise ValueError('changed or unsafe corpus reference')
            # ZIP members are lazy: inspect labels only, never load the large x array.
            with np.load(path, allow_pickle=False) as values:
                move, hand = values['move_y'], values['hand_y']
                assert len(move) == ref['lengths']['move_y'] == len(hand)
                assert np.all((move == 0) | (move == 1))
                assert np.all(hand[move == 1] >= 0)
                c = groups[Path(ref['path']).parts[1]]
                c.update(samples=len(move), move=int(move.sum()),
                         wait=int((move == 0).sum()), hand_supervised=int((move == 1).sum()))
        total = sum(groups.values(), collections.Counter())
        receipt = read(f'stages/{stage}/motor-023.json')
        assert total['samples'] == plan['examples'] == receipt['n']
        assert total['move'] == receipt['hand_supervised']
        plans[stage] = dict(total=dict(total), by_source={k: dict(v) for k, v in groups.items()},
                            wait_fraction=total['wait'] / total['samples'],
                            committed_updates=receipt['committed_updates'])

    scores = {}
    for stage in ('coordination-dev-0', 'coordination-cal-1', 'coordination-dev-1'):
        result = read(f'stages/{stage}/result.json')
        rows = result['results']
        eligible = [r for r in rows if not r['hand_initially_arrived']]
        scores[stage] = dict(summary=result['summary'], start_us=result['start_us'],
            end_us=result['end_us'], checkpoint=result['checkpoint'], boundary=result['boundary'],
            new_move_trials=sum(r['move_decisions'] > 0 for r in rows),
            move_decisions=sum(r['move_decisions'] for r in rows),
            maintenance_success=sum(r['success'] and r['hand_initially_arrived'] for r in rows),
            new_pointing_success=sum(r['hand_success'] for r in eligible),
            new_coordination_success=sum(r['success'] for r in eligible),
            new_pointing_denominator=len(eligible),
            teacher_trials=sum(r['teaching'] for r in rows))

    geometry = []
    # Fixed illustrative sample, selected before reading outcomes; not an overall accuracy estimate.
    for stage in ('coordination-dev-0', 'coordination-dev-1'):
        for index in (0, 5, 12, 23):
            relative = f'stages/{stage}/clips/{index:06d}.json.gz'
            path = work / relative
            sources[relative] = digest(path)
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                clip = json.load(stream)
            task = clip['task']
            target = np.array([*task['positions'][task['target']], .16])
            errors, best_errors, inside_errors = [], [], []
            for row in clip['process'][:120]:
                ob = row['observation']; camera = ob['camera']
                origin, forward, right, up = [np.asarray(camera[k])
                    for k in ('origin_m', 'forward', 'right', 'up')]
                centers = np.asarray(ob['retinal_centers'])
                offset = target - origin
                depth = float(offset @ forward)
                uv = np.array([offset @ right, offset @ up]) / depth
                nearest = int(np.argmin(((centers - uv) ** 2).sum(axis=1)))
                rays = forward + centers[:, :1] * right + centers[:, 1:] * up
                valid = rays[:, 2] < -1e-8
                endpoints = origin + ((.16 - origin[2]) / rays[valid, 2])[:, None] * rays[valid]
                per_ray = np.linalg.norm(endpoints[:, :2] - target[:2], axis=1)
                all_errors = np.full(len(centers), np.inf); all_errors[valid] = per_ray
                error = float(all_errors[nearest])
                errors.append(error); best_errors.append(float(per_ray.min()))
                if depth > 0 and max(abs(uv)) <= ob['eye_config']['center_half_width']:
                    inside_errors.append(error)
            geometry.append(dict(stage=stage, trial=index, frames=len(errors),
                label_ray_over_015m=sum(e > .15 for e in errors),
                any_ray_within_015m=sum(e <= .15 for e in best_errors),
                median_label_ray_error_m=float(np.median(errors)),
                max_label_ray_error_m=float(max(errors)),
                target_inside_frames=len(inside_errors),
                inside_label_ray_over_015m=sum(e > .15 for e in inside_errors)))
    return dict(schema='threemind.e69-motor-training-audit/1',
        generated_utc=datetime.now(timezone.utc).isoformat(), identity='e69-5.1-223',
        work=str(work), method='Frozen label counts, saved scores and optical ray geometry only; no model, Core or physical replay.',
        limits='Ray errors describe representability at saved camera poses, not physical servo accuracy or a causal intervention. The eight clips are illustrative, not a population estimate.',
        plans=plans, scores=scores, geometry=geometry, sources=sources,
        source_sha256=digest(Path(__file__)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve(); out = args.out.resolve()
    if not out.is_relative_to(work / '.continuation' / 'reviews') or out.exists():
        raise ValueError('a new derived review file under this continuation is required')
    result = audit(work)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in result.items() if k not in ('sources', 'plans')}, ensure_ascii=False))
    print(json.dumps({'plans': result['plans'], 'output': str(out)}, ensure_ascii=False))
