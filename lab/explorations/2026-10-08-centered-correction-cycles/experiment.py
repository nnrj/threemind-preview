"""E66: registered blank complete subject and bounded teacher-correction cycles."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from lab.tools.service_study import Study, StudyConfig, read_json, new_json, encoded
from lab.tools.recognition_session import RecognitionSystem
from lab.tools.centered_recognition import CenteredWorld, WORDS

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/centered-correction-cycles-20261008'
IDENTITY = 'e66-blank-223'
LIMIT = 1024
INITIAL = ((0.,0.),(-.008,0.),(.008,0.),(0.,.008))
TEACH = ((0.,0.),(-.012,0.),(.012,0.),(0.,-.012),(0.,.012))
CAL = ((.006,-.006),(-.006,.006))
DEV = ((.010,.010),(-.010,-.010))
FINAL = (((.013,-.013),(-.013,.013)), ((.014,-.014),(-.014,.014)),
         ((.016,.012),(-.016,-.012)), ((.018,-.006),(-.018,.006)))
BIRTH_REFERENCE = ROOT/'.work/vision-correction-20261006/cases/r4-teach/protocol.json'

class BoundedStudy(Study):
    def guard(self, force=False):
        super().guard(force)
        if force or not hasattr(self, 'failed_wall'):
            self.failed_wall = sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('*/stopped.json')
                                   if not (p.parent/'result.json').exists())
        active = time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+self.failed_wall+active > self.settings.wall_seconds:
            raise RuntimeError('aggregate compute budget including failed cases')


def study(prepare=False):
    from urllib.parse import urlsplit
    from threemind_lab.config import Settings
    u = urlsplit(Settings.from_env().database_url)
    if u.hostname not in ('127.0.0.1','localhost') or u.port != 5433 or u.path != '/threemind':
        raise ValueError('authorized existing local database only')
    return BoundedStudy(StudyConfig('centered-correction-cycles/1','E66 空白起点中央识别多轮纠错',
        HERE,WORK,24,instance_limit=LIMIT,wall_seconds=10800,storage_soft=4*2**30,
        storage_hard=6*2**30,usage_soft_delta=5,usage_hard_delta=7),prepare=prepare)


def count_instance():
    path = WORK/'instances.json'; n = read_json(path)['created']
    if n >= LIMIT: raise RuntimeError('complete creation/restore limit')
    path.write_bytes(encoded(dict(created=n+1)))


def restore(path):
    count_instance()
    a = RecognitionSystem.restore(path,device())
    if a.identity != IDENTITY: raise ValueError('wrong personal complete source')
    return a


def run(s,key,fn):
    p=WORK/'cases'/key
    if (p/'result.json').exists(): return read_json(p/'result.json')
    if p.exists(): raise RuntimeError('preserve partial case '+key)
    s.allow_extension(); p.mkdir(parents=True); start=time.monotonic()
    s.active_case=SimpleNamespace(born_wall=start)
    new_json(p/'started.json',dict(epoch=time.time(),runner=s.runner_signature))
    try:
        result=fn(p)|dict(wall_seconds=time.monotonic()-start,runner=s.runner_signature)
        new_json(p/'result.json',result); s.active_case=None
        s.completed_count+=1; s.completed_wall+=result['wall_seconds']
        print(encoded(dict(case=key,**result)).decode(),flush=True)
        return result
    except Exception as error:
        new_json(p/'stopped.json',dict(error=str(error),wall_seconds=time.monotonic()-start))
        raise

def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.6)
        return 'cuda'
    return 'cpu'

def task(label, shape=None, color=None, offset=(0., 0.), category='basic'):
    shape = (label if label < 4 else 2) if shape is None else shape
    color = (4 if label < 4 else label-4) if color is None else color
    noun = WORDS[label] if label < 4 else WORDS[label]+'的物体'
    return dict(label=label, shape=shape, color=color, offset=list(offset), category=category,
        attribute='shape' if label < 4 else 'color', pair_id=f'{shape}-{color}',
        statement=f'这是{noun}。', text='这是什么形状？' if label < 4 else '这是什么颜色？')

def record(f, rows, kind, trial=None):
    f.write(encoded(dict(kind=kind, process=rows, text=rows[0].get('teacher_utterance', kind),
                        **({'trial': trial} if trial is not None else {}))).decode()+'\n')

def speak(a, text, ticks, s):
    frames = list(a.session.sensor.frames(text))
    if len(frames) > ticks: raise ValueError('do not truncate a sentence')
    rows = []
    for i in range(ticks):
        row = a.session.tick(frames[i] if i < len(frames) else None, guard=s.guard)
        row['teacher_utterance'] = text
        rows.append(row)
    return rows

def ask(a, t, s):
    a.session.world.present(t['shape'], t['color'], offset=t['offset'])
    a.session.world.marker = None
    rows = speak(a, t['text'], 20, s)
    ids = np.rint(np.linspace(0, len(rows)-1, 8)).astype(int)
    x = np.stack([a.words.layout.frame(rows[i]['activity']) for i in ids])
    # No scene, teacher, label or answer enters this inference call.
    logits = a.words.predict(x[None])[0]
    selected = int(logits.argmax())
    result = t | dict(selected=selected, word=WORDS[selected], correct=selected == t['label'],
                      peripheral_updates=a.words.computed_updates)
    rows[-1]['expression'] = dict(word=WORDS[selected], probabilities=torch.as_tensor(logits).softmax(-1).tolist(),
        identity=a.identity, steps_before=a.words.computed_updates, readout_profile='whole-question')
    return rows, x, result

def tree_equal(a, b):
    if isinstance(a, torch.Tensor): return isinstance(b, torch.Tensor) and torch.equal(a, b)
    if isinstance(a, dict): return a.keys() == b.keys() and all(tree_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)): return len(a) == len(b) and all(tree_equal(x, y) for x, y in zip(a, b))
    return a == b

def type_key(t): return (t['shape'],t['color'],t['label'])


def grid(offset):
    return ([task(i,offset=offset,category='gray-shape') for i in range(4)] +
            [task(label,shape,color,offset,'colored-pair') for shape in range(4)
             for color in range(4) for label in (shape,4+color)])


def bank(name,offsets,seed):
    out=[]
    for side,offset in enumerate(offsets):
        rows=grid(offset)
        order=np.random.default_rng(seed+side).permutation(36)
        out += [rows[int(j)]|dict(split=name,side=side,question_id=f'{name}-{side}-{i}')
                for i,j in enumerate(order)]
    return out


def initial_calibration():
    out=[task(i,offset=o) for i in range(8) for o in INITIAL]
    out += [task(label,shape,color,category='colored-pair') for shape in range(4)
            for color in (shape,(shape+1)%4) for label in (shape,4+color)]
    return [t|dict(split='initial-calibration',question_id=f'initial-calibration-{i}') for i,t in enumerate(out)]


def initial_curriculum():
    out=[]
    for label in range(8):
        for rep in range(10):
            out.append(task(label,offset=INITIAL[rep%4])|dict(operation='initial-teaching',gap_s=0))
    for review,gap in enumerate((0,6,18)):
        for label in range(8):
            out.append(task(label,offset=INITIAL[(10+review)%4])|
                       dict(operation='initial-review',review=review+1,gap_s=gap if label==0 else 0))
    return [t|dict(lesson=i+1) for i,t in enumerate(out)]


def neighbors(t):
    shape,color,label=type_key(t)
    if label<4:
        out=[task(shape,shape,c) for c in range(5) if c!=color]
        out += [task(s,s,color) for s in range(4) if s!=shape]
        if color<4: out.append(task(4+color,shape,color))
    else:
        out=[task(4+color,s,color) for s in range(4) if s!=shape]
        out += [task(4+c,shape,c) for c in range(4) if c!=color]
        out.append(task(shape,shape,color))
    return out


def correction_curriculum(round_index,development,reclassified=()):
    evidence=list(development)+list(reclassified)
    errors=[t for t in evidence if not t['correct']]
    errors=sorted(errors,key=lambda t:(type_key(t),tuple(t['offset']),t['question_id']))
    wrong={type_key(t):t for t in errors}
    similar={type_key(n):n for t in wrong.values() for n in neighbors(t)}
    correct={type_key(t) for t in development if t['correct']}
    all_types={type_key(t):t for t in grid((0.,0.))}
    ordered=list(sorted(wrong))+list(sorted(set(similar)-set(wrong)))
    ordered += sorted(set(all_types)-set(ordered))
    assert set(ordered)==set(all_types) and len(ordered)==36
    out=[]
    for t in errors:
        clean=task(t['label'],t['shape'],t['color'],t['offset'])
        out.append(clean|dict(operation='correct-failed-question',gap_s=0,
            error_source=dict(question_id=t['question_id'],selected=t['selected'],word=t['word'],
                              source_stage=t.get('source_stage'))))
    for key in sorted(wrong):
        for rep in range(3):
            out.append(all_types[key]|dict(operation='target-strengthening',gap_s=0,
                offset=list(TEACH[(round_index+rep)%len(TEACH)]),repetition=rep+1))
    for review,gap in enumerate((0,6,18)):
        for i,key in enumerate(ordered):
            roles=[]
            if key in wrong: roles.append('failed-type')
            if key in similar: roles.append('similar-type')
            if key in correct: roles.append('previously-correct-type')
            out.append(all_types[key]|dict(operation='interleaved-review',review=review+1,
                gap_s=gap if i==0 else 0,offset=list(TEACH[(round_index+review+i)%len(TEACH)]),roles=roles))
    lessons=[t|dict(lesson=i+1) for i,t in enumerate(out)]
    return dict(round=round_index,errors=errors,error_types=[list(k) for k in sorted(wrong)],
        similar_types=[list(k) for k in sorted(similar)],previously_correct_types=[list(k) for k in sorted(correct)],
        lessons=lessons,expected_sim_seconds=sum(t['gap_s']+1.5+(1 if t['operation']=='correct-failed-question' else 0) for t in lessons))


def optical_check():
    world=CenteredWorld(seed=91,toys=False)
    offsets=sorted(set(INITIAL+TEACH+CAL+DEV+tuple(o for pair in FINAL for o in pair)))
    halfsizes=((.14,.14,.14),(.14,.14,.15),(.13,.13,.15),(.14,.14,.15))
    records=[]
    from itertools import product
    for shape,half in enumerate(halfsizes):
        for offset in offsets:
            world.present(shape,4,offset=offset)
            xy=world.positions[0]
            corners=[world.project(np.asarray(xy)+np.array([dx,dy]),z=.16+dz)
                     for dx,dy,dz in product(*[(-v,v) for v in half])]
            maximum=float(np.abs(np.stack(corners)).max())
            if maximum >= world.eye_config.center_half_width: raise AssertionError('object outside clear center')
            records.append(dict(shape=shape,offset=list(offset),max_absolute_uv=maximum))
    return dict(method='conservative projected object bounding-box corners',central_half_width=world.eye_config.center_half_width,
                cases=records,max_absolute_uv=max(r['max_absolute_uv'] for r in records))


def teach(s,key,source,lessons,expected_seconds):
    def op(p):
        if source is None:
            count_instance(); a=RecognitionSystem(device=device(),identity=IDENTITY)
            ref=read_json(WORK/'source-reference/birth-protocol.json')
            if a.session.engine.config.to_dict()!=ref['kernel_config'] or a.session.sensor.config.__dict__!=ref['text']:
                raise ValueError('birth configuration differs from preserved E56')
            if a.session.engine.time_us or a.words.computed_updates: raise AssertionError('not blank')
            a.save(p/'birth')
        else: a=restore(source)
        start=a.session.engine.time_us; timing=[]; answers=[]
        head_before={k:v.detach().clone() for k,v in a.words.state_dict().items()}
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for t in lessons:
                for _ in range(t['gap_s']*20): record(f,[a.session.tick(guard=s.guard)],'interval')
                if t['operation']=='correct-failed-question':
                    began=a.session.engine.time_us
                    rows,_,answer=ask(a,t,s)
                    answer=answer|dict(start_us=began,end_us=a.session.engine.time_us,
                        current_answer_wrong=not answer['correct'],followed_immediately_by_teacher=True)
                    record(f,rows,'student-reanswer',answer); answers.append(answer)
                a.session.world.present(t['shape'],t['color'],offset=t['offset']); a.session.world.marker=None
                began=a.session.engine.time_us
                rows=speak(a,t['statement'],30,s)
                trial=t|dict(start_us=began,end_us=a.session.engine.time_us)
                record(f,rows,t['operation'],trial); timing.append(trial); a.cursor+=1
                if t['lesson']%12==0:
                    print(json.dumps(dict(stage=key,lesson=t['lesson'],of=len(lessons),sim_s=a.session.engine.time_us/1e6)),flush=True)
        if not tree_equal(head_before,a.words.state_dict()): raise AssertionError('teacher changed head weights')
        if a.session.engine.time_us-start != round(expected_seconds*1e6): raise AssertionError('curriculum duration')
        a.phase=key; a.save(p/'system')
        new_json(p/'lesson-timing.json',timing); new_json(p/'student-reanswers.json',answers)
        return dict(identity=a.identity,parent=None if source is None else source.relative_to(WORK).as_posix(),
            lessons=len(timing),corrected_questions=len(answers),wrong_current_reanswers=sum(not r['correct'] for r in answers),
            additional_sim_seconds=expected_seconds,core_time_us=a.session.engine.time_us,
            updates=a.words.computed_updates,peripheral_unchanged_during_teaching=True)
    return run(s,key,op)


def collect(s,key,source,split):
    def op(p):
        xs=[];ys=[];scores=[];frozen=read_json(WORK/'questions.json')[split]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,t in enumerate(frozen):
                a=restore(source); rows,x,result=ask(a,t,s)
                result=result|dict(source_stage=key)
                xs.append(x);ys.append(t['label']);scores.append(result);record(f,rows,key,result)
                del a
                if (i+1)%12==0:
                    print(json.dumps(dict(stage=key,questions=i+1,of=len(frozen),correct=sum(r['correct'] for r in scores))),flush=True)
        np.savez_compressed(p/'features.npz',x=xs,y=ys);new_json(p/'predictions.json',scores)
        return dict(n=len(scores),correct=sum(r['correct'] for r in scores),split=split,
            groups={attr:dict(n=sum(r['attribute']==attr for r in scores),correct=sum(r['attribute']==attr and r['correct'] for r in scores)) for attr in ('shape','color')},
            source=source.relative_to(WORK).as_posix())
    return run(s,key,op)


def fit(s,key,source,corpora):
    def op(p):
        a=restore(source);before=encoded(a.session.snapshot());xs=[];ys=[]
        for name in corpora:
            with np.load(WORK/'cases'/name/'features.npz',allow_pickle=False) as d:
                xs.append(d['x']);ys.append(d['y'])
        result=a.words.calibrate(np.concatenate(xs),np.concatenate(ys),steps=1200,check=s.guard)
        if encoded(a.session.snapshot())!=before: raise AssertionError('calibration changed physical/Core state')
        a.phase=key;a.save(p/'system')
        return result|dict(identity=a.identity,corpora=corpora,core_time_us=a.session.engine.time_us,
            parent=source.relative_to(WORK).as_posix(),physical_core_unchanged_during_calibration=True)
    return run(s,key,op)


def preflight(s):
    def op(p):
        a=restore(WORK/'cases/initial-fit/system');a.save(p/'roundtrip');b=restore(p/'roundtrip')
        if encoded(a.session.snapshot())!=encoded(b.session.snapshot()): raise AssertionError('restore snapshot')
        ra=a.session.tick(guard=s.guard);rb=b.session.tick(guard=s.guard)
        if encoded(ra)!=encoded(rb) or a.session.engine.capture_state().digest!=b.session.engine.capture_state().digest:
            raise AssertionError('next input/activity/Core')
        with np.load(WORK/'cases/initial-calibration/features.npz',allow_pickle=False) as d:
            a.words.calibrate(d['x'],d['y'],steps=1,check=s.guard)
            b.words.calibrate(d['x'],d['y'],steps=1,check=s.guard)
        for x,y in ((a.words.state_dict(),b.words.state_dict()),(a.words.optimizer.state_dict(),b.words.optimizer.state_dict()),(a.words.learning_rng,b.words.learning_rng)):
            if not tree_equal(x,y): raise AssertionError('next weight/Adam/RNG update')
        return dict(next_input_activity_core_equal=True,next_optimizer_update_equal=True,
                    isolated_verification=True,device=str(next(a.words.parameters()).device))
    return run(s,'preflight',op)


def prepare(s,usage):
    if usage!=24: raise ValueError('update registration before preparing if the measured start has changed')
    if not (WORK/'instances.json').exists(): new_json(WORK/'instances.json',dict(created=0))
    (WORK/'usage.json').write_bytes(encoded(dict(used_percent=usage)))
    if not (WORK/'questions.json').exists():
        banks={'initial-calibration':initial_calibration(),'round-calibration':bank('round-calibration',CAL,6601),
               'development':bank('development',DEV,6611)}
        banks.update({f'final-{r}':bank(f'final-{r}',offsets,6621+2*r) for r,offsets in enumerate(FINAL)})
        new_json(WORK/'questions.json',banks);new_json(WORK/'initial-curriculum.json',initial_curriculum())
        new_json(WORK/'optical-verification.json',optical_check())
    dest=WORK/'source-reference';dest.mkdir(exist_ok=True)
    if not (dest/'birth-protocol.json').exists(): shutil.copy2(BIRTH_REFERENCE,dest/'birth-protocol.json')
    files=list((ROOT/'lab/tools').glob('*.py'))+[ROOT/'lab/tools/active_vision_replay.html',
         ROOT/'docs/zh/training-protocol.md',ROOT/'docs/en/training-protocol.md']
    manifest={}
    for path in files:
        target=dest/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists(): shutil.copy2(path,target)
        manifest[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest[BIRTH_REFERENCE.relative_to(ROOT).as_posix()]=hashlib.sha256(BIRTH_REFERENCE.read_bytes()).hexdigest()
    if not (dest/'manifest.json').exists():new_json(dest/'manifest.json',manifest)
    s.guard(True);print(json.dumps(dict(project_id=s.project)),flush=True)


def validate_design():
    assert len(initial_calibration())==48 and len(initial_curriculum())==104
    assert sum(1.5+t['gap_s'] for t in initial_curriculum())==180
    assert len(set(INITIAL+TEACH+CAL+DEV+tuple(o for pair in FINAL for o in pair)))==20
    reserved=set(o for pair in FINAL for o in pair)
    assert len(reserved)==8 and not reserved.intersection(INITIAL+TEACH+CAL+DEV)
    assert not set(CAL).intersection(TEACH+DEV)
    dev=bank('development',DEV,6611)
    assert len(dev)==72 and len({t['question_id'] for t in dev})==72
    assert all(WORDS[t['label']] not in t['text'] for t in dev)
    fake=[t|dict(correct=False,selected=(t['label']+1)%8,word=WORDS[(t['label']+1)%8]) for t in dev]
    course=correction_curriculum(1,fake)
    assert len(course['errors'])==72 and len(course['error_types'])==36
    assert sum(t['operation']=='interleaved-review' for t in course['lessons'])==108
    assert all(len(neighbors(t))>=6 for t in grid((0,0)))
    check=optical_check()
    print(json.dumps(dict(design_verified=True,optical_cases=len(check['cases']),max_absolute_uv=check['max_absolute_uv'])),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('check','prepare','run'));parser.add_argument('--usage',type=int)
    args=parser.parse_args();validate_design()
    if args.command=='check': return
    if args.command=='prepare' and args.usage is None:parser.error('actual usage reading required')
    s=study(args.command=='prepare' and not (WORK/'platform.json').exists())
    try:
        if args.command=='prepare':prepare(s,args.usage);return
        teach(s,'initial-teaching',None,read_json(WORK/'initial-curriculum.json'),180)
        collect(s,'initial-calibration',WORK/'cases/initial-teaching/system','initial-calibration')
        corpora=['initial-calibration'];fit(s,'initial-fit',WORK/'cases/initial-teaching/system',corpora);preflight(s)
        source=WORK/'cases/initial-fit/system';reclassified=[]
        for r in range(4):
            dev=collect(s,f'development-{r}',source,'development')
            if dev['correct']==72 or r==3:
                confirmation=collect(s,f'confirmation-{r}',source,f'final-{r}')
                if confirmation['correct']==72 or r==3:
                    status=dict(completed=True,rounds=r,final_source=source.relative_to(WORK).as_posix(),
                        final_case=f'confirmation-{r}',all_correct=confirmation['correct']==72,
                        development_correct=dev['correct'],confirmation_correct=confirmation['correct'],
                        stop_reason='independent-all-correct' if confirmation['correct']==72 else 'three-round-limit')
                    if not (WORK/'completion.json').exists():new_json(WORK/'completion.json',status)
                    print(encoded(status).decode(),flush=True);break
                reclassified=read_json(WORK/f'cases/confirmation-{r}/predictions.json')
                path=WORK/f'reclassifications/final-{r}.json'
                if not path.exists():new_json(path,dict(original_case=f'confirmation-{r}',reason='used to design next correction',
                    subsequent_status='development-only',next_reserved_bank=f'final-{r+1}'))
            else:reclassified=[]
            rows=read_json(WORK/f'cases/development-{r}/predictions.json')
            course=correction_curriculum(r+1,rows,reclassified);path=WORK/f'curricula/round-{r+1}.json'
            if path.exists():
                if encoded(read_json(path))!=encoded(course):raise AssertionError('frozen curriculum differs')
            else:new_json(path,course)
            teach(s,f'correction-{r+1}',source,course['lessons'],course['expected_sim_seconds'])
            collect(s,f'calibration-{r+1}',WORK/f'cases/correction-{r+1}/system','round-calibration')
            corpora.append(f'calibration-{r+1}')
            fit(s,f'fit-{r+1}',WORK/f'cases/correction-{r+1}/system',list(corpora))
            source=WORK/f'cases/fit-{r+1}/system'
    finally:s.db.close()


if __name__=='__main__':main()
