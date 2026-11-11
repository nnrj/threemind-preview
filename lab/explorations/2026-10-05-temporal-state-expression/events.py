"""Registered continuous-event transfer diagnostic; no Core edits."""
import argparse,random
import numpy as np
from experiment import *
from raw_analysis import load_process,summarize
from lab.tools.visual_event_world import VisualEventWorld
from lab.tools.raw_state_expression import RawStateProjection,ridge_fit,ridge_predict

EVENT_SEEDS=(223,279);MODES=('joint','split','frozen');TARGETS={1:'顺。',-1:'逆。'}

def state_source(s,a,world,seed,mode):
    path,tick=start(s,f'event-s{seed}-{mode}')
    if tick is None:return path
    value=LanguageSession(old.e45.protocol(71).model_dump(),config={'seed':seed,'plasticity':mode!='frozen'},seed=seed,readouts=old.e45.READOUTS)
    order=[(i,sign) for i in (0,1) for sign in (-1,1)];random.Random(seed).shuffle(order)
    lessons=[]
    for slot,(item,sign) in enumerate(order):
        lessons.extend({'at':slot*24+2*r,'item':item,'order':sign,'view':r%3} for r in range(12))
    for repeat in range(4):
        for slot,(item,sign) in enumerate(order):lessons.append({'at':96+repeat*16+slot*4,'item':item,'order':sign,'view':repeat%3})
    new_json(path/'definition.json',{'seed':seed,'mode':mode,'lessons':lessons,'config':value.engine.capture_state().to_dict()['config']})
    old.e45.previous.save_state(path/'initial',value,0)
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl');cursor=0;index=0
    with gzip.open(path/'process.jsonl.gz','xt',encoding='utf-8') as f:
        while value.engine.time_us<168000000 and value.engine.life!='dead':
            until=min(168000000,value.engine.time_us+500000);cursor=tape.queue_before(value.reader,cursor,until);acquisitions=[]
            while index<len(lessons) and lessons[index]['at']*1000000<until:
                lesson=lessons[index]
                frames,measurements=world.event(lesson['item'],lesson['order'],lesson['view'],mode=='split')
                value.reader.schedule(frames,at=lesson['at']*1000000,source='E48-physical-event',adapter_id='visual-event-world/1')
                value.reader.schedule(timed_frames(a,TARGETS[lesson['order']],20000),at=lesson['at']*1000000+900000,
                                      source='E48-event-teacher',adapter_id='language-dose-study/1')
                acquisitions.append({'lesson':lesson,'measurements':measurements});index+=1
            f.write(encoded({'process':observe(value,until,s),'acquisitions':acquisitions}).decode()+'\n')
    old.e45.previous.save_state(path/'checkpoint-168',value,cursor)
    finish(s,path,tick,{'kind':'event-source','seed':seed,'mode':mode,'life':value.engine.life})
    print({'event_source':path.name},flush=True);return path

def event_probe(s,world,parent,seed,mode,item,sign,view,intensity,split):
    path,tick=start(s,f'{parent.name}-item{item}-order{sign}-v{view}-i{intensity}-{split}')
    if tick is None:return
    checkpoint=parent/'checkpoint-168';value=old.e45.previous.restore(checkpoint,71)
    cursor=read_json(checkpoint/'summary.json')['cursor'];begin=value.engine.time_us
    acquisition=[]
    if item>=0:
        frames,acquisition=world.event(item,sign,view,mode=='split')
        frames=[{'stimulus':replace(r['stimulus'],intensity=intensity),'labels':{}} for r in frames]
        value.reader.schedule(frames,source='E48-event-test',adapter_id='visual-event-world/1')
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl');tape.queue_before(value.reader,cursor,begin+2800000)
    # Retain the sensory event separately; expression sees only its aftermath.
    event=observe(value,begin+800000,s);process=observe(value,begin+2800000,s)
    write_gzip(path/'process.json.gz',process);write_gzip(path/'event.json.gz',{'process':event,'measurements':acquisition})
    finish(s,path,tick,{'kind':'event-probe','seed':seed,'mode':mode,'item':item,'order':sign,'variant':view,'intensity':intensity,
        'split':split,'target':TARGETS[sign] if item>=0 else '', 'life':value.engine.life})

def analyze(s):
    paths=[p for p in (WORK/'cases').glob('event-*/result.json') if read_json(p).get('kind')=='event-probe']
    cache=[];channels=set();direct=set()
    world=VisualEventWorld(71)
    direct.update(c for i in range(4) for r in world.event(i,1)[0] for c,_ in r['stimulus'].channels)
    for p in paths:
        process=load_process(p.parent/'process.json.gz');channels.update(int(n['channel']) for f in process['trajectory'] for n in f['nodes'])
        cache.append((p,read_json(p),process))
    details=[]
    for seed in EVENT_SEEDS:
        for mode in MODES:
            subset=[r for r in cache if r[1]['seed']==seed and r[1]['mode']==mode]
            for scope in ('all','cross'):
                excluded=direct if scope=='cross' else set()
                projection=RawStateProjection(tuple(sorted(channels-excluded)),('activation','inhibition','trace','support','stability'),17,tuple(sorted(excluded)))
                rows=[r|{'values':projection.project(process)['values'],'evidence':str(p.parent.relative_to(ROOT))} for p,r,process in subset]
                train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='test']
                if len(train)!=9 or len(test)!=9:raise ValueError('incomplete event partition')
                model=ridge_fit(train);outputs=ridge_predict(model,[r['values'] for r in test])
                baseline=next(o for r,o in zip(test,outputs) if r['item']<0)
                for r,o in zip(test,outputs):
                    details.append({k:r[k] for k in ('seed','mode','item','order','variant','target','evidence')}|
                        {'scope':scope,'output':o,'raw_correct':r['item']>=0 and o==r['target'],
                         'correct':r['item']>=0 and o==r['target'] and o!=baseline})
    groups=[]
    for seed in EVENT_SEEDS:
        for mode in MODES:
            for scope in ('all','cross'):
                rows=[r for r in details if r['seed']==seed and r['mode']==mode and r['scope']==scope and r['item']>=0]
                groups.append({'seed':seed,'mode':mode,'scope':scope,'raw_correct':sum(r['raw_correct'] for r in rows),
                               'cue_specific':sum(r['correct'] for r in rows),'count':len(rows)})
    new_json(HERE/'events-results.json',{'summary':groups,'rows':details,'classifier':'fixed raw ridge','chance':.5,
        'scope':'post-event pattern transfer; not general reasoning'})
    print({'events':groups},flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=('run','analyze'));args=p.parse_args()
    torch.set_num_threads(2);s=study()
    try:
        if args.operation=='analyze':analyze(s);return
        a=adapter();world=VisualEventWorld(71)
        for seed in EVENT_SEEDS:
            for mode in MODES:
                parent=state_source(s,a,world,seed,mode)
                for split in ('train','test'):
                    event_probe(s,world,parent,seed,mode,-1,1,0,.5,split)
                    for item in ((0,1) if split=='train' else (2,3)):
                        for sign in (-1,1):
                            for view,intensity in (((0,.4),(2,.6)) if split=='train' else ((9,.5),(11,.5))):
                                event_probe(s,world,parent,seed,mode,item,sign,view,intensity,split)
    finally:s.db.close()

if __name__=='__main__':main()
