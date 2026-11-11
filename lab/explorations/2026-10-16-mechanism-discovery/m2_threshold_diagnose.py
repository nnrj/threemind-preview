"""Post-result arithmetic diagnosis. Never changes the frozen predictor or scores."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from m2_threshold_predictor import predict


def diagnose(work):
    rows=[]
    for origin in range(8):
        folder=work/'units'/f'o{origin}'
        result=json.loads((folder/'result.json').read_bytes())
        for h in result['histories']:
            for r in h['tests']:
                path=folder/r['initial']['path']
                raw=path.read_bytes()
                assert hashlib.sha256(raw).hexdigest()==r['initial']['sha256']
                whole=json.loads(gzip.decompress(raw));c=whole['model']['config']
                # Native stimulus receipt multiplies by direct_gain (local_shared.rs).
                # The frozen P1 predictor omitted this existing factor. This is a
                # post-hoc correction of a read-only formula, NOT a new validation.
                corrected=predict(whole,r['dose']*c['direct_gain'])
                bychannel={n['channel']:n for n in whole['model']['nodes']}
                value=0.
                for label,sign in [('A',1),('B',-1)]:
                    p=corrected['targets'][label]
                    if not p['passes']:continue
                    n=bychannel[whole['mappings'][label]]
                    assert n['fatigue']==0
                    dt=(corrected['first_arrival_us']-int(n['state_us']))/1e6
                    inhibition=n['inhibition']*(math.exp(-dt/c['inhibition_tau']) if c['inhibition_decay_enabled'] else 1)
                    soft=c['inhibition_saturation']*math.tanh(max(0.,inhibition)/c['inhibition_saturation'])
                    response=1/(1+c['inhibition_response_gain']*soft) if c['inhibition'] else 1.
                    value+=sign*p['message']*response
                rows.append({'origin':origin,'history':h['history'],'delay':r['delay'],'arm':r['arm'],'dose':r['dose'],
                             'novel_in_original':r['novel'],'direct_gain':c['direct_gain'],
                             'original_direction':r['prediction']['direction'],'actual_direction':r['probe']['direction'],
                             'gain_corrected_direction':corrected['direction'],
                             'posthoc_endpoint':value,'actual_endpoint':r['probe']['first'],
                             'absolute_error':abs(value-r['probe']['first'])})
    assert len(rows)==704
    return {'schema':'threemind.m2-threshold-posthoc-diagnosis/1','status':'retrospective; no prospective score replacement',
            'original_correct':sum(r['original_direction']==r['actual_direction'] for r in rows),
            'gain_corrected_correct':sum(r['gain_corrected_direction']==r['actual_direction'] for r in rows),
            'max_endpoint_absolute_error':max(r['absolute_error'] for r in rows),
            'direct_gains':sorted({r['direct_gain'] for r in rows}),
            'source_references':['crates/threemind-core/src/local_shared.rs:1825','m2_threshold_predictor.py'],
            'frozen_P1_verdict':'FAIL','Core_loaded':False,'simulation_advanced':False,'rows':rows}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);w=p.parse_args().work
    result=diagnose(w)
    with (w/'posthoc-diagnosis-v1.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
