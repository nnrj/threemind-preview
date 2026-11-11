"""Multi-angle physical/short-language teaching through the unchanged input bus."""
import argparse,random
from dataclasses import replace,asdict
from common import *
from lab.tools.recorded_background import RecordedBackground
from lab.tools.sensory_calibration import paired_visual
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.development import input_summary
from threemind_runtime.activity_stream import RawActivityStream


def curriculum(names,words,assignment,seed):
    order=[(item,form) for item in range(4) for form in range(3)];random.Random(seed).shuffle(order)
    rows=[];when=0.;reps={}
    def add(item,form,interval):
        nonlocal when
        key=item,form;repetition=reps.get(key,0);reps[key]=repetition+1
        name=names[assignment.index(item)];word=words[item]
        text=(name+'是'+word+'。','这是'+word+'，叫'+name+'。','看见'+word+'，这是'+name+'。')[form]
        rows.append({'seconds':when,'item':item,'form':form,'text':text,'view':repetition%8,'repetition':repetition});when+=interval
    for item,form in order:
        for _ in range(12):add(item,form,.5)
    for interval in (2,4,8,16):
        random.Random(seed+int(interval)).shuffle(order)
        for item,form in order:add(item,form,interval)
    return rows


def observe(value,until,s,full=False):
    start=value.engine.time_us;states=[];frames=[];stream=RawActivityStream();stream.subscribe('evidence',frames.append)
    checkpoints={start,start+100000,start+500000,start+1000000,until} if full else set()
    while True:
        stream.sample(value.engine)
        if value.engine.time_us in checkpoints:states.append(value.engine.capture_state().to_dict())
        if value.engine.time_us>=until or value.engine.life=='dead':break
        value.reader.advance_to(min(until,value.engine.time_us+20000),guard=lambda:guard(s))
    value.records.clear()
    return {'start_us':str(start),'end_us':str(value.engine.time_us),'trajectory':frames,'states':states,'life':value.engine.life}


