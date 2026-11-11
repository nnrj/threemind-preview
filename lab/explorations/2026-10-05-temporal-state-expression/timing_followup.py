"""One predeclared nonzero timing candidate, with immutable0ms controls."""
from raw_analysis import load_process,instrument,FIELDSETS,scored,summarize
from experiment import *

ASSIGNMENTS={'continued':[0,1,2,3],'reversal':[3,2,1,0],'cycle1':[1,2,3,0]}


def branch(s,a,seed,condition):
    path,tick=start(s,f'follow-s{seed}-dt1000-{condition}')
    if tick is None:return path
    checkpoint=WORK/'cases'/f's{seed}-dt1000'/'checkpoint-266'
    value=old.e45.previous.restore(checkpoint,71);cursor=read_json(checkpoint/'summary.json')['cursor']
    assignment=ASSIGNMENTS[condition];lessons=old.e45.previous.schedule(old.NAMES,seed)
    for lesson in lessons:
        lesson.update(seconds=lesson['seconds']+266,object=assignment[lesson['item']],
            text=old.NAMES[lesson['item']]+'是'+WORDS[assignment[lesson['item']]]+'。')
    new_json(path/'definition.json',{'seed':seed,'condition':condition,'assignment':assignment,'lessons':lessons,
        'parent':str(checkpoint.relative_to(ROOT)),'interval_us':1000})
    old.e45.previous.save_state(path/'initial',value,cursor);index=0;tape=RecordedBackground(WORK/'physical-telemetry.jsonl')
    for seconds in (532,592):
        with gzip.open(path/f'process-{seconds}.jsonl.gz','xt',encoding='utf-8') as f:
            while value.engine.time_us<seconds*1000000 and value.engine.life!='dead':
                until=min(seconds*1000000,value.engine.time_us+500000);cursor=tape.queue_before(value.reader,cursor,until);acquisition=[]
                while index<len(lessons) and round(lessons[index]['seconds']*1e6)<until:
                    lesson=lessons[index];measurement=a.world.sample(lesson['object'],lesson['repetition']%8)
                    frames=paired_visual(timed_frames(a,lesson['text'],1000,teaching=True),a.world.frame(measurement),10)
                    value.reader.schedule(frames,at=round(lesson['seconds']*1e6),source='E48-time-followup',adapter_id='language-dose-study/1')
                    acquisition.append({'lesson':lesson,'measurement':measurement,'input':input_summary(frames)});index+=1
                f.write(encoded({'process':observe(value,until,s),'acquisition':acquisition}).decode()+'\n')
        old.e45.previous.save_state(path/f'checkpoint-{seconds}',value,cursor)
    finish(s,path,tick,{'kind':'followup-source','seed':seed,'condition':condition,'interval_us':1000,'life':value.engine.life})
    return path


def probes(s,a,parent,seed,condition):
    for seconds in (532,592):
        for split in ('train','test'):
            if seconds==592 and split=='train':continue
            choices=[(-1,0,.5)]+[(i,v,n) for i in range(4) for v,n in (((8,.4),(10,.6)) if split=='train' else ((9,.5),))]
            for item,view,strength in choices:
                path,tick=start(s,f'{parent.name}-t{seconds}-item{item}-v{view}-i{strength}-{split}')
                if tick is None:continue
                checkpoint=parent/f'checkpoint-{seconds}';value=old.e45.previous.restore(checkpoint,71)
                cursor=read_json(checkpoint/'summary.json')['cursor']
                if item>=0:value.reader.schedule([{'stimulus':replace(a.world.frame(a.world.sample(item,view)),intensity=strength),'labels':{}}],
                    source='E48-time-followup-probe',adapter_id='language-dose-study/1')
                until=value.engine.time_us+2000000;RecordedBackground(WORK/'physical-telemetry.jsonl').queue_before(value.reader,cursor,until)
                write_gzip(path/'process.json.gz',observe(value,until,s))
                finish(s,path,tick,{'kind':'followup-probe','seed':seed,'condition':condition,'interval_us':1000,'seconds':seconds,
                    'item':item,'variant':view,'split':split,'modality':'words','target':old.NAMES[ASSIGNMENTS[condition].index(item)]+'。' if item>=0 else '',
                    'intensity':strength,'life':value.engine.life})


def analyze():
    from raw_transformer import recorded_rows
    rows=[r for r in recorded_rows() if r['seed'] in (223,279) and r['condition'] in ASSIGNMENTS and r['seconds'] in (532,592)]
    for p in (WORK/'cases').glob('follow-*/result.json'):
        r=read_json(p)
        if r['kind']!='followup-probe':continue
        process=load_process(p.parent/'process.json.gz')
        rows.append(r|{'evidence':str(p.parent.relative_to(ROOT)),'raw':{scope:instrument('words',FIELDSETS['history'],scope).project(process)['values'] for scope in ('all','cross')}})
    out=[]
    for seed in (223,279):
        for interval in (0,1000):
            own=[r for r in rows if r['seed']==seed and r['interval_us']==interval]
            for scope in ('all','cross'):
                train=[r for r in own if r['split']=='train' and r['condition'] in ('continued','reversal') and r['seconds']==532]
                test=[r for r in own if r['split']=='test']
                if len(train)!=18:raise ValueError('incomplete follow-up training')
                out.extend(r|{'scope':scope} for r in scored(train,test,FIELDSETS['history'],scope))
    new_json(HERE/'timing-followup-results.json',{'summary':summarize(out,('interval_us','scope','condition','seconds')),'rows':out,
        'fields':'raw history','classifier':'fixed ridge','selection':'smallest nonzero tied timing candidate'})


def main():
    torch.set_num_threads(2);s=study()
    try:
        a=adapter()
        for seed in (223,279):
            for condition in ASSIGNMENTS:
                parent=branch(s,a,seed,condition);probes(s,a,parent,seed,condition)
                print({'followup':parent.name},flush=True)
        analyze()
    finally:s.db.close()


if __name__=='__main__':main()
