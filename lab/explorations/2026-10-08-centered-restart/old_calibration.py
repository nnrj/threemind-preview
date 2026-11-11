"""Conditional continuation of E63's OWN peripheral, only after blank success.

The old study's STOP and partial case remain untouched. All new work belongs
to this separately registered study. No weights from the new subject are used.
"""
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from experiment import study,run,WORK,tasks,count_instance,device,record
from lab.tools.centered_recognition import CenteredSystem,PersonalVocabulary,WORDS
from lab.tools.service_study import read_json,new_json
from lab.tools.continuous_motor import recent_window

SOURCE=ROOT/'.work/rehearsal-centered-20261007/cases/centered-correction/system'


def restore(path):
    count_instance();return CenteredSystem.restore(path,device())


def question(a,t,s):
    a.session.world.present(t['shape'],t['color'],offset=t['offset']);a.session.world.marker=None
    frames=list(a.session.sensor.frames(t['text']));rows=[]
    # Keep E63's original two-second question, body, channel identities and head.
    for i in range(40):
        row=a.step(frames[i] if i<len(frames) else None,guard=s.guard)
        row['teacher_utterance']=t['text'];rows.append(row)
    ids=np.rint(np.linspace(0,len(rows)-1,16)).astype(int)
    x=np.stack([a.words.layout.frame(rows[i]['activity']) for i in ids])
    return rows,x


def collect(s):
    def op(p):
        xs=[];ys=[];settings=tasks('calibration')+tasks('practice')
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,t in enumerate(settings):
                a=restore(SOURCE);rows,x=question(a,t,s);xs.append(x);ys.append(t['label'])
                record(f,rows,kind='old-personal-calibration',trial=t)
                del a
                if (i+1)%12==0:print(json.dumps(dict(stage='old-calibration',questions=i+1,of=60)),flush=True)
        np.savez_compressed(p/'features.npz',x=xs,y=ys)
        return dict(n=len(ys),source=str(SOURCE),question_seconds=2,frames_per_question=16)
    return run(s,'old-question-calibration',op)


def fit(s):
    def op(p):
        a=restore(SOURCE);before=a.words.steps
        if a.words.readout_profile!='recent-window':raise ValueError('expect original E63 reader, not another calibrated branch')
        with np.load(WORK/'cases/old-question-calibration/features.npz',allow_pickle=False) as d:
            result=a.words.calibrate(d['x'],d['y'],updates=1200,guard=s.guard)
        a.words.readout_profile='whole-question';a.phase='calibrated-after-blank-verification';a.save(p/'system')
        return dict(before=before,after=a.words.steps,fit=result,identity=a.identity,
                    core_time_us=a.session.engine.time_us,source=str(SOURCE),
                    policy='original weights/Adam/cache/RNG, last calibration state; no new-subject weights')
    return run(s,'old-personal-fit',op)


def evaluate(s,split):
    def op(p):
        original=PersonalVocabulary.restore(SOURCE/'words',device());scores=[];xs=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,t in enumerate(tasks(split)):
                a=restore(WORK/'cases/old-personal-fit/system');rows,x=question(a,t,s)
                pred=a.words.predict(x)
                before=original.predict(x);recent=original.predict(recent_window(original.layout,rows))
                selected=None if pred is None else int(pred.argmax())
                result=t|dict(selected=selected,word=None if selected is None else WORDS[selected],correct=selected==t['label'],
                    original_whole=None if before is None else int(before.argmax()),
                    original_recent=None if recent is None else int(recent.argmax()))
                rows[-1]['recent_expression']=rows[-1]['expression']
                rows[-1]['expression']=dict(word=result['word'],probabilities=None if pred is None else pred.tolist(),
                    identity=a.identity,steps_before=a.words.steps,readout_profile='whole-question')
                scores.append(result);xs.append(x);record(f,rows,kind='old-calibrated-'+split,trial=result)
                del a
                if (i+1)%8==0:print(json.dumps(dict(stage='old-'+split,questions=i+1,correct=sum(r['correct'] for r in scores))),flush=True)
        new_json(p/'predictions.json',scores);np.savez_compressed(p/'features.npz',x=xs,y=[r['label'] for r in scores])
        shape=sum(r['correct'] for r in scores if r['label']<4);color=sum(r['correct'] for r in scores if r['label']>=4)
        return dict(n=len(scores),correct=shape+color,shape_correct=shape,color_correct=color,
                    reliable=shape>=12 and color>=12,
                    original_recent_correct=sum(r['original_recent']==r['label'] for r in scores),
                    original_whole_correct=sum(r['original_whole']==r['label'] for r in scores),
                    comparison='all three readings use these exact Core question trajectories; body/Core not fitted')
    return run(s,'old-'+split+'-normal',op)


def main():
    if not all(read_json(WORK/f'cases/{split}-normal/result.json')['reliable'] for split in ('test','confirmation')):
        raise RuntimeError('blank verification gate not met; old individual remains paused')
    s=study()
    try:
        collect(s);fit(s);evaluate(s,'test');evaluate(s,'confirmation')
    finally:s.db.close()


if __name__=='__main__':main()
