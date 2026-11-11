"""E45 independently registered calibration, ordinary Runtime and explicit controls."""

import argparse
import gzip
import importlib.util
import json
import shutil
import sys
import time
import unicodedata
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.language_teaching_world import WORDS, TeachingWorld
from lab.tools.recorded_background import RecordedBackground
from lab.tools.sensory_calibration import SensoryResponseLibrary, matched_frames, paired_visual, process_vector
from lab.tools.service_study import Study, StudyConfig, encoded, new_json, read_json, write_gzip
from threemind_kernels.novelty import NoveltyConfig
from threemind_transformer.development import StreamInput, compile_stream, input_summary
from threemind_transformer.language_protocol import LanguageProtocol, ScratchTraining
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.scratch_language import load as load_input
from threemind_transformer.scratch_language import train as train_input

HERE = Path(__file__).resolve().parent
WORK = ROOT / '.work/language-calibration-20261005'
OLD = ROOT / '.work/language-development-20261004'
spec = importlib.util.spec_from_file_location('e44_frozen_helpers', ROOT / 'lab/explorations/2026-10-04-language-development/experiment.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
READOUTS = previous.READOUTS
ROUTES = ('stream-sparse', 'text-simultaneous', 'text-repeat', 'stream-dense', 'stream-collapse', 'stream-reverse')
CAL_SEEDS, TEST_SEEDS = (17, 29), (71, 89, 107)
CAL_NAMES, TEST_NAMES = ('壬', '癸', '子', '丑'), ('甲', '乙', '丁', '戊')
PARAMETERS = {
    'default': {},
    'faster-decay': {'activation_tau': NoveltyConfig().activation_tau * 0.5},
    'stronger-inhibition': {'inhibition_gain': NoveltyConfig().inhibition_gain * 1.5},
    'facilitation-1s': {'stp_facilitation_tau_s': 1.0},
    'faster-recovery': {'stp_recovery_tau_s': 0.4},
    'lower-emission': {'propagation_rate': NoveltyConfig().propagation_rate * 0.5},
    'higher-learning': {'learning_rate': NoveltyConfig().learning_rate * 2},
}


def study(prepare=False):
    return Study(StudyConfig('language-calibration/1', 'E45 语言对应校准与双向感官联想', HERE, WORK, 38,
        instance_limit=2400, wall_seconds=14400, storage_soft=5*2**30, storage_hard=8*2**30,
        usage_soft_delta=8, usage_hard_delta=12), prepare=prepare)


def guard(s, force=False):
    s.guard(force)
    if force or not hasattr(s, 'model_seconds'):
        s.model_seconds = sum(read_json(p).get('wall_seconds', 0) for p in (WORK/'models').glob('*.json')
                              if not p.name.endswith('.training.json') and not read_json(p).get('reused'))
    active = time.monotonic()-s.active_case.born_wall if s.active_case else 0
    if s.completed_wall + s.model_seconds + active > 14400:
        raise RuntimeError('aggregate compute budget')
    if torch.cuda.is_available() and torch.cuda.memory_allocated() > 3*2**30:
        raise RuntimeError('GPU budget')


def protocol(seed):
    return LanguageProtocol(seed=seed, input_model='scratch', output_model='scratch', mode='strict',
                            scratch_width=64, scratch_layers=2, scratch_context=256, maximum_tokens=32)


def model(s, seed):
    path = WORK/'models'/f'input-{seed}.safetensors'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        guard(s, True)
        old = OLD/'models'/path.name
        if old.exists():
            shutil.copy2(old, path)
            new_json(path.with_suffix('.json'), read_json(old.with_suffix('.json')) | {'reused':str(old)})
        else:
            corpus = [*WORDS, *CAL_NAMES, *TEST_NAMES, '是', '我', '你', '谁', '。', '？']
            corpus += [prefix + word + end for word in WORDS for prefix in ('', '我看见', '这是') for end in ('。','？')]
            train = ScratchTraining(protocol=protocol(seed), texts=corpus, steps=1200, learning_rate=0.001)
            started = time.monotonic()
            s.active_case = SimpleNamespace(born_wall=started)
            result = train_input(train, path, 'cuda' if torch.cuda.is_available() else 'cpu', lambda: guard(s))
            new_json(path.with_suffix('.json'), result | {'wall_seconds':time.monotonic()-started, 'corpus':corpus,
                                                        'formal_assignments_exposed':False})
            s.active_case = None
            print(json.dumps({'input_trained':seed}), flush=True)
    p = protocol(seed).model_copy(update={'input_checkpoint_sha256':read_json(path.with_suffix('.json'))['checkpoint_sha256']})
    return load_input(p, 'input', 'cpu', path)[1]


class Input:
    def __init__(self, route, seed, encoder):
        self.route, self.seed, self.encoder = route, seed, encoder
        self.sensor = LanguageSession(protocol(seed).model_dump(), seed=seed, readouts=READOUTS).sensor
        self.world, self.cache = TeachingWorld(seed), {}

    def frames(self, text, intensity=1.0, teaching=False):
        key = (text, teaching)
        if key not in self.cache:
            count = len(unicodedata.normalize('NFKC', text))
            if self.route.startswith('text'):
                raw = list(self.sensor.frames(text))
                if len(raw) != 1:
                    raise ValueError('registered short text must fit one original frame')
            else:
                raw = compile_stream(text, self.encoder, StreamInput(seed=self.seed, top_k=0 if self.route=='stream-dense' else 4))
            self.cache[key] = matched_frames(raw, count,
                repetitions=count if self.route.startswith('text') else None,
                collapse=self.route in ('text-simultaneous','stream-collapse'), reverse=self.route=='stream-reverse' and teaching)
        return [{'stimulus':replace(r['stimulus'], intensity=intensity), 'labels':{}} for r in self.cache[key]]

    def visual_channels(self):
        return tuple(sorted({c for item in range(4) for c,_ in self.world.frame(self.world.sample(item)).channels}))

    def word_channels(self, names):
        return tuple(sorted({c for text in names for row in self.frames(text) for c,_ in row['stimulus'].channels}))

    def templates(self, names):
        channels = self.visual_channels()
        visual = np.array([[dict(self.world.frame(self.world.sample(item, view)).channels).get(c,0)
                            for c in channels] for item in range(4) for view in range(8)]).reshape(4,8,-1).mean(axis=1)
        word_channels = self.word_channels(names)
        words = []
        for name in names:
            row = dict(self.frames(name)[0]['stimulus'].channels)
            words.append([row.get(c, 0) for c in word_channels])
        return {'vision':SensoryResponseLibrary(channels, visual), 'words':SensoryResponseLibrary(word_channels, words)}


def observe(value, until, s):
    start, frames = value.engine.time_us, []
    before = value.engine.metrics()['transport']
    while True:
        frames.append({'time_us':str(value.engine.time_us), 'nodes':[
            {'id':str(n['id']), 'channel':int(n['channel']), 'activation':float(n['activation'])}
            for n in value.engine.observation_nodes() if n['activation'] > 0]})
        if value.engine.time_us >= until or value.engine.life == 'dead': break
        value.reader.advance_to(min(until, value.engine.time_us+20000), guard=lambda:guard(s))
    after = value.engine.metrics()['transport']
    value.records.clear()
    return {'start_us':str(start),'end_us':str(value.engine.time_us),'planned_end_us':str(until),'trajectory':frames,
            'transport_delta':{k:after[k]-before[k] for k in before},'life':value.engine.life}


def start_case(s, key):
    path = WORK/'cases'/key
    if (path/'result.json').exists(): return path, None
    if path.exists(): raise RuntimeError('incomplete case retained: '+key)
    guard(s, True)
    path.mkdir(parents=True)
    started=time.monotonic()
    s.active_case=SimpleNamespace(born_wall=started)
    return path, started


def finish(s, path, started, data):
    elapsed=time.monotonic()-started
    new_json(path/'result.json',data | {'wall_seconds':elapsed,'runner_signature':s.runner_signature})
    s.active_case=None
    s.completed_count=(s.completed_count or 0)+1
    s.completed_wall+=elapsed


def source(s, inp, condition, names, stage, parameter='default'):
    key=f'{stage}-{inp.route}-{parameter}-s{inp.seed}-{condition}'
    path, started=start_case(s,key)
    if started is None: return path
    config={'seed':inp.seed}|PARAMETERS[parameter]
    if condition=='frozen': config['plasticity']=False
    value=LanguageSession(protocol(inp.seed).model_dump(), config=config, seed=inp.seed, readouts=READOUTS)
    assignment=list(range(4))[::-1] if condition=='reversed' else list(range(4))
    lessons=previous.schedule(names,inp.seed)
    for row in lessons:
        row.update(text=names[row['item']]+'是'+WORDS[assignment[row['item']]]+'。',object=assignment[row['item']])
    libraries=inp.templates(names)
    new_json(path/'definition.json',{'schema':'E45-source/1','route':inp.route,'seed':inp.seed,'condition':condition,
        'names':names,'stage':stage,'parameter':parameter,'assignment':assignment,'lessons':lessons,
        'config':value.engine.capture_state().to_dict()['config'],'libraries':{k:v.to_dict() for k,v in libraries.items()},
        'dose_protocol':'threemind.language-dose-study/1','readouts':READOUTS})
    previous.save_state(path/'initial',value,0)
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl')
    cursor=lesson_index=0
    for checkpoint in ((266,326,566) if stage=='formal' else (266,326)):
        with gzip.open(path/f'process-{checkpoint}.jsonl.gz','xt',encoding='utf-8') as log:
            while value.engine.time_us<checkpoint*1000000 and value.engine.life!='dead':
                until=min(checkpoint*1000000,value.engine.time_us+500000)
                cursor=tape.queue_before(value.reader,cursor,until)
                acquisitions=[]
                while lesson_index<len(lessons) and round(lessons[lesson_index]['seconds']*1e6)<until:
                    lesson=lessons[lesson_index]
                    measurement=inp.world.sample(lesson['object'],lesson['repetition']%8)
                    frames=paired_visual(inp.frames(lesson['text'],teaching=True),inp.world.frame(measurement),10)
                    value.reader.schedule(frames,at=round(lesson['seconds']*1e6),source='E45-physical-teaching',adapter_id='language-dose-study/1')
                    acquisitions.append({'measurement':measurement,'text':lesson['text'],'input':input_summary(frames)})
                    lesson_index+=1
                process=observe(value,until,s)
                log.write(encoded({'process':process,'acquisition':acquisitions}).decode()+'\n')
        previous.save_state(path/f'checkpoint-{checkpoint}',value,cursor)
    finish(s,path,started,{'kind':'source','key':key,'life':value.engine.life,'route':inp.route,'parameter':parameter,
                            'seed':inp.seed,'condition':condition,'stage':stage,'metrics':value.engine.metrics()})
    print(json.dumps({'source_complete':key,'wall_s':round(time.monotonic()-started,1),'life':value.engine.life}),flush=True)
    return path


def probe(s, inp, parent, seconds, cue_index, intervention='none', edges=()):
    key=f'{parent.name}-t{seconds}-q{cue_index}-{intervention}'
    path,started=start_case(s,key)
    if started is None: return read_json(path/'result.json')
    checkpoint=parent/f'checkpoint-{seconds}'
    value=previous.restore(checkpoint,inp.seed)
    definition=read_json(parent/'definition.json')
    cursor=read_json(checkpoint/'summary.json')['cursor']
    if intervention=='transmission-off': value.engine.reconfigure(replace(value.engine.config,propagation_rate=0))
    elif edges: value.engine.intervene(edges=edges,action='silence')
    cue=None; target=None
    if 0<=cue_index<8:
        cue=definition['names'][cue_index//2]+('是' if cue_index%2 else '')
        frames=inp.frames(cue,0.5)
        target=definition['assignment'][cue_index//2]
        if value.engine.life!='dead':
            value.reader.schedule(frames,source='E45-word-cue',adapter_id='language-dose-study/1')
    elif cue_index>=8:
        item=cue_index-8
        measurement=inp.world.sample(item,9)
        frames=[{'stimulus':replace(inp.world.frame(measurement),intensity=0.5),'labels':{}}]
        cue={'physical_view':measurement,'item':item}
        target=definition['assignment'].index(item)
        if value.engine.life!='dead':
            value.reader.schedule(frames,source='E45-visual-cue',adapter_id='visual-teaching-world/1')
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl')
    until=value.engine.time_us+2000000
    if value.engine.life!='dead':cursor=tape.queue_before(value.reader,cursor,until)
    process=observe(value,until,s)
    write_gzip(path/'process.json.gz',process)
    vectors={}
    if int(process['end_us'])==until:
        for name,library in definition['libraries'].items():
            channels=library['channels']; start=int(process['start_us'])
            vectors[name]={'whole':process_vector(process,channels).tolist(),'windows':[
                process_vector(process,channels,start_us=start+left,end_us=start+right).tolist()
                for left,right in ((0,200000),(200000,500000),(500000,1000000),(1000000,2000000))]}
    result={'kind':'probe','source':parent.name,'route':inp.route,'seed':inp.seed,'condition':definition['condition'],
        'stage':definition['stage'],'parameter':definition['parameter'],'seconds':seconds,'cue_index':cue_index,
        'cue':cue,'target':target,'intervention':intervention,'vectors':vectors,'transport':process['transport_delta'],
        'life':value.engine.life,'edges_silenced':edges,'target_modality':definition.get('target_modality','vision')}
    finish(s,path,started,result)
    return result


def run_conditions(s, route, seed, stage, parameter='default', conditions=('normal','reversed')):
    inp=Input(route,seed,model(s,seed))
    for condition in conditions:
        parent=source(s,inp,condition,CAL_NAMES if stage=='cal' else TEST_NAMES,stage,parameter)
        for seconds in ((266,326,566) if stage=='formal' else (266,326)):
            for cue in (-1,*range(12)):
                probe(s,inp,parent,seconds,cue)


def analyse(stage='cal'):
    from collections import defaultdict
    cases=[read_json(p) for p in (WORK/'cases').glob(f'{stage}-*/result.json')]
    probes=[r for r in cases if r['kind']=='probe' and r['intervention']=='none']
    baselines={(r['source'],r['seconds']):r for r in probes if r['cue_index']==-1}
    rows=[]; pairs=defaultdict(dict); summaries=defaultdict(list)
    for r in probes:
        if r['cue_index']<0: continue
        direction=r.get('target_modality','vision') if r['cue_index']<8 else 'words'
        library=SensoryResponseLibrary(**read_json(WORK/'cases'/r['source']/'definition.json')['libraries'][direction])
        baseline=baselines[(r['source'],r['seconds'])]
        valid=bool(r['vectors'] and baseline['vectors'])
        delta=(np.array(r['vectors'][direction]['whole'])-np.array(baseline['vectors'][direction]['whole'])
               if valid else np.zeros(len(library.channels)))
        reading=library.read(delta); scores=reading['scores']; target=r['target']
        windows=([library.read(np.array(v)-np.array(b)) for v,b in zip(r['vectors'][direction]['windows'],baseline['vectors'][direction]['windows'],strict=True)]
                 if valid else [library.read(np.zeros(len(library.channels))) for _ in range(4)])
        row={k:r[k] for k in ('source','seed','route','parameter','condition','seconds','cue_index','target')}
        row.update(direction=direction,reading=reading,correct=reading['prediction']==target,valid_observation=valid,
                   margin=scores[target]-max(v for i,v in enumerate(scores) if i!=target),windows=windows)
        rows.append(row)
        if r['condition'] in ('normal','reversed'):
            # The same physical object must retrieve DIFFERENT names after
            # reversed teaching; pairing by target would reward a fixed bias.
            paired_cue=r['cue_index']
            pairs[(r['route'],r['parameter'],r['seed'],r['seconds'],paired_cue)][r['condition']]=row
    paired=[]
    for key,conditions in pairs.items():
        if len(conditions)!=2: continue
        a,b=conditions['normal'],conditions['reversed']
        p={'route':key[0],'parameter':key[1],'seed':key[2],'seconds':key[3],'cue_index':key[4],
           'direction':a['direction'],'correct':a['correct'] and b['correct'],'margin':(a['margin']+b['margin'])/2,
           'short_correct':[a['windows'][i]['prediction']==a['target'] and b['windows'][i]['prediction']==b['target'] for i in range(4)]}
        paired.append(p); summaries[(key[0],key[1],a['direction'])].append(p)
    return {'rows':rows,'pairs':paired,'summary':[{'route':k[0],'parameter':k[1],'direction':k[2],
        'correct':sum(r['correct'] for r in v),'count':len(v),'margin':float(np.mean([r['margin'] for r in v])),
        'short_correct':[sum(r['short_correct'][i] for r in v) for i in range(4)]} for k,v in summaries.items()]}


def select_inputs():
    if (WORK/'input-selection.json').exists(): return read_json(WORK/'input-selection.json')
    result=analyse(); options=[r for r in result['summary'] if r['direction']=='vision']
    if len(options)!=6 or any(r['count']!=32 for r in options): raise RuntimeError('incomplete calibration')
    options.sort(key=lambda r:(-r['correct'],-r['margin'],ROUTES.index(r['route'])))
    selected={'route':options[0]['route'],'rank':options,'requires_parameters':options[0]['correct']<24,
              'criterion':'joint normal/reversed whole-window correctness then margin; input dose matched',
              'formal_seen':False}
    new_json(WORK/'input-selection.json',selected); new_json(HERE/'input-selection.json',selected)
    return selected


def select_parameters():
    if (WORK/'parameter-selection.json').exists(): return read_json(WORK/'parameter-selection.json')
    inputs=read_json(WORK/'input-selection.json'); result=analyse()
    rows=[r for r in result['summary'] if r['direction']=='vision' and r['route']==inputs['route']]
    rows.sort(key=lambda r:(-r['correct'],-r['margin'],list(PARAMETERS).index(r['parameter'])))
    baseline=next(r for r in rows if r['parameter']=='default')
    best=rows[0] if rows[0]['correct']>baseline['correct'] else baseline
    selection={'route':inputs['route'],'parameter':best['parameter'],'changes':PARAMETERS[best['parameter']],
               'rank':rows,'formal_seen':False,'default_changed':False}
    new_json(WORK/'parameter-selection.json',selection);new_json(HERE/'parameter-selection.json',selection)
    return selection


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=['prepare','sensory','select-input','parameters','select-parameters','formal','summary'])
    args=parser.parse_args();torch.set_num_threads(2)
    if args.operation=='summary':
        result=analyse('formal' if list((WORK/'cases').glob('formal-*')) else 'cal')
        print(json.dumps(result['summary'],ensure_ascii=False));return
    if args.operation=='select-input': print(json.dumps(select_inputs()));return
    if args.operation=='select-parameters':print(json.dumps(select_parameters()));return
    s=study(args.operation=='prepare')
    try:
        if args.operation=='prepare':
            shutil.copy2(OLD/'physical-telemetry.jsonl',WORK/'physical-telemetry.jsonl')
            new_json(WORK/'usage.json',{'used_percent':38})
            for name in ('lab/tools/sensory_calibration.py','lab/tools/language_teaching_world.py',
                         'lab/tools/recorded_background.py','lab/explorations/2026-10-04-language-development/experiment.py'):
                dest=WORK/'frozen-tools'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
            print(json.dumps({'project':s.project}));return
        if args.operation=='sensory':
            for seed in CAL_SEEDS:
                for route in ROUTES:run_conditions(s,route,seed,'cal')
        elif args.operation=='parameters':
            selected=read_json(WORK/'input-selection.json')
            if selected['requires_parameters']:
                for parameter in PARAMETERS:
                    if parameter=='default':continue
                    for seed in CAL_SEEDS:run_conditions(s,selected['route'],seed,'cal',parameter)
        elif args.operation=='formal':
            selected=read_json(WORK/'parameter-selection.json')
            for seed in TEST_SEEDS:
                for parameter in dict.fromkeys(('default',selected['parameter'])):
                    run_conditions(s,selected['route'],seed,'formal',parameter,('normal','reversed','frozen'))
    finally:s.db.close()


if __name__=='__main__':main()
