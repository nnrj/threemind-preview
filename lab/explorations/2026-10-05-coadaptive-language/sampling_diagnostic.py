"""Read-only localization of literal-word information before and after sampling."""
import gzip
import json

from experiment import WORK, HERE
from threemind_transformer.local_activity import FIELDS, local_process


def compare(a, b):
    keys = a.keys() | b.keys()
    return max((abs(a.get(k, 0.) - b.get(k, 0.)) for k in keys), default=0.)


def dense(frame):
    return {(int(n['channel']), k): float(n[k]) for n in frame['nodes'] for k in FIELDS}


def main():
    rows = []
    for seed in (223, 279):
        folder = WORK/'cases'/f'transcription-s{seed}-stage0'
        raw = []
        for name in ('0-0.4.json.gz', '1-0.4.json.gz'):
            with gzip.open(folder/name, 'rt', encoding='utf-8') as stream:
                raw.append(json.load(stream))
        offsets = [[int(f['time_us'])-int(r['start_us']) for f in r['trajectory']] for r in raw]
        assert offsets[0] == offsets[1]
        differences = [compare(dense(a), dense(b))
                       for a, b in zip(raw[0]['trajectory'], raw[1]['trajectory'])]
        local = [local_process(r) for r in raw]
        values = [{(int(f['time_us'])-int(r['start_us']), n['channel'], k): float(v)
                   for f in r['frames'] for n in f['nodes'] for k, v in zip(r['node_fields'], n['values'])}
                  for r in local]
        rows.append({'seed': seed, 'files': [str(folder/name) for name in ('0-0.4.json.gz', '1-0.4.json.gz')],
                     'dense_frames': len(differences), 'different_frames': sum(x > 0 for x in differences),
                     'dense_max_difference': max(differences),
                     'difference_at_120ms': differences[offsets[0].index(120000)],
                     'sampled_frames': len(local[0]['frames']), 'actual_local_max_difference': compare(*values)})
    result = {'purpose': 'diagnostic differences only; never submitted to Core or expression adapters', 'rows': rows}
    (HERE/'sampling-diagnostic.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(rows)


if __name__ == '__main__':
    main()
