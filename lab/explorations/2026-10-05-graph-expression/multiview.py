"""Frozen common-reference tests; labels exist only in external teaching records."""
import argparse,random
from dataclasses import replace
from common import *
from threemind_runtime.graph_observation import graph_process,VERSION,EDGE_FIELDS
from threemind_transformer.graph_expression import GraphExpressionConfig,fit,load
from local_activity import local_process,FIELDS,POLICY


def rows(owner):
    result=[]
    for base in (FIRST,WORK):
        for path in sorted((base/'cases').glob(f's{owner}-multi-*/result.json')):
            row=read_json(path)
            if row.get('kind')=='probe':result.append(row|{'path':str(path.parent/'process.json.gz')})
    return result


def sensory(row):
    # Only what the input bus receives for this cue. No Core/history identity.
    combined={}
    for frame in row['delivered']:
        if int(frame['time_us'])!=0:raise ValueError('sensory baseline requires this registered same-time cue')
        for channel,amount in frame['channels']:
            combined[int(channel)]=combined.get(int(channel),0.)+float(amount)*frame['intensity']
    nodes=[{'id':str(c),'channel':c,'values':[v]} for c,v in sorted(combined.items())]
    return {'schema':VERSION,'node_fields':['amount'],'edge_fields':list(EDGE_FIELDS),
        'start_us':'0','end_us':'2000000','frames':[
            {'time_us':'0','nodes':nodes,'edges':[]},
            {'time_us':'2000000','nodes':[],'edges':[]}]}


def representation(row,mode):
    if mode=='sensory':return sensory(row)
    raw=process(row['path'])
    return local_process(raw,edges=mode=='localgraph') if mode.startswith('local') or mode=='random' else graph_process(raw)


def evaluate(model,items,mode,s):
    output=[]
    for i in range(0,len(items),4):
        guard(s);part=items[i:i+4];generated=model.decode([representation(r,mode) for r in part])
        output.extend({k:r[k] for k in ('owner','condition','seconds','item','target','perspective','view','split')}|
            {'output':o['text'],'tokens':o['tokens'],'evidence':r['path']} for r,o in zip(part,generated))
    return output


def consistency(items):
    groups={}
    for r in items:
        if r['item']<0:continue
        groups.setdefault((r['condition'],r['seconds'],r['item']),[]).append(r)
    return [{'condition':k[0],'seconds':k[1],'item':k[2],'count':len(v),
        'all_agree':len({r['output'] for r in v})==1,'all_correct':all(r['output']==r['target'] for r in v),
        'outputs':[r['output'] for r in v]} for k,v in groups.items()]


def main():
    p=argparse.ArgumentParser();p.add_argument('--owner',type=int,choices=(223,279),default=223)
    p.add_argument('--mode',choices=('local','localgraph','graph','nodes','sensory','random'),default='local')
    p.add_argument('--continue-from',type=Path);p.add_argument('--late',action='store_true')
    args=p.parse_args();torch.set_num_threads(2);s=study();guard(s,True)
    key=f'multi-s{args.owner}-{args.mode}'+('-late' if args.late else '')+('-follow' if args.continue_from else '')
    folder=WORK/'models';folder.mkdir(exist_ok=True)
    if (folder/f'{key}.json').exists():s.db.close();return
    tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    try:
        all_rows=rows(args.owner);training=[r for r in all_rows if r['split']=='train']
        testing=[r for r in all_rows if r['split']=='test']
        if len(training)!=32:raise ValueError('32 fixed common-reference training observations required')
        if args.late:
            # Teaching-derived targets on late, previously registered probe stimuli;
            # late training is explicit adaptation, never a zero-shot result.
            late=[r for r in testing if r['seconds']==500 and r['perspective'] in ('visual','bare') and r['view'] in (9,0)]
            training=training+late
            testing=[r for r in testing if r not in late]
        if args.mode=='random':
            rng=random.Random(503);training=[r|{'random_target':rng.choice(['甲。','乙。','丁。','戊。'])} for r in training]
        config=GraphExpressionConfig(use_edges=args.mode not in ('nodes','sensory','local','random'))
        if args.mode=='sensory':config=replace(config,node_fields=('amount',))
        elif args.mode.startswith('local') or args.mode=='random':config=replace(config,node_fields=FIELDS)
        samples=[{'process':representation(r,args.mode),'text':r.get('random_target',r['target'])} for r in training]
        model,meta=fit(samples,folder/f'{key}.safetensors',config=config,initial=args.continue_from,
            device='cuda' if torch.cuda.is_available() else 'cpu',check=lambda:guard(s),steps=2000 if args.mode=='random' else (1000 if args.mode=='sensory' else 4000))
        fitted=[]
        for i in range(0,len(samples),4):fitted.extend(model.decode([r['process'] for r in samples[i:i+4]]))
        generated=evaluate(model,testing,args.mode,s)
        result={'key':key,'mode':args.mode,'metadata':meta,'observation_policy':POLICY if args.mode.startswith('local') or args.mode=='random' else None,'training_cases':[r['path'] for r in training],
            'fit_correct':sum(o['text']==r['text'] for o,r in zip(fitted,samples)),'fit_count':len(samples),
            'training_labels':[r['text'] for r in samples],'rows':generated,
            'summary':scores(generated,('condition','seconds','perspective')),'consistency':consistency(generated),
            'random_labels_do_not_define_test_truth':args.mode=='random'}
        new_json(folder/f'{key}.json',result);new_json(WORK/'timing'/f'{key}.json',{'wall_seconds':time.monotonic()-tick})
        print({'key':key,'fit':result['fit_correct'],'summary':result['summary']},flush=True)
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':main()
