"""Read-only X1 arithmetic and full-state audit, with independent Decimal sums."""
import argparse
from decimal import Decimal
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE.parent), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import support as s
from allocation import disk_allocation
from closure_analyze import x1
from pilot_m1 import differences


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert read(work / 'summary.json')['origins'] == 8
    results = [read(work / 'units' / f'o{i}' / 'result.json') for i in range(8)]
    assert all(r['valid'] for r in results)
    result = x1(results)
    counts = {'origins': 0, 'probes': 0, 'complete_states': 0, 'fast_zero_change': 0, 'bundle_only_endpoints': 0}
    max_error = 0.; matches = []
    for r in results:
        folder = work / 'units' / f"o{r['origin']}"
        for path in folder.glob('*.json.gz'):
            whole = read(path)
            assert whole['schema'] == 'threemind.criteria63-whole/1'
            assert whole['seed'] == 1016100 + r['origin']
            assert whole['model']['dynamics'] == 'threemind.continuous-memory/6.3'
            assert int(whole['model']['time_us']) == whole['time_us']
            assert whole['model']['config']['prune_weight'] == .008
            counts['complete_states'] += 1
        independently = {}
        for t in r['trials']:
            path = folder / t['checkpoint']['path']
            assert s.sha(path) == t['checkpoint']['sha256']
            whole = read(path); probe = t['result']; start = probe['start_us']
            assert s.base.digest(whole) == probe['final_sha256']
            rows = [v for v in whole['rows'] if start < v['time_us'] <= start + 1500000]
            assert len(rows) == 1500
            first = next(v for v in rows if v['time_us'] == start + 110000)
            choice = int(first['response'] > 1e-4) - int(first['response'] < -1e-4)
            assert first['response'] == probe['first'] and choice == probe['choice'] == first['body']['gate']
            assert t['goal'] == (-1 if t['history'] == 0 else 1)
            assert t['success'] == (choice == t['goal'])
            sensory = [v for v in whole['inputs'] if v['time_us'] == start + 250000]
            assert sensory == [{'time_us': start + 250000, 'values': {'X' if choice > 0 else 'Z' if choice < 0 else 'N': .2}}]
            second = next(v for v in rows if v['time_us'] == start + 360000)
            next_action = int(second['response'] > 1e-4) - int(second['response'] < -1e-4)
            assert second['body']['gate'] == max(-1, min(1, choice + next_action))
            for lo, hi, name in ((100000, 300000, 'early_integral'), (500000, 1500000, 'late_integral')):
                value = sum(Decimal(str(v['response'])) * Decimal('.001') for v in rows if lo <= v['time_us'] - start <= hi)
                error = abs(float(value) - probe[name]); max_error = max(max_error, error)
                assert error <= 1e-12
            domain = 'target' if t['cue'] in ('X', 'Y', 'XY') else 'unrelated'
            independently.setdefault((t['arm'], domain), []).append(choice == t['goal'])
            counts['probes'] += 1
        reported = next(v for v in result['origins'] if v['origin'] == r['origin'])
        rates = {arm: {domain: sum(independently[arm, domain]) / 6 for domain in ('target', 'unrelated')}
                 for arm in ('intact', 'sham', 'target-bundle', 'matched-bundle', 'persistent', 'fast', 'restored')}
        assert rates == reported['rates']
        assert reported['pass'] == (rates['target-bundle']['target'] >= .75
            and rates['target-bundle']['target'] - rates['sham']['target'] >= .5
            and rates['sham']['unrelated'] - rates['target-bundle']['unrelated'] <= .1
            and rates['matched-bundle']['target'] - rates['sham']['target'] <= .1)
        for h in (0, 1):
            parent = read(folder / f'parent-h{h}.json.gz')
            matches.append(read(folder / 'matching.json')[str(h)])
            for arm in ('sham', 'restored'):
                assert read(folder / f'h{h}-{arm}-initial.json.gz') == parent
                for cue in ('X', 'Y', 'XY', 'Z', 'W', 'ZW'):
                    # Branch identity differs by lineage only; biological state and all observations must match.
                    a = read(folder / f'h{h}-intact-{cue}-final.json.gz')
                    b = read(folder / f'h{h}-{arm}-{cue}-final.json.gz')
                    a['branch'] = b['branch']
                    assert a == b
            for arm in ('target-bundle', 'matched-bundle', 'persistent', 'fast'):
                state = read(folder / f'h{h}-{arm}-initial.json.gz')
                changed = differences(parent, state)
                assert set(changed) <= {'model.edges', 'model.timers'}
                receipt = read(folder / f'h{h}-{arm}-intervention.json')
                assert receipt['changed_paths'] == changed
                if arm == 'fast': counts['fast_zero_change'] += not changed
                if arm == 'target-bundle':
                    counts['bundle_only_endpoints'] += all(
                        {k: v for k, v in old.items() if k != 'target'} == {k: v for k, v in new.items() if k != 'target'}
                        for old, new in zip(receipt['removed'], receipt['inserted']))
        counts['origins'] += 1
    assert counts['probes'] == 672 and counts['complete_states'] == 816
    assert result['passed_origins'] == sum(o['pass'] for o in result['origins'])
    files = [p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts) & {'.research-records', 'publication', 'readback'}]
    result.update(schema='threemind.r63g-transfer-analysis/1', independent_origins=8, matching=matches,
                  resources=read(work / 'resource-summary.json'), timing=read(work / 'summary.json'),
                  storage={'logical_bytes': sum(p.stat().st_size for p in files),
                           'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)})
    stop = result['verdict'] != 'PASS'
    audit = {'passed': True, 'counts': counts, 'maximum_decimal_integral_error': max_error,
             'scientific_stop': stop, 'Core_engines_loaded': 0, 'statistical_rules_independently_recounted': True}
    s.base.original(work / 'analysis.json', result); s.base.original(work / 'audit.json', audit)
    print(json.dumps({'verdict': result['verdict'], 'passed_origins': result['passed_origins'],
                      'persistent': result['persistent_verdict'], 'fast': result['fast_verdict'], 'audit': audit}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    analyze(p.parse_args().work.resolve())
