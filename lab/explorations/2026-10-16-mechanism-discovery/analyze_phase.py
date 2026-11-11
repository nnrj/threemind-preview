"""Read-only whole-state audit and prespecified statistics for phase v1."""
from __future__ import annotations

import argparse
import copy
import hashlib
import statistics
from collections import defaultdict
from pathlib import Path

import analyze_m2 as stats
import pilot_m2_phase as t


def describe(values):
    return stats.describe(values, 20261016)


def corrected_contrasts(rows):
    groups=defaultdict(dict)
    for r in rows:
        key=(r['case']['origin'],r['branch']['cue'],r['branch']['arm'])
        if r['case']['history'] in groups[key]:raise ValueError('duplicate history')
        groups[key][r['case']['history']]=r['response_110ms']-r['baseline_first']
    if any(set(g)!={0,1} for g in groups.values()):raise ValueError('missing history')
    return {key:(g[0]-g[1])/2 for key,g in groups.items()}


def analyze(work):
    m,f=t.m,t.f
    if any((work/n).exists() for n in ('STOP','in-flight.json','apparatus-in-flight.json')):
        raise RuntimeError('unresolved marker')
    if m.read(work/'status.json')['state']!='awaiting-analysis' or m.read(work/'progress.json')['completed']!=672:
        raise RuntimeError('not a complete batch')
    m.frozen_check(work)
    rows,baselines=[],{}
    identities=0
    for case in m.read(work/'parents.json'):
        folder=work/'parents'/case['id']; current=m.read(folder/'current.json'); p=folder/current['path']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=current['sha256']:raise ValueError('parent hash')
        parent=f.load(p)
        if parent['case']!=case or int(parent['core']['time_us'])!=40_000_000:raise ValueError('parent identity/time')
        graph=f.load(folder/'pre-cue-graph.json.gz'); forecasts=m.read(folder/'forecasts.json')
        for cue in t.CUES:
            initial_arms={}
            for arm in t.ARMS:
                out=work/'cases'/f'{case["id"]}-{cue}-{arm}'
                initial,final=f.load(out/'initial-whole.json.gz'),f.load(out/'final-whole.json.gz')
                lineage=m.read(out/'lineage.json')
                if lineage['parent_sha256']!=m.digest(parent) or lineage['branch_initial_sha256']!=m.digest(initial):
                    raise ValueError('lineage hashes')
                if lineage['changed_paths']!=f.differences(parent,initial):raise ValueError('lineage diff')
                if initial['case']!=case or final['case']!=case:raise ValueError('copy identity')
                if int(initial['core']['time_us'])!=40_000_000 or int(final['core']['time_us'])!=42_000_000:
                    raise ValueError('copy time')
                for field in ('mappings','random_state','peripheral_weights','optimizer','body'):
                    if initial[field]!=parent[field] or final[field]!=parent[field]:raise ValueError('whole component '+field)
                if initial['input_cursor']!=parent['input_cursor'] or initial['recent_activity']!=parent['recent_activity']:
                    raise ValueError('past experience')
                prefix=initial['input_cursor']
                if initial['environment']['schedule'][:prefix]!=parent['environment']['schedule'][:prefix]:
                    raise ValueError('past inputs')
                probes=[e for e in initial['environment']['schedule'] if e['kind']=='probe']
                if probes!=t.probe_events(parent['mappings'],40_000_000,cue):raise ValueError('cue/time/answer isolation')
                for state in (initial,final):
                    c=state['core']
                    if c['definition']['config']!=c['config'] or m.StateImage.from_dict(c['definition']).digest!=c['definition_hash']:
                        raise ValueError('definition identity')
                    if c['config']['energy_simulation_enabled']:raise ValueError('unexpected energy model')
                prediction=t.forecast(graph,parent['mappings'],parent['core']['config'],cue,arm)
                if prediction!=forecasts[cue][arm]:raise ValueError('saved prospective forecast')
                result=t.endpoint(final,prediction)
                if result!=m.read(out/'result.json') or result['grid_frames']!=2000:raise ValueError('endpoint/grid')
                if cue=='none':
                    baselines[(case['origin'],case['history'],arm)]={r['time_us']-40_000_000:r['response']
                                                                  for r in final['recent_activity'] if r['time_us']>40_000_000}
                rows.append(result)
                initial_arms[arm]=copy.deepcopy(initial); initial_arms[arm].pop('branch')
            if not f.intervention_identity_valid(initial_arms['normalized'],initial_arms['summed']):
                raise ValueError('undeclared between-arm intervention')
            identities+=1
    if len(rows)!=672:raise ValueError('copy count')
    for r in rows:
        key=(r['case']['origin'],r['case']['history'],r['branch']['arm'])
        r['baseline_first']=baselines[key][110_000]
    contrasts=corrected_contrasts(rows)
    origins=sorted({r['case']['origin'] for r in rows})
    if len(origins)!=8:raise ValueError('origin count')
    models=('phase-aware','all-same-cycle')
    errors={model:defaultdict(list) for model in models}
    classification={model:{'correct':0,'nested_predictions':0,'independent_origins':8} for model in models}
    by_cue={model:defaultdict(lambda:defaultdict(list)) for model in models}
    max_error={model:0. for model in models}; failures=[]
    for r in rows:
        cue=r['branch']['cue']
        if cue=='none':continue
        for model in models:
            actual,pred=r['response_110ms'],r['forecast']['response_at_110ms'][model]
            error=abs(actual-pred)
            errors[model][r['case']['origin']].append(error)
            by_cue[model][cue][r['case']['origin']].append(error)
            correct=(abs(actual)>1e-9)==(abs(pred)>1e-9)
            classification[model]['correct']+=correct
            classification[model]['nested_predictions']+=1
            max_error[model]=max(error,max_error[model])
            if model=='phase-aware' and (error>1e-6 or not correct):
                failures.append({'case':r['case']['id'],'cue':cue,'arm':r['branch']['arm'],
                                 'actual':actual,'predicted':pred,'error':error,'classification_correct':correct})
    origin_error={model:{o:statistics.mean(errors[model][o]) for o in origins} for model in models}
    summary={'origins':origins,
             'groups':{cue:{arm:describe([contrasts[(o,cue,arm)] for o in origins]) for arm in t.ARMS} for cue in t.CUES},
             'primary_prediction_mae':{model:describe(list(origin_error[model].values())) for model in models},
             'prediction_mae_by_origin':origin_error,
             'prediction_mae_by_cue':{model:{cue:describe([statistics.mean(group[o]) for o in origins]) for cue,group in by_cue[model].items()} for model in models},
             'paired_error_reduction':describe([origin_error['all-same-cycle'][o]-origin_error['phase-aware'][o] for o in origins]),
             'boundary_contrast':{arm:describe([contrasts[(o,'p99-d2',arm)]-contrasts[(o,'p99-d1',arm)] for o in origins]) for arm in t.ARMS},
             'classification':classification,'max_abs_error':max_error,
             'prespecified_tolerance':1e-6,'failed_forecast_cases':failures,'tolerance_passed':not failures,
             'max_abs_none':max(abs(v) for values in baselines.values() for v in values.values()),
             'nonzero_late_cases':sum(abs(r['late_mean'])>1e-9 for r in rows)}
    result={'schema':'threemind.m2-phase-analysis/1','independent_origins':8,'whole_parents':16,'causal_copies':672,
            'copy_snapshots_verified':1344,'prospective_forecasts_verified':672,'identity_pairs_verified':identities,
            'source_time_s':640,'causal_copy_time_s':1344,'summary':summary,'rows':rows,
            'limits':'Prospective exploratory first-cycle phase test; pointwise source intervals; no universal law or confirmation.'}
    m.original(work/'analysis-v1.json',result)
    print(m.encoded({k:v for k,v in result.items() if k!='rows'}).decode())


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,default=t.WORK)
    analyze(p.parse_args().work.resolve())
