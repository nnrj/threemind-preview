"""Explicit secondary analyses of unprompted behavior and full texture activity."""
import json
from analyze import rows,area,save
from experiment import SEEDS,PROTOCOLS

def integrated_vector(a,b):
    keys={n['id'] for r in a+b for n in r['nodes']}
    def get(r,key):return next((n['activation'] for n in r['nodes'] if n['id']==key),0)
    return {k:area(a,lambda r:get(r,k))-area(b,lambda r:get(r,k)) for k in keys}

def main():
    unprompted=[];textures=[];sequence=[]
    for seed in SEEDS:
        for protocol in PROTOCOLS:
            for age in (1,30,300):
                a=rows(f'memory-probe/s{seed}/{protocol}/age{age}/live/normal/none')
                b=rows(f'memory-probe/s{seed}/none/age{age}/live/normal/none')
                mapping={r['relative_us']:r for r in b}
                unprompted.append({'seed':seed,'protocol':protocol,'age_s':age,
                    'no_cue_motor_mae_5_15':area(a,lambda r:abs(r['control']-mapping[r['relative_us']]['control']),5_000_000,15_000_000)/10})
        for cond in ('intact','erase','matched_erase','novelty_off'):
            vectors=[]
            for i in range(4):
                base=f'novelty-probe/s{seed}/{cond}/round{i}'
                vector=integrated_vector(rows(base+'/fixed'),rows(base+'/none'));vectors.append(vector)
                original=vectors[0];previous=vectors[max(0,i-1)]
                dist=lambda other:sum(abs(vector.get(k,0)-other.get(k,0)) for k in set(vector)|set(other))
                textures.append({'seed':seed,'condition':cond,'round':i,'fixed_response_vector':vector,
                    'l1_from_first':dist(original),'l1_from_previous':dist(previous)})
    out={'kind':'secondary, no thresholds changed','unprompted':unprompted,'texture_vectors':textures}
    save('secondary-analysis.json',out)
    print(json.dumps({'max_unprompted_mae_at30':max(r['no_cue_motor_mae_5_15'] for r in unprompted if r['age_s']==30),
        'textures':[{k:v for k,v in r.items() if k!='fixed_response_vector'} for r in textures]}),flush=True)

if __name__=='__main__':main()
