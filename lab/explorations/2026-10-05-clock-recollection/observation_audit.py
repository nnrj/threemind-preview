"""Offline instrument audit, never a replacement answer or inference feature.

Compare the same present/question with different immediately preceding objects.
Report whether local selection discards any state difference, without training
a classifier or subtracting that difference from expression input.
"""
import math
from experiment import *


def vector(raw,selected=None):
    values={}
    for i,frame in enumerate(raw['trajectory']):
        for n in frame['nodes']:
            if selected is not None and n['channel'] not in selected:continue
            for k in FIELDS:values[(i,int(n['channel']),k)]=float(n[k])
    return values


def difference(a,b):
    differences=[abs(a.get(k,0)-b.get(k,0)) for k in a.keys()|b.keys()]
    return {'nonzero_entries':sum(x!=0 for x in differences),'maximum_absolute':max(differences,default=0),
            'l2':math.sqrt(sum(x*x for x in differences))}


def prepared_vector(value):
    return {(i,int(n['channel']),field):amount for i,f in enumerate(value['frames'])
            for n in f['nodes'] for field,amount in zip(value['node_fields'],n['values'])}


def main():
    rows=[read_json(p) for p in (WORK/'cases').glob('*/result.json')]
    result=[]
    for seed in (223,279):
        for learning in (True,False):
            for current in range(4):
                picked=[r for r in rows if r.get('kind')=='probe' and r['seed']==seed and r['learning']==learning
                        and r['current']==current and r['question']=='past' and r['mode']=='normal' and r['split']=='test']
                for i,a in enumerate(picked):
                    for b in picked[i+1:]:
                        raw_a=read_process(a['path']);raw_b=read_process(b['path'])
                        va=local_process(raw_a);vb=local_process(raw_b)
                        ca={n['channel'] for f in va['frames'] for n in f['nodes']};cb={n['channel'] for f in vb['frames'] for n in f['nodes']}
                        result.append({'seed':seed,'learning':learning,'current':current,'pasts':[a['past'],b['past']],
                            'full_dynamic':difference(vector(raw_a),vector(raw_b)),
                            'selected_dense_dynamic':difference(vector(raw_a,ca),vector(raw_b,cb)),
                            'actual_17_frame_input':difference(prepared_vector(va),prepared_vector(vb)),
                            'selected_channels':[len(ca),len(cb)],'all_channels':[len(raw_a['trajectory'][0]['nodes']),len(raw_b['trajectory'][0]['nodes'])]})
    new_json(WORK/'sampled-observation-audit.json',{'purpose':'analysis only; includes actual17-frame reader inputs; not fed as an inference feature','comparisons':result})
    print({'comparisons':len(result),'local_identical':sum(r['selected_dense_dynamic']['nonzero_entries']==0 for r in result),
           'full_identical':sum(r['full_dynamic']['nonzero_entries']==0 for r in result)},flush=True)


if __name__=='__main__':main()
