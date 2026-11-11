"""Apparatus-only visibility check, never modifying an experimental Core."""
import json
import time
import numpy as np
from experiment import WORK, read_gzip, task, MODES, EyeHandWorld, teacher_eye_angle, new_json


def main():
    started = time.monotonic()
    state = read_gzip(WORK/'cases/B-teach/checkpoint.json.gz')['world']
    results = []
    for i in range(12):
        spec = task(i, 'confirmation', MODES[i % 4]); world = EyeHandWorld.restore(state)
        world.set_scene(spec['items'], positions=spec['positions'])
        for slot in (spec['slot'], spec['following_slot']):
            for pose in ('common_start', 'teacher_aligned'):
                world.eye_angle = np.asarray(state['eye_angle']) if pose == 'common_start' else teacher_eye_angle(world, spec['positions'][slot])
                world._refresh_directions()
                world.marker = None; absent = np.asarray(world.vision()['values'])
                world.marker = spec['positions'][slot]; present = np.asarray(world.vision()['values'])
                delta = np.abs(present-absent).reshape(-1, 4)
                results.append({'trial': i, 'mode': spec['mode'], 'slot': slot, 'pose': pose,
                    'changed_receptors': int(np.sum(np.any(delta > 1e-8, axis=1))),
                    'largest_optical_difference': float(delta.max())})
    summary = {pose: {'visible': sum(r['changed_receptors'] > 0 for r in results if r['pose']==pose),
                       'total': sum(r['pose']==pose for r in results)} for pose in ('common_start','teacher_aligned')}
    value = {'schema':'threemind.eye-marker-audit/1', 'results': results, 'summary': summary,
             'scope':'apparatus at common start or teacher-aligned pose; no Core, no dynamics or input changes',
             'wall_seconds':time.monotonic()-started}
    new_json(WORK/'marker-visibility.json', value); print(json.dumps(value))


if __name__ == '__main__': main()
