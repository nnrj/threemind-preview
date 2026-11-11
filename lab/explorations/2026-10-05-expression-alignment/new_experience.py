"""New individuals and held-out assignments; guarded by the registered B gate."""
import gzip
import json
from experiment import *
from lab.tools.recorded_background import RecordedBackground
from lab.tools.sensory_calibration import paired_visual
from lab.tools.language_teaching_world import WORDS
from threemind_transformer.development import input_summary
from threemind_transformer.language_session import LanguageSession

NEW_SEEDS=(223,251,279)
ASSIGNMENTS={'normal':[0,1,2,3],'continued':[0,1,2,3],'reversal':[3,2,1,0],
             'cycle1':[1,2,3,0],'cycle2':[2,3,0,1],'frozen':[0,1,2,3]}


def source(s,adapter,seed,condition,parent=None):
    path,started=e46.start_case(s,f's{seed}-{condition}')
    if started is None:return path
    if parent:
        checkpoint=parent/'checkpoint-266'
        value=e46.e45.previous.restore(checkpoint,71)
        cursor=read_json(checkpoint/'summary.json')['cursor'];offset=266;boundaries=(532,592)
    else:
        value=LanguageSession(e46.e45.protocol(71).model_dump(),config={'seed':seed,'plasticity':condition!='frozen'},
                              seed=seed,readouts=e46.e45.READOUTS)
        cursor=0;offset=0;boundaries=(266,326)
    lessons=e46.e45.previous.schedule(e46.NAMES,seed)
    assignment=ASSIGNMENTS[condition]
    for lesson in lessons:
        lesson.update(seconds=lesson['seconds']+offset,object=assignment[lesson['item']],
                      text=e46.NAMES[lesson['item']]+'是'+WORDS[assignment[lesson['item']]]+'。')
    new_json(path/'definition.json',{'schema':'E47-source/1','seed':seed,'condition':condition,'parent':str(parent),
        'assignment':assignment,'lessons':lessons,'input_wiring':71,'route':adapter.route,
        'config':value.engine.capture_state().to_dict()['config'],'names':e46.NAMES})
    e46.e45.previous.save_state(path/'initial',value,cursor)
    tape=RecordedBackground(WORK/'physical-telemetry.jsonl');index=0
    for seconds in boundaries:
        with gzip.open(path/f'process-{seconds}.jsonl.gz','xt',encoding='utf-8') as stream:
            while value.engine.time_us<seconds*1000000 and value.engine.life!='dead':
                until=min(seconds*1000000,value.engine.time_us+500000)
                cursor=tape.queue_before(value.reader,cursor,until);acquisitions=[]
                while index<len(lessons) and round(lessons[index]['seconds']*1e6)<until:
                    lesson=lessons[index];measurement=adapter.world.sample(lesson['object'],lesson['repetition']%8)
                    frames=paired_visual(adapter.frames(lesson['text'],teaching=True),adapter.world.frame(measurement),10)
                    value.reader.schedule(frames,at=round(lesson['seconds']*1e6),source='E47-teaching',adapter_id='language-dose-study/1')
                    acquisitions.append({'lesson':lesson,'measurement':measurement,'input':input_summary(frames)})
                    index+=1
                stream.write(encoded({'process':e46.observe(value,until,s),'acquisition':acquisitions}).decode()+'\n')
        e46.e45.previous.save_state(path/f'checkpoint-{seconds}',value,cursor)
    e46.finish(s,path,started,{'kind':'source','seed':seed,'condition':condition,'life':value.engine.life,'route':adapter.route})
    print(json.dumps({'new_source':path.name,'wall_seconds':round(time.monotonic()-started,1)}),flush=True)
    return path


def main():
    if read_json(WORK/'feature-summary.json')['selected'] is None:
        raise RuntimeError('registered expansion gate not met; do not run new sources')
    torch.set_num_threads(2);s=study();adapter=helpers()
    try:
        for seed in NEW_SEEDS:
            parent=source(s,adapter,seed,'normal')
            for seconds in (266,326):e46.probes(s,adapter,parent,seconds,True)
            for condition in ('continued','reversal','cycle1','cycle2'):
                branch=source(s,adapter,seed,condition,parent)
                for seconds in (532,592):e46.probes(s,adapter,branch,seconds,True)
            frozen=source(s,adapter,seed,'frozen')
            e46.probes(s,adapter,frozen,266,False)
    finally:s.db.close()


if __name__=='__main__':main()
