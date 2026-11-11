"""Train candidate expression tools on fixed, labelled teaching evidence only."""
import argparse
from common import *
from lab.tools.expression_calibration import fit_raw,fit_classifier
from lab.tools.raw_state_expression import RawStateProjection

VARIANTS={'random-default':{'learning_rate':.001},'random-small-lr':{'learning_rate':.0001},
    'balanced':{'learning_rate':.001,'full_batch':True},
    'balanced-small-lr':{'learning_rate':.0001,'full_batch':True},
    'balanced-small-init':{'learning_rate':.001,'full_batch':True,'prefix_initial_gain':.01}}

def run(owner,variant,steps=8000,initial=None):
    torch.set_num_threads(2);s=study();guard(s,True)
    folder=WORK/'models';folder.mkdir(exist_ok=True)
    key=f's{owner}-{variant}'+('-continued' if initial else '')
    if (folder/f'{key}.json').exists():s.db.close();return
    if len(list(folder.glob('*.safetensors')))>=24:raise RuntimeError('model cap')
    train,test=partitions(owner);samples=[{'values':r['values'],'text':r['target']} for r in train]
    layout=read_json(PREVIOUS/'raw-models/223-words-history-all.json')['projection']
    projection=RawStateProjection(**layout);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    path=folder/f'{key}.safetensors'
    try:
        model,meta=fit_raw(samples,projection.basis,path,steps=steps,device=device,initial=initial,check=lambda:guard(s),**VARIANTS[variant])
        fit=model.decode(np.asarray([r['values'] for r in train],dtype=np.float32))
        out=[]
        for i in range(0,len(test),16):
            guard(s);out.extend(model.decode(np.asarray([r['values'] for r in test[i:i+16]],dtype=np.float32)))
        details=[{k:r[k] for k in ('seed','condition','seconds','item','target','variant','evidence')}|
                 {'output':o['text'],'tokens':o['tokens'],'terminated':o['terminated']} for r,o in zip(test,out)]
        result={'owner':owner,'variant':variant,'projection':projection.to_dict(),'metadata':meta,
            'fit_correct':sum(o['text']==r['target'] for o,r in zip(fit,train)),'fit_count':len(train),
            'training_outputs':[{'target':r['target'],'output':o['text'],'evidence':r['evidence']} for r,o in zip(train,fit)],
            'rows':details,'summary':summary(details)}
        new_json(folder/f'{key}.json',result);new_json(WORK/'timing'/f'{key}.json',{'wall_seconds':time.monotonic()-tick})
        print({'model':key,'fit':result['fit_correct'],'summary':result['summary']},flush=True)
    finally:s.active_case=None;s.db.close()

def diagnostic():
    torch.set_num_threads(2);s=study();tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    try:
        train,test=partitions(223);samples=[{'values':r['values'],'text':r['target']} for r in train]
        device='cuda' if torch.cuda.is_available() else 'cpu'
        model,labels,history=fit_classifier(samples,device=device,check=lambda:guard(s))
        values=torch.tensor(np.asarray([r['values'] for r in test]),device=device,dtype=torch.float32).flatten(1)
        with torch.no_grad():out=[labels[i] for i in model(values).argmax(-1).tolist()]
        details=[{k:r[k] for k in ('condition','seconds','item','target','evidence')}|{'output':o} for r,o in zip(test,out)]
        new_json(HERE/'classifier-diagnostic.json',{'history':history,'rows':details,'summary':summary(details),
            'scope':'calibration and separability diagnostic, not language'} )
        new_json(WORK/'timing'/'classifier.json',{'wall_seconds':time.monotonic()-tick})
        print({'classifier_fit':history[-1],'summary':summary(details)},flush=True)
    finally:s.active_case=None;s.db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('variant',choices=(*VARIANTS,'classifier'))
    p.add_argument('--owner',type=int,choices=(223,251,279),default=223);p.add_argument('--steps',type=int,default=8000)
    p.add_argument('--initial',type=Path);args=p.parse_args()
    diagnostic() if args.variant=='classifier' else run(args.owner,args.variant,args.steps,args.initial)
