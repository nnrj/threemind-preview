"""A kinematic camera scans physical MuJoCo objects; no answer enters Core.

The scene retains all four objects. Pan position is a virtual camera joint
encoder, not a claimed accelerometer or a semantic left/right label.
"""
import math
import mujoco
import numpy as np
from threemind_core import Stimulus
from lab.tools.language_teaching_world import TeachingWorld


class VisualEventWorld(TeachingWorld):
    def measurement(self,item,angle,view=0):
        target=self.data.xpos[item+1].copy()
        origin=target+np.array([-.55-.015*(view%3),.012*(view-1),.20])
        forward=target-origin;forward/=np.linalg.norm(forward)
        right=np.cross(forward,np.array([0.,0.,1.]));right/=np.linalg.norm(right)
        up=np.cross(right,forward)
        heading=math.cos(angle)*forward+math.sin(angle)*right
        screen_right=math.cos(angle)*right-math.sin(angle)*forward
        rays=[];values=[]
        for x,y in ((0,0),(-.13,0),(.13,0),(0,-.13),(0,.13)):
            direction=heading+x*screen_right+y*up;direction/=np.linalg.norm(direction)
            geometry=np.array([-1],dtype=np.int32)
            distance=float(mujoco.mj_ray(self.model,self.data,origin,direction,None,1,-1,geometry))
            rgb=self.model.geom_rgba[int(geometry[0]),:3].astype(float) if geometry[0]>=0 else np.zeros(3)
            values.extend([0. if distance<0 else 1/(1+distance),*rgb.tolist()])
            rays.append({'distance_m':distance,'rgb':rgb.tolist(),'direction':direction.tolist()})
        return {'schema':'threemind.visual-event-world/1','values':values,'rays':rays,
                'camera_origin_m':origin.tolist(),'camera_pan_rad':angle,'object_positions_m':self.data.xpos[1:].tolist(),
                'reference':'kinematic camera pan encoder; not an answer or absolute time',
                'active_body_control':False,'all_four_objects_present':True}

    def event(self,item,order,view=0,split=False):
        if order not in (-1,1):raise ValueError('scan order must be signed')
        # Both orders have identical exposure multiset and identical endpoints.
        angles=np.array([0,.065,.13,.065,0,-.065,-.13,-.065,0])*order
        frames=[];measurements=[]
        for i,angle in enumerate(angles):
            m=self.measurement(item,float(angle),view);measurements.append(m)
            visual=self.frame(m,amount=2/len(angles))
            # Fixed physical conversion; a constant support/reference plus
            # signed joint displacement. Perception remains anonymous.
            ref=((self.wiring.identity(0xD10000),.2/len(angles)),)
            if angle:
                ref+=((self.wiring.identity(0xD10001+int(angle<0)),abs(float(angle))/.13*.2/len(angles)),)
            when=i*100000
            if split:
                frames.extend([{'stimulus':Stimulus(when,visual.channels,1.),'labels':{}},
                               {'stimulus':Stimulus(when,ref,1.),'labels':{}}])
            else:frames.append({'stimulus':Stimulus(when,tuple(sorted(visual.channels+ref)),1.),'labels':{}})
        return frames,measurements

    def reference_channels(self):return tuple(self.wiring.identity(0xD10000+i) for i in range(3))
