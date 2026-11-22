"""Independent read-only arithmetic check; project stored edge weights to one time."""
import argparse
import gzip
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parents[3] / 'src')]
import support as s
from threemind_runtime import ArtifactCodec
from threemind_kernels.decay60 import decay_value


def verify(work):
    records = {}
    weights = {}
    errors = []
    for p in sorted((work / 'cases').glob('*/result.json')):
        r = json.loads(p.read_bytes())
        image = ArtifactCodec.decode(p.with_name('final.tmind').read_bytes())
        assert image.digest == r['final_sha256']
        doc = image.to_dict()
        cfg = SimpleNamespace(**doc['config'])
        assert cfg.consolidation_mode == 'adaptive-half-life' and cfg.plasticity
        now = int(doc['time_us'])
        edges = {}
        for e in doc['edges']:
            value, _, _ = decay_value(e['weight'], e['decay_age'], e['half_life'],
                                      (now - int(e['state_us'])) / 1e6, cfg)
            edges[e['source'], e['target']] = value
        tr = json.loads(gzip.decompress(p.with_name('trajectory.json.gz').read_bytes()))
        metric = tr['points'][-1]['metrics']
        observed = (metric['mean_weight'] or 0) * metric['edges']
        err = abs(sum(edges.values()) - observed)
        assert err < 1e-9, (p.parent.name, err)
        errors.append(err)
        weights[p.parent.name] = edges
        records[p.parent.name] = r
    assert len(records) == 264
    same_time_order = []
    strength = []
    retention = []
    for seed in (93001, 93002):
        for preset in ('ordinary', 'facilitation'):
            prefix = f'{seed}-{preset}'
            strength.append({'seed': seed, 'preset': preset, **{
                c: sum(weights[prefix + '-intensity-none-' + c].values())
                for c in ('none', 'single4', 'repeated1')}, **{
                'equal_drive_' + str(c): sum(weights[prefix + '-equal-drive-none-' + str(c)].values())
                for c in (1, 4)}})
            for template in ('inertial-cart', 'gravity-pendulum'):
                a = weights[prefix + f'-physical-{template}-complete']
                b = weights[prefix + f'-physical-{template}-shuffled']
                same_time_order.append({'seed': seed, 'preset': preset, 'template': template,
                    'weight_l1_difference': math.fsum(abs(a.get(k, 0) - b.get(k, 0)) for k in a.keys() | b.keys()),
                    'complete_sum': math.fsum(a.values()), 'shuffled_sum': math.fsum(b.values())})
            a = weights[prefix + '-retention']
            weak = [v for (i, j), v in a.items() if i not in (1001, 1002) and j not in (1001, 1002)]
            strong = [v for (i, j), v in a.items() if i in (1001, 1002) and j in (1001, 1002)]
            assert len(weak) == 96 and len(strong) == 2
            retention.append({'seed': seed, 'preset': preset, 'weak_min': min(weak), 'weak_max': max(weak),
                              'strong_min': min(strong), 'strong_max': max(strong)})
    result = {'passed': True, 'states_checked': 264, 'native_metric_max_abs_error': max(errors),
              'quantity': 'base weights analytically projected to each recorded endpoint; no instance loaded or advanced',
              'order': same_time_order, 'strength': strength, 'retention': retention,
              'note': 'analysis.json and result.json weight sums use stored last-update values. This separate check supplies common-time values without changing originals.'}
    s.base.original(work / 'arithmetic-verification.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    verify(p.parse_args().work.resolve())
