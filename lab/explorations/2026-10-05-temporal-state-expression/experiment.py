"""E48: isolated time-of-arrival experiments; no Core changes."""
import argparse,gzip,importlib.util,json,shutil,sys,time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import torch
from lab.tools.service_study import Study,StudyConfig,read_json,new_json,write_gzip,encoded
from lab.tools.recorded_background import RecordedBackground
from lab.tools.sensory_calibration import paired_visual
from lab.tools.language_teaching_world import WORDS
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.development import input_summary

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/temporal-state-20261005'
OLD=ROOT/'.work/expression-alignment-20261005'
spec=importlib.util.spec_from_file_location('e46_temporal_helpers',ROOT/'lab/explorations/2026-10-05-native-language/experiment.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
SEEDS=(223,251,279);INTERVALS=(0,1000,5000,20000,100000)

def study(prepare=False):
    return Study(StudyConfig('temporal-state-expression/1','E48 原始状态与时间过程',HERE,WORK,45,
        instance_limit=1600,wall_seconds=14400,storage_soft=4*2**30,storage_hard=12*2**30,
        usage_soft_delta=6,usage_hard_delta=10),prepare=prepare)

def guard(s,force=False):
    s.guard(force)
    extra=sum(read_json(p).get('wall_seconds',0) for p in (WORK/'timing').glob('*.json')) if force or not hasattr(s,'extra') else s.extra
    s.extra=extra
    active=time.monotonic()-s.active_case.born_wall if s.active_case else 0
    if s.completed_wall+extra+active>s.settings.wall_seconds:raise RuntimeError('aggregate compute budget')
    if torch.cuda.is_available() and torch.cuda.memory_allocated()>3*2**30:raise RuntimeError('GPU budget')

def adapter():
    # Load original frozen input and route; only scheduled times change later.
    old.WORK=ROOT/'.work/native-language-20261005'
    return old.inp()

def timed_frames(adapter,text,interval,intensity=1.,teaching=False):
    return [{'stimulus':replace(r['stimulus'],time_us=i*interval),'labels':{}}
            for i,r in enumerate(adapter.frames(text,intensity,teaching))]

def start(s,key):
    guard(s);path=WORK/'cases'/key
    if (path/'result.json').exists():return path,None
    if path.exists():raise RuntimeError('incomplete case retained: '+key)
    path.mkdir(parents=True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    return path,tick

def finish(s,path,tick,result):
    elapsed=time.monotonic()-tick
    new_json(path/'result.json',result|{'wall_seconds':elapsed,'runner_signature':s.runner_signature})
    s.active_case=None;s.completed_count=(s.completed_count or 0)+1;s.completed_wall+=elapsed

def observe(value,until,s,full=False):
    start=value.engine.time_us;frames=[];states=[]
    checkpoints={start,start+100000,start+500000,start+1000000,until} if full else set()
    while True:
        frames.append({'time_us':str(value.engine.time_us),'nodes':value.engine.observation_nodes()})
        if value.engine.time_us in checkpoints:
            # Full evidence only; model features separately whitelist dynamics.
            states.append(value.engine.capture_state().to_dict())
        if value.engine.time_us>=until or value.engine.life=='dead':break
        value.reader.advance_to(min(until,value.engine.time_us+20000),guard=lambda:guard(s))
    value.records.clear()
    return {'start_us':str(start),'end_us':str(value.engine.time_us),'planned_end_us':str(until),
            'trajectory':frames,'states':states,'life':value.engine.life}

def source(s,a,seed,interval,frozen=False):
    if interval==0 and not frozen:return OLD/'cases'/f's{seed}-normal'
    key=f's{seed}-dt{interval}'+('-frozen' if frozen else '')
    path,tick=start(s,key)
    if tick is None:return path
    value=LanguageSession(old.e45.protocol(71).model_dump(),config={'seed':seed,'plasticity':not frozen},seed=seed,readouts=old.e45.READOUTS)
    lessons=old.e45.previous.schedule(old.NAMES,seed)
    for i,lesson in enumerate(lessons):
        lesson.update(text=old.NAMES[lesson['item']]+'是'+WORDS[lesson['item']]+'。')
        span=(len(a.frames(lesson['text']))-1)*interval
        next_us=round(lessons[i+1]['seconds']*1e6) if i+1<len(lessons) else 266000000
        if round(lesson['seconds']*1e6)+span>=next_us:raise ValueError('overlapping lessons: amend schedule first')
    new_json(path/'definition.json',{'seed':seed,'interval_us':interval,'frozen':frozen,'assignment':[0,1,2,3],
        'lessons':lessons,'config':value.engine.capture_state().to_dict()['config']})
    old.e45.previous.save_state(path/'initial',value,0)
    cursor=0;index=0;tape=RecordedBackground(WORK/'physical-telemetry.jsonl')
    for seconds in (266,326):
        with gzip.open(path/f'process-{seconds}.jsonl.gz','xt',encoding='utf-8') as stream:
            while value.engine.time_us<seconds*1000000 and value.engine.life!='dead':
                until=min(seconds*1000000,value.engine.time_us+500000)
                cursor=tape.queue_before(value.reader,cursor,until);acquisitions=[]
                while index<len(lessons) and round(lessons[index]['seconds']*1e6)<until:
                    lesson=lessons[index];measurement=a.world.sample(lesson['item'],lesson['repetition']%8)
                    frames=paired_visual(timed_frames(a,lesson['text'],interval,teaching=True),a.world.frame(measurement),10)
                    value.reader.schedule(frames,at=round(lesson['seconds']*1e6),source='E48-teaching',adapter_id='language-dose-study/1')
                    acquisitions.append({'lesson':lesson,'measurement':measurement,'input':input_summary(frames)})
                    index+=1
                # Full teaching nodes at20ms are useful evidence but compress well.
                stream.write(encoded({'process':observe(value,until,s),'acquisition':acquisitions}).decode()+'\n')
        old.e45.previous.save_state(path/f'checkpoint-{seconds}',value,cursor)
    finish(s,path,tick,{'kind':'source','seed':seed,'interval_us':interval,'frozen':frozen,'life':value.engine.life})
    print({'source':key,'seconds':round(time.monotonic()-tick,1)},flush=True)
    return path

def probe(s,a,parent,seed,interval,seconds,modality,item,variant,intensity,split,full=False):
    key=f'{parent.name}-t{seconds}-{modality}{item}-v{variant}-i{intensity}-{split}'+('-full' if full else '')
    path,tick=start(s,key)
    if tick is None:return
    checkpoint=parent/f'checkpoint-{seconds}';value=old.e45.previous.restore(checkpoint,71)
    cursor=read_json(checkpoint/'summary.json')['cursor'];frames=[];target=''
    if item>=0 and modality=='vision':
        frames=timed_frames(a,old.NAMES[item]+('是' if variant else ''),interval,intensity)
        target=WORDS[item]+'。'
    elif item>=0:
        frames=[{'stimulus':replace(a.world.frame(a.world.sample(item,variant)),intensity=intensity),'labels':{}}]
        target=old.NAMES[item]+'。'
    if frames:value.reader.schedule(frames,source='E48-probe',adapter_id='temporal-state-study/1')
    until=value.engine.time_us+2000000
    RecordedBackground(WORK/'physical-telemetry.jsonl').queue_before(value.reader,cursor,until)
    write_gzip(path/'process.json.gz',observe(value,until,s,full))
    finish(s,path,tick,{'kind':'probe','source':parent.name,'seed':seed,'interval_us':interval,'seconds':seconds,
        'modality':modality,'item':item,'variant':variant,'intensity':intensity,'split':split,'target':target,
        'frozen':parent.name.endswith('-frozen'),'full_state':full,'life':value.engine.life})

def probes(s,a,parent,seed,interval,seconds,full=False):
    for modality in ('vision','words'):
        probe(s,a,parent,seed,interval,seconds,modality,-1,0,.5,'test',full)
        probe(s,a,parent,seed,interval,seconds,modality,-1,0,.5,'train',full)
        for item in range(4):
            for variant in ((0,1) if modality=='vision' else (9,)):
                probe(s,a,parent,seed,interval,seconds,modality,item,variant,.5,'test',full)
            for variant,intensity in (((0,.4),(0,.6)) if modality=='vision' else ((8,.4),(10,.6))):
                probe(s,a,parent,seed,interval,seconds,modality,item,variant,intensity,'train',full)

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=('prepare','timing','full'))
    p.add_argument('--intervals',type=int,nargs='+',default=list(INTERVALS[1:]));p.add_argument('--seeds',type=int,nargs='+',default=list(SEEDS))
    args=p.parse_args();torch.set_num_threads(2);s=study(args.operation=='prepare')
    try:
        if args.operation=='prepare':
            for name in ('physical-telemetry.jsonl','projection.json'):
                shutil.copy2(OLD/name,WORK/name)
            new_json(WORK/'usage.json',{'used_percent':45})
            print({'project':s.project},flush=True);return
        a=adapter()
        for interval in args.intervals:
            if interval not in INTERVALS:raise ValueError('unregistered cadence')
            for seed in args.seeds:
                if seed not in SEEDS:raise ValueError('unregistered source')
                parent=source(s,a,seed,interval)
                for seconds in (266,326):probes(s,a,parent,seed,interval,seconds,full=args.operation=='full')
    finally:s.db.close()

if __name__=='__main__':main()
