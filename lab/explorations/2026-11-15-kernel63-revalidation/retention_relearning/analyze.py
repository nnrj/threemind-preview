"""Read-only X2 audit: complete lives, exact inputs and independent arithmetic."""
import argparse
import copy
from decimal import Decimal, localcontext
import gzip
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT/'src')]
import scoring
import support as s
from allocation import disk_allocation

SYMBOLS = tuple('ABXYZWKN')
FIELDS = ('activation', 'inhibition', 'direct', 'associative')


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def teaching_inputs(seed, history, delay, trained=True):
    end = (17+delay)*1_000_000
    events = {t: [{'K': .2}] for t in range(0, end+1, 500_000)}
    if trained:
        groups = ('XYA', 'ZWB') if history == 0 else ('XYB', 'ZWA')
        if seed % 2:
            groups = groups[::-1]
        for round_no in range(16):
            for j, group in enumerate(groups):
                events.setdefault(1_000_000+round_no*1_000_000+j*250_000, []).append(dict.fromkeys(group, .4))
    events.setdefault(17_000_000, []).append({'N': .2})
    return [{'time_us': t, 'values': frame} for t, frames in sorted(events.items()) for frame in frames]


def probe_inputs(start, cue, dose):
    result = [{'time_us': start, 'values': dict.fromkeys(cue, dose/len(cue))}] if cue else []
    return result + [{'time_us': start+t, 'values': {'K': .2}} for t in (500_000, 1_000_000, 1_500_000)]


def arithmetic(rows, probe, four_fields=True):
    start = probe['start_us']
    trace = [r for r in rows if start < r['time_us'] <= start+1_500_000]
    assert [r['time_us']-start for r in trace] == list(range(1000, 1_500_001, 1000))
    assert probe['trace_count'] == len(trace) == 1500
    if four_fields:
        for r in trace:
            assert set(r['activity']) == set(FIELDS)
            assert all(len(r['activity'][f]) == 8 for f in FIELDS)
            assert all(math.isfinite(v) and v >= 0 for f in FIELDS for v in r['activity'][f])
            assert r['response'] == r['activity']['activation'][0]-r['activity']['activation'][1]
    first = trace[109]['response']
    assert probe['first'] == first
    assert probe['choice'] == int(first > 1e-4)-int(first < -1e-4)
    errors = []
    with localcontext() as context:
        context.prec = 45
        for lo, hi, key in ((100_000, 300_000, 'early_integral'), (500_000, 1_500_000, 'late_integral')):
            exact = sum(Decimal(str(r['response']))*Decimal('.001') for r in trace if lo <= r['time_us']-start <= hi)
            errors.append(abs(float(exact)-probe[key]))
        late = sum(Decimal(str(r['response'])) for r in trace if r['time_us']-start >= 500_000)/Decimal(1001)
        errors.append(abs(float(late)-probe['late_mean']))
    assert max(errors) <= 1e-12
    assert probe['peak'] == max(abs(r['response']) for r in trace[:500])
    return max(errors)


