"""Authorized temporal M5 measurement with simultaneous historical endpoint controls on 6.1."""
from __future__ import annotations

import copy
import json
import random
from dataclasses import replace

import numpy as np
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import pilot_m2 as m
from threemind_kernels.registry import resolve_kernel
KERNEL = 'threemind.continuous-memory/6.1'
FIELDS = ('activation', 'inhibition', 'direct', 'associative')
BINS = ((1000, 50000), (51000, 100000), (101000, 150000), (151000, 200000), (201000, 250000))
DIMENSION = 12 * len(FIELDS) * len(BINS)
from pilot_m1 import differences

SYMBOLS = 'ABUVZWXYCDKN'
OLD = ('U', 'V', 'UV', 'Z', 'W', 'ZW')
NEW = ('X', 'Y', 'XY', 'C', 'D', 'CD')
MARGIN = .25


class Reader:
    """Personal linear expression, with fixed calibration scaling and ridge state."""
    def __init__(self, saved=None, dimension=12):
        self.dimension = saved["dimension"] if saved else dimension
        self.scale = np.ones(self.dimension)
        self.gram = np.eye(self.dimension)*.001
        self.rhs = np.zeros(self.dimension)
        self.weights = np.zeros(self.dimension)
        self.samples = []
        self.updates = 0
        self.calibrated = False
        if saved:
            for k in ('scale', 'gram', 'rhs', 'weights'):
                setattr(self, k, np.array(saved[k], dtype=float))
            self.samples = copy.deepcopy(saved['samples'])
            self.updates, self.calibrated = saved['updates'], saved['calibrated']

    def save(self):
        return {'schema': 'threemind.m5-process61-personal-linear/1', 'dimension': self.dimension,
                **{k: getattr(self, k).tolist() for k in ('scale', 'gram', 'rhs', 'weights')},
                'samples': copy.deepcopy(self.samples), 'updates': self.updates,
                'calibrated': self.calibrated, 'ridge': .001, 'margin': MARGIN}

    def learn(self, rows):
        if not rows:
            raise ValueError('empty calibration')
        x = np.array([r['features'] for r in rows], dtype=float)
        y = np.array([r['label'] for r in rows], dtype=float)
        if x.shape != (len(rows), self.dimension) or not np.isfinite(x).all() or not set(y) <= {-1., 1.}:
            raise ValueError('invalid calibration')
        if not self.calibrated:
            maxima = np.max(np.abs(x), axis=0)
            self.scale = np.where(maxima > 1e-6, maxima, 1.)
            self.calibrated = True
        z = x/self.scale
        self.gram += z.T@z
        self.rhs += z.T@y
        self.weights = np.linalg.solve(self.gram, self.rhs)
        self.samples.extend(copy.deepcopy(rows))
        self.updates += len(rows)

    def infer(self, features):
        # No case, label, teaching history, timestamp or cue identity is accepted.
        a = np.asarray(features, dtype=float)
        if a.shape != (self.dimension,) or not np.isfinite(a).all():
            raise ValueError('invalid inference vector')
        score = float(self.weights@(a/self.scale))
        return {'score': score, 'answer': int(score > MARGIN)-int(score < -MARGIN)}


