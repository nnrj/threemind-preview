"""Versioned denser optical sampling; no object labels enter the input bus.

Old classroom/1 is untouched. /2 records resolution and per-ray gain explicitly.
Increasing resolution preserves optical field and total angular gain, not a
hidden multiplication of stimulus strength. Bodies/weather use the old ports.
"""
import math
import numpy as np
import mujoco
from threemind_core import Stimulus
from lab.tools.grounded_classroom import GroundedClassroom
from lab.tools.shape_color_world import POSITIONS, Pointer

VERSION = 'threemind.grounded-classroom/2'


class DetailedClassroom(GroundedClassroom):
    def __init__(self, seed=91, weather_seed=47, resolution=6):
        if resolution not in (4, 6, 8, 12, 16):
            raise ValueError('bounded optical sampling resolution')
        self.resolution = int(resolution)
        super().__init__(seed, weather_seed)

    @property
    def vision_width(self): return 16*self.resolution**2

    @property
    def channels(self):
        visual = (tuple(self.wiring.identity(0xE00000+i) for i in range(256))
                  if self.resolution == 4 else
                  tuple(self.wiring.identity(0xE20000+i) for i in range(self.vision_width)))
        return visual + super().channels[256:]

    def vision(self):
        if self.resolution == 4: return super().vision()
        key = (tuple(self.items), self.variant, self.resolution)
        if key in self.sample_cache: return self.sample_cache[key]
        values, records = [], []
        angle = .18*(self.variant % 7-3)
        # Same covered angular area as the legacy 4x4 point sampler.
        offsets = np.linspace(-.23, .23, self.resolution)
        for x, y in POSITIONS:
            target = np.array([x,y,.15])
            origin = target + [.58*math.cos(angle), .58*math.sin(angle), .36]
            forward = target-origin; forward /= np.linalg.norm(forward)
            right = np.cross(forward,[0.,0.,1.]); right /= np.linalg.norm(right)
            up = np.cross(right,forward)
            for dy in offsets:
                for dx in offsets:
                    direction = forward+dx*right+dy*up; direction /= np.linalg.norm(direction)
                    geom = np.array([-1],dtype=np.int32)
                    length = float(mujoco.mj_ray(self.model,self.data,origin,direction,None,1,-1,geom))
                    rgb = self.model.geom_rgba[geom[0],:3].tolist() if geom[0]>=0 else [0.,0.,0.]
                    values.extend([0. if length<0 else 1/(1+length),*rgb])
                    records.append({'distance_m':length,'rgb':rgb})
        self.sample_cache[key] = {'values':values,'rays':records}
        return self.sample_cache[key]

    def observe(self, *, motor_only=False):
        # GroundedClassroom's physics is reused; its base observe has a fixed
        # motor-only zero width, corrected here for this new protocol only.
        base = super().observe(motor_only=motor_only)
        if motor_only: base['values'] = [0.]*self.vision_width+base['values'][256:]
        return base | {'schema':VERSION, 'vision_resolution':self.resolution,
                       'visual_gain_per_channel':.03*16/self.resolution**2}

    def stimulus(self, observation):
        if observation['schema'] != VERSION or len(observation['values']) != self.vision_width+36:
            raise ValueError('detailed classroom observation schema')
        values=np.asarray(observation['values'],dtype=float)
        if not np.isfinite(values).all() or np.min(values)<0: raise ValueError('finite nonnegative senses')
        gains=[.03*16/self.resolution**2]*self.vision_width+[.5]*16+[.02]*20
        return Stimulus(0,tuple((c,float(v*g)) for c,v,g in zip(self.channels,values,gains) if v>0),intensity=1.)

    def state(self): return super().state() | {'schema':VERSION,'resolution':self.resolution}

    @classmethod
    def restore(cls,state):
        if state['schema']!=VERSION: raise ValueError('world version')
        w=cls(state['seed'],state['weather_seed'],state['resolution'])
        w.set_scene(state['items'],state['variant']); w.pointer=Pointer(**state['pointer'])
        for name in ('marker','time_s','body_temperature','acceleration','motor_power'):
            setattr(w,name,state[name])
        return w
