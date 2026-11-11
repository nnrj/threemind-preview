# Audit v2: decode serialized integer-string timestamps; no endpoint or data change.
"""File-only complete-state and path arithmetic audit; never creates an engine."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from safetensors.torch import load_file

import pilot_m2 as m
from m4_instrument import digest, tensor_tree


def stored_canonical(folder):
    receipt = m.read(folder/'complete.json')
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}-{'complete.json'}
    assert actual == set(receipt['files'])
    for name, sha in receipt['files'].items():
        p = (folder/name).resolve()
        assert p.is_relative_to(folder.resolve()) and hashlib.sha256(p.read_bytes()).hexdigest() == sha
    result = json.loads(gzip.decompress((folder/'system.json.gz').read_bytes()))
    for name in ('motor', 'words'):
        metadata = m.read(folder/name/'manifest.json')
        learning = torch.load(folder/name/'learning.pt', map_location='cpu', weights_only=True)
        result[name] = {'weights': tensor_tree(load_file(str(folder/name/'model.safetensors'))),
                        'optimizer': tensor_tree(learning['optimizer']), 'rng': tensor_tree(learning['rng']),
                        'computed': metadata['computed_updates'], 'committed': metadata['committed_updates'],
                        'training': False, 'identity': metadata['identity'], 'seed': metadata['seed']}
    assert digest(result) == receipt['canonical_sha256']
    assert result['identity'] == receipt['identity']
    assert int(result['session']['core']['time_us']) == receipt['time_us']
    return result, receipt


def audit(work):
    status = m.read(work/'status.json')
    assert status['state'] == 'awaiting-analysis' and status['completed'] == 4
    assert not any((work/p).exists() for p in ('STOP', 'in-flight.json'))
    m.frozen_check(work)
    birth, _ = stored_canonical(work/'birth')
    assert birth['cursor'] == 0 and not birth['session']['core']['nodes'] and not birth['session']['core']['edges']
    assert int(birth['session']['core']['time_us']) == 0
    hashes, paths, trace_hashes = [], [], []
    for mode in ('plain', 'observed', 'restored', 'paused'):
        folder = work/'paths'/mode
        middle, middle_receipt = stored_canonical(folder/'middle')
        final, receipt = stored_canonical(folder/'final')
        rows = json.loads(gzip.decompress((folder/'trajectory.json.gz').read_bytes()))
        result = m.read(folder/'result.json')
        checks = m.read(folder/'observer-checks.json')
        assert len(rows) == 60 and middle_receipt['time_us'] == 1_500_000 and receipt['time_us'] == 3_000_000
        assert middle['cursor'] == 30 and final['cursor'] == 60
        assert middle['motor']['computed'] == middle['motor']['committed'] == 2
        assert final['motor']['computed'] == final['motor']['committed'] == 4
        assert final['words']['computed'] == final['words']['committed'] == 0
        assert len(middle['corpus']) == 1 and len(final['corpus']) == 2
        assert len(checks) == (60 if mode == 'observed' else 0)
        assert all(c['equal'] and c['before'] == c['after'] for c in checks)
        assert [int(r['stimulus']['time_us']) for r in rows] == list(range(0, 3_000_000, 50_000))
        expected = (((.20, -.10), (0., 0.)), ((0., 0.), (.20, .10)), ((-.15, .12), (-.15, .18)))
        for i, row in enumerate(rows):
            eye, hand = expected[i//20]
            assert row['eye_action'] == list(eye) and row['hand_action'] == list(hand)
        transitions = result['body_transitions']
        assert [t['time_us'] for t in transitions] == [0, 1_000_000, 2_000_000, 3_000_000]
        moves = [{'eye': float(np.linalg.norm(np.subtract(b['eye'], p['eye']))),
                  'hand': float(np.linalg.norm(np.subtract(b['hand'], p['hand'])))}
                 for p, b in zip(transitions, transitions[1:])]
        assert moves == result['displacements']
        body_pass = moves[0]['eye'] > 1e-8 and moves[1]['hand'] > 1e-8 and moves[2]['eye'] > 1e-8 and moves[2]['hand'] > 1e-8
        assert body_pass == result['command_reached_body']
        assert result['canonical_sha256'] == receipt['canonical_sha256']
        hashes.append(receipt['canonical_sha256'])
        trace_hashes.append(digest(rows))
        paths.append({'mode': mode, 'canonical_sha256': hashes[-1], 'trajectory_sha256': trace_hashes[-1],
                      'physical_commands_reached_body': body_pass, 'displacements': moves,
                      'nodes': len(final['session']['core']['nodes']), 'edges': len(final['session']['core']['edges']),
                      'wall_seconds': result['wall_seconds']})
    passed = len(set(hashes)) == len(set(trace_hashes)) == 1 and all(x['physical_commands_reached_body'] for x in paths)
    assert passed == m.read(work/'apparatus.json')['passed']
    report = {'schema': 'threemind.m4-instrument-file-audit/1', 'passed': True, 'apparatus_passed': passed,
              'whole_states': 9, 'recorded_ticks': 240, 'observer_checks': 60, 'scientific_origins': 0,
              'Core_loaded': False, 'simulation_advanced': False, 'paths': paths}
    m.original(work/'audit-v1.json', report)
    m.original(work/'analysis-v1.json', {'schema': 'threemind.m4-instrument-analysis/1', 'valid': True,
        'verdict': 'PASS' if passed else 'FAIL', 'paths': paths, 'scientific_origins': 0,
        'target': 'Complete physical apparatus continuity and observation invariance',
        'criteria': {'whole_final_equal': len(set(hashes)) == 1, 'all_raw_trajectories_equal': len(set(trace_hashes)) == 1,
                     'observations_unchanged': True, 'time_and_learning_counts_exact': True,
                     'commanded_body_motion': all(x['physical_commands_reached_body'] for x in paths)}})
    print(json.dumps(report))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    audit(p.parse_args().work.resolve())
