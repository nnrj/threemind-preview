"""AS63-03 declared peripheral controls; genuine kernels and immutable originals."""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from threemind_core import StateImage, Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime.adapters import channel_id
from threemind_runtime.energy_supply import EnergySupplier, EnergySupplyConfig
from threemind_runtime.inheritance import birth, birth_metadata
from threemind_runtime.readout_session import ReadoutSession

WORK = ROOT / '.work/ring-mechanism63-20261118'
OLD = ROOT / '.work/input-rate-autonomy-20260929/cases/world'
PROFILE_FILE = ROOT / 'lab/explorations/2026-11-15-kernel63/resource_bypass/configurations.json'
NS = UUID('892c2b60-4562-4051-9a2d-bbc4961dc5d1')
PROJECT = 'd0a04159-ee0f-4200-ada9-13d5ce7197b7'
SEEDS = (9293201, 9293202)
HISTORIES = (0, 2)
PROFILES = ('legacy1', 'default63', 'prefix63')
STARTS = (.0625, .5625)
MOTOR_NS = 'world-motor-v1:ring-study-v1:0'
SENSE_NS = 'ring-sensory-v1'
READOUT = {k: {'enabled': False} for k in ('structural_readout', 'temporal_readout', 'activity_readout')}
SUPPLY = EnergySupplyConfig(enabled=True, rate_per_s=10, interval_us=100000, total_supply_limit=None)

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''): h.update(block)
    return h.hexdigest()

def save(path, value):
    path = Path(path)
    data = encoded(value)
    if path.suffix == '.gz': data = gzip.compress(data, compresslevel=3, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == data, 'immutable evidence differs: ' + str(path)
    else:
        with path.open('xb') as f: f.write(data)

def read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)

def guard():
    import psutil
    if (WORK / 'STOP').exists(): raise RuntimeError('operator STOP')
    assert shutil.disk_usage('E:/').free > 25*2**30, 'E disk reserve'
    assert shutil.disk_usage('C:/').free > 5*2**30, 'C disk reserve'
    assert psutil.virtual_memory().available > 4*2**30, 'RAM reserve'
    info = psutil.Process().memory_info()
    assert getattr(info, 'private', info.rss) < 2**30, 'process memory cap'

def kernel(profile):
    return 'threemind.continuous-memory/' + ('1' if profile == 'legacy1' else '6.3')

def config(profile, material):
    if profile == 'legacy1':
        cfg = copy.deepcopy(material['old_config'])
        cfg['energy_simulation_enabled'] = False
        return cfg
    cfg = copy.deepcopy(read(PROFILE_FILE)['S101/bypass']) if profile == 'prefix63' else {}
    cfg.update(seed=material['seed'], energy_simulation_enabled=False)
    return cfg

def material(seed, index):
    folder = OLD / f's{seed}/g0/c{index}'
    world = read(folder / 'world.json.gz')
    image = read(folder / 'parent-state.json.gz')
    frames = []
    with gzip.open(folder / 'input-frames.jsonl.gz', 'rt', encoding='utf8') as f:
        for line in f:
            row = json.loads(line)
            if 'stimulus' in row:
                assert row['status'] == 'delivered'
                frames.append(row)
    frames.sort(key=lambda r: (int(r['delivered_time_us']), int(r['core_sequence'])))
    mapping = {}
    for row in world['rows']:
        for n in row['nodes']:
            if str(n['channel']) in mapping: assert mapping[str(n['channel'])] == int(n['id'])
            mapping[str(n['channel'])] = int(n['id'])
    all_channels = {int(ch) for f in frames for ch, amp in f['stimulus']['channels']}
    all_channels.update(channel_id(seed, SENSE_NS, i) for i in range(10))
    added = {}
    for ch in sorted(all_channels - set(map(int, mapping))):
        added[str(ch)] = max(mapping.values()) + 1
        mapping[str(ch)] = added[str(ch)]
    return {'seed': seed, 'index': index, 'key': f's{seed}-c{index}',
            'old_config': image['config'], 'bindings': mapping, 'completed_bindings': added,
            'frames': frames, 'senses': world['senses'], 'rows': world['rows'],
            'final_body': world['final_body'],
            'sources': {str(p.relative_to(ROOT)): sha(p) for p in
                        (folder/'world.json.gz', folder/'parent-state.json.gz', folder/'input-frames.jsonl.gz')}}

