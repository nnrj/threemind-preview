"""E46: native activity calibration outside the unchanged kernel."""
import argparse
from dataclasses import replace
import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.service_study import Study, StudyConfig, encoded, new_json, read_json, write_gzip
from lab.tools.recorded_background import RecordedBackground
from lab.tools.sensory_calibration import paired_visual
from lab.tools.language_teaching_world import WORDS
from threemind_transformer.development import input_summary
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.native_readout import NativeProjection

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/native-language-20261005'
OLD = ROOT / '.work/language-calibration-20261005'
spec = importlib.util.spec_from_file_location('e45_native_helpers', ROOT/'lab/explorations/2026-10-05-language-calibration/experiment.py')
e45 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e45)
SEEDS = (137, 163, 191)
NAMES = e45.TEST_NAMES
WIRING = 71


def study(prepare=False):
    return Study(StudyConfig('native-language/1', 'E46 个体内部模式与语言表达', HERE, WORK, 41,
        instance_limit=1000, wall_seconds=14400, storage_soft=5*2**30, storage_hard=8*2**30,
        usage_soft_delta=8, usage_hard_delta=12), prepare=prepare)


def guard(s, force=False):
    s.guard(force)
    if force or not hasattr(s, 'extra_seconds'):
        s.extra_seconds = sum(read_json(p).get('wall_seconds', 0) for p in (WORK/'timing').glob('*.json'))
    active = time.monotonic()-s.active_case.born_wall if s.active_case else 0
    if s.completed_wall + s.extra_seconds + active >= s.settings.wall_seconds:
        raise RuntimeError('aggregate simulation/learning/decoding limit')
    if torch.cuda.is_available() and torch.cuda.memory_allocated() > 3*2**30:
        raise RuntimeError('GPU memory limit')


def inp():
    assets=WORK/'frozen-input'
    if not (assets/f'input-{WIRING}.safetensors').exists():
        assets=OLD/'models'
    p = e45.protocol(WIRING).model_copy(update={'input_checkpoint_sha256':
        read_json(assets/f'input-{WIRING}.json')['checkpoint_sha256']})
    model = e45.load_input(p, 'input', 'cpu', assets/f'input-{WIRING}.safetensors')[1]
    return e45.Input(read_json(WORK/'route-selection.json')['route'], WIRING, model)


def start_case(s, key):
    guard(s)
    path = WORK/'cases'/key
    if (path/'result.json').exists():
        return path, None
    if path.exists():
        raise RuntimeError(f'incomplete case retained for diagnosis: {key}')
    path.mkdir(parents=True)
    started = time.monotonic()
    s.active_case = SimpleNamespace(born_wall=started)
    return path, started


def finish(s, path, started, result):
    elapsed = time.monotonic()-started
    new_json(path/'result.json', result | {'wall_seconds':elapsed,'runner_signature':s.runner_signature})
    s.active_case = None
    s.completed_count = (s.completed_count or 0)+1
    s.completed_wall += elapsed


def observe(value, until, s):
    start = value.engine.time_us
    before = value.engine.metrics()['transport']
    frames = []
    while True:
        nodes = value.engine.observation_nodes()
        frames.append({'time_us':str(value.engine.time_us), 'nodes':[
            {k:n[k] for k in ('id','channel','activation','inhibition','trace','support','stability') if k in n}
            for n in nodes]})
        if value.engine.time_us >= until or value.engine.life == 'dead':
            break
        value.reader.advance_to(min(until, value.engine.time_us+20000), guard=lambda:guard(s))
    after = value.engine.metrics()['transport']
    value.records.clear()
    return {'start_us':str(start),'end_us':str(value.engine.time_us),'planned_end_us':str(until),
        'trajectory':frames,'transport_delta':{k:after[k]-before[k] for k in before},'life':value.engine.life}


