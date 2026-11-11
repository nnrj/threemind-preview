"""Pure saved-result arithmetic for the predeclared relearning assay gate."""
import argparse
import json
from pathlib import Path

import m2_relearning_cal_spec as spec


def summarize(results):
    assert len(results) == spec.N
    assert [r['case'] for r in results] == spec.cases()
    doses = []
    for dose in spec.DOSES:
        origins = []
        for r in results:
            histories = []
            for history in (0, 1):
                branch = next(b for b in r['branches'] if b['history'] == history and b['dose'] == dose)
                assert len(branch['lessons']) == spec.LESSONS
                sign = 1 if history == 0 else -1
                correct = [sign*x['probe']['first'] > spec.MARGIN for x in branch['lessons']]
                baseline_correct = sign*branch['baseline']['first'] > spec.MARGIN
                first = next((i+1 for i, x in enumerate(correct) if x), spec.LESSONS+1)
                late_correct = sum(correct[-4:])
                histories.append({'history': history, 'baseline_correct': baseline_correct,
                                  'first_correct_lesson': first, 'late_correct_of_four': late_correct,
                                  'correct_curve': correct,
                                  'signed_margins': [sign*x['probe']['first'] for x in branch['lessons']],
                                  'eligible': not baseline_correct and 2 <= first <= 12 and late_correct >= 3})
            origins.append({'origin':r['origin'], 'histories':histories,
                            'eligible':all(h['eligible'] for h in histories)})
        doses.append({'dose':dose, 'qualifying_origins':sum(o['eligible'] for o in origins),
                      'eligible':sum(o['eligible'] for o in origins) >= 6, 'origins':origins})
    chosen = next((d['dose'] for d in doses if d['eligible']), None)
    return {'schema':'threemind.relearning-assay-calibration/1', 'independent_calibration_origins':spec.N,
            'scientific_savings_effect_tested':False, 'trained_individuals_compared':0,
            'dose_selection_uses_naive_curve_only':True, 'verdict':'PASS' if chosen is not None else 'FAIL',
            'selected_lesson_dose':chosen, 'dose_results':doses,
            'decision':'Proceed to a separately preregistered savings experiment with new origins.' if chosen is not None
                       else 'No preregistered dose yields a usable acquisition window; retain this failed assay and do not run savings confirmation.',
            'old_closure_scores_changed':False}


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    work=p.parse_args().work
    assert json.loads((work/'status.json').read_bytes())['state']=='awaiting-analysis'
    results=[json.loads((work/'units'/f'o{i}'/'result.json').read_bytes()) for i in range(spec.N)]
    report=summarize(results)
    with (work/'analysis-v1.json').open('x',encoding='utf-8') as f: json.dump(report,f,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='dose_results'}))
