"""Training-only numerical calibration and frozen native-language replay."""
from dataclasses import asdict, dataclass
import numpy as np


@dataclass(frozen=True)
class FeatureCalibration:
    mean: list
    scale: list
    floor: float = 1e-6
    clip: float = 20.0
    schema: str = 'threemind.native-feature-calibration/1'

    def __post_init__(self):
        mean, scale = np.asarray(self.mean), np.asarray(self.scale)
        if (self.schema != 'threemind.native-feature-calibration/1' or mean.ndim != 2 or mean.shape != scale.shape
            or not np.isfinite(mean).all() or not np.isfinite(scale).all() or (scale <= 0).any()
            or not np.isfinite(self.floor) or self.floor <= 0 or not np.isfinite(self.clip) or self.clip <= 0):
            raise ValueError('invalid feature calibration')

    @classmethod
    def fit(cls, samples, floor=1e-6):
        if not samples or any(row.get('split') != 'train' for row in samples):
            raise ValueError('feature calibration requires the training partition')
        values = np.asarray([row['values'] for row in samples], dtype=float)
        if values.ndim != 3 or not np.isfinite(values).all() or floor <= 0:
            raise ValueError('invalid calibration features')
        return cls(values.mean(axis=0).tolist(), np.maximum(values.std(axis=0), floor).tolist(), floor)

    def transform(self, values):
        value, mean, scale = np.asarray(values, dtype=float), np.asarray(self.mean), np.asarray(self.scale)
        if value.shape[-2:] != mean.shape or not np.isfinite(value).all():
            raise ValueError('feature calibration shape/value mismatch')
        return np.clip((value-mean)/scale, -self.clip, self.clip).astype(np.float32)

    def to_dict(self):
        return asdict(self)


def main():
    import argparse
    import json
    from pathlib import Path
    import torch
    from threemind_transformer.development_model import load
    from threemind_transformer.native_readout import NativeProjection

    parser = argparse.ArgumentParser(description='Replay anonymous activity through a frozen native language adapter')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True, help='bounded JSONL processes')
    parser.add_argument('--output', type=Path, required=True, help='new output file')
    parser.add_argument('--device', choices=('cpu', 'cuda', 'auto'), default='cpu')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    projection = NativeProjection(**manifest['projection'])
    calibration = FeatureCalibration(**manifest['feature_calibration'])
    checkpoint = Path(manifest['checkpoint'])
    if not checkpoint.is_absolute():
        checkpoint = args.manifest.parent / checkpoint
    if args.input.stat().st_size > 256*2**20:
        raise ValueError('split input into files of at most256MiB')
    device = 'cuda' if args.device in ('cuda', 'auto') and torch.cuda.is_available() else 'cpu'
    model, _ = load(checkpoint, device)
    if model.basis != projection.basis:
        raise ValueError('model and observation basis differ')
    rows = [json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not 1 <= len(rows) <= 16384:
        raise ValueError('bounded nonempty input required')
    with args.output.open('x', encoding='utf-8') as stream:
        for start in range(0, len(rows), 16):
            features = [projection.project(row.get('process', row)) for row in rows[start:start+16]]
            generated = model.decode(calibration.transform([row['values'] for row in features]))
            for result, feature in zip(generated, features, strict=True):
                stream.write(json.dumps({'output':result, 'raw_sum':feature['raw_sum'],
                    'unknown_channels':feature['unknown_channels'], 'device':device}, ensure_ascii=False, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
