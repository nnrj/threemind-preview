"""E64: audited blank-start centered question/calibration procedure."""
import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from lab.tools.service_study import Study, StudyConfig, read_json, new_json, encoded
from lab.tools.recognition_session import RecognitionSystem
from lab.tools.centered_recognition import WORDS

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/centered-restart-20261008'
OLD = ROOT/'.work/vision-correction-20261006/cases/r4-teach/protocol.json'
OFFSETS = ((0.,0.),(-.008,0.),(.008,0.),(0.,.008))
COMBINATIONS = tuple((s,c) for s in range(4) for c in (s,(s+1)%4))


class BoundedStudy(Study):
    def guard(self, force=False):
        super().guard(force)
        if force or not hasattr(self,'failed_wall'):
            self.failed_wall = sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('*/stopped.json')
                                   if not (p.parent/'result.json').exists())
        active = time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+self.failed_wall+active > self.settings.wall_seconds:
            raise RuntimeError('total compute limit including partial cases')


def study(prepare=False):
    from urllib.parse import urlsplit
    from threemind_lab.config import Settings
    u = urlsplit(Settings.from_env().database_url)
    if u.hostname not in ('127.0.0.1','localhost') or u.port != 5433 or u.path != '/threemind':
        raise ValueError('authorized local DB only')
    return BoundedStudy(StudyConfig('centered-restart/1','E64 空白意识恢复成功校准流程',HERE,WORK,18,
        instance_limit=384,wall_seconds=5400,storage_soft=2*2**30,storage_hard=4*2**30,
        usage_soft_delta=5,usage_hard_delta=6),prepare=prepare)


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.6); return 'cuda'
    return 'cpu'


def count_instance():
    p=WORK/'instances.json'; n=read_json(p)['created']
    if n>=384: raise RuntimeError('creation/restore limit')
    p.write_bytes(encoded({'created':n+1}))


def restore(path):
    count_instance(); return RecognitionSystem.restore(path,device())


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
        print(encoded(dict(case=key,**result)).decode(),flush=True); return result
    except Exception as error:
        new_json(p/'stopped.json',dict(error=str(error),wall_seconds=time.monotonic()-start)); raise


def task(label,shape=None,color=None,offset=(0.,0.),category='basic'):
    shape = (label if label<4 else 2) if shape is None else shape
    color = (4 if label<4 else label-4) if color is None else color
    noun = WORDS[label] if label<4 else WORDS[label]+'的物体'
    return dict(label=label,shape=shape,color=color,offset=list(offset),category=category,
        statement=f'这是{noun}。',text='这是什么形状？' if label<4 else '这是什么颜色？',
        conjunction_calibrated=(shape,color) in COMBINATIONS or (color==4 and label<4) or (shape==2 and label>=4))


def tasks(split):
    out=[]
    if split=='calibration':
        for label in range(8):
            for offset in OFFSETS:
                out.append(task(label,offset=offset,category='shape' if label<4 else 'color'))
        for shape,color in COMBINATIONS:
            out.extend(task(label,shape,color,category='pair') for label in (shape,4+color))
    elif split=='practice':
        out=[task(i,offset=(0.,-.008)) for i in range(8)]
        for shape,color in ((0,1),(3,0)):
            out.extend(task(label,shape,color,(0.,-.008),'pair') for label in (shape,4+color))
    elif split in ('test','confirmation'):
        offset=(.012,-.012) if split=='test' else (-.012,.012)
        out=[task(i,shape=i if i<4 else 0,offset=offset,category='basic-question') for i in range(8)]
        for shape in (1,2,3):
            for color in range(4):
                out.extend(task(label,shape,color,offset,'colored-combination') for label in (shape,4+color))
        order=np.random.default_rng(6401 if split=='test' else 6403).permutation(len(out))
        out=[out[int(i)] for i in order]
    else: raise ValueError('registered split')
    return [row|dict(split=split,question_id=f'{split}-{i}') for i,row in enumerate(out)]


def record(f,rows,*,kind,trial=None):
    f.write(encoded(dict(kind=kind,process=rows,text=rows[0].get('teacher_utterance',kind),
                        **({'trial':trial} if trial is not None else {}))).decode()+'\n')


def speak(a,text,ticks,s):
    frames=list(a.session.sensor.frames(text))
    if len(frames)>ticks: raise ValueError('do not truncate sentence')
    rows=[]
    for i in range(ticks):
        row=a.session.tick(frames[i] if i<len(frames) else None,guard=s.guard)
        row['teacher_utterance']=text; rows.append(row)
    return rows


def window(a,rows,count=8):
    ids=np.rint(np.linspace(0,len(rows)-1,count)).astype(int)
    return np.stack([a.words.layout.frame(rows[i]['activity']) for i in ids])


