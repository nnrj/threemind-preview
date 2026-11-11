"""Reusable physical-sensor / input-bus / Core / raw-output research session.

No targets are accepted here. Teacher text is ordinary sensory input. Action
selection stays outside this transport; the full input and output are recorded.
"""
from dataclasses import replace
import json
import weakref
from collections import deque
from threemind_core import StateImage
from threemind_runtime.host import create_engine
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.activity_stream import RawActivityStream
from threemind_runtime.sensory import TextSensor,TextSensorConfig
from lab.tools.activity_controller import ActivityLayout
from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.whole_scene_classroom import WholeSceneClassroom
from lab.tools.classroom_eye import DetailedClassroom
from lab.tools.eye_hand_world import EyeHandWorld
from lab.tools.body_playground import BodyPlayground

WORLD_TYPES={'threemind.grounded-classroom/2':DetailedClassroom,
                    'threemind.grounded-classroom/3':WholeSceneClassroom,
                    'threemind.grounded-classroom/4':ActiveEyeClassroom,
                    'threemind.grounded-classroom/5':EyeHandWorld,
                    'threemind.body-playground/1':BodyPlayground}


class SensorimotorSession:
    def __init__(self,world=None,*,state=None,seed=223,plasticity=True,dt_us=50000,
                 kernel_id=None,kernel_config=None,backend='native'):
        if not 1000<=dt_us<=100000:raise ValueError('bounded sensory interval')
        self.dt_us=int(dt_us)
        if state:
            if self.dt_us!=state['dt_us']:raise ValueError('restore recorded sensory interval')
            if kernel_config is not None or (kernel_id is not None and kernel_id!=state['core']['dynamics']):
                raise ValueError('restore the saved kernel and configuration without conversion')
            self.world=WORLD_TYPES[state['world']['schema']].restore(state['world'])
            image=StateImage(json.dumps(state['core'],ensure_ascii=False).encode())
            self.engine=create_engine(state=image,kernel_id=state['core']['dynamics'],backend=backend)
        else:
            self.world=world or ActiveEyeClassroom()
            self.engine=create_engine(dict(kernel_config or {},seed=seed,plasticity=plasticity),
                kernel_id=kernel_id or 'threemind.continuous-memory/2',backend=backend)
        self.reader=ReadoutSession(self.engine,record=lambda row:None,config={
            'structural_readout':{'enabled':False},'temporal_readout':{'enabled':False},'activity_readout':{'enabled':False}},
            state=state['reader'] if state else None)
        self.sensor=TextSensor(91,TextSensorConfig(frame_characters=1,frame_interval_us=self.dt_us))
        self.layout=ActivityLayout((*self.world.channels,*(self.sensor.identity(0x100000+i) for i in range(self.sensor.config.channel_count))))
        self.stream=RawActivityStream();self.current=None;self.history=deque(maxlen=32)
        owner=weakref.ref(self)
        def receive(frame):
            obj=owner()
            if obj is not None:obj.current=frame
        self.stream.subscribe('sensorimotor-session',receive)

    def tick(self,text_frame=None,*,guard=lambda:None,hand=(0.,0.),eye=(0.,0.),mouth=None):
        guard();ob=self.world.observe();stim=self.world.stimulus(ob)
        if text_frame:
            channels=dict(stim.channels);extra=dict(text_frame['stimulus'].channels)
            if channels.keys()&extra.keys():raise ValueError('input port collision')
            channels.update(extra);stim=replace(stim,channels=tuple(sorted(channels.items())))
        self.reader.schedule([{'stimulus':stim,'labels':{}}],source='physical-sampling',adapter_id=ob['schema'])
        self.reader.advance_to(self.engine.time_us+self.dt_us,guard=guard)
        if self.engine.life=='dead':raise RuntimeError('Core died; no automatic revival')
        self.stream.sample(self.engine)
        kwargs={'eye_action':eye} if isinstance(self.world,ActiveEyeClassroom) else {}
        if mouth is not None:
            if not isinstance(self.world,BodyPlayground):raise ValueError('mouth requires a supporting world')
            kwargs['mouth']=mouth
        self.world.advance_physics(hand,self.dt_us/1e6,**kwargs)
        row={'observation':ob,'stimulus':stim.to_dict(),'activity':self.current,
             'hand_action':list(map(float,hand)),'eye_action':list(map(float,eye)),
             'pointer_after':self.world.state()['pointer']}
        if isinstance(self.world,BodyPlayground):row['mouth_action']=list(map(float,mouth if mouth is not None else (0.,0.)))
        self.history.append(row)
        return row

    def snapshot(self):
        return {'dt_us':self.dt_us,'core':self.engine.capture_state().to_dict(),
                'reader':self.reader.capture(),'world':self.world.state()}


def activity_totals(row):
    return {k:sum(float(n[k]) for n in row['activity']['nodes']) for k in ('activation','inhibition','direct','associative')}


def growth_summary(state):
    nodes=state['core']['nodes'];edges=state['core']['edges'];n=len(nodes)
    return {'nodes':n,'edges':len(edges),'directed_density':len(edges)/max(1,n*(n-1)),
            'unique_channels':len({v['channel'] for v in nodes}),'sim_seconds':int(state['core']['time_us'])/1e6}
