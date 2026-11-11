"""One streaming pass over E62 records; no rerun or rewriting of evidence."""
import gzip
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import numpy as np
from lab.tools.service_study import encoded, new_json, read_json

WORK = ROOT/'.work/continuous-development-20261007'


def traces(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            for row in record['process']:
                yield np.r_[row['eye_action'], row['hand_action'],
                            row['observation'].get('eye_angle_rad', [0, 0]),
                            [row['pointer_after'][k] for k in ('x', 'y')]]


def main():
    table = []
    for p in sorted((WORK/'cases').glob('*/result.json')):
        r = read_json(p)
        if (p.parent/'scores.json').exists() and 'checkpoint' in r:
            scores = read_json(p.parent/'scores.json')
            r['by_task'] = {mode:{'n':sum(x['mode']==mode for x in scores),
                'end_reached':sum(x['mode']==mode and x['end_reached'] for x in scores),
                'ever_reached':sum(x['mode']==mode and x['ever_reached'] for x in scores),
                'reached_from_outside':sum(x['mode']==mode and x.get('reached_from_outside',False) for x in scores),
                'mean_residence_s':float(np.mean([x['residence_s'] for x in scores if x['mode']==mode])),
                'mean_eye_error_rad':float(np.mean([x['eye_end_error_rad'] for x in scores if x['mode']==mode])),
                'mean_hand_error_m':float(np.mean([x['hand_end_error_m'] for x in scores if x['mode']==mode]))}
                for mode in ('look','point','both')}
        table.append({'case': p.parent.name, **r})
    comparisons = []
    for normal in (WORK/'cases').glob('*-normal/process.jsonl.gz'):
        stem = normal.parent.name.removesuffix('-normal')
        for mode in ('silence', 'rescue'):
            other = WORK/'cases'/f'{stem}-{mode}'/'process.jsonl.gz'
            if not (other.parent/'result.json').exists(): continue
            changed = action_changed = body_changed = count = 0; max_difference = 0.; difference_sum = 0.
            action_max = body_max = 0.
            for a, b in zip(traces(normal), traces(other), strict=True):
                delta = np.abs(a-b); changed += bool(np.any(delta > 1e-7))
                action_changed += bool(np.any(delta[:4] > 1e-7)); body_changed += bool(np.any(delta[4:] > 1e-7))
                action_max = max(action_max, float(delta[:4].max())); body_max = max(body_max, float(delta[4:].max()))
                count += 1; max_difference = max(max_difference, float(delta.max())); difference_sum += float(delta.sum())
            comparisons.append({'reference': normal.parent.name, 'intervention': other.parent.name,
                'frames': count, 'changed_frames': changed, 'maximum_absolute_difference': max_difference,
                'action_changed_frames':action_changed, 'body_changed_frames':body_changed,
                'maximum_command_difference':action_max, 'maximum_body_difference':body_max,
                'mean_absolute_difference': difference_sum/max(1, count*8), 'tolerance': 1e-7})
            left, right = read_json(normal.parent/'scores.json'), read_json(other.parent/'scores.json')
            comparisons[-1]['endpoint_changes'] = [
                {'trial':i, 'mode':a['mode'], 'target_index':a['target_index'],
                 'normal':a['end_reached'], 'intervention':b['end_reached']}
                for i,(a,b) in enumerate(zip(left,right,strict=True)) if a['end_reached'] != b['end_reached']]
    stopped = [{'case':p.parent.name, **read_json(p)} for p in (WORK/'cases').glob('*/stopped.json')]
    result = {'stages': table, 'stopped_attempts': stopped, 'action_and_body_comparisons': comparisons,
        'total_compute_minutes': (sum(r['wall_seconds'] for r in table)+sum(r['wall_seconds'] for r in stopped
            if not (WORK/'cases'/r['case']/'result.json').exists()))/60,
        'created_or_restored': read_json(WORK/'instances.json')['created']}
    target = WORK/'analysis.json'
    if target.exists(): raise FileExistsError('Use a dated follow-up analysis, do not overwrite')
    new_json(target, result)
    print(json.dumps({'analysis':str(target), 'stages':len(table), 'stopped_attempts':len(stopped),
        'total_compute_minutes':result['total_compute_minutes'], 'comparisons':comparisons}, ensure_ascii=False))


if __name__ == '__main__': main()
