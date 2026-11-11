"""R46b apparatus: declared strong-intensity and connection-novelty contrasts.

New research subjects only. This is a local mechanism assay with fixed input
adapters and complete temporal measurement, not a learned task-output adapter.
"""
import copy
import random
from dataclasses import replace
from threemind_core import Stimulus,StateImage
from threemind_kernels.local52 import Local52Config,Local52Engine
from retention_assay import Assay,SYMBOLS

CURVES=('exponential','inverse-logarithmic','power-law')
ARMS={'strong':('equal-drive-normal','strong-intensity','strong-gain-zero'),
      'novelty':('arrival-novelty','arrival-gain-zero')}


def profile(origin,family):
    assert 0<=origin<8
    if family=='strong':
        return dict(drive=(.4,.6,.8,1.)[origin%4],strong_intensity=2.+origin//4)
    if family=='novelty':
        return dict(old_amplitude=(.4,.8)[origin//4],new_amplitude=(.4,.8)[(origin//2)%2],
                    new_offset_us=(50_000,75_000)[origin%2])
    raise ValueError(family)


def cases():
    rows=[]
    for origin in range(8):
        for curve in CURVES:
            for relaxation in (True,False):
                for family,arms in ARMS.items():
                    for arm in arms:
                        for delay in (1,300):
                            for cue in (True,False):
                                key=f'o{origin}/{curve}-{int(relaxation)}/{family}/{arm}/d{delay}/q{int(cue)}'
                                rows.append(dict(key=key,origin=origin,seed=261110100+origin,curve=curve,
                                    relaxation=relaxation,family=family,arm=arm,delay=delay,cue=cue,
                                    profile=profile(origin,family)))
    return rows


class StimulusAssay(Assay):
    teaching_end_us=1_000_000

    def __init__(self,case,identity):
        self.seed,self.identity=case['seed'],identity
        self.mapping=dict(zip(SYMBOLS,random.Random(self.seed).sample(range(1,2**32),len(SYMBOLS))))
        self.next_background=0;self.events=[];self.cursor={'stage':'birth'}
        self.case=copy.deepcopy(case)
        cfg=Local52Config(seed=self.seed,energy_seed=self.seed^0x31E629,
            decay_curve=case['curve'],retention_relaxation_enabled=case['relaxation'])
        if case['arm']=='strong-gain-zero':cfg=replace(cfg,intensity_gain=0.)
        elif case['arm']=='arrival-gain-zero':cfg=replace(cfg,local_novelty_gain=0.)
        # The selected configuration belongs to this new birth. No developed
        # state is reconfigured or replaced.
        self.core=Local52Engine(cfg)

    def inject(self,t,values,role,intensity=1.):
        channels=tuple((self.mapping[k],float(v)) for k,v in values.items())
        event=Stimulus(t,channels,intensity=float(intensity))
        self.core.inject(event)
        self.events.append(dict(time_us=t,channels=[list(x) for x in channels],
            intensity=event.intensity,role=role))

    def state(self):
        out=super().state();out['schema']='threemind.stimulus-retention-assay/1'
        out['case']=copy.deepcopy(self.case)
        return out

    @classmethod
    def restore(cls,value):
        s=cls.__new__(cls)
        for k in ('seed','identity','mapping','next_background','events','cursor','case'):
            setattr(s,k,copy.deepcopy(value[k]))
        s.core=Local52Engine(state=StateImage.from_dict(value['core']))
        if s.state()!=value:raise RuntimeError('complete stimulus-assay state differs')
        return s

    def sample(self):
        # Preserve lazy physical state as well as the projected graph.
        state=self.core.capture_state().to_dict();graph=self.measure()
        assert self.core.capture_state().to_dict()==state
        return dict(core=state,graph=graph)

    def teach_mechanism(self):
        assert self.core.time_us==0 and self.cursor['stage']=='birth'
        c=self.case;p=c['profile'];samples={}
        self.cursor=dict(stage='teaching',family=c['family'],arm=c['arm'])
        if c['family']=='strong':
            t=100_000;self.advance(t)
            intensity=1. if c['arm']=='equal-drive-normal' else p['strong_intensity']
            amplitude=p['drive']/intensity
            self.inject(t,dict(cue=amplitude,out0=amplitude),'target-teaching',intensity)
            self.advance(t);samples['immediate']=self.sample()
        else:
            self.advance(100_000)
            self.inject(100_000,dict(cue=p['old_amplitude'],out1=p['old_amplitude']),'prior-connection')
            t=100_000+p['new_offset_us'];self.advance(t)
            samples['before_new']=self.sample()
            self.inject(t,dict(cue=p['new_amplitude'],out0=p['new_amplitude']),'target-teaching')
            self.advance(t);samples['pending']=self.sample()
            self.advance(310_000);samples['after_window']=self.sample()
        self.advance(self.teaching_end_us);self.cursor['stage']='taught'
        return dict(samples=samples,taught=self.measure())

    def first_probe(self,delay,cue=True):
        assert delay in (1,300) and self.cursor['stage']=='taught'
        self.advance(self.teaching_end_us+(delay-1)*1_000_000)
        baseline=self.window();before=self.measure()
        response=self.window(dict(cue=.8) if cue else None)
        self.cursor.update(stage='completed',delay_seconds=delay,cue_present=bool(cue))
        return dict(delay_seconds=delay,cue_present=bool(cue),before=before,
            baseline=baseline,response=response,after=self.measure())