def source(s,a,h,owner,condition):
    name=f's{owner}-multi-{condition}';path=WORK/'cases'/name
    if (path/'result.json').exists():return path
    if path.exists():raise RuntimeError('incomplete source preserved: '+name)
    guard(s,True);path.mkdir(parents=True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    assignment={'continued':[0,1,2,3],'reversal':[3,2,1,0],'cycle1':[2,0,3,1],'no-learning':[0,1,2,3]}[condition]
    config={'seed':owner}
    if condition=='no-learning':config['plasticity']=False
    value=LanguageSession(h.old.e45.protocol(71).model_dump(),config=config,seed=owner,readouts=h.old.e45.READOUTS)
    lessons=curriculum(h.old.NAMES,h.WORDS,assignment,owner)
    new_json(path/'definition.json',{'owner':owner,'condition':condition,'assignment':assignment,'lessons':lessons,'config':value.engine.capture_state().to_dict()['config']})
    h.old.e45.previous.save_state(path/'initial',value,0);cursor=0;index=0;tape=RecordedBackground(E48/'physical-telemetry.jsonl')
    for seconds in (440,500):
        with gzip.open(path/f'teaching-{seconds}.jsonl.gz','xt',encoding='utf-8') as out:
            while value.engine.time_us<seconds*1000000 and value.engine.life!='dead':
                until=min(seconds*1000000,value.engine.time_us+500000);cursor=tape.queue_before(value.reader,cursor,until)
                while index<len(lessons) and round(lessons[index]['seconds']*1e6)<until:
                    lesson=lessons[index];measurement=a.world.sample(lesson['item'],lesson['view'])
                    frames=paired_visual(h.timed_frames(a,lesson['text'],0,teaching=True),a.world.frame(measurement),10)
                    value.reader.schedule(frames,at=round(lesson['seconds']*1e6),source='E50-teacher',adapter_id='language-dose-study/1')
                    out.write(json.dumps({'lesson':lesson,'measurement':measurement,'input':input_summary(frames),
                        'delivered':[asdict(r['stimulus']) for r in frames]},ensure_ascii=False)+'\n');index+=1
                # Source dynamics progress normally; no interpretive output affects input.
                value.reader.advance_to(until,guard=lambda:guard(s));value.records.clear()
                out.write(json.dumps({'time_us':str(value.engine.time_us),'nodes':value.engine.observation_nodes()},ensure_ascii=False)+'\n')
        h.old.e45.previous.save_state(path/f'checkpoint-{seconds}',value,cursor)
    new_json(path/'result.json',{'kind':'source','owner':owner,'condition':condition,'life':value.engine.life,'lessons':index,'wall_seconds':time.monotonic()-tick})
    s.active_case=None;print({'source':name,'life':value.engine.life,'lessons':index},flush=True);return path


def probe(s,a,h,parent,seconds,item,kind,view,intensity,split):
    name=f'{parent.name}-t{seconds}-i{item}-{kind}-v{view}-x{intensity}-{split}';path=WORK/'cases'/name
    if (path/'result.json').exists():return
    if path.exists():raise RuntimeError('incomplete probe preserved')
    guard(s,True);path.mkdir(parents=True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    checkpoint=parent/f'checkpoint-{seconds}';value=h.old.e45.previous.restore(checkpoint,71)
    cursor=read_json(checkpoint/'summary.json')['cursor'];definition=read_json(parent/'definition.json');frames=[];text=None
    if item>=0:
        if kind=='visual':frames=[{'stimulus':replace(a.world.frame(a.world.sample(item,view)),intensity=intensity),'labels':{}}]
        else:
            word=h.WORDS[item];text={'bare':word+'。','description':'这是'+word+'。','unseen':'我看见'+word+'。'}[kind]
            frames=h.timed_frames(a,text,0,intensity)
        value.reader.schedule(frames,source='E50-probe',adapter_id='language-dose-study/1')
    tape=RecordedBackground(E48/'physical-telemetry.jsonl');tape.queue_before(value.reader,cursor,value.engine.time_us+2000000)
    data=observe(value,value.engine.time_us+2000000,s,True);write_gzip(path/'process.json.gz',data)
    result={'kind':'probe','owner':definition['owner'],'condition':definition['condition'],'seconds':seconds,'item':item,
            'perspective':kind,'view':view,'intensity':intensity,'split':split,'text':text,'input':input_summary(frames) if frames else None,
            'target':h.old.NAMES[definition['assignment'].index(item)]+'。' if item>=0 else None,
            'delivered':[asdict(r['stimulus']) for r in frames],
            'life':value.engine.life,'wall_seconds':time.monotonic()-tick}
    new_json(path/'result.json',result);s.active_case=None


def main():
    p=argparse.ArgumentParser();p.add_argument('--owner',type=int,choices=(223,279),required=True)
    p.add_argument('--condition',choices=('continued','reversal','cycle1','no-learning'));args=p.parse_args()
    torch.set_num_threads(2);s=study();h=helpers();a=h.adapter()
    try:
        for condition in ((args.condition,) if args.condition else ('continued','reversal')):
            parent=source(s,a,h,args.owner,condition)
            if condition=='no-learning':
                for item in range(4):probe(s,a,h,parent,440,item,'visual',9,.5,'test')
                continue
            for seconds in (440,500):
                if seconds==440 and condition!='cycle1':
                    for item in range(4):
                        for kind,view,intensity in [('visual',8,.4),('visual',10,.6),('bare',0,.4),('description',0,.6)]:
                            probe(s,a,h,parent,seconds,item,kind,view,intensity,'train')
                for item in range(4):
                    for kind,view in [('visual',9),('visual',11),('bare',0),('description',0),('unseen',0)]:
                        probe(s,a,h,parent,seconds,item,kind,view,.5,'test')
                probe(s,a,h,parent,seconds,-1,'none',0,.5,'test')
            print({'probed':parent.name},flush=True)
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':main()
