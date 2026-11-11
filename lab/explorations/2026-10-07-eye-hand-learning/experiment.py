"""E60: bounded teacher-led eye/hand learning, correction and causal controls.

python .../experiment.py prepare|calibrate|teach|validation|fit|evaluate|correct
Each case is append-only and resumable. No test task enters adapter inference.
"""
import argparse
from collections import deque
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from lab.tools.eye_hand_world import EyeHandWorld, teacher_eye_angle, motor_metrics
from lab.tools.continuous_motor import ContinuousMotor, recent_window
from lab.tools.sensorimotor_session import SensorimotorSession, activity_totals, growth_summary
from lab.tools.shape_color_world import POSITIONS, COLORS
from lab.tools.service_study import Study, StudyConfig, new_json, read_json, write_gzip, encoded

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/eye-hand-learning-20261007'
MODES = ('look', 'point', 'both', 'hold')
WORDS = {'look': '看这里，手先不动。', 'point': '用手指这里，眼睛先不动。',
         'both': '看这里，也用手指这里。', 'hold': '保持现在的位置。'}
PROVENANCE = {'teacher': '教师辅助：眼手均由教师示范控制', 'normal': '意识活动驱动：学习外设输出眼手力',
    'silence': '既有连接静默：学习外设读取干预后的活动', 'rescue': '既有连接解除静默：同一学习外设',
    'empty': '切断输出：眼手命令均为零，保留物理惯性和感觉',
    'incoming': '直接入射对照：明确绕过Core，不算意识控制'}


def read_gzip(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f: return json.load(f)


class BoundedStudy(Study):
    def guard(self, force=False):
        super().guard(force)
        if force:
            self.failed_wall = sum(read_json(p)['wall_seconds'] for p in (self.work/'cases').glob('*/stopped.json'))
        active = time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+getattr(self, 'failed_wall', 0)+active > self.settings.wall_seconds:
            raise RuntimeError('aggregate compute including failed attempts')


def study(prepare=False):
    return BoundedStudy(StudyConfig('eye-hand-learning/1', 'E60 学习转眼、注视与眼手协调', HERE, WORK, 0,
        instance_limit=256, wall_seconds=9000, storage_soft=6*2**30, storage_hard=8*2**30,
        usage_soft_delta=5, usage_hard_delta=8), prepare=prepare)


def instance(s, **kwargs):
    path = WORK/'instances.json'; n = read_json(path)['created']
    if n >= s.settings.instance_limit: raise RuntimeError('created/restored instance limit')
    path.write_bytes(encoded({'created': n+1}))
    return SensorimotorSession(**kwargs)


def run(s, key, execute):
    path = WORK/'cases'/key
    if (path/'result.json').exists(): return read_json(path/'result.json')
    if path.exists(): raise RuntimeError('preserve incomplete case; use a new registered case: '+key)
    s.guard(True); path.mkdir(parents=True); start = time.monotonic()
    # Small source files only. Preserve the tool revision used by each case,
    # without rehashing trajectories, snapshots or unrelated historical data.
    sources = [ROOT/'lab/tools'/n for n in ('continuous_motor.py', 'eye_hand_world.py', 'sensorimotor_session.py')]
    versions = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    tool_revision = hashlib.sha256(encoded(versions)).hexdigest()
    revision = WORK/'tool-revisions'/tool_revision
    if not revision.exists():
        revision.mkdir(parents=True)
        for source in sources: shutil.copy2(source, revision/source.name)
        new_json(revision/'manifest.json', versions)
    s.active_case = SimpleNamespace(born_wall=start)
    new_json(path/'started.json', {'epoch': time.time(), 'runner_signature': s.runner_signature, 'tool_revision': tool_revision})
    try:
        result = execute(path) | {'wall_seconds': time.monotonic()-start, 'runner_signature': s.runner_signature, 'tool_revision': tool_revision}
        new_json(path/'result.json', result)
        s.active_case = None; s.completed_count += 1; s.completed_wall += result['wall_seconds']
        print(json.dumps({'case': key, **{k: v for k, v in result.items() if k not in ('trials', 'lessons')}}, ensure_ascii=False), flush=True)
        return result
    except Exception as error:
        new_json(path/'stopped.json', {'error': str(error), 'wall_seconds': time.monotonic()-start})
        raise


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.60)
        return 'cuda'
    return 'cpu'


