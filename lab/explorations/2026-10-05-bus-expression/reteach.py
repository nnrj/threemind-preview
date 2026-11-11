"""Further ordinary teaching through InputBus; frozen external expression."""
import gzip
from dataclasses import replace
from common import *
from lab.tools.recorded_background import RecordedBackground
from lab.tools.sensory_calibration import paired_visual
from lab.tools.raw_state_expression import RawStateProjection
from threemind_runtime.activity_stream import RawActivityStream
from threemind_transformer.development_model import load

def observe(value,end,interval,s,record=None):
    stream=RawActivityStream();frames=[]
    stream.subscribe('evidence',frames.append if record is None else record)
    start=value.engine.time_us
    while True:
        stream.sample(value.engine)
        if value.engine.time_us>=end or value.engine.life=='dead':break
        value.reader.advance_to(min(end,value.engine.time_us+interval),guard=lambda:guard(s))
    value.records.clear()
    return {'start_us':str(start),'end_us':str(value.engine.time_us),'trajectory':frames,'life':value.engine.life}

def run():
    torch.set_num_threads(2);s=study();e48=old_helpers();a=e48.adapter();results=[]
    try:
        for owner in (223,279):
            head=WORK/'models'/f's{owner}-correction-continued.json'
            meta=read_json(head);projection=RawStateProjection(**meta['projection'])
            model,_=load(head.with_suffix('.safetensors'),'cuda' if torch.cuda.is_available() else 'cpu')
            mistakes=[r['item'] for r in meta['rows'] if r['condition']=='cycle1' and r['seconds']==592 and r['item']>=0 and r['output']!=r['target']]
            parent=OLD/'cases'/f's{owner}-cycle1';assignment=read_json(parent/'definition.json')['assignment']
            for condition in ('wait','balanced','targeted'):
                if condition=='targeted' and not mistakes:continue
                branch=WORK/'cases'/f'reteach-s{owner}-{condition}'
                if (branch/'result.json').exists():
                    results.extend(read_json(p) for p in (WORK/'cases').glob(f'probe-s{owner}-{condition}-*/result.json'));continue
                if branch.exists():raise RuntimeError('incomplete branch preserved')
                guard(s,True);branch.mkdir(parents=True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
                value=e48.old.e45.previous.restore(parent/'checkpoint-592',71)
                cursor=read_json(parent/'checkpoint-592'/'summary.json')['cursor'];lessons=[];offset=0.
                for i in range(48 if condition!='wait' else 0):
                    item=i//12 if condition=='balanced' else mistakes[i%len(mistakes)]
                    name=e48.old.NAMES[assignment.index(item)]
                    lessons.append({'seconds':592+offset,'item':item,'text':name+'是'+e48.WORDS[item]+'。','view':i%8})
                    offset+=.5 if i<16 else 1. if i<32 else 2.
                new_json(branch/'definition.json',{'owner':owner,'condition':condition,'mistakes':mistakes,
                    'lessons':lessons,'frozen_head':str(head),'assignment':assignment,'parent':str(parent)})
                tape=RecordedBackground(PREVIOUS/'physical-telemetry.jsonl');index=0
                for seconds in (650,710):
                    with gzip.open(branch/f'teaching-{seconds}.jsonl.gz','xt',encoding='utf-8') as out:
                        while value.engine.time_us<seconds*1000000 and value.engine.life!='dead':
                            until=min(seconds*1000000,value.engine.time_us+500000)
                            cursor=tape.queue_before(value.reader,cursor,until)
                            while index<len(lessons) and round(lessons[index]['seconds']*1e6)<until:
                                lesson=lessons[index]
                                frames=paired_visual(e48.timed_frames(a,lesson['text'],0,teaching=True),a.world.frame(a.world.sample(lesson['item'],lesson['view'])),10)
                                value.reader.schedule(frames,at=round(lesson['seconds']*1e6),source='E49-teacher',adapter_id='language-dose-study/1')
                                out.write(json.dumps({'input':e48.input_summary(frames),'lesson':lesson},ensure_ascii=False)+'\n');index+=1
                            observe(value,until,100000,s,record=lambda f:out.write(json.dumps({'frame':f},ensure_ascii=False)+'\n'))
                    checkpoint=branch/f'checkpoint-{seconds}';e48.old.e45.previous.save_state(checkpoint,value,cursor)
                    for item in range(-1,4):
                        probe=WORK/'cases'/f'probe-s{owner}-{condition}-t{seconds}-i{item}';probe.mkdir(parents=True)
                        probe_tick=time.monotonic();copy=e48.old.e45.previous.restore(checkpoint,71)
                        if item>=0:
                            copy.reader.schedule([{'stimulus':replace(a.world.frame(a.world.sample(item,9)),intensity=.5),'labels':{}}],source='E49-probe',adapter_id='raw-state-study/1')
                        tape.queue_before(copy.reader,cursor,copy.engine.time_us+2000000)
                        process=observe(copy,copy.engine.time_us+2000000,20000,s);write_gzip(probe/'process.json.gz',process)
                        raw=projection.project(process)['values'];output=model.decode(np.asarray([raw],dtype=np.float32))[0]
                        result={'owner':owner,'condition':condition,'seconds':seconds,'item':item,
                            'target':e48.old.NAMES[assignment.index(item)]+'。' if item>=0 else None,
                            'output':output['text'],'life':process['life'],'wall_seconds':time.monotonic()-probe_tick}
                        new_json(probe/'result.json',result);results.append(result)
                # Probe time is recorded in probes and removed from branch to avoid double charging.
                elapsed=time.monotonic()-tick
                probe_seconds=sum(r['wall_seconds'] for r in results if r['owner']==owner and r['condition']==condition)
                new_json(branch/'result.json',{'owner':owner,'condition':condition,'life':value.engine.life,
                    'lessons':len(lessons),'wall_seconds':max(0,elapsed-probe_seconds)})
                s.active_case=None
                print({'branch':branch.name,'results':[(r['seconds'],r['item'],r['output'],r['target']) for r in results if r['owner']==owner and r['condition']==condition]},flush=True)
        new_json(HERE/'reteaching-results.json',{'rows':results,'scope':'Core re-teaching with frozen corrected expression; no parameter changes'})
    finally:s.active_case=None;s.db.close()

if __name__=='__main__':run()
