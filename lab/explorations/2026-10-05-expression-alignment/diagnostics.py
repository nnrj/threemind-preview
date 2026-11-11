"""Post-result description of familiar-answer reuse; no fitting or simulation."""
from experiment import HERE, WORK, read_json, new_json


def main():
    output = []
    for scope, folder in (('cross', 'decoded'), ('all', 'all-decoded')):
        rows = [row for path in sorted((WORK / folder).glob('two-assignments-s*-words.json'))
                for row in read_json(path) if row['split'] == 'test' and row['item'] >= 0]
        known = {(r['seed'], r['condition'], r['item']): r['target'] for r in rows
                 if r['condition'] in ('continued', 'reversal') and r['seconds'] == 592}
        for condition in ('cycle1', 'cycle2'):
            for seconds in (532, 592):
                group = [r for r in rows if r['condition'] == condition and r['seconds'] == seconds]
                output.append({'scope': scope, 'condition': condition, 'seconds': seconds,
                    'total': len(group),
                    'old_identity': sum(r['transformer']['output']['text'] == known[r['seed'], 'continued', r['item']] for r in group),
                    'old_reversal': sum(r['transformer']['output']['text'] == known[r['seed'], 'reversal', r['item']] for r in group),
                    'empty': sum(not r['transformer']['output']['text'] for r in group)})
    new_json(HERE / 'interpretation-checks.json', {
        'status': 'post-result descriptive analysis, not a new success criterion',
        'meaning': 'Familiar answers can also coincide with a new target on some items; counts are not mutually exclusive with correctness.',
        'rows': output})


if __name__ == '__main__':
    main()