class Subject:
    def __init__(self, seed, saved=None):
        self.seed = seed
        if saved is None:
            rng = random.Random(seed)
            self.channels = dict(zip(SYMBOLS, rng.sample(range(1, 2**32), len(SYMBOLS))))
            self.rng = json.loads(m.encoded(rng.getstate()))
            self.core = resolve_kernel(KERNEL).create({'seed': seed, 'energy_seed': seed ^ 0x1634AB}, backend='native')
            self.time, self.reader, self.sensory = 0, Reader(dimension=DIMENSION), Reader()
            self.port_reader = Reader(dimension=DIMENSION)
            self.endpoint_reader, self.endpoint_port_reader = Reader(), Reader()
            self.inputs, self.rows, self.branch = [], [], None
            self.body, self.actuator = {'kind': 'passive-answer-terminal'}, 0
        else:
            if saved['seed'] != seed:
                raise ValueError('identity mismatch')
            self.channels, self.rng = saved['mappings'], copy.deepcopy(saved['rng'])
            self.core = resolve_kernel(KERNEL).create(state=m.StateImage.from_dict(saved['core']), backend='native')
            self.time = saved['time_us']
            self.reader, self.sensory = Reader(saved['reader']), Reader(saved['sensory_control'])
            self.port_reader = Reader(saved['port_reader'])
            self.endpoint_reader = Reader(saved['endpoint_reader'])
            self.endpoint_port_reader = Reader(saved['endpoint_port_reader'])
            self.inputs, self.rows = copy.deepcopy(saved['inputs']), copy.deepcopy(saved['rows'])
            self.branch, self.body = copy.deepcopy(saved['branch']), copy.deepcopy(saved['body'])
            self.actuator = saved['actuator']
            if self.save() != saved:
                raise RuntimeError('whole-system restore mismatch')

    @classmethod
    def restore(cls, state):
        return cls(state['seed'], state)

    def save(self):
        return {'schema': 'threemind.m5-process61-whole/1', 'seed': self.seed, 'core': self.core.capture_state().to_dict(),
                'time_us': self.time, 'mappings': self.channels, 'rng': copy.deepcopy(self.rng),
                'reader': self.reader.save(), 'sensory_control': self.sensory.save(),
                'port_reader': self.port_reader.save(),
                'endpoint_reader': self.endpoint_reader.save(), 'endpoint_port_reader': self.endpoint_port_reader.save(),
                'readout_spec': {'fields': list(FIELDS), 'bins_us': [list(v) for v in BINS], 'dimension': DIMENSION},
                'inputs': copy.deepcopy(self.inputs), 'rows': copy.deepcopy(self.rows),
                'branch': copy.deepcopy(self.branch), 'body': copy.deepcopy(self.body), 'actuator': self.actuator}

    def features(self):
        nodes = {n['channel']: n for n in self.core.observation_nodes()}
        # Stable anonymous channel order; no AB-only hand selection or answer lookup.
        return [nodes.get(c, {}).get('activation', 0.) for c in sorted(self.channels.values())]

    def port_features(self, features):
        # Two declared physical output interfaces; their word/sign meaning is learned.
        ports = {self.channels['A'], self.channels['B']}
        ordered = sorted(self.channels.values())
        return [v if ordered[i % 12] in ports else 0. for i, v in enumerate(features)]

    def tick(self, t, frames=None, observed=False):
        if t < self.time:
            raise ValueError('time reversal')
        frames = frames or []
        for frame in frames:
            self.inputs.append({'time_us': t, 'values': copy.deepcopy(frame)})
            self.core.inject(m.Stimulus(t, tuple((self.channels[k], v) for k, v in frame.items()), 1.))
        self.core.advance_to(t)
        self.time = t
        if self.core.life == 'dead':
            raise RuntimeError('new subject death; preserve incomplete marker')
        if observed:
            before = m.digest(self.save())
            self.features(); self.core.graph(); self.core.metrics(); self.save()
            if m.digest(self.save()) != before:
                raise RuntimeError('observation mutates whole subject')

    def advance(self, end, events=None, observed=False):
        events = events or {}
        if (end-self.time) % 1000:
            raise ValueError('declared 1ms grid required')
        for t in range(self.time+1000, end+1, 1000):
            frames = list(events.get(t, []))
            if t % 500_000 == 0:
                frames = [{'K': .2}]+frames
            self.tick(t, frames, observed=observed and t % 50_000 == 0)

    def fork(self, label):
        before = self.save()
        child = Subject.restore(before)
        child.branch = {'parent_sha256': m.digest(before), 'label': label, 'time_us': self.time}
        return child


def teach(subject, history=None, observed=False):
    """16 rounds with 0.8/1.0/1.2-s gaps; new learning includes equal-duration old review."""
    start = subject.time
    groups = ['UVA', 'ZWB'] if history is None else ['UVA', 'ZWB', 'XYA' if history == 0 else 'XYB',
                                                                    'CDB' if history == 0 else 'CDA']
    if subject.seed % 2:
        groups = groups[::-1]
    events = {}
    onset = start + 1_000_000
    for r in range(16):
        for j, group in enumerate(groups):
            events[onset+j*250_000] = [dict.fromkeys(group, .4)]
        if r < 15:
            onset += (800_000 if r < 5 else 1_000_000 if r < 10 else 1_200_000)
    totals = dict.fromkeys(SYMBOLS, 0.)
    order = sorted(subject.channels.values())
    for t in range(start+50_000, start+18_000_001, 50_000):
        subject.advance(t, events, observed=observed)
        values = subject.features()
        for symbol, channel in subject.channels.items():
            totals[symbol] += values[order.index(channel)]/360
    return {'mean_activation': totals, 'round_gaps_us': [800_000]*5+[1_000_000]*5+[1_200_000]*5,
            'old_new_activity_residual': abs(sum(totals[s] for s in 'UVZW')-sum(totals[s] for s in 'XYCD'))/4}


