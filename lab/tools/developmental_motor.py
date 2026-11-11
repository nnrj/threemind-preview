"""Persistent, individual motor peripheral. Raw Core activity is the only input.

Physical retinal cells share a reader; no object crops or answer-dependent masks.
Outputs are desired eye/hand positions, executed by a calibrated physical servo.
Teacher targets exist only in the explicitly supervised update/replay buffer.
"""
import copy
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from safetensors.torch import load_file, save_file
from lab.tools.activity_controller import ActivityLayout, FIELDS
from lab.tools.continuous_motor import WINDOW

VERSION = 'threemind.developmental-motor/1'
REHEARSAL_VERSION = 'threemind.developmental-motor/2'


class DevelopmentalMotor(nn.Module):
    def __init__(self, channels, retinal_channels, *, identity, seed=223, capacity=256):
        super().__init__()
        self.layout = ActivityLayout(channels)
        self.retinal_channels = tuple(map(int, retinal_channels))
        if not self.retinal_channels or len(self.retinal_channels) % 4:
            raise ValueError('physical retinal cells, four measured components each')
        if len(set(self.retinal_channels)) != len(self.retinal_channels) or not set(self.retinal_channels) <= set(self.layout.channels):
            raise ValueError('unique retinal ports within the recorded layout')
        if not identity or not 16 <= capacity <= 2048:
            raise ValueError('individual identity and bounded teaching memory')
        self.identity, self.seed, self.capacity = str(identity), int(seed), int(capacity)
        visual = [4*self.layout.index[c]+f for c in self.retinal_channels for f in range(4)]
        other = [4*self.layout.index[c]+f for c in self.layout.channels if c not in set(self.retinal_channels) for f in range(4)]
        self.register_buffer('visual_index', torch.tensor(visual, dtype=torch.long))
        self.register_buffer('other_index', torch.tensor(other, dtype=torch.long))
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.cell = nn.Sequential(nn.Linear(16, 8), nn.Tanh())
            self.input = nn.Linear(len(self.retinal_channels)//4*8+len(other), 48)
            self.position = nn.Parameter(torch.zeros(1, WINDOW, 48))
            layer = nn.TransformerEncoderLayer(48, 4, 96, dropout=0, batch_first=True, norm_first=True)
            self.temporal = nn.TransformerEncoder(layer, 1, enable_nested_tensor=False)
            self.output = nn.Sequential(nn.LayerNorm(48), nn.Linear(48, 4), nn.Tanh())
        self.optimizer = torch.optim.AdamW(self.parameters(), lr=.001, weight_decay=.0001)
        self.rng = np.random.default_rng(seed+1)
        self.noise_rng = np.random.default_rng(seed+2)
        self.noise = np.zeros(6)
        self.steps = self.examples_seen = 0
        self.replay_x, self.replay_y = [], []
        self.rehearsal = None

    def configure_rehearsal(self, mode):
        """Explicit experimental training-policy fork; no weights/state reset."""
        from lab.tools.rehearsal_memory import RehearsalMemory
        if self.rehearsal is not None: raise ValueError('policy already declared')
        correct = []
        for x, y in zip(self.replay_x, self.replay_y):
            prediction = self.intent(x)
            correct.append(prediction is not None and np.linalg.norm((prediction-y)[:2]*.35) <= .075
                           and np.linalg.norm((prediction-y)[2:]) <= .20)
        self.rehearsal = RehearsalMemory(mode, self.capacity, self.seed+51)
        self.replay_x, self.replay_y = self.rehearsal.initialize(self.replay_x, self.replay_y, correct=correct)
        return {'mode': mode, 'initial_examples': len(correct), 'initial_correct': int(sum(correct)),
                'anchors': self.rehearsal.anchors, 'source': 'retained teacher cache only'}

    def forward(self, x):
        if x.ndim != 3 or x.shape[-1] != self.layout.width or not 1 <= x.shape[1] <= WINDOW:
            raise ValueError('ordered raw activity window')
        b, t = x.shape[:2]
        retinal = x[..., self.visual_index].reshape(b, t, -1, 16)
        shared = self.cell(retinal).flatten(2)
        h = self.input(torch.cat((shared, x[..., self.other_index]), -1))
        return self.output(self.temporal(h+self.position[:, :t])[:, -1])

    def intent(self, window):
        x = np.asarray(window, dtype=np.float32)
        if x.shape != (WINDOW, self.layout.width) or not np.isfinite(x).all():
            raise ValueError('finite complete raw output window')
        if not np.any(x):
            return None  # No Core signal: no new motor command, not a center target.
        self.eval()
        with torch.no_grad():
            return self(torch.as_tensor(x[None], device=next(self.parameters()).device))[0].cpu().numpy()

    def variation(self, dt, scale=0.):
        if not 0 < dt <= .1 or not 0 <= scale <= .5:
            raise ValueError('bounded explicitly declared motor variation')
        r = np.exp(-dt/.35)
        self.noise = r*self.noise+scale*np.sqrt(1-r*r)*self.noise_rng.normal(size=6)
        return self.noise.copy()

    def teach(self, window, target, *, updates=2):
        x, y = np.asarray(window, dtype=np.float32), np.asarray(target, dtype=np.float32)
        if x.shape != (WINDOW, self.layout.width) or y.shape != (4,) or not np.isfinite(x).all() or not np.isfinite(y).all() or np.max(np.abs(y)) > 1:
            raise ValueError('aligned past raw window and bounded teacher pose')
        if not 0 <= updates <= 32:
            raise ValueError('bounded incremental learning')
        self.examples_seen += 1
        if self.rehearsal is None:
            self.replay_x.append(x.copy()); self.replay_y.append(y.copy())
            if len(self.replay_x) > self.capacity:
                self.replay_x.pop(0); self.replay_y.pop(0)
        else:
            self.rehearsal.append(self.replay_x, self.replay_y, x, y)
        return self.learn(updates)

    def learn(self, updates):
        if not 0 <= updates <= 32 or not self.replay_x:
            raise ValueError('bounded updates require existing teacher evidence')
        loss_value = None
        self.train(); device = next(self.parameters()).device
        for _ in range(updates):
            batch = min(16, len(self.replay_x))
            idx = (self.rng.integers(len(self.replay_x), size=batch) if self.rehearsal is None
                   else self.rehearsal.indices(len(self.replay_x), batch, self.rng))
            x = torch.as_tensor(np.stack([self.replay_x[i] for i in idx]), device=device)
            y = torch.as_tensor(np.stack([self.replay_y[i] for i in idx]), device=device)
            self.optimizer.zero_grad(set_to_none=True)
            loss = torch.mean((self(x)-y)**2)
            if not torch.isfinite(loss): raise RuntimeError('nonfinite teacher update')
            loss.backward(); nn.utils.clip_grad_norm_(self.parameters(), 1.)
            self.optimizer.step(); self.steps += 1; loss_value = float(loss.detach())
        self.eval()
        return loss_value

    def save(self, folder):
        folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
        save_file({k: v.detach().cpu().contiguous() for k, v in self.state_dict().items()}, str(folder/'weights.safetensors'))
        state = self.optimizer.state_dict(); tensors = {}; scalars = {}
        for index, entry in state['state'].items():
            scalars[str(index)] = {}
            for key, value in entry.items():
                if torch.is_tensor(value): tensors[f'{index}/{key}'] = value.detach().cpu().contiguous()
                else: scalars[str(index)][key] = value
        save_file(tensors, str(folder/'optimizer.safetensors'))
        np.savez_compressed(folder/'teaching.npz', x=np.asarray(self.replay_x, dtype=np.float32), y=np.asarray(self.replay_y, dtype=np.float32))
        m = {'schema': VERSION, 'identity': self.identity, 'channels': self.layout.channels,
             'retinal_channels': self.retinal_channels, 'seed': self.seed, 'capacity': self.capacity,
             'fields': FIELDS, 'window': WINDOW, 'steps': self.steps, 'examples_seen': self.examples_seen,
             'rng': copy.deepcopy(self.rng.bit_generator.state), 'noise_rng': copy.deepcopy(self.noise_rng.bit_generator.state),
             'noise': self.noise.tolist(), 'optimizer_groups': state['param_groups'], 'optimizer_scalars': scalars,
             'inference_input': 'raw Core output only', 'outputs': ['eye_yaw_fraction', 'eye_pitch_fraction', 'hand_x_m', 'hand_y_m'],
             'selection': 'latest joint state; no best-weight rollback'}
        if self.rehearsal is not None:
            m.update(schema=REHEARSAL_VERSION, rehearsal=self.rehearsal.state())
        (folder/'manifest.json').write_text(json.dumps(m, ensure_ascii=False, allow_nan=False), encoding='utf-8')

    @classmethod
    def restore(cls, folder, *, device='cpu', expected_identity=None):
        folder = Path(folder); m = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if m['schema'] not in (VERSION, REHEARSAL_VERSION) or m['fields'] != list(FIELDS) or m['window'] != WINDOW:
            raise ValueError('developmental peripheral version')
        if expected_identity is not None and m['identity'] != expected_identity:
            raise ValueError('wrong individual peripheral')
        obj = cls(m['channels'], m['retinal_channels'], identity=m['identity'], seed=m['seed'], capacity=m['capacity']).to(device)
        obj.load_state_dict(load_file(str(folder/'weights.safetensors')), strict=True)
        states = {int(i): dict(v) for i, v in m['optimizer_scalars'].items()}
        for key, value in load_file(str(folder/'optimizer.safetensors')).items():
            index, name = key.split('/', 1); states.setdefault(int(index), {})[name] = value
        obj.optimizer.load_state_dict({'state': states, 'param_groups': m['optimizer_groups']})
        with np.load(folder/'teaching.npz', allow_pickle=False) as data:
            obj.replay_x = list(data['x']); obj.replay_y = list(data['y'])
        obj.steps, obj.examples_seen = m['steps'], m['examples_seen']
        obj.rng.bit_generator.state = m['rng']; obj.noise_rng.bit_generator.state = m['noise_rng']
        obj.noise = np.asarray(m['noise']); obj.eval()
        if m['schema'] == REHEARSAL_VERSION:
            from lab.tools.rehearsal_memory import RehearsalMemory
            obj.rehearsal = RehearsalMemory.restore(m['rehearsal'])
            if obj.rehearsal.capacity != obj.capacity: raise ValueError('rehearsal capacity mismatch')
        return obj
