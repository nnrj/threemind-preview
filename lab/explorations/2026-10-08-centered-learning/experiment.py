"""E65: one registered central-recognition continuation, with whole-system state."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from lab.tools.service_study import Study, StudyConfig, read_json, new_json, encoded
from lab.tools.recognition_session import RecognitionSystem
from lab.tools.centered_recognition import WORDS

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/centered-learning-20261008'
PARENT = ROOT / '.work/centered-restart-20261008'
SOURCE = PARENT / 'cases/final-fit/system'
OFFSETS = ((0., 0.), (-.008, 0.), (.008, 0.), (0., .008))
CAL_OFFSETS = ((.004, -.004), (-.004, .004))
TARGETS = ((1, 1, 0), (2, 2, 1), (1, 1, 3), (2, 2, 0), (5, 3, 1))
PAIRS = ((1, 0), (2, 1), (1, 3), (2, 0), (3, 1), (0, 0), (1, 2), (3, 3))
LIMIT = 240


class BoundedStudy(Study):
    def guard(self, force=False):
        super().guard(force)
        if force or not hasattr(self, 'failed_wall'):
            self.failed_wall = sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('*/stopped.json')
                                   if not (p.parent/'result.json').exists())
        active = time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+self.failed_wall+active > self.settings.wall_seconds:
            raise RuntimeError('compute budget including partial cases')


def study(prepare=False):
    from urllib.parse import urlsplit
    from threemind_lab.config import Settings
    u = urlsplit(Settings.from_env().database_url)
    if u.hostname not in ('127.0.0.1', 'localhost') or u.port != 5433 or u.path != '/threemind':
        raise ValueError('authorized local DB only')
    return BoundedStudy(StudyConfig('centered-learning/1', 'E65 中央形色完整个体续学', HERE, WORK, 23,
        instance_limit=LIMIT, wall_seconds=3600, storage_soft=2*2**30, storage_hard=4*2**30,
        usage_soft_delta=3, usage_hard_delta=4), prepare=prepare)


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.6)
        return 'cuda'
    return 'cpu'


def restore(path):
    p = WORK/'instances.json'
    n = read_json(p)['created']
    if n >= LIMIT: raise RuntimeError('complete creation/restore limit')
    p.write_bytes(encoded({'created': n+1}))
    return RecognitionSystem.restore(path, device())


def run(s, key, fn):
    p = WORK/'cases'/key
    if (p/'result.json').exists(): return read_json(p/'result.json')
    if p.exists(): raise RuntimeError('preserve partial case '+key)
    s.allow_extension()
    p.mkdir(parents=True)
    start = time.monotonic()
    s.active_case = SimpleNamespace(born_wall=start)
    new_json(p/'started.json', dict(epoch=time.time(), runner=s.runner_signature))
    try:
        result = fn(p) | dict(wall_seconds=time.monotonic()-start, runner=s.runner_signature)
        new_json(p/'result.json', result)
        s.active_case = None
        s.completed_count += 1
        s.completed_wall += result['wall_seconds']
        print(encoded(dict(case=key, **result)).decode(), flush=True)
        return result
    except Exception as error:
        new_json(p/'stopped.json', dict(error=str(error), wall_seconds=time.monotonic()-start))
        raise


def task(label, shape=None, color=None, offset=(0., 0.), category='basic'):
    shape = (label if label < 4 else 2) if shape is None else shape
    color = (4 if label < 4 else label-4) if color is None else color
    noun = WORDS[label] if label < 4 else WORDS[label]+'的物体'
    return dict(label=label, shape=shape, color=color, offset=list(offset), category=category,
        attribute='shape' if label < 4 else 'color', pair_id=f'{shape}-{color}',
        statement=f'这是{noun}。', text='这是什么形状？' if label < 4 else '这是什么颜色？')


def tasks(split):
    if split == 'calibration':
        out = [task(i, offset=o) for i in range(8) for o in CAL_OFFSETS]
        out += [task(label, shape, color, o, 'colored-pair') for shape, color in PAIRS
                for label in (shape, 4+color) for o in CAL_OFFSETS]
    elif split in ('primary', 'confirmation'):
        offset = (.010, .010) if split == 'primary' else (-.010, -.010)
        out = [task(i, offset=offset, category='gray-shape') for i in range(4)]
        out += [task(label, shape, color, offset, 'colored-pair') for shape in range(4)
                for color in range(4) for label in (shape, 4+color)]
        order = np.random.default_rng(6501 if split == 'primary' else 6503).permutation(len(out))
        out = [out[int(i)] for i in order]
    else: raise ValueError('registered split only')
    return [t | dict(split=split, question_id=f'{split}-{i}') for i, t in enumerate(out)]


def schedule():
    out = []
    for target in TARGETS:
        for rep in range(10):
            out.append(task(*target, offset=OFFSETS[rep % 4]) | dict(block='consecutive', gap_s=0))
    for review, gap in enumerate((0, 6, 18)):
        examples = [task(i) for i in range(8)]+[task(*v) for v in TARGETS]
        for i, t in enumerate(examples):
            out.append(t | dict(offset=list(OFFSETS[(review+i) % 4]), block=f'review-{review+1}',
                                gap_s=gap if i == 0 else 0))
    return [t | dict(lesson=i+1) for i, t in enumerate(out)]


def record(f, rows, kind, trial=None):
    f.write(encoded(dict(kind=kind, process=rows, text=rows[0].get('teacher_utterance', kind),
                        **({'trial': trial} if trial is not None else {}))).decode()+'\n')


def speak(a, text, ticks, s):
    frames = list(a.session.sensor.frames(text))
    if len(frames) > ticks: raise ValueError('do not truncate a sentence')
    rows = []
    for i in range(ticks):
        row = a.session.tick(frames[i] if i < len(frames) else None, guard=s.guard)
        row['teacher_utterance'] = text
        rows.append(row)
    return rows


def ask(a, t, s):
    a.session.world.present(t['shape'], t['color'], offset=t['offset'])
    a.session.world.marker = None
    rows = speak(a, t['text'], 20, s)
    ids = np.rint(np.linspace(0, len(rows)-1, 8)).astype(int)
    x = np.stack([a.words.layout.frame(rows[i]['activity']) for i in ids])
    # No scene, teacher, label or answer enters this inference call.
    logits = a.words.predict(x[None])[0]
    selected = int(logits.argmax())
    result = t | dict(selected=selected, word=WORDS[selected], correct=selected == t['label'],
                      peripheral_updates=a.words.computed_updates)
    rows[-1]['expression'] = dict(word=WORDS[selected], probabilities=torch.as_tensor(logits).softmax(-1).tolist(),
        identity=a.identity, steps_before=a.words.computed_updates, readout_profile='whole-question')
    return rows, x, result


def tree_equal(a, b):
    if isinstance(a, torch.Tensor): return isinstance(b, torch.Tensor) and torch.equal(a, b)
    if isinstance(a, dict): return a.keys() == b.keys() and all(tree_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)): return len(a) == len(b) and all(tree_equal(x, y) for x, y in zip(a, b))
    return a == b


def preflight(s):
    def op(p):
        a = restore(WORK/'reference/system')
        if a.identity != 'e64-blank-223' or a.session.engine.time_us != 219000000 or a.words.computed_updates != 2400:
            raise ValueError('wrong complete baseline')
        a.save(p/'roundtrip')
        b = restore(p/'roundtrip')
        if encoded(a.session.snapshot()) != encoded(b.session.snapshot()): raise AssertionError('snapshot')
        ra, rb = a.session.tick(guard=s.guard), b.session.tick(guard=s.guard)
        if encoded(ra) != encoded(rb) or a.session.engine.capture_state().digest != b.session.engine.capture_state().digest:
            raise AssertionError('next physical input/activity/Core')
        with np.load(WORK/'reference/first-calibration.npz', allow_pickle=False) as d:
            a.words.calibrate(d['x'], d['y'], steps=1, check=s.guard)
            b.words.calibrate(d['x'], d['y'], steps=1, check=s.guard)
        if not all((tree_equal(a.words.state_dict(), b.words.state_dict()),
                    tree_equal(a.words.optimizer.state_dict(), b.words.optimizer.state_dict()),
                    tree_equal(a.words.learning_rng, b.words.learning_rng))):
            raise AssertionError('next personal optimizer update')
        optical = []
        offsets = sorted(set(OFFSETS+CAL_OFFSETS+((.010,.010),(-.010,-.010))))
        for offset in offsets:
            a.session.world.present(0, 4, offset=offset)
            uv = a.session.world.project(a.session.world.positions[0])
            if not np.all(np.abs(uv) < a.session.world.eye_config.center_half_width):
                raise AssertionError('object outside central clear field')
            optical.append(dict(offset=offset, projected_center=uv.tolist()))
        new_json(p/'optical-centers.json', optical)
        return dict(identity=a.identity, next_input_activity_core_equal=True, next_optimizer_update_equal=True,
                    central_offsets=len(optical), device=str(next(a.words.parameters()).device),
                    isolated_verification=True)
    return run(s, 'preflight', op)


def collect(s, source, split, key):
    def op(p):
        xs, ys, scores = [], [], []
        frozen = read_json(WORK/'questions.json')[split]
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as f:
            for i, t in enumerate(frozen):
                a = restore(source)
                rows, x, result = ask(a, t, s)
                xs.append(x); ys.append(t['label']); scores.append(result)
                record(f, rows, 'external-calibration' if split == 'calibration' else key, result)
                del a
                if (i+1) % 6 == 0:
                    print(json.dumps(dict(stage=key, questions=i+1, of=len(frozen), correct=sum(r['correct'] for r in scores))), flush=True)
        np.savez_compressed(p/'features.npz', x=xs, y=ys)
        new_json(p/'predictions.json', scores)
        groups = {attr: dict(n=sum(r['attribute'] == attr for r in scores),
                    correct=sum(r['attribute'] == attr and r['correct'] for r in scores)) for attr in ('shape','color')}
        return dict(n=len(scores), correct=sum(r['correct'] for r in scores), groups=groups,
                    source=source.relative_to(ROOT).as_posix(), split=split)
    return run(s, key, op)


def teaching(s):
    def op(p):
        a = restore(WORK/'reference/system')
        start = a.session.engine.time_us
        timing = []
        with gzip.open(p/'process.jsonl.gz', 'xt', encoding='utf-8') as f:
            for t in read_json(WORK/'curriculum.json'):
                for _ in range(t['gap_s']*20): record(f, [a.session.tick(guard=s.guard)], 'interval')
                a.session.world.present(t['shape'], t['color'], offset=t['offset'])
                a.session.world.marker = None
                began = a.session.engine.time_us
                rows = speak(a, t['statement'], 30, s)
                trial = t | dict(start_us=began, end_us=a.session.engine.time_us)
                record(f, rows, 'teaching', trial)
                timing.append(trial)
                a.cursor += 1
                if t['lesson'] % 10 == 0:
                    print(json.dumps(dict(stage='teaching', lesson=t['lesson'], of=89, sim_s=a.session.engine.time_us/1e6)), flush=True)
        a.phase = 'e65-taught'
        a.save(p/'system')
        new_json(p/'lesson-timing.json', timing)
        if a.session.engine.time_us-start != 157500000: raise AssertionError('registered teaching duration')
        return dict(lessons=len(timing), additional_sim_seconds=(a.session.engine.time_us-start)/1e6,
                    core_time_us=a.session.engine.time_us, updates=a.words.computed_updates,
                    identity=a.identity, parent='reference/system')
    return run(s, 'teaching', op)


def fit(s):
    def op(p):
        a = restore(WORK/'cases/teaching/system')
        before = a.session.engine.capture_state().digest
        corpora = ['reference/first-calibration.npz', 'reference/later-calibration.npz', 'cases/new-calibration/features.npz']
        xs, ys = [], []
        for name in corpora:
            with np.load(WORK/name, allow_pickle=False) as d: xs.append(d['x']); ys.append(d['y'])
        result = a.words.calibrate(np.concatenate(xs), np.concatenate(ys), steps=1200, check=s.guard)
        if a.session.engine.capture_state().digest != before: raise AssertionError('calibration changed Core')
        a.phase = 'e65-final-fit'
        a.save(p/'system')
        return result | dict(identity=a.identity, corpora=corpora, core_time_us=a.session.engine.time_us,
                             core_unchanged_during_calibration=True, parent='cases/teaching/system')
    return run(s, 'final-fit', op)


def source_hashes():
    return {p.relative_to(SOURCE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(SOURCE.rglob('*')) if p.is_file()}


def prepare(s, usage):
    if not (WORK/'instances.json').exists(): new_json(WORK/'instances.json', dict(created=0))
    (WORK/'usage.json').write_bytes(encoded(dict(used_percent=usage)))
    if not (WORK/'questions.json').exists():
        new_json(WORK/'questions.json', {split: tasks(split) for split in ('calibration','primary','confirmation')})
        new_json(WORK/'curriculum.json', schedule())
    if not (WORK/'reference').exists():
        dest = WORK/'reference'
        dest.mkdir()
        original = source_hashes()
        shutil.copytree(SOURCE, dest/'system')
        copied = {p.relative_to(dest/'system').as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((dest/'system').rglob('*')) if p.is_file()}
        if original != copied: raise AssertionError('baseline copy not exact')
        new_json(dest/'source-hashes.json', original)
        for key in ('first-calibration','later-calibration'):
            shutil.copy2(PARENT/'cases'/key/'features.npz', dest/(key+'.npz'))
            shutil.copy2(PARENT/'cases'/key/'predictions.json', dest/(key+'.json'))
        manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.glob('*') if p.is_file()}
        new_json(dest/'corpus-manifest.json', manifest)
    files = list((ROOT/'lab/tools').glob('*.py'))+[ROOT/'docs/zh/training-protocol.md', ROOT/'docs/en/training-protocol.md']
    manifest = {}
    for path in files:
        dest = WORK/'source-reference'/path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists(): shutil.copy2(path, dest)
        manifest[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not (WORK/'source-reference/manifest.json').exists(): new_json(WORK/'source-reference/manifest.json', manifest)
    s.guard(True)
    print(json.dumps(dict(project_id=s.project)), flush=True)


def validate_design():
    cal, primary, confirm = (tasks(k) for k in ('calibration','primary','confirmation'))
    assert (len(cal), len(primary), len(confirm), len(schedule())) == (48,36,36,89)
    assert sum(t['gap_s']+1.5 for t in schedule()) == 157.5
    for split in (primary, confirm):
        assert len({(t['shape'], t['color'], t['attribute']) for t in split}) == 36
        for shape in range(4):
            for color in range(4):
                assert {t['attribute'] for t in split if (t['shape'],t['color'])==(shape,color)} == {'shape','color'}
        assert not {tuple(t['offset']) for t in split} & set(OFFSETS+CAL_OFFSETS)
        assert all(WORDS[t['label']] not in t['text'] for t in split)
    print('registered curriculum, complete combinations, answer-free questions and reserved positions verified', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check','prepare','run'))
    parser.add_argument('--usage', type=int)
    args = parser.parse_args()
    validate_design()
    if args.command == 'check': return
    if args.command == 'prepare' and args.usage is None: parser.error('actual account measurement required')
    s = study(args.command == 'prepare' and not (WORK/'platform.json').exists())
    try:
        if args.command == 'prepare': prepare(s, args.usage); return
        if source_hashes() != read_json(WORK/'reference/source-hashes.json'): raise AssertionError('E64 source changed')
        preflight(s)
        collect(s, WORK/'reference/system', 'primary', 'baseline')
        teaching(s)
        collect(s, WORK/'cases/teaching/system', 'calibration', 'new-calibration')
        fit(s)
        collect(s, WORK/'cases/final-fit/system', 'primary', 'primary')
        collect(s, WORK/'cases/final-fit/system', 'confirmation', 'confirmation')
        if source_hashes() != read_json(WORK/'reference/source-hashes.json'): raise AssertionError('E64 source changed')
    finally: s.db.close()


if __name__ == '__main__': main()
