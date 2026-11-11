"""Check saved E60 adapter inference on CPU and CUDA; no Core is created."""
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.continuous_motor import ContinuousMotor

WORK = ROOT / '.work/eye-hand-learning-20261007'


def main():
    torch.set_num_threads(2)
    if not torch.cuda.is_available(): raise RuntimeError('CUDA required for this explicit device comparison')
    torch.cuda.set_per_process_memory_fraction(.60)
    model = json.loads((WORK / 'selection.json').read_text())['model']
    folder = WORK / 'cases' / model / 'controller'
    with np.load(WORK / 'cases' / 'B-teach' / 'features.npz') as data:
        x = data['activity'][::max(1, len(data['activity']) // 8)][:8]
    cpu = ContinuousMotor.restore(folder, 'cpu')
    cuda = ContinuousMotor.restore(folder, 'cuda')
    a, b = cpu.predict(x), cuda.predict(x)
    difference = float(np.max(np.abs(a - b)))
    if difference > 1e-5: raise ValueError('CPU/CUDA motor inference divergence')
    result = {'model': model, 'windows': len(x), 'maximum_absolute_difference': difference,
              'tolerance': 1e-5, 'gpu': torch.cuda.get_device_name(0),
              'cpu_inference': True, 'cuda_inference': True,
              'scope': 'same saved adapter; no Core execution or changed world input'}
    with (WORK / 'device-check.json').open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
