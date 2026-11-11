"""New /5.2 complete subjects with the declared R43 three-adapter apparatus.

This class changes the birth kernel, not the sensory, teaching, temporal readout
or motor path. It never converts an old /5.1 individual into /5.2.
"""
import copy
import importlib.util
from pathlib import Path
import random
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
R43=HERE.parent/'2026-11-09-context-revision'
spec=importlib.util.spec_from_file_location('r46_original_apparatus',R43/'experiment.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
from threemind_kernels.local52 import Local52Config,Local52Engine,KERNEL_ID


class Student(old.Student):
    def __init__(self,seed,identity,curve,relaxation):
        self.seed,self.identity=seed,identity
        self.rng=random.Random(seed)
        self.mapping=dict(zip(old.SYMBOLS,self.rng.sample(range(1,2**32),len(old.SYMBOLS))))
        self.core=Local52Engine(Local52Config(seed=seed,energy_seed=seed^0x1634AB,
            decay_curve=curve,retention_relaxation_enabled=relaxation))
        self.adapters={k:old.CalibratedActivity([self.mapping[x] for x in ports],old.WORDS[k],identity+':'+k,
            seed=seed+j) for j,(k,ports) in enumerate(old.PORTS.items())}
        self.next_background=0
        self.input_digest,self.input_count=old.base.digest([]),0
        self.recent,self.samples=[],[]
        self.world=dict(kind='two-context-world/1',actual=None,observed=False,exit=None,query_used=False)
        self.cursor,self.parent=dict(stage='birth'),None
        self.adapter_refs,self.frozen_digest={},None
        self.activity_sum,self.activity_n={s:0. for s in old.SYMBOLS},0
        self.calibration_valid=False

    @classmethod
    def restore(cls,work,value):
        if value['core']['dynamics']!=KERNEL_ID:raise ValueError('no conversion of old research subjects')
        s=cls.__new__(cls)
        for k in ('seed','identity','mapping','next_background','input_digest','input_count','recent','samples',
                  'world','cursor','parent','adapter_refs','frozen_digest','activity_sum','activity_n','calibration_valid'):
            setattr(s,k,copy.deepcopy(value[k]))
        s.core=Local52Engine(state=old.base.StateImage.from_dict(value['core']))
        s.rng=random.Random();s.rng.setstate(old.tup(value['rng']))
        s.adapters={}
        for k,ref in value['adapter_refs'].items():
            for name,expected in ref['files'].items():
                if old.sha(work/ref['path']/name)!=expected:raise RuntimeError('adapter original changed')
            s.adapters[k]=old.CalibratedActivity.restore(work/ref['path'])
        old.torch.set_rng_state(old.torch.tensor(value['torch_rng'],dtype=old.torch.uint8))
        if old.base.digest(s.state())!=old.base.digest(value):raise RuntimeError('whole-state restoration mismatch')
        return s
