"""Full-state follow-up on immutable old naming branches, raw units only."""
import argparse,time
from types import SimpleNamespace
import numpy as np
import torch
from experiment import *
from raw_analysis import load_process,summarize
from lab.tools.raw_state_expression import RawGraphStateProjection,load_graph_expression
from threemind_transformer.development_model import fit

CONDITIONS=('continued','reversal','cycle1','cycle2')

def capture(s,a):
    # Preserve the old mapping targets by using the recorded assignment.
    for seed in SEEDS:
        for condition in CONDITIONS:
            parent=OLD/'cases'/f's{seed}-{condition}'
            assignment=read_json(parent/'definition.json')['assignment']
            for seconds in (532,592):
                for split in ('train','test'):
                    if split=='train' and seconds!=532:continue
                    choices=[(-1,0,.5)]
                    choices += [(item,view,strength) for item in range(4) for view,strength in
                                (((8,.4),(10,.6)) if split=='train' else ((9,.5),))]
                    for item,view,strength in choices:
                        key=f'graph-{parent.name}-t{seconds}-item{item}-v{view}-i{strength}-{split}'
                        path,tick=start(s,key)
                        if tick is None:continue
                        checkpoint=parent/f'checkpoint-{seconds}';value=old.e45.previous.restore(checkpoint,71)
                        cursor=read_json(checkpoint/'summary.json')['cursor']
                        if item>=0:
                            frames=[{'stimulus':replace(a.world.frame(a.world.sample(item,view)),intensity=strength),'labels':{}}]
                            value.reader.schedule(frames,source='E48-state-probe',adapter_id='temporal-state-study/1')
                        until=value.engine.time_us+2000000
                        RecordedBackground(WORK/'physical-telemetry.jsonl').queue_before(value.reader,cursor,until)
                        write_gzip(path/'process.json.gz',observe(value,until,s,True))
                        finish(s,path,tick,{'kind':'graph-probe','seed':seed,'condition':condition,'seconds':seconds,'item':item,
                            'variant':view,'intensity':strength,'split':split,'target':old.NAMES[assignment.index(item)]+'。' if item>=0 else '',
                            'modality':'words','source':parent.name,'life':value.engine.life})
            print({'full_state_captured':parent.name},flush=True)

def train(s,graph=True):
    directory=WORK/'graph-models';directory.mkdir(exist_ok=True)
    p=read_json(WORK/'projection.json')['words'];channels=tuple(sorted(set(p['channels'])|set(p['excluded_channels'])))
    projection=RawGraphStateProjection(channels,graph)
    device='cuda' if torch.cuda.is_available() else 'cpu'
    for seed in SEEDS:
        key=f'{seed}-'+('graph' if graph else 'node')
        if (directory/f'{key}.json').exists():continue
        tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick);rows=[]
        for path in sorted((WORK/'cases').glob(f'graph-s{seed}-*/result.json')):
            meta=read_json(path)
            process=load_process(path.parent/'process.json.gz')
            rows.append(meta|{'values':projection.project(process),'evidence':str(path.parent.relative_to(ROOT))})
        teaching=[r for r in rows if r['split']=='train' and r['condition'] in ('continued','reversal')]
        test=[r for r in rows if r['split']=='test']
        if len(teaching)!=18:raise ValueError('registered train partition incomplete')
        path=directory/f'{key}.safetensors'
        meta=fit([{'values':r['values'],'text':r['target']} for r in teaching],projection.basis,path,
                 seed=47,steps=1200,batch_size=8,device=device,check=lambda:guard(s),checkpoints=())
        model,_=load_graph_expression(path,device)
        out=[]
        for i in range(0,len(test),8):out.extend(model.decode(np.stack([r['values'] for r in test[i:i+8]])))
        fitted=model.decode(np.stack([r['values'] for r in teaching]))
        baseline={(r['condition'],r['seconds']):o['text'] for r,o in zip(test,out) if r['item']<0}
        details=[{k:r[k] for k in ('seed','condition','seconds','item','modality','target','variant','evidence')}|
                 {'output':o['text'],'tokens':o['tokens'],'correct':r['item']>=0 and o['text']==r['target']
                  and o['text']!=baseline[(r['condition'],r['seconds'])]} for r,o in zip(test,out)]
        result={'projection':projection.to_dict(),'metadata':meta,'owner':seed,'scope':'all','normalization':'none','subtraction':False,
                'fit_correct':sum(a['text']==b['target'] for a,b in zip(fitted,teaching)),'fit_count':len(teaching),
                'rows':details,'summary':summarize(details,('condition','seconds','modality'))}
        new_json(directory/f'{key}.json',result);new_json(WORK/'timing'/f'model-{key}.json',{'wall_seconds':time.monotonic()-tick})
        s.active_case=None;guard(s,True);print({'model':key,'fit':(result['fit_correct'],len(teaching)),'summary':result['summary']},flush=True)
        del model,rows,teaching,test
        if torch.cuda.is_available():torch.cuda.empty_cache()

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=('capture','node','graph'));args=p.parse_args()
    torch.set_num_threads(2);s=study()
    try:
        if args.operation=='capture':capture(s,adapter())
        else:train(s,args.operation=='graph')
    finally:s.active_case=None;s.db.close()

if __name__=='__main__':main()
