"""Diagnostic component checks; registered after the first composition result."""
from dataclasses import replace

import numpy as np
import torch
from experiment import (
    HERE,
    READOUTS,
    WORK,
    Input,
    LanguageSession,
    RecordedBackground,
    finish,
    model,
    observe,
    previous,
    protocol,
    read_json,
    start_case,
    study,
)

from lab.tools.oscillator_sensor import OscillatorSensor
from lab.tools.sensory_calibration import SensoryResponseLibrary, process_vector
from lab.tools.service_study import new_json, write_gzip


def audio_calibration(s,inp,parent):
    definition=read_json(parent/'definition.json')
    library=SensoryResponseLibrary(**definition['libraries']['audio']);samples=[]
    for item in (-1,0,1,2,3):
        path,started=start_case(s,f'component-audio-reader-s{inp.seed}-o{item}')
        if started is None:samples.append(read_json(path/'result.json'));continue
        value=LanguageSession(protocol(inp.seed).model_dump(),config={'seed':inp.seed},seed=inp.seed,readouts=READOUTS)
        tape=RecordedBackground(WORK/'physical-telemetry.jsonl');cursor=tape.queue_before(value.reader,0,2000000)
        observe(value,2000000,s)
        if item>=0:
            frame=replace(OscillatorSensor(inp.seed).frame(definition['sound_physics'][item]),intensity=0.5)
            value.reader.schedule([{'stimulus':frame,'labels':{}}],source='E45-independent-sound-reader',adapter_id=OscillatorSensor.schema)
        tape.queue_before(value.reader,cursor,4000000);process=observe(value,4000000,s)
        write_gzip(path/'process.json.gz',process)
        result={'kind':'audio-reader','seed':inp.seed,'item':item,'vector':process_vector(process,library.channels).tolist()}
        finish(s,path,started,result);samples.append(result)
    return [{'seed':inp.seed,'item':r['item'],'reading':library.read(np.array(r['vector'])-samples[0]['vector'])}
            for r in samples[1:]]


def visual_sound(s,inp,parent,seconds,item):
    path,started=start_case(s,f'component-{parent.name}-t{seconds}-v{item}')
    if started is None:return read_json(path/'result.json')
    definition=read_json(parent/'definition.json');checkpoint=parent/f'checkpoint-{seconds}'
    value=previous.restore(checkpoint,inp.seed);cursor=read_json(checkpoint/'summary.json')['cursor']
    observation=inp.world.sample(item,9)
    value.reader.schedule([{'stimulus':replace(inp.world.frame(observation),intensity=0.5),'labels':{}}],
        source='E45-component-visual-cue',adapter_id='visual-teaching-world/1')
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl');tape.queue_before(value.reader,cursor,seconds*1000000+2000000)
    process=observe(value,seconds*1000000+2000000,s);write_gzip(path/'process.json.gz',process)
    library=SensoryResponseLibrary(**definition['libraries']['audio'])
    baseline=read_json(WORK/'cases'/f'{parent.name}-t{seconds}-q-1-none'/'result.json')
    vector=process_vector(process,library.channels)-baseline['vectors']['audio']['whole']
    reading=library.read(vector)
    result={'kind':'component-probe','source':parent.name,'seed':inp.seed,'seconds':seconds,
        'condition':definition['condition'],'component':'vision-to-sound','item':item,
        'reading':reading,'correct':reading['prediction']==item,'physical_cue':observation}
    finish(s,path,started,result)
    return result


def run():
    torch.set_num_threads(2);s=study();selected=read_json(WORK/'parameter-selection.json');rows=[];calibration=[]
    try:
        for seed in (71,89):
            inp=Input(selected['route'],seed,model(s,seed))
            normal=WORK/'cases'/f"composition-{selected['route']}-{selected['parameter']}-s{seed}-normal"
            calibration+=audio_calibration(s,inp,normal)
            for condition in ('normal','reversed','frozen'):
                parent=WORK/'cases'/f"composition-{selected['route']}-{selected['parameter']}-s{seed}-{condition}"
                definition=read_json(parent/'definition.json');library=SensoryResponseLibrary(**definition['libraries']['vision'])
                for seconds in (532,592,832):
                    baseline=read_json(WORK/'cases'/f'{parent.name}-t{seconds}-q-1-none'/'result.json')
                    for cue in range(8):
                        probe=read_json(WORK/'cases'/f'{parent.name}-t{seconds}-q{cue}-none'/'result.json')
                        reading=library.read(np.array(probe['vectors']['vision']['whole'])-baseline['vectors']['vision']['whole'])
                        rows.append({'component':'name-to-vision','source':parent.name,'seed':seed,'condition':condition,
                            'seconds':seconds,'item':cue,'target':probe['target'],'reading':reading,'correct':reading['prediction']==probe['target']})
                    for item in range(4):rows.append(visual_sound(s,inp,parent,seconds,item))
        new_json(HERE/'component-results.json',{'rows':rows,'audio_reader_validation':calibration,
            'posthoc_diagnostic':True,'changes_primary_criterion':False})
        print('component diagnosis complete')
    finally:s.db.close()


if __name__=='__main__':run()
