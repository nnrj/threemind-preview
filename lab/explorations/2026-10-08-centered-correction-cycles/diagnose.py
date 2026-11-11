"""Reproduce the read-only cube/cylinder comparison from E66 confirmation 1."""
import gzip
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BASE=ROOT/'.work/centered-correction-cycles-20261008/cases/confirmation-1'


def measure():
    rows=json.loads((BASE/'predictions.json').read_bytes())
    with np.load(BASE/'features.npz',allow_pickle=False) as d:x=d['x']
    pairs=[];ids=set()
    for i,t in enumerate(rows):
        if t['correct']:continue
        if t['shape']!=2 or t['label']!=2:raise ValueError('this diagnostic is scoped to the recorded cube-shape failures')
        j=next(j for j,u in enumerate(rows) if u['side']==t['side'] and u['color']==t['color'] and u['label']==1 and u['shape']==1)
        pairs.append((i,j));ids.update((t['question_id'],rows[j]['question_id']))
    records={}
    with gzip.open(BASE/'process.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);qid=row['trial']['question_id']
            if qid in ids:records[qid]=row['process']
    retina=lambda frames:np.asarray([r['observation']['values'][:4*len(r['observation']['retinal_centers'])] for r in frames])
    out=[]
    for i,j in pairs:
        a,b=rows[i],rows[j];av,bv=(retina(records[r['question_id']]) for r in (a,b))
        vd=np.abs(av-bv);ad=np.abs(x[i]-x[j])
        out.append(dict(failed_question=a['question_id'],shape=a['shape'],color=a['color'],offset=a['offset'],answer=a['word'],
            comparison_question=b['question_id'],comparison_shape=b['shape'],comparison_correct=b['correct'],
            retinal_values_equal=bool(np.array_equal(av,bv)),retinal_different_values=int(np.count_nonzero(vd)),
            retinal_max_absolute_difference=float(vd.max()),raw_activity_equal=bool(np.array_equal(x[i],x[j])),
            activity_different_values=int(np.count_nonzero(ad)),activity_max_absolute_difference=float(ad.max()),
            activity_l2_difference=float(np.linalg.norm(ad))))
    return out


if __name__=='__main__':
    measured=measure()
    saved=json.loads((HERE/'recorded-shape-differences.json').read_bytes())
    if measured!=saved['comparisons']:raise AssertionError('saved read-only comparison differs')
    print(json.dumps(dict(reproduced=True,comparisons=measured),ensure_ascii=False))