def ask(a,t,s):
    a.session.world.present(t['shape'],t['color'],offset=t['offset']); a.session.world.marker=None
    rows=speak(a,t['text'],20,s); x=window(a,rows)
    logits=a.words.predict(x[None])[0]; selected=int(logits.argmax())
    probabilities=torch.as_tensor(logits).softmax(-1).numpy().tolist()
    result=t|dict(selected=selected,word=WORDS[selected],correct=selected==t['label'],
                  peripheral_updates=a.words.computed_updates)
    rows[-1]['expression']=dict(word=WORDS[selected],probabilities=probabilities,
        identity=a.identity,steps_before=a.words.computed_updates,readout_profile='whole-question')
    return rows,x,result


def teaching(s):
    def op(p):
        count_instance(); a=RecognitionSystem(device=device())
        expected=read_json(OLD)
        if a.session.engine.config.to_dict()!=expected['kernel_config']:
            raise ValueError('birth kernel differs from preserved E56; stop before stimulation')
        if a.session.sensor.config.__dict__!=expected['text']:
            raise ValueError('text mapping differs from preserved E56')
        a.save(p/'birth'); schedule=[]
        for label in range(8):
            schedule.extend((label,rep,0) for rep in range(10))
        for review in range(3): schedule.extend((label,10+review,review+1) for label in range(8))
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,(label,rep,review) in enumerate(schedule):
                if i in (80,88,96):
                    for _ in range((0,6,18)[review-1]*20):
                        record(f,[a.session.tick(guard=s.guard)],kind='interval')
                t=task(label,offset=OFFSETS[rep%4])
                a.session.world.present(t['shape'],t['color'],offset=t['offset']); a.session.world.marker=None
                rows=speak(a,t['statement'],30,s)
                record(f,rows,kind='teaching',trial=t|dict(rep=rep,review=review))
                a.cursor=i+1
                if (i+1)%16==0:
                    print(json.dumps(dict(stage='blank-teaching',lesson=i+1,of=104,sim_s=a.session.engine.time_us/1e6)),flush=True)
            f.flush()
        a.phase='taught'; a.save(p/'system')
        new_json(p/'schedule.json',schedule)
        return dict(lessons=104,sim_seconds=a.session.engine.time_us/1e6,updates=a.words.computed_updates,
                    identity=a.identity,nodes=len(a.session.engine.observation_nodes()))
    return run(s,'blank-teaching',op)


def collect(s,source,split,key):
    def op(p):
        xs=[];ys=[];results=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,t in enumerate(tasks(split)):
                a=restore(WORK/'cases'/source/'system')
                rows,x,result=ask(a,t,s); xs.append(x);ys.append(t['label']);results.append(result)
                record(f,rows,kind='external-calibration' if split=='calibration' else 'practice',trial=result)
                del a
                if (i+1)%8==0: print(json.dumps(dict(stage=key,questions=i+1,of=len(tasks(split)))),flush=True)
        np.savez_compressed(p/'features.npz',x=xs,y=ys);new_json(p/'predictions.json',results)
        return dict(n=len(ys),correct=sum(t['correct'] for t in results),source=source,split=split)
    return run(s,key,op)


def fit(s,source,corpora,key):
    def op(p):
        a=restore(WORK/'cases'/source/'system');xs=[];ys=[]
        for name in corpora:
            with np.load(WORK/'cases'/name/'features.npz',allow_pickle=False) as d:
                xs.append(d['x']);ys.append(d['y'])
        x,y=np.concatenate(xs),np.concatenate(ys)
        result=a.words.calibrate(x,y,steps=1200,check=s.guard)
        a.phase=key; a.save(p/'system')
        return result|dict(corpora=corpora,identity=a.identity,core_time_us=a.session.engine.time_us)
    return run(s,key,op)


def exposure(s):
    def op(p):
        a=restore(WORK/'cases/first-fit/system')
        errors=[r for r in read_json(WORK/'cases/first-practice/predictions.json') if not r['correct']]
        start=a.session.engine.time_us
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for rep,gap in enumerate((0,0,0,6,18)):
                for _ in range(gap*20):record(f,[a.session.tick(guard=s.guard)],kind='interval')
                for t in errors:
                    rows,_,result=ask(a,t,s)
                    rows.extend(a.session.tick(guard=s.guard) for _ in range(40))
                    record(f,rows,kind='matched-exposure',trial=result|dict(rep=rep))
                print(json.dumps(dict(stage='exposure',round=rep+1,error_items=len(errors),sim_s=a.session.engine.time_us/1e6)),flush=True)
        a.phase='exposed'; a.save(p/'system')
        return dict(errors=len(errors),lessons=5*len(errors),sim_seconds=(a.session.engine.time_us-start)/1e6,
                    peripheral_updates=a.words.computed_updates)
    return run(s,'exposure',op)


