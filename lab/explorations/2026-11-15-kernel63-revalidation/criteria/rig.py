"""Port of frozen cross-system-criteria/2 measurement; explicit new 6.3 identity.

The four controller implementations, materials, body, readout and interventions
are unchanged. Only Core construction/restoration, mode metadata and the whole
state schema differ from the selected functions of closure_rig.py.
"""
from __future__ import annotations
import copy
import math
import random
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import pilot_m2 as m
from pilot_m1 import differences
from pilot_m3 import Controller
from threemind_kernels.registry import resolve_kernel
KERNEL = 'threemind.continuous-memory/6.3'
KINDS = ('reactive', 'finite-state', 'hebbian', 'fixed-rnn-reader', 'threemind')


class Rig:
    def __init__(self, kind, seed, mode='6.3-default', saved=None):
        self.kind, self.seed, self.mode = kind, seed, mode
        if saved is None:
            self.channels, self.rng = m.mapping(seed)
            self.time = 0
            self.inputs, self.rows = [], []
            self.body = {'x': .3125, 'v': 0., 'gate': 0}
            self.actuator = 0.
            self.branch = None
            if kind == 'threemind':
                cfg = {'seed': seed, 'energy_seed': seed ^ 0x1634AB}
                self.model = resolve_kernel(KERNEL).create(cfg, backend='native')
            else:
                ordered = sorted(self.channels.values())
                self.model = Controller(kind, seed, ordered.index(self.channels['A']), ordered.index(self.channels['B']))
        else:
            if (saved['kind'], saved['seed'], saved['mode']) != (kind, seed, mode):
                raise ValueError('rig identity mismatch')
            self.channels, self.rng = saved['mappings'], saved['rng']
            self.time, self.inputs, self.rows = saved['time_us'], copy.deepcopy(saved['inputs']), copy.deepcopy(saved['rows'])
            self.body, self.actuator, self.branch = copy.deepcopy(saved['body']), saved['actuator'], saved['branch']
            if kind == 'threemind':
                self.model = resolve_kernel(KERNEL).create(state=m.StateImage.from_dict(saved['model']), backend='native')
            else:
                c = saved['model']
                self.model = Controller(kind, seed, c['a'], c['b'], c)
            if self.save() != saved:
                raise RuntimeError('whole restoration mismatch')

    def save(self):
        return {'schema': 'threemind.criteria63-whole/1', 'kind': self.kind, 'seed': self.seed, 'mode': self.mode,
                'model': self.model.capture_state().to_dict() if self.kind == 'threemind' else self.model.save(),
                'time_us': self.time, 'mappings': self.channels, 'rng': self.rng,
                'body': copy.deepcopy(self.body), 'actuator': self.actuator, 'branch': self.branch,
                'inputs': copy.deepcopy(self.inputs), 'rows': copy.deepcopy(self.rows),
                'reader': {'kind': 'fixed-AB' if self.kind == 'threemind' else self.kind,
                           'Core_trainable_reader': False},
                'optimizer': None if self.kind != 'fixed-rnn-reader' else 'RLS-P-in-model'}

    @classmethod
    def restore(cls, saved):
        return cls(saved['kind'], saved['seed'], saved['mode'], saved)

    def observe(self):
        if self.kind != 'threemind':
            return self.model.observe()
        p = m.project(self.model.observation_nodes(), self.channels)
        return p['activation'][0] - p['activation'][1]

    def tick(self, t, values=None, *, frequent=False, log=False):
        if t < self.time:
            raise ValueError('time reversal')
        frames = values if isinstance(values, list) else [values or {}]
        values = {}
        for frame in frames:
            if frame:
                self.inputs.append({'time_us': t, 'values': dict(frame)})
            for symbol, value in frame.items():
                values[symbol] = values.get(symbol, 0.)+value
        if self.kind == 'threemind':
            for frame in frames:
                if frame:
                    self.model.inject(m.Stimulus(t, tuple((self.channels[s], v) for s, v in frame.items()), 1.))
            self.model.advance_to(t)
            if self.model.life == 'dead':
                raise RuntimeError('new subject death; preserve marker')
        elif values or t % 50_000 == 0:
            ordered = sorted(self.channels.values())
            x = np.zeros(8)
            for symbol, value in values.items():
                x[ordered.index(self.channels[symbol])] += value
            self.model.step(x)
        self.time = t
        self.actuator = self.observe()
        if frequent:
            before = m.digest(self.save())
            self.observe(); self.save()
            if self.kind == 'threemind':
                self.model.graph(); self.model.metrics(); self.model.capture_state()
            if m.digest(self.save()) != before:
                raise RuntimeError('observer mutates state')
        if log:
            self.rows.append({'time_us': t, 'response': self.actuator, 'body': copy.deepcopy(self.body)})
        return self.actuator

    def advance(self, end, events=None, *, step=50_000, frequent=False, log=False):
        events = events or {}
        if end < self.time or (end-self.time) % step:
            raise ValueError('invalid declared time grid')
        for t in range(self.time+step, end+1, step):
            self.tick(t, events.get(t), frequent=frequent, log=log)

    def fork(self, label):
        saved = self.save()
        child = Rig.restore(saved)
        child.branch = {'parent_sha256': m.digest(saved), 'label': label, 'time_us': self.time}
        return child



