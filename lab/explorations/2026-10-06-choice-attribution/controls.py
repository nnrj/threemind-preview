"""Predeclared copied-state pathway controls, gated by reliable history reading."""
import argparse
import bisect
import numpy as np
from experiment import (study,Case,WORK,Classroom,old,read_json,new_json,cached,probe,
                        evaluate_frozen,DetailedClassroom,StateImage,encoded)
from threemind_runtime.sensory import TextSensor,TextSensorConfig


def masks_for(image):
    visual=set(DetailedClassroom(91,resolution=4).channels[:256])
    sensor=TextSensor(91,TextSensorConfig(frame_characters=1,frame_interval_us=50000))
    words={sensor.identity(0x100000+i) for i in range(sensor.config.channel_count)}
    channels={int(n['id']):int(n['channel']) for n in image['nodes']}
    def target(e):
        a,b=channels[int(e['source'])],channels[int(e['target'])]
        return a in visual and b in words or b in visual and a in words
    selected=[e for e in image['edges'] if target(e)]
    rest=sorted((float(e['weight']),int(e['source']),int(e['target'])) for e in image['edges'] if not target(e))
    if not selected or len(rest)<len(selected):raise RuntimeError('no count-matched pathway control')
    matches=[];errors=[]
    for edge in sorted(selected,key=lambda e:-e['weight']):
        k=bisect.bisect_left(rest,(float(edge['weight']),-1,-1))
        choices=[i for i in (k-1,k) if 0<=i<len(rest)]
        index=min(choices,key=lambda i:(abs(rest[i][0]-edge['weight']),rest[i][1:]))
        weight,a,b=rest.pop(index);matches.append((a,b));errors.append(abs(weight-edge['weight']))
    return {'target':[(int(e['source']),int(e['target'])) for e in selected],'matched':matches,
       'count':len(selected),'mean_weight_error':float(np.mean(errors)),'max_weight_error':max(errors),
       'method':'descending_target_nearest_available_weight; deterministic ID tie break',
       'limitation':'count matched and approximate weight matching; topology/function not matched'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,choices=(223,279),required=True);a=p.parse_args()
    s=study()
    try:
        score=read_json(WORK/f'cases/B-s{a.seed}-learned-fit/result.json')
        if score['correct']<24:
            print('Below preregistered24/32; no enlarged pathway experiment.');return
        s.allow_extension()
        for h in (0,1):
            source=f'B-s{a.seed}-p1-h{h}-teach';path=WORK/f'masks-s{a.seed}-h{h}.json'
            if not path.exists():new_json(path,masks_for(old.read_gzip(WORK/'cases'/source/'checkpoint.json.gz')['core']))
            masks=read_json(path)
            for mode in ('silence-target','silence-matched','rescue','transfer-target','transfer-matched'):
                if not cached(f'{source}-test-{mode}'):
                    probe(s,source,h,'test',common_key=f'B-s{a.seed}-p1-h0-teach',mode=mode,
                          masks=masks['matched' if mode.endswith('matched') else 'target'],
                          donor=f'B-s{a.seed}-p1-h{1-h}-teach')
        for mode in ('silence-target','silence-matched','rescue','transfer-target','transfer-matched'):
            key=f'B-s{a.seed}-control-score-{mode}'
            if not cached(key):evaluate_frozen(s,a.seed,[f'B-s{a.seed}-p1-h{h}-teach-test-{mode}' for h in (0,1)],key)
    finally:s.db.close()


if __name__=='__main__':main()
