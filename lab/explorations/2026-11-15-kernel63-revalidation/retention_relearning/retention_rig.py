"""Whole 6.3 individuals and passive process records for the X2 replication."""
import copy
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT/'src'), str(HERE.parent)]
spec = importlib.util.spec_from_file_location('r63u_criteria_rig', HERE.parent/'criteria/rig.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
m = base.m
KERNEL = base.KERNEL
SYMBOLS = tuple('ABXYZWKN')
FIELDS = ('activation', 'inhibition', 'direct', 'associative')
MODES = ('default', 'stability')
DELAYS = (1, 30, 60, 300)
teaching = base.teaching
case_seed = base.case_seed


class Rig(base.Rig):
    def __init__(self, kind, seed, mode='default', saved=None):
        assert kind == 'threemind' and mode in MODES
        if saved is not None:
            super().__init__(kind, seed, mode, saved)
            return
        self.kind, self.seed, self.mode = kind, seed, mode
        self.channels, self.rng = m.mapping(seed)
        self.time = 0
        self.inputs, self.rows = [], []
        self.body = {'x': .3125, 'v': 0., 'gate': 0}
        self.actuator, self.branch = 0., None
        config = {'seed': seed, 'energy_seed': seed ^ 0x1634AB}
        if mode == 'stability':
            config['consolidation_mode'] = 'stability'
        self.model = base.resolve_kernel(KERNEL).create(config, backend='native')

    def save(self):
        saved = super().save()
        saved['schema'] = 'threemind.retention63-whole/1'
        return saved

    def fork(self, label):
        saved = self.save()
        child = Rig.restore(saved)
        child.branch = {'parent_sha256': m.digest(saved), 'label': label, 'time_us': self.time}
        return child


def four_fields(rig):
    nodes = {n['channel']: n for n in rig.model.observation_nodes()}
    return {field: [nodes.get(rig.channels[s], {}).get(field, 0.) for s in SYMBOLS] for field in FIELDS}


def probe(rig, cue='X', dose=.8, *, frequent=False, restore_mid=False, pause_mid=False):
    """Same X2 stimulus, clock grid and fixed answers; four fields are recorded."""
    start, initial = rig.time, len(rig.rows)
    rig.tick(start, dict.fromkeys(cue, dose/len(cue)) if cue else {})
    events = {start+500_000: {'K': .2}, start+1_000_000: {'K': .2}, start+1_500_000: {'K': .2}}
    for t in range(start+1000, start+1_500_001, 1000):
        rig.tick(t, events.get(t), frequent=frequent and (t-start) % 50_000 == 0)
        rig.rows.append({'time_us': t, 'response': rig.actuator,
                         'body': copy.deepcopy(rig.body), 'activity': four_fields(rig)})
        if t == start+500_000:
            if restore_mid:
                restored = Rig.restore(rig.save())
                rig.__dict__.update(restored.__dict__)
            if pause_mid:
                import time
                saved = rig.save()
                time.sleep(.03)
                assert rig.save() == saved
    rows = rig.rows[initial:]
    def integral(lo, hi):
        return sum(r['response']*.001 for r in rows if lo <= r['time_us']-start <= hi)
    first = next(r['response'] for r in rows if r['time_us'] == start+110_000)
    return {'start_us': start, 'first': first, 'choice': int(first>1e-4)-int(first < -1e-4),
            'early_integral': integral(100_000, 300_000), 'late_integral': integral(500_000, 1_500_000),
            'late_mean': integral(500_000, 1_500_000)/1.001,
            'peak': max(abs(r['response']) for r in rows if r['time_us']-start <= 500_000),
            'trace_count': len(rows), 'final_sha256': m.digest(rig.save())}


def response_mean(result, history):
    return (1 if history == 0 else -1) * result['early_integral'] / .201


def waiting_seconds(lesson):
    assert 1 <= lesson <= 16
    return 2 * 2**((lesson-1)//4)


def course(rig, history, threshold=None, *, always_complete=False):
    """One continuous course; all probe experiences remain in the individual."""
    rows = []
    run = legacy_run = 0
    attained = legacy_attained = 17
    for lesson in range(1, 17):
        initial = m.digest(rig.save())
        start = rig.time
        rig.tick(start, dict.fromkeys('XYA' if history == 0 else 'XYB', .4))
        seconds = waiting_seconds(lesson)
        rig.advance(start+seconds*1_000_000,
                    {start+j*500_000: {'K': .2} for j in range(1, 2*seconds+1)})
        answer = probe(rig, 'X', .8)
        value = response_mean(answer, history)
        correct = None if threshold is None else value > threshold
        run = run+1 if correct else 0
        legacy_correct = (1 if history == 0 else -1)*answer['first'] > 1e-4
        legacy_run = legacy_run+1 if legacy_correct else 0
        if legacy_run >= 2 and legacy_attained == 17:
            legacy_attained = lesson
        if run >= 2 and attained == 17:
            attained = lesson
        rows.append({'lesson': lesson, 'start_us': start, 'wait_seconds': seconds,
                     'initial_sha256': initial, 'final_sha256': m.digest(rig.save()),
                     'directed_process_mean': value, 'threshold': threshold,
                     'correct': correct, 'legacy_correct': legacy_correct, 'result': answer})
        if attained != 17 and not always_complete:
            break
    return {'rounds': attained, 'censored': attained == 17, 'legacy_rounds': legacy_attained,
            'threshold': threshold, 'lessons': rows}
