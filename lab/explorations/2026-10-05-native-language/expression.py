"""Native trajectory datasets, frozen split manifests and external expression models."""
import argparse
import gzip
import json
import time
from types import SimpleNamespace

import numpy as np
import torch

from experiment import HERE, WORK, SEEDS, guard, study, read_json, new_json
from threemind_transformer.native_readout import NativeProjection, PrototypeLanguage
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.development_model import fit, load

REGIMES=('individual','shared','developmental','history-cold')


def dataset():
    projections={k:NativeProjection(**v) for k,v in read_json(WORK/'projection.json').items()}
    rows=[]
    for path in sorted((WORK/'cases').glob('*/result.json')):
        r=read_json(path)
        if r['kind']!='probe':
            continue
        with gzip.open(path.parent/'process.json.gz','rt',encoding='utf-8') as stream:
            process=json.load(stream)
        if int(process['end_us'])!=int(process['planned_end_us']):
            raise RuntimeError(f'incomplete observation: {path.parent.name}')
        projected=projections[r['modality']].project(process)
        rows.append({k:r[k] for k in ('source','seed','condition','seconds','modality','item','variant','intensity','split','target','intervention')} |
            {'id':path.parent.name,'text':r['target'],'projection':projected,'values':projected['values']})
    return rows,projections


def fit_rows(rows, calibration, basis):
    values=calibration.transform([row['values'] for row in rows]).tolist()
    result=[{'id':r['id'],'split':'train','values':v,'text':r['text']} for r,v in zip(rows,values,strict=True)]
    result.append({'id':'explicit-zero-activity','split':'train','values':calibration.transform(np.zeros((basis.bins,basis.width))).tolist(),'text':''})
    return result


def train():
    torch.set_num_threads(2)
    s=study()
    rows,projections=dataset()
    training=[r for r in rows if r['split']=='train' and r['condition']=='normal' and r['intervention']=='none']
    if any(sum(r['seed']==seed and r['modality']==modality for r in training)!=27
           for seed in SEEDS for modality in projections):
        raise RuntimeError('complete all registered training probes before fitting any shared model')
    models=WORK/'models';models.mkdir(exist_ok=True)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    try:
        for seed in SEEDS:
            for modality,projection in projections.items():
                own=[r for r in training if r['seed']==seed and r['modality']==modality]
                if len(own)!=27:
                    raise RuntimeError('all27 physical calibration probes per individual/modality required')
                for regime in REGIMES:
                    key=f'{regime}-s{seed}-{modality}'
                    if (models/f'{key}.json').exists():continue
                    guard(s,True);started=time.monotonic();s.active_case=SimpleNamespace(born_wall=started)
                    if regime=='shared':
                        selected=[r for r in training if r['seed']!=seed and r['modality']==modality and r['seconds']==266]
                        reference=selected
                    elif regime=='individual':
                        selected=reference=[r for r in own if r['seconds']==266]
                    else:
                        selected=own
                        reference=[r for r in own if r['seconds']==24]
                    calibration=FeatureCalibration.fit(reference)
                    manifest={'seed':seed,'modality':modality,'regime':regime,'training_ids':[r['id'] for r in selected],
                        'normalization_ids':[r['id'] for r in reference],'feature_calibration':calibration.to_dict(),
                        'projection':projection.to_dict(),'test_exposure':False,'no_question_or_assignment_input':True,
                        'adapter_role':'language-central-adapter','direction':'output','role_grants_core_privileges':False,
                        'input_wiring':71,'individual_binding':seed,'frozen_before_new_experience':True}
                    previous=None;receipts=[]
                    stages=(24,72,266) if regime=='developmental' else (266,)
                    for stage in stages:
                        training_rows=[r for r in selected if regime!='developmental' or r['seconds']<=stage]
                        converted=fit_rows(training_rows,calibration,projection.basis)
                        output=models/(f'{key}-t{stage}.safetensors' if regime=='developmental' else f'{key}.safetensors')
                        receipts.append(fit(converted,projection.basis,output,seed=seed+1009,steps=400 if regime=='developmental' else 1200,
                            batch_size=16,device=device,initial=previous,check=lambda:guard(s),checkpoints=()))
                        previous=output
                    prototype=PrototypeLanguage(fit_rows(selected,calibration,projection.basis))
                    raw=PrototypeLanguage([{'id':r['id'],'split':'train','values':r['values'],'text':r['text']} for r in selected])
                    new_json(models/f'{key}.json',manifest|{'checkpoint':previous.name,'receipts':receipts,
                        'prototype':prototype.to_dict(),'raw_prototype':raw.to_dict()})
                    new_json(WORK/'timing'/f'train-{key}.json',{'wall_seconds':time.monotonic()-started})
                    s.active_case=None
                    print(json.dumps({'trained':key,'seconds':round(time.monotonic()-started,1),
                        'final_loss':receipts[-1]['loss_samples'][-1]['loss']}),flush=True)
    finally:s.db.close()


