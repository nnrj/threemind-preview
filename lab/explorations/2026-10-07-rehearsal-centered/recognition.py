"""One visible object, ordinary teacher input, own continuously learned words."""
import argparse
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from experiment import study,run,WORK,count_instance,device,E62
from lab.tools.centered_recognition import CenteredSystem,WORDS
from lab.tools.continuous_motor import WINDOW
from lab.tools.service_study import new_json


def task(label,shape=None,color=None,offset=(0.,0.)):
    if shape is None:shape=label if label<4 else 0
    if color is None:color=4 if label<4 else label-4
    kind='形状' if label<4 else '颜色'
    return dict(label=label,shape=shape,color=color,offset=list(offset),
                statement=f'这是{WORDS[label]}。',question=f'这是什么{kind}？')


def lesson(s,a,t,teach=False):
    w=a.session.world;w.present(t['shape'],t['color'],offset=t['offset'])
    rows=[];sensor=a.session.sensor
    if teach:
        frames=list(sensor.frames(t['statement']))
        for i in range(30):
            row=a.step(frames[i] if i<len(frames) else None,guard=s.guard)
            row['teacher_utterance']=t['statement'];rows.append(row)
    frames=list(sensor.frames(t['question']));question_start=len(rows)
    for i in range(40):
        # Answer absent from the question. Supervision only after question arrives.
        row=a.step(frames[i] if i<len(frames) else None,
                   label=t['label'] if teach and i>=20 and i%4==0 else None,guard=s.guard)
        row['teacher_utterance']=t['question'];rows.append(row)
    if a.words.readout_profile=='whole-question':
        probabilities=a.words.predict(question_window(a,rows[question_start:]))
        rows[-1]['recent_expression']=rows[-1]['expression']
        rows[-1]['expression']=dict(probabilities=None if probabilities is None else probabilities.tolist(),
            word=None if probabilities is None else WORDS[int(probabilities.argmax())],
            steps_before=a.words.steps,identity=a.identity,readout_profile='whole-question')
    probabilities=rows[-1]['expression']['probabilities']
    selected=None if probabilities is None else int(np.argmax(probabilities))
    return rows,t|dict(selected=selected,word=None if selected is None else WORDS[selected],
                       correct=selected==t['label'],teaching=teach,steps=a.words.steps,
                       answer_source='raw Core activity only',text=t['question'])


def question_window(a,rows):
    indices=np.rint(np.linspace(0,len(rows)-1,WINDOW)).astype(int)
    return np.stack([a.words.layout.frame(rows[i]['activity']) for i in indices])


def curriculum():
    out=[dict(kind='lesson',task=task(label),phase='initial') for label in range(8) for _ in range(10)]
    rng=np.random.default_rng(6331)
    for r,gap in enumerate((2.,6.,18.),1):
        out.append(dict(kind='gap',seconds=gap,phase=f'review-{r}-interval'))
        out.extend(dict(kind='lesson',task=task(int(label)),phase=f'review-{r}') for label in rng.permutation(8))
    return out


def train(s,resume_from=None):
    resume_from=None if resume_from is None else Path(resume_from).resolve()
    if resume_from is not None and not resume_from.is_relative_to((WORK/'cases').resolve()):
        raise ValueError('resume only a declared complete snapshot within this study')
    key='centered-teaching' if resume_from is None else 'centered-teaching-resume-'+resume_from.name
    def operation(p):
        count_instance()
        a=CenteredSystem(device=device()) if resume_from is None else CenteredSystem.restore(resume_from,device())
        if a.identity!='e63-centered-631':raise ValueError('normal continuation of the same individual only')
        if resume_from is None:a.save(p/'birth')
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for index in range(a.cursor,len(curriculum())):
                item=curriculum()[index]
                a.phase=item['phase']
                if item['kind']=='lesson':
                    rows,result=lesson(s,a,item['task'],True)
                    E62.record(f,a.phase,index,rows,trial=result)
                else:
                    rows=[a.step(guard=s.guard) for _ in range(round(item['seconds']/.05))]
                    E62.record(f,a.phase,index,rows)
                a.cursor=index+1
                if index+1 in (40,80,107):
                    a.save(p/f'stage-{index+1}');f.flush()
                if (index+1)%10==0:print(json.dumps({'centered_lesson':index+1,'steps':a.words.steps,'sim_s':a.session.engine.time_us/1e6}),flush=True)
        a.phase='taught';a.save(p/'system')
        return dict(identity=a.identity,lessons=104,updates=a.words.steps,sim_seconds=a.session.engine.time_us/1e6,
                    snapshot=str(p/'system'),input='fixed whole eye, physical background, ordinary teacher text',
                    policy='individual 256-example reservoir; last state, no rollback')
    return run(s,key,operation)


