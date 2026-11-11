"""Versioned whole-scene foveated eye and independent two-axis eye actuator.

Every receptor measures fixed angular support, not a supplied object crop.
Only optical/body measurements enter Stimulus; scene metadata is evidence.
"""
from dataclasses import dataclass, asdict
import math
import numpy as np
import mujoco
from threemind_core import Stimulus
from lab.tools.whole_scene_classroom import WholeSceneClassroom
from lab.tools.shape_color_world import Pointer

VERSION='threemind.grounded-classroom/4'


@dataclass(frozen=True)
class EyeConfig:
    center_half_width: float=.075
    aperture: float=.38
    angle_limit_rad: float=.35
    speed_limit_rad_s: float=.9
    acceleration_rad_s2: float=8.
    damping_s_inv: float=4.
    visual_gain: float=.03*64/68

    def __post_init__(self):
        if not all(math.isfinite(v) and v>0 for v in asdict(self).values()):
            raise ValueError('positive finite optical and actuator parameters')
        if not .02<=self.center_half_width<self.aperture/2 or not self.aperture<=1:
            raise ValueError('bounded non-overlapping retinal supports')
        if self.angle_limit_rad>.6 or self.speed_limit_rad_s>5 or self.visual_gain>1:
            raise ValueError('bounded eye configuration')


