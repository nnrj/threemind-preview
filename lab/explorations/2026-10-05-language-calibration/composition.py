"""Separately taught word–vision and vision–sound; no word–sound teaching pair."""
import gzip
import json
import math

import torch
from experiment import (
    TEST_NAMES,
    WORK,
    Input,
    RecordedBackground,
    encoded,
    finish,
    model,
    observe,
    previous,
    probe,
    read_json,
    start_case,
    study,
)

from lab.tools.oscillator_sensor import OscillatorSensor
from lab.tools.sensory_calibration import SensoryResponseLibrary, paired_visual
from lab.tools.service_study import new_json


def source(s,inp,condition,parameter):
    # Formal sources are read-only parents. Copy only their state through restoration.
    parent=WORK/'cases'/f'formal-{inp.route}-{parameter}-s{inp.seed}-{condition}'
    if not (parent/'result.json').exists():raise RuntimeError('formal teaching must complete first')
    path,started=start_case(s,f'composition-{inp.route}-{parameter}-s{inp.seed}-{condition}')
    if started is None:return path
    value=previous.restore(parent/'checkpoint-266',inp.seed)
    cursor=read_json(parent/'checkpoint-266'/'summary.json')['cursor']
    definition=read_json(parent/'definition.json')
    sensor=OscillatorSensor(inp.seed)
    physical=[]; audio=[]
    for item,hz in enumerate((220,330,440,660)):
        mass=float(inp.world.model.body_mass[item+1])
        measurement=sensor.sample(mass,(2*math.pi*hz)**2*mass)
        physical.append(measurement);audio.append(sensor.frame(measurement))
    channels=tuple(sorted({c for frame in audio for c,_ in frame.channels}))
    library=SensoryResponseLibrary(channels,[[dict(frame.channels).get(c,0) for c in channels] for frame in audio])
    definition.update(stage='composition',target_modality='audio',sound_physics=physical,
                      source_parent=parent.name,no_word_sound_copresentation=True)
    definition['libraries']['audio']=library.to_dict()
    lessons=previous.schedule(TEST_NAMES,inp.seed)
    definition['sound_lessons']=lessons
    new_json(path/'definition.json',definition)
    previous.save_state(path/'initial',value,cursor)
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl');lesson_index=0
    for checkpoint in (532,592,832):
        with gzip.open(path/f'process-{checkpoint}.jsonl.gz','xt',encoding='utf-8') as log:
            while value.engine.time_us<checkpoint*1000000 and value.engine.life!='dead':
                until=min(checkpoint*1000000,value.engine.time_us+500000)
                cursor=tape.queue_before(value.reader,cursor,until)
                acquisitions=[]
                while lesson_index<len(lessons) and round((266+lessons[lesson_index]['seconds'])*1e6)<until:
                    row=lessons[lesson_index];item=row['item']
                    from dataclasses import replace
                    frames=[{'stimulus':replace(audio[item],time_us=i*20000),'labels':{}} for i in range(5)]
                    visual=inp.world.sample(item,row['repetition']%8)
                    frames=paired_visual(frames,inp.world.frame(visual),10)
                    value.reader.schedule(frames,at=round((266+row['seconds'])*1e6),source='E45-physical-vision-vibration',adapter_id=sensor.schema)
                    acquisitions.append({'visual':visual,'oscillator_index':item,'name_not_delivered':True})
                    lesson_index+=1
                log.write(encoded({'process':observe(value,until,s),'acquisition':acquisitions}).decode()+'\n')
        previous.save_state(path/f'checkpoint-{checkpoint}',value,cursor)
    finish(s,path,started,{'kind':'source','stage':'composition','parameter':parameter,'route':inp.route,
                          'seed':inp.seed,'condition':condition,'life':value.engine.life,'parent':parent.name})
    print(json.dumps({'composition_source':path.name,'life':value.engine.life}),flush=True)
    return path


def run():
    torch.set_num_threads(2);s=study()
    try:
        selected=read_json(WORK/'parameter-selection.json')
        for seed in (71,89):
            inp=Input(selected['route'],seed,model(s,seed))
            for condition in ('normal','reversed','frozen'):
                path=source(s,inp,condition,selected['parameter'])
                for seconds in (532,592,832):
                    for cue in (-1,*range(8)):
                        probe(s,inp,path,seconds,cue)
    finally:s.db.close()


if __name__=='__main__':run()
