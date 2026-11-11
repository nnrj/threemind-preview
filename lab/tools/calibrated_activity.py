"""Persistent calibration of the established E56 raw-activity Transformer.

Labels supervise this external instrument only. Its architecture is unchanged
from ActivityController; inference accepts no teacher, scene or target metadata.
"""
import copy
import json
from pathlib import Path

import numpy as np
import torch
from safetensors.torch import load_file, save_file
from lab.tools.activity_controller import ActivityController, ActivityLayout, FIELDS

VERSION = 'threemind.calibrated-activity/1'


class CalibratedActivity(ActivityController):
    def __init__(self, channels, words, identity, *, seed=223):
        self.layout = ActivityLayout(channels)
        super().__init__(self.layout.width, len(words), seed=seed)
        self.words, self.identity = tuple(words), identity
        self.optimizer = torch.optim.AdamW(self.parameters(), lr=.002, weight_decay=.0001)
        self.learning_rng = None
        self.computed_updates = self.committed_updates = 0

    def calibrate(self, x, y, *, steps=1200, check=lambda: None):
        device = next(self.parameters()).device
        x = torch.as_tensor(np.asarray(x), dtype=torch.float32, device=device)
        y = torch.as_tensor(np.asarray(y), dtype=torch.long, device=device)
        if x.ndim != 3 or x.shape[1:] != (8, self.features) or y.shape != (len(x),):
            raise ValueError('eight raw frames spanning each complete question required')
        if not torch.isfinite(x).all() or not 1 <= len(x) <= 1024 or not 1 <= steps <= 4000:
            raise ValueError('finite bounded calibration')
        if torch.any((y < 0) | (y >= len(self.words))):
            raise ValueError('teacher label outside fixed vocabulary')
        rng = torch.Generator(device=device).manual_seed(self.seed)
        if self.learning_rng is not None:
            rng.set_state(self.learning_rng.cpu())
        self.train()
        best, best_loss = None, float('inf')
        start_committed = self.committed_updates
        for i in range(steps):
            if i % 50 == 0: check()
            ids = torch.randint(len(x), (min(32, len(x)),), generator=rng, device=device)
            self.optimizer.zero_grad(set_to_none=True)
            loss = torch.nn.functional.cross_entropy(self(x[ids]), y[ids])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.parameters(), 1.)
            self.optimizer.step()
            self.computed_updates += 1
            if i % 50 == 0 or i == steps-1:
                with torch.no_grad(): value = float(torch.nn.functional.cross_entropy(self(x), y))
                if value < best_loss:
                    best_loss = value
                    best = (copy.deepcopy(self.state_dict()), copy.deepcopy(self.optimizer.state_dict()),
                            rng.get_state().clone(), start_committed+i+1)
        # The old calibration selects by TRAINING loss. Keep the matching Adam
        # and RNG as well, so a later calibration really continues this state.
        self.load_state_dict(best[0]); self.optimizer.load_state_dict(best[1])
        self.learning_rng, self.committed_updates = best[2], best[3]
        self.eval()
        with torch.no_grad(): correct = int((self(x).argmax(-1) == y).sum())
        return dict(loss=best_loss, training_correct=correct, n=len(y), updates=steps,
                    computed_updates=self.computed_updates, committed_updates=self.committed_updates,
                    selection='lowest training loss, including its optimizer and RNG; no test selection')

    def save(self, folder, *args, **kwargs):
        p = Path(folder); p.mkdir(parents=True, exist_ok=False)
        save_file({k: v.detach().cpu().contiguous() for k, v in self.state_dict().items()}, str(p/'model.safetensors'))
        torch.save(dict(optimizer=self.optimizer.state_dict(), rng=self.learning_rng), p/'learning.pt')
        (p/'manifest.json').write_text(json.dumps(dict(schema=VERSION, channels=self.layout.channels,
            words=self.words, identity=self.identity, seed=self.seed, fields=FIELDS,
            computed_updates=self.computed_updates, committed_updates=self.committed_updates,
            sampling='8 raw frames across whole question; no subtraction or rescaling')), encoding='utf-8')

    def continue_calibration(self, x, y, *, steps=1200, check=lambda: None):
        """Continue to the LAST state; never restore an earlier loss minimum.

        The historical ``calibrate`` method remains unchanged for frozen studies.
        Learning RNG and optimizer are committed after every actual update, so
        a boundary pause preserves the next update as well as current weights.
        Labels supervise this peripheral only; no simulation is run here.
        """
        device = next(self.parameters()).device
        x = torch.as_tensor(np.asarray(x), dtype=torch.float32, device=device)
        y = torch.as_tensor(np.asarray(y), dtype=torch.long, device=device)
        if x.ndim != 3 or x.shape[1:] != (8, self.features) or y.shape != (len(x),):
            raise ValueError('eight raw frames spanning each complete question required')
        if not torch.isfinite(x).all() or not 1 <= len(x) <= 1024 or not 1 <= steps <= 4000:
            raise ValueError('finite bounded calibration')
        if torch.any((y < 0) | (y >= len(self.words))):
            raise ValueError('teacher label outside fixed vocabulary')
        rng = torch.Generator(device=device).manual_seed(self.seed)
        if self.learning_rng is not None:
            rng.set_state(self.learning_rng.cpu())
        self.train()
        for _ in range(steps):
            check()  # before an atomic optimizer update, never half way through
            ids = torch.randint(len(x), (min(32, len(x)),), generator=rng, device=device)
            self.optimizer.zero_grad(set_to_none=True)
            loss = torch.nn.functional.cross_entropy(self(x[ids]), y[ids])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.parameters(), 1.)
            self.optimizer.step()
            self.computed_updates += 1
            self.committed_updates += 1
            self.learning_rng = rng.get_state().clone()
        self.eval()
        with torch.no_grad():
            logits = self(x)
            value = float(torch.nn.functional.cross_entropy(logits, y))
            correct = int((logits.argmax(-1) == y).sum())
        return dict(loss=value, training_correct=correct, n=len(y), updates=steps,
                    computed_updates=self.computed_updates, committed_updates=self.committed_updates,
                    selection='last state; no weight, optimizer, RNG or loss-minimum rollback')

    @classmethod
    def restore(cls, folder, device='cpu'):
        p = Path(folder); m = json.loads((p/'manifest.json').read_text(encoding='utf-8'))
        if m['schema'] != VERSION or m['fields'] != list(FIELDS): raise ValueError('calibration version')
        value = cls(m['channels'], m['words'], m['identity'], seed=m['seed']).to(device)
        value.load_state_dict(load_file(str(p/'model.safetensors')))
        learning = torch.load(p/'learning.pt', map_location=device, weights_only=True)
        value.optimizer.load_state_dict(learning['optimizer']); value.learning_rng = learning['rng']
        value.computed_updates, value.committed_updates = m['computed_updates'], m['committed_updates']
        return value.eval()