def tests(offset=False):
    off=(.012,-.012) if offset else (0.,0.)
    out=[task(i,offset=off)|{'category':'taught-basic'} for i in range(8)]
    for shape in (1,2,3):
        for color in range(4):
            out += [task(shape,shape,color,off)|{'category':'unseen-combination'},
                    task(color+4,shape,color,off)|{'category':'unseen-combination'}]
    order=np.random.default_rng(6337 if offset else 6333).permutation(len(out))
    return [out[i] for i in order]


def evaluate(s,mode,corrected=False,source_case=None,variant_test=False):
    source_case=source_case or ('centered-correction' if corrected else 'centered-teaching')
    if Path(source_case).name!=source_case or not source_case.startswith('centered-'):raise ValueError('declared case name')
    source=WORK/'cases'/source_case/'system'
    feedback=source_case=='centered-feedback';calibrated=source_case=='centered-calibration'
    key='centered-'+('calibrated-' if calibrated else 'feedback-' if feedback else 'corrected-' if corrected else 'variant-' if variant_test else '')+(source_case+'-' if 'resume-' in source_case else '')+mode
    def operation(p):
        count_instance();a=CenteredSystem.restore(source,device(),branch=key)
        a.phase='evaluation';before=a.words.steps
        edges=[(e['source'],e['target']) for e in a.session.engine.capture_state().to_dict()['edges']]
        if mode in ('silence','rescue'):
            a.session.engine.intervene(edges=edges,action='silence')
            if mode=='rescue':a.session.engine.intervene(edges=edges,action='unsilence')
        if mode=='blank-core':
            # Explicit transplant control: trained words kept; only blank Core,
            # reader and raw history come from this individual's birth snapshot.
            count_instance();blank=CenteredSystem.restore(WORK/'cases/centered-teaching/birth',device())
            body=a.session.world
            a.session=blank.session;a.session.world=body
            new_json(p/'intervention.json',dict(type='blank Core plus trained personal expression',
                core='own birth',body='post-teaching',words='post-teaching frozen',
                caveat='changes both structural and recent activity history; not ordinary development'))
        scores=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,t in enumerate(tests(corrected or variant_test or feedback or calibrated)):
                rows,result=lesson(s,a,t)
                scores.append(result);E62.record(f,a.phase,i,rows,trial=result)
                print(json.dumps({'recognition':key,'trial':i,'expected':WORDS[t['label']],'actual':result['word']}),flush=True)
        assert a.words.steps==before
        new_json(p/'scores.json',scores);a.save(p/'system')
        return dict(mode=mode,n=len(scores),correct=sum(t['correct'] for t in scores),
                    basic_correct=sum(t['correct'] for t in scores if t['category']=='taught-basic'),
                    combination_correct=sum(t['correct'] for t in scores if t['category']=='unseen-combination'),
                    shape_correct=sum(t['correct'] for t in scores if t['label']<4),
                    color_correct=sum(t['correct'] for t in scores if t['label']>=4),updates=before)
    return run(s,key,operation)


def correct(s):
    def operation(p):
        count_instance();a=CenteredSystem.restore(WORK/'cases/centered-teaching/system',device());a.phase='corrective-teaching'
        oldsteps=a.words.steps;attempts=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,label in enumerate(np.random.default_rng(6339).permutation(8)):
                t=task(int(label));rows,result=lesson(s,a,t);attempts.append(result)
                E62.record(f,'try-yourself',i,rows,trial=result)
                if not result['correct']:
                    for rep in range(5):
                        rows,result=lesson(s,a,t,True);E62.record(f,'teacher-correction',i*5+rep,rows,trial=result)
                # Old *teacher* labels reviewed, never the peripheral's guesses.
                for old in range(8):
                    if old==label:continue
                    rows,result=lesson(s,a,task(old),True);E62.record(f,'mixed-review',i*8+old,rows,trial=result)
                f.flush()
                print(json.dumps({'corrective_practice':i+1,'initial_answer_correct':attempts[-1]['correct'],
                                  'updates':a.words.steps,'sim_s':a.session.engine.time_us/1e6}),flush=True)
        a.save(p/'system')
        return dict(before=oldsteps,after=a.words.steps,practice_correct=sum(t['correct'] for t in attempts),
                    trials=8,sim_seconds=a.session.engine.time_us/1e6)
    return run(s,'centered-correction',operation)


