"""Scratch expression on raw E47 processes, with no conversational cache."""
import argparse,time
from types import SimpleNamespace
import numpy as np
import torch
from raw_analysis import collect,instrument,values,summarize,FIELDSETS
from experiment import *
from threemind_transformer.development_model import fit,load

def recorded_rows():
    # All variants share these declared raw E47 samples. Cache them once,
    # retaining source paths, rather than repeatedly decompressing old evidence.
    path=WORK/'raw-word-features.npz'
    if path.exists():
        with np.load(path,allow_pickle=False) as data:
            metadata=json.loads(str(data['metadata']))
            all_values=data['all'];cross_values=data['cross']
        return [r|{'raw':{'all':all_values[i],'cross':cross_values[i]}} for i,r in enumerate(metadata)]
    rows=collect(OLD,old_data=True,modality='words')
    metadata=[{k:v for k,v in r.items() if k!='raw'} for r in rows]
    np.savez_compressed(path,metadata=json.dumps(metadata,ensure_ascii=False),
        all=np.asarray([r['raw']['all'] for r in rows],dtype=np.float32),
        cross=np.asarray([r['raw']['cross'] for r in rows],dtype=np.float32))
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scope',choices=('all','cross'),default='all')
    parser.add_argument('--fields',choices=('activity','history'),default='history')
    parser.add_argument('--shared',action='store_true')
    parser.add_argument('--steps',type=int,choices=(1200,6000),default=1200)
    parser.add_argument('--no-blank-supervision',action='store_true')
    parser.add_argument('--owners',type=int,nargs='+',choices=SEEDS,default=list(SEEDS));args=parser.parse_args()
    torch.set_num_threads(2);s=study();rows=recorded_rows();device='cuda' if torch.cuda.is_available() else 'cpu'
    folder=WORK/'raw-models';folder.mkdir(exist_ok=True)
    owners=('shared',) if args.shared else args.owners
    try:
        for seed in owners:
            for modality in ('words',):
                key=f'{seed}-{modality}-{args.fields}-{args.scope}'
                if args.steps!=1200:key+=f'-steps{args.steps}'
                if args.no_blank_supervision:key+='-unlabelled-no-cue'
                receipt=folder/f'{key}.json'
                if receipt.exists():continue
                own=[r for r in rows if r['modality']==modality and (seed=='shared' or r['seed']==seed)]
                train=[r for r in own if r['split']=='train' and r['condition'] in ('continued','reversal') and r['seconds']==532
                       and (seed!='shared' or r['seed'] in (223,251))]
                if args.no_blank_supervision:train=[r for r in train if r['item']>=0]
                test=[r for r in own if r['split']=='test']
                fields=FIELDSETS[args.fields];projection=instrument(modality,fields,args.scope)
                samples=[{'values':values(r,fields,args.scope),'text':r['target']} for r in train]
                path=folder/f'{key}.safetensors';tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
                metadata=fit(samples,projection.basis,path,seed=47,steps=args.steps,batch_size=16,device=device,
                             check=lambda:guard(s),checkpoints=())
                model,_=load(path,device);out=[]
                for start in range(0,len(test),16):
                    out.extend(model.decode(np.asarray([values(r,fields,args.scope) for r in test[start:start+16]],dtype=np.float32)))
                learned=model.decode(np.asarray([r['values'] for r in samples],dtype=np.float32))
                baseline={(r['seed'],r['condition'],r['seconds']):o['text'] for r,o in zip(test,out) if r['item']<0}
                details=[{k:r[k] for k in ('seed','condition','seconds','item','target','variant','modality','evidence')}|
                         {'output':o['text'],'tokens':o['tokens'],'correct':r['item']>=0 and o['text']==r['target']
                          and o['text']!=baseline[(r['seed'],r['condition'],r['seconds'])]} for r,o in zip(test,out)]
                result={'owner':seed,'scope':args.scope,'fields':args.fields,'projection':projection.to_dict(),
                        'no_cue_blank_supervision':not args.no_blank_supervision,
                        'normalization':'none','subtraction':False,'cache':False,'metadata':metadata,
                        'fit_correct':sum(a['text']==b['text'] for a,b in zip(learned,samples)), 'fit_count':len(samples),
                        'rows':details,'summary':summarize(details,('seed','condition','seconds','modality'))}
                new_json(receipt,result);new_json(WORK/'timing'/f'model-{key}.json',{'wall_seconds':time.monotonic()-tick})
                s.active_case=None;guard(s,True);print({'model':key,'fit':(result['fit_correct'],len(samples)),
                    'summary':[r for r in result['summary'] if r['seconds']==592]},flush=True)
                del model
                if torch.cuda.is_available():torch.cuda.empty_cache()
    finally:s.active_case=None;s.db.close()

if __name__=='__main__':main()
