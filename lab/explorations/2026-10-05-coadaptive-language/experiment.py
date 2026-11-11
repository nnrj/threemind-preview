"""Bounded coadaptive language pilot. Teacher labels never enter inference."""
import argparse
import gzip
import importlib.util
import json
import random
import shutil
import sys
import time
from functools import lru_cache
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import torch
from lab.tools.service_study import Study, StudyConfig, new_json, read_json, write_gzip
from lab.tools.recorded_background import RecordedBackground
from lab.tools.sensory_calibration import paired_visual
from lab.tools.semantic_teaching_world import SemanticTeachingWorld, WORDS, COLORS, SHAPES
from threemind_runtime.activity_stream import RawActivityStream
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.local_activity import local_process
from threemind_transformer.adaptive_expression import AdaptiveExpression, return_utterance
from threemind_transformer.graph_expression import load

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/coadaptive-language-20261005'
TAPE = ROOT / '.work/temporal-state-20261005/physical-telemetry.jsonl'
spec = importlib.util.spec_from_file_location('e52_frozen_input', ROOT / 'lab/explorations/2026-10-05-temporal-state-expression/experiment.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
NAMES = ('甲', '乙', '丁', '戊')
ARMS = ('feedback', 'no-feedback', 'no-core-learning')


def study(prepare=False):
    return Study(StudyConfig('coadaptive-language/1', 'E52 共同学习的语言中枢与语句所指', HERE, WORK, 52,
        instance_limit=640, wall_seconds=10800, storage_soft=3*2**30, storage_hard=8*2**30,
        usage_soft_delta=6, usage_hard_delta=10), prepare=prepare)


def guard(s, force=False):
    s.guard(force)
    if not hasattr(s, 'extra_core_copies'):
        s.extra_core_copies = sum(max(0, read_json(p).get('core_copies', 1)-1)
            for p in (WORK/'cases').glob('*/result.json'))
    if (s.completed_count or 0) + s.extra_core_copies >= s.settings.instance_limit:
        raise RuntimeError('actual source/probe copy budget')
    if torch.cuda.is_available() and torch.cuda.memory_allocated() > 3*2**30:
        raise RuntimeError('GPU budget')


def start(s, key):
    guard(s, True)
    path = WORK / 'cases' / key
    if (path / 'result.json').exists():
        return path, None
    if path.exists():
        raise RuntimeError('incomplete case retained: ' + key)
    path.mkdir(parents=True)
    tick = time.monotonic()
    s.active_case = SimpleNamespace(born_wall=tick)
    return path, tick


def finish(s, path, tick, result):
    seconds = time.monotonic() - tick
    new_json(path / 'result.json', result | {'wall_seconds': seconds, 'runner_signature': s.runner_signature})
    s.active_case = None
    s.completed_count = (s.completed_count or 0) + 1
    s.completed_wall += seconds
    s.extra_core_copies += max(0, result.get('core_copies', 1)-1)


def adapter():
    a = h.adapter()
    a.world = SemanticTeachingWorld(71)
    return a


def assignment(stage, seed):
    base = [0, 1, 2, 3] if seed == 223 else [1, 0, 3, 2]
    if stage == 2:
        base[0], base[1] = base[1], base[0]
    return base


def statements(item, name):
    other = WORDS[item ^ 2]
    return (
        f'这个{WORDS[item]}叫{name}。',
        f'{name}是{COLORS[item]}的。',
        f'{name}是{SHAPES[item]}。',
        f'与{other}同色的{SHAPES[item]}叫{name}。',
    )


def question(item, kind):
    if kind == 'visual':
        return '它叫什么？'
    if kind == 'description':
        return f'{COLORS[item]}的{SHAPES[item]}叫什么？'
    if kind == 'paraphrase':
        return f'{SHAPES[item]}里面，{COLORS[item]}的是谁？'
    if kind == 'relation':
        return f'跟{WORDS[item ^ 2]}颜色一样的{SHAPES[item]}叫什么？'
    if kind == 'none':
        return None
    raise ValueError(kind)


@lru_cache(maxsize=1)
def background():
    return RecordedBackground(TAPE)


def advance(s, value, cursor, until, *, observe=False):
    if until > 835000000:
        raise RuntimeError('physical recording coverage; do not silently loop background')
    cursor = background().queue_before(value.reader, cursor, until)
    frames = []
    beginning = value.engine.time_us
    if observe:
        stream = RawActivityStream()
        stream.subscribe('e52-raw', frames.append)
        while True:
            stream.sample(value.engine)
            if value.engine.time_us >= until or value.engine.life == 'dead':
                break
            value.reader.advance_to(min(until, value.engine.time_us+20000), guard=lambda: guard(s))
    else:
        value.reader.advance_to(until, guard=lambda: guard(s))
    value.records.clear()
    if value.engine.life == 'dead':
        raise RuntimeError('death reached; no automatic revival')
    raw = {'start_us': str(beginning), 'end_us': str(value.engine.time_us), 'trajectory': frames, 'life': value.engine.life}
    return cursor, raw


def submit(a, value, text, *, item=None, view=0, intensity=1., source='teacher'):
    frames = h.timed_frames(a, text, 20000, intensity, teaching=source == 'teacher')
    measured = a.world.sample(item, view) if item is not None else None
    if measured is not None:
        frames = paired_visual(frames, a.world.frame(measured), 10 if source == 'teacher' else 2)
    if frames and max(int(f['stimulus'].time_us) for f in frames) >= 700000:
        raise RuntimeError('sentence exceeds declared interval')
    value.reader.schedule(frames, source='E52-'+source, adapter_id='language-dose-study/1')
    return {'time_us': str(value.engine.time_us), 'text': text, 'measurement': measured,
            'frames': [asdict(f['stimulus']) for f in frames]}


def teach_course(s, a, value, cursor, stage, names, seed, path):
    items = (2, 3) if stage == 1 else (0, 1)
    pairs = [(i, f) for i in items for f in range(4)]
    random.Random(seed+stage).shuffle(pairs)
    lessons = [(i, f, r, .8) for i, f in pairs for r in range(10)]
    for gap in (2, 4):
        order = pairs.copy()
        random.Random(seed+stage+gap).shuffle(order)
        lessons.extend((i, f, 10+gap, gap) for i, f in order)
    with gzip.open(path/'teaching.jsonl.gz', 'xt', encoding='utf-8') as out:
        for item, form, repetition, interval in lessons:
            row = submit(a, value, statements(item, NAMES[names[item]])[form], item=item, view=repetition%8)
            out.write(json.dumps(row | {'item': item, 'form': form, 'repeat': repetition}, ensure_ascii=False)+'\n')
            cursor, _ = advance(s, value, cursor, value.engine.time_us+round(interval*1e6))
    return cursor


def ask(s, a, value, cursor, item, kind, view):
    text = question(item, kind)
    delivered = submit(a, value, text, item=item if kind == 'visual' else None,
                       view=view, intensity=.5, source='question') if text else None
    cursor, raw = advance(s, value, cursor, value.engine.time_us+2000000, observe=True)
    return cursor, raw, delivered


def stage_source(s, a, seed, arm, stage):
    path, tick = start(s, f's{seed}-{arm}-stage{stage}')
    if tick is None:
        return path
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if stage == 0:
        value = LanguageSession(h.old.e45.protocol(71).model_dump(),
            config={'seed': seed, 'plasticity': arm != 'no-core-learning'}, seed=seed, readouts=h.old.e45.READOUTS)
        cursor = 0
        head = AdaptiveExpression(device=device)
    else:
        previous = WORK/'cases'/f's{seed}-{arm}-stage{stage-1}'
        value = h.old.e45.previous.restore(previous/'checkpoint', 71)
        cursor = read_json(previous/'checkpoint/summary.json')['cursor']
        head = AdaptiveExpression.restore(previous/'expression-2', device=device)
    names = assignment(stage, seed)
    h.old.e45.previous.save_state(path/'initial', value, cursor)
    new_json(path/'definition.json', {'seed': seed, 'arm': arm, 'stage': stage,
        'assignment': names, 'config': value.engine.capture_state().to_dict()['config']})
    cursor = teach_course(s, a, value, cursor, stage, names, seed, path)
    # Four examples per update. Stage0 only two objects, two observation views.
    items = (0, 1) if stage == 0 else (0, 1, 2, 3)
    trials = [(i, k, v) for v in ((8, 10) if stage == 0 else (8,))
              for i in items for k in ('visual', 'description')]
    teaching = []
    with gzip.open(path/'dialogue.jsonl.gz', 'xt', encoding='utf-8') as out:
        for index, (item, kind, view) in enumerate(trials):
            cursor, raw, delivered = ask(s, a, value, cursor, item, kind, view)
            observed = local_process(raw)
            answer = head.decode([observed])[0] if head.model is not None else {'text': '', 'uncalibrated': True}
            write_gzip(path/f'teaching-observation-{index}.json.gz', raw)
            feedback = return_utterance(value.reader, answer['text'], lambda text: h.timed_frames(a, text, 20000, 1.),
                enabled=arm != 'no-feedback')
            cursor, _ = advance(s, value, cursor, value.engine.time_us+700000)
            target = NAMES[names[item]]+'。'
            teacher = submit(a, value, f'老师说：这个{WORDS[item]}叫{NAMES[names[item]]}。', item=item, view=view)
            cursor, _ = advance(s, value, cursor, value.engine.time_us+800000)
            receipt = f'{path.name}-turn{index}'
            head.teach(observed, target, receipt=receipt)
            teaching.append({'process': observed, 'text': target, 'receipt': receipt})
            out.write(json.dumps({'index': index, 'item': item, 'kind': kind, 'question': delivered,
                'answer': answer, 'self_hearing': feedback, 'teacher': teacher, 'target_external_only': target},
                ensure_ascii=False, default=str)+'\n')
            out.flush()
            if index in (3, 7):
                steps = (1000 if index == 3 else 2000) if stage == 0 else 1000
                update = head.adapt(path/f'expression-{1 if index == 3 else 2}', steps=steps, check=lambda: guard(s))
                print({'stage': path.name, 'update': index+1, 'steps': update['training']['steps']}, flush=True)
    outputs = head.decode([r['process'] for r in teaching])
    correct = sum(o['text'] == r['text'] for o, r in zip(outputs, teaching))
    h.old.e45.previous.save_state(path/'checkpoint', value, cursor)
    finish(s, path, tick, {'kind': 'source', 'seed': seed, 'arm': arm, 'stage': stage,
        'assignment': names, 'teaching_fit': correct, 'teaching_count': 8,
        'training_outputs': [o['text'] for o in outputs], 'end_us': value.engine.time_us,
        'adapter_revision': head.revision, 'self_hearing': arm != 'no-feedback'})
    print({'source': path.name, 'fit': f'{correct}/8', 'sim_seconds': value.engine.time_us/1e6}, flush=True)
    return path


def probes(s, a, source):
    info = read_json(source/'result.json')
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    head = AdaptiveExpression.restore(source/'expression-2', device=device)
    frozen = WORK/'cases'/f"s{info['seed']}-{info['arm']}-stage0"/'expression-2'
    prior = AdaptiveExpression.restore(frozen, device=device)
    items = (0, 1) if info['stage'] == 0 else (0, 1, 2, 3)
    trials = [(i, k) for i in items for k in ('visual', 'description', 'paraphrase', 'relation')] + [(-1, 'none')]
    for item, kind in trials:
        path, tick = start(s, source.name+f'-test-{item}-{kind}')
        if tick is None:
            continue
        value = h.old.e45.previous.restore(source/'checkpoint', 71)
        cursor = read_json(source/'checkpoint/summary.json')['cursor']
        _, raw, delivered = ask(s, a, value, cursor, item, kind, 9)
        write_gzip(path/'process.json.gz', raw)
        observed = local_process(raw)
        output = head.decode([observed])[0]
        static = prior.decode([observed])[0]
        finish(s, path, tick, {'kind': 'test', 'seed': info['seed'], 'arm': info['arm'], 'stage': info['stage'],
            'item': item, 'perspective': kind, 'prompt': delivered,
            'target': NAMES[info['assignment'][item]]+'。' if item >= 0 else None,
            'output': output['text'], 'frozen_output': static['text'], 'tokens': output['tokens'],
            'process': str(path/'process.json.gz')})
    print({'tested': source.name}, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=('prepare', 'stage', 'probe'))
    parser.add_argument('--seed', type=int, choices=(223, 279), default=223)
    parser.add_argument('--arm', choices=ARMS, default='feedback')
    parser.add_argument('--stage', type=int, choices=(0, 1, 2), default=0)
    args = parser.parse_args()
    torch.set_num_threads(2)
    s = study(args.operation == 'prepare')
    try:
        if args.operation == 'prepare':
            new_json(WORK/'usage.json', {'used_percent': 52})
            folder = WORK/'external-tools'
            folder.mkdir(exist_ok=True)
            for name in ('src/threemind_transformer/adaptive_expression.py', 'src/threemind_transformer/graph_expression.py',
                         'src/threemind_transformer/local_activity.py', 'lab/tools/semantic_teaching_world.py'):
                shutil.copy2(ROOT/name, folder/Path(name).name)
            new_json(WORK/'dependencies.json', {'frozen_input': str(ROOT/'.work/native-language-20261005/frozen-input'),
                                              'background': str(TAPE), 'core_changed': False})
            print({'project': s.project}, flush=True)
            return
        a = adapter()
        s.allow_extension()
        source = WORK/'cases'/f's{args.seed}-{args.arm}-stage{args.stage}'
        if args.operation == 'stage':
            source = stage_source(s, a, args.seed, args.arm, args.stage)
        probes(s, a, source)
    finally:
        s.active_case = None
        s.db.close()


if __name__ == '__main__':
    main()
