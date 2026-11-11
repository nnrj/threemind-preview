"""E68 transport/measurement helpers; no restoration or subject selection."""
from contextlib import contextmanager
import hashlib, json, os, time
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '2'
import numpy as np
import torch
from lab.tools.centered_recognition import CenteredWorld, WORDS
from threemind_lab.storage_files import atomic_json
from curriculum import INITIAL, TEACH, CAL, DEV, FINAL


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str).encode('utf-8')

def read(path):
    return json.loads(Path(path).read_bytes())

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while block := f.read(1024**2): h.update(block)
    return h.hexdigest()

def fixed_json(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != json.loads(encoded(value)): raise ValueError('immutable content conflict: ' + str(path))
    else: atomic_json(path, value)

def device():
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.6)
        return 'cuda'
    return 'cpu'

class Meter:
    def __init__(self, previous=None): self.values = dict(previous or {})

    @contextmanager
    def clock(self, name):
        start = time.perf_counter_ns()
        try: yield
        finally:
            self.values[name + '_ns'] = self.values.get(name + '_ns', 0) + time.perf_counter_ns() - start
            self.values[name + '_calls'] = self.values.get(name + '_calls', 0) + 1

class NativeMeter:
    """Measure native boundary calls, without changing their arguments or result."""
    def __init__(self, native, meter): self.native, self.meter = native, meter

    def __getattr__(self, name):
        value = getattr(self.native, name)
        label = {'advance': 'core', 'inject': 'core_inject', 'state_json': 'core_capture',
                 'observation_nodes_json': 'core_observation', 'metrics_json': 'core_metrics'}.get(name)
        if label is None: return value
        def call(*args, **kwargs):
            with self.meter.clock(label): return value(*args, **kwargs)
        return call

def instrument(a, meter):
    a.session.engine._engine = NativeMeter(a.session.engine._engine, meter)
    for owner, method, label in ((a.session.world, 'observe', 'sensing'),
                                (a.session.world, 'advance_physics', 'body'),
                                (a.session.stream, 'sample', 'observation'),
                                (a.words, 'predict', 'inference')):
        original = getattr(owner, method)
        def measured(*args, _call=original, _label=label, **kwargs):
            with meter.clock(_label): return _call(*args, **kwargs)
        setattr(owner, method, measured)
    return a

def optical_check():
    from itertools import product
    world = CenteredWorld(seed=91, toys=False)
    offsets = sorted(set(INITIAL+TEACH+CAL+DEV+FINAL))
    rows = []
    for shape, half in enumerate(((.14,.14,.14),(.14,.14,.15),(.13,.13,.15),(.14,.14,.15))):
        for offset in offsets:
            world.present(shape, 4, offset=offset)
            corners = [world.project(np.array(world.positions[0])+[dx,dy], z=.16+dz)
                       for dx,dy,dz in product(*[(-v,v) for v in half])]
            maximum = float(np.abs(np.stack(corners)).max())
            assert maximum < world.eye_config.center_half_width
            rows.append(dict(shape=shape, offset=offset, maximum=maximum))
    return dict(cases=rows, maximum=max(x['maximum'] for x in rows), center_half_width=.075)

def equal(a, b):
    if isinstance(a, torch.Tensor): return isinstance(b, torch.Tensor) and torch.equal(a.detach().cpu(), b.detach().cpu())
    if isinstance(a, dict): return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)): return len(a) == len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a == b

def speak(a, text, ticks, guard):
    frames = list(a.session.sensor.frames(text)) if text else []
    if len(frames) > ticks: raise ValueError('complete utterance required')
    rows = []
    for i in range(ticks):
        row = a.session.tick(frames[i] if i < len(frames) else None, guard=guard)
        row['teacher_utterance'] = text
        rows.append(row)
    return rows

def ask(a, task, guard):
    a.session.world.present(task['shape'], task['color'], offset=task['offset'])
    a.session.world.marker = None
    rows = speak(a, task['text'], 20, guard)
    indices = np.rint(np.linspace(0,19,8)).astype(int)
    x = np.stack([a.words.layout.frame(rows[i]['activity']) for i in indices])
    logits = a.words.predict(x[None])[0]
    selected = int(logits.argmax())
    result = task | dict(selected=selected, word=WORDS[selected], correct=selected == task['label'])
    rows[-1]['expression'] = dict(word=WORDS[selected], probabilities=torch.as_tensor(logits).softmax(-1).tolist(),
                                identity=a.identity, readout_profile='whole-question', steps_before=a.words.computed_updates)
    return rows, x, result
