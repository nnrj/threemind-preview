"""Isolated prospective-M4 instrument: genuine optics, body and personal readers.

This module does not launch a study, teach a formal subject, or modify Core.
The new wrapper randomizes both optical and text port identities at birth;
historical E69 objects and the historical whole-system schema are untouched.
"""
from __future__ import annotations

from dataclasses import asdict
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.activity_controller import ActivityLayout
from lab.tools.calibrated_activity import CalibratedActivity
from lab.tools.centered_recognition import WORDS
from lab.tools.continuous_foveal_motor import ContinuousFovealMotor
from lab.tools.sensorimotor_session import SensorimotorSession
from threemind_runtime.sensory import TextSensor,TextSensorConfig

_spec=importlib.util.spec_from_file_location('m4_frozen_e69_system',ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/system.py')
_old=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_old)
Executor=_old.Executor
window=_old.window
SCHEMA='threemind.regional-eye-hand-whole/1'
KERNEL='threemind.continuous-memory/5.1'


def tensor_tree(value):
    if torch.is_tensor(value):
        a=value.detach().cpu().contiguous()
        return {'tensor':str(a.dtype),'shape':list(a.shape),'sha256':hashlib.sha256(a.numpy().tobytes()).hexdigest()}
    if isinstance(value,np.ndarray):
        return {'array':str(value.dtype),'shape':list(value.shape),'sha256':hashlib.sha256(value.tobytes()).hexdigest()}
    if isinstance(value,dict):return {str(k):tensor_tree(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [tensor_tree(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class Whole:
    def __init__(self,seed,*,identity):
        self.seed=int(seed);self.identity=identity
        self.text_seed=self.seed ^ 0x6D3412
        self.session=SensorimotorSession(ActiveEyeClassroom(seed=self.seed ^ 0x3C0411,weather_seed=self.seed ^ 0xB75102),
                seed=self.seed,kernel_id=KERNEL,backend='native')
        self._text_mapping()
        s=self.session;w=s.world
        blank=s.engine.capture_state().to_dict()
        assert not blank['nodes'] and not blank['edges'] and int(blank['time_us'])==0
        with torch.random.fork_rng(devices=[]):
            self.motor=ContinuousFovealMotor(s.layout.channels,w.channels[:w.vision_width],w.retinal_centers,w.retinal_widths,
                                            identity=identity,seed=self.seed).to('cpu')
            self.words=CalibratedActivity(s.layout.channels,WORDS,identity,seed=self.seed).to('cpu').eval()
        self.executor=Executor();self.phase='birth';self.cursor=0
        # Small instrument-calibration corpora are inlined in the complete state.
        # A formal study must freeze a separate bounded immutable-corpus design.
        self.corpus=[];self.branch=None

    def _text_mapping(self):
        s=self.session
        s.sensor=TextSensor(self.text_seed,TextSensorConfig(frame_characters=1,frame_interval_us=s.dt_us))
        s.layout=ActivityLayout((*s.world.channels,*(s.sensor.identity(0x100000+i) for i in range(s.sensor.config.channel_count))))

    def state(self):
        s=self.session
        return {'schema':SCHEMA,'identity':self.identity,'seed':self.seed,'text_seed':self.text_seed,
                'session':s.snapshot(),'history':list(s.history),'current':s.current,'published':s.stream.published,
                'sensor':asdict(s.sensor.config),'layout':list(s.layout.channels),'executor':self.executor.state(),
                'phase':self.phase,'cursor':self.cursor,'corpus':copy.deepcopy(self.corpus),'branch':copy.deepcopy(self.branch)}

    def canonical(self):
        result=self.state()
        for name in ('motor','words'):
            head=getattr(self,name)
            result[name]={'weights':tensor_tree(head.state_dict()),'optimizer':tensor_tree(head.optimizer.state_dict()),
                          'rng':tensor_tree(head.learning_rng),'computed':head.computed_updates,'committed':head.committed_updates,
                          'training':head.training,'identity':head.identity,'seed':head.seed}
        return result

    def save(self,folder):
        folder=Path(folder);part=folder.with_name(folder.name+'.partial')
        if folder.exists():raise FileExistsError(folder)
        part.mkdir(parents=True,exist_ok=False)
        body=json.dumps(self.state(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        (part/'system.json.gz').write_bytes(gzip.compress(body,mtime=0))
        self.motor.save(part/'motor');self.words.save(part/'words')
        manifest={p.relative_to(part).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in part.rglob('*') if p.is_file()}
        (part/'complete.json').write_text(json.dumps({'schema':SCHEMA,'canonical_sha256':digest(self.canonical()),
             'files':manifest,'time_us':self.session.engine.time_us,'identity':self.identity},sort_keys=True),encoding='utf-8')
        part.rename(folder)

    @classmethod
    def restore(cls,folder):
        folder=Path(folder);receipt=json.loads((folder/'complete.json').read_bytes())
        assert receipt['schema']==SCHEMA
        for n,h in receipt['files'].items():
            p=(folder/n).resolve()
            if not p.is_relative_to(folder.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=h:
                raise ValueError('incomplete or modified instrument state')
        value=json.loads(gzip.decompress((folder/'system.json.gz').read_bytes()))
        if value['schema']!=SCHEMA:raise ValueError('wrong instrument identity')
        a=cls.__new__(cls)
        for n in ('identity','seed','text_seed','phase','cursor','corpus','branch'):setattr(a,n,value[n])
        a.session=SensorimotorSession(state=value['session'],dt_us=value['session']['dt_us'],backend='native')
        a._text_mapping();s=a.session
        if list(s.layout.channels)!=value['layout'] or asdict(s.sensor.config)!=value['sensor']:
            raise ValueError('mapping changed during restoration')
        s.history.extend(value['history']);s.current=value['current'];s.stream.published=value['published']
        with torch.random.fork_rng(devices=[]):
            a.motor=ContinuousFovealMotor.restore(folder/'motor',device='cpu',expected_identity=a.identity)
            a.words=CalibratedActivity.restore(folder/'words',device='cpu')
        a.executor=Executor.restore(value['executor'])
        if a.words.identity!=a.identity or a.motor.layout.channels!=s.layout.channels or a.words.layout.channels!=s.layout.channels:
            raise ValueError('personal peripheral mismatch')
        if digest(a.canonical())!=receipt['canonical_sha256']:raise ValueError('whole-system restoration differs')
        return a


def calibrate_instrument(a,rows):
    """Two declared external calibration updates, not scientific task learning."""
    x=window(a.motor.layout,rows)[None]
    ob=rows[-1]['observation'];w=a.session.world
    def receptor(z):
        c=ob['camera'];ray=np.array([.4,.3,z])-np.array(c['origin_m'])
        uv=np.array([ray@c['right'],ray@c['up']])/(ray@c['forward'])
        return int(np.argmin(np.sum((w.retinal_centers-uv)**2,axis=1)))
    eye=receptor(.52);hand=receptor(.16)
    a.corpus.append({'x':x.tolist(),'eye':[eye],'hand':[hand],'move':[1],'source':'instrument-calibration-only'})
    before=a.session.engine.time_us
    result=a.motor.continue_calibration(x,[eye],[hand],[1],steps=2,batch_size=1)
    if a.session.engine.time_us!=before:raise RuntimeError('external calibration advanced Core')
    return result
