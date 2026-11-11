"""One bounded all-recorded-sample decoder control; no dynamics changes."""
import numpy as np
from types import SimpleNamespace
from experiment import *
from raw_transformer import recorded_rows
from raw_analysis import load_process,instrument,FIELDSETS,summarize
from lab.tools.raw_state_expression import ridge_fit,ridge_predict
from threemind_transformer.development_model import fit,load


def main():
    torch.set_num_threads(2);s=study();all_rows=recorded_rows();folder=WORK/'raw-models'
    try:
        for seed in SEEDS:
            key=f'{seed}-words-history-all-samples101';receipt=folder/f'{key}.json'
            if receipt.exists():
                if read_json(receipt)['fit_correct']<17:break
                continue
            rows=[r for r in all_rows if r['seed']==seed and r['condition'] in ('continued','reversal','cycle1','cycle2') and r['seconds'] in (532,592)]
            spec=instrument('words',FIELDSETS['history'],'all',samples=101)
            for r in rows:r['values']=spec.project(load_process(ROOT/r['evidence']/'process.json.gz'))['values']
            train=[r for r in rows if r['split']=='train' and r['condition'] in ('continued','reversal') and r['seconds']==532]
            test=[r for r in rows if r['split']=='test'];tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
            linear=ridge_fit(train);linear_fit=ridge_predict(linear,[r['values'] for r in train]);linear_test=ridge_predict(linear,[r['values'] for r in test])
            path=receipt.with_suffix('.safetensors');device='cuda' if torch.cuda.is_available() else 'cpu'
            meta=fit([{'values':r['values'],'text':r['target']} for r in train],spec.basis,path,seed=47,steps=1200,batch_size=16,
                     device=device,check=lambda:guard(s),checkpoints=())
            model,_=load(path,device);fitted=model.decode(np.asarray([r['values'] for r in train],dtype=np.float32));out=[]
            for i in range(0,len(test),8):out.extend(model.decode(np.asarray([r['values'] for r in test[i:i+8]],dtype=np.float32)))
            baseline={(r['condition'],r['seconds']):o['text'] for r,o in zip(test,out) if r['item']<0}
            details=[{k:r[k] for k in ('seed','condition','seconds','item','target','modality','evidence')}|
                {'output':o['text'],'linear_output':lin,'correct':r['item']>=0 and o['text']==r['target'] and o['text']!=baseline[(r['condition'],r['seconds'])]}
                for r,o,lin in zip(test,out,linear_test)]
            result={'owner':seed,'fields':'history','scope':'all','projection':spec.to_dict(),'metadata':meta,
                'fit_correct':sum(r['target']==o['text'] for r,o in zip(train,fitted)),'fit_count':len(train),
                'linear_fit_correct':sum(r['target']==o for r,o in zip(train,linear_fit)),
                'rows':details,'summary':summarize(details,('condition','seconds','modality'))}
            new_json(receipt,result);new_json(WORK/'timing'/f'model-{key}.json',{'wall_seconds':time.monotonic()-tick})
            s.active_case=None;print({'trajectory':seed,'fit':result['fit_correct'],'linear_fit':result['linear_fit_correct']},flush=True)
            if result['fit_correct']<17:break
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':main()
