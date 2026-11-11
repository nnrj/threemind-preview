"""Bounded alternating-development diagnostic, retaining all frozen failures."""
import argparse
from dataclasses import replace
from common import *
from reteach import observe
from lab.tools.recorded_background import RecordedBackground
from lab.tools.expression_calibration import fit_raw
from lab.tools.raw_state_expression import RawStateProjection
from threemind_transformer.development_model import load

def collect():
    torch.set_num_threads(2);s=study();e48=old_helpers();a=e48.adapter();allrows=[]
    try:
        for owner in (223,279):
            checkpoint=WORK/'cases'/f'reteach-s{owner}-balanced'/'checkpoint-710'
            assignment=read_json(OLD/'cases'/f's{owner}-cycle1'/'definition.json')['assignment']
            projection=RawStateProjection(**read_json(WORK/'models'/f's{owner}-correction-continued.json')['projection'])
            for seconds in (710,770):
                parent=checkpoint
                if seconds==770:
                    branch=WORK/'cases'/f'joint-s{owner}-wait770';guard(s,True)
                    if not (branch/'result.json').exists():
                        branch.mkdir(parents=True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
                        value=e48.old.e45.previous.restore(checkpoint,71);cursor=read_json(checkpoint/'summary.json')['cursor']
                        tape=RecordedBackground(PREVIOUS/'physical-telemetry.jsonl')
                        while value.engine.time_us<770000000 and value.engine.life!='dead':
                            until=min(770000000,value.engine.time_us+500000);cursor=tape.queue_before(value.reader,cursor,until)
                            value.reader.advance_to(until,guard=lambda:guard(s));value.records.clear()
                        e48.old.e45.previous.save_state(branch/'checkpoint',value,cursor)
                        new_json(branch/'result.json',{'owner':owner,'life':value.engine.life,'wall_seconds':time.monotonic()-tick});s.active_case=None
                    parent=branch/'checkpoint'
                specs=[(item,view,strength,'train') for item in range(4) for view,strength in ((8,.4),(10,.6))] if seconds==710 else [(item,9,.5,'test') for item in range(-1,4)]
                for item,view,strength,split in specs:
                    path=WORK/'cases'/f'joint-s{owner}-t{seconds}-i{item}-v{view}';guard(s)
                    if (path/'result.json').exists():
                        allrows.append(read_json(path/'result.json'));continue
                    path.mkdir(parents=True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
                    value=e48.old.e45.previous.restore(parent,71);cursor=read_json(parent/'summary.json')['cursor']
                    if item>=0:value.reader.schedule([{'stimulus':replace(a.world.frame(a.world.sample(item,view)),intensity=strength),'labels':{}}],source='E49-probe',adapter_id='raw-state-study/1')
                    RecordedBackground(PREVIOUS/'physical-telemetry.jsonl').queue_before(value.reader,cursor,value.engine.time_us+2000000)
                    process=observe(value,value.engine.time_us+2000000,20000,s);write_gzip(path/'process.json.gz',process)
                    result={'owner':owner,'seconds':seconds,'item':item,'view':view,'intensity':strength,'split':split,
                        'target':e48.old.NAMES[assignment.index(item)]+'。' if item>=0 else None,
                        'values':projection.project(process)['values'],'life':value.engine.life,'wall_seconds':time.monotonic()-tick}
                    new_json(path/'result.json',result);allrows.append(result);s.active_case=None
        new_json(WORK/'joint-data.json',{'rows':allrows});print({'joint_rows':len(allrows)},flush=True)
    finally:s.active_case=None;s.db.close()

def train(owner,continued):
    import gzip
    torch.set_num_threads(2);s=study();guard(s,True)
    key=f's{owner}-joint-'+('continued' if continued else 'cold');folder=WORK/'models'
    if (folder/f'{key}.json').exists():s.db.close();return
    own=[r for r in rows() if r['seed']==owner and r['modality']=='words']
    teaching=[r for r in own if r['split']=='train' and r['seconds']==532 and r['condition'] in ('continued','reversal','cycle1') and r['item']>=0]
    joint=[r for r in read_json(WORK/'joint-data.json')['rows'] if r['owner']==owner]
    teaching += [r for r in joint if r['split']=='train']
    meta=read_json(folder/f's{owner}-correction-continued.json');projection=RawStateProjection(**meta['projection'])
    test=[r for r in own if r['split']=='test']
    for path in sorted((WORK/'cases').glob(f'probe-s{owner}-balanced-t710-*/result.json')):
        r=read_json(path)
        with gzip.open(path.parent/'process.json.gz','rt',encoding='utf-8') as f:process=json.load(f)
        test.append(r|{'condition':'post-review','values':projection.project(process)['values']})
    test += [r|{'condition':'post-review'} for r in joint if r['split']=='test']
    tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick);device='cuda' if torch.cuda.is_available() else 'cpu'
    try:
        model,training=fit_raw([{'values':r['values'],'text':r['target']} for r in teaching],projection.basis,
            folder/f'{key}.safetensors',full_batch=True,initial=folder/f's{owner}-correction-continued.safetensors' if continued else None,
            device=device,check=lambda:guard(s))
        out=[]
        for i in range(0,len(test),16):out.extend(model.decode(np.asarray([r['values'] for r in test[i:i+16]],dtype=np.float32)))
        details=[{k:r.get(k) for k in ('condition','seconds','item','target','evidence')}|{'output':o['text'],'tokens':o['tokens']} for r,o in zip(test,out)]
        fitted=model.decode(np.asarray([r['values'] for r in teaching],dtype=np.float32))
        result={'owner':owner,'regime':'joint','continued':continued,'metadata':training,'projection':projection.to_dict(),
            'fit_correct':sum(r['target']==o['text'] for r,o in zip(teaching,fitted)),'fit_count':len(teaching),
            'rows':details,'summary':summary(details)}
        new_json(folder/f'{key}.json',result);new_json(WORK/'timing'/f'{key}.json',{'wall_seconds':time.monotonic()-tick})
        print({'model':key,'fit':result['fit_correct'],'summary':result['summary']},flush=True)
    finally:s.active_case=None;s.db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=('collect','train'));args=p.parse_args()
    if args.operation=='collect':collect()
    else:
        for owner in (223,279):
            for continued in (True,False):train(owner,continued)