def source(s, input_adapter, seed, condition='normal', parent=None):
    key = f's{seed}-{condition}'
    path, started = start_case(s, key)
    if started is None:
        return path
    if parent:
        checkpoint = parent/'checkpoint-266'
        value = e45.previous.restore(checkpoint, WIRING)
        cursor = read_json(checkpoint/'summary.json')['cursor']
        offset, checkpoints = 266, (532,592)
    else:
        value = LanguageSession(e45.protocol(WIRING).model_dump(), config={'seed':seed,'plasticity':condition!='frozen'},
            seed=seed, readouts=e45.READOUTS)
        cursor, offset, checkpoints = 0, 0, ((266,326) if condition=='frozen' else (24,72,266,326))
    assignment = list(range(4))[::-1] if condition=='reversal' else list(range(4))
    lessons = [] if condition=='background' else e45.previous.schedule(NAMES, seed)
    for lesson in lessons:
        lesson.update(seconds=lesson['seconds']+offset, object=assignment[lesson['item']],
            text=NAMES[lesson['item']]+'是'+WORDS[assignment[lesson['item']]]+'。')
    new_json(path/'definition.json', {'schema':'E46-source/1','seed':seed,'condition':condition,'parent':str(parent),
        'assignment':assignment,'lessons':lessons,'input_wiring':WIRING,'route':input_adapter.route,
        'config':value.engine.capture_state().to_dict()['config'], 'names':NAMES})
    e45.previous.save_state(path/'initial', value, cursor)
    tape, index = RecordedBackground(WORK/'physical-telemetry.jsonl'), 0
    for checkpoint in checkpoints:
        with gzip.open(path/f'process-{checkpoint}.jsonl.gz','xt',encoding='utf-8') as stream:
            while value.engine.time_us < checkpoint*1000000 and value.engine.life!='dead':
                until = min(checkpoint*1000000, value.engine.time_us+500000)
                cursor = tape.queue_before(value.reader,cursor,until)
                acquisitions = []
                while index<len(lessons) and round(lessons[index]['seconds']*1e6)<until:
                    lesson=lessons[index]
                    measurement=input_adapter.world.sample(lesson['object'],lesson['repetition']%8)
                    frames=paired_visual(input_adapter.frames(lesson['text'],teaching=True),input_adapter.world.frame(measurement),10)
                    value.reader.schedule(frames,at=round(lesson['seconds']*1e6),source='E46-teaching',adapter_id='language-dose-study/1')
                    acquisitions.append({'measurement':measurement,'lesson':lesson,'input':input_summary(frames)})
                    index+=1
                stream.write(encoded({'process':observe(value,until,s),'acquisition':acquisitions}).decode()+'\n')
        e45.previous.save_state(path/f'checkpoint-{checkpoint}',value,cursor)
    finish(s,path,started,{'kind':'source','seed':seed,'condition':condition,'life':value.engine.life,'route':input_adapter.route})
    print(json.dumps({'source':key,'wall_seconds':round(time.monotonic()-started,1)}),flush=True)
    return path


def probe(s, input_adapter, parent, seconds, modality, item, variant, intensity, split, intervention='none', edges=()):
    key=f'{parent.name}-t{seconds}-{modality}{item}-v{variant}-i{intensity}-{split}-{intervention}'
    path,started=start_case(s,key)
    if started is None:
        return path
    checkpoint=parent/f'checkpoint-{seconds}'
    value=e45.previous.restore(checkpoint,WIRING)
    cursor=read_json(checkpoint/'summary.json')['cursor']
    definition=read_json(parent/'definition.json')
    if edges:
        value.engine.intervene(edges=edges,action='silence')
    frames=[];cue=None;target=''
    if item>=0 and modality=='vision':
        cue=NAMES[item]+('是' if variant else '')
        frames=input_adapter.frames(cue,intensity)
        target=WORDS[definition['assignment'][item]]+'。'
    elif item>=0:
        cue=input_adapter.world.sample(item,variant)
        frames=[{'stimulus':replace(input_adapter.world.frame(cue),intensity=intensity),'labels':{}}]
        target=NAMES[definition['assignment'].index(item)]+'。'
    if frames and value.engine.life!='dead':
        value.reader.schedule(frames,source='E46-probe',adapter_id='native-expression-study/1')
    until=value.engine.time_us+2000000
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl')
    if value.engine.life!='dead':
        tape.queue_before(value.reader,cursor,until)
    process=observe(value,until,s)
    write_gzip(path/'process.json.gz',process)
    finish(s,path,started,{'kind':'probe','source':parent.name,'seed':definition['seed'],'condition':definition['condition'],
        'seconds':seconds,'modality':modality,'item':item,'variant':variant,'intensity':intensity,'split':split,
        'cue':cue,'target':target,'life':value.engine.life,'intervention':intervention,'edges':edges})
    return path


