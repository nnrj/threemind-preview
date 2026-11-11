"""Raw-value expression calibration. Changes external training only, not Core.

No per-example scaling, centering, no-cue subtraction, hidden test labels or
cross-window dialogue memory. Supervision is accepted only while fitting.
"""
import random,time
import numpy as np
import torch
from torch import nn
from threemind_transformer.development_model import TemporalLanguage,save
from threemind_transformer.scratch_language import EOS


def fit_raw(samples,basis,path,*,seed=47,steps=8000,learning_rate=.001,
            full_batch=False,prefix_initial_gain=1.,initial=None,device='cpu',check=lambda:None,
            projection_manifest=None):
    from threemind_transformer.development_model import load
    from pathlib import Path
    if Path(path).exists():raise FileExistsError(path)
    if not 2<=len(samples)<=64 or not 1<=steps<=20000:raise ValueError('bounded calibration required')
    if not 0<learning_rate<=.1 or not 0<prefix_initial_gain<=10:raise ValueError('invalid training parameters')
    if initial:
        model,previous=load(initial,device)
        if projection_manifest is not None and previous.get('projection') is not None:
            from lab.tools.raw_state_expression import RawStateProjection
            if RawStateProjection(**previous['projection'])!=RawStateProjection(**projection_manifest):
                raise ValueError('checkpoint channel/field layout mismatch')
    else:model=TemporalLanguage(basis,seed).to(device)
    if model.basis!=basis:raise ValueError('same raw layout required')
    if initial is None:
        # A learnable projection's initialization; raw measured inputs are unchanged.
        with torch.no_grad():
            model.prefix.weight.mul_(prefix_initial_gain);model.prefix.bias.mul_(prefix_initial_gain)
    elif prefix_initial_gain!=1:raise ValueError('do not rescale a previously learned projection')
    data=torch.tensor(np.asarray([s['values'] for s in samples]),device=device,dtype=torch.float32)
    if tuple(data.shape[1:])!=(basis.bins,basis.width) or not torch.isfinite(data).all():raise ValueError('raw layout')
    targets=[[*s['text'].encode('utf-8'),EOS] for s in samples]
    optimizer=torch.optim.AdamW(model.parameters(),lr=learning_rate)
    rng=random.Random(seed);history=[];best=None;best_score=(-1,float('-inf'));stable=0;started=time.monotonic()
    for step in range(steps):
        model.train()
        indices=list(range(len(samples))) if full_batch else [rng.randrange(len(samples)) for _ in range(min(16,len(samples)))]
        rows=[targets[i] for i in indices];length=max(map(len,rows))
        ids=torch.full((len(rows),length),EOS,device=device,dtype=torch.long);labels=torch.full_like(ids,-100)
        for i,row in enumerate(rows):
            ids[i,:len(row)]=torch.tensor(row,device=device);labels[i,:len(row)]=ids[i,:len(row)]
        prefix=model.condition(data[indices]);joined=torch.cat([prefix,model.lm.token(ids)],dim=1)
        target=torch.cat([torch.full(prefix.shape[:2],-100,device=device,dtype=torch.long),labels],dim=1)
        loss=model.lm(inputs_embeds=joined,labels=target).loss
        if not torch.isfinite(loss):raise RuntimeError('nonfinite calibration loss')
        optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
        if step%100==0:check()
        if (step+1)%500==0 or step==steps-1:
            out=model.decode(data.detach().cpu().numpy());correct=sum(r['text']==s['text'] for r,s in zip(out,samples))
            score=(correct,-float(loss.detach().cpu()))
            history.append({'steps':step+1,'loss':-score[1],'correct':correct,'count':len(samples),
                            'outputs':[r['text'] for r in out]})
            if score>best_score:
                best_score=score;best={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            stable=stable+1 if correct==len(samples) else 0
            print({'step':step+1,'fit':f'{correct}/{len(samples)}','loss':round(-score[1],6)},flush=True)
            if stable>=2:break
    model.load_state_dict(best)
    metadata={'training_method':'raw-calibration/1','steps':step+1,'history':history,
        'samples':len(samples),'learning_rate':learning_rate,'full_batch':full_batch,
        'prefix_initial_gain':prefix_initial_gain,'initial':str(initial) if initial else None,
        'selection':'best training accuracy, then training loss; no test selection',
        'normalization':'none','baseline_subtraction':False,'no_cue_blank_supervision':False,
        'wall_seconds':time.monotonic()-started,'device':device,'parameters':sum(p.numel() for p in model.parameters())}
    if projection_manifest is not None:metadata['projection']=projection_manifest
    save(model,path,metadata)
    return model,metadata


def fit_classifier(samples,*,device='cpu',steps=3000,check=lambda:None):
    """Small raw MLP diagnostic, explicitly not natural-language generation."""
    labels=sorted({s['text'] for s in samples});x=torch.tensor(np.asarray([s['values'] for s in samples]),device=device,dtype=torch.float32).flatten(1)
    y=torch.tensor([labels.index(s['text']) for s in samples],device=device)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(47);model=nn.Sequential(nn.Linear(x.shape[1],128),nn.GELU(),nn.Linear(128,len(labels))).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001);history=[]
    for step in range(steps):
        logits=model(x);loss=nn.functional.cross_entropy(logits,y)
        optimizer.zero_grad();loss.backward();optimizer.step()
        if step%100==0:
            check();correct=int((model(x).argmax(-1)==y).sum())
            history.append({'step':step+1,'loss':float(loss.detach().cpu()),'correct':correct})
            if correct==len(samples):break
    return model,labels,history


