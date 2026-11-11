"""Read finished cases once; no fitting, Core stepping or result selection."""
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from lab.tools.service_study import read_json,new_json
from lab.tools.developmental_motor import DevelopmentalMotor
from lab.tools.continuous_motor import recent_window
from lab.tools.centered_recognition import PersonalVocabulary
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/rehearsal-centered-20261007'


def trace(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for line in f:
            record=json.loads(line)
            for row in record['process']:yield row


def main():
    torch.set_num_threads(2)
    cases={p.parent.name:read_json(p) for p in (WORK/'cases').glob('*/result.json')}
    failed={p.parent.name:read_json(p) for p in (WORK/'cases').glob('*/stopped.json')}
    output=dict(schema='threemind.rehearsal-centered-results/1',cases=cases,failures=failed,
                compute_minutes=(sum(r['wall_seconds'] for r in cases.values())+sum(r['wall_seconds'] for k,r in failed.items() if k not in cases))/60,
                instances=read_json(WORK/'instances.json'),motor={},recognition={},teaching={},readout_comparison={},trace_controls={})
    for policy in ('recent','reservoir','representative'):
        c=cases.get('rehearsal-'+policy)
        if not c:continue
        p=WORK/'cases'/('rehearsal-'+policy);m=DevelopmentalMotor.restore(p/'system/motor')
        xs=[];ys=[]
        with gzip.open(p/'process.jsonl.gz','rt',encoding='utf-8') as f:
            for line in f:
                record=json.loads(line)
                if record['phase']!='equal-refresher':continue
                rows=record['process'];indices=[i for i,r in enumerate(rows) if 'supervision_time_us' in r['development']]
                i=indices[-1];xs.append(recent_window(m.layout,rows[:i+1]));ys.append(rows[i]['development']['teacher_pose'])
        with torch.no_grad():pred=np.concatenate([m(torch.tensor(np.stack(xs[i:i+16]))).numpy() for i in range(0,len(xs),16)])
        error=pred-np.array(ys)
        output['motor'][policy]=dict(old_mse_before=c['calibration']['before_old']['mean_squared_pose_error'],
              old_mse_after=c['calibration']['after_old']['mean_squared_pose_error'],
              fresh_teacher_MSE=float(np.mean(error**2)),fresh_teacher_examples=len(xs),updates=c['updates'],
              behavior=cases.get('motor-'+policy+'-normal'),
              note='fixed old cache is common; fresh teacher trajectories are policy-specific closed-loop evidence')
    for name,c in cases.items():
        if not name.startswith('centered-') or not (WORK/'cases'/name/'scores.json').exists():continue
        scores=read_json(WORK/'cases'/name/'scores.json');confusion=np.zeros((8,8),dtype=int)
        for r in scores:
            if r['selected'] is not None:confusion[r['label'],r['selected']]+=1
        output['recognition'][name]=dict(n=len(scores),correct=sum(r['correct'] for r in scores),
            basic_correct=sum(r['correct'] for r in scores if r['category']=='taught-basic'),
            combination_correct=sum(r['correct'] for r in scores if r['category']=='unseen-combination'),
            shape_correct=sum(r['correct'] for r in scores if r['label']<4),
            color_correct=sum(r['correct'] for r in scores if r['label']>=4),confusion=confusion.tolist())
    for name in ('centered-teaching','centered-correction','centered-feedback'):
        path=WORK/'cases'/name/'process.jsonl.gz'
        if name not in cases:continue
        counts={}
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                record=json.loads(line);trial=record.get('trial')
                if not trial:continue
                phase=record['phase'];c=counts.setdefault(phase,dict(n=0,correct=0))
                c['n']+=1;c['correct']+=bool(trial['correct'])
        output['teaching'][name]=counts
    if 'centered-calibrated-normal' in cases:
        old=PersonalVocabulary.restore(WORK/'cases/centered-correction/system/words')
        path=WORK/'cases/centered-calibrated-normal/process.jsonl.gz'
        scores=[]
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                record=json.loads(line);rows=record['process'];trial=record['trial'];label=trial['label']
                indices=np.rint(np.linspace(0,len(rows)-1,16)).astype(int)
                x=np.stack([old.layout.frame(rows[i]['activity']) for i in indices])
                prediction=old.predict(x)
                new_recent=rows[-1]['recent_expression']['probabilities']
                scores.append(dict(expected=label,old_whole=None if prediction is None else int(prediction.argmax()),
                    new_recent=None if new_recent is None else int(np.argmax(new_recent)),new_whole=trial['selected']))
        output['readout_comparison']=dict(n=len(scores),old_recent=cases['centered-corrected-normal']['correct'],
            old_whole=sum(r['expected']==r['old_whole'] for r in scores),
            new_recent=sum(r['expected']==r['new_recent'] for r in scores),
            new_whole=sum(r['expected']==r['new_whole'] for r in scores),rows=scores,
            note='two read-only cross-readings; whole-question-calibrated head is not retrained for recent windows')
    for prefix in ('motor-representative-','motor-reservoir-','centered-','centered-corrected-','centered-calibrated-'):
        normal=WORK/'cases'/(prefix+'normal')/'process.jsonl.gz'
        if not normal.exists():continue
        for mode in ('silence','rescue','blank-core'):
            other=WORK/'cases'/(prefix+mode)/'process.jsonl.gz'
            if not other.exists():continue
            changed=0;count=0;maximum=0.;length_equal=True
            from itertools import zip_longest
            for a,b in zip_longest(trace(normal),trace(other)):
                if a is None or b is None:length_equal=False;continue
                if 'expression' in a:
                    va=a['expression']['probabilities'];vb=b['expression']['probabilities']
                else:va=a['eye_action']+a['hand_action'];vb=b['eye_action']+b['hand_action']
                diff=float(np.max(np.abs(np.array(va)-np.array(vb)))) if va is not None and vb is not None else float(va!=vb)
                changed+=diff>1e-7;maximum=max(maximum,diff);count+=1
            output['trace_controls'][prefix+mode]=dict(frames=count,changed_above_1e_7=int(changed),maximum_difference=maximum,equal_length=length_equal)
    new_json(HERE/'results.json',output)
    print(json.dumps({k:v for k,v in output.items() if k not in ('cases','failures')},ensure_ascii=False))


if __name__=='__main__':main()
