"""Summarize completed E60 cases without rehashing or scanning prior evidence."""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/eye-hand-learning-20261007'


def main():
    results = {}
    for path in sorted((WORK/'cases').glob('*/result.json')):
        value = json.loads(path.read_text(encoding='utf-8'))
        if path.parent.name.startswith(('C-fit-', 'D-')) and 'fit2' not in path.parent.name:
            value['evidence_status'] = 'tooling failure: empty training batches; untrained adapter, preserved'
        else:
            value['evidence_status'] = 'completed'
        if path.parent.name.startswith('D-'):
            trials = json.loads((path.parent/'trials.json').read_text(encoding='utf-8'))
            for name, modes in [('eye_requested', ('look', 'both')), ('eye_hold', ('point', 'hold')),
                                ('hand_requested', ('point', 'both')), ('hand_hold', ('look', 'hold'))]:
                subset = [r for r in trials if r['mode'] in modes]
                if subset:
                    value[name] = {'n': len(subset), **{k: float(np.mean([r[k] for r in subset])) for k in
                        ('eye_mean_error_rad', 'eye_center_fraction', 'eye_stable_fraction', 'eye_longest_stable_s',
                         'hand_mean_distance_m', 'hand_arrived_fraction')},
                         'final_eye_aligned': sum(r['eye_final_error_rad'] < .075 for r in subset),
                         'final_hand_arrived': sum(r['hand_final_distance_m'] <= .2 for r in subset)}
        results[path.parent.name] = value
    stopped = {p.parent.name: json.loads(p.read_text(encoding='utf-8'))
               for p in (WORK/'cases').glob('*/stopped.json')}
    summary = {'schema': 'threemind.eye-hand-study/1', 'cases': results, 'stopped_cases': stopped,
               'compute_wall_seconds': sum(v['wall_seconds'] for v in results.values())
                                       + sum(v['wall_seconds'] for v in stopped.values()),
               'instances': json.loads((WORK/'instances.json').read_text(encoding='utf-8'))['created'],
               'scope': 'new E60 evidence only; labels and continuous motor metrics; Core unchanged'}
    audit = WORK/'marker-visibility.json'
    if audit.exists(): summary['optical_audit'] = json.loads(audit.read_text(encoding='utf-8'))
    (HERE/'results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for name, value in results.items():
        if name.startswith('D-'):
            print(json.dumps({'case': name, 'eye_requested': value.get('eye_requested'),
                              'hand_requested': value.get('hand_requested')}, ensure_ascii=False))
    print(json.dumps({'completed_cases': len(results), 'compute_minutes': summary['compute_wall_seconds']/60,
                      'instances': summary['instances']}))


if __name__ == '__main__': main()
