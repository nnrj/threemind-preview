"""Replay identical timestamped windows under different decoding schedules."""
from collections import deque
import gzip
import json
import time
from types import SimpleNamespace
import numpy as np
import torch
from experiment import OLD,WORK,SEEDS,study,guard,new_json,read_json,write_gzip
from lab.tools.expression_observation import decode_timed
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.native_readout import NativeProjection
from threemind_transformer.development_model import load


def windows(path):
    queue=deque(maxlen=4)
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            chunk=json.loads(line)['process'];queue.append(chunk)
            if len(queue)<4:continue
            frames=[];last=-1
            for part in queue:
                for frame in part['trajectory']:
                    when=int(frame['time_us'])
                    if when>last:frames.append(frame);last=when
            yield {'start_us':queue[0]['start_us'],'end_us':queue[-1]['end_us'],
                   'planned_end_us':queue[-1]['end_us'],'trajectory':frames}


def main():
    torch.set_num_threads(2);s=study();tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    outputs=[];summaries=[];gpu='cuda' if torch.cuda.is_available() else 'cpu'
    try:
        for seed in SEEDS:
            selected={i:p for i,p in enumerate(windows(OLD/'cases'/f's{seed}-background'/'process-532.jsonl.gz')) if i in (0,8,528)}
            if len(selected)!=3:raise RuntimeError('expected original windows absent')
            for regime in ('individual','developmental'):
                for modality in ('vision','words'):
                    guard(s)
                    key=f'{regime}-s{seed}-{modality}'
                    manifest=read_json(OLD/'models'/f'{key}.json')
                    projection=NativeProjection(**manifest['projection'])
                    calibration=FeatureCalibration(**manifest['feature_calibration'])
                    features=calibration.transform([projection.project(p)['values'] for p in selected.values()])
                    ids=[{'id':f'{seed}-{i}','start_us':p['start_us'],'end_us':p['end_us']} for i,p in selected.items()]
                    model,_=load(OLD/'models'/manifest['checkpoint'],'cpu')
                    variants={}
                    variants['cpu-sequential']=[decode_timed(model,features[i:i+1],[ids[i]])[0] for i in range(3)]
                    variants['cpu-reversed']=decode_timed(model,features[::-1].copy(),ids[::-1])
                    variants['cpu-reloaded']=[decode_timed(load(OLD/'models'/manifest['checkpoint'],'cpu')[0],features[i:i+1],[ids[i]])[0] for i in range(3)]
                    queued=time.time_ns();time.sleep(.05)
                    variants['cpu-delayed']=decode_timed(model,features,ids,queued_at_ns=queued)
                    model,_=load(OLD/'models'/manifest['checkpoint'],gpu)
                    variants['accelerator-batch']=decode_timed(model,features,ids)
                    reference={r['window']['id']:r['output']['tokens'] for r in variants['cpu-sequential']}
                    mismatches=[]
                    for variant,rows in variants.items():
                        for row in rows:
                            if row['output']['tokens']!=reference[row['window']['id']]:mismatches.append([variant,row['window']['id']])
                            outputs.append(row|{'reader':key,'variant':variant,'device':gpu if variant=='accelerator-batch' else 'cpu'})
                    zero_features=calibration.transform(np.zeros_like(features[:1]))
                    zero=model.decode(zero_features)[0]
                    summaries.append({'reader':key,'token_mismatches':mismatches,'zero_activity_output':zero,
                        'late_window_output':variants['cpu-sequential'][-1]['output'],
                        'late_sensory_activation':{m:max(sum(n['activation'] for n in f['nodes'] if int(n['channel']) in set(read_json(OLD/'projection.json')[m]['excluded_channels'])) for f in selected[528]['trajectory']) for m in ('vision','words')}})
            print({'latency_seed':seed,'rows':len(outputs)},flush=True)
        write_gzip(WORK/'latency-output.json.gz',outputs)
        new_json(WORK/'latency-summary.json',{'rows':len(outputs),'readers':summaries,'gpu':gpu,
            'mismatches':sum(len(r['token_mismatches']) for r in summaries)})
        new_json(WORK/'timing/latency.json',{'wall_seconds':time.monotonic()-tick})
    finally:s.db.close()


if __name__=='__main__':main()
