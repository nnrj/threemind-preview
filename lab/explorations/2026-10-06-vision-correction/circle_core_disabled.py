"""E55 interval control: simulate the physical world without creating a Core.

Only the published teacher schedule sets external scene/marker changes. Recorded
positions and activities are loaded AFTER the physical trajectory is generated,
and are used solely for comparison. No controller or recorded force is applied.
"""
from dataclasses import asdict
import gzip
import json
import math
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import psutil
from lab.tools.grounded_classroom import GroundedClassroom
from lab.tools.shape_color_world import POSITIONS

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/vision-correction-20261006'
OLD = ROOT / '.work/grounded-reviews-20261006'
DT_US = 50_000
GIB = 2**30


def compare(rows, reference):
    if not rows:
        raise ValueError('empty comparison')
    pairs = [(row, reference[row['time_us']]) for row in rows]
    return {
        'samples': len(pairs),
        'simulation_seconds': [rows[0]['time_us']/1e6, rows[-1]['time_us']/1e6],
        'max_pointer_distance_m': max(math.dist(
            [r['pointer_before']['x'], r['pointer_before']['y']], f['p']) for r, f in pairs),
        'max_physical_background_difference': {
            k: max(abs(r['physical_background'][k]-f['body'][k]) for r, f in pairs)
            for k in rows[0]['physical_background']},
        'scene_mismatches': sum(r['items'] != f['items'] for r, f in pairs),
        'marker_mismatches': sum(r['teacher_marker'] != f['marker'] for r, f in pairs),
        'reference_explicit_motor_commands': sum(f['force'] is not None for _, f in pairs),
    }


def main():
    result_path = HERE / 'circle-core-disabled.json'
    trajectory_path = WORK / 'circle-core-disabled-trajectory.jsonl.gz'
    if result_path.exists() or trajectory_path.exists():
        raise FileExistsError('preserve the recorded control')
    started = time.monotonic()
    schedule_path = OLD / 'cases/s223-spaced-teaching/schedule.json'
    schedule = json.loads(schedule_path.read_bytes())
    world = GroundedClassroom(seed=91, weather_seed=47)
    initial_state = world.state()
    rows = []

    def tick():
        if len(rows) % 128 == 0:
            if time.monotonic()-started > 120 or len(rows) >= 11_000:
                raise RuntimeError('physics-only time/step budget')
            if psutil.virtual_memory().available < 2*GIB or psutil.Process().memory_info().rss > 4*GIB:
                raise RuntimeError('physics-only memory budget')
            if shutil.disk_usage('E:/').free < 15*GIB or shutil.disk_usage('C:/').free < 5*GIB:
                raise RuntimeError('physics-only disk reserve')
        observation = world.observe()
        rows.append({'time_us': (len(rows)+1)*DT_US,
                     'observed_at_us': len(rows)*DT_US,
                     'pointer_before': asdict(world.pointer),
                     'physical_background': observation['physical_background'],
                     'items': [list(p) for p in world.items], 'variant': world.variant,
                     'teacher_marker': world.marker, 'motor_force': [0., 0.]})
        world.advance_physics(action=(0., 0.), dt=DT_US/1e6)
        # E55 uses its integer simulation clock here, not accumulated floats.
        world.time_s = len(rows)*DT_US/1e6

    for task in schedule:
        world.set_scene([(i, 4) for i in range(4)])
        world.marker = None
        while len(rows)*DT_US < task['time_us']:
            tick()
        if len(rows)*DT_US != task['time_us']:
            raise ValueError('teacher schedule outside the physical clock')
        world.set_scene(task['items'], task['variant'])
        world.marker = list(POSITIONS[task['slot']])
        for _ in range(30):
            tick()
    # The independently generated trajectory is frozen before reading references.
    with gzip.open(trajectory_path, 'xt', encoding='utf-8') as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n')
    if trajectory_path.stat().st_size > 16*2**20:
        raise RuntimeError('physics-only output budget')

    source = OLD / 'complete-media/complete-replay.json'
    data = json.loads(source.read_bytes())
    references = {}
    for chapter in data['chapters']:
        if chapter['kind'] == 'teaching' and chapter['case'] in (
                's223-spaced-teaching', 's223-frozen-teaching'):
            references[chapter['case']] = {
                round(f['t']*1e6): f for clip in chapter['clips'] for f in clip['frames']}
    expected_times = {r['time_us'] for r in rows}
    if any(set(ref) != expected_times for ref in references.values()) or len(references) != 2:
        raise ValueError('full-course time alignment mismatch')
    audit = json.loads((HERE/'circle-audit.json').read_bytes())
    windows = []
    for window in audit['windows']:
        lo, hi = [round(t*1e6) for t in window['simulation_seconds']]
        selected = [r for r in rows if lo <= r['time_us'] <= hi]
        case = window['chapters'][0]['case']
        windows.append({'video_seconds': window['video_seconds'], 'reference_case': case,
                        **compare(selected, references[case])})
    result = {
        'schema': 'threemind.circle-physical-control/1', 'recorded_on': '2026-10-06',
        'core_instances_created': 0, 'core_advanced': False,
        'recorded_trajectory_used_as_control': False,
        'recorded_activity_used_as_control': False,
        'control': 'Core absent; physical world, initial body state, teacher scene schedule and weather retained; motor force zero',
        'comparison_alignment': 'As in E55, frame time denotes end of step; displayed pointer and physical measurements were observed before that step.',
        'initial_physical_state': initial_state,
        'schedule': str(schedule_path.relative_to(ROOT)),
        'reference': str(source.relative_to(ROOT)),
        'trajectory': str(trajectory_path.relative_to(ROOT)),
        'full_course': {case: compare(rows, ref) for case, ref in references.items()},
        'user_windows': windows,
        'simulated_seconds': world.time_s, 'physical_steps': len(rows),
        'wall_seconds': time.monotonic()-started, 'trajectory_bytes': trajectory_path.stat().st_size,
    }
    with result_path.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
