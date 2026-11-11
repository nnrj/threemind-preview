"""Independent modality-specific scratch expression, with raw processes retained."""
import gzip
import json
import time
from types import SimpleNamespace

import numpy as np
import torch
from experiment import (
    HERE,
    READOUTS,
    TEST_NAMES,
    TEST_SEEDS,
    WORK,
    Input,
    LanguageSession,
    RecordedBackground,
    finish,
    guard,
    model,
    observe,
    protocol,
    read_json,
    start_case,
    study,
)

from lab.tools.language_teaching_world import WORDS
from lab.tools.service_study import new_json, write_gzip
from threemind_transformer.development import TrajectoryBasis
from threemind_transformer.development_model import fit, load


def project(process,basis,left=None,right=None):
    start=int(process['start_us']) if left is None else left
    end=int(process['end_us']) if right is None else right
    channels=set(basis.channels)
    scoped={'start_us':str(start),'end_us':str(end),'planned_end_us':str(end),'trajectory':[
        {'time_us':r['time_us'],'nodes':[n for n in r['nodes'] if int(n['channel']) in channels]}
        for r in process['trajectory'] if start<=int(r['time_us'])<=end]}
    values=np.array(basis.project(scoped)['values'])
    magnitude=float(values.sum())
    if magnitude:values/=magnitude
    return {'values':values.tolist(),'raw_sum':magnitude,'scope':'declared modality only; original full process retained'}


def word_sample(s,inp,item,intensity):
    path,started=start_case(s,f'word-reader-s{inp.seed}-n{item}-i{intensity}')
    if started is None:return path
    value=LanguageSession(protocol(inp.seed).model_dump(),config={'seed':inp.seed},seed=inp.seed,readouts=READOUTS)
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl')
    cursor=tape.queue_before(value.reader,0,2000000);observe(value,2000000,s)
    value.reader.schedule(inp.frames(TEST_NAMES[item],intensity),source='E45-independent-name-reader',adapter_id='language-dose-study/1')
    tape.queue_before(value.reader,cursor,4000000)
    process=observe(value,4000000,s)
    write_gzip(path/'process.json.gz',process)
    finish(s,path,started,{'kind':'word-reader','seed':inp.seed,'item':item,'intensity':intensity,
                          'word':TEST_NAMES[item],'formal_object_assignment_exposed':False})
    return path


def processes(path):
    with gzip.open(path/'process.json.gz','rt',encoding='utf-8') as stream:return json.load(stream)


def samples(inp,kind):
    channels=inp.visual_channels() if kind=='vision' else inp.word_channels(TEST_NAMES)
    basis=TrajectoryBasis(channels)
    training=[];validation=[]
    pattern=f'visual-reader-s{inp.seed}-*' if kind=='vision' else f'word-reader-s{inp.seed}-*'
    for path in sorted((WORK/'cases').glob(pattern)):
        if not (path/'result.json').exists():continue
        row=read_json(path/'result.json');p=processes(path)
        train=row.get('view',8)==8 if kind=='vision' else row['intensity']!=1
        label='' if row['item']<0 else (WORDS if kind=='vision' else TEST_NAMES)[row['item']]+'。'
        for index in range(4):
            left=int(p['start_us'])+index*500000;right=left+500000
            item=project(p,basis,left,right)
            item.update(text=label if item['raw_sum'] else '',source=path.name,window=index)
            (training if train else validation).append(item)
    for i in range(8):
        training.append({'values':np.zeros((basis.bins,basis.width)).tolist(),'text':'','source':'explicit-zero','window':i})
    return basis,training,validation


def train_heads():
    torch.set_num_threads(2);s=study();validation=[]
    try:
        selected=read_json(WORK/'parameter-selection.json')
        for seed in TEST_SEEDS:
            inp=Input(selected['route'],seed,model(s,seed))
            for item in range(4):
                for intensity in (0.1,0.5,1):word_sample(s,inp,item,intensity)
            for kind in ('vision','words'):
                basis,training,held=samples(inp,kind)
                path=WORK/'models'/f'expression-{kind}-s{seed}.safetensors'
                if not path.exists():
                    new_json(path.with_suffix('.training.json'),{'basis':basis.to_dict(),'samples':training,
                                                               'feature_protocol':'E45-modality-L1-trajectory/1',
                                                               'modality':kind,'normalization':'whole-window L1; raw_sum retained',
                                                               'formal_assignments_exposed':False,
                                                               'heldout_sources':sorted({r['source'] for r in held})})
                    s.active_case=SimpleNamespace(born_wall=time.monotonic())
                    result=fit(training,basis,path,seed=seed,steps=1200,checkpoints=(),
                               device='cuda' if torch.cuda.is_available() else 'cpu',check=lambda:guard(s))
                    new_json(path.with_suffix('.json'),result);s.active_case=None
                head,_=load(path,'cuda' if torch.cuda.is_available() else 'cpu')
                output=head.decode([r['values'] for r in held])
                for row,text in zip(held,output,strict=True):
                    validation.append({'seed':seed,'modality':kind,'source':row['source'],'window':row['window'],
                                       'expected':row['text'],'raw_sum':row['raw_sum'],'output':text,
                                       'correct':text['text']==row['text']})
                print(json.dumps({'expression':kind,'seed':seed,'validation_correct':sum(r['correct'] for r in validation if r['seed']==seed and r['modality']==kind),
                                  'validation_total':len(held)}),flush=True)
                del head
        new_json(HERE/'expression-validation.json',{'rows':validation,'formal_assignments_exposed':False})
    finally:s.db.close()


def decode():
    torch.set_num_threads(2);s=study();started=time.monotonic()
    s.active_case=SimpleNamespace(born_wall=started)
    try:
        for seed in TEST_SEEDS:
            for kind in ('vision','words'):
                target=WORK/'expression'/f'{kind}-s{seed}.json'
                if target.exists():continue
                head,_=load(WORK/'models'/f'expression-{kind}-s{seed}.safetensors','cuda' if torch.cuda.is_available() else 'cpu')
                rows=[];values=[];metadata=[]
                def flush(values=values,head=head,rows=rows,metadata=metadata):
                    if not values:return
                    translated=head.decode(values)
                    rows.extend(r|{'output':out} for r,out in zip(metadata,translated,strict=True))
                    values.clear();metadata.clear();guard(s)
                for path in sorted((WORK/'cases').glob(f'formal-*-s{seed}-*/result.json')):
                    case=read_json(path)
                    if case['kind']!='probe':continue
                    process=processes(path.parent)
                    for i in range(4):
                        left=int(process['start_us'])+i*500000
                        item=project(process,head.basis,left,left+500000)
                        values.append(item['values']);metadata.append({k:case[k] for k in ('source','parameter','condition','seconds','cue_index','target','intervention')} |
                            {'case':path.parent.name,'window':i,'raw_sum':item['raw_sum']})
                        if len(values)>=32:flush()
                flush();new_json(target,{'modality':kind,'seed':seed,'rows':rows,'no_cross_window_cache':True})
                print(json.dumps({'translated_modality':kind,'seed':seed,'windows':len(rows)}),flush=True)
                del head
        new_json(WORK/'models'/'expression-decoding.json',{'wall_seconds':time.monotonic()-started})
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':
    import sys
    decode() if sys.argv[1:]==['decode'] else train_heads()
