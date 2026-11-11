"""Retrospective description of R47a failures; does not change registered scores."""
import argparse
import gzip
import json
import math
from pathlib import Path


def load(p):
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix == '.gz' else raw)


def describe(work):
    result = load(work / 'analysis-v1.json')
    rows = []
    for curve in sorted({x['curve'] for x in result['details']}):
        subjects = [x for x in result['details'] if x['curve'] == curve]
        courses = {}
        for course in ('massed', 'spaced', 'strong'):
            values = [x['measurements'][course]['expression'] for x in subjects]
            courses[course] = {
                'ranges': {k: [min(v[k] for v in values), max(v[k] for v in values)]
                           for k in ('early_rms', 'late_rms', 'cosine')},
                'overlapping_failure_counts': {
                    'early_rms_at_or_below_1e-4': sum(v['early_rms'] <= 1e-4 for v in values),
                    'late_rms_at_or_below_1e-4': sum(v['late_rms'] <= 1e-4 for v in values),
                    'late_less_than_10pct_early': sum(v['late_rms'] < .1*v['early_rms'] for v in values),
                    'cosine_below_0p8': sum(v['cosine'] < .8 for v in values)},
            }
        weak_birth, weak_late = [], []
        for subject in subjects:
            for history in (0, 1):
                root = work / 'subjects' / f"o{subject['origin']}" / curve / f'weak/d30/h{history}/q1'
                for dst, g in ((weak_birth, load(root/'teaching/result.json.gz')['samples'][-1]),
                               (weak_late, load(root/'probe/result.json.gz')['before'])):
                    dst.extend(e['weight'] for e in g['edges'] if {e['source_symbol'], e['target_symbol']} == {'cue', f'out{history}'})
        fields = ('activation', 'inhibition', 'direct', 'associative')
        late_fields = {}
        for course in ('massed', 'spaced', 'strong'):
            measured = {f: [] for f in fields}
            for subject in subjects:
                values = []
                for h in (0, 1):
                    qs = []
                    for q in (0, 1):
                        p=load(work/'subjects'/f"o{subject['origin']}"/curve/f'{course}/d300/h{h}/q{q}/probe/result.json.gz')
                        qs.append({f: [b[n][f]-a[n][f] for a,b in zip(p['baseline']['frames'],p['response']['frames']) for n in ('out0','out1')] for f in fields})
                    values.append({f: [a-b for a,b in zip(qs[1][f],qs[0][f])] for f in fields})
                for f in fields:
                    vector = [a-b for a,b in zip(values[1][f],values[0][f])]
                    measured[f].append(math.sqrt(sum(v*v for v in vector)/len(vector)))
            late_fields[course] = {f: [min(v),max(v)] for f,v in measured.items()}
        rows.append(dict(curve=curve, expression=courses,
                         weak_initial_weight_range=[min(weak_birth), max(weak_birth)],
                         weak_30s_weight_range=[min(weak_late), max(weak_late)],
                         late_history_rms_by_field=late_fields))
    return dict(retrospective=True, alters_registered_scores=False, independent_origins=8, rows=rows)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args(); result=describe(args.work)
    with (args.work/'retrospective-diagnostics-v1.json').open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(result))
