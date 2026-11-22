"""Post-result descriptive tables; reads saved files and never creates a Core."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
from threemind_runtime import ArtifactCodec


def changed_paths(a, b, path=''):
    if type(a) is not type(b):
        return [path]
    if isinstance(a, dict):
        return [p for k in sorted(a.keys() | b.keys())
                for p in changed_paths(a.get(k), b.get(k), path + '/' + k)]
    if isinstance(a, list):
        if len(a) != len(b):
            return [path + '/length']
        return [p for i, (x, y) in enumerate(zip(a, b))
                for p in changed_paths(x, y, path + '/' + str(i))]
    return [path] if a != b else []


def describe(work):
    a = json.loads((work / 'analysis.json').read_bytes())
    out = {'analysis_type': 'retrospective descriptive tables; registered scores unchanged',
           'Core_engines_loaded': 0, 'integral_margins': [], 'matched_stage_timing': {},
           'intervention_changed_fields': {}, 'raw_directions': []}
    for v in ('v2', 'v31', 'v51', 'v53', 'v61', 'v61-signal004'):
        rows = [r for r in a['responses'] if r['variant'] == v and r['arm'] == 'intact' and r['mode'] == 'full']
        out['raw_directions'].append({'variant': v, 'n': len(rows),
            'directions': dict(Counter(r['windows']['raw_post']['direction'] for r in rows))})
        for seed in (930101, 930102, 930103, 930104):
            margins = []
            for r in rows:
                if r['seed'] == seed:
                    q = r['windows']['post_input']['fields']['activation']['signed_integrals']
                    expected = int(r['sign'] < 0)
                    margins.append(q[expected] - q[1 - expected])
            out['integral_margins'].append({'variant': v, 'seed': seed, 'n': len(margins),
                'mean': sum(margins) / len(margins), 'minimum': min(margins), 'maximum': max(margins)})
        if v != 'v61-signal004':
            times = []
            for p in (work / 'subjects').glob(v + '-*/**/result.json'):
                r = json.loads(p.read_bytes())
                if r['variant'] == v and r['mode'] in ('full', 'no_imu') and (
                        r['stage'] in ('teaching', 'wait1') or r.get('arm') == 'intact'):
                    times.append(r['wall_seconds'])
            assert len(times) == 80
            out['matched_stage_timing'][v] = {'n': len(times), 'seconds': sum(times)}
    for v in ('v2', 'v61'):
        for arm, field in (('test-no-inhibition', 'inhibition'), ('test-no-fast', 'fast_enabled')):
            frequencies = Counter()
            count = 0
            for p in (work / 'subjects').glob(v + '-*/' + arm + '-*/intervened.tmind'):
                before = ArtifactCodec.decode((p.parent / 'initial.tmind').read_bytes()).to_dict()
                after = ArtifactCodec.decode(p.read_bytes()).to_dict()
                assert before['time_us'] == after['time_us']
                assert before['dynamics'] == after['dynamics']
                config_changes = [k for k in before['config'] if before['config'][k] != after['config'][k]]
                assert config_changes == [field] and after['config'][field] is False
                paths = changed_paths(before, after)
                normalized = {'/'.join('*' if c.isdigit() else c for c in path.split('/')) for path in paths}
                frequencies.update(normalized)
                count += 1
            assert count == 48
            out['intervention_changed_fields'][v + ':' + arm] = {'states': count,
                'configured_change': field, 'same_internal_time': True,
                'field_occurrences': dict(sorted(frequencies.items()))}
    dest = work / 'report-statistics.json'
    with dest.open('x', encoding='utf-8') as stream:
        json.dump(out, stream, ensure_ascii=False, sort_keys=True, indent=2)
    print(json.dumps({'path': str(dest), 'patch_states': 192,
        'matched_stage_timing': out['matched_stage_timing'],
        'fields': {k: sorted(v['field_occurrences']) for k, v in out['intervention_changed_fields'].items()}}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    describe(p.parse_args().work.resolve())
