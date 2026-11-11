"""Raw temporal Core output -> independently variable physical actuator forces.

Inference accepts no query, target, task/effector label or scene inventory.
The shared network may learn its own representation. Separate encoders are a
comparison, not a Core partition. External teacher supervision is explicit.
"""
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from safetensors.torch import save_file, load_file
from lab.tools.activity_controller import ActivityLayout, FIELDS

VERSION = 'threemind.continuous-motor/1'
NORMALIZED_VERSION = 'threemind.continuous-motor/2'
TRAINING_VERSION = 'threemind.continuous-motor-fit/2'
WINDOW = 16


class _Process(nn.Module):
    def __init__(self, features, width, outputs, readout_version=1):
        super().__init__()
        self.input = nn.Linear(features, width)
        self.position = nn.Parameter(torch.zeros(1, WINDOW, width))
        layer = nn.TransformerEncoderLayer(width, 4, width*2, dropout=0, batch_first=True, norm_first=True)
        self.temporal = nn.TransformerEncoder(layer, 1, enable_nested_tensor=False)
        self.output = nn.Linear(width, outputs)
        self.final_norm = nn.LayerNorm(width) if readout_version == 2 else nn.Identity()
        if readout_version == 2:
            nn.init.zeros_(self.output.weight); nn.init.zeros_(self.output.bias)

    def forward(self, x):
        return torch.tanh(self.output(self.final_norm(self.temporal(self.input(x)+self.position[:, :x.shape[1]])[:, -1])))