def teaching(rig, history, intensity=.4, delay=1, trained=True):
    end = (17+delay)*1_000_000
    events = {t: [{'K': .2}] for t in range(0, end+1, 500_000)}
    if trained:
        groups = ('XYA', 'ZWB') if history == 0 else ('XYB', 'ZWA')
        if rig.seed % 2:
            groups = groups[::-1]
        for r in range(16):
            for j, group in enumerate(groups):
                events.setdefault(1_000_000+r*1_000_000+j*250_000, []).append(dict.fromkeys(group, intensity))
    events.setdefault(17_000_000, []).append({'N': .2})
    rig.tick(0, events[0])
    records = []
    for t in range(50_000, end+1, 50_000):
        values = events.get(t)
        rig.tick(t, values)
        if 1_000_000 <= t <= 17_000_000:
            if rig.kind == 'fixed-rnn-reader':
                records.append({'h': rig.model.h.tolist(), 'target': bool(values and any('X' in v or 'Y' in v for v in values))})
            elif rig.kind == 'threemind':
                nodes = {n['channel']: n for n in rig.model.observation_nodes()}
                records.append({'activation': {s: nodes.get(c, {}).get('activation', 0.) for s, c in rig.channels.items()}})
    return records



def matching(a, records=None):
    graph = a.model.graph()
    nodes = {n['channel']: n['id'] for n in graph['nodes']}
    rows = {}
    for group in ('XY', 'ZW'):
        edges = [e for e in graph['edges'] if e['source'] in {nodes[a.channels[s]] for s in group}
                 and e['target'] in {nodes[a.channels[s]] for s in 'AB'}]
        rows[group] = [{'weight': e['weight'], 'degrees': [
            [sum(f['source'] == n for f in graph['edges']), sum(f['target'] == n for f in graph['edges'])]
            for n in (e['source'], e['target'])]} for e in edges]
    count = [len(rows[g]) for g in ('XY', 'ZW')]
    delta = None if count != [2, 2] else sum(r['weight'] for r in rows['XY'])/2-sum(r['weight'] for r in rows['ZW'])/2
    degree_equal = count == [2, 2] and sorted(str(r['degrees']) for r in rows['XY']) == sorted(str(r['degrees']) for r in rows['ZW'])
    activity_delta = 0. if not records else sum(sum(r['activation'][s] for s in 'XY')-
                    sum(r['activation'][s] for s in 'ZW') for r in records)/(2*len(records))
    return {'rows': rows, 'count': count, 'weight_residual': delta, 'degree_equal': degree_equal,
            'teaching_activity_residual': activity_delta,
            'passed': degree_equal and abs(delta) <= .02 and abs(activity_delta) <= .02}



def probe(rig, cue='X', dose=.8, *, second=None, gate=False, frequent=False, restore_mid=False, pause_mid=False):
    start = rig.time
    initial = len(rig.rows)
    rig.tick(start, dict.fromkeys(cue, dose/len(cue)) if cue else {})
    events = {start+500_000: {'K': .2}, start+1_000_000: {'K': .2}, start+1_500_000: {'K': .2}}
    if second:
        events.setdefault(start+500_000, {}).update({second: dose})
    action = 0
    for t in range(start+1000, start+1_500_001, 1000):
        rig.tick(t, events.get(t), frequent=frequent and (t-start) % 50_000 == 0)
        if t == start+110_000 and gate:
            action = int(rig.actuator > 1e-4)-int(rig.actuator < -1e-4)
            rig.body['gate'] = action
            events[start+250_000] = {'X' if action > 0 else 'Z' if action < 0 else 'N': .2}
        if t == start+360_000 and gate:
            next_action = int(rig.actuator > 1e-4)-int(rig.actuator < -1e-4)
            rig.body['gate'] = max(-1, min(1, rig.body['gate']+next_action))
        rig.rows.append({'time_us': t, 'response': rig.actuator, 'body': copy.deepcopy(rig.body)})
        if t == start+500_000:
            if restore_mid:
                restored = Rig.restore(rig.save())
                rig.__dict__.update(restored.__dict__)
            if pause_mid:
                import time
                saved = rig.save(); time.sleep(.03)
                if rig.save() != saved: raise RuntimeError('wall pause changed whole state')
    rows = rig.rows[initial:]
    def integral(lo, hi):
        return sum(r['response']*.001 for r in rows if lo <= r['time_us']-start <= hi)
    first = next(r['response'] for r in rows if r['time_us'] == start+110_000)
    return {'start_us': start, 'first': first, 'choice': action if gate else int(first>1e-4)-int(first < -1e-4),
            'early_integral': integral(100_000, 300_000), 'late_integral': integral(500_000, 1_500_000),
            'late_mean': integral(500_000, 1_500_000)/1.001,
            'peak': max(abs(r['response']) for r in rows if r['time_us']-start <= 500_000),
            'trace_count': len(rows), 'final_sha256': m.digest(rig.save())}



