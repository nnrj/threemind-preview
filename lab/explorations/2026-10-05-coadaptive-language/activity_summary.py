"""Describe raw process distinctions; never transform the expression input."""
import gzip
import json
from itertools import combinations

from experiment import WORK, HERE
from threemind_transformer.local_activity import local_process


def main():
    records = []
    groups = {}
    for file in sorted((WORK/'cases').glob('*/result.json')):
        row = json.loads(file.read_bytes())
        if row['kind'] != 'test':
            continue
        with gzip.open(row['process'], 'rt', encoding='utf-8') as stream:
            raw = json.load(stream)
        observed = local_process(raw)
        values = {(i, n['channel'], k): float(v)
                  for i, frame in enumerate(observed['frames']) for n in frame['nodes']
                  for k, v in zip(observed['node_fields'], n['values']) if v != 0}
        item = {key: row[key] for key in ('seed', 'arm', 'stage', 'item', 'perspective', 'output')}
        item.update({'nonzero_associative_samples': sum(any(n['associative'] > 0 for n in f['nodes']) for f in raw['trajectory']),
                     'samples': len(raw['trajectory']), 'local_nodes': len({n['channel'] for f in observed['frames'] for n in f['nodes']})})
        records.append(item)
        if row['item'] >= 0:
            groups.setdefault((row['seed'], row['arm'], row['stage'], row['perspective']), []).append((item, values))
    comparisons = []
    for key, group in groups.items():
        for (left, a), (right, b) in combinations(group, 2):
            delta = max((abs(a.get(k, 0)-b.get(k, 0)) for k in a.keys() | b.keys()), default=0.)
            comparisons.append(dict(zip(('seed', 'arm', 'stage', 'perspective'), key)) | {
                'items': [left['item'], right['item']], 'raw_max_absolute_difference': delta,
                'same_expression': left['output'] == right['output']})
    result = {'definition': 'raw six-field local observations at equal relative sample positions; difference is diagnostic only, never an expression input',
              'limitation': 'different activity alone does not establish learnt meaning; no-cue includes recorded physical background',
              'records': records, 'comparisons': comparisons}
    (HERE/'activity-results.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    print({'comparisons': len(comparisons), 'distinct_raw': sum(r['raw_max_absolute_difference'] > 0 for r in comparisons),
           'same_words_despite_different_raw': sum(r['raw_max_absolute_difference'] > 0 and r['same_expression'] for r in comparisons)})


if __name__ == '__main__':
    main()
