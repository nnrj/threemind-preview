"""Historical X3 rules applied to new saved 6.1 data; no subject engines loaded."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE.parent), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import support as s
from audit import disk_allocation
from closure_analyze import x3
from m3_confirm_audit import check_probe, check_world, criteria
from closure_audit import replay_rnn
from pilot_m1 import differences

KINDS = ('reactive', 'finite-state', 'hebbian', 'fixed-rnn-reader', 'threemind')
ARMS = ('intact', 'sham', 'target', 'matched', 'restored', 'all')


def read(p):
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix == '.gz' else raw)


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert read(work / 'summary.json')['systems'] == 40
    results = [read(p) for p in sorted((work / 'units').glob('*/result.json'))]
    assert len(results) == 40 and all(r['valid'] for r in results)
    result = x3(results)
    for value in result['systems'].values():
        assert len(value['origins']) == 8
        value['joint_count'] = sum(all(r['passes']) for r in value['origins'])
        value['denominator'] = 8
    matrix = {(kind, r['origin']): r['passes'] for kind, v in result['systems'].items() for r in v['origins']}
    counts = {'systems': 0, 'probes': 0, 'complete_states': 0, 'loop_groups': 0, 'rnn_teaching_replays': 0}
    maximum_rnn_residual = 0.
    core_matches = []
    for r in results:
        kind, origin = r['kind'], r['origin']
        sub = work / 'units' / f'o{origin}-{kind}'
        for p in sub.glob('*.json.gz'):
            whole = read(p)
            assert whole['schema'] == 'threemind.criteria61-whole/1'
            assert whole['kind'] == kind and whole['seed'] == 1036100 + origin
            if kind == 'threemind':
                assert whole['model']['dynamics'] == 'threemind.continuous-memory/6.1'
                assert int(whole['model']['time_us']) == whole['time_us']
                assert all(n['id'] == n['channel'] for n in whole['model']['nodes'])
            counts['complete_states'] += 1
        for h in r['histories']:
            prefix = f'h{h["history"]}'
            parent = read(sub / f'{prefix}-parent.json.gz')
            selected = read(sub / f'{prefix}-selection.json')
            if kind == 'fixed-rnn-reader':
                assert replay_rnn(parent) == h['selection'] == selected and selected['passed']
                maximum_rnn_residual = max(maximum_rnn_residual, *selected['standardized_residual'])
                counts['rnn_teaching_replays'] += 1
            elif kind == 'threemind':
                assert selected == h['selection'] and selected['passed']
                core_matches.append(selected)
            for arm in ARMS:
                initial = read(sub / f'{prefix}-{arm}-initial.json.gz')
                receipt = read(sub / f'{prefix}-{arm}-intervention.json')
                if arm in ('intact', 'sham', 'restored'):
                    left, right = copy.deepcopy(parent), copy.deepcopy(initial)
                    left['branch'] = right['branch'] = None
                    assert left == right
                else:
                    field = {'reactive': None, 'finite-state': 'model.memory', 'hebbian': 'model.W',
                             'fixed-rnn-reader': 'model.R' if arm == 'all' else 'model.h',
                             'threemind': 'model.silenced_edges'}[kind]
                    changed = differences(parent, initial)
                    assert changed == receipt['changed_paths'] and set(changed) <= {'branch', field}
                for cue in ('X', 'none'):
                    whole = read(sub / f'{prefix}-{arm}-{cue}-final.json.gz')
                    assert whole['branch']['parent_sha256'] == s.base.digest(initial)
                    check_probe(initial, whole, h['cells'][arm + '-' + cue], '' if cue == 'none' else cue)
                    counts['probes'] += 1
            for name, probe in h['temporal'].items():
                arm, sequence = name.split('-')
                initial = read(sub / f'{prefix}-{arm}-initial.json.gz')
                check_probe(initial, read(sub / f'{prefix}-temporal-{name}.json.gz'), probe,
                            '' if sequence[0] == '0' else sequence[0], None if sequence[1] == '0' else sequence[1])
                counts['probes'] += 1
        for sequence, stages in r['worlds'].items():
            current = read(sub / f'{sequence}-birth.json.gz')
            for j, stage in enumerate(stages, 1):
                live = read(sub / f'{sequence}-stage{j}.json.gz')
                check_world(current, live, stage['world'])
                for cue, probe in stage['diagnostics'].items():
                    whole = read(sub / f'{sequence}-stage{j}-diagnostic-{cue}.json.gz')
                    assert whole['branch']['parent_sha256'] == s.base.digest(live)
                    assert whole['body'] == {'x': .3125, 'v': 0., 'gate': 0}
                    check_probe(live, whole, probe, '' if cue == 'none' else cue)
                    counts['probes'] += 1
                if j == 2:
                    loop = stage['world']['loop_audit']
                    replay = read(sub / f'{sequence}-stage2-replay.json.gz')
                    reverse = read(sub / f'{sequence}-stage2-replay-reversed.json.gz')
                    closed = read(sub / f'{sequence}-stage2-closed-reversed.json.gz')
                    frames = stage['world']['input_frames']
                    check_world(current, replay, loop['replay'], frames)
                    check_world(current, reverse, loop['reversed_replay'], frames)
                    check_world(current, closed, loop['closed_reversed'])
                    assert loop['replay_model_equal'] == (replay['model'] == live['model'])
                    assert loop['reversed_replay_model_equal'] == (replay['model'] == reverse['model'])
                    assert loop['closed_reversal_inputs_differ'] == (loop['closed_reversed']['input_frames'] != frames)
                    assert loop['closed_reversal_model_differs'] == (closed['model'] != live['model'])
                    counts['loop_groups'] += 1
                current = live
        assert criteria(r) == matrix[(kind, origin)]
        counts['systems'] += 1
    assert counts == {'systems': 40, 'probes': 2560, 'complete_states': 4240, 'loop_groups': 160, 'rnn_teaching_replays': 16}
    result['scientific_stop'] = result['systems']['threemind']['overall'] != 'PASS' or bool(result['all_four_comparator_passes'])
    result['kernel'] = '6.1'
    result['core_matching'] = core_matches
    result['independent_origins'] = 8
    files = [p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    result['storage'] = {'logical_bytes': sum(p.stat().st_size for p in files),
                         'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}
    s.base.original(work / 'analysis.json', result)
    audit = {'passed': True, 'counts': counts, 'scientific_stop': result['scientific_stop'],
             'maximum_rnn_matching_residual': maximum_rnn_residual,
             'Core_engines_loaded': 0, 'analysis_sha256': s.sha(work / 'analysis.json'),
             'baseline_replays': 'Read-only numerical verification of saved teaching; no new scientific individual.'}
    s.base.original(work / 'audit.json', audit)
    print(json.dumps({'systems': {k: {f: v[f] for f in ('counts', 'verdicts', 'overall', 'joint_count')} for k, v in result['systems'].items()},
                      'scientific_stop': result['scientific_stop'], 'audit': audit, 'storage': result['storage']}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    analyze(p.parse_args().work.resolve())
