"""Read recorded eye/hand activity without advancing or altering a Core.

Association/eye-motion correlation is descriptive, never a causal classifier.
Task coordinates are used only for offline optical coverage measurements.
"""
import argparse
import gzip
import json
from pathlib import Path
import numpy as np


def correlation(a,b):
    a,b=np.asarray(a),np.asarray(b)
    if len(a)<3 or np.std(a)<1e-12 or np.std(b)<1e-12:return None
    return float(np.corrcoef(a,b)[0,1])


def describe(rows,task=None):
    times=[];speeds=[];association=[];direct=[];activation=[];distances=[];coverage=[]
    for row in rows:
        ob=row['observation'];camera=ob['camera'];nodes=row['activity']['nodes']
        times.append(float(ob['time_s']));speeds.append(float(np.linalg.norm(ob['eye_velocity_rad_s'])))
        association.append(sum(float(n['associative']) for n in nodes))
        direct.append(sum(float(n['direct']) for n in nodes));activation.append(sum(float(n['activation']) for n in nodes))
        origin=np.array(camera['origin_m']);f=np.array(camera['forward'])
        point=origin+(.16-origin[2])/f[2]*f
        distances.append(float(np.linalg.norm(point[:2]-[ob['pointer']['x'],ob['pointer']['y']])))
        if task:
            p=np.array([*task['positions'][task['slot']],.16])-origin
            uv=np.array([p@camera['right'],p@camera['up']])/(p@f)
            h=ob['eye_config']['center_half_width'];a=ob['eye_config']['aperture']
            coverage.append({'central':bool(np.max(np.abs(uv))<=h),'field':bool(np.max(np.abs(uv))<=a)})
    if len(times)<2:raise ValueError('at least two actual recorded samples')
    dt=float(np.median(np.diff(times)))
    if dt<=0 or not np.allclose(np.diff(times),dt,atol=1e-7):raise ValueError('one uninterrupted uniform sampled segment')
    lead={}
    for seconds in (-.5,0.,.5):
        k=int(round(seconds/dt))
        a,b=(speeds[:-k],association[k:]) if k>0 else (speeds[-k:],association[:k]) if k<0 else (speeds,association)
        lead[str(seconds)]=correlation(a,b)
    return {'samples':len(rows),'duration_s':len(rows)*dt,'mean_eye_speed_rad_s':float(np.mean(speeds)),
            'association_integral':float(np.sum(association)*dt),'direct_integral':float(np.sum(direct)*dt),
            'peak_association':max(association),'mean_activation':float(np.mean(activation)),
            'eye_speed_to_later_association_correlation':lead,
            'mean_gaze_hand_distance_m':float(np.mean(distances)),
            'target_central_fraction':float(np.mean([c['central'] for c in coverage])) if coverage else None,
            'target_in_field_fraction':float(np.mean([c['field'] for c in coverage])) if coverage else None,
            'interpretation':'descriptive association; neither answer inference nor a claim of internal decision'}


def analyze(path):
    result=[];apparatus=[]
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for line in f:
            record=json.loads(line)
            if 'process' not in record:apparatus.append(record);continue
            if len(record['process'])<2:continue
            result.append({'task':record.get('task'),'kind':record.get('kind'),
                           'metrics':describe(record['process'],record.get('task'))})
    if apparatus:result.append({'kind':'apparatus','metrics':describe(apparatus)})
    return {'schema':'threemind.gaze-activity-analysis/1','source':str(path),'segments':result}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recording',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=analyze(a.recording)
    with a.output.open('x',encoding='utf-8') as out:json.dump(result,out,ensure_ascii=False,allow_nan=False)
    print(json.dumps({'segments':len(result['segments']),'output':str(a.output)}))


if __name__=='__main__':main()
