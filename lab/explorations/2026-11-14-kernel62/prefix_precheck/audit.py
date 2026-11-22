"""Read-only R51t8 audit: complete states, parentage and independently scored traces."""
import argparse
from decimal import Decimal, localcontext
from dataclasses import replace
import gzip
import itertools
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import run as x
s = x.s


def process(folder, result):
    points = s.unpack(folder / 'process.json.gz')
    assert len(points) == 1502
    times = [p['time_us'] - points[0]['time_us'] for p in points]
    assert times == [0] + list(range(0, 15_000_001, 10000))
    values = {}
    errors = []
    with localcontext() as ctx:
        ctx.prec = 45
        for symbol in 'CE':
            for field in s.measure.FIELDS:
                pairs = [(t, Decimal(str(next((n[field] for n in p['nodes']
                    if n['channel'] == s.measure.TOKENS[symbol]), 0))))
                    for t, p in zip(times, points) if t >= 1_000_000]
                peak = max(v for _, v in pairs)
                area = sum(Decimal(b[0] - a[0]) * (b[1] + a[1]) / Decimal(2_000_000)
                           for a, b in itertools.pairwise(pairs))
                expected = result['measures'][symbol][field]
                errors += [abs(float(peak) - expected['peak']), abs(float(area) - expected['area'])]
                values[symbol, field] = peak, area
        margin = float(values[result['target'], 'activation'][0] - values[result['other'], 'activation'][0])
        area = float(values[result['target'], 'activation'][1] - values[result['other'], 'activation'][1])
        errors += [abs(margin - result['signed_peak']), abs(area - result['signed_area'])]
    assert max(errors) < 1e-12
    return margin, max(errors)


def stream(path):
    with gzip.open(path, 'rt', encoding='utf8') as f:
        for line in f:
            yield json.loads(line)


def flatten(obj, prefix=''):
    if isinstance(obj, dict):
        return {p: v for k, item in obj.items() for p, v in flatten(item, prefix + '/' + str(k)).items()}
    if isinstance(obj, list):
        return {p: v for k, item in enumerate(obj) for p, v in flatten(item, prefix + '/' + str(k)).items()}
    return {prefix: obj}


def divergence(a, b):
    first = None
    max_numeric = 0.0
    differing_rows = 0
    total = 0
    for left, right in zip(stream(a), stream(b), strict=True):
        assert left['time_us'] == right['time_us']
        left.pop('transport', None); right.pop('transport', None)
        lf, rf = flatten(left), flatten(right)
        differences = []
        for key in sorted(lf.keys() | rf.keys()):
            av, bv = lf.get(key), rf.get(key)
            if isinstance(av, (float, int)) and isinstance(bv, (float, int)):
                delta = abs(av - bv)
                max_numeric = max(max_numeric, delta)
                unequal = delta > 1e-12
            else:
                unequal = av != bv
            if unequal:
                differences.append({'field': key, 'a': av, 'b': bv})
        if differences:
            differing_rows += 1
            if first is None:
                first = {'time_us': left['time_us'], 'differences': differences[:30],
                         'difference_count': len(differences),
                         'connections': [[e['source'], e['target']] for e in left['edges']]}
        total += 1
    return {'first': first, 'differing_rows': differing_rows, 'rows': total, 'maximum_numeric_difference': max_numeric}


def run(work):
    x.check(work)
    assert not (work / 'in-flight.json').exists() and not (work / 'STOP').exists()
    summary = s.read(work / 'summary.json')
    assert summary['stages'] == len(summary['results']) == 30
    index = s.read(work / 'cases.json')
    matrix = []
    states = []
    errors = []
    process_count = 0
    for kind, names in (('controls', x.CONTROLS), ('cases', x.VARIANTS)):
        for name in names:
            blocks = []
            for block in (0, 1):
                margins = []
                parent = None
                for cue in ('train', 'AB', 'DB'):
                    folder = work / kind / name / str(block) / cue
                    q = s.read(folder / 'result.json')
                    native = (folder / 'initial.tmind').exists()
                    before = (s.ArtifactCodec.decode((folder / 'initial.tmind').read_bytes()) if native else
                              x.get(folder / 'initial.rstate.gz'))
                    after = (s.ArtifactCodec.decode((folder / 'final.tmind').read_bytes()) if native else
                             x.get(folder / 'final.rstate.gz'))
                    assert before.digest == q['initial_sha256'] and after.digest == q['final_sha256']
                    if kind == 'cases':
                        assert x.r.ResearchEngine(state=after).capture_state().digest == after.digest
                        assert q in summary['results']
                    assert int(after.to_dict()['time_us']) == q['time_us']
                    if cue == 'train':
                        assert q['parent_sha256'] is None and q['time_us'] == 212200000
                        assert int(before.to_dict()['time_us']) == 0
                        parent = after
                    else:
                        assert parent.digest == q['parent_sha256']
                        assert before.to_dict()['time_us'] == parent.to_dict()['time_us']
                        if kind == 'cases':
                            # Reconstruct only the declared no-time-advance config change in a disposable copy.
                            case = index[f'history/s{block}/101/d1/{cue}']
                            copy = x.r.ResearchEngine(state=parent)
                            copy.reconfigure(replace(copy.config, **case['patch']))
                            assert copy.capture_state().digest == before.digest
                        margin, error = process(folder, q)
                        margins.append(margin); errors.append(error); process_count += 1
                    states.append({'folder': folder.relative_to(work).as_posix(),
                                   'initial': before.digest, 'final': after.digest})
                blocks.append({'block': block, 'AB': margins[0], 'DB': margins[1],
                               'passed': all(v > 1e-6 for v in margins)})
            matrix.append({'kind': kind, 'variant': name, 'blocks': blocks,
                           'passed_blocks': sum(b['passed'] for b in blocks)})
    comparisons = {}
    pairs = [(f'cases/{name}', f'controls/{name.removeprefix("pre-")}')
             for name in x.VARIANTS if name.startswith('pre-')]
    pairs += [('cases/old-without-pre', 'controls/old-full'),
              ('cases/pre-old-high', 'controls/old-full')]
    for a, b in pairs:
        comparisons[a + ' vs ' + b] = [divergence(work / a / str(block) / 'train/teaching.jsonl.gz',
              work / b / str(block) / 'train/teaching.jsonl.gz') for block in (0, 1)]
    result = {'material_blocks': 2, 'new_stages': 30, 'reused_stages': 30,
        'matrix': matrix, 'teaching_comparisons': comparisons, 'processes': process_count,
        'states': len(states) * 2, 'maximum_arithmetic_error': max(errors),
        'scientific_wall_seconds': sum(q['wall_seconds'] for q in summary['results'])}
    s.write(work / 'analysis.json', result)
    s.write(work / 'audit.json', {'passed': True, 'scientific_stop': False,
        'new_stages': 30, 'reused_stages': 30, 'processes': process_count,
        'states': len(states) * 2, 'maximum_arithmetic_error': max(errors), 'state_hashes': states})
    print(json.dumps({k: v for k, v in result.items() if k != 'teaching_comparisons'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    args = p.parse_args(); run(args.work)
