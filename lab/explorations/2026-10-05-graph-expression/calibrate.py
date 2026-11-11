"""Old evidence, new graph reader. No new Core simulation or hidden targets."""
import argparse
from dataclasses import replace
from common import *
from threemind_runtime.graph_observation import graph_process
from threemind_transformer.graph_expression import GraphExpressionConfig,fit


def old_rows(owner):
    rows=[]
    for path in sorted((E48/'cases').glob(f'graph-s{owner}-*/result.json')):
        r=read_json(path)
        if r['split']=='train' and (r['condition'] not in ('continued','reversal') or r['item']<0):continue
        if r['split']=='train' and r['seconds']!=532:continue
        rows.append(r|{'path':str(path.parent/'process.json.gz')})
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--owner',type=int,choices=(223,279),default=223)
    p.add_argument('--nodes-only',action='store_true');p.add_argument('--rate',type=float,choices=(.001,.0003),default=.001)
    args=p.parse_args();torch.set_num_threads(2);s=study();guard(s,True)
    key=f's{args.owner}-'+('nodes' if args.nodes_only else 'graph')+('-slow' if args.rate==.0003 else '')
    folder=WORK/'models';folder.mkdir(exist_ok=True)
    if (folder/f'{key}.json').exists():s.db.close();return
    tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    try:
        rows=old_rows(args.owner);training=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='test']
        if len(training)!=16:raise ValueError('frozen calibration partition')
        samples=[{'process':graph_process(process(r['path'])),'text':r['target']} for r in training]
        cfg=GraphExpressionConfig(use_edges=not args.nodes_only)
        model,meta=fit(samples,folder/f'{key}.safetensors',config=cfg,learning_rate=args.rate,
                       device='cuda' if torch.cuda.is_available() else 'cpu',check=lambda:guard(s))
        fitted=[]
        for i in range(0,len(samples),4):fitted.extend(model.decode([r['process'] for r in samples[i:i+4]]))
        details=[]
        for i in range(0,len(test),4):
            guard(s);part=test[i:i+4];out=model.decode([graph_process(process(r['path'])) for r in part])
            details.extend({k:r[k] for k in ('seed','condition','seconds','item','target','variant')}|
                           {'output':o['text'],'tokens':o['tokens'],'evidence':r['path']} for r,o in zip(part,out))
        result={'owner':args.owner,'use_edges':cfg.use_edges,'metadata':meta,'fit_correct':sum(r['text']==o['text'] for r,o in zip(samples,fitted)),
                'fit_count':len(samples),'rows':details,'summary':scores(details)}
        new_json(folder/f'{key}.json',result);new_json(WORK/'timing'/f'{key}.json',{'wall_seconds':time.monotonic()-tick})
        print({'model':key,'fit':result['fit_correct'],'summary':result['summary']},flush=True)
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':main()
