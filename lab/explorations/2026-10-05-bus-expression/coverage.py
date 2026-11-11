"""Same raw states, expanded observable teaching for an external decoder."""
import argparse
from common import *
from lab.tools.expression_calibration import fit_raw
from lab.tools.raw_state_expression import RawStateProjection

def run(owner,regime,initial=None):
    torch.set_num_threads(2);s=study();guard(s,True)
    key=f's{owner}-{regime}'+('-continued' if initial else '')
    folder=WORK/'models';folder.mkdir(exist_ok=True)
    if (folder/f'{key}.json').exists():s.db.close();return
    own=[r for r in rows() if r['seed']==owner and r['modality']=='words']
    conditions={('continued',592),('reversal',592)} if regime=='late' else (
        {('normal',266),('normal',326),('continued',532),('continued',592),('reversal',532),('reversal',592)} if regime=='times' else
        {('continued',532),('reversal',532),('cycle1',532)})
    train=[r for r in own if r['split']=='train' and r['item']>=0 and (r['condition'],r['seconds']) in conditions]
    test=[r for r in own if r['split']=='test']
    projection=RawStateProjection(**read_json(PREVIOUS/'raw-models/223-words-history-all.json')['projection'])
    tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    try:
        model,meta=fit_raw([{'values':r['values'],'text':r['target']} for r in train],projection.basis,
            folder/f'{key}.safetensors',steps=8000,full_batch=True,initial=initial,device=device,check=lambda:guard(s))
        fit=model.decode(np.asarray([r['values'] for r in train],dtype=np.float32));out=[]
        for i in range(0,len(test),16):out.extend(model.decode(np.asarray([r['values'] for r in test[i:i+16]],dtype=np.float32)))
        details=[{k:r[k] for k in ('seed','condition','seconds','item','target','variant','evidence')}|
            {'output':o['text'],'tokens':o['tokens'],'terminated':o['terminated']} for r,o in zip(test,out)]
        result={'owner':owner,'regime':regime,'teaching_conditions':sorted(conditions),'projection':projection.to_dict(),'metadata':meta,
            'fit_correct':sum(r['target']==o['text'] for r,o in zip(train,fit)),'fit_count':len(train),
            'training_outputs':[{'target':r['target'],'output':o['text'],'evidence':r['evidence']} for r,o in zip(train,fit)],
            'rows':details,'summary':summary(details)}
        new_json(folder/f'{key}.json',result);new_json(WORK/'timing'/f'{key}.json',{'wall_seconds':time.monotonic()-tick})
        print({'model':key,'fit':[result['fit_correct'],len(train)],'summary':result['summary']},flush=True)
    finally:s.active_case=None;s.db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('regime',choices=('late','times','correction'))
    p.add_argument('--owner',type=int,default=223);p.add_argument('--initial',type=Path);args=p.parse_args()
    run(args.owner,args.regime,args.initial)
