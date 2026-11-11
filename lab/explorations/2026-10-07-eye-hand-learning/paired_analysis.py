"""Read recorded E60 interventions once; do not rerun or alter Core."""
import gzip
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.gaze_events import gaze_events

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/eye-hand-learning-20261007'


def records(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def phase_summary(rows):
    selected = [r for r in rows if r['result']['mode'] in ('look', 'both')]
    phases = [p for r in selected for p in gaze_events(r['process'], r['scoring_only_eye_targets'])['phases']]
    not_aligned = [p for p in phases if not p['clear_center']['inside_at_start']]
    return {
        'requested_eye_trials': len(selected), 'target_phases': len(phases),
        'initially_aligned_phases': len(phases) - len(not_aligned),
        'initially_unaligned_phases': len(not_aligned),
        'unaligned_then_entered': sum(p['clear_center']['first_s'] is not None for p in not_aligned),
        'unaligned_then_aligned_slow': sum(p['aligned_slow']['first_s'] is not None for p in not_aligned),
        'unaligned_and_ended_aligned': sum(p['clear_center']['inside_at_end'] for p in not_aligned),
        'longest_aligned_slow_s': max((p['aligned_slow']['longest_s'] for p in phases), default=0),
        'retarget_phases': [gaze_events(r['process'], r['scoring_only_eye_targets'])['phases'][-1]
                            for r in selected],
    }


def compare(reference, other):
    if len(reference) != len(other) or any(a['task'] != b['task'] for a, b in zip(reference, other)):
        raise ValueError('paired tasks differ')
    trials = []
    for i, (a, b) in enumerate(zip(reference, other)):
        if len(a['process']) != len(b['process']): raise ValueError('paired observation counts differ')
        eye = float(np.linalg.norm(np.subtract(a['result']['eye_final'], b['result']['eye_final'])))
        hand = float(np.linalg.norm(np.subtract(a['result']['hand_final'], b['result']['hand_final'])))
        action_delta = max(float(np.max(np.abs(np.subtract(x[k], y[k]))))
                           for x, y in zip(a['process'], b['process'])
                           for k in ('eye_action', 'hand_action'))
        trials.append({'trial': i, 'mode': a['result']['mode'], 'eye_endpoint_difference_rad': eye,
                       'hand_endpoint_difference_m': hand, 'maximum_action_difference': action_delta,
                       'reference_associative_integral': a['result']['associative_integral'],
                       'other_associative_integral': b['result']['associative_integral']})
    return {'n': len(trials), 'endpoint_tolerance': 1e-9,
            'changed_eye_endpoints': sum(t['eye_endpoint_difference_rad'] > 1e-9 for t in trials),
            'changed_hand_endpoints': sum(t['hand_endpoint_difference_m'] > 1e-9 for t in trials),
            'maximum_action_difference': max(t['maximum_action_difference'] for t in trials),
            'trials': trials}


def main():
    model = json.loads((WORK / 'selection.json').read_text())['model']
    version = '-v2' if model.endswith('-v2') else ''
    updated = f'C-fit-B-teach-shared-activity-fit2-E-correct-B-teach{version}-val2'
    prefix = f'D-E-correct-B-teach-{updated}'
    suffix = '-brief-confirmation-world-B-teach'
    datasets = {}
    for mode in ('normal', 'empty', 'silence', 'rescue'):
        folder = WORK / 'cases' / f'{prefix}-{mode}{suffix}'
        if (folder / 'result.json').exists(): datasets[mode] = records(folder / 'process.jsonl.gz')
    if 'normal' not in datasets: raise ValueError('normal confirmation not completed')
    output = {'schema': 'threemind.eye-hand-paired-analysis/1',
              'scope': 'fixed updated reader; corrected student; common physical starting state',
              'phase_metrics': {name: phase_summary(rows) for name, rows in datasets.items()},
              'paired': {name: compare(datasets['normal'], rows) for name, rows in datasets.items() if name != 'normal'}}
    (HERE / 'paired-results.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: {n: {a: b for a, b in v.items() if a not in ('trials', 'retarget_phases')}
                               for n, v in values.items()} for k, values in output.items()
                      if k in ('phase_metrics', 'paired')}, ensure_ascii=False))


if __name__ == '__main__': main()
