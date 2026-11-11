"""Read-only gaze events; scoring targets never enter a controller or Core."""
import argparse
import gzip
import json
from pathlib import Path
import numpy as np


def gaze_events(rows, targets, *, dt=.05, half_width=None, slow_speed=.08):
    if not rows or len(rows) != len(targets) or dt <= 0:
        raise ValueError('aligned observations and scoring-only targets')
    eye = np.asarray([r['observation']['eye_angle_rad'] for r in rows])
    speed = np.linalg.norm([r['observation']['eye_velocity_rad_s'] for r in rows], axis=1)
    target = np.asarray(targets)
    half_width = float(half_width if half_width is not None else rows[0]['observation'].get('eye_config', {}).get('center_half_width', .075))
    if target.shape != eye.shape or eye.shape != (len(rows), 2) or half_width <= 0 or slow_speed < 0:
        raise ValueError('two-axis gaze and positive physical clear area')
    if not all(np.isfinite(v).all() for v in (eye, target, speed, [dt, half_width, slow_speed])):
        raise ValueError('finite physical measurements')
    d = np.column_stack((np.sin(target[:, 0])*np.cos(target[:, 1]), np.sin(target[:, 1]),
                         np.cos(target[:, 0])*np.cos(target[:, 1])))
    yaw, pitch = eye[:, 0], eye[:, 1]
    forward = np.column_stack((np.sin(yaw)*np.cos(pitch), np.sin(pitch), np.cos(yaw)*np.cos(pitch)))
    right = np.column_stack((np.cos(yaw), np.zeros(len(eye)), -np.sin(yaw)))
    up = np.column_stack((-np.sin(yaw)*np.sin(pitch), np.cos(pitch), -np.cos(yaw)*np.sin(pitch)))
    depth = np.sum(d*forward, axis=1)
    center = (depth > 0) & (np.maximum(np.abs(np.sum(d*right, axis=1)),
                                    np.abs(np.sum(d*up, axis=1))) <= half_width*depth)
    stable = center & (speed < slow_speed)
    boundaries = [0, *(np.flatnonzero(np.any(np.abs(np.diff(target, axis=0)) > 1e-8, axis=1))+1), len(rows)]
    phases = []
    for start, end in zip(boundaries, boundaries[1:]):
        def summarize(values):
            subset = values[start:end]; hits = np.flatnonzero(subset); longest = current = 0
            for present in subset:
                current = current+1 if present else 0; longest = max(longest, current)
            return {'fraction': float(subset.mean()), 'first_s': float(hits[0]*dt) if len(hits) else None,
                    'longest_s': longest*dt, 'inside_at_start': bool(subset[0]), 'inside_at_end': bool(subset[-1])}
        phases.append({'start_s': int(start)*dt, 'duration_s': int(end-start)*dt,
                       'clear_center': summarize(center), 'aligned_slow': summarize(stable)})
    return {'schema': 'threemind.gaze-events/1', 'half_width': half_width, 'slow_speed_rad_s': slow_speed,
            'phases': phases, 'minimum_dwell_imposed_on_controller': None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('recordings', nargs='+', type=Path); p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(); output = []
    for path in a.recordings:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for index, line in enumerate(f):
                record = json.loads(line)
                if 'scoring_only_eye_targets' in record:
                    output.append({'case': path.parent.name, 'clip': index, 'task': record.get('task'),
                                   **gaze_events(record['process'], record['scoring_only_eye_targets'])})
    with a.output.open('x', encoding='utf-8') as f: json.dump(output, f, ensure_ascii=False)
    print(json.dumps({'output': str(a.output.resolve()), 'clips': len(output)}))


if __name__ == '__main__': main()
