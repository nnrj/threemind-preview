"""Read-only whole-state audit and prespecified statistics for timing v1."""
from __future__ import annotations

import argparse
import copy
import hashlib
import statistics
from collections import defaultdict
from pathlib import Path

import analyze_m2 as stats
import pilot_m2_timing as t


def describe(values):
    return stats.describe(values, 20261016)


def corrected_contrasts(rows):
    groups=defaultdict(dict)
    for r in rows:
        key=(r['case']['origin'],r['branch']['cue'],r['branch']['arm'])
        if r['case']['history'] in groups[key]:raise ValueError('duplicate history')
        groups[key][r['case']['history']]=r['response_second_arrival']-r['baseline_second']
    if any(set(g)!={0,1} for g in groups.values()):raise ValueError('missing history')
    return {key:(g[0]-g[1])/2 for key,g in groups.items()}


def analyze(work):
    m,f=t.m,t.f
    if any((work/n).exists() for n in ('STOP','in-flight.json','apparatus-in-flight.json')):
        raise RuntimeError('unresolved marker')
    if m.read(work/'status.json')['state']!='awaiting-analysis' or m.read(work/'progress.json')['completed']!=288:
        raise RuntimeError('not a complete batch')
    m.frozen_check(work)
    rows,baselines=[],{}
    identities=0
    for case in m.read(work/'parents.json'):
        folder=work/'parents'/case['id']; current=m.read(folder/'current.json'); p=folder/current['path']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=current['sha256']:raise ValueError('parent hash')
        parent=f.load(p)
        if parent['case']!=case or int(parent['core']['time_us'])!=32_000_000:raise ValueError('parent identity/time')
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
                if int(initial['core']['time_us'])!=32_000_000 or int(final['core']['time_us'])!=34_000_000:
                    raise ValueError('copy time')
                for field in ('mappings','random_state','peripheral_weights','optimizer','body'):
                    if initial[field]!=parent[field] or final[field]!=parent[field]:raise ValueError('whole component '+field)
                if initial['input_cursor']!=parent['input_cursor'] or initial['recent_activity']!=parent['recent_activity']:
                    raise ValueError('past experience')
                prefix=initial['input_cursor']
                if initial['environment']['schedule'][:prefix]!=parent['environment']['schedule'][:prefix]:
                    raise ValueError('past inputs')
                probes=[e for e in initial['environment']['schedule'] if e['kind']=='probe']
                if probes!=t.probe_events(parent['mappings'],32_000_000,cue):raise ValueError('cue/time/answer isolation')
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
                    baselines[(case['origin'],case['history'],arm)]={r['time_us']-32_000_000:r['response']
                                                                  for r in final['recent_activity'] if r['time_us']>32_000_000}
                rows.append(result)
                initial_arms[arm]=copy.deepcopy(initial); initial_arms[arm].pop('branch')
            if not f.intervention_identity_valid(initial_arms['normalized'],initial_arms['summed']):
                raise ValueError('undeclared between-arm intervention')
            identities+=1
    if len(rows)!=288:raise ValueError('copy count')
    for r in rows:
        key=(r['case']['origin'],r['case']['history'],r['branch']['arm'])
        r['baseline_second']=baselines[key][r['forecast']['second_arrival_ms']*1000]
    contrasts=corrected_contrasts(rows)
    origins=sorted({r['case']['origin'] for r in rows})
    if len(origins)!=8:raise ValueError('origin count')
    gains=[contrasts[(o,'XY-1','normalized')]-contrasts[(o,'XY-0','normalized')] for o in origins]
    errors=defaultdict(list); lag_errors=defaultdict(lambda:defaultdict(list))
    classification={'correct':0,'nested_predictions':0,'independent_origins':8}
    for r in rows:
        cue=r['branch']['cue']
        if not cue.startswith('XY-'):continue
        actual,pred=r['response_second_arrival'],r['forecast']['at_second_arrival']
        error=abs(actual-pred)
        errors[r['case']['origin']].append(error); lag_errors[cue][r['case']['origin']].append(error)
        classification['correct']+=(abs(actual)>1e-9)==(abs(pred)>1e-9)
        classification['nested_predictions']+=1
    summary={'origins':origins,'primary_1ms_gain':describe(gains),'gain_by_origin':dict(zip(origins,gains)),
             'groups':{cue:{arm:describe([contrasts[(o,cue,arm)] for o in origins]) for arm in t.ARMS} for cue in t.CUES},
             'primary_prediction_mae':describe([statistics.mean(errors[o]) for o in origins]),
             'prediction_mae_by_origin':{o:statistics.mean(errors[o]) for o in origins},
             'prediction_mae_by_lag':{cue:describe([statistics.mean(group[o]) for o in origins]) for cue,group in lag_errors.items()},
             'classification':classification,'max_abs_none':max(abs(v) for values in baselines.values() for v in values.values()),
             'nonzero_late_cases':sum(abs(r['late_mean'])>1e-9 for r in rows)}
    result={'schema':'threemind.m2-timing-analysis/1','independent_origins':8,'whole_parents':16,'causal_copies':288,
            'copy_snapshots_verified':576,'prospective_forecasts_verified':288,'identity_pairs_verified':identities,
            'source_time_s':512,'causal_copy_time_s':576,'summary':summary,'rows':rows,
            'limits':'Prospective exploratory timing test; pointwise source intervals; no universal law or confirmation.'}
    m.original(work/'analysis-v1.json',result)
    print(m.encoded({k:v for k,v in result.items() if k!='rows'}).decode())


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,default=t.WORK)
    analyze(p.parse_args().work.resolve())
