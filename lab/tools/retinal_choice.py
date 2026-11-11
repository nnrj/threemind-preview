"""Shared local retinal reader; no object boxes or target-conditioned crops.

Every pixel receives the same 3x3 physical neighborhood and nonvisual inputs.
The external supervised reader chooses a retinal pixel, not a supplied object.
"""
import json
from pathlib import Path
import numpy as np
import torch
from safetensors.torch import save_file, load_file
from lab.tools.activity_controller import ActivityController, ActivityLayout

VERSION='threemind.retinal-choice/1'


class RetinalChoice(ActivityController):
    def __init__(self,channels,visual_channels,resolution,*,seed=223):
        self.layout=ActivityLayout(channels)
        self.resolution=int(resolution)
        visual=list(map(int,visual_channels))
        if len(visual)!=4*resolution**2 or not set(visual).issubset(self.layout.index):
            raise ValueError('one RGB/range retina')
        common=[c for c in self.layout.channels if c not in set(visual)]
        super().__init__(9*16+4*len(common),1,seed=seed)
        self.visual_channels=visual
        self.register_buffer('visual_indices',torch.tensor([self.layout.index[c]*4+i for c in visual for i in range(4)]))
        self.register_buffer('common_indices',torch.tensor([self.layout.index[c]*4+i for c in common for i in range(4)]))

    def forward(self,x):
        b,t,_=x.shape; n=self.resolution
        pixels=x[:,:,self.visual_indices].reshape(b*t,n,n,16).permute(0,3,1,2)
        local=torch.nn.functional.unfold(pixels,3,padding=1).transpose(1,2).reshape(b,t,n*n,144)
        common=x[:,:,self.common_indices].unsqueeze(2).expand(-1,-1,n*n,-1)
        features=torch.cat((local,common),-1).permute(0,2,1,3).reshape(b*n*n,t,-1)
        return super().forward(features).reshape(b,n*n)

    def save(self,folder,channels=None,*,excluded_channels=()):
        p=Path(folder);p.mkdir(parents=True,exist_ok=False)
        save_file({k:v.detach().cpu().contiguous() for k,v in self.state_dict().items()},str(p/'model.safetensors'))
        (p/'manifest.json').write_text(json.dumps({'schema':VERSION,'channels':list(self.layout.channels),
            'visual_channels':self.visual_channels,'resolution':self.resolution,'seed':self.seed,
            'processing':'shared regular retinal 3x3 neighborhoods; raw Core fields; no object crops'}),encoding='utf-8')

    @classmethod
    def restore(cls,folder,device='cpu'):
        p=Path(folder);m=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
        if m['schema']!=VERSION:raise ValueError('retinal reader version')
        result=cls(m['channels'],m['visual_channels'],m['resolution'],seed=m['seed'])
        result.load_state_dict(load_file(str(p/'model.safetensors')))
        return result.to(device).eval(),result.layout
