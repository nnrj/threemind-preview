"""M5 personal-reader study apparatus. No production kernel modifications."""
from __future__ import annotations

import copy
import json
import random
from dataclasses import replace

import numpy as np
import pilot_m2 as m
from pilot_m1 import differences

SYMBOLS = 'ABUVZWXYCDKN'
OLD = ('U', 'V', 'UV', 'Z', 'W', 'ZW')
NEW = ('X', 'Y', 'XY', 'C', 'D', 'CD')
MARGIN = .25


class Reader:
    """Personal linear expression, with fixed calibration scaling and ridge state."""
    def __init__(self, saved=None):
        self.scale = np.ones(12)
        self.gram = np.eye(12)*.001
        self.rhs = np.zeros(12)
        self.weights = np.zeros(12)
        self.samples = []
        self.updates = 0
        self.calibrated = False
        if saved:
            for k in ('scale', 'gram', 'rhs', 'weights'):
                setattr(self, k, np.array(saved[k], dtype=float))
            self.samples = copy.deepcopy(saved['samples'])
            self.updates, self.calibrated = saved['updates'], saved['calibrated']

    def save(self):
        return {'schema': 'threemind.m5-personal-linear/1',
                **{k: getattr(self, k).tolist() for k in ('scale', 'gram', 'rhs', 'weights')},
                'samples': copy.deepcopy(self.samples), 'updates': self.updates,
                'calibrated': self.calibrated, 'ridge': .001, 'margin': MARGIN}

    def learn(self, rows):
        if not rows:
            raise ValueError('empty calibration')
        x = np.array([r['features'] for r in rows], dtype=float)
        y = np.array([r['label'] for r in rows], dtype=float)
        if x.shape != (len(rows), 12) or not np.isfinite(x).all() or not set(y) <= {-1., 1.}:
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
        if a.shape != (12,) or not np.isfinite(a).all():
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
            cfg = m.Local51Config(seed=seed, energy_seed=seed ^ 0x1634AB)
            self.core = m.create_engine(cfg, kernel_id=m.KERNEL, backend='native')
            self.time, self.reader, self.sensory = 0, Reader(), Reader()
            self.port_reader = Reader()
            self.inputs, self.rows, self.branch = [], [], None
            self.body, self.actuator = {'kind': 'passive-answer-terminal'}, 0
        else:
            if saved['seed'] != seed:
                raise ValueError('identity mismatch')
            self.channels, self.rng = saved['mappings'], copy.deepcopy(saved['rng'])
            self.core = m.create_engine(state=m.StateImage.from_dict(saved['core']), kernel_id=m.KERNEL, backend='native')
            self.time = saved['time_us']
            self.reader, self.sensory = Reader(saved['reader']), Reader(saved['sensory_control'])
            self.port_reader = Reader(saved['port_reader'])
            self.inputs, self.rows = copy.deepcopy(saved['inputs']), copy.deepcopy(saved['rows'])
            self.branch, self.body = copy.deepcopy(saved['branch']), copy.deepcopy(saved['body'])
            self.actuator = saved['actuator']
            if self.save() != saved:
                raise RuntimeError('whole-system restore mismatch')

    @classmethod
    def restore(cls, state):
        return cls(state['seed'], state)

    def save(self):
        return {'schema': 'threemind.m5-whole/1', 'seed': self.seed, 'core': self.core.capture_state().to_dict(),
                'time_us': self.time, 'mappings': self.channels, 'rng': copy.deepcopy(self.rng),
                'reader': self.reader.save(), 'sensory_control': self.sensory.save(),
                'port_reader': self.port_reader.save(),
                'inputs': copy.deepcopy(self.inputs), 'rows': copy.deepcopy(self.rows),
                'branch': copy.deepcopy(self.branch), 'body': copy.deepcopy(self.body), 'actuator': self.actuator}

    def features(self):
        nodes = {n['channel']: n for n in self.core.observation_nodes()}
        # Stable anonymous channel order; no AB-only hand selection or answer lookup.
        return [nodes.get(c, {}).get('activation', 0.) for c in sorted(self.channels.values())]

    def port_features(self, features):
        # Two declared physical output interfaces; their word/sign meaning is learned.
        ports = {self.channels['A'], self.channels['B']}
        return [v if c in ports else 0. for c, v in zip(sorted(self.channels.values()), features)]

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
    """16 fixed rounds; new learning includes equal-duration declared old review."""
    start = subject.time
    groups = ['UVA', 'ZWB'] if history is None else ['UVA', 'ZWB', 'XYA' if history == 0 else 'XYB',
                                                                    'CDB' if history == 0 else 'CDA']
    if subject.seed % 2:
        groups = groups[::-1]
    events = {}
    for r in range(16):
        for j, group in enumerate(groups):
            events[start+1_000_000+r*1_000_000+j*250_000] = [dict.fromkeys(group, .4)]
    totals = dict.fromkeys(SYMBOLS, 0.)
    order = sorted(subject.channels.values())
    for t in range(start+50_000, start+18_000_001, 50_000):
        subject.advance(t, events, observed=observed)
        values = subject.features()
        for symbol, channel in subject.channels.items():
            totals[symbol] += values[order.index(channel)]/360
    return {'mean_activation': totals,
            'old_new_activity_residual': abs(sum(totals[s] for s in 'UVZW')-sum(totals[s] for s in 'XYCD'))/4}


def question(subject, cue, dose=.8, observed=False):
    """One second of continuous experience, answer fixed at 110ms. No teacher input."""
    start = subject.time
    frame = dict.fromkeys(cue, dose/len(cue)) if cue else {}
    # The preceding complete interval already delivered K at this boundary.
    frames = [frame] if frame else []
    begin = m.digest(subject.save())
    subject.tick(start, frames, observed)
    trajectory = []
    for dt in range(1000, 1_000_001, 1000):
        subject.tick(start+dt, [{'K': .2}] if (start+dt) % 500_000 == 0 else [],
                     observed=observed and dt % 50_000 == 0)
        if dt <= 250_000:
            trajectory.append({'dt_us': dt, 'features': subject.features()})
        if dt == 110_000:
            features = subject.features()
            response = subject.reader.infer(features)
            port_response = subject.port_reader.infer(subject.port_features(features))
            subject.actuator = response['answer']
    sensory = [frame.get(next(s for s, c2 in subject.channels.items() if c2 == c), 0.)
               for c in sorted(subject.channels.values())]
    row = {'start_us': start, 'end_us': subject.time, 'cue': cue, 'dose': dose,
           'features': features, 'port_features': subject.port_features(features), 'sensory': sensory,
           'response': response, 'port_response': port_response,
           'sensory_response': subject.sensory.infer(sensory), 'trajectory': trajectory,
           'reader_sha256': m.digest(subject.reader.save()), 'before_sha256': begin}
    row['port_reader_sha256'] = m.digest(subject.port_reader.save())
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


def calibrate(subject, observed=False):
    teach(subject, observed=observed)
    rows = []
    for dose in (.7, .9):
        for cue in (OLD if subject.seed % 2 == 0 else OLD[::-1]):
            rows.append(question(subject, cue, dose, observed) | {'label': label(cue)})
    subject.reader.learn([{'features': r['features'], 'label': r['label']} for r in rows])
    subject.port_reader.learn([{'features': r['port_features'], 'label': r['label']} for r in rows])
    subject.sensory.learn([{'features': r['sensory'], 'label': r['label']} for r in rows])
    return rows


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