class ActiveEyeClassroom(WholeSceneClassroom):
    def __init__(self,seed=91,weather_seed=47,*,config=None,visible_self=True):
        self.eye_config=config or EyeConfig()
        self.eye_angle=np.zeros(2);self.eye_velocity=np.zeros(2);self.eye_power=0.
        h=self.eye_config.center_half_width;a=self.eye_config.aperture
        fine=np.linspace(-h,h,7)
        coarse=np.array([-a,-(a+h)/2,-h,0,h,(a+h)/2,a])
        cells=[]
        for edges,kind in ((fine,'central'),(coarse,'peripheral')):
            for r in range(6):
                for c in range(6):
                    if kind=='peripheral' and r in (2,3) and c in (2,3):continue
                    cells.append((edges[c],edges[c+1],edges[r],edges[r+1],kind))
        self.cells=cells
        self.retinal_centers=np.array([[(x0+x1)/2,(y0+y1)/2] for x0,x1,y0,y1,_ in cells])
        self.retinal_widths=np.array([[x1-x0,y1-y0] for x0,x1,y0,y1,_ in cells])
        # Equal fixed quadrature pattern; larger peripheral supports average
        # larger angular areas. It never uses geometry/object IDs for sampling.
        self.subrays=np.array([[(x0+u*(x1-x0),y0+v*(y1-y0)) for u,v in
                              ((.25,.25),(.75,.25),(.25,.75),(.75,.75))]
                             for x0,x1,y0,y1,_ in cells])
        super().__init__(seed,weather_seed,16,visible_self)
        self.aperture=a
        self._refresh_directions()

    @property
    def vision_width(self):return 4*len(self.cells)

    @property
    def channels(self):
        visual=tuple(self.wiring.identity(0xE40000+i) for i in range(self.vision_width))
        body=tuple(self.wiring.identity(0xE00000+256+i) for i in range(8))
        weather=tuple(self.wiring.identity(0xE10000+i) for i in range(20))
        contact=tuple(self.wiring.identity(0xE31000+i) for i in range(4))
        eye=tuple(self.wiring.identity(0xE41000+i) for i in range(10))
        return visual+body+weather+contact+eye

    def basis(self):
        base=-self.origin/np.linalg.norm(self.origin); right=np.array([1.,0.,0.]); up=np.cross(right,base)
        yaw,pitch=self.eye_angle
        f=math.cos(yaw)*base+math.sin(yaw)*right
        r=math.cos(yaw)*right-math.sin(yaw)*base
        return math.cos(pitch)*f+math.sin(pitch)*up,r,math.cos(pitch)*up-math.sin(pitch)*f

    def _refresh_directions(self):
        self.forward,self.right,self.up=self.basis()
        def directions(points):
            d=self.forward+points[...,0,None]*self.right+points[...,1,None]*self.up
            return d/np.linalg.norm(d,axis=-1,keepdims=True)
        self._directions=directions(self.retinal_centers)
        self._subdirections=directions(self.subrays)

    def set_scene(self,items,variant=0,positions=None):
        super().set_scene(items,variant,positions)
        self._refresh_directions()

    def vision(self):
        self._refresh_directions()
        self.model.geom_pos[self.self_id]=[self.pointer.x,self.pointer.y,.4] if self.visible_self else [0,0,-10]
        self.model.geom_pos[self.teacher_id]=[*self.marker,.52] if self.marker is not None else [0,0,-10]
        mujoco.mj_forward(self.model,self.data)
        samples=[];geom=np.array([-1],dtype=np.int32)
        for directions in self._subdirections:
            values=[]
            for direction in directions:
                distance=float(mujoco.mj_ray(self.model,self.data,self.origin,direction,None,1,-1,geom))
                rgb=self.model.geom_rgba[geom[0],:3].tolist() if geom[0]>=0 else [0.,0.,0.]
                values.append([0. if distance<0 else 1/(1+distance),*rgb])
            samples.append(np.mean(values,axis=0))
        return {'values':np.asarray(samples).ravel().tolist()}

    def advance_physics(self,action=(0.,0.),dt=.05,*,eye_action=(0.,0.)):
        a=np.asarray(eye_action,dtype=float)
        if a.shape!=(2,) or not np.isfinite(a).all():raise ValueError('finite eye action')
        super().advance_physics(action,dt)
        c=self.eye_config;torque=c.acceleration_rad_s2*np.clip(a,-1,1)
        self.eye_velocity=np.clip(self.eye_velocity+dt*(torque-c.damping_s_inv*self.eye_velocity),
                                  -c.speed_limit_rad_s,c.speed_limit_rad_s)
        free=self.eye_angle+dt*self.eye_velocity
        self.eye_angle=np.clip(free,-c.angle_limit_rad,c.angle_limit_rad)
        self.eye_velocity[np.abs(free)>c.angle_limit_rad]=0.
        # Unit-inertia apparatus; mechanical power is measured feedback only.
        self.eye_power=float(np.sum(np.abs(torque*self.eye_velocity)))
        self._refresh_directions()

    def observe(self,*,motor_only=False):
        observed=super().observe(motor_only=motor_only)
        physical=[*self.eye_angle,*self.eye_velocity,self.eye_power]
        scales=[self.eye_config.angle_limit_rad]*2+[self.eye_config.speed_limit_rad_s]*2+[8.]
        feedback=[part for v,s in zip(physical,scales) for part in (max(0.,v/s),max(0.,-v/s))]
        return observed|{'schema':VERSION,'values':observed['values']+feedback,
            'resolution':None,'receptor_count':len(self.cells),'eye_config':asdict(self.eye_config),
            'eye_angle_rad':self.eye_angle.tolist(),'eye_velocity_rad_s':self.eye_velocity.tolist(),
            'eye_power_W':self.eye_power,'retinal_centers':self.retinal_centers.tolist(),
            'retinal_widths':self.retinal_widths.tolist(),'visual_gain_per_channel':self.eye_config.visual_gain,
            'camera':{'origin_m':self.origin.tolist(),'forward':self.forward.tolist(),
                      'right':self.right.tolist(),'up':self.up.tolist(),'aperture':self.eye_config.aperture}}

    def stimulus(self,observation):
        v=np.asarray(observation['values'],dtype=float)
        if observation['schema']!=VERSION or v.shape!=(len(self.channels),) or not np.isfinite(v).all() or np.min(v)<0:
            raise ValueError('finite /4 physical measurements required')
        gains=[self.eye_config.visual_gain]*self.vision_width+[.5]*8+[.02]*24+[.05]*10
        return Stimulus(0,tuple((ch,float(value*gain)) for ch,value,gain in zip(self.channels,v,gains) if value>0),intensity=1.)

    def project(self,xy,z=.16):
        """Continuous optical coordinates for calibration/evidence, not labels."""
        self._refresh_directions();v=np.array([*xy,z])-self.origin;d=np.dot(v,self.forward)
        return np.array([np.dot(v,self.right)/d,np.dot(v,self.up)/d])

    def receptor_for_point(self,xy,z=.16):
        # Teacher/scoring only. Never used by inference or physical sensing.
        uv=self.project(xy,z)
        return int(np.argmin(np.sum((self.retinal_centers-uv)**2,axis=1)))

    def ground_point(self,receptor,z=.16):
        self._refresh_directions();d=self._directions[int(receptor)]
        return (self.origin+(z-self.origin[2])/d[2]*d)[:2]

    def eye_servo(self,target_angle):
        c=self.eye_config
        return np.clip(16*(np.asarray(target_angle)-self.eye_angle)-2*self.eye_velocity,-1,1)

    def aim_at_receptor(self,receptor):
        # Calibrated motor execution of a selected retinal location. No world
        # object inventory or task target is consulted.
        delta=np.arctan(self.retinal_centers[int(receptor)])
        return self.eye_servo(self.eye_angle+delta)

    def selected_ray(self,receptor,observation):
        """Ray calibration at acquisition time, even while the eye keeps moving."""
        if observation['schema']!=VERSION:raise ValueError('recorded /4 eye frame required')
        camera=observation['camera'];u,v=self.retinal_centers[int(receptor)]
        direction=np.array(camera['forward'])+u*np.array(camera['right'])+v*np.array(camera['up'])
        return direction/np.linalg.norm(direction)

    def execute_eye_selection(self,receptor,observation):
        if receptor is None:return np.zeros(2)
        if observation['schema']!=VERSION:raise ValueError('recorded /4 eye frame required')
        # A receptor reports an angular area, not a sub-pixel point. If the
        # optical axis is in that area, hold the acquisition direction rather
        # than making perpetual half-pixel corrections. This is a fixed motor
        # calibration, not target/meaning selection or a Core attention gate.
        center=self.retinal_centers[int(receptor)];width=self.retinal_widths[int(receptor)]
        uv=np.where(np.abs(center)<=width/2+1e-12,0.,center)
        camera=observation['camera']
        direction=np.array(camera['forward'])+uv[0]*np.array(camera['right'])+uv[1]*np.array(camera['up'])
        base=-self.origin/np.linalg.norm(self.origin);right=np.array([1.,0.,0.]);up=np.cross(right,base)
        target=np.array([np.arctan2(direction@right,direction@base),
                         np.arctan2(direction@up,np.hypot(direction@right,direction@base))])
        return self.eye_servo(target)

    def execute_hand_selection(self,receptor,observation):
        if receptor is None:return np.zeros(2)
        direction=self.selected_ray(receptor,observation)
        endpoint=(self.origin+(.16-self.origin[2])/direction[2]*direction)[:2]
        # A calibrated position servo acts on the predicted ray, never a task
        # answer. This is execution, not a claim of learned joint mechanics.
        return np.clip(3*(endpoint-[self.pointer.x,self.pointer.y])-.9*np.array([self.pointer.vx,self.pointer.vy]),-1,1)

    def state(self):
        return super().state()|{'schema':VERSION,'eye_config':asdict(self.eye_config),
            'eye_angle':self.eye_angle.tolist(),'eye_velocity':self.eye_velocity.tolist(),'eye_power':self.eye_power}

    @classmethod
    def restore(cls,state):
        if state['schema']!=VERSION:raise ValueError('active-eye world version')
        w=cls(state['seed'],state['weather_seed'],config=EyeConfig(**state['eye_config']),visible_self=state['visible_self'])
        w.set_scene(state['items'],state['variant'],state['positions']);w.pointer=Pointer(**state['pointer'])
        for key in ('marker','time_s','body_temperature','acceleration','motor_power','contact_force','eye_power'):
            setattr(w,key,state[key])
        w.eye_angle=np.array(state['eye_angle']);w.eye_velocity=np.array(state['eye_velocity']);w._refresh_directions()
        return w


