"""E66 read-only results, feedback and complete-state audit; never simulate or fit."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from lab.tools.service_study import read_json,new_json,encoded
from lab.tools.calibrated_activity import CalibratedActivity
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/centered-correction-cycles-20261008'


def counts(rows):return dict(n=len(rows),correct=sum(r['correct'] for r in rows))
def kind(r):return (r['shape'],r['color'],r['label'])


def score(rows):
    confusion=[[0]*8 for _ in range(8)]
    pairs={}
    for r in rows:
        assert r['correct']==(r['label']==r['selected'])
        confusion[r['label']][r['selected']]+=1
        if r['color']<4:pairs.setdefault((r['side'],r['pair_id']),[]).append(r)
    assert len(pairs)==32 and all(len(v)==2 and {r['attribute'] for r in v}=={'shape','color'} for v in pairs.values())
    categories={name:counts([r for r in rows if keep(r)]) for name,keep in {
        'shape':lambda r:r['attribute']=='shape','color':lambda r:r['attribute']=='color',
        'gray_shape':lambda r:r['color']==4,'colored_shape':lambda r:r['color']<4 and r['attribute']=='shape'}.items()}
    sides={str(side):counts([r for r in rows if r['side']==side])|dict(
        shape=counts([r for r in rows if r['side']==side and r['attribute']=='shape']),
        color=counts([r for r in rows if r['side']==side and r['attribute']=='color']),
        combinations=dict(n=16,correct=sum(all(t['correct'] for t in v) for k,v in pairs.items() if k[0]==side))) for side in (0,1)}
    return counts(rows)|categories|dict(sides=sides,combinations=dict(n=32,correct=sum(all(t['correct'] for t in v) for v in pairs.values())),
        confusion=confusion,wrong=[r for r in rows if not r['correct']])


def paired(before,after):
    bm={r['question_id']:r for r in before};am={r['question_id']:r for r in after};assert bm.keys()==am.keys()
    return dict(n=len(am),changed=sum(am[k]['selected']!=bm[k]['selected'] for k in bm),
        wrong_to_correct=sum(not bm[k]['correct'] and am[k]['correct'] for k in bm),
        correct_to_wrong=sum(bm[k]['correct'] and not am[k]['correct'] for k in bm),
        remained_wrong=sum(not bm[k]['correct'] and not am[k]['correct'] for k in bm),
        remained_correct=sum(bm[k]['correct'] and am[k]['correct'] for k in bm))


def whole(path):
    with gzip.open(path/'system.json.gz','rt',encoding='utf-8') as f:return json.load(f)


def main():
    completion=read_json(WORK/'completion.json');rounds=completion['rounds']
    cases={p.parent.name:read_json(p) for p in (WORK/'cases').glob('*/result.json')}
    failures={p.parent.name:read_json(p) for p in (WORK/'cases').glob('*/stopped.json')}
    expected={'initial-teaching','initial-calibration','initial-fit','preflight'}
    expected|={f'development-{i}' for i in range(rounds+1)}
    expected|={f'{phase}-{i}' for i in range(1,rounds+1) for phase in ('correction','calibration','fit')}
    assert expected.issubset(cases) and completion['final_case'] in cases
    answers={name:read_json(WORK/f'cases/{name}/predictions.json') for name in cases if name.startswith(('development-','confirmation-'))}
    scores={name:score(rows) for name,rows in answers.items()}
    transitions={};teaching={};intervals={};state_audit={}
    physical=('identity','cursor','session','current','history','published','sensor','layout')
    for key in ['initial-fit']+[f'fit-{i}' for i in range(1,rounds+1)]:
        c=cases[key];a=whole(WORK/c['parent']);b=whole(WORK/f'cases/{key}/system')
        ok=all(encoded(a[k])==encoded(b[k]) for k in physical);assert ok
        state_audit[key]=dict(all_physical_core_recent_state_unchanged=True)
    for key in ['initial-teaching']+[f'correction-{i}' for i in range(1,rounds+1)]:
        c=cases[key];parent=WORK/c['parent'] if c['parent'] else WORK/f'cases/{key}/birth'
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        assert sha(parent/'words/model.safetensors')==sha(WORK/f'cases/{key}/system/words/model.safetensors')
        lessons=read_json(WORK/f'cases/{key}/lesson-timing.json')
        reanswers=read_json(WORK/f'cases/{key}/student-reanswers.json')
        assert all(t['end_us']-t['start_us']==1500000 for t in lessons)
        assert all(t['end_us']-t['start_us']==1000000 for t in reanswers)
        lesson_by_id={t['lesson']:t for t in lessons}
        assert all(lesson_by_id[r['lesson']]['start_us']==r['end_us'] for r in reanswers)
        teaching[key]=dict(lessons=len(lessons),feedback_events=len(reanswers),
            current_reanswers=counts(reanswers),previous_error_source_retained=all('error_source' in r for r in reanswers),
            immediate_correct_teacher_feedback=len(reanswers),peripheral_weights_unchanged=True)
        for scope,fn in [('concept',lambda r:str(r['label'])),('object_attribute',lambda r:'-'.join(map(str,kind(r))))]:
            grouped={}
            for t in lessons:grouped.setdefault(fn(t),[]).append(t)
            intervals.setdefault(key,{})[scope]={k:dict(lessons=[t['lesson'] for t in v],starts_us=[t['start_us'] for t in v],
                end_to_next_start_s=[(b['start_us']-a['end_us'])/1e6 for a,b in zip(v,v[1:])]) for k,v in grouped.items()}
    for i in range(1,rounds+1):
        before=answers[f'development-{i-1}'];after=answers[f'development-{i}']
        course=read_json(WORK/f'curricula/round-{i}.json');wrong={tuple(k) for k in course['error_types']};similar={tuple(k) for k in course['similar_types']}
        transitions[str(i)]=paired(before,after)|dict(error_types=len(wrong),similar_types=len(similar),
            targeted_types_before=counts([r for r in before if kind(r) in wrong]),targeted_types_after=counts([r for r in after if kind(r) in wrong]),
            similar_excluding_targets_before=counts([r for r in before if kind(r) in similar-wrong]),
            similar_excluding_targets_after=counts([r for r in after if kind(r) in similar-wrong]))
        assert teaching[f'correction-{i}']['feedback_events']==len(course['errors'])
    frames={};raw_records={};actuator_max=0.;feedback_pairs=0
    for path in sorted((WORK/'cases').glob('*/process.jsonl.gz')):
        n=c=0;previous=None
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                row=json.loads(line);c+=1
                if previous and previous['kind']=='student-reanswer':
                    assert row['kind']=='correct-failed-question'
                    assert row['trial']['lesson']==previous['trial']['lesson']
                    assert row['trial']['label']==previous['trial']['label']
                    assert row['process'][0]['teacher_utterance']==row['trial']['statement']
                    feedback_pairs+=1
                previous=row
                for fr in row['process']:
                    n+=1;ob=fr['observation'];assert ob['schema']=='threemind.centered-observation/1' and ob['teacher_marker'] is None
                    actuator_max=max(actuator_max,*(abs(v) for k in ('eye_action','hand_action') for v in fr[k]))
        if 'additional_sim_seconds' in cases[path.parent.name]:expected_frames=round(cases[path.parent.name]['additional_sim_seconds']*20)
        else:expected_frames=cases[path.parent.name]['n']*20
        assert n==expected_frames,(path,n,expected_frames)
        frames[path.parent.name]=n;raw_records[path.parent.name]=c
    assert actuator_max==0 and feedback_pairs==sum(v['feedback_events'] for v in teaching.values())
    torch.set_num_threads(2)
    final=WORK/completion['final_source'];head=CalibratedActivity.restore(final/'words','cpu')
    corpora=cases[Path(completion['final_source']).parent.name]['corpora'];calibration={}
    for name in corpora:
        with np.load(WORK/f'cases/{name}/features.npz',allow_pickle=False) as d:
            x,y=d['x'],d['y'];pred=head.predict(x).argmax(-1)
            calibration[name]=dict(n=len(y),correct=int((pred==y).sum()),
                shape=dict(n=int((y<4).sum()),correct=int(((y<4)&(pred==y)).sum())),
                color=dict(n=int((y>=4).sum()),correct=int(((y>=4)&(pred==y)).sum())))
    bank=read_json(WORK/'questions.json');final_offsets={tuple(t['offset']) for t in bank[f'final-{rounds}']}
    used=[]
    for path in (WORK/'cases').glob('*/lesson-timing.json'):used+=read_json(path)
    for name in corpora:used+=read_json(WORK/f'cases/{name}/predictions.json')
    assert not final_offsets.intersection(tuple(t['offset']) for t in used)
    birth=read_json(WORK/'cases/initial-teaching/birth/complete.json');assert birth['time_us']==0 and birth['updates']==0
    ref=WORK/'source-reference/birth-protocol.json';source=ROOT/'.work/vision-correction-20261006/cases/r4-teach/protocol.json'
    assert ref.read_bytes()==source.read_bytes()
    result=dict(schema='threemind.centered-correction-results/1',completion=completion,cases=cases,failures=failures,
        scores=scores,transitions=transitions,retention_retest=cases.get('retention-retest'),baseline_to_final_development=paired(answers['development-0'],answers[f'development-{rounds}']),
        teaching=teaching,continuity=state_audit,final_calibration_readability=calibration,
        process_audit=dict(frames=frames,total_frames=sum(frames.values()),raw_records=raw_records,
            max_actuator_command=actuator_max,verified_immediate_feedback_pairs=feedback_pairs),
        compute_minutes=(sum(c['wall_seconds'] for c in cases.values())+sum(c['wall_seconds'] for k,c in failures.items() if k not in cases))/60,
        instances=read_json(WORK/'instances.json'),independent_training_sources=1,
        final_positions_absent_from_teaching_calibration=True,blank_birth=True)
    new_json(HERE/'teaching-intervals.json',intervals);new_json(HERE/'results.json',result)
    for name,row in scores.items():print(json.dumps(dict(case=name,**{k:v for k,v in row.items() if k not in ('confusion','wrong')}),ensure_ascii=False))
    print(json.dumps(dict(compute_minutes=result['compute_minutes'],instances=result['instances'],transitions=transitions,teaching=teaching,
        final_calibration_readability=calibration,total_frames=sum(frames.values())),ensure_ascii=False))


if __name__=='__main__':main()
