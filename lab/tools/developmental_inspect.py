"""Read-only calibration checks for a personal developmental motor peripheral.

These are scores on retained TEACHER examples, not independent behavior or a
claim to decode subjective intent. No Core is created and no weights are fitted.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from lab.tools.developmental_motor import DevelopmentalMotor


def retained_calibration(model, examples=None):
    source = model if examples is None else examples
    if source.identity != model.identity or source.layout.channels != model.layout.channels:
        raise ValueError('Calibration samples must belong to the same individual and mapping')
    count = len(source.replay_x)
    result = {'schema':'threemind.motor-calibration-check/1', 'identity':model.identity,
              'motor_steps':model.steps, 'examples_seen':model.examples_seen,
              'retained_examples':count, 'scope':'retained supervised examples, not held-out behavior',
              'input':'unmodified raw Core activity windows', 'example_source_motor_steps':source.steps}
    if not count: return result
    was_training = model.training; predictions = []
    model.eval()
    try:
        with torch.no_grad():
            for start in range(0, count, 16):
                x = torch.as_tensor(np.stack(source.replay_x[start:start+16]), device=next(model.parameters()).device)
                predictions.append(model(x).cpu().numpy())
    finally: model.train(was_training)
    predictions = np.concatenate(predictions)
    difference = predictions-np.asarray(source.replay_y)
    return result | {'mean_squared_pose_error':float(np.mean(difference**2)),
        'mean_absolute_error_by_output':np.mean(np.abs(difference), axis=0).tolist(),
        'eye_fraction_error_median':float(np.median(np.linalg.norm(difference[:,:2],axis=1))),
        'hand_target_error_m_median':float(np.median(np.linalg.norm(difference[:,2:],axis=1))),
        'outputs':['eye_yaw_fraction','eye_pitch_fraction','hand_x_m','hand_y_m']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('motor', type=Path, help='Saved personal motor directory, not a Core-only checkpoint')
    p.add_argument('--output', type=Path)
    p.add_argument('--examples-from', type=Path, help='Optional earlier/later teacher cache of the SAME individual; read-only')
    args = p.parse_args(); torch.set_num_threads(2)
    model = DevelopmentalMotor.restore(args.motor, device='cpu')
    examples = DevelopmentalMotor.restore(args.examples_from, device='cpu') if args.examples_from else None
    result = retained_calibration(model, examples)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream: stream.write(text)
    print(text)


if __name__ == '__main__': main()