def main():
    import argparse,json,psutil
    from pathlib import Path
    from lab.tools.raw_state_expression import RawStateProjection
    from threemind_transformer.development_model import load
    p=argparse.ArgumentParser(description='Raw activity through OutputBus to a stateless expression adapter')
    p.add_argument('operation',choices=('train','decode'))
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--checkpoint',type=Path)
    p.add_argument('--device',choices=('auto','cpu','cuda'),default='auto')
    p.add_argument('--steps',type=int,default=8000);p.add_argument('--learning-rate',type=float,default=.001)
    p.add_argument('--sampling',choices=('balanced','random'),default='balanced')
    p.add_argument('--wall-seconds',type=int,default=1800)
    args=p.parse_args();torch.set_num_threads(2)
    if args.output.exists():raise FileExistsError(args.output)
    if args.operation=='decode' and args.checkpoint is None:raise ValueError('decoding requires checkpoint')
    if not 1<=args.wall_seconds<=10800:raise ValueError('wall budget must be 1..10800 seconds')
    if args.input.stat().st_size>256*2**20:raise ValueError('input limit256MiB')
    projection=RawStateProjection(**json.loads(args.manifest.read_text(encoding='utf-8')))
    device='cuda' if args.device!='cpu' and torch.cuda.is_available() else 'cpu'
    started=time.monotonic()
    def guard():
        if time.monotonic()-started>args.wall_seconds:raise RuntimeError('time budget')
        if psutil.Process().memory_info().rss>4*2**30 or psutil.virtual_memory().available<2*2**30:raise RuntimeError('memory reserve')
        if device=='cuda' and torch.cuda.memory_allocated()>3*2**30:raise RuntimeError('GPU limit')
    records=[]
    from threemind_runtime.activity_stream import RawActivityStream
    with args.input.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():continue
            guard()
            row=json.loads(line);allowed={'id','process'}|({'text'} if args.operation=='train' else set())
            if set(row)-allowed:raise ValueError('undeclared data or labels in inference')
            source=row['process'];frames=[];bus=RawActivityStream();bus.subscribe('expression',frames.append)
            for frame in source['trajectory']:bus.publish(frame)
            process=source|{'trajectory':frames}
            records.append({'id':row.get('id'),'values':projection.project(process)['values'],
                            **({'text':row['text']} if args.operation=='train' else {})})
            if len(records)>(64 if args.operation=='train' else 512):raise ValueError('record count limit')
    if not records:raise ValueError('nonempty observations required')
    if args.operation=='train':
        _,meta=fit_raw(records,projection.basis,args.output,steps=args.steps,learning_rate=args.learning_rate,
            full_batch=args.sampling=='balanced',initial=args.checkpoint,device=device,check=guard,
            projection_manifest=projection.to_dict())
        print(json.dumps({'checkpoint':str(args.output),'device':device,'steps':meta['steps']},ensure_ascii=False))
    else:
        model,meta=load(args.checkpoint,device)
        if model.basis!=projection.basis:raise ValueError('checkpoint basis mismatch')
        if meta.get('projection') is not None and RawStateProjection(**meta['projection'])!=projection:
            raise ValueError('checkpoint channel/field layout mismatch')
        with args.output.open('x',encoding='utf-8') as out:
            for i in range(0,len(records),16):
                guard();part=records[i:i+16];decoded=model.decode(np.asarray([r['values'] for r in part],dtype=np.float32))
                for row,value in zip(part,decoded):out.write(json.dumps({'id':row['id'],'output':value,'device':device},ensure_ascii=False)+'\n')


if __name__=='__main__':main()
