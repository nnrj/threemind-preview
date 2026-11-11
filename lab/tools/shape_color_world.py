"""Versioned physical classroom and pointing organ, outside Core.

Names in scene definitions are renderer geometry/material choices, never input
channels. Teacher and learner pointers are distinct physical observations.
"""
from dataclasses import dataclass, asdict
import math

import mujoco
import numpy as np

from threemind_core import Stimulus
from threemind_runtime.receptors import ReceptorWiring

VERSION = 'threemind.shape-color-classroom/1'
SHAPES = ('球体', '圆柱体', '立方体', '圆锥体')
COLORS = ('红色', '黄色', '蓝色', '绿色')
RGB = ((1., .08, .08), (1., 1., .08), (.08, .08, 1.), (.08, 1., .08), (.55, .55, .55))
POSITIONS = ((-.55, -.55), (.55, -.55), (-.55, .55), (.55, .55))


@dataclass
class Pointer:
    x: float = 0.
    y: float = 0.
    vx: float = 0.
    vy: float = 0.

    def step(self, action, dt=.05):
        action = np.asarray(action, dtype=float)
        if action.shape != (2,) or not np.isfinite(action).all() or not 0 < dt <= .1:
            raise ValueError('two finite forces and bounded physical step required')
        # Unit-mass carriage, acceleration-limited motors and viscous drag.
        v = np.array([self.vx, self.vy]) + dt * (4*np.clip(action, -1, 1)-3*np.array([self.vx,self.vy]))
        v = np.clip(v, -1, 1)
        p = np.array([self.x, self.y]) + dt*v
        hit = np.abs(p) > 1
        p = np.clip(p, -1, 1)
        v[hit] = 0
        self.x, self.y = map(float, p)
        self.vx, self.vy = map(float, v)
        return float(np.dot(action, action)*dt)  # mechanical effort, not a Core reward

    def teacher_action(self, target):
        """External demonstration only; never called by a learned controller."""
        return np.clip(3*(np.asarray(target)-[self.x,self.y])-.9*np.array([self.vx,self.vy]), -1, 1)


class ShapeColorWorld:
    def __init__(self, seed=91):
        self.seed = seed
        self.wiring = ReceptorWiring(seed)
        self.pointer = Pointer()
        self.marker = None
        self.items = []
        self.sample_cache = {}
        self.time_s = 0.
        self.set_scene([(i,4) for i in range(4)])

    @property
    def channels(self):
        # 4 spatial views x4x4rays x(depth+RGB), plus signed physical channels.
        return tuple(self.wiring.identity(0xE00000+i) for i in range(272))

    def set_scene(self, items, variant=0):
        if len(items) != 4 or any(not 0 <= s < 5 or not 0 <= c < 5 for s,c in items):
            raise ValueError('four valid shape/material objects')
        self.items = [tuple(v) for v in items]
        self.variant = int(variant)
        cone = [(0.,0.,.15)] + [(.14*math.cos(i*math.pi/8),.14*math.sin(i*math.pi/8),-.15) for i in range(16)]
        vertices = ' '.join(str(v) for p in cone for v in p)
        bodies = []
        for i, ((shape,color),(x,y)) in enumerate(zip(items,POSITIONS)):
            typ, size = (('sphere','.14'),('cylinder','.14 .15'),('box','.13 .13 .15'),('mesh',''),('box','.18 .18 .001'))[shape]
            geometry = 'mesh="cone"' if shape == 3 else f'size="{size}"'
            rgb = ' '.join(str(v) for v in RGB[color])
            bodies.append(f'<geom name="o{i}" type="{typ}" {geometry} pos="{x} {y} .16" rgba="{rgb} 1"/>')
        self.model = mujoco.MjModel.from_xml_string(f'<mujoco><option timestep=".005" gravity="0 0 -9.81"/>'
            f'<asset><mesh name="cone" vertex="{vertices}"/></asset><worldbody>'
            '<geom type="plane" size="3 3 .1" rgba=".15 .15 .15 1"/>'+''.join(bodies)+'</worldbody></mujoco>')
        self.data = mujoco.MjData(self.model)
        mujoco.mj_forward(self.model, self.data)

    def vision(self):
        key = (tuple(self.items), self.variant)
        if key in self.sample_cache:
            return self.sample_cache[key]
        values, records = [], []
        # Four FIXED spatial optical fields, independent of target and identity.
        angle = .18*(self.variant % 7-3)
        for x,y in POSITIONS:
            target = np.array([x,y,.15])
            origin = target + np.array([.58*math.cos(angle), .58*math.sin(angle), .36])
            forward = target-origin;forward /= np.linalg.norm(forward)
            right = np.cross(forward,[0.,0.,1.]);right /= np.linalg.norm(right)
            up = np.cross(right,forward)
            for dy in (-.23,-.077,.077,.23):
                for dx in (-.23,-.077,.077,.23):
                    direction = forward+dx*right+dy*up;direction /= np.linalg.norm(direction)
                    geom = np.array([-1],dtype=np.int32)
                    length = float(mujoco.mj_ray(self.model,self.data,origin,direction,None,1,-1,geom))
                    # Render surface RGB and metric distance, including the floor.
                    rgb = self.model.geom_rgba[geom[0],:3].tolist() if geom[0]>=0 else [0.,0.,0.]
                    row = [0. if length<0 else 1/(1+length),*rgb]
                    values.extend(row);records.append({'distance_m':length,'rgb':rgb})
        self.sample_cache[key] = {'values':values,'rays':records}
        return self.sample_cache[key]

    def observe(self, *, motor_only=False):
        v = [0.]*256 if motor_only else list(self.vision()['values'])
        p = self.pointer
        # A local optical spot tracker measures coordinates; it doesn't select an
        # object or interpret its name. Camera marker is removed in goal tests.
        # The carriage remains in contact with its two-axis guide throughout;
        # the final value is its physical contact switch, not a teaching label.
        physical = [p.x,p.y,p.vx,p.vy,*(self.marker if self.marker is not None else (0.,0.)),
                    float(self.marker is not None),1.]
        for f in physical:
            v.extend((max(0.,float(f)),max(0.,-float(f))))
        return {'schema':VERSION,'time_s':self.time_s,'values':v,'pointer':asdict(p),
                'teacher_marker':self.marker,'items':self.items,'variant':self.variant,
                'motor_only':motor_only}

    def stimulus(self, observation):
        if observation['schema'] != VERSION or len(observation['values']) != 272:
            raise ValueError('classroom observation schema')
        values = np.asarray(observation['values'],dtype=float)
        if not np.isfinite(values).all() or np.min(values)<0:
            raise ValueError('finite nonnegative sensor values required')
        gains = [.03]*256+[.5]*16
        return Stimulus(0,tuple((c,float(v*g)) for c,v,g in zip(self.channels,values,gains) if v>0),intensity=1.)

    def state(self):
        return {'schema':VERSION,'seed':self.seed,'pointer':asdict(self.pointer),'marker':self.marker,
                'items':self.items,'variant':self.variant,'time_s':self.time_s}

    @classmethod
    def restore(cls,state):
        if state['schema']!=VERSION:raise ValueError('world version')
        w=cls(state['seed']);w.set_scene(state['items'],state['variant']);w.pointer=Pointer(**state['pointer'])
        w.marker=state['marker'];w.time_s=state['time_s'];return w
