"""One camera, visible self and measured guide contact; unchanged Core.

Geometry metadata is evidence only. The stimulus contains RGB/range pixels,
proprioception and physical weather, never object boxes, names or target IDs.
Legacy classroom versions retain their original optical origins and ports.
"""
from dataclasses import asdict
import math
import mujoco
import numpy as np
from threemind_core import Stimulus
from lab.tools.grounded_classroom import GroundedClassroom, FIELDS, SCALES
from lab.tools.shape_color_world import POSITIONS, RGB, Pointer

VERSION = 'threemind.grounded-classroom/3'


class WholeSceneClassroom(GroundedClassroom):
    allow_empty_scene = False
    def __init__(self, seed=91, weather_seed=47, resolution=16, visible_self=True, teacher_radius_m=.12):
        if resolution not in (12, 16, 24, 32):
            raise ValueError('bounded retinal resolution')
        self.resolution = int(resolution)
        self.visible_self = bool(visible_self)
        if not math.isfinite(teacher_radius_m) or not .03<=teacher_radius_m<=.3:
            raise ValueError('bounded physical teacher marker radius')
        self.teacher_radius_m=float(teacher_radius_m)
        self.contact_force = [0., 0.]
        self.origin = np.array([0., -2., 3.])
        self.forward = -self.origin / np.linalg.norm(self.origin)
        self.right = np.array([1., 0., 0.])
        self.up = np.cross(self.right, self.forward)
        self.aperture = .38
        super().__init__(seed, weather_seed)

    @property
    def vision_width(self):
        return 4*self.resolution**2

    @property
    def channels(self):
        retina = tuple(self.wiring.identity(0xE30000+i) for i in range(self.vision_width))
        body = tuple(self.wiring.identity(0xE00000+256+i) for i in range(8))
        weather = tuple(self.wiring.identity(0xE10000+i) for i in range(20))
        contact = tuple(self.wiring.identity(0xE31000+i) for i in range(4))
        return retina+body+weather+contact

    def set_scene(self, items, variant=0, positions=None):
        minimum = 0 if self.allow_empty_scene else 1
        if not minimum <= len(items) <= 8 or any(not 0 <= s < 5 or not 0 <= c < 5 for s,c in items):
            raise ValueError('one to eight valid physical objects')
        if positions is None:
            if len(items) != 4:
                raise ValueError('explicit positions for variable object counts')
            positions = POSITIONS
        xy = np.asarray(positions, dtype=float)
        if not items and xy.shape == (0,):
            xy = xy.reshape(0, 2)
        if xy.shape != (len(items), 2) or not np.isfinite(xy).all() or (xy.size and np.max(np.abs(xy)) > .85):
            raise ValueError('finite positions within optical workspace')
        self.items = [tuple(v) for v in items]
        self.positions = xy.tolist()
        self.variant = int(variant)
        cone = [(0., 0., .15)] + [(.14*math.cos(i*math.pi/8), .14*math.sin(i*math.pi/8), -.15) for i in range(16)]
        vertices = ' '.join(str(v) for p in cone for v in p)
        geoms = []
        for i, ((shape,color),(x,y)) in enumerate(zip(items, xy)):
            typ,size = (('sphere','.14'),('cylinder','.14 .15'),('box','.13 .13 .15'),('mesh',''),('box','.18 .18 .001'))[shape]
            spec = 'mesh="cone"' if shape==3 else f'size="{size}"'
            rgb = ' '.join(str(v) for v in RGB[color])
            geoms.append(f'<geom name="o{i}" type="{typ}" {spec} pos="{x} {y} .16" rgba="{rgb} 1"/>')
        # Named geometry is used only to position physical visible bodies, not
        # to segment returned pixels or to give the reader object identities.
        geoms += ['<geom name="self" type="sphere" size=".09" pos="0 0 .4" rgba=".1 .85 .9 1"/>',
                  f'<geom name="teacher" type="sphere" size="{self.teacher_radius_m}" pos="0 0 .52" rgba=".9 .1 .8 1"/>']
        self.model = mujoco.MjModel.from_xml_string('<mujoco><option timestep=".005" gravity="0 0 -9.81"/>'
            f'<asset><mesh name="cone" vertex="{vertices}"/></asset><worldbody>'
            '<geom type="plane" size="3 3 .1" rgba=".15 .15 .15 1"/>'+''.join(geoms)+'</worldbody></mujoco>')
        self.data = mujoco.MjData(self.model)
        self.self_id = mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_GEOM,'self')
        self.teacher_id = mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_GEOM,'teacher')
        self._directions = []
        # Single optical origin and one regular retina, never four object crops.
        for y in np.linspace(self.aperture, -self.aperture, self.resolution):
            for x in np.linspace(-self.aperture, self.aperture, self.resolution):
                d = self.forward+x*self.right+y*self.up
                self._directions.append(d/np.linalg.norm(d))
        self._directions = np.asarray(self._directions)

    def vision(self):
        self.model.geom_pos[self.self_id] = [self.pointer.x,self.pointer.y,.4] if self.visible_self else [0,0,-10]
        self.model.geom_pos[self.teacher_id] = [*self.marker,.52] if self.marker is not None else [0,0,-10]
        mujoco.mj_forward(self.model,self.data)
        values, records = [], []
        geom = np.array([-1],dtype=np.int32)
        for direction in self._directions:
            distance = float(mujoco.mj_ray(self.model,self.data,self.origin,direction,None,1,-1,geom))
            rgb = self.model.geom_rgba[geom[0],:3].tolist() if geom[0]>=0 else [0.,0.,0.]
            values.extend([0. if distance<0 else 1/(1+distance),*rgb])
            records.append({'distance_m':distance,'rgb':rgb})
        return {'values':values,'rays':records}

    def project(self, xy, z=.16):
        """Camera calibration for teacher labels/display; never a Core field."""
        vec = np.array([*xy,z])-self.origin
        depth = np.dot(vec,self.forward)
        return np.array([(np.dot(vec,self.right)/depth/self.aperture+1)/2,
                         (1-np.dot(vec,self.up)/depth/self.aperture)/2])*(self.resolution-1)

    def ground_point(self, column, row, z=.16):
        direction = self._directions[int(row)*self.resolution+int(column)]
        return (self.origin+(z-self.origin[2])/direction[2]*direction)[:2]

    def advance_physics(self, action=(0.,0.), dt=.05):
        old = np.array([self.pointer.vx,self.pointer.vy])
        wind = np.array(self.weather()[:2])
        free_v = np.clip(old+dt*(4*np.clip(action,-1,1)-3*old+.15*(wind-old)),-1,1)
        free_p = np.array([self.pointer.x,self.pointer.y])+dt*free_v
        super().advance_physics(action,dt)
        # Inward guide reaction impulse / dt for the unit-mass carriage.
        self.contact_force = np.where(np.abs(free_p)>1,-free_v/dt,0.).tolist()

    def observe(self, *, motor_only=False):
        retina = [0.]*self.vision_width if motor_only else self.vision()['values']
        p=self.pointer; wx,wy,air,humidity=self.weather()
        raw=(wx,wy,air,humidity,self.body_temperature,*self.acceleration,9.81,9.81,self.motor_power)
        values=list(retina)
        for value in (p.x,p.y,p.vx,p.vy): values.extend((max(0.,value),max(0.,-value)))
        for value,scale in zip(raw,SCALES): values.extend((max(0.,value/scale),max(0.,-value/scale)))
        for value in self.contact_force: values.extend((max(0.,value/10),max(0.,-value/10)))
        return {'schema':VERSION,'time_s':self.time_s,'values':values,'pointer':asdict(p),
                'physical_background':dict(zip(FIELDS,raw)),'guide_contact_force_N':list(self.contact_force),
                'items':self.items,'positions':self.positions,'teacher_marker':self.marker,
                'resolution':self.resolution,'visible_self':self.visible_self,'teacher_radius_m':self.teacher_radius_m,
                'camera':{'origin_m':self.origin.tolist(),'aperture':self.aperture},
                'visual_gain_per_channel':.03*64/self.resolution**2}

    def stimulus(self, observation):
        values=np.asarray(observation['values'],dtype=float)
        if observation['schema']!=VERSION or values.shape!=(len(self.channels),) or not np.isfinite(values).all() or np.min(values)<0:
            raise ValueError('finite whole-scene physical observation required')
        gains=[.03*64/self.resolution**2]*self.vision_width+[.5]*8+[.02]*20+[.02]*4
        return Stimulus(0,tuple((c,float(v*g)) for c,v,g in zip(self.channels,values,gains) if v>0),intensity=1.)

    def state(self):
        return super().state() | {'schema':VERSION,'resolution':self.resolution,'visible_self':self.visible_self,
                'positions':self.positions,'contact_force':self.contact_force,'teacher_radius_m':self.teacher_radius_m}

    @classmethod
    def restore(cls,state):
        if state['schema']!=VERSION: raise ValueError('whole-scene world version')
        w=cls(state['seed'],state['weather_seed'],state['resolution'],state['visible_self'],state.get('teacher_radius_m',.065))
        w.set_scene(state['items'],state['variant'],state['positions'])
        w.pointer=Pointer(**state['pointer'])
        for name in ('marker','time_s','body_temperature','acceleration','motor_power','contact_force'):
            setattr(w,name,state[name])
        return w


