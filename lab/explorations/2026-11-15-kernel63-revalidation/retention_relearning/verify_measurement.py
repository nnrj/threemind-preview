"""Pre-birth checks using old originals and synthetic decisions, without a Core."""
import ast
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT/'src')]
import scoring
import analyze
from threemind_kernels.local63_config import Local63Config
from closure_analyze import x2

OLD = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/closure-v1/units')


def function_tree(path, name):
    tree = ast.parse(path.read_text('utf8'))
    return ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), include_attributes=False)


def synthetic_units():
    result = []
    for mode in scoring.MODES:
        for delay in scoring.DELAYS:
            for origin in range(8):
                histories = []
                for history in (0,1):
                    sign = 1 if history == 0 else -1
                    histories.append({'history':history, 'target_edges':[{},{}],
                        'tests':{'none':{'first':0.}, 'weak':{'first':0.}, 'joint':{'first':0.},
                                 'strong':{'first':sign*.01,'late_mean':0.,'early_integral':sign*.001}},
                        'relearning':{'rounds':4}, 'untrained':{'rounds':8}})
                result.append({'mode':mode,'delay':delay,'origin':origin,'histories':histories})
    return result


def verify():
    old_tool = ROOT/'lab/explorations/2026-10-16-mechanism-discovery'
    assert function_tree(old_tool/'closure_rig.py', 'teaching') == function_tree(HERE.parent/'criteria/rig.py', 'teaching')
    configs = {m:Local63Config(**({'consolidation_mode':'stability'} if m == 'stability' else {})).to_dict()
               for m in scoring.MODES}
    assert {k for k in configs['default'] if configs['default'][k] != configs['stability'][k]} == {'consolidation_mode'}
    results, error, probes = [], 0., 0
    for delay in scoring.DELAYS:
        for origin in range(8):
            folder = OLD/f'X2-d{delay}-o{origin}'
            r = analyze.read(folder/'result.json')
            assert r['delay'] == delay and r['origin'] == origin and r['valid']
            for h in r['histories']:
                for test in h['tests'].values():
                    state = analyze.read(folder/test['checkpoint']['path'])
                    assert analyze.s.sha(folder/test['checkpoint']['path']) == test['checkpoint']['sha256']
                    assert analyze.s.base.digest(state) == test['final_sha256']
                    error = max(error, analyze.arithmetic(state['rows'], test, False))
                    probes += 1
                assert h['relearning']['rounds'] == h['untrained']['rounds'] == 2
            results.append(r)
    old = x2(results)
    unavailable = {mode:{'valid':False,'threshold':None} for mode in scoring.MODES}
    doubled = [dict(copy.deepcopy(r),mode=mode) for mode in scoring.MODES for r in results]
    recounted = scoring.evaluate(doubled, unavailable)
    for mode in scoring.MODES:
        for delay in scoring.DELAYS:
            a, b = old['cohorts'][str(delay)], recounted['configurations'][mode]['cohorts'][str(delay)]
            for k in ('separation_count','transient_count','separation_verdict','transient_verdict'):
                assert a[k] == b[k], (mode,delay,k)
            assert b['relearning']['verdict'] == 'MEASUREMENT_UNAVAILABLE'
    # An actually resolved course, a flat floor and a signed response are distinct.
    calibration = [{'mode':mode,'values':[i*.001 for i in range(16)]}
                   for mode in scoring.MODES for _ in range(4)]
    valid = scoring.calibrate(calibration)
    assert all(r['valid'] and r['calibration_rounds'] == [10]*4 for r in valid.values())
    flat = [{'mode':mode,'values':[.01]*16} for mode in scoring.MODES for _ in range(4)]
    assert all(not r['valid'] for r in scoring.calibrate(flat).values())
    assert scoring.first_two([.0,.1,.0,.2,.2], .15) == 5
    assert scoring.first_two([-.1]*16, .001) == 17
    units = synthetic_units()
    baseline = scoring.evaluate(units, valid)
    assert not baseline['scientific_stop']
    for mode in scoring.MODES:
        assert all(c['relearning']['verdict'] == 'PASS' for c in baseline['configurations'][mode]['cohorts'].values())
    one_direction = copy.deepcopy(units)
    for u in one_direction:
        u['histories'][1]['tests']['strong']['first'] = .01
    failed = scoring.evaluate(one_direction, valid)
    assert failed['scientific_stop'] and failed['configurations']['default']['cohorts']['30']['retrieved_origins'] == 0
    for rounds, reason in ((2,'floor_origins'),(17,'censored_origins')):
        changed = copy.deepcopy(units)
        for u in changed:
            for h in u['histories']:
                h['untrained']['rounds'] = rounds
        decision = scoring.evaluate(changed, valid)['configurations']['default']['cohorts']['30']['relearning']
        assert decision['verdict'] == 'INSUFFICIENT_SENSITIVITY' and decision[reason] == 8
    weak_retrieval = copy.deepcopy(units)
    for u in weak_retrieval:
        for h in u['histories']:
            h['tests']['weak']['first'] = .01 if h['history'] == 0 else -.01
    decision = scoring.evaluate(weak_retrieval, valid)
    assert not decision['scientific_stop']
    assert decision['configurations']['default']['cohorts']['30']['separation_count'] == 0
    return {'passed':True, 'Core_engines_created':0, 'old_origins':32, 'old_diagnostic_probes':probes,
            'maximum_decimal_error':error, 'old_separation_counts':{d:c['separation_count'] for d,c in old['cohorts'].items()},
            'old_transient_counts':{d:c['transient_count'] for d,c in old['cohorts'].items()},
            'old_all_relearning_and_naive_at_two_rounds':True,
            'six_counterexample_and_calibration_checks':True, 'teaching_function_ast_identical':True,
            'only_configuration_difference':'consolidation_mode'}


if __name__ == '__main__':
    print(json.dumps(verify(),ensure_ascii=False,indent=2))
