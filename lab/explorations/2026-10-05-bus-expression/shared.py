from common import *
from lab.tools.expression_calibration import fit_raw
from lab.tools.raw_state_expression import RawStateProjection

def run():
    torch.set_num_threads(2);s=study();guard(s,True);folder=WORK/'models';key='shared-balanced'
    teaching=[];test=[]
    for owner in (223,251,279):
        train,part=partitions(owner)
        if owner!=279:teaching.extend(train)
        test.extend(part)
    projection=RawStateProjection(**read_json(PREVIOUS/'raw-models/223-words-history-all.json')['projection'])
    tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    try:
        model,meta=fit_raw([{'values':r['values'],'text':r['target']} for r in teaching],projection.basis,
            folder/f'{key}.safetensors',full_batch=True,device='cuda' if torch.cuda.is_available() else 'cpu',check=lambda:guard(s))
        fitted=model.decode(np.asarray([r['values'] for r in teaching],dtype=np.float32));out=[]
        for i in range(0,len(test),16):out.extend(model.decode(np.asarray([r['values'] for r in test[i:i+16]],dtype=np.float32)))
        details=[{k:r[k] for k in ('seed','condition','seconds','item','target','evidence')}|{'output':o['text'],'tokens':o['tokens']} for r,o in zip(test,out)]
        result={'owner':'shared','teaching_sources':[223,251],'heldout_source':279,'projection':projection.to_dict(),'metadata':meta,
            'fit_correct':sum(r['target']==o['text'] for r,o in zip(teaching,fitted)),'fit_count':len(teaching),
            'rows':details,'summary_by_source':{str(owner):summary([r for r in details if r['seed']==owner]) for owner in (223,251,279)}}
        new_json(folder/f'{key}.json',result);new_json(WORK/'timing'/f'{key}.json',{'wall_seconds':time.monotonic()-tick})
        print({'shared_fit':result['fit_correct'],'results':result['summary_by_source']},flush=True)
    finally:s.active_case=None;s.db.close()
if __name__=='__main__':run()