def feedback(s):
    """Teach the actual answering window, before the verbal correct answer.

    Continue the same complete corrected individual and optimizer. The teacher
    label is training supervision only; the peripheral still reads raw Core.
    """
    def operation(p):
        count_instance();a=CenteredSystem.restore(WORK/'cases/centered-correction/system',device())
        a.phase='answer-feedback';oldsteps=a.words.steps;attempts=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            rng=np.random.default_rng(6347)
            for cycle in range(5):
                if cycle in (1,2,4):
                    gap={1:2.,2:6.,4:18.}[cycle]
                    rows=[a.step(guard=s.guard) for _ in range(round(gap/.05))]
                    E62.record(f,'feedback-review-gap',cycle,rows)
                for label in rng.permutation(8):
                    t=task(int(label));rows,result=lesson(s,a,t);attempts.append(result)
                    result['training_feedback_after_answer']=True
                    result['updates_after_answer']=8
                    E62.record(f,'answer-before-feedback',len(attempts)-1,rows,trial=result)
                    # Snapshot the raw answer window before saying the answer.
                    a.words.teach(a.window(),int(label),updates=8)
                    frames=list(a.session.sensor.frames(t['statement']));rows=[]
                    for i in range(30):
                        row=a.step(frames[i] if i<len(frames) else None,guard=s.guard)
                        row['teacher_utterance']=t['statement'];rows.append(row)
                    E62.record(f,'verbal-feedback',len(attempts)-1,rows)
                f.flush()
                print(json.dumps({'feedback_cycle':cycle+1,'practice_correct':sum(t['correct'] for t in attempts[-8:]),
                                  'n':8,'updates':a.words.steps,'sim_s':a.session.engine.time_us/1e6}),flush=True)
        a.save(p/'system')
        return dict(before=oldsteps,after=a.words.steps,practice_correct=sum(t['correct'] for t in attempts),
                    trials=len(attempts),sim_seconds=a.session.engine.time_us/1e6,
                    teacher_feedback='raw answering window before verbal answer; same personal peripheral')
    return run(s,'centered-feedback',operation)


def calibrate(s):
    """Explicit user-approved instrument calibration, not organism lessons."""
    def operation(p):
        source=WORK/'cases/centered-correction/system'
        count_instance();a=CenteredSystem.restore(source,device());before=a.words.steps
        xs=[];ys=[]
        offsets=((0.,0.),(.008,0.),(-.008,0.),(0.,.008),(0.,-.008),(-.008,.008))
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for index in range(48):
                count_instance();copy=CenteredSystem.restore(source,device(),branch=f'question-calibration-{index}')
                t=task(index%8,offset=offsets[index//8])
                rows,result=lesson(s,copy,t)
                xs.append(question_window(copy,rows));ys.append(t['label'])
                E62.record(f,'calibration-question',index,rows,trial=result)
                del copy
                if (index+1)%8==0:print(json.dumps({'calibration_questions':index+1,'of':48}),flush=True)
        np.savez_compressed(p/'calibration.npz',x=xs,y=ys)
        a.words.readout_profile='whole-question'
        fit=a.words.calibrate(xs,ys,updates=1200,guard=s.guard)
        a.phase='question-calibrated';a.save(p/'system')
        return dict(before=before,after=a.words.steps,fit=fit,core_time_us=a.session.engine.time_us,
                    sampling='16 unchanged raw frames spanning the full question, no subtraction or scaling',
                    note='same peripheral weights/Adam; Core source unchanged during read-only calibration')
    return run(s,'centered-calibration',operation)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('train','evaluate','correct','feedback','calibrate'))
    p.add_argument('--mode',choices=('normal','silence','rescue','blank-core'),default='normal')
    p.add_argument('--corrected',action='store_true')
    p.add_argument('--variant-test',action='store_true',help='Pre-correction copy on the same changed-position test used after correction')
    p.add_argument('--resume-from',type=Path,help='Continue a saved complete individual and exact curriculum cursor')
    p.add_argument('--source-case',help='Explicit completed continuation case for evaluation')
    args=p.parse_args();s=study()
    try:
        if args.command=='train':train(s,args.resume_from)
        elif args.command=='correct':correct(s)
        elif args.command=='feedback':feedback(s)
        elif args.command=='calibrate':calibrate(s)
        else:evaluate(s,args.mode,args.corrected,args.source_case,args.variant_test)
    finally:s.db.close()


if __name__=='__main__':main()
