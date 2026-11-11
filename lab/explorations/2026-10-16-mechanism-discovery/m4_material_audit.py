"""Independent saved-file checks; no subject creation or reconstruction."""
import argparse
from collections import Counter
import gzip
import hashlib
from itertools import groupby
import json
import math
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def audit(work):
    manifest, result = read(work/'materials.json'), read(work/'analysis-v1.json')
    source = Path(manifest['source_root'])
    assert sha(work/'materials.json') == result['materials_sha256']
    assert len(manifest['clips']) == len(result['rows']) == 192
    for relative, item in manifest['members'].items():
        path = source/relative
        assert sha(path) == item['sha256'] and path.stat().st_size == item['bytes']
    keyed = {r['key']: r for r in result['rows']}
    moves, waits, subset = 0, 0, []
    for item in manifest['clips']:
        row = keyed[item['key']]; unit = read(source/item['unit'])
        assert row['new_move_decisions'] == unit['move_decisions']
        assert row['new_wait_decisions'] == unit['wait_decisions']
        assert unit['move_decisions']+unit['wait_decisions'] == unit['new_decisions'] == 8
        moves += unit['move_decisions']; waits += unit['wait_decisions']
        # Fixed first/last questions of every stage, not selected on motion or success.
        if Path(item['clip']).name not in ('000000.json.gz', '000023.json.gz'): continue
        with gzip.open(source/item['clip'], 'rt', encoding='utf-8') as f: clip = json.load(f)
        assert len(clip['process']) == row['frames'] == 120
        assert all(not f['assistance'] for f in clip['process'])
        for eye, hand in manifest['thresholds']:
            labels = []
            for frame in clip['process']:
                ob = frame['observation']; v = ob['pointer']
                eye_active = sum(x*x for x in ob['eye_velocity_rad_s']) >= eye*eye
                hand_active = v['vx']**2+v['vy']**2 >= hand*hand
                labels.append(('neither', 'hand-only', 'eye-only', 'joint')[2*eye_active+hand_active])
            measured = row['strata'][f'{eye:g}/{hand:g}']
            assert dict(Counter(labels)) == measured['frames']
            lengths = {}
            for label, group in groupby(labels):
                count = sum(1 for _ in group)
                lengths.setdefault(label, [])
                if count >= 6: lengths[label].append(count)
            assert lengths == measured['qualified_runs']
        subset.append(item['key'])
    assert len(subset) == 16 and moves == result['new_move_decisions'] and waits == result['new_wait_decisions']
    assert result['frames'] == 192*120 and result['independent_individuals'] == 1
    assert (source/'STOP').is_file() and not (source/'subject/in-flight.json').exists()
    report = {'schema': 'threemind.m4-material-audit/1', 'passed': True,
              'source_members_rehashed': len(manifest['members']), 'all_units_recounted': 192,
              'independent_velocity_recount': subset, 'threshold_pairs_recounted': 9,
              'Core_engines_loaded': 0, 'source_files_modified': 0,
              'method': 'Executing-assistant independent file/arithmetic audit; not external replication.'}
    with (work/'audit-v1.json').open('x', encoding='utf-8') as f: json.dump(report, f, indent=2)
    print(json.dumps(report))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    audit(p.parse_args().work)