def probes(s, input_adapter, parent, seconds, training=False):
    for modality in ('vision','words'):
        probe(s,input_adapter,parent,seconds,modality,-1,0,0.5,'test')
        for item in range(4):
            for variant in ((0,1) if modality=='vision' else (9,)):
                probe(s,input_adapter,parent,seconds,modality,item,variant,0.5,'test')
            if training:
                for variant,intensity in (((0,0.4),(0,0.6)) if modality=='vision' else ((8,0.4),(10,0.6))):
                    probe(s,input_adapter,parent,seconds,modality,item,variant,intensity,'train')
        if training:
            probe(s,input_adapter,parent,seconds,modality,-1,0,0.5,'train')


def projection_config(input_adapter):
    language=set()
    for text in (*NAMES, *[n+'是'+word+'。' for n in NAMES for word in WORDS], *[n+'是' for n in NAMES]):
        language.update(c for row in input_adapter.frames(text) for c,_ in row['stimulus'].channels)
    visual=set(input_adapter.visual_channels())
    background={int(c) for row in RecordedBackground(WORK/'physical-telemetry.jsonl').rows
                if row['stimulus'] for c,_ in row['stimulus']['channels']}
    if language & visual or language & background or visual & background:
        raise RuntimeError('sensory domains unexpectedly collide')
    known=language|visual|background
    return {modality:NativeProjection(tuple(sorted(known-excluded)),tuple(sorted(excluded))).to_dict()
        for modality,excluded in (('vision',language),('words',visual))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=('prepare','sources','continuations'))
    args=parser.parse_args()
    torch.set_num_threads(2)
    s=study(args.operation=='prepare')
    try:
        if args.operation=='prepare':
            shutil.copy2(OLD/'physical-telemetry.jsonl',WORK/'physical-telemetry.jsonl')
            new_json(WORK/'usage.json',{'used_percent':41})
            for name in ('lab/tools/recorded_background.py','lab/tools/language_teaching_world.py',
                         'lab/tools/sensory_calibration.py','src/threemind_transformer/native_readout.py',
                         'lab/explorations/2026-10-05-language-calibration/experiment.py',
                         'lab/explorations/2026-10-04-language-development/experiment.py'):
                dest=WORK/'frozen-tools'/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/name,dest)
            print(json.dumps({'project':s.project}),flush=True)
            return
        input_adapter=inp()
        if not (WORK/'projection.json').exists():
            new_json(WORK/'projection.json',projection_config(input_adapter))
        for seed in SEEDS:
            if args.operation=='sources':
                parent=source(s,input_adapter,seed)
                for seconds in (24,72,266,326):
                    probes(s,input_adapter,parent,seconds,training=seconds!=326)
                frozen=source(s,input_adapter,seed,'frozen')
                probes(s,input_adapter,frozen,266)
            else:
                for condition in ('continued','reversal','background'):
                    parent=source(s,input_adapter,seed,condition,WORK/'cases'/f's{seed}-normal')
                    for seconds in (532,592):
                        probes(s,input_adapter,parent,seconds)
    finally:
        s.db.close()


if __name__=='__main__':
    main()
