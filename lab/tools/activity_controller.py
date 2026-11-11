"""Small supervised external adapter: raw Core process -> forces/finite words.

No teacher/query argument exists at inference. Teaching targets are deliberately
separate. This does not claim the adapter itself cannot learn a task.
"""
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from safetensors.torch import save_file, load_file

VERSION = 'threemind.activity-controller/1'
FIELDS = ('activation','inhibition','direct','associative')


class ActivityLayout:
    def __init__(self, channels, *, excluded_channels=()):
        self.channels = tuple(sorted(map(int,channels)))
        self.excluded_channels=tuple(sorted(map(int,excluded_channels)))
        if not self.channels or len(set(self.channels)) != len(self.channels):
            raise ValueError('unique anonymous ports')
        if set(self.channels)&set(self.excluded_channels):raise ValueError('included/excluded overlap')
        self.index = {c:i for i,c in enumerate(self.channels)}

    @property
    def width(self):return len(self.channels)*len(FIELDS)

    def frame(self, observation):
        values=np.zeros((len(self.channels),len(FIELDS)),dtype=np.float32)
        for node in observation['nodes']:
            fields=[float(node[k]) for k in FIELDS]
            if not any(fields):continue
            channel=int(node['channel'])
            if channel in self.excluded_channels:continue
            if channel not in self.index:raise ValueError('unknown active port; never silently omit')
            values[self.index[channel]]=fields
        if not np.isfinite(values).all():raise ValueError('nonfinite observation')
        return values.ravel()


class ActivityController(nn.Module):
    def __init__(self, features, outputs, *, regression=False, seed=71):
        super().__init__();torch.manual_seed(seed)
        self.features,self.outputs,self.regression,self.seed=features,outputs,regression,seed
        self.input=nn.Linear(features,48)
        self.position=nn.Parameter(torch.zeros(1,32,48))
        layer=nn.TransformerEncoderLayer(48,4,96,dropout=0,batch_first=True,norm_first=True)
        self.temporal=nn.TransformerEncoder(layer,1,enable_nested_tensor=False)
        self.head=nn.Linear(48,outputs)

    def forward(self,x):
        if x.ndim!=3 or x.shape[2]!=self.features or not 1<=x.shape[1]<=32:
            raise ValueError('explicit bounded raw time sequence')
        h=self.temporal(self.input(x)+self.position[:,:x.shape[1]])
        y=self.head(h[:,-1])
        return torch.tanh(y) if self.regression else y

    def fit(self,x,y,*,steps=500,check=lambda:None,validation=None,batch_size=32):
        device=next(self.parameters()).device
        x=torch.as_tensor(np.asarray(x),dtype=torch.float32,device=device)
        y=torch.as_tensor(np.asarray(y),dtype=torch.float32 if self.regression else torch.long,device=device)
        if not torch.isfinite(x).all() or len(x)!=len(y) or not 1<=steps<=4000 or not 1<=batch_size<=32:raise ValueError('training bounds')
        vx,vy=x,y
        if validation is not None:
            vx=torch.as_tensor(np.asarray(validation[0]),dtype=torch.float32,device=device)
            vy=torch.as_tensor(np.asarray(validation[1]),dtype=y.dtype,device=device)
            if vx.ndim!=x.ndim or vx.shape[1:]!=x.shape[1:] or vy.shape[1:]!=y.shape[1:] or not len(vx) or len(vx)!=len(vy) or not torch.isfinite(vx).all() or not torch.isfinite(vy).all():
                raise ValueError('finite, compatible held-out validation examples')
        opt=torch.optim.AdamW(self.parameters(),lr=.002,weight_decay=.0001)
        lossfn=nn.MSELoss() if self.regression else nn.CrossEntropyLoss()
        rng=torch.Generator(device=device).manual_seed(self.seed)
        self.train();best=None;bestloss=float('inf')
        for i in range(steps):
            if i%50==0:check()
            idx=torch.randint(len(x),(min(batch_size,len(x)),),generator=rng,device=device)
            opt.zero_grad();loss=lossfn(self(x[idx]),y[idx]);loss.backward()
            torch.nn.utils.clip_grad_norm_(self.parameters(),1.);opt.step()
            if i%50==0 or i==steps-1:
                with torch.no_grad():value=float(lossfn(self(vx),vy))
                if value<bestloss:
                    bestloss=value;best={k:v.detach().cpu().clone() for k,v in self.state_dict().items()}
        self.load_state_dict(best);self.eval()
        result={'loss':bestloss,'steps':steps,'device':str(device),'teacher_labels':'training only'}
        if validation is not None:
            with torch.no_grad():training_loss=float(lossfn(self(x),y))
            result.update(selection='held-out demonstration loss',training_loss=training_loss,
                          validation_count=len(vx),training_count=len(x))
        return result

    def predict(self, values):
        self.eval()
        with torch.no_grad():return self(torch.as_tensor(np.asarray(values),dtype=torch.float32,
                                   device=next(self.parameters()).device)).cpu().numpy()

    def save(self,folder,channels,*,excluded_channels=()):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
        save_file({k:v.detach().cpu().contiguous() for k,v in self.state_dict().items()},str(folder/'model.safetensors'))
        (folder/'manifest.json').write_text(json.dumps({'schema':VERSION,'features':self.features,'outputs':self.outputs,
             'regression':self.regression,'seed':self.seed,'channels':list(channels),'fields':FIELDS,
             'excluded_channels':list(excluded_channels),
             'input_processing':'raw fields; no baseline subtraction or per-example scaling'}),encoding='utf-8')

    @classmethod
    def restore(cls,folder,device='cpu'):
        folder=Path(folder);m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if m['schema']!=VERSION or m['fields']!=list(FIELDS):raise ValueError('controller version')
        value=cls(m['features'],m['outputs'],regression=m['regression'],seed=m['seed'])
        value.load_state_dict(load_file(str(folder/'model.safetensors')),strict=True)
        return value.to(device).eval(),ActivityLayout(m['channels'],excluded_channels=m.get('excluded_channels',()))
