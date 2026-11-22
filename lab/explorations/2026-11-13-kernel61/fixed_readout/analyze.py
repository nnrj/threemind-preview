"""Read-only temporal/endpoint M5 scoring; historical goals are scored separately."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import support as s
from audit import disk_allocation
from audit_readout import audit
from m5_analyze import summarize_unit


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def endpoint_view(result):
    def convert(value):
        if isinstance(value, list): return [convert(v) for v in value]
        if not isinstance(value, dict): return value
        out = {k: convert(v) for k, v in value.items()}
        for key in ('response', 'port_response', 'features', 'port_features', 'readers_before', 'readers_after'):
            if 'endpoint_' + key in out: out[key] = copy.deepcopy(out['endpoint_' + key])
        return out
    return convert(result)


def goals(units):
    out = {}
    for head in ('full', 'ports'):
        for target in ('first_expression', 'causal_attribution', 'continued_reader_gain'):
            count = sum(u['tests'][head][target] for u in units)
            valid = all(u['integrity_valid'] and (target != 'causal_attribution' or u['matching_valid']) for u in units)
            out[head + '-' + target] = {'passed_origins': count, 'n': 8,
                                      'verdict': 'INVALID' if not valid else 'PASS' if count >= 6 else 'FAIL'}
    count = sum(u['representation_gain'] for u in units)
    out['output-port-representation-gain'] = {'passed_origins': count, 'n': 8,
                                             'verdict': 'PASS' if count >= 6 else 'FAIL'}
    return out


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert read(work / 'summary.json')['origins'] == 8
    temporal, endpoint = [], []
    states = 0; correction_rounds = []
    for i in range(8):
        folder = work / 'units' / f'o{i}'
        r = read(folder / 'result.json')
        assert r['origin'] == i and r['seed'] == 1056100 + i
        temporal.append(summarize_unit(r))
        endpoint.append(summarize_unit(endpoint_view(r)))
        correction_rounds.append(len(r['calibration']['corrections']))
        for path in folder.glob('*.json.gz'):
            whole = read(path)
            assert whole['schema'] == 'threemind.m5-process61-whole/1'
            assert whole['core']['dynamics'] == 'threemind.continuous-memory/6.1'
            assert whole['seed'] == 1056100 + i and whole['core']['config']['prune_weight'] == .008
            assert int(whole['core']['time_us']) == whole['time_us']
            states += 1
        print(json.dumps({'scored_origins': i + 1, 'total': 8}), flush=True)
    assert states == 2024
    checked = audit(work)
    assert checked['passed']
    main, legacy = goals(temporal), goals(endpoint)
    valid = all(u['valid'] for u in temporal + endpoint)
    keys = ('ports-first_expression', 'ports-causal_attribution')
    process_ok = all(main[k]['verdict'] == 'PASS' for k in keys)
    endpoint_ok = all(legacy[k]['verdict'] == 'PASS' for k in keys)
    stop = not valid or (not process_ok and not endpoint_ok)
    files = [p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    result = {'schema': 'threemind.r51k-analysis/1', 'kernel': '6.1', 'independent_origins': 8,
              'valid': valid, 'primary_condition': 'temporal', 'temporal_goals': main, 'endpoint_goals': legacy,
              'temporal_units': temporal, 'endpoint_units': endpoint, 'old_correction_rounds': correction_rounds,
              'scientific_stop': stop, 'timing': read(work / 'summary.json'),
              'resources': read(work / 'resource-summary.json'),
              'storage': {'logical_bytes': sum(p.stat().st_size for p in files),
                          'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}}
    checked.update(complete_states=states, scientific_stop=stop, Core_engines_loaded=0)
    s.base.original(work / 'analysis.json', result); s.base.original(work / 'audit.json', checked)
    print(json.dumps({k: v for k, v in result.items() if k not in ('temporal_units', 'endpoint_units')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    analyze(p.parse_args().work.resolve())
