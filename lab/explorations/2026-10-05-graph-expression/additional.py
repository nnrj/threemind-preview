"""Offline frozen decoding only. May run after the Core-case budget is full."""
import collections,psutil
from common import *
from multiview import rows,representation,sensory,consistency
from threemind_transformer.graph_expression import load


def main():
    torch.set_num_threads(2);start=time.monotonic();device='cuda' if torch.cuda.is_available() else 'cpu'
    completed=sum(read_json(p).get('wall_seconds',0) for base in (FIRST,WORK) for kind in ('cases','timing')
        for p in ((base/kind).glob('*/result.json') if kind=='cases' else (base/kind).glob('*.json')))
    def check():
        if time.monotonic()-start>600 or completed+time.monotonic()-start>14400:raise RuntimeError('offline time budget')
        if psutil.Process().memory_info().rss>4*2**30 or psutil.virtual_memory().available<2*2**30:raise RuntimeError('offline memory reserve')
        if read_json(WORK/'usage.json')['used_percent']>=59:raise RuntimeError('account budget')
    evaluations={}
    jobs=[('cycle-early','multi-s223-local',223,('cycle1','no-learning')),
          ('cycle-followed','multi-s223-local-late-follow',223,('cycle1',)),
          ('s223-reader-on-s279','multi-s223-local',279,('continued','reversal')),
          ('s279-reader-on-s223','multi-s279-local',223,('continued','reversal'))]
    for name,key,owner,conditions in jobs:
        check();model,_=load(WORK/'models'/f'{key}.safetensors',device)
        items=[r for r in rows(owner) if r['split']=='test' and r['condition'] in conditions];out=[]
        if not items:raise ValueError('registered additional observations missing')
        for i in range(0,len(items),4):
            check();part=items[i:i+4];decoded=model.decode([representation(r,'local') for r in part])
            out.extend({k:r[k] for k in ('owner','condition','seconds','item','target','perspective','view','split')}|
                {'output':o['text'],'tokens':o['tokens'],'evidence':r['path']} for r,o in zip(part,decoded))
        evaluations[name]={'rows':out,'summary':scores(out,('condition','seconds','perspective')),'consistency':consistency(out)}
        print({'frozen':name,'summary':scores(out,('condition','seconds'))},flush=True)
    groups={};test=[r for r in rows(223) if r['split']=='test' and r['item']>=0 and r['condition'] in ('continued','reversal')]
    for r in test:
        signature=json.dumps(sensory(r),sort_keys=True,separators=(',',':'))
        groups.setdefault(signature,collections.Counter())[r['target']]+=1
    result={'evaluations':evaluations,'sensory_only_ceiling':{'maximum_correct':sum(max(c.values()) for c in groups.values()),
        'count':len(test),'distinct_actual_inputs':len(groups),'inference':'identical current cue inputs have conflicting teaching-history targets'},
        'wall_seconds':time.monotonic()-start}
    new_json(WORK/'additional-tests.json',result);new_json(WORK/'timing/additional.json',{'wall_seconds':result['wall_seconds']})


if __name__=='__main__':main()
