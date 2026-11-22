"""Read-only matched comparison of completed E21 and R63m scores."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def compare(work):
    old_path = ROOT / '.work/order-mechanisms-20261001/final.json'
    new_path = work / 'analysis.json'
    assert json.loads((work / 'audit.json').read_bytes())['passed']
    old, new = (json.loads(p.read_bytes()) for p in (old_path, new_path))
    index = {(r['seed'], *r['group']): r for r in old['pairs']}
    matched, counts = [], Counter()
    for r in new['scores']['contrasts']:
        key = (r['seed'], r['family'], r['tau'], r['gap_us'], r['phase_us'], r['delay_s'], r['cue'])
        prior = index[key]
        status = ('retained' if r['bidirectional'] else 'lost') if prior['bidirectional_1e6'] else ('gained' if r['bidirectional'] else 'absent_both')
        counts[(r['family'], status)] += 1
        matched.append({'key': key, 'status': status, 'old': prior,
                        'new_bidirectional': r['bidirectional'],
                        'old_primacy': max(prior['margins']) < -1e-6,
                        'new_recency': r['recency'],
                        'new_margins': [v['recency'] for v in r['responses']]})
    assert len(matched) == 384
    result = {'created_engines': 0, 'matched_comparisons': len(matched),
              'old_path': str(old_path), 'old_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(),
              'new_sha256': hashlib.sha256(new_path.read_bytes()).hexdigest(),
              'counts': [{'family': k[0], 'status': k[1], 'n': v} for k, v in counts.items()],
              'primacy_to_recency': sum(r['old_primacy'] and r['new_recency'] for r in matched),
              'matched': matched}
    target = work / 'postprocessing/historical-comparison.json'
    with target.open('x', encoding='utf-8') as out: json.dump(result, out, ensure_ascii=False, sort_keys=True)
    print(json.dumps({k: v for k, v in result.items() if k != 'matched'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True)
    compare(parser.parse_args().work.resolve())
