"""An external choice reader sharing the SAME decoder across optical fields.

The physical receptor inventory defines field membership. Neither object names,
the requested label nor ground-truth coordinates are inference arguments. Raw
Core activation/inhibition/touch values retain their recorded magnitudes.
"""
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
from safetensors.torch import save_file,load_file
from lab.tools.activity_controller import ActivityController,ActivityLayout

VERSION='threemind.spatial-choice-reader/1'


class SpatialChoice(ActivityController):
    def __init__(self,channels,visual_channels,*,seed=223):
        self.layout=ActivityLayout(channels)
        visual=list(map(int,visual_channels))
        if len(visual)%4 or not set(visual).issubset(self.layout.index):raise ValueError('four physical optical fields')
        common=[c for c in self.layout.channels if c not in set(visual)]
        fields=[]
        for field in np.array_split(visual,4):
            fields.append([self.layout.index[c]*4+i for c in [*field.tolist(),*common] for i in range(4)])
        super().__init__(len(fields[0]),1,seed=seed)
        self.register_buffer('field_indices',torch.as_tensor(fields,dtype=torch.long))
        self.full_features=self.layout.width;self.visual_channels=visual

    def forward(self,x):
        if x.ndim!=3 or x.shape[-1]!=self.full_features:raise ValueError('raw full-port observation width')
        batch,steps,_=x.shape
        field=x[:,:,self.field_indices].permute(0,2,1,3).reshape(batch*4,steps,-1)
        return super().forward(field).reshape(batch,4)

    def save(self,folder,channels=None,*,excluded_channels=()):
        p=Path(folder);p.mkdir(parents=True,exist_ok=False)
        save_file({k:v.detach().cpu().contiguous() for k,v in self.state_dict().items()},str(p/'model.safetensors'))
        (p/'manifest.json').write_text(json.dumps({'schema':VERSION,'channels':list(self.layout.channels),
          'visual_channels':self.visual_channels,'seed':self.seed,'fields':'raw activation, inhibition, direct, associative',
          'processing':'same temporal decoder per physical optical field; no subtraction or per-trial scaling'}),encoding='utf-8')

    @classmethod
    def restore(cls,folder,device='cpu'):
        p=Path(folder);m=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
        if m['schema']!=VERSION:raise ValueError('spatial reader version')
        model=cls(m['channels'],m['visual_channels'],seed=m['seed'])
        model.load_state_dict(load_file(str(p/'model.safetensors')))
        return model.to(device).eval(),model.layout
