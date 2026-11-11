"""Frozen pass/fail rules for closure-v1. Reads originals without loading subjects."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import statistics as st
from pathlib import Path

import numpy as np
import pilot_m2 as m


def interval(values):
    a=np.asarray(values,dtype=float)
    rng=np.random.default_rng(16102026)
    means=a[rng.integers(0,len(a),(10000,len(a)))].mean(axis=1)
    return {'mean':float(a.mean()),'ci95':np.quantile(means,[.025,.975]).tolist(),'n':len(a),'values':a.tolist()}


def x1(results):
    origins=[]
    for r in results:
        if not r['valid']:
            origins.append({'origin':r['origin'],'valid':False,'pass':False});continue
        rates={}
        for arm in ('intact','sham','target-bundle','matched-bundle','persistent','fast','restored'):
            rates[arm]={}
            for domain,cues in [('target',('X','Y','XY')),('unrelated',('Z','W','ZW'))]:
                rows=[t for t in r['trials'] if t['arm']==arm and t['cue'] in cues]
                rates[arm][domain]=st.mean(t['success'] for t in rows)
        target=rates['target-bundle']['target']
        gain=target-rates['sham']['target']
        unrelated_loss=rates['sham']['unrelated']-rates['target-bundle']['unrelated']
        matched_gain=rates['matched-bundle']['target']-rates['sham']['target']
        origins.append({'origin':r['origin'],'valid':True,'rates':rates,'gain':gain,'unrelated_loss':unrelated_loss,
            'matched_gain':matched_gain,'pass':target>=.75 and gain>=.5 and unrelated_loss<=.1 and matched_gain<=.1,
            'persistent_pass':rates['persistent']['target']>=.75,'fast_pass':rates['fast']['target']>=.75})
    valid=all(o['valid'] for o in origins)
    passed=sum(o['pass'] for o in origins)
    return {'verdict':'INVALID' if not valid else 'PASS' if passed>=6 else 'FAIL','passed_origins':passed,
            'origins':origins,'persistent_verdict':'PASS' if sum(o.get('persistent_pass',False) for o in origins)>=6 else 'FAIL',
            'fast_verdict':'PASS' if sum(o.get('fast_pass',False) for o in origins)>=6 else 'FAIL',
            'target_gain':interval([o['gain'] for o in origins if o['valid']]) if valid else None}


def x2(results):
    cohorts={}
    for delay in (1,30,60,300):
        rows=[]
        for r in (r for r in results if r['delay']==delay):
            separation=[]; transient=[]; savings=[]
            for h in r['histories']:
                sign=1 if h['history']==0 else -1
                t=h['tests']
                strong=sign*t['strong']['first']>1e-4
                elicited=strong or sign*t['joint']['first']>1e-4
                separation.append(len(h['target_edges'])==2 and abs(t['weak']['first'])<=1e-9 and elicited
                                  and abs(t['none']['first'])<=1e-9)
                transient.append(strong and abs(t['strong']['late_mean'])<=1e-9)
                savings.append(h['untrained']['rounds']-h['relearning']['rounds'])
            rows.append({'origin':r['origin'],'separation':all(separation),'transient':all(transient),
                         'savings':st.mean(savings),'histories':r['histories']})
        sep=sum(r['separation'] for r in rows); transient=sum(r['transient'] for r in rows)
        gains=interval([r['savings'] for r in rows]); pos=sum(r['savings']>0 for r in rows)
        cohorts[str(delay)]={'separation_verdict':'PASS' if sep>=6 else 'FAIL','separation_count':sep,
                            'transient_verdict':'PASS' if transient>=6 else 'FAIL','transient_count':transient,
                            'relearning_verdict':'PASS' if gains['mean']>=2 and pos>=6 else 'FAIL',
                            'positive_savings_count':pos,'savings':gains,'origins':rows}
    return {'separation_verdict':'PASS' if any(c['separation_verdict']=='PASS' for c in cohorts.values()) else 'FAIL',
            'transient_verdict':'PASS' if any(c['transient_verdict']=='PASS' for c in cohorts.values()) else 'FAIL',
            'cohorts':cohorts}


def x3(results):
    systems={}
    for kind in ('reactive','finite-state','hebbian','fixed-rnn-reader','threemind'):
        origins=[]
        for r in (r for r in results if r['kind']==kind):
            h=r['histories']
            def diff(cells,arm):return cells[arm+'-X']['early_integral']-cells[arm+'-none']['early_integral']
            contrast=(diff(h[0]['cells'],'intact')-diff(h[1]['cells'],'intact'))/2
            c2=[]; c3=[]; matches=[]
            for row in h:
                cells=row['cells']; base=diff(cells,'intact')
                target=abs(base-diff(cells,'target')); matched=abs(base-diff(cells,'matched'))
                sham=abs(base-diff(cells,'sham')); restore=abs(base-diff(cells,'restored'))
                match=row['selection'] is None or row['selection']['passed']; matches.append(match)
                c2.append({'target':target,'matched':matched,'sham':sham,'restoration_error':restore,
                           'pass':match and target>1e-4 and target>10*sham and matched<=.25*target and restore<=1e-9})
                t=row['temporal']
                interaction={arm:t[arm+'-XY']['late_integral']-t[arm+'-X0']['late_integral']-
                             t[arm+'-0Y']['late_integral']+t[arm+'-00']['late_integral'] for arm in ('intact','all')}
                effect=abs(interaction['intact']-interaction['all'])
                c3.append({'interaction':interaction,'effect':effect,'pass':effect>1e-4})
            def diagnostic(seq,r=r):
                d=r['worlds'][seq][1]['diagnostics']
                return d['X']['early_integral']-d['none']['early_integral']
            env_effects=[abs(diagnostic('PQP')-diagnostic('PPP')),abs(diagnostic('QPQ')-diagnostic('QQQ'))]
            audits=[r['worlds'][s][1]['world']['loop_audit'] for s in ('PPP','PQP','QQQ','QPQ')]
            replay_valid=all(a['replay_model_equal'] and a['reversed_replay_model_equal'] for a in audits)
            feedback=any(a['closed_reversal_inputs_differ'] and a['closed_reversal_model_differs'] for a in audits)
            passes=[abs(contrast)>1e-4,all(v['pass'] for v in c2),any(v['pass'] for v in c3),
                    any(e>1e-4 for e in env_effects) and feedback and replay_valid]
            origins.append({'origin':r['origin'],'passes':passes,'C1_contrast':contrast,'C2':c2,'C3':c3,
                            'C4_effects':env_effects,'C4_feedback':feedback,'replay_valid':replay_valid,
                            'matching_valid':all(matches)})
        counts=[sum(o['passes'][j] for o in origins) for j in range(4)]
        verdicts=['PASS' if n>=6 else 'FAIL' for n in counts]
        if not all(o['matching_valid'] for o in origins):verdicts[1]='INVALID'
        if not all(o['replay_valid'] for o in origins):verdicts[3]='INVALID'
        overall='INVALID' if 'INVALID' in verdicts else 'PASS' if all(v=='PASS' for v in verdicts) else 'FAIL'
        systems[kind]={'counts':counts,'verdicts':verdicts,'overall':overall,'origins':origins}
    counterexamples=[k for k,v in systems.items() if k!='threemind' and v['overall']=='PASS']
    return {'systems':systems,'all_four_comparator_passes':counterexamples,
            'discrimination_verdict':'FAIL' if counterexamples else 'PASS_ON_REGISTERED_SYSTEMS' if systems['threemind']['overall']=='PASS'
            and all(v['overall']=='FAIL' for k,v in systems.items() if k!='threemind') else 'NOT_ESTABLISHED_BY_FROZEN_RULE'}


def analyze(work):
    if m.read(work/'status.json')['state']!='awaiting-analysis':raise RuntimeError('not complete')
    results=[m.read(p) for p in sorted((work/'units').glob('*/result.json'))]
    if len(results)!=80:raise RuntimeError('incomplete registered units')
    manifests=[]
    for p in sorted((work/'units').rglob('*.json.gz')):
        raw=p.read_bytes(); whole=json.loads(gzip.decompress(raw))
        if whole['schema']!='threemind.goal-closure-whole/1':raise RuntimeError('unknown whole state')
        if whole['kind']=='threemind' and int(whole['model']['time_us'])!=whole['time_us']:raise RuntimeError('clock mismatch')
        manifests.append({'path':p.relative_to(work).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),
                          'time_us':whole['time_us'],'kind':whole['kind']})
    report={'schema':'threemind.goal-closure-analysis/1','X1':x1([r for r in results if r['package']=='X1']),
            'X2':x2([r for r in results if r['package']=='X2']),'X3':x3([r for r in results if r['package']=='X3']),
            'unit_count':len(results),'whole_count':len(manifests),'whole_manifest':manifests,
            'resources':m.read(work/'resource-summary.json'),'predefined_targets_unchanged':True}
    m.original(work/'analysis-v1.json',report)
    print(json.dumps({'units':len(results),'wholes':len(manifests),'X1':report['X1']['verdict'],
        'X2_separation':report['X2']['separation_verdict'],'X2_transient':report['X2']['transient_verdict'],
        'X3':{k:{'counts':v['counts'],'verdicts':v['verdicts'],'overall':v['overall']} for k,v in report['X3']['systems'].items()}}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    analyze(p.parse_args().work.resolve())
