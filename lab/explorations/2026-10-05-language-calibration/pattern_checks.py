"""Post-result registered classification of native patterns, not physical templates."""
from collections import defaultdict

import numpy as np
from experiment import HERE, WORK, read_json

from lab.tools.service_study import new_json


def classify(reference,queries,center):
    reference=np.array(reference);queries=np.array(queries)
    mean=reference.mean(axis=0) if center else np.zeros(reference.shape[1])
    original_ref=np.linalg.norm(reference,axis=1);original_query=np.linalg.norm(queries,axis=1)
    reference=reference-mean;queries=queries-mean
    norms=np.linalg.norm(reference,axis=1);qnorm=np.linalg.norm(queries,axis=1)
    scores=(queries@reference.T)/np.maximum(qnorm[:,None]*norms[None,:],1e-30)
    result=[]
    for i,row in enumerate(scores):
        order=np.argsort(-row);first,second=order[:2]
        valid=original_query[i]>1e-8 and original_ref[first]>1e-8 and norms[first]>1e-8 and qnorm[i]>1e-8
        result.append({'prediction':int(first) if valid and row[first]>0 and row[first]-row[second]>1e-6 else None,
            'scores':row.tolist(),'query_norm':float(original_query[i]),'margin':float(row[first]-row[second])})
    return result


def main():
    raw={};rows=[]
    for path in (WORK/'cases').glob('formal-*-none/result.json'):
        r=read_json(path);raw[(r['seed'],r['condition'],r['seconds'],r['cue_index'])]=r
    def vectors(seed,condition,seconds,direction,cues):
        baseline=raw[(seed,condition,seconds,-1)]['vectors'][direction]['windows']
        return [np.ravel(np.array(raw[(seed,condition,seconds,c)]['vectors'][direction]['windows'])-baseline) for c in cues]
    def add(test,seed,condition,seconds,direction,ref,query,targets):
        for center in (False,True):
            for i,(prediction,target) in enumerate(zip(classify(ref,query,center),targets,strict=True)):
                rows.append({'test':test,'seed':seed,'condition':condition,'seconds':seconds,'direction':direction,
                    'centered':center,'item':i,'target':target,'reading':prediction,'correct':prediction['prediction']==target})
    for seed in (71,89,107):
        for condition in ('normal','reversed','frozen'):
            for seconds in (266,326,566):
                ref=vectors(seed,condition,seconds,'vision',(0,2,4,6))
                query=vectors(seed,condition,seconds,'vision',(1,3,5,7))
                add('name-to-name-is',seed,condition,seconds,'vision',ref,query,range(4))
            for direction,cues in (('vision',(0,2,4,6)),('words',(8,9,10,11))):
                ref=vectors(seed,condition,266,direction,cues)
                for seconds in (326,566):
                    add('across-delay',seed,condition,seconds,direction,ref,vectors(seed,condition,seconds,direction,cues),range(4))
        for seconds in (266,326,566):
            for direction,cues in (('vision',(0,2,4,6)),('words',(8,9,10,11))):
                add('assignment-reversal',seed,'normal-to-reversed',seconds,direction,
                    vectors(seed,'normal',seconds,direction,cues),vectors(seed,'reversed',seconds,direction,cues),(3,2,1,0))
    summary=defaultdict(lambda:{'correct':0,'count':0,'unknown':0})
    for r in rows:
        key=(r['test'],r['direction'],r['condition'],r['centered']);x=summary[key]
        x['correct']+=r['correct'];x['count']+=1;x['unknown']+=r['reading']['prediction'] is None
    result={'posthoc_registered':True,'changes_primary_criteria':False,'rows':rows,
        'summary':[{'test':k[0],'direction':k[1],'condition':k[2],'centered':k[3]}|v for k,v in summary.items()]}
    new_json(HERE/'pattern-results.json',result)
    print(result['summary'])


if __name__=='__main__':main()
