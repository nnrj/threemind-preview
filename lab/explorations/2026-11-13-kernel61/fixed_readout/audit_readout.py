"""Independent arithmetic/file audit of M5 originals; never instantiates a Core."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import math
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT / 'src'), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import numpy as np
import pilot_m2 as m
from pilot_m1 import differences

def projected_weight(edge, clock, cfg):
    # Independent closed-form inverse-logarithmic ratio, using the stored normalized age.
    assert cfg.decay_curve == 'inverse-logarithmic' and not cfg.retention_relaxation_enabled
    age = edge['decay_age']
    later = age + (clock - int(edge['state_us'])) / (1e6 * edge['half_life'])
    return edge['weight'] * (1 + math.log1p(math.expm1(1.) * age)) / (1 + math.log1p(math.expm1(1.) * later))

HEADS = ('reader', 'port_reader', 'endpoint_reader', 'endpoint_port_reader', 'sensory_control')
FIELDS = ('activation', 'inhibition', 'direct', 'associative')
checked_readers = set()

def temporal_features(trajectory):
    return [math.fsum(r[field][channel] for r in trajectory[start:start+50]) / 50
            for start in range(0, 250, 50) for field in FIELDS for channel in range(12)]


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def inferred(reader, features):
    score = sum(w*x/s for w, x, s in zip(reader['weights'], features, reader['scale']))
    return score, int(score > .25)-int(score < -.25)


def reader_check(reader):
    key = m.digest(reader)
    if key in checked_readers: return
    samples = reader['samples']
    assert reader['updates'] == len(samples) and len(samples) in (12, 18, 24, 30)
    dimension = reader['dimension']
    assert dimension in (12, 240)
    x = np.asarray([r['features'] for r in samples]); y = np.asarray([r['label'] for r in samples])
    maxima = abs(x[:12]).max(axis=0)
    scales = np.where(maxima > 1e-6, maxima, 1.)
    assert np.array_equal(scales, reader['scale'])
    z = x/scales
    gram = np.eye(dimension)*.001+z[:12].T@z[:12]
    rhs = z[:12].T@y[:12]
    for start in range(12, len(samples), 6):
        gram += z[start:start+6].T@z[start:start+6]; rhs += z[start:start+6].T@y[start:start+6]
    assert np.allclose(gram, reader['gram'], rtol=1e-12, atol=1e-12)
    assert np.allclose(rhs, reader['rhs'], rtol=1e-12, atol=1e-12)
    assert np.allclose(np.linalg.solve(gram, rhs), reader['weights'], rtol=1e-9, atol=1e-9)
    checked_readers.add(key)


def exam_check(folder, initial, rows, counts):
    previous = load(folder/(initial+'.json.gz'))
    readers = {key: previous[key] for key in HEADS}
    for reader in readers.values(): reader_check(reader)
    for row in rows:
        path = folder/row['checkpoint']['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['checkpoint']['sha256']
        whole = load(path)
        assert row['before_sha256'] == m.digest(previous)
        assert row['start_us'] == previous['time_us']
        assert row['end_us']-row['start_us'] == 1_000_000 and whole['time_us'] == row['end_us']
        assert all(whole[key] == before for key, before in readers.items())
        assert row['reader_sha256'] == m.digest(readers['reader'])
        assert row['port_reader_sha256'] == m.digest(readers['port_reader'])
        assert whole['rows'][-1] == {k: v for k, v in row.items() if k not in ('checkpoint', 'label', 'group')}
        assert len(row['trajectory']) == 250
        assert [r['dt_us'] for r in row['trajectory']] == list(range(1000, 250001, 1000))
        assert np.allclose(row['features'], temporal_features(row['trajectory']), rtol=1e-12, atol=1e-12)
        assert row['endpoint_features'] == row['trajectory'][109]['activation']
        order = sorted(whole['mappings'].values())
        ports = {whole['mappings'][s] for s in 'AB'}
        assert row['port_features'] == [v if order[i % 12] in ports else 0. for i, v in enumerate(row['features'])]
        assert row['endpoint_port_features'] == [v if c in ports else 0. for c, v in zip(order, row['endpoint_features'])]
        cue_channels = {whole['mappings'][s] for s in row['cue']}
        assert row['sensory'] == [row['dose']/len(row['cue']) if c in cue_channels else 0. for c in order]
        for feature, reader, output in [('features', 'reader', 'response'), ('port_features', 'port_reader', 'port_response'),
                                        ('sensory', 'sensory_control', 'sensory_response'),
                                        ('endpoint_features', 'endpoint_reader', 'endpoint_response'),
                                        ('endpoint_port_features', 'endpoint_port_reader', 'endpoint_port_response')]:
            score, answer = inferred(readers[reader], row[feature])
            assert abs(score-row[output]['score']) <= 1e-9 and answer == row[output]['answer']
        new_inputs = whole['inputs'][len(previous['inputs']):]
        assert new_inputs[0] == {'time_us': row['start_us'], 'values': dict.fromkeys(row['cue'], row['dose']/len(row['cue']))}
        assert all(set(e['values']) <= set(row['cue']) | {'K'} for e in new_inputs)
        assert all(e['time_us'] >= row['start_us'] for e in new_inputs)
        assert all(e['values'] == {'K': .2} for e in new_inputs[1:])
        assert len(new_inputs) == 3
        counts['questions'] += 1
        counts['primary_singletons'] += len(row['cue']) == 1
        previous = whole
    return previous


def audit(work):
    assert not (work / "in-flight.json").exists()
    counts = {'origins': 0, 'questions': 0, 'primary_singletons': 0, 'mask_receipts': 0, 'reader_crosses': 0}
    max_residuals = {'weight': 0., 'activity': 0.}
    for folder in sorted((work/'units').glob('o*')):
        result = m.read(folder/'result.json')
        assert result['seed'] == 1056100+result['origin']
        assert [h['history'] for h in result['histories']] == [0, 1]
        baseline_cases = [(r['cue'], r['dose']) for r in result['early']]
        assert len(baseline_cases) == 12 and len(set(baseline_cases)) == 12
        parent = exam_check(folder, 'old-calibrated', result['early'], counts)
        assert parent == load(folder/'parent-before-new-teaching.json.gz')
        for h in result['histories']:
            history = h['history']; cases = h['cases']
            assert set(cases) == {'sham', 'target', 'matched', 'restored', 'plasticity-off'}
            taught = load(folder/f'h{history}-plasticity-True-taught.json.gz')
            for enabled in (True, False):
                start = load(folder/f'h{history}-plasticity-{enabled}-start.json.gz')
                end = load(folder/f'h{history}-plasticity-{enabled}-taught.json.gz')
                assert start['branch']['parent_sha256'] == m.digest(parent)
                assert start['time_us'] == parent['time_us'] and end['time_us']-start['time_us'] == 18_000_000
                assert start['core']['config']['plasticity'] is enabled
                assert start['core']['definition']['config']['plasticity'] is enabled
                assert {k for k in parent if k not in ('core', 'branch') and parent[k] != start[k]} == set()
                assert {k for k in start if k not in ('core', 'time_us', 'inputs') and start[k] != end[k]} == set()
                receipt = cases['sham' if enabled else 'plasticity-off']['configuration']
                changed = set(differences(parent['core'], start['core']))
                assert changed == {p.removeprefix('core.') for p in receipt['changed_paths']}
                assert changed <= {'audit.edge_visits', 'audit.node_visits', 'config.plasticity',
                                   'definition.config.plasticity', 'definition_hash', 'edges', 'nodes', 'timers'}
            for arm, cell in cases.items():
                assert [(r['cue'], r['dose']) for r in cell['rows']] == baseline_cases
                initial = load(folder/f'h{history}-{arm}-initial.json.gz')
                source = taught if arm != 'plasticity-off' else load(folder/f'h{history}-plasticity-False-taught.json.gz')
                assert initial['branch']['parent_sha256'] == m.digest(source)
                assert {k for k in source if k not in ('core', 'branch') and source[k] != initial[k]} == set()
                allowed = {'silenced_edges'} if arm in ('target', 'matched') else set()
                assert {k for k in source['core'] if source['core'][k] != initial['core'][k]} <= allowed
                if arm != 'plasticity-off':
                    assert {k for k in taught['core'] if taught['core'][k] != initial['core'][k]} <= allowed
                    receipt = cell['mask']
                    assert sorted(initial['core']['silenced_edges']) == sorted(receipt['pairs'] if arm in ('target', 'matched') else [])
                    cfg = SimpleNamespace(**taught['core']['config'])
                    nodes = {n['channel']: n['id'] for n in taught['core']['nodes']}
                    weights = {}
                    for name, symbols in (('target', 'XYCD'), ('matched', 'UVZW')):
                        ids = {nodes[taught['mappings'][s]] for s in symbols}
                        outputs = {nodes[taught['mappings'][s]] for s in 'AB'}
                        edges = [e for e in taught['core']['edges'] if e['source'] in ids and e['target'] in outputs]
                        weights[name] = [projected_weight(e, taught['time_us'], cfg) for e in edges]
                        assert len(edges) == 4
                        assert np.allclose(sorted(weights[name]), sorted(receipt['weights'][name]), rtol=1e-10, atol=1e-12)
                        all_edges = taught['core']['edges']
                        degrees = sorted([[sum(e['source'] == n for e in all_edges), sum(e['target'] == n for e in all_edges)]
                                          for edge in edges for n in (edge['source'], edge['target'])])
                        assert degrees == receipt['degrees'][name]
                    assert receipt['degrees']['target'] == receipt['degrees']['matched']
                    delta = abs(np.mean(weights['target'])-np.mean(weights['matched']))
                    assert abs(delta-receipt['weight_mean_residual']) < 1e-12
                    max_residuals['weight'] = max(max_residuals['weight'], float(delta))
                    max_residuals['activity'] = max(max_residuals['activity'], cell['teaching']['old_new_activity_residual'])
                    assert delta <= .05 and cell['teaching']['old_new_activity_residual'] <= .02
                    counts['mask_receipts'] += 1
                for row in cell['rows']:
                    expected = 1 if set(row['cue']) <= set('UV') else -1 if set(row['cue']) <= set('ZW') else (
                               (1 if history == 0 else -1) if set(row['cue']) <= set('XY') else (-1 if history == 0 else 1))
                    assert row['label'] == expected
                exam_check(folder, f'h{history}-{arm}-initial', cell['rows'], counts)
            fixed = exam_check(folder, f'h{history}-fixed-heldout-start', cases['sham']['heldout']['fixed'], counts)
            continued = exam_check(folder, f'h{history}-continued-reader-start', cases['sham']['heldout']['continued'], counts)
            assert fixed['core'] == continued['core'] and fixed['inputs'] == continued['inputs']
            for head, field in [('full', 'reader'), ('ports', 'port_reader')]:
                assert cases['sham']['readers_before'][head] == fixed[field]
                assert cases['sham']['readers_after'][head] == continued[field]
                assert continued[field]['samples'][:len(fixed[field]['samples'])] == fixed[field]['samples']
                reader_check(continued[field]); counts['reader_crosses'] += 1
            for field in ('endpoint_reader', 'endpoint_port_reader'):
                reader_check(fixed[field]); reader_check(continued[field])
                assert continued[field]['samples'][:len(fixed[field]['samples'])] == fixed[field]['samples']
                counts['reader_crosses'] += 1
            assert fixed['sensory_control'] == continued['sensory_control']
        calibration = result['calibration']
        assert len(calibration['initial']) == 12 and len(calibration['corrections']) <= 2
        assert calibration['future_new_labels_used'] is False
        for cycle, correction in enumerate(calibration['corrections']):
            wrong = [r for r in calibration['development'][cycle] if len(r['cue']) == 1 and
                     any(r[key]['answer'] != r['label'] for key in ('response', 'port_response'))]
            assert correction['wrong_cues'] == [r['cue'] for r in wrong]
            assert correction['teacher_groups'] == sorted({'UVA' if set(r['cue']) <= set('UV') else 'ZWB' for r in wrong})
            assert correction['review_wait_s'] == (6, 18)[cycle]
            assert correction['end_us'] - correction['start_us'] == ((6, 18)[cycle] + 6) * 1000000
        counts['origins'] += 1
    assert counts['origins'] == 8
    return {'schema': 'threemind.r51k-m5-process-audit/1', 'passed': True, 'counts': counts, 'max_matching_residuals': max_residuals,
            'method': 'Separate saved-file/arithmetic audit, not an external replication; no Core loaded or advanced.'}