def controls(seed, nodes, bindings):
    raw = math.tanh(.5 * math.fsum(
        (1 if channel_id(seed, MOTOR_NS, int(n['id'])) & 1 else -1) * n['activation']
        for n in sorted(nodes, key=lambda n: int(n['id']))))
    unknown = [n['channel'] for n in nodes if str(n['channel']) not in bindings]
    assert not unknown, ('unknown motor channels', unknown)
    aligned = math.tanh(.5 * math.fsum(
        (1 if channel_id(seed, MOTOR_NS, bindings[str(n['channel'])]) & 1 else -1) * n['activation']
        for n in sorted(nodes, key=lambda n: bindings[str(n['channel'])])))
    return {'id': raw, 'aligned': aligned}

class Trial:
    def __init__(self, key, profile, material, *, whole=None, parent=None, position=None, backend='native'):
        assert not (whole and parent)
        self.key, self.profile, self.material, self.backend = key, profile, material, backend
        self.events, self.inputs, self.rows, self.requested = [], [], [], []
        self.plan = None
        self.ancestry = {'kind': 'blank', 'birth_called': False}
        if whole:
            assert whole['kernel'] == kernel(profile)
            image = StateImage.from_dict(whole['core'])
            self.engine = resolve_kernel(kernel(profile)).create(state=image, backend=backend)
            assert self.engine.capture_state().digest == image.digest
            self.supplier = EnergySupplier(SUPPLY, self.engine, whole['supplier'])
            # Public supplier restore rebases an overdue inactive timer. Preserve the
            # exact experimental wrapper state while energy is disabled; no Core edit.
            if not self.engine.config.energy_simulation_enabled:
                assert whole['supplier']['pending'] is None
                self.supplier.next_us = int(whole['supplier']['next_us'])
            self.session = ReadoutSession(self.engine, record=self.events.append,
                state=copy.deepcopy(whole['session']), event_sink=self.sink)
            self.body = copy.deepcopy(whole['body'])
            self.ancestry = {'kind': 'complete-state-copy', 'birth_called': False, 'source': digest(whole)}
        else:
            if parent:
                before = digest(parent)
                original = StateImage.from_dict(parent['core'])
                image = birth(original, decay_age='preserve')
                self.engine = resolve_kernel(kernel(profile)).create(state=image, backend=backend)
                assert before == digest(parent)
                self.ancestry = {'kind': 'offspring', 'birth_called': True, 'source': before,
                                 **birth_metadata(original, decay_age='preserve')}
            else:
                self.engine = resolve_kernel(kernel(profile)).create(config(profile, material), backend=backend)
            self.supplier = EnergySupplier(SUPPLY, self.engine)
            self.session = ReadoutSession(self.engine, record=self.events.append, config=READOUT,
                state={'schema': 'threemind.cli-readouts/1', 'session_id': str(uuid5(NS, key))}, event_sink=self.sink)
            self.body = {'x': .125 if material['index'] == 0 else .625, 'v': 0., 'phase': 0.}
        if position is not None:
            self.ancestry['declared_body_positioning'] = {'before': copy.deepcopy(self.body), 'x': position, 'v': 0.}
            self.body.update(x=float(position), v=0., phase=0.)
        self.origin = self.snapshot()

    def sink(self, event, delivered):
        self.events.append(event)
        if event['kind'] == 'energy': self.supplier.delivered(event)
        if delivered: self.inputs.append(delivered)

    def snapshot(self):
        return {'schema': 'ring-mechanism63/whole/1', 'kernel': kernel(self.profile), 'profile': self.profile,
                'material': self.material['key'], 'core': self.engine.capture_state().to_dict(),
                'supplier': self.supplier.capture(), 'session': self.session.capture(),
                'body': copy.deepcopy(self.body), 'plan': copy.deepcopy(self.plan),
                'bindings': self.material['bindings']}

    def schedule(self, stimulus, source):
        self.requested.append({'source': source, 'stimulus': stimulus.to_dict()})
        self.session.schedule([{'stimulus': stimulus}], source=source, adapter_id='historical-ring-replay',
            envelope_id=uuid5(NS, self.session.host.run_id + ':' + source + ':' + str(stimulus.time_us)), at=0)

    def sense(self, now):
        seed = self.material['seed']
        region = int(self.body['x'] >= .5)
        channels = [(channel_id(seed, SENSE_NS, region*4+i), 1.) for i in range(4)]
        if self.body['v']:
            channels.append((channel_id(seed, SENSE_NS, 8+int(self.body['v'] < 0)), math.tanh(abs(self.body['v'])/.375)))
        return Stimulus(now, tuple(channels), .8)

    def move(self, control, seconds):
        decay = math.exp(-.8 * seconds)
        terminal = .3 * control / .8
        distance = terminal*seconds + (self.body['v']-terminal)*(1-decay)/.8
        self.body['x'] = (self.body['x']+distance) % 1.
        self.body['v'] = terminal + (self.body['v']-terminal)*decay
        return distance

    def run(self, *, seconds=60, mode='closed', motor='id', instrument='normal'):
        begin, wall = self.engine.time_us, time.monotonic()
        bg = [f['stimulus'] for f in self.material['frames'] if f['source'] == 'host-telemetry']
        self.plan = {'begin': begin, 'next_motor': begin, 'bg_cursor': 0, 'mode': mode,
                     'motor': motor, 'seconds': seconds, 'material_digest': digest(self.material)}
        distance = 0.
        def advance(target):
            self.supplier.prepare(self.engine)
            while self.plan['bg_cursor'] < len(bg):
                f = bg[self.plan['bg_cursor']]
                when = begin + int(f['time_us'])
                if when > target: break
                assert when >= self.engine.time_us
                self.schedule(Stimulus(when, tuple(tuple(v) for v in f['channels']), f['intensity']), 'host-telemetry')
                self.plan['bg_cursor'] += 1
            self.session.advance_to(target)
        for i in range(round(seconds*10)):
            if i % 10 == 0: guard()
            assert time.monotonic()-wall < 180, 'per-stage wall budget'
            now = begin + i*100000
            assert self.engine.time_us == now and self.engine.life != 'dead', 'time/life mismatch'
            if i % 10 == 0:
                if mode == 'replay':
                    f = self.material['senses'][i//10]
                    stimulus = Stimulus(now, tuple(tuple(v) for v in f['channels']), f['intensity'])
                else: stimulus = self.sense(now)
                self.schedule(stimulus, 'ring-study')
                advance(now)
            nodes = self.engine.observation_nodes()
            projected = controls(self.material['seed'], nodes, self.material['bindings'])
            applied = self.material['rows'][i]['applied_control'] if mode == 'replay' else 0. if mode == 'probe' else projected[motor]
            self.rows.append({'time_us': now, 'relative_us': i*100000, 'region': int(self.body['x'] >= .5),
                'body': copy.deepcopy(self.body), 'controls': projected, 'applied': applied, 'nodes': nodes})
            if i % 100 == 0 or instrument != 'normal':
                before = digest(self.snapshot())
                self.engine.observation_nodes(); self.engine.metrics(); self.snapshot()
                assert digest(self.snapshot()) == before, 'observation changed complete state'
            distance += abs(self.move(applied, .1))
            advance(now+100000)
            self.plan['next_motor'] = now+100000
            if i == 9 and instrument in ('restored', 'paused'):
                state = self.snapshot()
                if instrument == 'paused':
                    time.sleep(.02)
                    assert self.snapshot() == state
                else:
                    replacement = Trial(self.key, self.profile, self.material, whole=json.loads(encoded(state)), backend=self.backend)
                    self.engine, self.session, self.supplier, self.body = replacement.engine, replacement.session, replacement.supplier, replacement.body
                    self.session.event_sink = self.sink
                    self.session.host.record = self.events.append
                    assert self.snapshot() == state
        assert self.engine.life != 'dead'
        final = self.snapshot()
        assert final['core']['energy']['unserved_total'] < 1e-10
        return {'key': self.key, 'profile': self.profile, 'material': self.material['key'],
            'mode': mode, 'motor': motor, 'seconds': seconds, 'region1': sum(r['region'] for r in self.rows)/len(self.rows),
            'travel_distance': distance, 'stationary_fraction': sum(abs(r['body']['v']) < 1e-6 for r in self.rows)/len(self.rows),
            'samples': len(self.rows), 'life': self.engine.life, 'begin_us': begin, 'end_us': self.engine.time_us,
            'origin_hash': digest(self.origin), 'final_hash': digest(final),
            'input_hash': digest(self.requested), 'wall_seconds': time.monotonic()-wall}

def execute(folder, key, profile, material, *, whole=None, parent=None, position=None, backend='native', **kwargs):
    folder = Path(folder)
    if (folder/'result.json').exists(): return read(folder/'result.json'), read(folder/'final.json.gz')
    assert not folder.exists(), 'preserve interrupted original: '+str(folder)
    folder.mkdir(parents=True)
    obj = Trial(key, profile, material, whole=whole, parent=parent, position=position, backend=backend)
    save(folder/'initial.json.gz', obj.origin)
    save(folder/'ancestry.json', obj.ancestry)
    try:
        result = obj.run(**kwargs)
    except BaseException:
        save(folder/'interrupted.json.gz', obj.snapshot())
        save(folder/'interrupted-trace.json.gz', {'rows': obj.rows, 'events': obj.events, 'inputs': obj.inputs, 'requested': obj.requested})
        raise
    final = obj.snapshot()
    save(folder/'final.json.gz', final)
    save(folder/'trajectory.json.gz', {'rows': obj.rows, 'events': obj.events, 'inputs': obj.inputs, 'requested': obj.requested})
    save(folder/'result.json', result)
    return result, final

def compare(a, b, tol=1e-12):
    if isinstance(a, float) and isinstance(b, (float, int)): assert abs(a-b) <= tol, (a,b)
    elif isinstance(a, dict):
        assert a.keys() == b.keys(), (a.keys()-b.keys(), b.keys()-a.keys())
        for k in a: compare(a[k], b[k], tol)
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x,y in zip(a,b): compare(x,y,tol)
    else: assert a == b, (a,b)

def check_apparatus():
    folder = WORK/'apparatus-v3'
    save(folder/'declared.json', {'formal': False, 'protocol_hash': sha(HERE/'protocol-v2.zh.md'),
        'purpose': 'observation, save/restore, backend and historical-witness checks; no scientific selection'})
    mat = material(9293202, 0)
    results = {}
    for profile in PROFILES:
        endings = {}
        for mode in ('normal','frequent','restored','paused'):
            result, state = execute(folder/profile/mode, 'apparatus:'+profile, profile, mat,
                                    seconds=3, mode='replay', instrument=mode)
            endings[mode] = state
        assert len({digest(x) for x in endings.values()}) == 1
        rr, ref = execute(folder/profile/'reference', 'apparatus:'+profile, profile, mat,
                          seconds=3, mode='replay', backend='reference')
        compare(ref['core'], endings['normal']['core'])
        compare(ref['body'], endings['normal']['body'])
        parent_hash = digest(endings['normal'])
        child = Trial('apparatus-child:'+profile, profile, mat, parent=endings['normal'])
        assert child.engine.time_us == 0 and digest(endings['normal']) == parent_hash
        results[profile] = {'modes_identical': True, 'reference_native': True,
                            'birth': child.ancestry, 'full_config': endings['normal']['core']['config']}
        print(json.dumps({'apparatus': profile, 'passed': True}), flush=True)
    save(WORK/'apparatus.json', {'passed': True, 'profiles': results})

if __name__ == '__main__': check_apparatus()
