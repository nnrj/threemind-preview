"""Read-only complete-state and prospective endpoint audit for fusion v2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import statistics
from collections import defaultdict
from pathlib import Path

import analyze_m2 as statistics_tools
import pilot_m2_fusion_v2 as f


def paired(rows, field):
    by = defaultdict(dict)
    for row in rows:
        case, branch = row['case'], row['branch']
        key = (case['origin'], branch['cue'], branch['arm'])
        if case['history'] in by[key]:
            raise ValueError('duplicate history observation')
        by[key][case['history']] = row[field]
    result = {}
    for key, histories in by.items():
        if set(histories) != {0, 1}:
            raise ValueError('missing opposite history')
        origin, _cue, arm = key
        baseline = by[(origin, 'none', arm)]
        result[key] = ((histories[0]-baseline[0])-(histories[1]-baseline[1]))/2
    return result


def describe(values):
    return statistics_tools.describe(values, 20261016)


def scientific_summary(rows):
    values = paired(rows, 'response_110ms')
    origins = sorted({r['case']['origin'] for r in rows})
    if len(origins) != 8:
        raise ValueError('eight independent origins required')
    group = {cue: {arm: describe([values[(o, cue, arm)] for o in origins]) for arm in f.ARMS} for cue in f.CUES}
    interactions, conditional = [], []
    for origin in origins:
        get = lambda cue, arm, origin=origin: values[(origin, cue, arm)]
        norm_single = (get('X', 'normalized')+get('Y', 'normalized'))/2
        sum_single = (get('X', 'summed')+get('Y', 'summed'))/2
        interactions.append((get('XY-per', 'summed')-sum_single)-(get('XY-per', 'normalized')-norm_single))
        if min(get('X', 'normalized'), get('Y', 'normalized'), get('X', 'summed'), get('Y', 'summed')) > 1e-6:
            conditional.append({'origin': origin, 'normalized_joint_to_single': get('XY-per', 'normalized')/norm_single,
                                'summed_joint_to_single': get('XY-per', 'summed')/sum_single})
    errors, classification = {}, {}
    for model in ['receiver', 'total-dose']:
        by_origin = defaultdict(list)
        correct, total = 0, 0
        for row in rows:
            if row['branch']['arm'] not in ['normalized', 'summed']:
                continue
            prediction = row['forecast']['response_at_110ms'][model]
            actual = row['response_110ms']
            by_origin[row['case']['origin']].append(abs(prediction-actual))
            correct += (abs(prediction) > 1e-9) == (abs(actual) > 1e-9)
            total += 1
        errors[model] = {'per_origin': {o: statistics.mean(by_origin[o]) for o in origins},
                         'summary': describe([statistics.mean(by_origin[o]) for o in origins])}
        classification[model] = {'zero_nonzero_correct': correct, 'nested_predictions': total, 'independent_origins': 8}
    advantage = [errors['total-dose']['per_origin'][o]-errors['receiver']['per_origin'][o] for o in origins]
    return {'origins': origins, 'groups': group, 'primary_interaction': describe(interactions),
            'interaction_by_origin': dict(zip(origins, interactions)), 'conditional_ratios': conditional,
            'conditional_ratio_origins': len(conditional), 'prediction_errors': errors,
            'prediction_error_advantage': describe(advantage), 'classification': classification,
            'max_single_arm_difference': max(abs(values[(o,c,'normalized')]-values[(o,c,'summed')])
                                             for o in origins for c in ['X-low','X','Y','X-total']),
            'max_restoration_control_difference': max(abs(values[(o,c,'restored')]-values[(o,c,'double-sham')])
                                                      for o in origins for c in f.CUES),
            'nonzero_late_cases': sum(abs(r['late_mean']) > 1e-9 for r in rows),
            'late_mean_max_abs': max(abs(r['late_mean']) for r in rows)}


def analyze(work):
    if any((work/n).exists() for n in ['STOP','in-flight.json','apparatus-in-flight.json']):
        raise RuntimeError('unresolved marker')
    status = f.m.read(work/'status.json')
    if status['completed'] != 448 or status['state'] != 'awaiting-analysis':
        raise RuntimeError('not a complete batch')
    f.m.frozen_check(work)
    rows, snapshot_count, restored_count = [], 0, 0
    inputs, forecast_count = {}, 0
    for case in f.m.read(work/'parents.json'):
        folder = work/'parents'/case['id']
        current = f.m.read(folder/'current.json')
        p = folder/current['path']
        if hashlib.sha256(p.read_bytes()).hexdigest() != current['sha256']:
            raise ValueError('parent current hash differs')
        parent = f.load(p)
        graph = f.load(folder/'pre-cue-graph.json.gz')
        forecasts = f.m.read(folder/'forecasts.json')
        if int(parent['core']['time_us']) != 32_000_000 or parent['case'] != case:
            raise ValueError('wrong parent boundary/identity')
        for cue in f.CUES:
            originals, finals = {}, {}
            for arm in f.ARMS:
                out = work/'cases'/f'{case["id"]}-{cue}-{arm}'
                initial, final = f.load(out/'initial-whole.json.gz'), f.load(out/'final-whole.json.gz')
                originals[arm], finals[arm] = copy.deepcopy(initial), copy.deepcopy(final)
                snapshot_count += 2
                lineage, stored = f.m.read(out/'lineage.json'), f.m.read(out/'result.json')
                if lineage['parent_sha256'] != f.m.digest(parent) or lineage['branch_initial_sha256'] != f.m.digest(initial):
                    raise ValueError('lineage hashes differ')
                if lineage['changed_paths'] != f.differences(parent,initial):
                    raise ValueError('lineage diff differs')
                for name in ['mappings','random_state','peripheral_weights','optimizer','body']:
                    if initial[name] != parent[name] or final[name] != parent[name]:
                        raise ValueError('nondeclared component changed: '+name)
                if initial['input_cursor'] != parent['input_cursor'] or initial['recent_activity'] != parent['recent_activity']:
                    raise ValueError('past experience changed')
                prefix = initial['input_cursor']
                if initial['environment']['schedule'][:prefix] != parent['environment']['schedule'][:prefix]:
                    raise ValueError('past inputs changed')
                if int(initial['core']['time_us']) != 32_000_000 or int(final['core']['time_us']) != 34_000_000:
                    raise ValueError('copy time differs')
                if initial['core']['config']['energy_simulation_enabled']:
                    raise ValueError('unexpected energy model')
                for state in (initial,final):
                    core = state['core']
                    if core['config'] != core['definition']['config'] or f.m.StateImage.from_dict(core['definition']).digest != core['definition_hash']:
                        raise ValueError('definition identity mismatch')
                payload = [e for e in initial['environment']['schedule'] if e['kind'] == 'probe']
                key = (case['origin'],cue)
                if key in inputs and inputs[key] != payload:
                    raise ValueError('current input leaks history or arm')
                inputs[key] = payload
                prediction = f.forecast(graph,parent['mappings'],parent['core']['config'],cue,f.ARMS[arm][-1])
                if prediction != forecasts[cue][arm]:
                    raise ValueError('prospective prediction differs')
                forecast_count += 1
                recomputed = f.endpoint(final,prediction)
                if recomputed != stored or recomputed['grid_frames'] != 2000:
                    raise ValueError('saved endpoint/grid differs')
                rows.append(recomputed)
                originals[arm].pop('branch'); finals[arm].pop('branch')
            if not f.intervention_identity_valid(originals['normalized'],originals['summed']):
                raise ValueError('scientific intervention whitelist failed')
            if originals['restored'] != originals['double-sham'] or finals['restored'] != finals['double-sham']:
                raise ValueError('full reversal control differs')
            restored_count += 1
    if len(rows) != 448:
        raise ValueError('case count differs')
    result = {'schema':'threemind.m2-fusion-analysis/1','independent_origins':8,'whole_parents':16,
              'causal_copies':448,'copy_snapshots_verified':snapshot_count,'prospective_forecasts_verified':forecast_count,
              'full_restored_pairs_verified':restored_count,'source_time_s':512,'causal_copy_time_s':896,
              'summary':scientific_summary(rows),'rows':rows,
              'limits':'Exploratory S-mode receiver test; no Core default change, no broad memory law, no confirmation or independent replication.'}
    f.m.original(work/'analysis-v1.json',result)
    print(f.m.encoded({k:v for k,v in result.items() if k!='rows'}).decode())


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,default=f.WORK)
    args=parser.parse_args()
    analyze(args.work.resolve())
