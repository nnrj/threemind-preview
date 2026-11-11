"""Later-registered development retention check; no fitting or Core intervention."""
import gzip
import importlib.util
import json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('e66_registered',HERE/'experiment.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


def tasks():
    selected={}
    for file in sorted((e.WORK/'reclassifications').glob('*.json')):
        meta=e.read_json(file);bank=e.read_json(e.WORK/'cases'/meta['original_case']/'predictions.json')
        for old in bank:
            if old['correct']:continue
            own=dict(old)
            if old['attribute']=='shape':
                shape=old['selected'] if old['selected']<4 else (old['shape']+1)%4
                other=next(t for t in bank if t['side']==old['side'] and t['color']==old['color'] and t['shape']==shape and t['attribute']=='shape')
            else:
                color=old['selected']-4 if old['selected']>=4 else (old['color']+1)%4
                other=next(t for t in bank if t['side']==old['side'] and t['shape']==old['shape'] and t['color']==color and t['attribute']=='color')
            for item,role in ((own,'previous-error'),(other,'confusable-contrast')):
                key=item['question_id']
                if key not in selected:selected[key]=dict(item)|dict(retention_roles=[],original_correct=item['correct'],original_selected=item['selected'],original_word=item['word'])
                if role not in selected[key]['retention_roles']:selected[key]['retention_roles'].append(role)
    return [selected[k] for k in sorted(selected)]


def main():
    completion=e.read_json(e.WORK/'completion.json')
    rows=tasks()
    if not rows:raise RuntimeError('no reclassified questions to review')
    if len(rows)>24:raise RuntimeError('complete supplement exceeds registered cap; do not select favorable items')
    path=e.WORK/'retention-questions.json'
    if path.exists():
        if e.encoded(e.read_json(path))!=e.encoded(rows):raise AssertionError('frozen retention bank changed')
    else:e.new_json(path,rows)
    s=e.study()
    try:
        def op(p):
            scores=[];xs=[];ys=[]
            with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as f:
                for t in rows:
                    a=e.restore(e.WORK/completion['final_source']);process,x,result=e.ask(a,t,s)
                    result=result|dict(source_stage='retention-retest');scores.append(result);xs.append(x);ys.append(t['label'])
                    e.record(f,process,'retention-retest',result);del a
            np.savez_compressed(p/'features.npz',x=xs,y=ys);e.new_json(p/'predictions.json',scores)
            return dict(n=len(scores),correct=sum(t['correct'] for t in scores),source=completion['final_source'],
                diagnostic='later-registered development retention; no training or final-test reuse',
                groups={role:dict(n=sum(role in t['retention_roles'] for t in scores),
                    correct=sum(role in t['retention_roles'] and t['correct'] for t in scores),
                    original_correct=sum(role in t['retention_roles'] and t['original_correct'] for t in scores)) for role in ('previous-error','confusable-contrast')})
        e.run(s,'retention-retest',op)
    finally:s.db.close()


if __name__=='__main__':main()
