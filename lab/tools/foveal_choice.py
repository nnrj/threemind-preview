"""Shared local reader for a nonuniform retina, with no scene/object inventory.

Neighborhoods are fixed by receptor geometry, not active values or targets.
External supervision is explicit; a good score alone is not Core attribution.
"""
import json
from pathlib import Path
import numpy as np
import torch
from safetensors.torch import save_file,load_file
from lab.tools.activity_controller import ActivityController,ActivityLayout

VERSION='threemind.foveal-choice/1'


class FovealChoice(ActivityController):
    def __init__(self,channels,visual_channels,centers,widths,*,seed=223):
        self.layout=ActivityLayout(channels)
        centers=np.asarray(centers,dtype=float);widths=np.asarray(widths,dtype=float)
        visual=list(map(int,visual_channels));n=len(centers)
        if centers.shape!=(n,2) or widths.shape!=(n,2) or n<9 or not np.isfinite(centers).all() or not np.isfinite(widths).all() or np.min(widths)<=0:
            raise ValueError('finite bounded receptor geometry')
        if len(visual)!=4*n or not set(visual).issubset(self.layout.index):raise ValueError('RGB/range ports')
        common=[c for c in self.layout.channels if c not in set(visual)]
        super().__init__(9*16+4*len(common)+9*4,1,seed=seed)
        neighbors=np.argsort(np.sum((centers[:,None]-centers[None,:])**2,axis=-1),axis=1,kind='stable')[:,:9]
        geometry=np.concatenate((centers[neighbors]-centers[:,None],widths[neighbors]),axis=-1).reshape(n,-1)
        self.centers=centers.tolist();self.widths=widths.tolist();self.visual_channels=visual
        self.register_buffer('neighbors',torch.tensor(neighbors))
        self.register_buffer('geometry',torch.tensor(geometry,dtype=torch.float32))
        self.register_buffer('visual_indices',torch.tensor([self.layout.index[c]*4+i for c in visual for i in range(4)]))
        self.register_buffer('common_indices',torch.tensor([self.layout.index[c]*4+i for c in common for i in range(4)]))

    def forward(self,x):
        b,t,_=x.shape;n=len(self.centers)
        retina=x[:,:,self.visual_indices].reshape(b,t,n,16)
        local=retina[:,:,self.neighbors].reshape(b,t,n,144)
        common=x[:,:,self.common_indices].unsqueeze(2).expand(-1,-1,n,-1)
        geom=self.geometry[None,None].expand(b,t,-1,-1)
        f=torch.cat((local,common,geom),-1).permute(0,2,1,3).reshape(b*n,t,-1)
        return super().forward(f).reshape(b,n)

    def select(self,values):
        values=np.asarray(values,dtype=np.float32)
        if not np.any(values):return None
        return int(np.argmax(self.predict(values[None])[0]))

    def save(self,folder,channels=None,*,excluded_channels=()):
        p=Path(folder);p.mkdir(parents=True,exist_ok=False)
        save_file({k:v.detach().cpu().contiguous() for k,v in self.state_dict().items()},str(p/'model.safetensors'))
        (p/'manifest.json').write_text(json.dumps({'schema':VERSION,'channels':list(self.layout.channels),
            'visual_channels':self.visual_channels,'centers':self.centers,'widths':self.widths,'seed':self.seed,
            'processing':'fixed geometric neighborhoods; raw four-field Core process; supervised external reader'}),encoding='utf-8')

    @classmethod
    def restore(cls,folder,device='cpu'):
        p=Path(folder);m=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
        if m['schema']!=VERSION:raise ValueError('foveal reader version')
        result=cls(m['channels'],m['visual_channels'],m['centers'],m['widths'],seed=m['seed'])
        result.load_state_dict(load_file(str(p/'model.safetensors')))
        return result.to(device).eval(),result.layout
