"""Prospective mechanism instrument; does not replace a personal task adapter.

Anonymous paired stimuli, isolated life-maintaining background, and complete
temporal activity measurement. No old individual is loaded or upgraded.
"""
from __future__ import annotations
import copy
import random
from threemind_core import Stimulus, StateImage
from threemind_kernels.local52 import Local52Config, Local52Engine

FIELDS=('activation','inhibition','direct','associative')
COURSES=('weak','ordinary','strong','massed','spaced')
SYMBOLS=('background','cue','out0','out1','neutral0','neutral1','neutral2')
TIMES={'weak':(127.,),'ordinary':(127.,),'strong':(127.,),
       'massed':tuple(float(x) for x in range(120,128)),
       'spaced':(16.,17.,19.,23.,31.,47.,79.,127.)}
DOSES={'weak':.12,'ordinary':.4,'strong':1.,'massed':.4,'spaced':.4}


class Assay:
    def __init__(self,seed,curve,relaxation,identity):
        self.seed,self.identity=seed,identity
        self.mapping=dict(zip(SYMBOLS,random.Random(seed).sample(range(1,2**32),len(SYMBOLS))))
        self.core=Local52Engine(Local52Config(seed=seed,energy_seed=seed^0x31E629,
            decay_curve=curve,retention_relaxation_enabled=relaxation))
        self.next_background=0
        self.events=[]
        self.cursor={'stage':'birth'}

    def inject(self,t,values,role):
        channels=tuple((self.mapping[k],float(v)) for k,v in values.items())
        self.core.inject(Stimulus(t,channels))
        self.events.append(dict(time_us=t,channels=[list(x) for x in channels],role=role))

    def advance(self,t):
        if t<self.core.time_us:raise ValueError('no experimental rollback')
        # Each background event is separate, even when simultaneous with a lesson.
        # It cannot create a co-stimulated background-to-task edge.
        while self.next_background<=t:
            self.inject(self.next_background,{'background':.2},'background')
            self.next_background+=500_000
        self.core.advance_to(t)
        if self.core.life=='dead':raise RuntimeError('new subject death; preserve complete state and in-flight')

    def state(self):
        return dict(schema='threemind.retention-assay/1',seed=self.seed,identity=self.identity,
            core=self.core.capture_state().to_dict(),mapping=self.mapping,
            next_background=self.next_background,events=copy.deepcopy(self.events),
            cursor=copy.deepcopy(self.cursor),
            apparatus=dict(input='fixed anonymous stimulus adapter',output='four-field temporal instrument',
                learned_peripherals=False,body='isolated non-behavioral preparation'))

    @classmethod
    def restore(cls,value):
        s=cls.__new__(cls)
        for k in ('seed','identity','mapping','next_background','events','cursor'):
            setattr(s,k,copy.deepcopy(value[k]))
        s.core=Local52Engine(state=StateImage.from_dict(value['core']))
        if s.state()!=value:raise RuntimeError('complete assay state differs')
        return s

    def measure(self):
        before=self.core.capture_state().payload
        g=self.core.graph();names={v:k for k,v in self.mapping.items()}
        ids={n['id']:names[n['channel']] for n in g['nodes']}
        nodes=[dict(n,symbol=ids[n['id']]) for n in g['nodes']]
        edges=[dict(e,source_symbol=ids[e['source']],target_symbol=ids[e['target']]) for e in g['edges']]
        if any('background' in (e['source_symbol'],e['target_symbol']) for e in edges):
            raise RuntimeError('background unexpectedly connected to task')
        if before!=self.core.capture_state().payload:raise RuntimeError('measurement changed state')
        return dict(time_us=self.core.time_us,nodes=nodes,edges=edges)

    def teach(self,course,familiar,history):
        assert course in COURSES and history in (0,1) and self.core.time_us==0
        self.cursor=dict(stage='teaching',course=course,familiar=bool(familiar),history=history)
        # Familiarization has the same amount and timing of stimulation. Its
        # single-channel events create no task connections; all channels remain
        # anonymous to Core. The novel arm receives unrelated neutral channels.
        symbols=('cue','out0','out1') if familiar else ('neutral0','neutral1','neutral2')
        for i in range(12):
            t=100_000+i*1_000_000;self.advance(t)
            self.inject(t,{symbols[i%3]:.4},'familiarization' if familiar else 'matched-neutral')
        for second in TIMES[course]:
            t=round(second*1e6);self.advance(t)
            self.inject(t,{'cue':DOSES[course],f'out{history}':DOSES[course]},'paired-teaching')
        self.advance(128_000_000)
        self.cursor['stage']='taught'
        return self.measure()

    def window(self,values=None):
        start=self.core.time_us
        self.advance(start)
        if values:self.inject(start,values,'cue-probe')
        raw=[]
        for i in range(20):
            self.advance(start+(i+1)*50_000)
            by={n['channel']:n for n in self.core.observation_nodes()}
            raw.append({name:{f:by.get(c,{}).get(f,0.) for f in FIELDS} for name,c in self.mapping.items()})
        return dict(start_us=start,end_us=self.core.time_us,
            frame_times_us=[start+(i+1)*50_000 for i in range(20)],raw=raw)

    def first_probe(self,delay,cue=True):
        # Delay is measured from the fixed end of teaching (128 s), not from
        # an earlier test. The baseline contains background but no cue.
        assert delay>=1 and self.cursor['stage']=='taught'
        self.advance(128_000_000+round((delay-1)*1e6))
        baseline=self.window()
        before=self.measure()
        response=self.window({'cue':.8} if cue else None)
        self.cursor.update(stage='completed',delay_seconds=delay,cue_present=bool(cue))
        return dict(delay_seconds=delay,cue_present=bool(cue),before=before,baseline=baseline,response=response,after=self.measure())


def temporal_contrast(window):
    """Fixed instrument, independent of the history/answer used for scoring."""
    return {f:sum(frame['out1'][f]-frame['out0'][f] for frame in window['raw'])*.05 for f in FIELDS}