def sensory_replay(current, stationary, *, vision=True, body=True):
    """Research-only feedback replacement using an actual reference recording.

All motion-dependent body fields (including temperature/power) are replaced;
ambient weather remains the corresponding tape value. No Core state is edited.
"""
    if current['schema']!=VERSION or stationary['schema']!=VERSION or current['resolution']!=stationary['resolution']:
        raise ValueError('same versioned retinal inventory required')
    n=4*current['resolution']**2
    return current | {'values':list(current['values'][:n] if vision else stationary['values'][:n])+
                       list(current['values'][n:] if body else stationary['values'][n:]),
                      'research_feedback':{'vision':vision,'body':body,'reference_time_s':stationary['time_s']}}


def main():
    """Headless physical sampling; no Core or services are started."""
    import argparse
    import json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,help='restore a /3 world JSON')
    parser.add_argument('--output',type=Path,required=True,help='new directory, never overwritten')
    parser.add_argument('--seconds',type=float,default=1.)
    parser.add_argument('--force',nargs=2,type=float,default=[0.,0.])
    args=parser.parse_args()
    if not 0<args.seconds<=60:parser.error('duration must be in (0,60] seconds')
    world=WholeSceneClassroom.restore(json.loads(args.state.read_text(encoding='utf-8'))) if args.state else WholeSceneClassroom()
    args.output.mkdir(parents=True,exist_ok=False)
    with (args.output/'observations.jsonl').open('x',encoding='utf-8') as out:
        for _ in range(math.ceil(args.seconds/.05)):
            observation=world.observe()
            out.write(json.dumps({'observation':observation,'stimulus':world.stimulus(observation).to_dict()},ensure_ascii=False)+'\n')
            world.advance_physics(args.force)
    (args.output/'state.json').write_text(json.dumps(world.state(),ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'schema':VERSION,'output':str(args.output.resolve()),'sim_seconds':world.time_s}))


if __name__=='__main__':main()