def rnn_selection(rig, records):
    h = np.asarray([r['h'] for r in records])
    mask = np.asarray([r['target'] for r in records])
    activity = np.abs(h).mean(axis=0)
    weight = np.abs(rig.model.w)
    selectivity = np.abs(h[mask].mean(axis=0)-h[~mask].mean(axis=0))*weight
    features = np.stack([weight, activity], axis=1)
    scale = np.maximum(features.std(axis=0), 1e-9)
    # Pair first under a fixed nuisance caliper, then rank teaching selectivity.
    # A top-eight-first selection can exhaust adequate weight-matched controls.
    pairs = [(float(selectivity[j]-selectivity[k]), j, k) for j in range(64) for k in range(64)
             if j != k and selectivity[j] >= selectivity[k]
             and np.max(np.abs((features[j]-features[k])/scale)) <= .5]
    pairs.sort(key=lambda v: (-v[0], v[1], v[2]))
    targets, controls, used = [], [], set()
    for _, j, k in pairs:
        if j in used or k in used: continue
        targets.append(j); controls.append(k); used.update((j,k))
        if len(targets) == 8: break
    residual = np.abs(features[targets].mean(axis=0)-features[controls].mean(axis=0))/scale
    return {'target': targets, 'matched': controls, 'standardized_residual': residual.tolist(),
            'passed': len(targets) == 8 and bool(np.all(residual <= .5)), 'teaching_only': True,
            'matching_rule': 'pair-first per-feature standardized caliper .5, rank teaching selectivity difference'}



def intervene(rig, arm, selection=None):
    before = rig.save()
    child = rig.fork(arm)
    if arm in ('intact', 'sham', 'restored'):
        # Restored arm actually applies and then undoes the chosen state intervention.
        if arm == 'restored':
            masked, receipt = intervene(rig, 'target', selection)
            child = Rig.restore(masked.save())
            child = Rig.restore(before)
            return child, receipt | {'restored_exactly': child.save() == before}
        return child, {'arm': arm, 'changed_paths': []}
    if arm not in ('target', 'matched', 'all'):
        raise ValueError('unknown intervention')
    group = 'ZW' if arm == 'matched' else 'XY'
    if rig.kind == 'threemind':
        graph = child.model.graph()
        nodes = {n['channel']: n['id'] for n in graph['nodes']}
        edges = [[e['source'], e['target']] for e in graph['edges'] if arm == 'all' or (
            e['source'] in {nodes[rig.channels[s]] for s in group} and
            e['target'] in {nodes[rig.channels[s]] for s in 'AB'})]
        child.model.intervene(edges=edges, action='silence')
    else:
        ordered = sorted(rig.channels.values())
        ids = [ordered.index(rig.channels[s]) for s in group]
        c = child.model
        if rig.kind == 'finite-state':
            c.memory[:] = 0 if arm == 'all' else c.memory
            if arm != 'all': c.memory[ids] = 0
        elif rig.kind == 'hebbian':
            if arm == 'all': c.W[:] = 0
            else: c.W[np.ix_(ids, [c.a, c.b])] = 0
        elif rig.kind == 'fixed-rnn-reader':
            if arm == 'all': c.R[:] = 0
            else: c.h[selection[arm]] = 0
    return child, {'arm': arm, 'changed_paths': differences(before, child.save()), 'selection': selection}



def ring_stage(rig, environment, seconds=30, sign=1, replay=None):
    """Environment→sense→model→motor→position, with no score supplied to model."""
    start = rig.time
    inputs = []
    rows = []
    replay = None if replay is None else {r['relative_us']: r['values'] for r in replay}
    for i in range(1, seconds*20+1):
        t = start+i*50_000
        values = {}
        if replay is not None:
            values = replay.get(i*50_000, {})
        else:
            if i % 10 == 0: values['K'] = .2
            if i % 20 == 1:
                left = rig.body['x'] < .5
                group = ('XYA' if left else 'ZWB') if environment == 'P' else ('XYB' if left else 'ZWA')
                values.update(dict.fromkeys(group, .8))
            if i % 5 == 0:
                values['N'] = .05+.1*abs(rig.body['v'])
        rig.tick(t, values)
        rig.body['v'] = .9*rig.body['v']+.1*sign*math.tanh(rig.actuator)
        rig.body['x'] = (rig.body['x']+.05*rig.body['v']) % 1.
        if values: inputs.append({'relative_us': i*50_000, 'values': dict(values)})
        rows.append({'time_us': t, 'response': rig.actuator, 'body': copy.deepcopy(rig.body)})
    rig.rows.extend(rows)
    return {'environment': environment, 'sign': sign, 'input_frames': inputs, 'start_us': start,
            'end_us': rig.time, 'model_sha256': m.digest(rig.save()['model']),
            'path_displacement': abs(rows[-1]['body']['x']-rows[0]['body']['x'])}



def case_seed(package, origin, delay=0):
    return {'X1': 1016100, 'X2': 1026100, 'X3': 1036100}[package]+delay*100+origin



def serializable_rng(seed):
    return list(random.Random(seed).getstate())
