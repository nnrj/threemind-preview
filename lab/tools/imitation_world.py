"""Explicit extension: distinct teacher limb seen alongside one's own limb.

No sensor is remapped to its corresponding other-agent sensor. Only ordinary
joint observations can form any relationship inside Core.
"""
from dataclasses import asdict
import numpy as np
from threemind_core import Stimulus
from lab.tools.shape_color_world import ShapeColorWorld,Pointer

VERSION='threemind.imitation-classroom/1'


class ImitationWorld(ShapeColorWorld):
    def __init__(self,seed=91):
        super().__init__(seed);self.teacher=Pointer()

    @property
    def channels(self):
        return super().channels+tuple(self.wiring.identity(0xE00200+i) for i in range(8))

    def observe(self,*,motor_only=True):
        observation=super().observe(motor_only=motor_only)
        observation['schema']=VERSION;observation['teacher_limb']=asdict(self.teacher)
        for v in (self.teacher.x,self.teacher.y,self.teacher.vx,self.teacher.vy):
            observation['values'].extend((max(0.,v),max(0.,-v)))
        return observation

    def stimulus(self,observation):
        if observation['schema']!=VERSION or len(observation['values'])!=280:raise ValueError('imitation schema')
        if not np.isfinite(observation['values']).all() or min(observation['values'])<0:raise ValueError('physical values')
        gains=[.03]*256+[.5]*24
        return Stimulus(0,tuple((c,float(v*g)) for c,v,g in zip(self.channels,observation['values'],gains) if v>0),intensity=1.)

    def state(self):return super().state()|{'schema':VERSION,'teacher':asdict(self.teacher)}

    @classmethod
    def restore(cls,state):
        if state['schema']!=VERSION:raise ValueError('imitation version')
        w=cls(state['seed']);w.set_scene(state['items'],state['variant']);w.pointer=Pointer(**state['pointer'])
        w.marker=state['marker'];w.teacher=Pointer(**state['teacher']);w.time_s=state['time_s'];return w
