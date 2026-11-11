"""Continuous sensory-pattern observation with no new teaching and causal replay."""
import gzip
import json
import time

import torch
from experiment import (
    HERE,
    TEST_NAMES,
    WORK,
    Input,
    RecordedBackground,
    finish,
    guard,
    model,
    observe,
    previous,
    read_json,
    start_case,
    study,
)
from expression import project

from lab.tools.sensory_calibration import SensoryResponseLibrary, process_vector
from lab.tools.service_study import encoded, new_json, write_gzip
from threemind_transformer.development_model import load


def intervention(s,inp,parent,when):
    from dataclasses import replace

    from interventions import matched_masks
    definition=read_json(parent/'definition.json');results=[]
    checkpoint=532 if definition['stage']=='composition' else 266
    for method in ('none','transmission-off','local','matched'):
        path,started=start_case(s,f"continuous-{parent.name}-at{when}-{method}")
        if started is None:results.append(read_json(path/'result.json'));continue
        value=previous.restore(parent/f'checkpoint-{checkpoint}',inp.seed)
        cursor=read_json(parent/f'checkpoint-{checkpoint}'/'summary.json')['cursor']
        tape=RecordedBackground(WORK/'physical-telemetry.jsonl')
        # Replay the actual common prefix first; no cue or label is inserted.
        while value.engine.time_us<when:
            until=min(when,value.engine.time_us+500000)
            cursor=tape.queue_before(value.reader,cursor,until);observe(value,until,s)
        if method=='transmission-off':value.engine.reconfigure(replace(value.engine.config,propagation_rate=0))
        mask_info=None
        if method in ('local','matched'):
            image=value.engine.capture_state().to_dict()
            sensory={c for lib in definition['libraries'].values() for c in lib['channels']}
            all_channels={int(n['channel']) for n in image['nodes']}
            mask_info=matched_masks(image,sensory,all_channels)
            if mask_info:
                value.engine.intervene(edges=mask_info['target' if method=='local' else 'matched'],action='silence')
        cursor=tape.queue_before(value.reader,cursor,when+2000000)
        process=observe(value,when+2000000,s);write_gzip(path/'process.json.gz',process)
        result={'kind':'uncued-intervention','source':parent.name,'when_us':when,'method':method,'mask':mask_info,
                'transport':process['transport_delta'],'vectors':{key:process_vector(process,val['channels']).tolist() for key,val in definition['libraries'].items()}}
        finish(s,path,started,result);results.append(result)
    return results


def run():
    torch.set_num_threads(2);s=study();selected=read_json(WORK/'parameter-selection.json');started=time.monotonic()
    guard(s,True)
    compute_before=s.completed_wall+s.model_seconds
    try:
        summary=[];interventions=[]
        for seed in (71,89,107):
            candidates={}
            heads={kind:load(WORK/'models'/f'expression-{kind}-s{seed}.safetensors','cuda' if torch.cuda.is_available() else 'cpu')[0]
                   for kind in ('vision','words')}
            sources=[(stage,condition) for stage in (('formal','composition') if seed in (71,89) else ('formal',))
                     for condition in ('normal','reversed','frozen')]
            for stage,condition in sources:
                parent=WORK/'cases'/f"{stage}-{selected['route']}-{selected['parameter']}-s{seed}-{condition}"
                base=532 if stage=='composition' else 266
                target=WORK/'continuous'/f'{parent.name}.jsonl.gz'
                if target.exists():
                    raise RuntimeError('continuous output already exists; preserve it and resume explicitly')
                definition=read_json(parent/'definition.json');libraries={k:SensoryResponseLibrary(**v) for k,v in definition['libraries'].items()}
                target.parent.mkdir(parents=True,exist_ok=True)
                last={k:0 for k in libraries};declining={k:0 for k in libraries};last_time=None
                records=[]
                for boundary in (base+60,base+300):
                    with gzip.open(parent/f'process-{boundary}.jsonl.gz','rt',encoding='utf-8') as source:
                        for line in source:
                            r=json.loads(line);p=r['process'];observed={}
                            for kind,library in libraries.items():
                                reading=library.read(process_vector(p,library.channels));observed[kind]=reading
                            for frame in p['trajectory']:
                                when=int(frame['time_us'])
                                if last_time is not None and when<=last_time:continue
                                elapsed=0 if last_time is None else when-last_time
                                for kind,library in libraries.items():
                                    channels=set(library.channels)
                                    amount=sum(n['activation'] for n in frame['nodes'] if int(n['channel']) in channels)
                                    if (stage not in candidates and condition!='frozen' and when>=(base+5)*1000000 and
                                            amount>last[kind]+1e-8 and declining[kind]>=100000):
                                        candidates[stage]={'source':parent.name,'modality':kind,'when_us':max(base*1000000,when-200000)}
                                    declining[kind]=declining[kind]+elapsed if amount<=last[kind]+1e-8 else 0
                                    last[kind]=amount
                                last_time=when
                            records.append({'start_us':p['start_us'],'end_us':p['end_us'],'observed':observed,
                                            'transport':p['transport_delta'],
                                            'projected':{k:project(p,h.basis) for k,h in heads.items()}})
                for kind,head in heads.items():
                    for start in range(0,len(records),32):
                        block=records[start:start+32];texts=head.decode([r['projected'][kind]['values'] for r in block])
                        for row,text in zip(block,texts,strict=True):row.setdefault('text',{})[kind]=text
                        guard(s)
                        if compute_before+time.monotonic()-started>14400:
                            raise RuntimeError('aggregate continuous-observation compute budget')
                with gzip.open(target,'xt',encoding='utf-8') as stream:
                    for row in records:
                        row['magnitude']={k:v['raw_sum'] for k,v in row.pop('projected').items()}
                        stream.write(encoded(row).decode()+'\n')
                summary.append({'source':parent.name,'seed':seed,'condition':condition,'windows':len(records),
                    'text_windows':{k:sum(bool(r['text'][k]['text']) for r in records) for k in heads},
                    'sensory_active_windows':{k:sum(r['observed'][k]['activity_l1']>1e-8 for r in records) for k in libraries}})
                print(json.dumps({'continuous_source':parent.name,'windows':len(records),'candidate':candidates.get(stage)}),flush=True)
            for candidate in candidates.values():
                inp=Input(selected['route'],seed,model(s,seed))
                interventions+=intervention(s,inp,WORK/'cases'/candidate['source'],candidate['when_us'])
        elapsed=time.monotonic()-started
        branch_seconds=sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('continuous-*/result.json'))
        new_json(HERE/'continuous-results.json',{'sources':summary,'interventions':interventions,'word_order':TEST_NAMES,
            'background':'recorded physical telemetry present','new_teaching':False,'wall_seconds':elapsed,
            'analysis_wall_seconds':max(0,elapsed-branch_seconds)})
    finally:s.db.close()


if __name__=='__main__':run()