class Audit:
    def __init__(self):
        self.files = set()
        self.probes = self.lessons = self.input_frames = 0
        self.error = self.weight_error = 0.

    def state(self, folder, receipt, seed, mode):
        path = folder/receipt['path']
        assert s.sha(path) == receipt['file_receipt']['sha256']
        assert path.stat().st_size == receipt['file_receipt']['byte_count']
        value = read(path)
        assert s.base.digest(value) == receipt['whole_sha256']
        assert value['schema'] == 'threemind.retention63-whole/1'
        assert value['seed'] == seed and value['mode'] == mode
        assert value['time_us'] == receipt['time_us'] == int(value['model']['time_us'])
        assert value['model']['dynamics'] == 'threemind.continuous-memory/6.3'
        assert value['reader'] == {'kind': 'fixed-AB', 'Core_trainable_reader': False}
        assert value['optimizer'] is None
        config = value['model']['config']
        assert config['consolidation_mode'] == ('stability' if mode == 'stability' else 'adaptive-half-life')
        assert config['decay_curve'] == 'inverse-logarithmic' and config['prune_weight'] == .008
        assert not config['retention_growth_enabled'] and not config['retention_relaxation_enabled']
        assert config['inhibition_updates_usage'] and not config['inhibition_bypasses_resources']
        assert config['subthreshold_expiry_enabled'] and not config['resource_precheck_enabled']
        assert all(n['id'] == n['channel'] for n in value['model']['nodes'])
        assert set(value['mappings']) == set(SYMBOLS)
        assert value['model']['life'] != 'dead'
        self.files.add(str(path))
        return value

    def teaching(self, birth, parent, seed, history, delay, trained=True):
        assert birth['time_us'] == 0 and birth['inputs'] == birth['rows'] == []
        assert parent['time_us'] == (17+delay)*1_000_000
        expected = teaching_inputs(seed, history, delay, trained)
        assert parent['inputs'] == expected and parent['rows'] == []
        assert parent['mappings'] == birth['mappings'] and parent['rng'] == birth['rng']
        assert parent['body'] == birth['body'] and parent['branch'] is None
        self.input_frames += len(expected)

    def fork(self, parent, child, label):
        expected = copy.deepcopy(parent)
        expected['branch'] = {'parent_sha256': s.base.digest(parent), 'label': label, 'time_us': parent['time_us']}
        assert child == expected

    def probe(self, initial, final, result, cue, dose):
        assert result['start_us'] == initial['time_us']
        assert final['time_us'] == initial['time_us']+1_500_000
        assert result['final_sha256'] == s.base.digest(final)
        inputs = probe_inputs(initial['time_us'], cue, dose)
        assert final['inputs'] == initial['inputs']+inputs
        assert final['rows'][:len(initial['rows'])] == initial['rows']
        assert len(final['rows'])-len(initial['rows']) == 1500
        assert final['body'] == initial['body'] and final['branch'] == initial['branch']
        assert final['mappings'] == initial['mappings'] and final['rng'] == initial['rng']
        assert final['actuator'] == final['rows'][-1]['response']
        self.error = max(self.error, arithmetic(final['rows'], result))
        self.probes += 1
        self.input_frames += len(inputs)

    def course(self, initial, final, course, history, threshold, calibration=False):
        assert course['threshold'] == threshold
        expected = list(initial['inputs'])
        time_us = initial['time_us']
        last_hash = s.base.digest(initial)
        values, legacy = [], []
        for lesson, row in enumerate(course['lessons'], 1):
            assert row['lesson'] == lesson and row['start_us'] == time_us
            assert row['initial_sha256'] == last_hash
            wait = 2*2**((lesson-1)//4)
            assert row['wait_seconds'] == wait
            expected.append({'time_us': time_us, 'values': dict.fromkeys('XYA' if history == 0 else 'XYB', .4)})
            expected.extend({'time_us': time_us+t, 'values': {'K': .2}} for t in range(500_000, wait*1_000_000+1, 500_000))
            probe = row['result']
            assert probe['start_us'] == time_us+wait*1_000_000
            expected.extend(probe_inputs(probe['start_us'], 'X', .8))
            self.error = max(self.error, arithmetic(final['rows'], probe))
            value = (1 if history == 0 else -1)*probe['early_integral']/.201
            assert value == row['directed_process_mean'] and row['threshold'] == threshold
            assert row['correct'] == (None if threshold is None else value > threshold)
            old_correct = (1 if history == 0 else -1)*probe['first'] > 1e-4
            assert row['legacy_correct'] == old_correct
            assert row['final_sha256'] == probe['final_sha256']
            values.append(value)
            legacy.append(1. if old_correct else 0.)
            time_us = probe['start_us']+1_500_000
            last_hash = row['final_sha256']
        assert 2 <= len(values) <= 16
        assert final['time_us'] == time_us and s.base.digest(final) == last_hash
        assert final['inputs'] == expected
        assert final['rows'][:len(initial['rows'])] == initial['rows']
        assert len(final['rows'])-len(initial['rows']) == 1500*len(values)
        assert final['mappings'] == initial['mappings'] and final['rng'] == initial['rng']
        assert final['body'] == initial['body'] and final['branch'] == initial['branch']
        assert course['legacy_rounds'] == scoring.first_two(legacy, .5)
        attained = 17 if calibration else scoring.first_two(values, threshold)
        assert course['rounds'] == attained and course['censored'] == (attained == 17)
        assert len(values) == (16 if attained == 17 else attained)
        self.lessons += len(values)
        self.probes += len(values)
        self.input_frames += len(expected)-len(initial['inputs'])
        return values

    def edges(self, parent, recorded):
        mapping = parent['mappings']
        # Check the actual target later; caller supplies only one relation's edges.
        for edge in recorded:
            assert edge['source'] in {mapping['X'], mapping['Y']}
            assert edge['target'] in {mapping['A'], mapping['B']}
        present = {(e['source'], e['target']): e for e in parent['model']['edges'] if not e['sleeping']}
        cfg = parent['model']['config']
        for edge in recorded:
            raw = present[edge['source'], edge['target']]
            weight = raw['weight']
            if cfg['consolidation_mode'] != 'stability':
                assert cfg['decay_curve'] == 'inverse-logarithmic' and not cfg['retention_relaxation_enabled']
                age = raw['decay_age']
                elapsed = (parent['time_us']-int(raw['state_us']))/1e6
                new_age = age+elapsed/raw['half_life']
                weight *= (1+math.log1p(math.expm1(1.)*age))/(1+math.log1p(math.expm1(1.)*new_age))
            error = abs(weight-edge['weight'])
            assert error <= 1e-12
            self.weight_error = max(self.weight_error, error)


def analyze(work):
    assert not any((work/n).exists() for n in ('STOP', 'in-flight.json', 'analysis.json', 'audit.json'))
    assert read(work/'summary.json')['configuration_units'] == 64
    assert read(work/'registration.json')['pending'] == 0
    frozen = read(work/'frozen.json')
    for rel, sha in frozen['sources'].items() | frozen['production_sources'].items():
        assert s.sha(ROOT/rel) == sha, rel
    seal = read(work/'formal-freeze.json')
    assert s.sha(work/'calibration.json') == seal['calibration_sha256']
    assert s.sha(work/'budget.json') == seal['budget_sha256']
    calibration = read(work/'calibration.json')
    assert scoring.calibrate(calibration['rows']) == calibration['selections']
    audit = Audit()
    for r in calibration['rows']:
        seed, mode, history = r['seed'], r['mode'], r['history']
        folder = work/'calibration'/f'{mode}-s{seed}-h{history}'
        assert read(folder/'result.json') == r
        birth, initial, final = [audit.state(folder, r[k], seed, mode) for k in ('birth','initial','final')]
        audit.teaching(birth, initial, seed, history, 30, False)
        assert audit.course(initial, final, r['course'], history, None, True) == r['values']
    units = []
    for case in read(work/'cases.json'):
        folder = work/'units'/case['key']
        r = read(folder/'result.json')
        assert all(r[k] == v for k, v in case.items()) and r['valid']
        seed, mode, delay = r['seed'], r['mode'], r['delay']
        assert seed == 1026100+100*delay+r['origin']
        assert [h['history'] for h in r['histories']] == [0,1]
        for h in r['histories']:
            history = h['history']
            load = lambda receipt: audit.state(folder, receipt, seed, mode)
            birth, parent = load(h['birth']), load(h['parent'])
            audit.teaching(birth, parent, seed, history, delay)
            target = parent['mappings']['A' if history == 0 else 'B']
            stored = [e for e in parent['model']['edges']
                      if e['source'] in {parent['mappings'][s] for s in 'XY'} and e['target'] == target]
            assert stored == h['stored_target_edges']
            assert h['sleeping_target_edges'] == sum(e['sleeping'] for e in stored)
            keys = {(e['source'], e['target']) for e in parent['model']['edges'] if not e['sleeping']
                    and e['source'] in {parent['mappings'][s] for s in 'XY'} and e['target'] == target}
            assert keys == {(e['source'], e['target']) for e in h['target_edges']}
            audit.edges(parent, h['target_edges'])
            for name, cue, dose in (('none','',0.),('weak','X',.4),('strong','X',.8),('joint','XY',.8)):
                result = h['tests'][name]
                initial, final = load(result['initial']), load(result['final'])
                audit.fork(parent, initial, name)
                audit.probe(initial, final, result, cue, dose)
            naive_birth, naive = load(h['naive_birth']), load(h['naive_initial'])
            audit.teaching(naive_birth, naive, seed, history, delay, False)
            assert naive_birth == birth
            selection = calibration['selections'][mode]
            if selection['valid']:
                trained, untrained = h['relearning'], h['untrained']
                initial, final = load(trained['initial']), load(trained['final'])
                audit.fork(parent, initial, 'relearning')
                audit.course(initial, final, trained, history, selection['threshold'])
                assert load(untrained['initial']) == naive
                audit.course(naive, load(untrained['final']), untrained, history, selection['threshold'])
            else:
                assert h['relearning'] is h['untrained'] is None
        units.append(r)
        print(json.dumps({'audited_units': len(units), 'total':64}), flush=True)
    result = scoring.evaluate(units, calibration['selections'])
    assert len(units) == 64 and len({u['seed'] for u in units}) == 32
    assert audit.probes-audit.lessons == 512
    files = [p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    result.update(schema='threemind.r63u-analysis/1', kernel='6.3', calibration=calibration['selections'],
                  timing=read(work/'summary.json'), resources=read(work/'resource-summary.json'),
                  storage={'logical_bytes':sum(p.stat().st_size for p in files),
                           'allocated_bytes':sum(disk_allocation(p)['allocated_bytes'] for p in files)})
    checked = {'passed':True, 'Core_engines_loaded':0, 'states':len(audit.files), 'probes':audit.probes,
               'course_lessons':audit.lessons, 'input_frames':audit.input_frames,
               'maximum_decimal_error':audit.error, 'maximum_weight_projection_error':audit.weight_error,
               'intermediate_course_check':'input/observation continuity and chained whole-state hashes; initial and final complete states retained',
               'scientific_stop':result['scientific_stop']}
    s.base.original(work/'analysis.json', result)
    s.base.original(work/'audit.json', checked)
    print(json.dumps(checked), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,required=True)
    analyze(parser.parse_args().work.resolve())
