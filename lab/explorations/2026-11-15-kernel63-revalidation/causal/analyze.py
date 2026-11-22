"""Read-only causal comparisons, complete-state checks, and explicit batch verdict."""
import argparse
import gzip
import json
from pathlib import Path
import statistics as st
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import support as s
from allocation import disk_allocation

ARMS = ('intact', 'sham', 'target', 'matched', 'restored')
FIELDS = ('activation', 'inhibition', 'direct', 'associative')


def load(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_bytes())


def window(rows, start, end):
    chosen = [r for r in rows if start <= r['time_us'] <= end]
    assert chosen
    return st.mean(r['projection']['activation'][0] - r['projection']['activation'][1] for r in chosen)


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert load(work / 'summary.json')['causal_copies'] == 80
    cases = load(work / 'frozen.json')['parents']
    measured, residuals, checks = {}, [], []
    for case in cases:
        folder = work / 'parents' / case['id']
        parent = load(folder / 'parent.json.gz')
        earlier = load(folder / 'boundary-9s.json.gz')
        assert earlier['case'] == case
        assert int(earlier['core']['time_us']) == 9000000
        assert earlier['core']['dynamics'] == 'threemind.continuous-memory/6.3'
        assert parent['rows'][:len(earlier['rows'])] == earlier['rows']
        assert earlier['schedule'] == parent['schedule'] and earlier['cursor'] < parent['cursor']
        assert parent['case'] == case
        assert parent['core']['dynamics'] == 'threemind.continuous-memory/6.3'
        assert int(parent['core']['time_us']) == 18000000
        assert all(n['channel'] == n['id'] for n in parent['core']['nodes'])
        selection = load(folder / 'selection.json')
        a, b = selection['groups']['target'], selection['groups']['matched']
        counts_ok = len(a) == len(b) == 2
        valid = counts_ok
        if valid:
            weight_diff = st.mean(x['weight'] for x in a) - st.mean(x['weight'] for x in b)
            activity_diff = [st.mean(x['teaching_activity'][i] for x in a) - st.mean(x['teaching_activity'][i] for x in b) for i in (0, 1)]
            degrees = all(x['degrees'] == y['degrees'] for x, y in zip(a, b))
            valid = degrees and abs(weight_diff) <= .02 and all(abs(v) <= .02 for v in activity_diff)
            assert abs(selection['residuals']['weight_mean_difference'] - weight_diff) < 1e-12
        assert valid == selection['matching_passed']
        residuals.append({'case': case['id'], 'passed': valid, **selection['residuals']})
        finals = {}
        for arm in ARMS:
            out = folder / arm
            initial, final, result = [load(out / name) for name in ('initial.json.gz', 'final.json.gz', 'result.json')]
            assert result['case'] == case and result['arm'] == arm
            assert s.base.digest(final) == result['final_digest']
            assert result['intervention']['before'] == s.base.digest(parent)
            assert s.base.digest(initial) == result['intervention']['after']
            assert int(final['core']['time_us']) == 20000000
            assert final['cursor'] == len(final['schedule'])
            assert final['rows'][:len(parent['rows'])] == parent['rows']
            if arm in ('target', 'matched'):
                assert result['intervention']['changed_fields'] == ['core.silenced_edges']
                assert len(initial['core']['silenced_edges']) == 2
            else:
                assert s.base.digest(initial) == s.base.digest(parent)
            primary = window(final['rows'], 18100000, 18300000)
            assert abs(primary - result['primary_response']) < 1e-12
            measured[case['id'], arm] = {'primary': primary,
                'late': window(final['rows'], 18500000, 19500000),
                'point_500ms': window(final['rows'], 18500000, 18500000)}
            finals[arm] = final
        assert s.base.digest(finals['intact']) == s.base.digest(finals['sham']) == s.base.digest(finals['restored'])
        unrelated = {}
        for arm in ARMS:
            rows = [r for r in finals[arm]['rows'] if r['time_us'] > 18000000]
            reference = [r for r in finals['intact']['rows'] if r['time_us'] > 18000000]
            assert [r['time_us'] for r in rows] == [r['time_us'] for r in reference]
            unrelated[arm] = {f: max(abs(x['projection'][f][i] - y['projection'][f][i])
                                      for x, y in zip(rows, reference) for i in (2, 3)) for f in FIELDS}
        checks.append({'case': case['id'], 'restored_whole_state_equal': True,
                       'sham_whole_state_equal': True, 'unrelated_max_errors': unrelated})
    origins = []
    for o in range(8):
        values = {arm: {metric: (measured[f'o{o}-h0', arm][metric] - measured[f'o{o}-h1', arm][metric]) / 2
                       for metric in ('primary', 'late', 'point_500ms')} for arm in ARMS}
        reference = values['intact']['primary']
        ratio = lambda arm: 1 - values[arm]['primary'] / reference if reference != 0 else None
        target, matched = ratio('target'), ratio('matched')
        valid = all(x['passed'] for x in residuals if x['case'].startswith(f'o{o}-'))
        passed = valid and reference > 0 and target is not None and target >= .9 and matched <= .1
        origins.append({'origin': f'm1-o{o}', 'seed': 817100 + o, 'matching_valid': valid,
                        'effects': values, 'target_reduction': target, 'matched_reduction': matched,
                        'strong_replication': passed})
    missing = all(x['effects']['intact']['primary'] <= 0 for x in origins)
    reversal = st.mean(x['effects']['target']['primary'] for x in origins) > st.mean(x['effects']['matched']['primary'] for x in origins)
    stop = missing or reversal
    verdict = 'strong selective causal effect replicated' if all(x['strong_replication'] for x in origins) else (
        'measurement matching insufficient' if not all(x['matching_valid'] for x in origins) else 'strong replication target not met')
    files = [p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    result = {'kernel': '6.3', 'origins': origins, 'matching': residuals, 'checks': checks,
              'verdict': verdict, 'scientific_stop': stop,
              'stop_reasons': {'all_history_effects_nonpositive': missing, 'target_matched_reversal': reversal},
              'whole_state_count': 192, 'independent_origins': 8, 'causal_copies': 80,
              'storage': {'logical_bytes': sum(p.stat().st_size for p in files),
                          'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}}
    s.base.original(work / 'analysis.json', result)
    s.base.original(work / 'audit.json', {'passed': True, 'complete_states': 192,
                                        'scientific_stop': stop, 'independent_origins': 8})
    print(json.dumps({k: v for k, v in result.items() if k not in ('matching', 'checks')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    analyze(p.parse_args().work.resolve())
