"""Calibrate observations on physical-only independent responses, not new-name answers."""
import json
from dataclasses import replace

import numpy as np
import torch
from experiment import (
    HERE,
    READOUTS,
    TEST_SEEDS,
    WORK,
    Input,
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

from lab.tools.sensory_calibration import SensoryResponseLibrary, process_vector
from lab.tools.service_study import new_json, write_gzip
from threemind_transformer.language_session import LanguageSession


def calibration(s,inp,item,view,intensity):
    key=f'visual-reader-s{inp.seed}-o{item}-v{view}-i{intensity}'
    path,started=start_case(s,key)
    if started is None:return read_json(path/'result.json')
    value=LanguageSession(protocol(inp.seed).model_dump(),config={'seed':inp.seed},seed=inp.seed,readouts=READOUTS)
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl')
    cursor=tape.queue_before(value.reader,0,2000000)
    observe(value,2000000,s)
    measurement=None if item<0 else inp.world.sample(item,view)
    if item>=0:
        visual=replace(inp.world.frame(measurement),intensity=intensity)
        value.reader.schedule([{'stimulus':visual,'labels':{}}],source='E45-reader-physical-calibration',adapter_id='visual-teaching-world/1')
    cursor=tape.queue_before(value.reader,cursor,4000000)
    process=observe(value,4000000,s)
    write_gzip(path/'process.json.gz',process)
    previous.save_state(path/'final',value,cursor)
    result={'kind':'visual-reader','seed':inp.seed,'item':item,'view':view,'intensity':intensity,
            'measurement':measurement,'channels':inp.visual_channels(),
            'vector':process_vector(process,inp.visual_channels()).tolist()}
    finish(s,path,started,result)
    return result


def run():
    torch.set_num_threads(2);s=study()
    try:
        result=[]
        for seed in TEST_SEEDS:
            inp=Input(read_json(WORK/'input-selection.json')['route'],seed,model(s,seed))
            baseline=calibration(s,inp,-1,0,1)
            rows=[calibration(s,inp,item,view,intensity) for item in range(4) for view in (8,9) for intensity in (0.1,0.5)]
            prototypes=[]
            for item in range(4):
                vectors=[np.array(r['vector'])-baseline['vector'] for r in rows if r['item']==item and r['view']==8]
                prototypes.append(np.mean(vectors,axis=0))
            library=SensoryResponseLibrary(inp.visual_channels(),prototypes)
            target=WORK/'libraries'/f'visual-s{seed}.json'
            if not target.exists():new_json(target,library.to_dict())
            for row in rows:
                if row['view']==9:
                    reading=library.read(np.array(row['vector'])-baseline['vector'])
                    result.append({k:row[k] for k in ('seed','item','view','intensity')} | {'reading':reading,'correct':reading['prediction']==row['item']})
            print(json.dumps({'reader_validated_seed':seed,'correct':sum(r['correct'] for r in result if r['seed']==seed)}),flush=True)
        output=HERE/'visual-reader-validation.json'
        if not output.exists():new_json(output,{'rows':result,'correct':sum(r['correct'] for r in result),'count':len(result),
            'formal_names_or_associations_used':False,'calibration_view':8,'validation_view':9})
    finally:s.db.close()


def reanalyse():
    from collections import defaultdict
    result=[]; baselines={}; candidates=[];paired=defaultdict(dict)
    for path in (WORK/'cases').glob('formal-*/result.json'):
        row=read_json(path)
        if row['kind']!='probe' or row['intervention']!='none':continue
        if row['cue_index']==-1:baselines[(row['source'],row['seconds'])]=row
        elif 0<=row['cue_index']<8:candidates.append(row)
    for row in candidates:
        library=SensoryResponseLibrary(**read_json(WORK/'libraries'/f"visual-s{row['seed']}.json"))
        base=baselines[(row['source'],row['seconds'])]
        reading=library.read(np.array(row['vectors']['vision']['whole'])-base['vectors']['vision']['whole'])
        item={k:row[k] for k in ('seed','source','route','parameter','condition','seconds','cue_index','target')}
        item.update(reading=reading,correct=reading['prediction']==row['target']);result.append(item)
        if row['condition'] in ('normal','reversed'):
            paired[(row['parameter'],row['seed'],row['seconds'],row['cue_index'])][row['condition']]=item
    pairs=[{'parameter':k[0],'seed':k[1],'seconds':k[2],'cue_index':k[3],
            'correct':all(r['correct'] for r in v.values())} for k,v in paired.items() if len(v)==2]
    new_json(HERE/'visual-reader-formal.json',{'rows':result,'pairs':pairs,'observer_received_formal_answers':False})


if __name__=='__main__':
    import sys
    reanalyse() if sys.argv[1:] == ['analyse'] else run()
