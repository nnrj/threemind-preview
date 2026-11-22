"""Read-only analysis of RT63-01 originals, with separate source/audit evidence."""
from __future__ import annotations
import csv
from decimal import Decimal
import itertools
import json
import math
import numpy as np
import study as s
from threemind_kernels.mechanisms import ShortTermState, FastTrace


def load(folder):
    rows = s.read(folder / 'trajectory.json.gz')
    return np.array([r['time_us'] for r in rows], dtype=np.int64), np.array([r['values'] for r in rows], dtype=float)


def distance(a, b, times, indices, field=0):
    v = np.abs(a[:, indices, field] - b[:, indices, field]).sum(axis=1)
    return float(np.sum((v[1:] + v[:-1]) * np.diff(times) / 2_000_000))


def decimal_distance(a, b, times, indices, field=0):
    values = [sum((abs(Decimal.from_float(float(a[t, i, field])) - Decimal.from_float(float(b[t, i, field])))
                   for i in indices), Decimal(0)) for t in range(len(times))]
    return float(sum(((values[j]+values[j-1]) * Decimal(int(times[j]-times[j-1])) / Decimal(2_000_000)
                      for j in range(1, len(times))), Decimal(0)))


def analyze():
    assert s.read(s.WORK / 'science-complete.json')['stages'] == 144
    s.frozen_check()
    rows, quiet, shams, checks = [], [], [], []
    originals = list((s.WORK / 'science').rglob('result.json'))
    for result_path in originals:
        folder = result_path.parent
        r = s.read(result_path)
        start, final = s.state_read(folder / 'initial.tmind'), s.state_read(folder / 'final.tmind')
        assert (start.digest, final.digest) == (r['initial_sha256'], r['final_sha256'])
        assert final.to_dict()['dynamics'] == s.KERNEL
        assert int(final.to_dict()['time_us']) == r['end_us']
        cfg = s.resolve_kernel(s.KERNEL).configuration({'seed': r['seed']}).to_dict()
        assert r['config'] == cfg == final.to_dict()['config']
        ctl = s.read(folder / 'controller-initial.json')
        events = s.read(folder / 'events.json.gz')
        received = [e['payload'] for e in events if e['kind'] == 'stimulus']
        assert received == [x['stimulus'] for x in ctl['rows']]
        for event in events:
            assert r['begin_us'] <= int(event['time_us']) <= r['end_us']
        assert not s.cross_edges(final.to_dict(), s.mapping(r['seed']))
        assert s.read(folder / 'controller-final.json')['next_input'] == len(received)
        if folder.name != 'main':
            if folder.name in ('cue', 'no-cue'):
                parent = s.state_read(folder.parent / 'main/final.tmind')
                assert start.digest == parent.digest
            else:
                intervention = s.read(folder.parent / (folder.name + '-intervention.json'))
                assert start.digest == intervention['state_sha256']
        checks.append({'path': folder.relative_to(s.WORK).as_posix(), 'inputs': len(received),
                       'initial': start.digest, 'final': final.digest})

    max_decimal_error = 0.
    for seed, dose in itertools.product(s.SEEDS, s.DOSES):
        base = s.WORK / 'science' / str(seed) / f'{dose:g}'
        m, response, curves, weights = {}, {}, {}, {}
        for p in s.PATTERNS:
            folder = base / p
            mt, mv = load(folder / 'main')
            keep = (mt >= 4_000_000) & (mt <= 5_000_000)
            m[p] = (mt[keep], mv[keep])
            t, cue = load(folder / 'cue')
            nt, null = load(folder / 'no-cue')
            st, sham = load(folder / 'sham')
            assert np.array_equal(t, nt) and np.array_equal(t, st)
            err = float(np.max(np.abs(cue-sham)))
            shams.append({'seed': seed, 'dose': dose, 'pattern': p, 'max_error': err, 'passed': err <= 1e-10})
            curves[p] = {'cue': cue, 'no-cue': null, 'sham': sham}
            response[p] = cue-null
            graph = s.read(folder / 'main/graph-final.json')
            weights[p] = {(r['source'], r['target']): r['weight'] for r in graph['edges']}
            qc = s.read(folder / 'quiet-check.json')
            task = {s.mapping(seed)[key] for key in ('x1', 'x2', 'x3')}
            act = max(r['activation'] for r in qc['observation']['nodes'] if r['id'] in task)
            # In this apparatus no external input remains queued at 34 s.
            assert not qc['queue']
            cfg = s.engine(state=s.state_read(folder / 'main/final.tmind')).config
            available, fast = [], []
            for edge in graph['edges']:
                raw = edge.get('short_term')
                if raw:
                    state = ShortTermState(**(raw | {'time_us': int(raw['time_us'])})).recovered(34_000_000, cfg.short_term())
                    available.append(state.available)
                raw = edge.get('fast')
                if raw:
                    fast.append(FastTrace(**(raw | {'time_us': int(raw['time_us'])})).projected(34_000_000, cfg.fast_trace()))
            quiet.append({'seed': seed, 'dose': dose, 'pattern': p, 'activation_max': act,
                          'null_task_activation_max': float(np.max(np.abs(null[:, :3, 0]))),
                          'queue_empty': True, 'resources_min': min(available, default=1.),
                          'fast_max': max(fast, default=0.), 'passed': act == 0.})

        for a, b in itertools.combinations(s.PATTERNS, 2):
            mt, ma = m[a]
            assert np.array_equal(mt, m[b][0])
            im = distance(ma, m[b][1], mt, (0, 1, 2))
            late = distance(response[a], response[b], t, (1, 2))
            wd = max(abs(weights[a].get(k, 0.) - weights[b].get(k, 0.)) for k in weights[a].keys() | weights[b].keys())
            effects, donor_movements = [], []
            for recipient, donor in ((a, b), (b, a)):
                xt, transplant = load(base / recipient / ('weights-from-' + donor))
                assert np.array_equal(xt, t)
                effect = distance(transplant, curves[recipient]['sham'], t, (1, 2))
                before = distance(curves[recipient]['sham'], curves[donor]['sham'], t, (1, 2))
                after = distance(transplant, curves[donor]['sham'], t, (1, 2))
                effects.append(effect)
                donor_movements.append(1-after/before if before > 0 else None)
                max_decimal_error = max(max_decimal_error, abs(effect-decimal_distance(
                    transplant, curves[recipient]['sham'], t, (1, 2))))
            max_decimal_error = max(max_decimal_error, abs(im-decimal_distance(ma, m[b][1], mt, (0, 1, 2))),
                                     abs(late-decimal_distance(response[a], response[b], t, (1, 2))))
            validity = all(x['passed'] for x in quiet if x['seed'] == seed and x['dose'] == dose)
            validity &= all(x['passed'] for x in shams if x['seed'] == seed and x['dose'] == dose)
            rows.append({'seed': seed, 'intensity': dose, 'first': a, 'second': b,
                         'question': 'Q2' if a == 'short' else 'Q1',
                         'immediate_activity_distance': im, 'immediate_pass': im > 1e-6,
                         'weight_max_difference': wd, 'weight_retention_pass': wd > 1e-6,
                         'delayed_response_distance': late, 'delayed_expression_pass': late > 1e-6,
                         'first_receives_second_effect': effects[0], 'second_receives_first_effect': effects[1],
                         'first_toward_donor_fraction': donor_movements[0], 'second_toward_donor_fraction': donor_movements[1],
                         'weight_causality_pass': min(effects) > 1e-6, 'valid': bool(validity),
                         'Q3_complete_pass': bool(validity and wd > 1e-6 and late > 1e-6 and min(effects) > 1e-6)})

    groups = []
    for dose, (a, b) in itertools.product(s.DOSES, itertools.combinations(s.PATTERNS, 2)):
        sub = [r for r in rows if r['intensity'] == dose and r['first'] == a and r['second'] == b]
        groups.append({'intensity': dose, 'pair': [a, b], 'blocks': len(sub),
                       **{key: sum(r[key] for r in sub) for key in ('immediate_pass', 'weight_retention_pass',
                         'delayed_expression_pass', 'weight_causality_pass', 'Q3_complete_pass')},
                       'immediate_range': [min(r['immediate_activity_distance'] for r in sub), max(r['immediate_activity_distance'] for r in sub)],
                       'delayed_range': [min(r['delayed_response_distance'] for r in sub), max(r['delayed_response_distance'] for r in sub)],
                       'weight_range': [min(r['weight_max_difference'] for r in sub), max(r['weight_max_difference'] for r in sub)]})
    result = {'tag': s.TAG, 'groups': groups, 'rows': rows, 'quiet': quiet, 'shams': shams,
              'audit': {'passed': all(r['valid'] for r in rows), 'stages': len(checks),
                        'inputs_verified': sum(r['inputs'] for r in checks), 'production_frozen': True,
                        'sham_max_error': max(r['max_error'] for r in shams),
                        'decimal_integration_max_error': max_decimal_error,
                        'all_null_task_activation_zero': all(r['null_task_activation_max'] == 0. for r in quiet)}}
    assert max_decimal_error < 1e-12
    s.save(s.WORK / 'analysis-v1/audit-details.json', checks)
    s.save(s.WORK / 'analysis-v1/analysis.json', result)
    s.save(s.HERE / 'summary.json', result)
    with (s.HERE / 'comparisons.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(json.dumps({'groups': groups, 'audit': result['audit']}, ensure_ascii=False, indent=2))
    return result


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Microsoft YaHei', 'DejaVu Sans'],
                                'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 10})
    target = s.HERE / 'figures'; target.mkdir(exist_ok=True)
    seed = s.SEEDS[0]
    labels = {'zh': ('连续呈现', '中断0.2秒', '中断1秒'), 'en': ('Continuous', '0.2 s gap', '1 s gap')}
    colors = ('#226a9a', '#df8424', '#008672')
    for lang in ('zh', 'en'):
        fig, axes = plt.subplots(2, 2, figsize=(10, 6.6), layout='constrained')
        for col, dose in enumerate(s.DOSES):
            for p, label, color in zip(s.PATTERNS, labels[lang], colors):
                folder = s.WORK / 'science' / str(seed) / f'{dose:g}' / p
                t, v = load(folder / 'main'); keep = (t >= 4_000_000) & (t <= 5_000_000)
                axes[0, col].plot((t[keep]-4_000_000)/1e6, v[keep, :3, 0].sum(axis=1), label=label, color=color, lw=1.8)
                t, v = load(folder / 'cue'); _, null = load(folder / 'no-cue')
                axes[1, col].plot((t-34_000_000)/1e6, (v-null)[:, 1:3, 0].sum(axis=1), label=label, color=color, lw=1.8)
            axes[0, col].set_title(('刺激强度' if lang == 'zh' else 'Input intensity') + f' = {dose:g}')
            axes[0, col].set_xlabel('呈现结束后的内部时间（秒）' if lang == 'zh' else 'Internal seconds after presentation')
            axes[1, col].set_xlabel('30秒后给予相同测试刺激，随后时间（秒）' if lang == 'zh' else 'Seconds after identical cue at 30 s delay')
            for row in (0, 1):
                axes[row, col].set_ylim(bottom=0); axes[row, col].grid(alpha=.18)
            axes[1, col].set_ylim(0, .019)
            axes[0, col].legend(frameon=False, fontsize=9)
        axes[0, 0].set_ylabel('三个X节点的激活之和' if lang == 'zh' else 'Summed activation of the three X nodes')
        axes[1, 0].set_ylabel('两个未直接刺激节点的净激活之和' if lang == 'zh' else 'Net activation of the two uncued X nodes')
        fig.suptitle('相同输入内容与总量，不同呈现间隔' if lang == 'zh' else 'Identical input content and dose, different temporal spacing', fontsize=13)
        fig.savefig(target / f'responses.{lang}.png', dpi=220)
        fig.savefig(target / f'responses.{lang}.svg')
        plt.close(fig)


if __name__ == '__main__':
    analyze()
    figures()
