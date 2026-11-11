"""Post-result descriptive checks of committed files; no student is loaded.

These measurements explain the registered scores. They do not replace them or
add new passing criteria. All observations remain nested within eight origins.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def diagnostics(work):
    assert load(work / 'status.json') == dict(state='awaiting-analysis', sequences_completed=40)
    assert load(work / 'independent-audit-v1.json')['passed']
    analysis = load(work / 'analysis-v1.json')
    details = []
    for subject in analysis['subjects']:
        root = work / 'subjects' / subject['key']
        receipts = {r['ordinal']: r for r in (load(p) for p in root.rglob('complete.json'))}
        stages = {}
        for stage, registered in subject['stages'].items():
            phases = {}
            for phase in ('immediate', 'delayed'):
                result = load(root / stage / phase / 'result.json.gz')
                receipt = load(root / stage / phase / 'complete.json')
                final = load(work / receipt['state_file'])
                rows = result['rows']
                phase_data = dict(
                    correct=sum(r['choice'] == r['target'] for r in rows),
                    questions=len(rows),
                    all_reader_frames_zero=sum(not any(v for f in r['reader_frames'] for v in f) for r in rows),
                    final_nodes=len(final['core']['nodes']), final_edges=len(final['core']['edges']),
                    task_edges=[],
                )
                # The state at entry to the whole test records actual body position.
                previous = receipts[receipt['ordinal']-1]
                prior = load(work / previous['state_file'])['body']['position']
                changed = held = changed_correct = held_correct = 0
                target_already = target_new = target_already_correct = target_new_correct = 0
                for row in rows:
                    correct = row['choice'] == row['target']
                    if row['choice'] != prior:
                        changed += 1; changed_correct += correct
                    else:
                        held += 1; held_correct += correct
                    if row['target'] == prior:
                        target_already += 1; target_already_correct += correct
                    else:
                        target_new += 1; target_new_correct += correct
                    prior = row['body']['position']
                phase_data['command_changed_position'] = dict(n=changed, correct=changed_correct)
                phase_data['command_held_position'] = dict(n=held, correct=held_correct)
                phase_data['target_already_reached'] = dict(n=target_already, correct=target_already_correct)
                phase_data['target_required_new_position'] = dict(n=target_new, correct=target_new_correct)
                mapping = final['mapping']
                edges = {(int(e['source']), int(e['target'])): e for e in final['core']['edges']}
                nodes = {}
                for n in final['core']['nodes']:
                    nodes.setdefault(n['channel'], []).append(n['id'])
                for cue in ('P0','P1','A0','A1','B0','B1'):
                    for port in ('out0', 'out1'):
                        found = [edges[(src, dst)] for src in nodes.get(mapping[cue], [])
                                 for dst in nodes.get(mapping[port], []) if (src,dst) in edges]
                        phase_data['task_edges'].append(dict(cue=cue, port=port,
                            edges=[{k:e[k] for k in ('source','target','weight','birth_us')} for e in found]))
                phases[phase] = phase_data
            stages[stage] = dict(phases=phases,
                                correction_rounds=len(registered['development'])-1,
                                passed=subject['goals'][stage])
        details.append(dict(key=subject['key'], curve=subject['curve'], stages=stages))
    aggregate = {}
    for curve in dict.fromkeys(r['curve'] for r in details):
        group = [r for r in details if r['curve'] == curve]
        by_stage = {}
        for stage in ('initial', 'new', 'reversal', 'return'):
            by_stage[stage] = dict(correction_rounds=sum(r['stages'][stage]['correction_rounds'] for r in group), phases={})
            for phase in ('immediate', 'delayed'):
                rows = [r['stages'][stage]['phases'][phase] for r in group]
                by_stage[stage]['phases'][phase] = dict(correct=sum(r['correct'] for r in rows),
                    questions=sum(r['questions'] for r in rows),
                    median_edges=statistics.median(r['final_edges'] for r in rows),
                    all_reader_frames_zero=sum(r['all_reader_frames_zero'] for r in rows),
                    target_already_reached={k:sum(r['target_already_reached'][k] for r in rows) for k in ('n','correct')},
                    target_required_new_position={k:sum(r['target_required_new_position'][k] for r in rows) for k in ('n','correct')})
        aggregate[curve] = by_stage
    return dict(schema='threemind.r48b-descriptive-analysis/1', retrospective=True,
                analysis_sha256=hashlib.sha256((work/'analysis-v1.json').read_bytes()).hexdigest(),
                independent_origins=8, aggregate=aggregate, subjects=details,
                scope='Scores and interventions are unchanged. End-of-test edge states include the test itself; absence here is not a new causal intervention. Actual position commands and already-reached targets are separate denominators.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    work = p.parse_args().work
    result = diagnostics(work)
    with (work/'descriptive-analysis-v1.json').open('x', encoding='utf8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result['aggregate']))
