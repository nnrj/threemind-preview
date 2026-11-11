"""E62 bounded whole-system development; no kernel edits or controller swaps."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from curriculum import schedule, cursor, validate_cursor
import numpy as np
import psutil
import torch
from lab.tools.service_study import Study, StudyConfig, encoded, read_json, new_json
from lab.tools.developmental_session import DevelopmentalSession
from lab.tools.eye_hand_world import teacher_eye_angle
from lab.tools.sensorimotor_session import activity_totals, growth_summary, SensorimotorSession
from lab.tools.activity_controller import ActivityLayout
from lab.tools.continuous_motor import recent_window

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/continuous-development-20261007'
MODES = ('look', 'point', 'both')
TARGETS = ((-.55, -.55), (.55, -.55), (-.55, .55), (.55, .55))


class BoundedStudy(Study):
    def guard(self, force=False):
        super().guard(force)
        if force or not hasattr(self, 'failed_wall'):
            self.failed_wall = sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('*/stopped.json')
                if not (p.parent/'result.json').exists())
        active = time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+self.failed_wall+active > self.settings.wall_seconds:
            raise RuntimeError('total computation limit, including failures')

    def allow_extension(self):
        super().allow_extension()
        if self.completed_wall+self.failed_wall >= 5400:
            raise RuntimeError('90 minute expansion limit')


def study(prepare=False):
    from urllib.parse import urlsplit
    from threemind_lab.config import Settings
    url = urlsplit(Settings.from_env().database_url)
    if url.hostname not in ('localhost', '127.0.0.1') or url.port != 5433 or url.path != '/threemind':
        raise RuntimeError('only the authorized local ThreeMind database')
    return BoundedStudy(StudyConfig('continuous-development/1', 'E62 完整意识与运动外设连续成长重试', HERE, WORK, 14,
        instance_limit=96, wall_seconds=9000, storage_soft=3*2**30, storage_hard=4*2**30,
        usage_soft_delta=4, usage_hard_delta=6), prepare=prepare)


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.6)
        return 'cuda'
    return 'cpu'


def count_instance():
    p = WORK/'instances.json'; n = read_json(p)['created']
    if n >= 96: raise RuntimeError('creation/restore budget')
    p.write_bytes(encoded({'created': n+1}))


def restore(path, **kwargs):
    count_instance(); return DevelopmentalSession.restore(path, device=device(), **kwargs)


def run(s, key, operation):
    p = WORK/'cases'/key
    if (p/'result.json').exists():
        print(json.dumps({'already_complete': key})); return read_json(p/'result.json')
    if p.exists(): raise RuntimeError('preserve incomplete case; register a recovery branch: '+key)
    s.guard(True); p.mkdir(parents=True); start = time.monotonic()
    files = [ROOT/'lab/tools'/n for n in ('developmental_motor.py', 'developmental_world.py', 'developmental_session.py',
        'sensorimotor_session.py', 'active_eye.py', 'body_playground.py')]
    hashes = {f.relative_to(ROOT).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    signature = hashlib.sha256(encoded(hashes)).hexdigest(); dest = WORK/'tool-revisions'/signature
    if not dest.exists():
        for f in files:
            out = dest/f.relative_to(ROOT); out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, out)
        new_json(dest/'manifest.json', hashes)
    new_json(p/'started.json', {'epoch': time.time(), 'tools': signature, 'runner': s.runner_signature})
    s.active_case = SimpleNamespace(born_wall=start)
    try:
        value = operation(p) | {'wall_seconds': time.monotonic()-start, 'tools': signature, 'runner': s.runner_signature}
        new_json(p/'result.json', value); s.active_case = None
        s.completed_count += 1; s.completed_wall += value['wall_seconds']
        print(json.dumps({'case': key, **value}, ensure_ascii=False), flush=True)
        return value
    except Exception as e:
        new_json(p/'stopped.json', {'error': str(e), 'wall_seconds': time.monotonic()-start,
            'process_rss_bytes': psutil.Process().memory_info().rss,
            'available_memory_bytes': psutil.virtual_memory().available}); raise


def record(stream, phase, index, rows, **metadata):
    stream.write(encoded({'phase': phase, 'index': index, **metadata, 'process': rows}).decode()+'\n')


def score(rows, eye_target, hand_target, mode):
    eyes = np.array([r['observation']['eye_angle_rad'] for r in rows])
    hands = np.array([[r['pointer_after'][k] for k in ('x', 'y')] for r in rows])
    ee = np.linalg.norm(eyes-eye_target, axis=1); he = np.linalg.norm(hands-hand_target, axis=1)
    valid = (ee <= .075 if mode != 'point' else np.ones(len(rows), dtype=bool)) & (he <= .20 if mode != 'look' else np.ones(len(rows), dtype=bool))
    start_hand = [rows[0]['observation']['pointer'][k] for k in ('x', 'y')]
    starts_inside = (ee[0] <= .075 if mode != 'point' else True) and (np.linalg.norm(np.asarray(start_hand)-hand_target) <= .20 if mode != 'look' else True)
    return {'mode': mode, 'eye_end_error_rad': float(ee[-1]), 'hand_end_error_m': float(he[-1]),
        'eye_min_error_rad': float(ee.min()), 'hand_min_error_m': float(he.min()),
        'ever_reached': bool(valid.any()), 'end_reached': bool(valid[-1]), 'residence_s': float(valid.sum()*.05),
        'eye_error_reduction': float(ee[0]-ee[-1]), 'hand_error_reduction': float(he[0]-he[-1]),
        'first_reached_s': float(np.flatnonzero(valid)[0]*.05) if valid.any() else None,
        'starts_inside': bool(starts_inside), 'reached_from_outside': bool(not starts_inside and valid.any()),
        'new_entries': int(np.sum(~np.r_[starts_inside, valid[:-1]] & valid))}


def lesson(s, organism, mode, target_index, *, seconds=2.5, assistance=0., learning=False, corrective=False, cue_seconds=.75):
    c, w = organism.session, organism.session.world
    point = np.asarray(TARGETS[target_index]); start_hand = np.array([w.pointer.x, w.pointer.y]); start_eye = w.eye_angle.copy()
    eye = teacher_eye_angle(w, point) if mode != 'point' else start_eye
    hand = point if mode != 'look' else start_hand
    target_pose = np.r_[eye/w.eye_config.angle_limit_rad, hand].clip(-1, 1)
    text = {'look': '用眼睛看这里，手先不动。', 'point': '用手指这里，眼睛先不动。', 'both': '用眼睛看这里，也用手指这里。'}[mode]
    frames = list(c.sensor.frames(('再示范一次。' if corrective else '')+text))
    rows = []
    for i in range(round(seconds/.05)):
        w.marker = point.tolist() if i*.05 < cue_seconds or learning else None
        rows.append(organism.step(frames[i] if i < len(frames) else None,
            teacher_pose=target_pose if learning or assistance else None, assistance=assistance,
            learn=learning and i % 4 == 0, guard=s.guard))
    w.marker = None
    return rows, score(rows, eye, hand, mode) | {'target_index': target_index, 'eye_target': eye.tolist(),
        'hand_target': hand.tolist(), 'text': text, 'assistance': assistance, 'learning': learning,
        'cue_seconds':seconds if learning else cue_seconds}


def wait(s, obj, seconds, *, variation=0., passive=False):
    return [obj.step(variation=variation, passive=passive, guard=s.guard) for _ in range(round(seconds/.05))]


def birth(s, seed):
    def operation(p):
        count_instance(); a = DevelopmentalSession(seed=seed, identity=f'e62-source-{seed}', device=device())
        a.save(p/'system')
        return {'seed': seed, 'identity': a.identity, 'device': str(next(a.motor.parameters()).device), 'parameters': sum(x.numel() for x in a.motor.parameters())}
    return run(s, f'birth-{seed}', operation)


def develop(s, seed, group, resume_from=None):
    key = f's{seed}-{group}-aligned'
    if resume_from is not None:
        resume_from = Path(resume_from).resolve()
        if not resume_from.is_relative_to((WORK/'cases').resolve()):
            raise ValueError('resume only an explicit snapshot in this study')
        key += '-resume-'+resume_from.name
    def operation(p):
        if resume_from is None:
            a = restore(WORK/f'cases/birth-{seed}/system', branch=group); start_step = 0
        else:
            start_step = validate_cursor(read_json(resume_from/'curriculum.json'), group)
            a = restore(resume_from)
            if a.identity != f'e62-source-{seed}/{group}':
                raise ValueError('resume individual does not match declared seed and group')
        def checkpoint(name, next_step):
            a.save(p/name)
            new_json(p/name/'curriculum.json', cursor(group, next_step))
        if group == 'direct' and start_step == 0:
            checkpoint('before-teaching', 0)
        plan = schedule(group)
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as stream:
            for index in range(start_step, len(plan)):
                task = plan[index]; a.phase = task['phase']; result = None
                if task['kind'] == 'lesson':
                    rows, result = lesson(s, a, task['mode'], task['target'], assistance=task['assistance'], learning=True)
                    record(stream, a.phase, index, rows, trial=result)
                else:
                    rows = wait(s, a, task['seconds'], variation=task.get('variation', 0.), passive=task.get('passive', False))
                    record(stream, a.phase, index, rows)
                if task['checkpoint']:
                    checkpoint(task['checkpoint'], index+1)
                    stream.flush()
                    print(json.dumps({'stage': key, 'checkpoint': task['checkpoint'], 'next_step': index+1,
                        'time_s': a.session.engine.time_us/1e6, 'steps': a.motor.steps, 'recent': result}), flush=True)
            a.phase = 'taught'; checkpoint('system', len(plan))
        return {'seed': seed, 'group': group, 'identity': a.identity, 'motor_steps': a.motor.steps,
            'examples_seen': a.motor.examples_seen, 'lessons': 156, 'sim_seconds': a.session.engine.time_us/1e6,
            'contacts': a.session.world.contact_count, 'growth': growth_summary(a.session.snapshot()),
            'device': str(next(a.motor.parameters()).device), 'peripheral_replacements': 0,
            'preschool_peripheral_updates': 0, 'whole_system_checkpoint': str(p/'system'),
            'resume_from': str(resume_from) if resume_from else None, 'resumed_at_step': start_step,
            'schedule': cursor(group, len(plan))}
    return run(s, key, operation)


def evaluate(s, seed, group, mode, checkpoint='system', count=12, after_correction=False, source_case=None, cue_seconds=.75):
    source = source_case or f's{seed}-{group}-aligned'+('-correction' if after_correction else '')
    if Path(source).name != source or not source.startswith(f's{seed}-{group}-aligned'):
        raise ValueError('evaluation source must be a declared case for this individual')
    key = f'{source}-{checkpoint}'+('-visible-cue' if cue_seconds == 4. else '')+f'-{mode}'
    def operation(p):
        a = restore(WORK/'cases'/source/checkpoint, branch='evaluation-'+mode)
        original_steps = a.motor.steps; a.phase = 'evaluation'
        state = a.session.engine.capture_state().to_dict()
        edges = [(e['source'], e['target']) for e in state['edges']]
        if mode in ('silence', 'rescue'):
            a.session.engine.intervene(edges=edges, action='silence')
            if mode == 'rescue': a.session.engine.intervene(edges=edges, action='unsilence')
        scores = []
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as stream:
            order = np.random.default_rng(62411).permutation(12)[:count]
            for i, index in enumerate(order):
                rows, result = lesson(s, a, MODES[index//4], int(index%4), seconds=4., cue_seconds=cue_seconds)
                scores.append(result); record(stream, a.phase, i, rows, trial=result)
                print(json.dumps({'case': key, 'trial': i, **result}), flush=True)
        assert a.motor.steps == original_steps
        new_json(p/'scores.json', scores); a.save(p/'system')
        return {'seed': seed, 'group': group, 'mode': mode, 'checkpoint': checkpoint, 'n': len(scores),
            'ever_reached': sum(r['ever_reached'] for r in scores), 'end_reached': sum(r['end_reached'] for r in scores),
            'mean_eye_error_rad': float(np.mean([r['eye_end_error_rad'] for r in scores if r['mode'] != 'point'])),
            'mean_hand_error_m': float(np.mean([r['hand_end_error_m'] for r in scores if r['mode'] != 'look'])),
            'motor_steps': a.motor.steps, 'silenced_edges': len(edges) if mode != 'normal' else 0,
            'whole_system_checkpoint': str(p/'system'), 'cue_seconds':cue_seconds}
    return run(s, key, operation)


def correct(s, seed, group):
    """Try first, then teach the same ongoing individual after its own errors."""
    key = f's{seed}-{group}-aligned-correction'
    def operation(p):
        a = restore(WORK/f'cases/s{seed}-{group}-aligned/system')
        a.phase = 'corrective-practice'; before = a.motor.steps; scores = []; corrections = 0
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as stream:
            for i, index in enumerate(np.random.default_rng(62497).permutation(12)):
                mode, target = MODES[index//4], int(index%4)
                rows, result = lesson(s, a, mode, target, seconds=4.)
                scores.append(result); record(stream, 'try-yourself', i, rows, trial=result)
                if not result['end_reached']:
                    corrections += 1
                    for rep, assistance in enumerate((.7, .4, .1)):
                        rows, feedback = lesson(s, a, mode, target, assistance=assistance, learning=True, corrective=True)
                        record(stream, 'teacher-correction', i*3+rep, rows, trial=feedback)
                    record(stream, 'correction-gap', i, wait(s, a, 2.))
            a.phase = 'after-correction'; a.save(p/'system')
        return {'seed':seed, 'group':group, 'corrected_trials':corrections, 'attempts':len(scores),
            'own_attempts_end_reached':sum(r['end_reached'] for r in scores), 'steps_before':before,
            'motor_steps':a.motor.steps, 'sim_seconds':a.session.engine.time_us/1e6,
            'whole_system_checkpoint':str(p/'system'), 'peripheral_replacements':0}
    return run(s, key, operation)


def reference(s):
    from lab.tools.spatial_choice import SpatialChoice
    from lab.tools.shape_color_world import Pointer, POSITIONS
    base = ROOT/'.work/vision-correction-20261006/cases'
    def operation(p):
        with gzip.open(base/'r4-exposure/checkpoint.json.gz', 'rt', encoding='utf-8') as f: state = json.load(f)
        head, layout = SpatialChoice.restore(base/'r4-exposure-shared-fit/controller', device())
        tasks = read_json(ROOT/'lab/explorations/2026-10-06-vision-correction/confirmation-tasks.json')
        scores = []
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as stream:
            for index in (0, 3, 8, 11, 16, 19):
                task = tasks[index]; count_instance()
                c = SensorimotorSession(state=state | {'dt_us': 50000})
                c.world.set_scene(task['items'], task['variant']); c.world.marker = None
                c.world.pointer = Pointer(*task['start']); c.world.acceleration = [0., 0.]; c.world.motor_power = 0.
                frames = list(c.sensor.frames(task['text']))
                rows = [c.tick(frame, guard=s.guard) for frame in frames]
                rows += [c.tick(guard=s.guard) for _ in range(max(0, 20-len(rows)))]
                # Preserve the original E56 eight evenly spaced samples.
                indices = np.rint(np.linspace(0, len(rows)-1, 8)).astype(int)
                x = np.stack([layout.frame(rows[i]['activity']) for i in indices])
                selected = int(head.predict(x[None]).argmax(-1)[0])
                for _ in range(40):
                    rows.append(c.tick(hand=c.world.pointer.teacher_action(POSITIONS[selected]), guard=s.guard))
                error = float(np.linalg.norm(np.array([c.world.pointer.x, c.world.pointer.y])-POSITIONS[task['slot']]))
                result = {'category': task['category'], 'slot': task['slot'], 'selected': selected, 'correct': selected == task['slot'], 'reached': error <= .15, 'error_m': error}
                scores.append(result); record(stream, 'original-e56-assembly', index, rows, trial=result)
        new_json(p/'scores.json', scores)
        return {'n': len(scores), 'correct': sum(r['correct'] for r in scores), 'reached': sum(r['reached'] for r in scores),
            'scope': 'original evaluation assembly, not reconstruction of missing historical training state'}
    return run(s, 'e56-reference', operation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'reference', 'birth', 'develop', 'evaluate', 'correct'))
    parser.add_argument('--seed', type=int, choices=(223, 279), default=223)
    parser.add_argument('--group', choices=('explore', 'quiet', 'direct'), default='explore')
    parser.add_argument('--mode', choices=('normal', 'silence', 'rescue'), default='normal')
    parser.add_argument('--checkpoint', choices=('preschool', 'before-teaching', 'initial-teaching', 'review-1', 'review-2', 'system'), default='system')
    parser.add_argument('--after-correction', action='store_true')
    parser.add_argument('--resume-from', type=Path, help='Complete E62 snapshot with its saved curriculum cursor')
    parser.add_argument('--source-case', help='Explicit completed development/resume case for evaluation')
    parser.add_argument('--cue-seconds', type=float, choices=(.75,4.), default=.75, help='Primary brief cue or declared visible-cue calibration control')
    args = parser.parse_args(); s = study(args.command == 'prepare')
    try:
        if args.command == 'prepare':
            new_json(WORK/'usage.json', {'used_percent': 14}); new_json(WORK/'instances.json', {'created': 0}); s.guard(True)
            print(json.dumps({'project': s.project, 'storage_bytes': s.storage_bytes}), flush=True)
        else:
            s.allow_extension()
            if args.command == 'reference': reference(s)
            elif args.command == 'birth': birth(s, args.seed)
            elif args.command == 'develop': develop(s, args.seed, args.group, args.resume_from)
            elif args.command == 'correct': correct(s, args.seed, args.group)
            else: evaluate(s, args.seed, args.group, args.mode, args.checkpoint, after_correction=args.after_correction, source_case=args.source_case, cue_seconds=args.cue_seconds)
    finally: s.db.close()


if __name__ == '__main__': main()