class ContinuousMotor(nn.Module):
    def __init__(self, channels, *, organization='shared', seed=223, readout_version=1):
        super().__init__()
        if organization not in ('shared', 'separate'):
            raise ValueError('shared or separate motor representation')
        if readout_version not in (1, 2): raise ValueError('motor readout version')
        self.readout_version = readout_version
        torch.manual_seed(seed)
        self.layout = ActivityLayout(channels); self.organization = organization; self.seed = seed
        self.models = nn.ModuleList([_Process(self.layout.width, 48, 4, readout_version)] if organization == 'shared'
                                   else [_Process(self.layout.width, 24, 2, readout_version), _Process(self.layout.width, 24, 2, readout_version)])

    def forward(self, x):
        if x.ndim != 3 or x.shape[-1] != self.layout.width or not 1 <= x.shape[1] <= WINDOW:
            raise ValueError('bounded ordered raw activity window')
        return torch.cat([model(x) for model in self.models], dim=-1)

    def predict(self, values):
        x = np.asarray(values, dtype=np.float32)
        if not np.isfinite(x).all():
            raise ValueError('finite raw process')
        self.eval()
        with torch.no_grad():
            return self(torch.as_tensor(x, device=next(self.parameters()).device)).cpu().numpy()

    def action(self, values):
        x = np.asarray(values, dtype=np.float32)
        if not np.any(x):
            return np.zeros(4, dtype=np.float32)
        return self.predict(x[None])[0]

    def fit(self, x, y, *, validation, steps=1600, check=lambda: None):
        x = np.asarray(x, dtype=np.float32); y = np.asarray(y, dtype=np.float32)
        vx, vy = (np.asarray(v, dtype=np.float32) for v in validation)
        if x.ndim != 3 or not len(x) or not len(vx) or y.shape != (len(x), 4) or vy.shape != (len(vx), 4) or vx.shape[1:] != x.shape[1:]:
            raise ValueError('aligned demonstration windows and four force targets')
        if not all(np.isfinite(v).all() for v in (x, y, vx, vy)) or np.max(np.abs(y)) > 1 or not 1 <= steps <= 4000:
            raise ValueError('finite bounded training data')
        device = next(self.parameters()).device
        opt = torch.optim.AdamW(self.parameters(), lr=.001, weight_decay=.0001)
        rng = np.random.default_rng(self.seed)
        # Balance physical movement and holding examples; no task labels are read.
        bins = [np.flatnonzero(np.max(np.abs(y), axis=1) > .15), np.flatnonzero(np.max(np.abs(y), axis=1) <= .15)]
        bins = [b for b in bins if len(b)]
        best = None; best_loss = float('inf'); best_step = 0; curve = []
        self.train()
        for i in range(steps):
            if i % 50 == 0: check()
            idx = np.concatenate([rng.choice(b, 32//len(bins)) for b in bins])
            if not len(idx): raise RuntimeError('empty training batch')
            tx = torch.as_tensor(x[idx], device=device); ty = torch.as_tensor(y[idx], device=device)
            opt.zero_grad(); loss = torch.mean((self(tx)-ty)**2)
            if not torch.isfinite(loss): raise RuntimeError('non-finite motor training loss')
            loss.backward()
            nn.utils.clip_grad_norm_(self.parameters(), 1.); opt.step()
            if i % 100 == 0 or i == steps-1:
                with torch.no_grad():
                    value = sum(float(torch.sum((self(torch.as_tensor(vx[j:j+32], device=device))-
                        torch.as_tensor(vy[j:j+32], device=device))**2)) for j in range(0, len(vx), 32))/(len(vx)*4)
                if value < best_loss:
                    best_loss, best_step = value, i+1
                    best = {k: v.detach().cpu().clone() for k, v in self.state_dict().items()}
                curve.append({'step': i+1, 'validation_mse': value})
        self.load_state_dict(best); self.eval()
        return {'training_version': TRAINING_VERSION, 'validation_mse': best_loss, 'selected_step': best_step, 'steps': steps,
                'training_samples': len(x), 'validation_samples': len(vx), 'device': str(device),
                'parameters': sum(p.numel() for p in self.parameters()),
                'readout_version': self.readout_version, 'curve': curve,
                'selection': 'separate teacher demonstrations; no final-test labels'}

    def save(self, folder, *, input_source='activity'):
        folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
        save_file({k: v.detach().cpu().contiguous() for k, v in self.state_dict().items()}, str(folder/'model.safetensors'))
        (folder/'manifest.json').write_text(json.dumps({'schema': NORMALIZED_VERSION if self.readout_version == 2 else VERSION, 'channels': self.layout.channels,
            'organization': self.organization, 'seed': self.seed, 'fields': FIELDS, 'window': WINDOW,
            'input_source': input_source, 'outputs': ['eye_x_force', 'eye_y_force', 'hand_x_force', 'hand_y_force'],
            'processing': 'raw ordered process; no answer, task label, subtraction or example normalization'}), encoding='utf-8')

    @classmethod
    def restore(cls, folder, device='cpu'):
        folder = Path(folder); m = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if m['schema'] not in (VERSION, NORMALIZED_VERSION) or m['fields'] != list(FIELDS) or m['window'] != WINDOW:
            raise ValueError('continuous motor protocol')
        value = cls(m['channels'], organization=m['organization'], seed=m['seed'],
                    readout_version=2 if m['schema'] == NORMALIZED_VERSION else 1)
        value.load_state_dict(load_file(str(folder/'model.safetensors')), strict=True)
        return value.to(device).eval()


def recent_window(layout, rows, *, incoming=False, count=WINDOW):
    """Only recent samples, oldest-to-newest; prefix repeats first available frame."""
    from lab.tools.choice_attribution import incoming_frame
    if not rows: raise ValueError('sample before acting')
    rows = list(rows)[-count:]
    values = [incoming_frame(layout, r['stimulus']) if incoming else layout.frame(r['activity']) for r in rows]
    return np.stack([values[0]]*(count-len(values))+values)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--observations', type=Path, required=True, help='JSON array of recorded session rows')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    args = parser.parse_args()
    head = ContinuousMotor.restore(args.model, args.device)
    manifest = json.loads((args.model/'manifest.json').read_text(encoding='utf-8'))
    rows = json.loads(args.observations.read_text(encoding='utf-8'))
    values = recent_window(head.layout, rows, incoming=manifest['input_source'] == 'incoming')
    print(json.dumps({'schema': manifest['schema'], 'action': head.action(values).tolist(),
                      'source': manifest['input_source'], 'executed': False}))


if __name__ == '__main__': main()
