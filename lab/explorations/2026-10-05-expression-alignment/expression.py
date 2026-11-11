"""Frozen output training with explicit exclusion of held-out cyclic assignments."""
import argparse
import json
import time
from types import SimpleNamespace
import numpy as np
import torch
from experiment import WORK,OLD,study,guard,new_json,read_json,write_gzip
from features import index_cases,preceding,load_process,observation
from new_experience import NEW_SEEDS
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.native_readout import PrototypeLanguage
from threemind_transformer.development_model import fit,load
from lab.tools.expression_observation import decode_timed
from lab.tools.expression_observation import ExpressionObservation


def instrument_for(modality,selection,scope):
    instrument=observation(modality,selection['mode'])
    if scope=='cross':return instrument
    config=dict(instrument.projection)
    config['channels']=sorted(set(config['channels'])|set(config['excluded_channels']))
    config['excluded_channels']=[]
    return ExpressionObservation(config,instrument.mode,instrument.fields)


def collect(s,selection,scope='cross'):
    index=index_cases();rows=[];mode=selection['mode']
    for seed in NEW_SEEDS:
        for condition in ('normal','continued','reversal','cycle1','cycle2','frozen'):
            for seconds in ((266,326) if condition=='normal' else (266,) if condition=='frozen' else (532,592)):
                previous=preceding(WORK/'cases'/f's{seed}-{condition}',seconds) if mode=='preceding' else None
                for modality in ('vision','words'):
                    guard(s)
                    selected=[(p,r) for key,(p,r) in index.items() if key[:4]==(seed,condition,seconds,modality)]
                    if len(selected)!=(14 if modality=='words' else 18) and condition!='frozen':
                        # vision has9 train+9 test; words9 train+5 test.
                        raise ValueError(f'incomplete source probes: {seed} {condition} {seconds} {modality} {len(selected)}')
                    baseline=load_process(index[(seed,condition,seconds,modality,-1,0,.5,'test')][0]/'process.json.gz')
                    instrument=instrument_for(modality,selection,scope)
                    for path,row in selected:
                        process=load_process(path/'process.json.gz')
                        feature=instrument.project(process,baseline if mode.startswith('paired') else previous if mode=='preceding' else None)
                        rows.append({k:row[k] for k in ('seed','condition','seconds','modality','item','variant','intensity','split','target')}|
                                    {'id':path.name,'values':feature['values'],'contrast_magnitude':feature['contrast_magnitude'],
                                     'start_us':process['start_us'],'end_us':process['end_us']})
    write_gzip(WORK/('new-features.json.gz' if scope=='cross' else 'all-features.json.gz'),rows)
    return rows


def train_and_decode(s,rows,selection,scope='cross'):
    models=WORK/('models' if scope=='cross' else 'all-models');models.mkdir(exist_ok=True)
    device='cuda' if torch.cuda.is_available() else 'cpu';results=[]
    for seed in NEW_SEEDS:
        for modality in ('vision','words'):
            instrument=instrument_for(modality,selection,scope)
            own=[r for r in rows if r['seed']==seed and r['modality']==modality]
            for regime in ('identity','two-assignments'):
                key=f'{regime}-s{seed}-{modality}';out=WORK/('decoded' if scope=='cross' else 'all-decoded')/f'{key}.json'
                if out.exists():results.extend(read_json(out));continue
                started=time.monotonic();guard(s,True);s.active_case=SimpleNamespace(born_wall=started)
                conditions=('normal','continued') if regime=='identity' else ('normal','continued','reversal')
                selected=[r for r in own if r['split']=='train' and r['condition'] in conditions]
                if any(r['condition'].startswith('cycle') for r in selected):raise ValueError('held-out assignment leakage')
                training=[{'id':r['id'],'values':r['values'],'text':r['target'],'split':'train'} for r in selected]
                # Optimizer conditioning remains training-only, as in E46.
                # The finite cosine control retains B's separately selected
                # raw/conditioned geometry; it is not changed to match the LM.
                calibration=FeatureCalibration.fit(training)
                converted=[r|{'values':calibration.transform(r['values']).tolist()} for r in training]
                converted.append({'id':'explicit-zero','values':calibration.transform(np.zeros((instrument.basis.bins,instrument.basis.width))).tolist(),'text':'','split':'train'})
                checkpoint=models/f'{key}.safetensors'
                meta_path=models/f'{key}.json'
                if not meta_path.exists():
                    receipt=fit(converted,instrument.basis,checkpoint,seed=seed+1009,steps=2400,batch_size=16,device=device,
                                checkpoints=(),check=lambda:guard(s))
                    prototype=PrototypeLanguage(converted if selection['calibrate'] else training)
                    new_json(meta_path,{'schema':'E47-expression/1','checkpoint':checkpoint.name,
                        'observation':instrument.to_dict(),'feature_calibration':calibration.to_dict(),
                        'training_ids':[r['id'] for r in selected],'training_conditions':conditions,
                        'held_out_assignments':['cycle1','cycle2'],'instance_seed':seed,'modality':modality,'regime':regime,
                        'receipt':receipt,'prototype':prototype.to_dict(),'prototype_uses_conditioning':selection['calibrate'],
                        'scope':scope,'core_gradients':False,'role':'observer-interpretation'})
                manifest=read_json(meta_path);model,_=load(checkpoint,device)
                prototype=PrototypeLanguage.from_dict(manifest['prototype'])
                outputs=[]
                for start in range(0,len(own),32):
                    guard(s);batch=own[start:start+32]
                    values=calibration.transform([r['values'] for r in batch])
                    generated=decode_timed(model,values,[{'id':r['id'],'start_us':r['start_us'],'end_us':r['end_us']} for r in batch])
                    finite=prototype.decode(values if manifest['prototype_uses_conditioning'] else [r['values'] for r in batch])
                    for row,g,p in zip(batch,generated,finite,strict=True):
                        outputs.append({k:v for k,v in row.items() if k!='values'}|{'regime':regime,'transformer':g,
                            'prototype':p,'decoder_training':row['id'] in manifest['training_ids']})
                new_json(out,outputs);results.extend(outputs)
                new_json(WORK/'timing'/f'{scope}-expression-{key}.json',{'wall_seconds':time.monotonic()-started})
                s.active_case=None
                print(json.dumps({'expression':key,'rows':len(outputs),'loss':manifest['receipt']['loss_samples'][-1]['loss']}),flush=True)
    return results


