"""Old fixed-layout expression on exactly the same local observations/labels."""
from common import *
from multiview import rows,representation,consistency
from lab.tools.expression_calibration import fit_raw
from threemind_transformer.development import TrajectoryBasis
import numpy as np


def flatten(value,channels):
    index={c:i for i,c in enumerate(channels)};width=1+len(value['node_fields'])
    values=np.zeros((len(value['frames']),len(channels),width),np.float32)
    for t,frame in enumerate(value['frames']):
        for node in frame['nodes']:
            if node['channel'] not in index:raise ValueError('new channel outside old training dictionary')
            values[t,index[node['channel']]]=[1,*node['values']]
    return values.reshape(len(values),-1).tolist()


def main():
    torch.set_num_threads(2);s=study();guard(s,True);folder=WORK/'models';key='multi-s223-legacy-local'
    if (folder/f'{key}.json').exists():s.db.close();return
    tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    try:
        items=rows(223);train=[r for r in items if r['split']=='train'];test=[r for r in items if r['split']=='test']
        inputs=[representation(r,'local') for r in train]
        channels=sorted({n['channel'] for p in inputs for f in p['frames'] for n in f['nodes']})
        width=len(channels)*(1+len(inputs[0]['node_fields']));basis=TrajectoryBasis(tuple(range(width-1)),17,1)
        samples=[{'values':flatten(p,channels),'text':r['target']} for p,r in zip(inputs,train)]
        model,meta=fit_raw(samples,basis,folder/f'{key}.safetensors',full_batch=True,steps=4000,
            device='cuda' if torch.cuda.is_available() else 'cpu',check=lambda:guard(s))
        output=[];unread=[]
        for row in test:
            try:value=flatten(representation(row,'local'),channels)
            except ValueError as error:unread.append({'evidence':row['path'],'reason':str(error)});continue
            word=model.decode([value])[0]
            output.append({k:row[k] for k in ('owner','condition','seconds','item','target','perspective','view','split')}|
                {'output':word['text'],'tokens':word['tokens'],'evidence':row['path']})
        fitted=model.decode(np.asarray([r['values'] for r in samples]))
        new_json(folder/f'{key}.json',{'key':key,'mode':'legacy-local','metadata':meta,'anonymous_channels':channels,
            'fit_correct':sum(o['text']==r['text'] for o,r in zip(fitted,samples)),'fit_count':len(samples),
            'rows':output,'unread':unread,'summary':scores(output,('condition','seconds','perspective')),'consistency':consistency(output)})
        new_json(WORK/'timing'/f'{key}.json',{'wall_seconds':time.monotonic()-tick})
        print({'legacy-fit':sum(o['text']==r['text'] for o,r in zip(fitted,samples)),'unread':len(unread),'summary':scores(output,('seconds',))},flush=True)
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':main()
