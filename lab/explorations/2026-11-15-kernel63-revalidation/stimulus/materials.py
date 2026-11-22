"""Frozen E17-scale material construction, without loading a Core."""
import copy
import json
import random
from dataclasses import replace
from pathlib import Path
from threemind_core import Stimulus
from threemind_runtime.body import AmbientConfig, AmbientField
from threemind_runtime.random_stimuli import RandomStimuli, RandomStimulusConfig
from threemind_runtime.stimulus_units import unit_frames
from threemind_runtime.telemetry import HostTelemetryConfig, TelemetryEncoder

SEEDS=(93001,93002)
PRESETS=('ordinary','facilitation')
BACKGROUNDS=('fresh-single','fresh-group','repeated-random','fixed-amplitude','synthetic','telemetry')


def frame(unit):
    return next(iter(unit_frames({'units':[unit]})))['stimulus']


def course(material_dir, seed, preset, family, condition, template=None):
    rows=[]
    def put(stim,kind='teaching'):
        rows.append({'kind':kind,'stimulus':stim.to_dict()})
    if family=='background':
        for i in range(10):put(Stimulus(i*100000,((1001,1.),(1002,1.)),1))
        source=RandomStimuli(RandomStimulusConfig(seed=seed,channels=2,mode=condition if condition in ('fresh-single','fresh-group','fixed-amplitude') else 'fresh-group'))
        fixed=[source.sample() for _ in range(12)] if condition=='repeated-random' else None
        ambient=AmbientField(AmbientConfig(intensity=.2),seed)
        encoder=TelemetryEncoder(seed,HostTelemetryConfig(enabled=True,intensity=.2))
        host=json.loads((material_dir/'host-recording.json').read_bytes())
        for i in range(48):
            at=1000000+i*100000
            if condition=='synthetic':
                stimuli=[replace(s,time_us=at) for _,s in ambient.sample(i*100000)]
            elif condition=='telemetry':
                stim,_=encoder.encode(host[i]['measurements'],monotonic_s=host[i]['monotonic_s'],delivery_us=at)
                stimuli=[stim] if stim else []
            else:
                unit=copy.deepcopy(fixed[i%12]) if fixed else source.sample()
                unit['time_us']=str(at)
                stimuli=[frame(unit)]
            for stim in stimuli:
                assert not {1001,1002}.intersection(c for c,_ in stim.channels)
                put(stim,'background')
        return rows,5800000,[(1001,1.)]
    if family=='intensity':
        for i in range(10 if condition=='repeated1' else 1 if condition=='single4' else 0):
            put(Stimulus(i*100000,((101,1.),(102,1.)),4 if condition=='single4' else 1))
        return rows,1000000,[(101,1.)]
    if family=='equal-drive':
        strength=int(condition); amplitude=1 if strength==1 else .25
        put(Stimulus(0,((101,amplitude),(102,amplitude)),strength))
        return rows,100000,[]
    record=json.loads((material_dir/f'physical-{template}-{seed}.json').read_bytes())
    units=record['units']
    cue=next(m['encoded'] for m in units[100]['measurements'] if m['kind']=='joint_position')
    order=list(range(len(units)))
    if condition=='shuffled':random.Random(seed).shuffle(order)
    if condition!='untrained':
        for cycle in range(2):
            for i,source_i in enumerate(order):
                unit=copy.deepcopy(units[source_i]);unit['time_us']=str((cycle*len(units)+i+1)*20000)
                unit['frame_id']=f'{cycle}:{source_i}'
                if condition=='no-proprioception':
                    unit['elements']=[e for m in unit['measurements'] if m['kind'] not in ('accelerometer','gyroscope') for e in m['encoded']]
                parts=[unit|{'kind':'element','elements':[e],'grouping_basis':'registered split'} for e in unit['elements']] if condition=='split' else [unit]
                for part in parts:
                    if part['elements']:put(frame(part),'physical-recording-replay')
    return rows,8000000,[(v['channel'],v['value']) for v in cue]


def cases(material_dir):
    result=[]
    for seed in SEEDS:
        for preset in PRESETS:
            specs=[('background',c,None) for c in BACKGROUNDS]
            specs += [('intensity',c,None) for c in ('none','single4','repeated1')]
            specs += [('equal-drive',str(c),None) for c in (1,4)]
            specs += [('physical',c,t) for t in ('inertial-cart','gravity-pendulum') for c in ('complete','no-proprioception','split','shuffled','untrained')]
            retention_parent=None
            for family,condition,template in specs:
                key=f'{seed}-{preset}-{family}-{template or "none"}-{condition}'
                rows,end,cue=course(material_dir,seed,preset,family,condition,template)
                cfg={'seed':seed}|({'stp_facilitation_tau_s':1.0} if preset=='facilitation' else {})
                meta={'key':key,'seed':seed,'preset':preset,'family':family,'condition':condition,'template':template,'config':cfg,'parent':None,'stage':'teaching','inputs':rows,'target_us':end,'cue':cue}
                result.append(meta)
                if family=='background' and condition=='fresh-group':retention_parent=meta
                doses=(0,.5) if family in ('background','physical') else (0,.2,1,4) if family=='intensity' else ()
                for dose in doses:
                    inputs=[{'kind':'probe','stimulus':Stimulus(end,tuple(cue),dose).to_dict()}] if dose else []
                    result.append(meta|{'key':key+f'-probe-{dose}','parent':key,'stage':'probe','cue_intensity':dose,
                                        'inputs':inputs,'target_us':end+(15000000 if family=='background' else 5000000)})
            parent=retention_parent
            start=parent['target_us']
            inputs=[{'kind':'maintenance','stimulus':Stimulus(start+d,((999991,1.),),.2).to_dict()} for d in range(0,120000000,500000)]
            result.append(parent|{'key':f'{seed}-{preset}-retention','parent':parent['key'],'stage':'retention','inputs':inputs,'target_us':start+120000000})
    assert len(result)==264 and len({r['key'] for r in result})==264
    return result