def scan_angle(time_s):
    """Answer-independent continuous scan, defined by time, not scene objects."""
    return np.array([.22*math.sin(2*math.pi*time_s/2.6),.18*math.sin(2*math.pi*time_s/4.1+.7)])


def main():
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=float,default=2.);p.add_argument('--gaze',choices=['fixed','scan'],default='scan')
    a=p.parse_args()
    if not 0<a.seconds<=60:p.error('duration in (0,60]')
    w=ActiveEyeClassroom.restore(json.loads(a.state.read_text(encoding='utf-8'))) if a.state else ActiveEyeClassroom()
    a.output.mkdir(parents=True,exist_ok=False)
    with (a.output/'observations.jsonl').open('x',encoding='utf-8') as out:
        for _ in range(math.ceil(a.seconds/.05)):
            ob=w.observe();act=w.eye_servo(scan_angle(w.time_s)) if a.gaze=='scan' else np.zeros(2)
            out.write(json.dumps({'observation':ob,'stimulus':w.stimulus(ob).to_dict(),'eye_action':act.tolist()})+'\n')
            w.advance_physics(eye_action=act)
    (a.output/'state.json').write_text(json.dumps(w.state()),encoding='utf-8')
    print(json.dumps({'schema':VERSION,'output':str(a.output.resolve()),'receptors':len(w.cells),'seconds':w.time_s}))


if __name__=='__main__':main()
