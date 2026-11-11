"""Saved-file and independent arithmetic audit; no engine is instantiated."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

import m2_relearning_cal_spec as spec
import pilot_m2 as m


def load(path, receipt=None):
    raw = path.read_bytes()
    if receipt is not None:
        assert hashlib.sha256(raw).hexdigest() == receipt['sha256']
        assert len(raw) == receipt['byte_count']
    return json.loads(gzip.decompress(raw))


def check_probe(previous, whole, result, *, history=None, dose=None):
    """Verify actual input history, whole-state continuity and measured response."""
    start = previous['time_us']
    offset = 0 if history is None else 2_000_000
    assert result['start_us'] == start+offset
    assert whole['time_us'] == start+offset+1_500_000
    assert whole['inputs'][:len(previous['inputs'])] == previous['inputs']
    assert whole['rows'][:len(previous['rows'])] == previous['rows']
    assert all(whole[k] == previous[k] for k in previous
               if k not in ('model', 'time_us', 'actuator', 'inputs', 'rows'))
    expected = []
    if history is not None:
        expected.append({'time_us':start, 'values':dict.fromkeys('XYA' if history == 0 else 'XYB', dose)})
        expected.extend({'time_us':start+j*500_000, 'values':{'K':.2}} for j in range(1, 5))
    expected.append({'time_us':start+offset, 'values':{'X':spec.PROBE_DOSE}})
    expected.extend({'time_us':start+offset+j*500_000, 'values':{'K':.2}} for j in range(1, 4))
    assert whole['inputs'][len(previous['inputs']):] == expected
    rows = whole['rows'][len(previous['rows']):]
    assert len(rows) == result['trace_count'] == 1500
    assert [r['time_us']-result['start_us'] for r in rows] == list(range(1000, 1_500_001, 1000))
    assert result['first'] == rows[109]['response']
    assert result['choice'] == int(result['first'] > spec.MARGIN)-int(result['first'] < -spec.MARGIN)
    for lo, hi, key in ((100_000,300_000,'early_integral'), (500_000,1_500_000,'late_integral')):
        value = sum(r['response']*.001 for r in rows if lo <= r['time_us']-result['start_us'] <= hi)
        assert abs(value-result[key]) <= 1e-15
    assert m.digest(whole) == result['final_sha256']


def audit(work):
    m.frozen_check(work)
    assert m.read(work/'status.json')['state'] == 'awaiting-analysis'
    analysis = m.read(work/'analysis-v1.json')
    assert analysis['scientific_savings_effect_tested'] is False
    votes = {dose:[] for dose in spec.DOSES}
    counts = {'origins':0, 'branches':0, 'probes':0, 'whole_snapshots':0}
    for origin, case in enumerate(spec.cases()):
        folder = work/'units'/f'o{origin}'
        result = m.read(folder/'result.json')
        assert result['origin'] == origin and result['case'] == case and result['valid']
        birth = load(folder/'birth.json.gz')
        parent = load(folder/'naive-parent.json.gz')
        assert birth['time_us'] == 0 and parent['time_us'] == 47_000_000
        assert parent['seed'] == birth['seed'] == case['seed'] and parent['mode'] == 'S'
        assert set(s for e in parent['inputs'] for s in e['values']) == {'K', 'N'}
        assert parent['rows'] == [] and parent['reader']['kind'] == 'fixed-AB' and parent['optimizer'] is None
        assert len(result['branches']) == len(spec.DOSES)*2
        assert {(b['dose'],b['history']) for b in result['branches']} == {(d,h) for d in spec.DOSES for h in (0,1)}
        counts['whole_snapshots'] += 2
        for dose in spec.DOSES:
            both = []
            for history in (0, 1):
                b = next(b for b in result['branches'] if (b['dose'],b['history']) == (dose,history))
                initial = load(folder/b['initial']['path'], b['initial'])
                expected = copy.deepcopy(parent)
                expected['branch'] = {'parent_sha256':m.digest(parent), 'time_us':parent['time_us'],
                                      'label':f'd{dose:.2f}-h{history}'}
                assert initial == expected
                previous = load(folder/b['baseline_checkpoint']['path'], b['baseline_checkpoint'])
                check_probe(initial, previous, b['baseline'])
                counts['whole_snapshots'] += 2; counts['probes'] += 1
                signed = []
                assert [x['lesson'] for x in b['lessons']] == list(range(1, spec.LESSONS+1))
                for row in b['lessons']:
                    whole = load(folder/row['checkpoint']['path'], row['checkpoint'])
                    assert row['start_us'] == previous['time_us'] and row['end_us'] == whole['time_us']
                    check_probe(previous, whole, row['probe'], history=history, dose=dose)
                    signed.append((1 if history == 0 else -1)*row['probe']['first'])
                    previous = whole; counts['whole_snapshots'] += 1; counts['probes'] += 1
                correct = [v > spec.MARGIN for v in signed]
                first = min([j+1 for j, ok in enumerate(correct) if ok] or [spec.LESSONS+1])
                baseline = (1 if history == 0 else -1)*b['baseline']['first'] > spec.MARGIN
                eligible = not baseline and 2 <= first <= 12 and sum(correct[-4:]) >= 3
                both.append(eligible); counts['branches'] += 1
                a = next(d for d in analysis['dose_results'] if d['dose'] == dose)['origins'][origin]['histories'][history]
                assert a['eligible'] == eligible and a['correct_curve'] == correct
                assert a['signed_margins'] == signed and a['first_correct_lesson'] == first
            votes[dose].append(all(both))
        counts['origins'] += 1
    selected = next((d for d in spec.DOSES if sum(votes[d]) >= 6), None)
    assert analysis['selected_lesson_dose'] == selected
    assert analysis['verdict'] == ('PASS' if selected is not None else 'FAIL')
    for d in analysis['dose_results']:
        assert d['qualifying_origins'] == sum(votes[d['dose']])
    assert counts == {'origins':8, 'branches':64, 'probes':1088, 'whole_snapshots':1168}
    report = {'schema':'threemind.relearning-assay-file-audit/1', 'passed':True, 'counts':counts,
              'selected_lesson_dose':selected, 'Core_engines_loaded':0,
              'naive_curves_only':True, 'scientific_savings_effect_tested':False}
    m.original(work/'audit-v1.json',report)
    print(json.dumps(report))


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,required=True)
    audit(p.parse_args().work)
