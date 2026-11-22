"""Descriptive diagnostics from audited answer integrals; no simulation."""
import argparse
import json
from pathlib import Path


def run(work):
    read = lambda p: json.loads(p.read_text('utf8'))
    assert read(work / 'audit.json')['passed']
    answers = read(work / 'analysis.json')['answers']
    rows = [r for r in answers if r['task'] == 'pair' and r['profile'] == 'no-inhibition'
            and r['category'] != 'blank']
    result = {'analysis_role': 'Descriptive explanation of the frozen final choices; no new success criterion',
              'pair_without_inhibition': {'questions': len(rows),
                  'C_integral_range': [min(r['process_integrals']['activation']['C'] for r in rows),
                                       max(r['process_integrals']['activation']['C'] for r in rows)],
                  'E_integral_range': [min(r['process_integrals']['activation']['E'] for r in rows),
                                       max(r['process_integrals']['activation']['E'] for r in rows)],
                  'maximum_absolute_C_minus_E': max(abs(r['margin_C_minus_E']) for r in rows),
                  'WAIT_count': sum(r['choice'] == 'WAIT' for r in rows)},
              'by_exact_delay': []}
    for task in ('pair', 'prefix'):
        for profile in ('reference', 'short-inhibition', 'prefix-candidate', 'no-inhibition'):
            for delay in (.5, 3., 30., 60.):
                rr = [r for r in answers if r['task'] == task and r['profile'] == profile
                      and r['cue'] is not None and not r['distractor'] and r['delay'] == delay]
                result['by_exact_delay'].append({'task': task, 'profile': profile, 'delay_seconds': delay,
                    'questions': len(rr), 'correct': sum(r['correct'] for r in rr),
                    'WAIT': sum(r['choice'] == 'WAIT' for r in rr)})
    path = work / 'decision-diagnostic.json'
    assert not path.exists()
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    run(p.parse_args().work)
