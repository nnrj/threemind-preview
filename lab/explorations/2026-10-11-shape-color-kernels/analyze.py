"""Observational E67 scoring, paired changes, exposure and performance audit."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

ARMS = ('2','3.1')
TESTS = ['development-'+str(r) for r in range(4)]+['final']
WORDS = ('球体','圆柱体','立方体','圆锥体','红色','黄色','蓝色','绿色')


def read(path):return json.loads(Path(path).read_bytes())


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def transition(before,after):
    left={r['question_id']:r for r in before};right={r['question_id']:r for r in after}
    if left.keys()!=right.keys():raise ValueError('unpaired questions')
    result={k:[] for k in ('right_right','wrong_right','right_wrong','wrong_wrong')}
    for key,a in left.items():
        b=right[key];name=('right' if a['correct'] else 'wrong')+'_'+('right' if b['correct'] else 'wrong')
        result[name].append(key)
    return {'counts':{k:len(v) for k,v in result.items()},'question_ids':result}


def confusion(rows):
    matrix=[[0]*8 for _ in range(8)]
    for row in rows:matrix[row['label']][row['selected']]+=1
    return matrix


def paired_questions(stage, questions):
    """Human-readable comparison, validating the paired question definitions."""
    grouped={arm:{q['question_id']:q for q in questions[arm]} for arm in ARMS}
    left,right=(grouped[arm] for arm in ARMS)
    if left.keys()!=right.keys():raise ValueError('unpaired question table')
    rows=[]
    for key,a in left.items():
        b=right[key]
        if any(a[k]!=b[k] for k in ('shape','color','label','offset','attribute')):
            raise ValueError('question definitions differ: '+key)
        rows.append(dict(stage=stage,question_id=key,shape=WORDS[a['shape']],
            color=WORDS[4+a['color']] if a['color']<4 else '灰色',
            attribute=a['attribute'],x=a['offset'][0],y=a['offset'][1],expected=WORDS[a['label']],
            answer_2=WORDS[a['selected']],correct_2=a['correct'],
            answer_31=WORDS[b['selected']],correct_31=b['correct']))
    return rows


def exact_conflicts(items):
    groups={}
    for item in items:groups.setdefault(item['sha256'],[]).append(item)
    conflicts=[];upper=0
    for digest,rows in groups.items():
        counts={}
        for row in rows:counts[row['label']]=counts.get(row['label'],0)+1
        upper+=max(counts.values())
        if len(counts)>1:conflicts.append(dict(sha256=digest,questions=rows))
    return dict(questions=len(items),conflicts=conflicts,deterministic_exact_input_upper_bound=upper)


def representation_audit(folder, questions):
    """Exact contradictions in same-source question inputs/features, not an ablation."""
    import numpy as np
    inputs=[];features=[]
    for i,q in enumerate(questions):
        clip=read_gzip(folder/'clips'/f'{i:06d}.json.gz')
        if clip['trial']['question_id']!=q['question_id']:raise ValueError('question clip order differs')
        h=hashlib.sha256()
        for frame in clip['process']:h.update(encoded(frame['stimulus']));h.update(b'\n')
        inputs.append(dict(question_id=q['question_id'],label=q['label'],sha256=h.hexdigest()))
        with np.load(folder/'trials'/f'{i:04d}.npz',allow_pickle=False) as data:x=data['x']
        if not np.isfinite(x).all():raise ValueError('nonfinite saved activity')
        digest=hashlib.sha256(encoded(dict(dtype=x.dtype.str,shape=list(x.shape)))+x.tobytes()).hexdigest()
        features.append(dict(question_id=q['question_id'],label=q['label'],sha256=digest))
    return dict(recorded_input_sequences=exact_conflicts(inputs),reader_activity_windows=exact_conflicts(features),
        interpretation='Only exact byte-equivalent cross-label contradictions are checked. Distinct signals need not be easy for this reader to separate. No simulation or learning was executed.')


def read_gzip(path):return json.loads(gzip.decompress(path.read_bytes()))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--audit-inputs',action='store_true');args=p.parse_args();work=args.work.resolve()
    if not (work/'computation-complete.json').exists():raise ValueError('registered computation is incomplete')
    complete=read(work/'computation-complete.json')
    if complete['arms']!=list(ARMS):raise ValueError('completed arms do not match the analysis scope')
    result={'schema':'threemind.e67-analysis/1','arms':{},'input_audit':{},'deferred_arms':complete['deferred_arms'],
            'scope':'two completed arms; one paired training seed; final questions are not independent training replicates'}
    original_bytes=0;all_questions={}
    for arm in ARMS:
        base=work/'arms'/arm
        stages={f.parent.name:read(f) for f in base.glob('*/result.json')}
        timing={}
        for stage in stages.values():
            for key,value in stage['timing'].items():timing[key]=timing.get(key,0)+value
        primary=[stages['initial-teaching'],*[stages[f'correction-{r}'] for r in range(1,4)]]
        questions={name:read(base/name/'predictions.json') for name in TESTS}
        all_questions[arm]=questions
        final=questions['final']
        row=dict(scores={name:{k:stages[name][k] for k in ('n','correct','shape','color','pairs')} for name in TESTS},
            transitions={str(r):transition(questions[f'development-{r-1}'],questions[f'development-{r}']) for r in range(1,4)},
            final_errors=[r for r in final if not r['correct']],final_confusion=confusion(final),
            teaching_lessons=sum(s['lessons'] for s in primary),teaching_sim_s=sum(s['sim_s'] for s in primary),
            wall_s=sum(s['wall_seconds'] for s in stages.values()),
            core_advance_s=timing.get('core_ns',0)/1e9,core_inject_s=timing.get('core_inject_ns',0)/1e9,
            timing=timing,stages=stages,
            bytes=sum(f.stat().st_size for f in base.rglob('*') if f.is_file()))
        row['scored_question_sim_s']=sum(stages[name]['sim_s'] for name in TESTS)
        row['all_advanced_sim_s']=sum(s.get('sim_s',0) for s in stages.values())
        row['core_seconds_per_sim_second']=row['core_advance_s']/row['all_advanced_sim_s']
        row['teaching_core_s']=sum(s['timing'].get('core_ns',0)/1e9 for s in primary)
        row['final_core_ms_per_question']=stages['final']['timing'].get('core_ns',0)/1e6/len(final)
        row['restore_s']=timing.get('restore_ns',0)/1e9
        row['restore_calls']=timing.get('restore_calls',0)
        row['source_graph']=stages['correction-3']['metrics']
        reanswers=[read(base/f'correction-{r}'/'student-reanswers.json') for r in range(1,4)]
        row['teacher_reanswers']=sum(len(r) for r in reanswers)
        row['current_wrong_reanswers']=sum(not t['correct'] for r in reanswers for t in r)
        row['reanswer_rounds']=[{'n':len(r),'currently_wrong':sum(not t['correct'] for t in r)} for r in reanswers]
        row['representation_audit']={name:representation_audit(base/name,questions[name]) for name in TESTS}
        result['arms'][arm]=row;original_bytes+=row['bytes']
        if args.audit_inputs:
            input_audit={};teaching_times={};condition_times={}
            order=['initial-teaching',*[f'correction-{r}' for r in range(1,4)]]
            for folder in sorted(base.iterdir(),key=lambda f:(order.index(f.name) if f.name in order else len(order),f.name)):
                paths=sorted((folder/'clips').glob('*.json.gz'))
                if not paths:continue
                h=hashlib.sha256();count=0
                for path in paths:
                    raw=json.loads(gzip.decompress(path.read_bytes()))
                    if raw['kind']=='teaching':
                        trial=raw['trial'];label=str(trial['label'])
                        condition=f"{trial['shape']}:{trial['color']}:{trial['label']}"
                        when=trial['start_us']/1e6
                        teaching_times.setdefault(label,[]).append(when)
                        condition_times.setdefault(condition,[]).append(when)
                    for frame in raw['process']:
                        h.update(encoded(frame['stimulus']));h.update(b'\n');count+=1
                input_audit[folder.name]={'sha256':h.hexdigest(),'frames':count}
            result['input_audit'][arm]=input_audit
            def intervals(values):
                return {key:{'count':len(times),'sim_s':times,
                             'intervals_s':[b-a for a,b in zip(times,times[1:])]} for key,times in values.items()}
            row['teaching_intervals_by_word']=intervals(teaching_times)
            row['teaching_intervals_by_object_attribute']=intervals(condition_times)
        print(json.dumps({'analyzed':arm,'final':row['scores']['final'],'core_s':row['core_advance_s']}),flush=True)
    final_rows={arm:read(work/'arms'/arm/'final/predictions.json') for arm in ARMS}
    result['paired_final']={left+'__'+right:transition(final_rows[left],final_rows[right])
        for i,left in enumerate(ARMS) for right in ARMS[i+1:]}
    assert len({r['teaching_lessons'] for r in result['arms'].values()})==1
    assert len({r['teaching_sim_s'] for r in result['arms'].values()})==1
    if args.audit_inputs:
        reference=result['input_audit'][ARMS[0]]
        result['matched_input_sequences']=all(v==reference for v in result['input_audit'].values())
        if not result['matched_input_sequences']:raise ValueError('actual recorded inputs differ between arms')
    result['arm_original_bytes']=original_bytes
    out=work/'analysis';out.mkdir(exist_ok=True)
    table=[]
    for name in TESTS:
        table.extend(paired_questions(name,{arm:all_questions[arm][name] for arm in ARMS}))
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    table_path=out/'paired-question-scores.csv';table_bytes=stream.getvalue().encode('utf-8-sig')
    if table_path.exists() and table_path.read_bytes()!=table_bytes:raise ValueError('immutable question table differs')
    table_path.write_bytes(table_bytes)
    result['question_table']=table_path.relative_to(work).as_posix()
    dest=out/('verified-results.json' if args.audit_inputs else 'results.json')
    value=json.dumps(result,ensure_ascii=False,indent=2)
    if dest.exists() and dest.read_text(encoding='utf-8')!=value:raise ValueError('immutable analysis differs')
    dest.write_text(value,encoding='utf-8')
    summary={arm:{k:r[k] for k in ('scores','teaching_lessons','teaching_sim_s','wall_s',
        'core_advance_s','core_seconds_per_sim_second','final_core_ms_per_question','restore_s','bytes')}
        for arm,r in result['arms'].items()}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