def evaluate(s,split='test',mode='normal'):
    def op(p):
        scores=[];xs=[];head=None
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
            for i,t in enumerate(tasks(split)):
                a=restore(WORK/'cases/final-fit/system')
                if mode in ('silence','rescue'):
                    edges=[(e['source'],e['target']) for e in a.session.engine.capture_state().to_dict()['edges']]
                    a.session.engine.intervene(edges=edges,action='silence')
                    if mode=='rescue':a.session.engine.intervene(edges=edges,action='unsilence')
                rows,x,result=ask(a,t,s);xs.append(x);scores.append(result);head=a.words
                record(f,rows,kind='test-'+mode,trial=result)
                if (i+1)%8==0:print(json.dumps(dict(stage=split+'-'+mode,questions=i+1,correct=sum(t['correct'] for t in scores))),flush=True)
                del a
        x=np.array(xs); y=np.array([r['label'] for r in scores])
        zero=head.predict(np.zeros_like(x)).argmax(-1)
        order=np.random.default_rng(6407).permutation(len(x));shuffled=head.predict(x[order]).argmax(-1)
        groups={kind:dict(n=sum((r['label']<4)==(kind=='shape') for r in scores),
                 correct=sum(r['correct'] and (r['label']<4)==(kind=='shape') for r in scores)) for kind in ('shape','color')}
        new_json(p/'predictions.json',scores);np.savez_compressed(p/'features.npz',x=x,y=y)
        new_json(p/'readout-controls.json',dict(zero=zero.tolist(),shuffled=shuffled.tolist(),source_indices=order.tolist()))
        return dict(n=len(scores),correct=sum(r['correct'] for r in scores),groups=groups,
            reliable=sum(r['correct'] for r in scores)>=24 and all(g['correct']>=12 for g in groups.values()),
            zero_correct=int((zero==y).sum()),shuffled_correct=int((shuffled==y).sum()),split=split,mode=mode)
    return run(s,split+'-'+mode,op)


def prepare(s,usage):
    if not (WORK/'instances.json').exists():new_json(WORK/'instances.json',dict(created=0))
    (WORK/'usage.json').write_bytes(encoded(dict(used_percent=usage)))
    if not (WORK/'questions.json').exists():
        new_json(WORK/'questions.json',{split:tasks(split) for split in ('calibration','practice','test','confirmation')})
    sources=[ROOT/'lab/tools'/name for name in ('recognition_session.py','calibrated_activity.py','centered_recognition.py',
        'activity_controller.py','sensorimotor_session.py','active_eye.py','whole_scene_classroom.py',
        'body_playground.py','developmental_world.py','eye_hand_world.py','grounded_classroom.py','shape_color_world.py')]
    sources += [ROOT/'lab/explorations/2026-10-06-vision-correction'/name for name in ('experiment.py','shared.py','report.zh.md')]
    manifest={}
    for path in sources:
        dest=WORK/'source-reference'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copy2(path,dest)
        manifest[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    if not (WORK/'source-reference/manifest.json').exists():new_json(WORK/'source-reference/manifest.json',manifest)
    # Notebook links allow documentation, not arbitrary Python-file routes.
    body=re.sub(r'\[([^\]]+)\]\(([^)]+\.py)\)',r'\1 (`\2`)',(HERE/'audit.md').read_text(encoding='utf-8'))
    s.note('preflight-audit','E64 启动前源码核查',body)
    s.guard(True);print(json.dumps(dict(project_id=s.project)),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('prepare','run','attribution'));p.add_argument('--usage',type=int)
    args=p.parse_args()
    if args.command=='prepare' and args.usage is None:p.error('actual account reading required')
    s=study(args.command=='prepare' and not (WORK/'platform.json').exists())
    try:
        if args.command=='prepare':prepare(s,args.usage);return
        if args.command=='attribution':
            if not all(read_json(WORK/f'cases/{sp}-normal/result.json')['reliable'] for sp in ('test','confirmation')):
                raise RuntimeError('registered reliable-improvement gate not met')
            evaluate(s,'test','silence');evaluate(s,'test','rescue');return
        teaching(s)
        collect(s,'blank-teaching','calibration','first-calibration')
        fit(s,'blank-teaching',['first-calibration'],'first-fit')
        collect(s,'first-fit','practice','first-practice')
        exposure(s)
        collect(s,'exposure','practice','later-calibration')
        fit(s,'exposure',['first-calibration','later-calibration'],'final-fit')
        evaluate(s,'test');evaluate(s,'confirmation')
    finally:s.db.close()


if __name__=='__main__':main()
