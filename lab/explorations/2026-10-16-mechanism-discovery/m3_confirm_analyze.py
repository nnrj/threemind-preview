"""Read-only, source-level confirmation statistics; no simulation engine is created."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import beta,binomtest

import closure_analyze as old
import m3_confirm_spec as spec
import pilot_m2 as m


def cp(k,n):
    return [0. if k==0 else float(beta.ppf(.025,k,n-k+1)),
            1. if k==n else float(beta.ppf(.975,k+1,n-k))]


def source_scores(result):
    # Reuse only frozen per-source criterion arithmetic. The old 6/8 aggregate is discarded.
    raw=old.x3(list(result['systems'].values()))['systems']
    scores={}
    for kind in spec.KINDS:
        rows=raw[kind]['origins'];assert len(rows)==1
        scores[kind]=rows[0]
    return {'origin':result['origin'],'case':result['case'],'scores':scores}


def evaluate(units):
    assert len(units)==spec.N and {u['origin'] for u in units}==set(range(spec.N))
    units=sorted(units,key=lambda u:u['origin'])
    valid=all(s['matching_valid'] and s['replay_valid'] for u in units for s in u['scores'].values())
    systems={};matrices={}
    for kind in spec.KINDS:
        matrix=np.asarray([u['scores'][kind]['passes'] for u in units],dtype=bool)
        assert matrix.shape==(spec.N,4)
        matrices[kind]=matrix
        counts=matrix.sum(axis=0).tolist();joint=matrix.all(axis=1)
        verdicts=['PASS' if n>=spec.MIN_PASS else 'FAIL' for n in counts]
        if not all(u['scores'][kind]['matching_valid'] for u in units):verdicts[1]='INVALID'
        if not all(u['scores'][kind]['replay_valid'] for u in units):verdicts[3]='INVALID'
        systems[kind]={'criterion_counts':counts,'criterion_verdicts':verdicts,
                       'joint_count':int(joint.sum()),'joint_rate':float(joint.mean()),
                       'joint_proportion_95':cp(int(joint.sum()),spec.N),
                       'cohort_all_four':'INVALID' if 'INVALID' in verdicts else 'PASS' if min(counts)>=spec.MIN_PASS else 'FAIL'}
    comparisons={};t=matrices['threemind'].all(axis=1)
    rng=np.random.default_rng(2026101692)
    boot=rng.integers(0,spec.N,(20000,spec.N))
    for kind in spec.KINDS[:-1]:
        c=matrices[kind].all(axis=1);d=t.astype(int)-c.astype(int)
        plus=int((d==1).sum());minus=int((d==-1).sum());discordant=plus+minus
        p=float(binomtest(plus,discordant,.5,alternative='two-sided').pvalue) if discordant else 1.
        comparisons[kind]={'positive':plus,'negative':minus,'ties':spec.N-discordant,
                           'mean_paired_difference':float(d.mean()),'exact_two_sided_p':p,
                           'paired_bootstrap_95':np.quantile(d[boot].mean(axis=1),[.025,.975]).tolist()}
    running=0.
    for rank,(kind,row) in enumerate(sorted(comparisons.items(),key=lambda item:item[1]['exact_two_sided_p'])):
        running=max(running,min(1.,(4-rank)*row['exact_two_sided_p']))
        row['holm_p']=running
        row['verdict']='PASS' if running<.05 and row['mean_paired_difference']>=spec.MIN_PAIRED_ADVANTAGE else 'FAIL'
    counterexamples=[k for k in spec.KINDS[:-1] if systems[k]['cohort_all_four']=='PASS']
    passed=(systems['threemind']['cohort_all_four']=='PASS' and systems['threemind']['joint_count']>=spec.MIN_PASS
            and not counterexamples and all(v['verdict']=='PASS' for v in comparisons.values()))
    return {'schema':'threemind.m3-confirmation-analysis/1','independent_origins':spec.N,'valid':valid,
            'verdict':'INVALID' if not valid else 'PASS' if passed else 'FAIL',
            'systems':systems,'paired_comparisons':comparisons,'cohort_counterexamples':counterexamples,
            'units':units,'criterion_implementation':'cross-system-criteria/2 unchanged',
            'conjunction_not_score':True,'old_eight_origins_excluded':True}


def analyze(work):
    assert m.read(work/'status.json')['state']=='awaiting-analysis'
    assert m.read(work/'cases.json')==spec.cases()
    units=[];manifest=[]
    for case in spec.cases():
        path=work/'units'/f'o{case["origin"]}'/'result.json';raw=m.read(path)
        assert raw['case']==case
        units.append(source_scores(raw))
        manifest.append({'path':path.relative_to(work).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    result=evaluate(units);result['result_manifest']=manifest
    m.original(work/'analysis-v1.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('units','result_manifest')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    analyze(p.parse_args().work)