def curriculum():
    result = []; start = 0.
    for mode in MODES:
        onsets = [start+3*i for i in range(10)]
        for gap in (6., 12., 24.): onsets.append(onsets[-1]+gap)
        result.extend({'mode': mode, 'repeat': i, 'onset_s': onset} for i, onset in enumerate(onsets))
        start = onsets[-1]+3.
    return result


def task(index, split='train', mode=None):
    seed = {'train': 6001, 'validation': 6043, 'practice': 6079, 'test': 6101, 'confirmation': 6131}[split]
    rng = np.random.default_rng(seed+index*17)
    shapes = rng.permutation(4); colors = rng.permutation(4)
    positions = np.asarray(POSITIONS)+rng.uniform(-.07, .07, (4, 2))
    selected = int(rng.integers(4)); following = (selected+1+int(rng.integers(3))) % 4
    return {'index': index, 'split': split, 'mode': mode or MODES[index//4 % 4],
        'text': WORDS[mode or MODES[index//4 % 4]], 'items': list(zip(shapes.tolist(), colors.tolist())),
        'positions': positions.tolist(), 'slot': selected, 'following_slot': following}


def set_task(c, spec):
    c.world.set_scene(spec['items'], positions=spec['positions'])
    c.world.marker = spec['positions'][spec['slot']]
    return c.world.eye_angle.copy(), np.array([c.world.pointer.x, c.world.pointer.y])


def targets(world, spec, eye_start, hand_start, slot=None):
    point = spec['positions'][spec['slot'] if slot is None else slot]
    return (teacher_eye_angle(world, point) if spec['mode'] in ('look', 'both') else eye_start,
            np.asarray(point) if spec['mode'] in ('point', 'both') else hand_start)


def guide(world, eye_target, hand_target):
    return np.concatenate((world.eye_servo(eye_target), world.pointer.teacher_action(hand_target)))


def pack_features(samples, path):
    if not samples: raise ValueError('no supervision samples')
    np.savez_compressed(path, activity=np.stack([x[0] for x in samples]), incoming=np.stack([x[1] for x in samples]),
                        y=np.stack([x[2] for x in samples]))


def lesson(s, c, spec, *, assist=True, head=None, seconds=3., corrective=False, cue='brief', retarget=False,
           intervention='normal', input_source='activity'):
    eye_start, hand_start = set_task(c, spec)
    frames = list(c.sensor.frames(('再示范一次。'+spec['text']) if corrective else spec['text']))
    rows = []; samples = []; eye_targets = []; hand_targets = []
    for i in range(round(seconds/.05)):
        changed = retarget and i >= round(seconds/.1)
        slot = spec['following_slot'] if changed else spec['slot']
        elapsed = i*.05-(seconds/2 if changed else 0.)
        c.world.marker = spec['positions'][slot] if cue == 'visible' or (cue == 'brief' and elapsed < .8) else None
        et, ht = targets(c.world, spec, eye_start, hand_start, slot)
        desired = guide(c.world, et, ht) if assist else None
        if not c.history or i == 0:
            command = np.zeros(4)
        elif assist:
            command = desired
        elif intervention == 'empty':
            command = np.zeros(4)
        else:
            command = head.action(recent_window(c.layout, c.history, incoming=input_source == 'incoming'))
        # Only earlier observed output is included; never pair a label with its
        # later mechanical consequence as if that consequence predicted it.
        if assist and c.history and i > 0 and (i < 10 or i % 2 == 0):
            samples.append((recent_window(c.layout, c.history), recent_window(c.layout, c.history, incoming=True), desired))
        if changed and i == round(seconds/.1):
            frames = list(c.sensor.frames(spec['text']))
        j = i-round(seconds/.1) if changed else i
        row = c.tick(frames[j] if j < len(frames) else None, eye=command[:2], hand=command[2:], guard=s.guard)
        row['action_source'] = PROVENANCE['teacher' if assist else 'incoming' if input_source == 'incoming' else intervention]
        rows.append(row); eye_targets.append(et.tolist()); hand_targets.append(ht.tolist())
    result = motor_metrics(rows, eye_targets, hand_targets)
    for label, start, end in [('late', max(0, len(rows)//2-20), len(rows)//2), ('retarget_late', len(rows)-20, len(rows))]:
        result[label] = motor_metrics(rows[start:end], eye_targets[start:end], hand_targets[start:end])
    result['associative_integral'] = sum(activity_totals(r)['associative'] for r in rows)*.05
    result['eye_final'] = c.world.eye_angle.tolist(); result['hand_final'] = [c.world.pointer.x, c.world.pointer.y]
    result['mode'] = spec['mode']
    record = {'task': spec, 'kind': 'teacher' if assist else 'test', 'process': rows, 'result': result,
              'scoring_only_eye_targets': eye_targets, 'scoring_only_hand_targets': hand_targets,
              'action_source': rows[0]['action_source'], 'cue': cue}
    return record, samples


def calibrate(s):
    def execute(p):
        results = []
        for nose in (False, True):
            world = EyeHandWorld(nose=nose)
            for xy in POSITIONS:
                eye_target = teacher_eye_angle(world, xy)
                for _ in range(80): world.advance_physics(world.pointer.teacher_action(xy), eye_action=world.eye_servo(eye_target))
                results.append({'nose': nose, 'target': xy, 'eye_error': float(np.linalg.norm(world.eye_angle-eye_target)),
                    'speed': float(np.linalg.norm(world.eye_velocity)), 'hand_distance': float(np.linalg.norm(np.array([world.pointer.x, world.pointer.y])-xy))})
        return {'mechanical': results, 'pass': all(x['eye_error'] < .01 and x['speed'] < .01 and x['hand_distance'] < .2 for x in results)}
    return run(s, 'A-apparatus', execute)


def teach(s, nose=False):
    key = 'B-teach'+('-nose' if nose else '')
    def execute(p):
        c = instance(s, world=EyeHandWorld(nose=nose)); data = []; records = []; schedule = curriculum()
        write_gzip(p/'initial.json.gz', c.snapshot()); new_json(p/'layout.json', c.layout.channels)
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as out:
            for index, item in enumerate(schedule):
                interval = []
                while c.world.time_s+1e-6 < item['onset_s']:
                    c.world.marker = None
                    row = c.tick(guard=s.guard); row['action_source'] = '复习间隔：无运动命令，完整环境和身体反馈持续'
                    interval.append(row)
                if interval: out.write(encoded({'kind': 'interval', 'process': interval}).decode()+'\n')
                spec = task(index, mode=item['mode']) | item
                record, samples = lesson(s, c, spec)
                data.extend(samples); out.write(encoded(record).decode()+'\n')
                records.append(item | {'actual_onset_s': record['process'][0]['observation']['time_s'], 'result': record['result']})
                if index % 5 == 0:
                    print(json.dumps({'stage': key, 'lesson': index+1, 'of': len(schedule), 'sim_s': c.world.time_s}), flush=True)
        pack_features(data, p/'features.npz'); write_gzip(p/'checkpoint.json.gz', c.snapshot())
        new_json(p/'schedule.json', records)
        return {'nose': nose, 'lessons': records, 'lesson_count': len(records), 'samples': len(data), **growth_summary(c.snapshot())}
    return run(s, key, execute)


def demonstrations(s, source, count=12):
    def execute(p):
        c = instance(s, state=read_gzip(WORK/'cases'/source/'checkpoint.json.gz')); data = []
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as out:
            for i in range(count):
                spec = task(i, 'validation', MODES[i % 4]); record, samples = lesson(s, c, spec)
                out.write(encoded(record).decode()+'\n'); data.extend(samples)
        pack_features(data, p/'features.npz')
        return {'demonstrations': count, 'samples': len(data), 'source': source}
    return run(s, 'B-validation-'+source, execute)


def fit(s, source, organization='shared', kind='activity', correction=None, steps=1600, readout_version=1, mixed_validation=False):
    key = f'C-fit-{source}-{organization}-{kind}-fit2'+('-'+correction if correction else '')
    if readout_version != 1: key += f'-v{readout_version}'
    if mixed_validation: key += '-val2'
    if steps != 1600: key += f'-s{steps}'
    def execute(p):
        base = np.load(WORK/'cases'/source/'features.npz')
        x, y = base[kind], base['y']
        if correction:
            more = np.load(WORK/'cases'/correction/'features.npz')
            x = np.concatenate((x, more[kind])); y = np.concatenate((y, more['y']))
        val = np.load(WORK/'cases'/('B-validation-'+source)/'features.npz')
        vx, vy = val[kind], val['y']
        if mixed_validation:
            if not correction: raise ValueError('post-correction validation needs a corrected student')
            later = np.load(WORK/'cases'/('B-validation-'+correction)/'features.npz')
            vx = np.concatenate((vx, later[kind])); vy = np.concatenate((vy, later['y']))
        layout = read_json(WORK/'cases'/source/'layout.json')
        head = ContinuousMotor(layout, organization=organization, seed=223, readout_version=readout_version).to(device())
        fitted = head.fit(x, y, validation=(vx, vy), steps=steps, check=s.guard)
        head.save(p/'controller', input_source=kind)
        train_error = sum(float(np.sum((head.predict(x[j:j+32])-y[j:j+32])**2)) for j in range(0, len(x), 32))/(len(x)*4)
        return {'fit': fitted, 'training_mse': train_error, 'source': source, 'organization': organization, 'input_source': kind, 'correction': correction,
                'validation_sources': [source, correction] if mixed_validation else [source]}
    return run(s, key, execute)


def summarize(results):
    fields = ('eye_mean_error_rad', 'eye_center_fraction', 'eye_stable_fraction', 'eye_longest_stable_s',
              'hand_mean_distance_m', 'hand_arrived_fraction', 'associative_integral')
    summary = {key: float(np.mean([r[key] for r in results])) for key in fields}
    summary['by_mode'] = {m: {k: float(np.mean([r[k] for r in results if r['mode'] == m])) for k in fields}
                          for m in MODES if any(r['mode'] == m for r in results)}
    return summary


def evaluate(s, source, model, *, mode='normal', kind='activity', cue='brief', split='test', count=16, suffix='', world_reference=None):
    key = f'D-{source}-{model}-{mode}-{cue}-{split}'+suffix
    if world_reference: key += '-world-'+world_reference
    def execute(p):
        saved = read_gzip(WORK/'cases'/source/'checkpoint.json.gz')
        reference_world = read_gzip(WORK/'cases'/world_reference/'checkpoint.json.gz')['world'] if world_reference else None
        head = ContinuousMotor.restore(WORK/'cases'/model/'controller', device())
        if read_json(WORK/'cases'/model/'controller/manifest.json')['input_source'] != kind:
            raise ValueError('reader input source mismatch; activity and bypass are not interchangeable')
        results = []; contexts = []; saved_first = False
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as out:
            for i in range(count):
                c = instance(s, state=saved)
                if reference_world:
                    replayed = EyeHandWorld.restore(reference_world)
                    if c.world.channels != replayed.channels: raise ValueError('common-world sensory identity mismatch')
                    c.world = replayed
                context = {'core_time_us': int(c.engine.time_us), 'world_time_s': c.world.time_s,
                           'world_reference': world_reference, 'core_source': source}
                contexts.append(context)
                if mode in ('silence', 'rescue'):
                    pairs = [(e['source'], e['target']) for e in saved['core']['edges']]
                    c.engine.intervene(edges=pairs, action='silence')
                    if mode == 'rescue': c.engine.intervene(edges=pairs, action='unsilence')
                spec = task(i, split, MODES[i % 4])
                record, _ = lesson(s, c, spec, assist=False, head=head, seconds=6., retarget=True,
                    intervention=mode, input_source=kind, cue=cue)
                record['initial_context'] = context
                out.write(encoded(record).decode()+'\n'); results.append(record['result'])
                if not saved_first:
                    write_gzip(p/'first-end-state.json.gz', c.snapshot()); saved_first = True
                if i % 4 == 0:
                    print(json.dumps({'stage': key, 'trial': i+1, 'of': count, 'eye_stable_fraction': record['result']['eye_stable_fraction']}), flush=True)
        new_json(p/'trials.json', results)
        new_json(p/'initial-contexts.json', contexts)
        return {'source': source, 'model': model, 'mode': mode, 'input_source': kind, 'cue': cue, 'n': count,
                'world_reference': world_reference, **summarize(results)}
    return run(s, key, execute)


def correct(s, source, model, *, count=12):
    key = 'E-correct-'+source
    def execute(p):
        c = instance(s, state=read_gzip(WORK/'cases'/source/'checkpoint.json.gz'))
        head = ContinuousMotor.restore(WORK/'cases'/model/'controller', device())
        data = []; before = []; corrections = 0
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as out:
            for i in range(count):
                spec = task(i, 'practice', MODES[i % 4])
                record, _ = lesson(s, c, spec, assist=False, head=head)
                out.write(encoded(record).decode()+'\n'); before.append(record['result'])
                # Practice, never final holdout. Both physical positioning and
                # stillness are demonstrated again; no Core state is rewritten.
                for repeat in range(2):
                    record, samples = lesson(s, c, spec, corrective=True)
                    out.write(encoded(record).decode()+'\n'); data.extend(samples); corrections += 1
                print(json.dumps({'stage': key, 'practice': i+1, 'of': count}), flush=True)
        pack_features(data, p/'features.npz'); write_gzip(p/'checkpoint.json.gz', c.snapshot())
        new_json(p/'practice.json', before)
        return {'practice_count': count, 'corrective_demonstrations': corrections, 'samples': len(data), **summarize(before)}
    return run(s, key, execute)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'calibrate', 'teach', 'validation', 'fit', 'evaluate', 'correct'])
    parser.add_argument('--nose', action='store_true'); parser.add_argument('--source', default='B-teach')
    parser.add_argument('--organization', choices=['shared', 'separate'], default='shared')
    parser.add_argument('--kind', choices=['activity', 'incoming'], default='activity')
    parser.add_argument('--model', default='C-fit-B-teach-shared-activity-fit2')
    parser.add_argument('--mode', choices=['normal', 'empty', 'silence', 'rescue'], default='normal')
    parser.add_argument('--cue', choices=['brief', 'visible', 'none'], default='brief',
                        help='none is a missing-target-information control for this here-pointing curriculum')
    parser.add_argument('--split', choices=['test', 'confirmation', 'practice'], default='test')
    parser.add_argument('--count', type=int, default=16); parser.add_argument('--steps', type=int, default=1600)
    parser.add_argument('--reader-version', type=int, choices=[1, 2], default=1)
    parser.add_argument('--mixed-validation', action='store_true')
    parser.add_argument('--world-reference', help='Explicit external-world replay, retaining the source Core state and clock')
    parser.add_argument('--correction'); parser.add_argument('--suffix', default='')
    args = parser.parse_args()
    if not 1 <= args.count <= 16: parser.error('one to sixteen bounded trials')
    if args.stage == 'prepare':
        WORK.mkdir(parents=True, exist_ok=True)
        if not (WORK/'usage.json').exists(): new_json(WORK/'usage.json', {'used_percent': 0})
        if not (WORK/'instances.json').exists(): new_json(WORK/'instances.json', {'created': 0})
    s = study(args.stage == 'prepare')
    try:
        if args.stage == 'prepare':
            for name in ('continuous_motor.py', 'eye_hand_world.py', 'sensorimotor_session.py', 'active_eye.py'):
                dest = WORK/'frozen-tools'/name; dest.parent.mkdir(exist_ok=True)
                if not dest.exists(): shutil.copy2(ROOT/'lab/tools'/name, dest)
            print(json.dumps({'project_id': s.project, 'work': str(WORK)}))
        elif args.stage == 'calibrate': calibrate(s)
        elif args.stage == 'teach': teach(s, args.nose)
        elif args.stage == 'validation': demonstrations(s, args.source, min(12, args.count))
        elif args.stage == 'fit': fit(s, args.source, args.organization, args.kind, args.correction, args.steps, args.reader_version, args.mixed_validation)
        elif args.stage == 'evaluate': evaluate(s, args.source, args.model, mode=args.mode, kind=args.kind,
            cue=args.cue, split=args.split, count=args.count, suffix=args.suffix, world_reference=args.world_reference)
        elif args.stage == 'correct': correct(s, args.source, args.model, count=min(16, args.count))
    finally: s.db.close()


if __name__ == '__main__': main()
