"""Read-only arithmetic and saved-state audit. Never creates or advances a Core."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics as st

from threemind_runtime import ArtifactCodec

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile(chunk):
    return {r['id']: r for r in chunk['profile']['rows']}


def audit(work):
    assert not list(work.rglob('in-flight.json'))
    meta = read(REPO / '.work/kernel60-cost/instrumentation.json')
    for rel, digest in meta['source_files'].items():
        assert sha(REPO / rel) == digest, rel
    for rel, digest in meta['modified_files'].items():
        assert sha(REPO / '.work/kernel60-cost/checkout' / rel) == digest, rel
    assert sha(HERE / 'protocol.md') == meta['protocol_sha256']
    assert sha(HERE / 'prepare.py') == meta['prepare_sha256']
    batches = {kind: read(work / kind / 'results.json') for kind in ('stock', 'instrument')}
    checked = []
    states = {}
    for kind, rows in batches.items():
        frozen = read(work / kind / 'frozen.json')
        assert sha(Path(frozen['module'])) == frozen['module_sha256']
        assert sha(HERE / 'run.py') == frozen['runner_sha256']
        assert sha(HERE / 'protocol.md') == frozen['protocol_sha256']
        for row in rows:
            folder = work / kind / row['key']
            assert read(folder / 'result.json') == row
            for when in ('initial', 'final'):
                path = folder / (when + '.tmind')
                state = ArtifactCodec.decode(path.read_bytes())
                assert state.digest == row[when], (kind, row['key'], when)
                data = state.to_dict()
                assert data['dynamics'] == 'threemind.continuous-memory/' + row['version']
                assert int(data['time_us']) == (0 if when == 'initial' else 10000000)
                assert len(data['nodes']) == len(data['edges']) == row['nodes']
                assert [(n['id'], n['channel']) for n in data['nodes']] == [(i, i) for i in range(row['nodes'])]
                checked.append({'path': path.relative_to(work).as_posix(), 'sha256': sha(path), 'state': state.digest})
                if when == 'final' and kind == 'stock' and row['key'].startswith('r0-') and not row['overrides']:
                    states[row['version']] = data
    assert len(batches['stock']) == 31 and len(batches['instrument']) == 21 and len(checked) == 104
    references = {v: next(r for r in batches['stock'] if r['version'] == v and r['nodes'] == 1024 and not r['overrides']) for v in ('5.1', '6.0')}
    for row in batches['instrument']:
        assert row['initial'] == references[row['version']]['initial']
        assert row['final'] == references[row['version']]['final']

    summaries = read(work / 'summary.json')
    for group in summaries['groups']:
        kind, version, nodes, overrides, level, segmented = group['condition']
        rows = [r for r in batches[kind] if (r['version'], r['nodes'], r['overrides'], r['level'], r['segments']) == (version, nodes, overrides, level, segmented)]
        assert group['n'] == len(rows)
        assert all(r['final'] == group['state'] for r in rows)
        assert st.median(r['wall_s'] for r in rows) == group['wall_s']
        assert st.median(r['cpu_s'] for r in rows) == group['cpu_s']

    coarse, fine, phases = {}, {}, {}
    for version in ('5.1', '6.0'):
        rows = [r for r in batches['instrument'] if r['version'] == version and r['level'] == 1 and not r['segments']]
        p = [profile(r['chunks'][0]) for r in rows]
        coarse[version] = {}
        for idx in (0, 1, 2, 13, 14):
            coarse[version][meta['labels'][str(idx)]] = {
                'calls': [q.get(idx, {}).get('calls', 0) for q in p],
                'median_inclusive_ms': st.median(q.get(idx, {}).get('inclusive_ns', 0) / 1e6 for q in p),
                'median_exclusive_ms': st.median(q.get(idx, {}).get('exclusive_ns', 0) / 1e6 for q in p),
                'median_inclusive_fraction': st.median(q.get(idx, {}).get('inclusive_ns', 0) / q[0]['inclusive_ns'] for q in p),
            }
        for q in p:
            assert sum(v['exclusive_ns'] for k, v in q.items() if k < 40) == q[0]['inclusive_ns']
        if version == '6.0':
            for q in p:
                assert [q[i]['calls'] for i in (40, 42, 43, 44, 45)] == [102400, 102400, 97280, 5120, 2048]
        rows = [r for r in batches['instrument'] if r['version'] == version and r['level'] == 2]
        fine[version] = {}
        for idx, label in meta['labels'].items():
            if int(idx) >= 40:
                continue
            records = [profile(r['chunks'][0]).get(int(idx), {}) for r in rows]
            fine[version][label] = {key: st.median(q.get(key, 0) for q in records) for key in ('calls', 'inclusive_ns', 'exclusive_ns')}
    segmented = [r for r in batches['instrument'] if r['segments']]
    for index, label in enumerate(('0-1s', '1-10s')):
        chunks = [r['chunks'][index] for r in segmented]
        p = [profile(c) for c in chunks]
        phases[label] = {'wall_s': [c['wall_s'] for c in chunks],
                         'median_wall_s': st.median(c['wall_s'] for c in chunks),
                         'counters': {meta['labels'][str(i)]: [q.get(i, {}).get('calls', 0) for q in p] for i in range(40, 46)}}
        for q in p:
            assert sum(v['exclusive_ns'] for k, v in q.items() if k < 40) == q[0]['inclusive_ns']
            if index == 1:
                assert q[42]['calls'] == q[43]['calls'] == 92160
                assert q.get(44, {}).get('calls', 0) == q.get(45, {}).get('calls', 0) == 0
    final_activity = {}
    for version, s in states.items():
        final_activity[version] = {
            'activation_range': [min(n['activation'] for n in s['nodes']), max(n['activation'] for n in s['nodes'])],
            'inhibition_range': [min(n['inhibition'] for n in s['nodes']), max(n['inhibition'] for n in s['nodes'])],
            'timers': len(s['timers']), 'queue': len(s['queue']), 'active_nodes': len(s['active']),
            'signal_config': {key: value for key, value in s['config'].items() if any(x in key for x in ('threshold', 'propagation', 'inhibition_sender', 'activation_floor'))},
        }
    return {'passed': True, 'engineering_trials': 52, 'scientific_origins': 0, 'complete_state_files': 104,
            'instrument_exact_state_matches': 21, 'production_sources_unchanged': len(meta['source_files']),
            'coarse_profile': coarse, 'fine_profile': fine, 'phases': phases,
            'median_late_wall_fraction': st.median(r['chunks'][1]['wall_s'] / r['wall_s'] for r in segmented),
            'final_activity': final_activity, 'state_files': checked,
            'reviewer': 'Independent file arithmetic by the same assistant; not external replication.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.work.resolve())
    with (args.work / 'profile-analysis.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k not in ('state_files', 'fine_profile')}, indent=2))
