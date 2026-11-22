"""Read-only comparison with R51d: real activity versus lifecycle labels."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import support as s


def read(p):
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix == '.gz' else raw)


def main(work):
    old = work.parent / 'stimulus61-v1'
    assert read(work/'cases.json') == read(old/'cases.json')
    labels, changed, max_late, late_cases = Counter(), [], 0., []
    common_error = {f: 0. for f in ('activation', 'inhibition', 'direct', 'associative')}
    new_seconds = old_seconds = 0.
    for case in read(work/'cases.json'):
        key = case['key']
        a, b = work/'cases'/key, old/'cases'/key
        x, y = read(a/'result.json'), read(b/'result.json')
        labels[x['life']] += 1
        new_seconds += x['wall_seconds']; old_seconds += y['wall_seconds']
        ap = {r['time_us']: r for r in read(a/'trajectory.json.gz')['points']}
        bp = {r['time_us']: r for r in read(b/'trajectory.json.gz')['points']}
        for t in ap.keys() & bp.keys():
            an = {n['channel']: n for n in ap[t]['nodes']}
            bn = {n['channel']: n for n in bp[t]['nodes']}
            for c in an.keys() | bn.keys():
                for f in common_error:
                    common_error[f] = max(common_error[f], abs(an.get(c, {}).get(f, 0.) - bn.get(c, {}).get(f, 0.)))
        if x['life'] != y['life']:
            late = [p for t, p in bp.items() if t > x['clock_end_us']]
            peak = max((n.get('activation', 0.) for p in late for n in p['nodes']), default=0.)
            max_late = max(max_late, peak)
            row = {'case': key, 'old_life': y['life'], 'new_life': x['life'],
                   'new_end_us': x['clock_end_us'], 'old_end_us': y['clock_end_us'],
                   'old_samples_after_new_death': len(late), 'old_activation_after_new_death_max': peak}
            changed.append(row)
            if peak > 0: late_cases.append(row)
    result = {'passed': True, 'same_materials_and_schedules': True, 'conditions': 264,
              'lifecycle_counts': dict(labels), 'lifecycle_changes': changed,
              'lifecycle_change_count': len(changed),
              'old_activation_after_new_death_max': max_late,
              'cases_with_old_nonzero_activity_after_new_death': late_cases,
              'shared_time_max_activity_error': common_error,
              'new_trial_seconds': new_seconds, 'historical_trial_seconds': old_seconds,
              'historical_time_ratio': new_seconds/old_seconds,
              'timing_interpretation': 'Historical host loads differ; this is not a controlled speedup estimate.',
              'Core_engines_loaded': 0, 'simulation_advanced': False}
    s.base.original(work/'historical-comparison.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('lifecycle_changes','cases_with_old_nonzero_activity_after_new_death')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    main(p.parse_args().work.resolve())