def process_features(trajectory):
    if len(trajectory) != 250 or [r['dt_us'] for r in trajectory] != list(range(1000, 250001, 1000)):
        raise ValueError('complete 1-ms observation window required')
    values = []
    for lo, hi in BINS:
        selected = [r for r in trajectory if lo <= r['dt_us'] <= hi]
        for field in FIELDS:
            for i in range(12):
                values.append(sum(r[field][i] for r in selected) / len(selected))
    return values


def question(subject, cue, dose=.8, observed=False):
    """Continuous one-second question; process answer at 250 ms, endpoint control at 110 ms."""
    start = subject.time
    frame = dict.fromkeys(cue, dose/len(cue)) if cue else {}
    begin = m.digest(subject.save())
    subject.tick(start, [frame] if frame else [], observed)
    trajectory = []
    for dt in range(1000, 1000001, 1000):
        subject.tick(start+dt, [{'K': .2}] if (start+dt) % 500000 == 0 else [],
                     observed=observed and dt % 50000 == 0)
        if dt <= 250000:
            nodes = {n['channel']: n for n in subject.core.observation_nodes()}
            row = {'dt_us': dt}
            for field in FIELDS:
                row[field] = [nodes.get(c, {}).get(field, 0.) for c in sorted(subject.channels.values())]
            trajectory.append(row)
        if dt == 110000:
            endpoint_features = trajectory[-1]['activation']
            endpoint_response = subject.endpoint_reader.infer(endpoint_features)
            endpoint_port_response = subject.endpoint_port_reader.infer(subject.port_features(endpoint_features))
        if dt == 250000:
            features = process_features(trajectory)
            response = subject.reader.infer(features)
            port_response = subject.port_reader.infer(subject.port_features(features))
            subject.actuator = response['answer']
    sensory = [frame.get(next(s for s, c2 in subject.channels.items() if c2 == c), 0.)
               for c in sorted(subject.channels.values())]
    row = {'start_us': start, 'end_us': subject.time, 'cue': cue, 'dose': dose,
           'features': features, 'port_features': subject.port_features(features), 'sensory': sensory,
           'response': response, 'port_response': port_response, 'sensory_response': subject.sensory.infer(sensory),
           'endpoint_features': endpoint_features, 'endpoint_port_features': subject.port_features(endpoint_features),
           'endpoint_response': endpoint_response, 'endpoint_port_response': endpoint_port_response,
           'trajectory': trajectory, 'before_sha256': begin,
           'reader_sha256': m.digest(subject.reader.save()), 'port_reader_sha256': m.digest(subject.port_reader.save()),
           'endpoint_reader_sha256': m.digest(subject.endpoint_reader.save()),
           'endpoint_port_reader_sha256': m.digest(subject.endpoint_port_reader.save())}
    subject.rows.append(row)
    return copy.deepcopy(row)


def label(cue, history=0):
    if set(cue) <= set('UV'):
        return 1
    if set(cue) <= set('ZW'):
        return -1
    if set(cue) <= set('XY'):
        return 1 if history == 0 else -1
    if set(cue) <= set('CD'):
        return -1 if history == 0 else 1
    raise ValueError('no scoring target')


def exam(subject, history, dose=.8, observed=False):
    cues = list(zip(NEW, OLD))
    if subject.seed % 2:
        cues = cues[::-1]
    rows = []
    for pair in cues:
        for cue in pair:
            row = question(subject, cue, dose, observed)
            rows.append(row | {'label': label(cue, history), 'group': 'new' if cue in NEW else 'old'})
    return rows


def learn_readers(subject, rows):
    for name, key in (('reader', 'features'), ('port_reader', 'port_features'),
                      ('sensory', 'sensory'), ('endpoint_reader', 'endpoint_features'),
                      ('endpoint_port_reader', 'endpoint_port_features')):
        getattr(subject, name).learn([{'features': r[key], 'label': r['label']} for r in rows])


