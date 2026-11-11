"""Complete bounded temporal reader, preserving the E59 original /1 reader.

No query text, object list or target coordinates at inference. Raw sensory or
Core fields enter in actual sample order. Labels are external training only.
"""
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from safetensors.torch import save_file,load_file
from lab.tools.foveal_choice import FovealChoice

VERSION='threemind.foveal-sequence/1'


class FovealSequence(FovealChoice):
    def __init__(self,channels,visual_channels,centers,widths,*,seed=223,capacity=64):
        super().__init__(channels,visual_channels,centers,widths,seed=seed)
        if not 1<=capacity<=128:raise ValueError('bounded temporal capacity')
        self.capacity=capacity;self.position=nn.Parameter(torch.zeros(1,capacity,48))

    def forward(self,x):
        if x.ndim!=3 or x.shape[2]!=self.layout.width or not 1<=x.shape[1]<=self.capacity:
            raise ValueError('bounded raw sequence in the recorded channel layout')
        b,t,_=x.shape;n=len(self.centers)
        retina=x[:,:,self.visual_indices].reshape(b,t,n,16)
        local=retina[:,:,self.neighbors].reshape(b,t,n,144)
        common=x[:,:,self.common_indices].unsqueeze(2).expand(-1,-1,n,-1)
        geom=self.geometry[None,None].expand(b,t,-1,-1)
        f=torch.cat((local,common,geom),-1).permute(0,2,1,3).reshape(b*n,t,-1)
        h=self.temporal(self.input(f)+self.position[:,:t])
        return self.head(h[:,-1]).reshape(b,n)

    def fit(self,x,y,*,steps=1200,check=lambda:None,validation=None,batch_size=4):
        device=next(self.parameters()).device
        x=torch.as_tensor(np.asarray(x),dtype=torch.float32,device=device)
        y=torch.as_tensor(np.asarray(y),dtype=torch.long,device=device)
        if not torch.isfinite(x).all() or len(x)!=len(y) or not 1<=steps<=4000 or not 1<=batch_size<=8:raise ValueError('finite bounded fit')
        vx,vy=x,y
        if validation is not None:
            vx=torch.as_tensor(np.asarray(validation[0]),dtype=torch.float32,device=device)
            vy=torch.as_tensor(np.asarray(validation[1]),dtype=torch.long,device=device)
        if not len(vx) or len(vx)!=len(vy) or vx.shape[1:]!=x.shape[1:] or not torch.isfinite(vx).all():raise ValueError('validation layout')
        lossfn=nn.CrossEntropyLoss();opt=torch.optim.AdamW(self.parameters(),lr=.002,weight_decay=.0001)
        rng=torch.Generator(device=device).manual_seed(self.seed);best=None;bestloss=float('inf')
        def loss_at(a,b):
            with torch.no_grad():return sum(float(lossfn(self(a[i:i+batch_size]),b[i:i+batch_size]))*len(a[i:i+batch_size])
                for i in range(0,len(a),batch_size))/len(a)
        self.train()
        for i in range(steps):
            if i%50==0:check()
            index=torch.randint(len(x),(min(len(x),batch_size),),generator=rng,device=device)
            opt.zero_grad();loss=lossfn(self(x[index]),y[index]);loss.backward();nn.utils.clip_grad_norm_(self.parameters(),1.);opt.step()
            if i%50==0 or i==steps-1:
                value=loss_at(vx,vy)
                if value<bestloss:bestloss=value;best={k:v.detach().cpu().clone() for k,v in self.state_dict().items()}
        self.load_state_dict(best);self.eval()
        return {'loss':bestloss,'training_loss':loss_at(x,y),'steps':steps,'device':str(device),
                'training_count':len(x),'validation_count':len(vx),'selection':'held-out validation loss',
                'teacher_labels':'external training only','temporal_samples':x.shape[1]}

    def save(self,folder,channels=None,*,excluded_channels=()):
        p=Path(folder);p.mkdir(parents=True,exist_ok=False)
        save_file({k:v.detach().cpu().contiguous() for k,v in self.state_dict().items()},str(p/'model.safetensors'))
        (p/'manifest.json').write_text(json.dumps({'schema':VERSION,'channels':list(self.layout.channels),
            'visual_channels':self.visual_channels,'centers':self.centers,'widths':self.widths,'seed':self.seed,
            'capacity':self.capacity,'processing':'raw chronological fields; fixed geometric neighborhoods'}),encoding='utf-8')

    @classmethod
    def restore(cls,folder,device='cpu'):
        p=Path(folder);m=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
        if m['schema']!=VERSION:raise ValueError('sequence reader version')
        result=cls(m['channels'],m['visual_channels'],m['centers'],m['widths'],seed=m['seed'],capacity=m['capacity'])
        result.load_state_dict(load_file(str(p/'model.safetensors')))
        return result.to(device).eval(),result.layout