def decode(tag, regimes=REGIMES, suffix=''):
    torch.set_num_threads(2);s=study();started=time.monotonic()
    s.active_case=SimpleNamespace(born_wall=started)
    rows,_=dataset();out=WORK/'decoded';out.mkdir(exist_ok=True)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    try:
        for seed in SEEDS:
            for modality in ('vision','words'):
                for regime in regimes:
                    key=f'{regime}-s{seed}-{modality}'
                    target=out/f'{tag}-{key}.json'
                    if target.exists():continue
                    manifest=read_json(WORK/'models'/f'{key}.json')
                    calibration=FeatureCalibration(**manifest['feature_calibration'])
                    model,_=load(WORK/'models'/manifest['checkpoint'],device)
                    proto=PrototypeLanguage.from_dict(manifest['prototype'])
                    raw=PrototypeLanguage.from_dict(manifest['raw_prototype'])
                    selected=[r for r in rows if r['seed']==seed and r['modality']==modality]
                    selected=[r for r in selected if (r['seconds']<=326 if tag=='initial' else r['seconds']>326)]
                    output=[]
                    for offset in range(0,len(selected),32):
                        batch=selected[offset:offset+32]
                        values=calibration.transform([r['values'] for r in batch])
                        generated=model.decode(values)
                        attention=proto.decode(values)
                        raw_attention=raw.decode([r['values'] for r in batch])
                        for r,g,p,a in zip(batch,generated,attention,raw_attention,strict=True):
                            output.append({k:v for k,v in r.items() if k not in ('values','projection')} |
                                {'transformer':g,'prototype':p,'raw_prototype':a,
                                 'magnitude':r['projection']['raw_sum'],'unknown_channels':r['projection']['unknown_channels']})
                        guard(s)
                    new_json(target,{'model':key,'rows':output,'training_ids':manifest['training_ids']})
                    del model
        new_json(WORK/'timing'/f'decoding-{tag}{suffix}.json',{'wall_seconds':time.monotonic()-started})
        print(json.dumps({'decoded':tag,'seconds':round(time.monotonic()-started,1)}),flush=True)
    finally:s.active_case=None;s.db.close()


def summarize():
    from collections import defaultdict
    result=[]
    for path in sorted((WORK/'decoded').glob('*.json')):
        source=read_json(path)
        regime=source['model'].split('-s')[0]
        groups=defaultdict(lambda:{'correct':0,'count':0,'blank':0})
        for r in source['rows']:
            for instrument in ('transformer','prototype','raw_prototype'):
                partition='calibration' if r['id'] in source['training_ids'] else r['split']
                key=(regime,r['seed'],r['modality'],r['condition'],r['seconds'],partition,r['item']<0,instrument)
                group=groups[key]
                group['count']+=1;group['correct']+=r[instrument]['text']==r['target'];group['blank']+=r[instrument]['text']==''
        result.extend(dict(zip(('regime','seed','modality','condition','seconds','partition','no_cue','instrument'),k,strict=True))|v
                      for k,v in groups.items())
    print(json.dumps(result,ensure_ascii=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=('train','initial','new-experience','summary'))
    args=parser.parse_args()
    if args.operation=='train':train()
    elif args.operation=='summary':summarize()
    else:decode(args.operation)