def calibrate(subject, observed=False):
    teach(subject, observed=observed)
    rows = []
    for dose in (.7, .9):
        for cue in (OLD if subject.seed % 2 == 0 else OLD[::-1]):
            rows.append(question(subject, cue, dose, observed) | {'label': label(cue)})
    learn_readers(subject, rows)
    development, corrections = [], []
    for cycle in range(3):
        dev = [question(subject, cue, .75, observed) | {'label': label(cue)}
               for cue in (OLD if subject.seed % 2 == 0 else OLD[::-1])]
        development.append(dev)
        wrong = [r for r in dev if len(r['cue']) == 1 and
                 any(r[key]['answer'] != r['label'] for key in ('response', 'port_response'))]
        if not wrong or cycle == 2: break
        # The teacher corrects observed old-task errors; no future task labels enter this stage.
        groups = sorted({'UVA' if set(r['cue']) <= set('UV') else 'ZWB' for r in wrong})
        start = subject.time
        events = {start + 1_000_000 + j * 250_000: [dict.fromkeys(group, .4)] for j, group in enumerate(groups)}
        wait = (6, 18)[cycle]
        subject.advance(start + wait * 1_000_000, events, observed)
        sampled = [question(subject, cue, .75, observed) | {'label': label(cue)}
                   for cue in (OLD if subject.seed % 2 == 0 else OLD[::-1])]
        learn_readers(subject, sampled)
        corrections.append({'cycle': cycle + 1, 'wrong_cues': [r['cue'] for r in wrong], 'teacher_groups': groups,
                            'start_us': start, 'review_wait_s': wait, 'samples': sampled, 'end_us': subject.time})
    return {'initial': rows, 'development': development, 'corrections': corrections,
            'maximum_correction_rounds': 2, 'future_new_labels_used': False}


def plasticity(subject, enabled):
    before = subject.save()
    subject.core.reconfigure(replace(subject.core.config, plasticity=enabled))
    after = subject.save()
    if subject.time != before['time_us'] or before['reader'] != after['reader']:
        raise RuntimeError('configuration changed time or reader')
    return {'enabled': enabled, 'changed_paths': differences(before, after),
            'note': 'Existing plasticity bundle: contact growth, strengthening, retention decay and fast learning; not a pure learning-only switch.'}


def mask(subject, arm):
    before = subject.save()
    graph = subject.core.graph()
    nodes = {n['channel']: n['id'] for n in graph['nodes']}
    groups = {}
    for name, symbols in (('target', 'XYCD'), ('matched', 'UVZW')):
        ids = {nodes[subject.channels[s]] for s in symbols}
        outputs = {nodes[subject.channels[s]] for s in 'AB'}
        groups[name] = [e for e in graph['edges'] if e['source'] in ids and e['target'] in outputs]
    weights = {k: [e['weight'] for e in es] for k, es in groups.items()}
    degree = {k: sorted([[sum(e['source'] == n for e in graph['edges']), sum(e['target'] == n for e in graph['edges'])]
                         for edge in es for n in (edge['source'], edge['target'])]) for k, es in groups.items()}
    selected = groups['matched' if arm == 'matched' else 'target'] if arm in ('target', 'matched', 'restored') else []
    pairs = [[e['source'], e['target']] for e in selected]
    if pairs:
        subject.core.intervene(edges=pairs, action='silence')
    if arm == 'restored':
        subject.core.intervene(edges=pairs, action='restore')
    after = subject.save()
    if arm in ('sham', 'restored') and before != after:
        raise RuntimeError('sham/restoration changed full state')
    if set(differences(before, after)) - {'core.silenced_edges'}:
        raise RuntimeError('mask changed undeclared state')
    delta = abs(float(np.mean(weights['target']))-float(np.mean(weights['matched']))) if all(weights.values()) else None
    return {'arm': arm, 'pairs': pairs, 'weights': weights, 'degrees': degree,
            'weight_mean_residual': delta, 'count': {k: len(v) for k, v in groups.items()},
            'matching_valid': all(len(v) == 4 for v in groups.values()) and degree['target'] == degree['matched']
                              and delta is not None and delta <= .05,
            'changed_paths': differences(before, after)}
