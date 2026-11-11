"""Registered bounded clock/retelling pilot. No Core or input encoder changes."""
import argparse,gzip,importlib.util,json,random,sys,time,shutil
from pathlib import Path
from dataclasses import replace,asdict
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import torch
from lab.tools.service_study import Study,StudyConfig,new_json,read_json,write_gzip
from lab.tools.recorded_background import RecordedBackground
from lab.tools.teaching_clock import TeachingClock
from lab.tools.sensory_calibration import paired_visual
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.graph_expression import GraphExpressionConfig,fit
from threemind_transformer.local_activity import local_process,FIELDS
from threemind_runtime.activity_stream import RawActivityStream

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/clock-recollection-20261005'
TAPE=ROOT/'.work/temporal-state-20261005/physical-telemetry.jsonl'
spec=importlib.util.spec_from_file_location('clock_e48_helpers',ROOT/'lab/explorations/2026-10-05-temporal-state-expression/experiment.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
PAIRS=[(a,b) for a in range(4) for b in range(4) if a!=b]
HELD={(a,(a+1)%4) for a in range(4)}


def study(prepare=False):
    return Study(StudyConfig('clock-recollection/1','E51 时钟教学与现在、刚刚的复述',HERE,WORK,51,
        instance_limit=256,wall_seconds=7200,storage_soft=2*2**30,storage_hard=6*2**30,
        usage_soft_delta=4,usage_hard_delta=6),prepare=prepare)


def guard(s,force=False):
    s.guard(force)
    if force or not hasattr(s,'extra'):s.extra=sum(read_json(p)['wall_seconds'] for p in (WORK/'timing').glob('*.json'))
    active=time.monotonic()-s.active_case.born_wall if s.active_case else 0
    if s.completed_wall+s.extra+active>7200:raise RuntimeError('aggregate simulation and training budget')
    if torch.cuda.is_available() and torch.cuda.memory_allocated()>3*2**30:raise RuntimeError('GPU budget')


def start(s,key):
    guard(s,True);p=WORK/'cases'/key
    if (p/'result.json').exists():return p,None
    if p.exists():raise RuntimeError('incomplete evidence retained: '+key)
    p.mkdir(parents=True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    return p,tick


def finish(s,p,tick,result):
    wall=time.monotonic()-tick;new_json(p/'result.json',result|{'wall_seconds':wall,'runner_signature':s.runner_signature})
    s.active_case=None;s.completed_count=(s.completed_count or 0)+1;s.completed_wall+=wall


def course(seed):
    pairs=list(PAIRS);random.Random(seed).shuffle(pairs);rows=[];when=0
    for pair in pairs:
        for repeat in range(10):rows.append({'start':when,'past':pair[0],'current':pair[1],'repeat':repeat});when+=4
    for interval in (6,8):
        random.Random(seed+interval).shuffle(pairs)
        for pair in pairs:rows.append({'start':when,'past':pair[0],'current':pair[1],'repeat':interval});when+=interval
    return rows,when+4


def clock_word(clock,seconds):
    phase=int(clock.sample(seconds)['pointer_rad']/(.5*3.141592653589793)+1e-8)%4
    return '钟在第'+('一','二','三','四')[phase]+'格。'


def source(s,a,seed,learning):
    p,tick=start(s,f's{seed}-'+('learned' if learning else 'no-learning'))
    if tick is None:return p
    v=LanguageSession(h.old.e45.protocol(71).model_dump(),config={'seed':seed,'plasticity':learning},seed=seed,readouts=h.old.e45.READOUTS)
    lessons,end=course(seed);clock=TeachingClock();events=[];words=h.WORDS
    for lesson in lessons:
        t=lesson['start'];past,current=lesson['past'],lesson['current'];view=lesson['repeat']%8
        for offset,text,item in [(0,'现在看见了'+words[past]+'。',past),(1,'现在看见了'+words[current]+'。',current),
                (1.5,'刚刚看见什么？',None),(1.8,'刚刚看见了'+words[past]+'。',None),
                (2.4,'现在看见什么？',None),(2.7,'现在看见了'+words[current]+'。',None),
                (3.2,clock_word(clock,t+3.2),None)]:
            frames=h.timed_frames(a,text,20000,1.,teaching=True)
            measurement=a.world.sample(item,view) if item is not None else None
            if measurement:frames=paired_visual(frames,a.world.frame(measurement),10)
            if max(int(r['stimulus'].time_us) for r in frames)>=300000:raise ValueError('teacher sentences overlap; preserve evidence and revise registration')
            events.append({'at':round((t+offset)*1e6),'frames':frames,'text':text,'measurement':measurement})
    h.old.e45.previous.save_state(p/'initial',v,0)
    new_json(p/'definition.json',{'seed':seed,'learning':learning,'lessons':lessons,'end_seconds':end,
        'clock':asdict(clock),'config':v.engine.capture_state().to_dict()['config']})
    tape=RecordedBackground(TAPE);cursor=0;index=0
    with gzip.open(p/'teaching.jsonl.gz','xt',encoding='utf-8') as out:
        while v.engine.time_us<end*1000000 and v.engine.life!='dead':
            now=v.engine.time_us;until=now+250000;cursor=tape.queue_before(v.reader,cursor,until)
            observation=clock.sample(now/1e6)
            v.reader.schedule([{'stimulus':clock.frame(observation),'labels':{}}],at=now,source='E51-clock',adapter_id='teaching-clock/1')
            supplied=[]
            while index<len(events) and events[index]['at']<until:
                event=events[index];v.reader.schedule(event['frames'],at=event['at'],source='E51-teacher',adapter_id='language-dose-study/1')
                supplied.append({k:val for k,val in event.items() if k!='frames'}|{'delivered':[asdict(r['stimulus']) for r in event['frames']]});index+=1
            v.reader.advance_to(until,guard=lambda:guard(s));v.records.clear()
            out.write(json.dumps({'time_us':str(now),'clock':observation,'teaching':supplied,'life':v.engine.life})+'\n')
    if v.engine.life=='dead':raise RuntimeError('course ended with death; do not silently revive')
    h.old.e45.previous.save_state(p/'checkpoint',v,cursor)
    finish(s,p,tick,{'kind':'source','seed':seed,'learning':learning,'lessons':len(lessons),'end_seconds':end,'life':v.engine.life})
    print({'source':p.name,'episodes':len(lessons),'sim_seconds':end},flush=True);return p


def probe(s,a,parent,past,current,question,view,mode,split,phase=0):
    key=f'{parent.name}-a{past}-b{current}-{question}-v{view}-{mode}-{split}-p{phase}-frames'
    p,tick=start(s,key)
    if tick is None:return
    v=h.old.e45.previous.restore(parent/'checkpoint',71);cursor=read_json(parent/'checkpoint/summary.json')['cursor']
    start_us=v.engine.time_us;query_us=start_us+2400000
    clock=TeachingClock(origin_s=query_us/1e6,phase_rad=(phase*.5*3.141592653589793)+(1.5707963267948966 if mode=='shift' else 0)+(.12 if question=='clock' and split=='test' else 0),period_s=2. if mode=='fast' else 4.)
    delivered=[]
    if question!='clock':
        for item,offset in ((past,0),(current,1000000)):
            for sample in range(5):
                measurement=a.world.sample(item,view);frame=a.world.frame(measurement,amount=2)
                when=start_us+offset+sample*40000
                v.reader.schedule([{'stimulus':frame,'labels':{}}],at=when,source='E51-new-experience',adapter_id='visual-teaching-world/1')
                delivered.append({'at':str(when),'measurement':measurement,'stimulus':asdict(frame)})
    text={'past':'刚刚看见什么？','now':'现在看见什么？','clock':'钟指哪里？'}[question]
    frames=h.timed_frames(a,text,20000,.5)
    v.reader.schedule(frames,at=query_us,source='E51-question',adapter_id='language-dose-study/1')
    target=('刚刚看见了'+h.WORDS[past]+'。' if question=='past' else '现在看见了'+h.WORDS[current]+'。') if question!='clock' else clock_word(clock,query_us/1e6)
    until=query_us+2000000;tape=RecordedBackground(TAPE);cursor=tape.queue_before(v.reader,cursor,until)
    readings=[]
    for when in range(start_us,until,250000):
        measured=clock.sample(query_us/1e6 if mode=='fixed' else when/1e6);stimulus=clock.frame(measured)
        v.reader.schedule([{'stimulus':stimulus,'labels':{}}],at=when,source='E51-clock',adapter_id='teaching-clock/1')
        readings.append({'at':str(when),'measurement':measured,'stimulus':asdict(stimulus)})
    v.reader.advance_to(query_us,guard=lambda:guard(s));v.records.clear();observations=[]
    stream=RawActivityStream();stream.subscribe('local-expression',observations.append)
    while True:
        stream.sample(v.engine)
        if v.engine.time_us>=until or v.engine.life=='dead':break
        v.reader.advance_to(min(until,v.engine.time_us+20000),guard=lambda:guard(s));v.records.clear()
    raw={'start_us':str(query_us),'end_us':str(v.engine.time_us),'trajectory':observations,'life':v.engine.life}
    write_gzip(p/'process.json.gz',raw)
    definition=read_json(parent/'definition.json')
    finish(s,p,tick,{'kind':'probe','seed':definition['seed'],'learning':definition['learning'],'past':past,'current':current,
        'question':question,'view':view,'mode':mode,'split':split,'held':(past,current) in HELD,'phase':phase,'target':target,
        'question_text':text,'question_delivered':[asdict(r['stimulus']) for r in frames],'experiences':delivered,
        'clock':readings,'life':v.engine.life,'path':str(p/'process.json.gz')})


def collect(s,a,seed,learning):
    parent=source(s,a,seed,learning)
    for past,current in PAIRS:
        for question in ('past','now'):
            if learning and (past,current) not in HELD:
                for view in (8,10):probe(s,a,parent,past,current,question,view,'normal','train')
            probe(s,a,parent,past,current,question,9,'normal','test')
            if learning and (past,current) in HELD:
                for mode in ('fixed','shift','fast'):probe(s,a,parent,past,current,question,9,mode,'test')
    if learning:
        for phase in range(4):
            probe(s,a,parent,-1,-1,'clock',8,'normal','train',phase)
            probe(s,a,parent,-1,-1,'clock',9,'normal','test',phase)


def read_process(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)


def express(s,seed):
    folder=WORK/'models';folder.mkdir(exist_ok=True);key=f's{seed}-local'
    if (folder/f'{key}.json').exists():return read_json(folder/f'{key}.json')['fit_correct']>=33
    guard(s,True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    allrows=[read_json(p) for p in (WORK/'cases').glob(f's{seed}-*/result.json')]
    train=[r for r in allrows if r['kind']=='probe' and r['split']=='train']
    test=[r for r in allrows if r['kind']=='probe' and r['split']=='test']
    samples=[{'process':local_process(read_process(r['path'])),'text':r['target']} for r in train]
    if len(samples)!=36:raise ValueError('36 registered teacher observations required')
    model,meta=fit(samples,folder/f'{key}.safetensors',config=GraphExpressionConfig(node_fields=FIELDS,use_edges=False),
        steps=2500,device='cuda' if torch.cuda.is_available() else 'cpu',check=lambda:guard(s))
    fitted=[]
    for i in range(0,len(samples),4):fitted.extend(model.decode([r['process'] for r in samples[i:i+4]]))
    count=sum(o['text']==r['text'] for o,r in zip(fitted,samples));output=[]
    for i in range(0,len(test),4):
        guard(s);part=test[i:i+4];decoded=model.decode([local_process(read_process(r['path'])) for r in part])
        output.extend({k:r[k] for k in ('seed','learning','past','current','question','mode','held','phase','target','path')}|
            {'output':o['text'],'tokens':o['tokens']} for r,o in zip(part,decoded))
    result={'seed':seed,'fit_correct':count,'fit_count':len(samples),'metadata':meta,'rows':output,
        'training_cases':[r['path'] for r in train],'teacher_training_outputs':[o['text'] for o in fitted]}
    new_json(folder/f'{key}.json',result);new_json(WORK/'timing'/f'{key}.json',{'wall_seconds':time.monotonic()-tick})
    s.active_case=None;print({'fit':f'{count}/36','tests':len(test),'seed':seed},flush=True);return count>=33


def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=('prepare','run'));args=p.parse_args();torch.set_num_threads(2)
    s=study(args.operation=='prepare')
    try:
        if args.operation=='prepare':
            new_json(WORK/'usage.json',{'used_percent':51})
            folder=WORK/'external-tools';folder.mkdir(exist_ok=True)
            for relative in ('lab/tools/teaching_clock.py','lab/tools/language_teaching_world.py','lab/tools/sensory_calibration.py','lab/tools/recorded_background.py'):
                shutil.copy2(ROOT/relative,folder/Path(relative).name)
            new_json(WORK/'dependencies.json',{'source_input_and_background':'E48 frozen input/E50 physical replay unchanged','clock_schema':'threemind.teaching-clock/1','background':str(TAPE)})
            print({'project':s.project},flush=True);return
        a=h.adapter()
        for seed in (223,279):
            s.allow_extension();collect(s,a,seed,True);collect(s,a,seed,False)
            if not express(s,seed):
                new_json(WORK/'stopped.json',{'reason':'registered teaching-fit gate','seed':seed});break
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':main()