def summarize(rows,scope='cross'):
    summaries=[]
    for seed in NEW_SEEDS:
        for modality in ('vision','words'):
            for regime in ('identity','two-assignments'):
                for condition in ('normal','continued','reversal','cycle1','cycle2','frozen'):
                    for seconds in ((266,326) if condition=='normal' else (266,) if condition=='frozen' else (532,592)):
                        group=[r for r in rows if (r['seed'],r['modality'],r['regime'],r['condition'],r['seconds'])==(seed,modality,regime,condition,seconds) and r['split']=='test']
                        for kind in ('transformer','prototype'):
                            text=lambda r:r[kind]['output']['text'] if kind=='transformer' else r[kind]['text']
                            baseline=next(text(r) for r in group if r['item']==-1)
                            cues=[r for r in group if r['item']>=0]
                            summaries.append({'seed':seed,'modality':modality,'regime':regime,'condition':condition,'seconds':seconds,'instrument':kind,
                                'total':len(cues),'correct':sum(text(r)==r['target'] for r in cues),
                                'cue_specific':sum(text(r)==r['target'] and text(r)!=baseline for r in cues),'no_cue_output':baseline})
    gates=[]
    for kind in ('transformer','prototype'):
        for regime in ('identity','two-assignments'):
            for modality in ('vision','words'):
                for seconds in (532,592):
                    passed=[]
                    for seed in NEW_SEEDS:
                        pair=[r for r in summaries if (r['seed'],r['regime'],r['modality'],r['seconds'],r['instrument'])==(seed,regime,modality,seconds,kind) and r['condition'] in ('cycle1','cycle2')]
                        if len(pair)==2 and all(r['cue_specific']/r['total']>=.75 for r in pair):passed.append(seed)
                    gates.append({'instrument':kind,'regime':regime,'modality':modality,'seconds':seconds,'passing_seeds':passed,'passed':len(passed)>=2})
    result={'summaries':summaries,'gates':gates}
    new_json(WORK/('new-expression-summary.json' if scope=='cross' else 'all-expression-summary.json'),result)
    print(json.dumps({'gates':gates}),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=('features','train'))
    parser.add_argument('--scope',choices=('cross','all'),default='cross')
    args=parser.parse_args();torch.set_num_threads(2);s=study();tick=time.monotonic()
    try:
        selection=read_json(WORK/'feature-summary.json')['selected']
        if selection is None:raise RuntimeError('registered expansion gate not met')
        if args.operation=='features':
            s.active_case=SimpleNamespace(born_wall=tick);collect(s,selection,args.scope)
            new_json(WORK/'timing'/f'{args.scope}-new-features.json',{'wall_seconds':time.monotonic()-tick})
        else:
            rows=load_process(WORK/('new-features.json.gz' if args.scope=='cross' else 'all-features.json.gz'))
            summarize(train_and_decode(s,rows,selection,args.scope),args.scope)
    finally:s.db.close()


if __name__=='__main__':main()
