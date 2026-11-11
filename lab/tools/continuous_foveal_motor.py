"""Persistent foveal eye/hand reader for a continuously developing individual.

Only raw Core activity enters inference. Fixed receptor geometry belongs to the
instrument, not the scene. Eye and hand select independently; a learned hand
MOVE/WAIT output never consults the teacher, stage, or scoring target. Execution
of WAIT and selected rays belongs to the separately declared physical actuator.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from safetensors.torch import load_file, save_file
from torch import nn

from lab.tools.activity_controller import FIELDS
from lab.tools.foveal_choice import FovealChoice

VERSION = 'threemind.continuous-foveal-motor/1'
FRAMES = 8


class ContinuousFovealMotor(FovealChoice):
    def __init__(self, channels, visual_channels, centers, widths, *, identity, seed=223):
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError('individual identity required')
        # Birth/restoration must not change another peripheral's global RNG.
        with torch.random.fork_rng(devices=list(range(torch.cuda.device_count()))):
            super().__init__(channels, visual_channels, centers, widths, seed=seed)
            self.head = nn.Linear(48, 2)  # Independent eye and hand location scores.
            self.position = nn.Parameter(torch.zeros(1, FRAMES, 48))
            # The gate sees actual Core values, without receptor geometry.
            # Each receptor contributes its 4 sensory ports x 4 Core fields.
            self.move_input = nn.Linear(16 + len(self.common_indices), 48)
            self.move_head = nn.Linear(48, 2)
        self.identity = identity
        self.optimizer = torch.optim.AdamW(self.parameters(), lr=.002, weight_decay=.0001)
        self.learning_rng = None
        self.computed_updates = self.committed_updates = 0
        self.eval()

    def forward(self, x):
        if x.ndim != 3 or x.shape[1:] != (FRAMES, self.layout.width):
            raise ValueError('eight raw Core frames in the fixed full-port layout required')
        batch, steps, _ = x.shape
        receptors = len(self.centers)
        retina = x[:, :, self.visual_indices].reshape(batch, steps, receptors, 16)
        local = retina[:, :, self.neighbors].reshape(batch, steps, receptors, 144)
        common = x[:, :, self.common_indices]
        expanded = common.unsqueeze(2).expand(-1, -1, receptors, -1)
        geometry = self.geometry[None, None].expand(batch, steps, -1, -1)
        features = torch.cat((local, expanded, geometry), -1)
        features = features.permute(0, 2, 1, 3).reshape(batch * receptors, steps, -1)
        hidden = self.temporal(self.input(features) + self.position)[:, -1]
        scores = self.head(hidden).reshape(batch, receptors, 2)
        gate = torch.cat((retina.mean(dim=2), common), -1)
        gate_hidden = self.temporal(self.move_input(gate) + self.position)[:, -1]
        return {'eye_logits': scores[:, :, 0], 'hand_logits': scores[:, :, 1],
                'move_logits': self.move_head(gate_hidden)}

    def _values(self, values):
        result = np.asarray(values, dtype=np.float32)
        if result.ndim != 3 or result.shape[1:] != (FRAMES, self.layout.width) or not len(result):
            raise ValueError('nonempty batch of eight raw Core frames required')
        if not np.isfinite(result).all():
            raise ValueError('finite raw Core activity required')
        return result

    def predict(self, values):
        values = self._values(values)
        self.eval()
        with torch.no_grad():
            output = self(torch.as_tensor(values, device=next(self.parameters()).device))
        return {name: value.detach().cpu().numpy() for name, value in output.items()}

    def intent(self, values):
        values = np.asarray(values, dtype=np.float32)
        if values.shape != (FRAMES, self.layout.width) or not np.isfinite(values).all():
            raise ValueError('finite eight-frame raw Core window required')
        if not np.any(values):
            return None
        output = self.predict(values[None])
        move = bool(output['move_logits'][0].argmax())
        return {'eye_receptor': int(output['eye_logits'][0].argmax()),
                'hand_receptor': int(output['hand_logits'][0].argmax()) if move else None,
                'move': move}

    def select(self, values):
        raise TypeError('independent eye/hand intent required; a single shared selection is not supported')

    def fit(self, *args, **kwargs):
        raise TypeError('use continue_calibration; optimizer reset and best-state rollback are forbidden')

    @staticmethod
    def _targets(values, count, name):
        result = np.asarray(values)
        if (result.shape != (count,) or result.dtype.kind not in 'biu'
                or not np.isfinite(result).all()):
            raise ValueError(f'integer {name} targets aligned with the raw windows required')
        if result.dtype.kind == 'u' and np.any(result > np.iinfo(np.int64).max):
            raise ValueError(f'{name} target exceeds the integer output range')
        return result.astype(np.int64)

    @staticmethod
    def _loss(output, eye, hand, move):
        loss = nn.functional.cross_entropy(output['eye_logits'], eye)
        loss = loss + nn.functional.cross_entropy(output['move_logits'], move)
        active = move == 1
        if active.any():
            loss = loss + nn.functional.cross_entropy(output['hand_logits'][active], hand[active])
        return loss

    def continue_calibration(self, x, eye_y, hand_y, move_y, *, steps=1200, check=lambda: None, batch_size=32):
        x = self._values(x)
        if (not 1 <= len(x) <= 32768 or type(steps) is not int or not 1 <= steps <= 4000
                or type(batch_size) is not int or not 1 <= batch_size <= 32):
            raise ValueError('bounded calibration size, steps and batch required')
        eye = self._targets(eye_y, len(x), 'eye')
        hand = self._targets(hand_y, len(x), 'hand')
        move = self._targets(move_y, len(x), 'MOVE/WAIT')
        count = len(self.centers)
        if np.any((eye < 0) | (eye >= count)) or np.any((move < 0) | (move > 1)):
            raise ValueError('eye index or MOVE/WAIT target outside declared output range')
        # WAIT has no supervised pointing answer. -1 is an explicit absent label.
        if np.any((hand < -1) | (hand >= count)) or np.any((move == 1) & (hand < 0)):
            raise ValueError('MOVE requires a valid hand index; WAIT allows -1')
        device = next(self.parameters()).device
        # The retained classroom corpus can exceed device memory. Keep its
        # original values on CPU; transfer only the same selected minibatch.
        tx = torch.as_tensor(x)
        te, th, tm = [torch.as_tensor(v, dtype=torch.long) for v in (eye, hand, move)]
        # Always CPU sampling: a device change does not replace the RNG algorithm.
        rng = torch.Generator(device='cpu').manual_seed(self.seed)
        if self.learning_rng is not None:
            rng.set_state(self.learning_rng.cpu())
        self.train()
        try:
            for _ in range(steps):
                check()  # Only before complete updates, never halfway through one.
                indices = torch.randint(len(x), (min(batch_size, len(x)),), generator=rng)
                self.optimizer.zero_grad(set_to_none=True)
                bx, be, bh, bm = [value[indices].to(device) for value in (tx, te, th, tm)]
                loss = self._loss(self(bx), be, bh, bm)
                if not torch.isfinite(loss):
                    raise RuntimeError('nonfinite foveal calibration loss')
                loss.backward()
                norm = nn.utils.clip_grad_norm_(self.parameters(), 1.)
                if not torch.isfinite(norm):
                    raise RuntimeError('nonfinite foveal calibration gradient')
                self.optimizer.step()
                self.computed_updates += 1
                self.committed_updates += 1
                self.learning_rng = rng.get_state().clone()
        finally:
            self.eval()
        total = 0.
        with torch.no_grad():
            for start in range(0, len(x), batch_size):
                end = min(len(x), start + batch_size)
                bx, be, bh, bm = [value[start:end].to(device) for value in (tx, te, th, tm)]
                total += float(self._loss(self(bx), be, bh, bm)) * (end-start)
        return {'loss': total / len(x), 'n': len(x), 'updates': steps,
                'computed_updates': self.computed_updates, 'committed_updates': self.committed_updates,
                'selection': 'last state; no weight, optimizer, RNG or loss-minimum rollback',
                'hand_supervised': int(np.sum(move)), 'frames': FRAMES}

    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=False)
        save_file({key: value.detach().cpu().contiguous() for key, value in self.state_dict().items()},
                  str(folder / 'model.safetensors'))
        torch.save({'optimizer': self.optimizer.state_dict(), 'rng': self.learning_rng}, folder / 'learning.pt')
        manifest = {'schema': VERSION, 'identity': self.identity, 'seed': self.seed,
                    'channels': list(self.layout.channels), 'visual_channels': self.visual_channels,
                    'centers': self.centers, 'widths': self.widths, 'fields': list(FIELDS), 'frames': FRAMES,
                    'computed_updates': self.computed_updates, 'committed_updates': self.committed_updates,
                    'move_labels': ['wait', 'move'], 'inference': 'raw Core activity only; fixed optical geometry',
                    'selection': 'last state', 'sampling_rng': 'torch-cpu-generator'}
        (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, allow_nan=False), encoding='utf-8')

    @classmethod
    def restore(cls, folder, device='cpu', *, expected_identity=None):
        folder = Path(folder)
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        if (manifest['schema'] != VERSION or manifest['frames'] != FRAMES or manifest['fields'] != list(FIELDS)
                or manifest['move_labels'] != ['wait', 'move'] or manifest['selection'] != 'last state'
                or manifest['sampling_rng'] != 'torch-cpu-generator'):
            raise ValueError('continuous foveal peripheral contract mismatch')
        if expected_identity is not None and expected_identity != manifest['identity']:
            raise ValueError('wrong individual peripheral')
        computed, committed = manifest['computed_updates'], manifest['committed_updates']
        if type(computed) is not int or type(committed) is not int or computed < 0 or committed != computed:
            raise ValueError('continuous peripheral update history mismatch')
        result = cls(manifest['channels'], manifest['visual_channels'], manifest['centers'], manifest['widths'],
                     identity=manifest['identity'], seed=manifest['seed']).to(device)
        result.load_state_dict(load_file(str(folder / 'model.safetensors')), strict=True)
        # AdamW's non-capturable step counters stay on CPU even for CUDA
        # weights. Let the optimizer place moments; do not move every tensor.
        learning = torch.load(folder / 'learning.pt', map_location='cpu', weights_only=True)
        result.optimizer.load_state_dict(learning['optimizer'])
        result.learning_rng = learning['rng'].cpu() if learning['rng'] is not None else None
        if (computed == 0) != (result.learning_rng is None):
            raise ValueError('continuous peripheral RNG history mismatch')
        result.computed_updates, result.committed_updates = computed, committed
        return result.eval()
