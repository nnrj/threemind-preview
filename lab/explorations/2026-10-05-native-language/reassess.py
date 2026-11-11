"""Reassess every old calibration route, without re-running or rewriting E45."""
from collections import defaultdict
import json
import numpy as np

from experiment import OLD, HERE, WORK, e45, read_json, new_json


def classify(reference, queries):
    reference=np.asarray(reference);queries=np.asarray(queries)
    nr=np.linalg.norm(reference,axis=1);nq=np.linalg.norm(queries,axis=1)
    scores=queries@reference.T/np.maximum(nq[:,None]*nr[None,:],1e-30)
    result=[]
    for i,row in enumerate(scores):
        order=np.argsort(-row,kind='stable');a,b=order[:2]
        ok=nq[i]>1e-8 and nr[a]>1e-8 and row[a]>0 and row[a]-row[b]>1e-6
        result.append({'prediction':int(a) if ok else None,'scores':row.tolist(),'norm':float(nq[i])})
    return result


def main():
    raw={};rows=[]
    for path in (OLD/'cases').glob('cal-*-default-*-none/result.json'):
        r=read_json(path)
        raw[(r['route'],r['seed'],r['condition'],r['seconds'],r['cue_index'])]=r
    def vectors(route,seed,condition,seconds,modality,cues):
        base=raw[(route,seed,condition,seconds,-1)]['vectors'][modality]['windows']
        return [np.ravel(np.asarray(raw[(route,seed,condition,seconds,c)]['vectors'][modality]['windows'])-base) for c in cues]
    def add(route,seed,condition,seconds,modality,test,ref,query,targets):
        for item,(result,target) in enumerate(zip(classify(ref,query),targets,strict=True)):
            rows.append({'route':route,'seed':seed,'condition':condition,'seconds':seconds,'modality':modality,
                'test':test,'item':item,'target':target,'reading':result,'correct':result['prediction']==target})
    for route in e45.ROUTES:
        for seed in (17,29):
            for condition in ('normal','reversed'):
                for seconds in (266,326):
                    add(route,seed,condition,seconds,'vision','prompt-form',vectors(route,seed,condition,seconds,'vision',(0,2,4,6)),
                        vectors(route,seed,condition,seconds,'vision',(1,3,5,7)),range(4))
                for modality,cues in (('vision',(0,2,4,6)),('words',(8,9,10,11))):
                    add(route,seed,condition,326,modality,'delay',vectors(route,seed,condition,266,modality,cues),
                        vectors(route,seed,condition,326,modality,cues),range(4))
            for seconds in (266,326):
                for modality,cues in (('vision',(0,2,4,6)),('words',(8,9,10,11))):
                    add(route,seed,'normal-to-reversed',seconds,modality,'assignment',vectors(route,seed,'normal',seconds,modality,cues),
                        vectors(route,seed,'reversed',seconds,modality,cues),(3,2,1,0))
    groups=defaultdict(lambda:{'correct':0,'count':0,'unknown':0})
    for row in rows:
        group=groups[(row['route'],row['test'],row['modality'])]
        group['count']+=1;group['correct']+=row['correct'];group['unknown']+=row['reading']['prediction'] is None
    summary=[{'route':k[0],'test':k[1],'modality':k[2]}|v for k,v in groups.items()]
    rank=[]
    for route in e45.ROUTES:
        selected=[r for r in rows if r['route']==route]
        rank.append({'route':route,'correct':sum(r['correct'] for r in selected),'count':len(selected),
            'unknown':sum(r['reading']['prediction'] is None for r in selected),'eligible':route!='stream-reverse'})
    rank.sort(key=lambda r:(not r['eligible'],-r['correct']/r['count'],e45.ROUTES.index(r['route'])))
    result={'rows':rows,'summary':summary,'rank':rank,'old_evidence_unchanged':True}
    new_json(HERE/'route-reassessment.json',result)
    new_json(WORK/'route-selection.json',{'route':rank[0]['route'],'rank':rank,'criterion':'native pattern fraction; fixed route tie-break'})
    print(json.dumps({'rank':rank,'summary':summary},ensure_ascii=False))


if __name__=='__main__':main()
