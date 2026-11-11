"""Locate user-reported E55 video moments in their original recorded frames.

Run after E56's pointing experiments. No simulation, video decoding or inference.
"""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'.work/grounded-reviews-20261006/complete-media/complete-replay.json'


def locate(data,start,end):
    frames=[];chapters=[]
    for chapter in data['chapters']:
        if chapter['end']<start or chapter['start']>end:continue
        chapters.append({k:chapter[k] for k in ('title','case','kind','source')})
        for clip in chapter['clips']:
            for i,frame in enumerate(clip['frames']):
                t=clip['start']+i*.05/clip['speed']
                if start<=t<=end:frames.append(frame|{'video_s':t,'mode':clip['mode']})
    if not frames:raise ValueError('unmatched video interval')
    return {'video_seconds':[start,end],'chapters':chapters,'samples':len(frames),
        'simulation_seconds':[frames[0]['t'],frames[-1]['t']],
        'explicit_action_frames':sum(f['force'] is not None for f in frames),
        'teacher_marker_frames':sum(f['marker'] is not None for f in frames),
        'activation_range':[min(f['a'] for f in frames),max(f['a'] for f in frames)],
        'association_range':[min(f['r'] for f in frames),max(f['r'] for f in frames)],
        'path_length_m':sum(math.dist(a['p'],b['p']) for a,b in zip(frames,frames[1:])),
        'frames':frames}


def main():
    output=HERE/'circle-audit.json'
    if output.exists():raise FileExistsError('preserve recorded audit')
    data=json.loads(SOURCE.read_bytes())
    first=locate(data,147,155);second=locate(data,748,758)
    # Same simulation moments, not similar-looking video frames.
    source_frames={}
    for chapter in data['chapters']:
        if chapter['kind']!='teaching':continue
        source_frames[chapter['case']]={round(f['t'],5):f for c in chapter['clips'] for f in c['frames']}
    normal=source_frames['s223-spaced-teaching'];frozen=source_frames['s223-frozen-teaching']
    comparisons=[]
    for segment in (first,second):
        times=sorted({round(f['t'],5) for f in segment['frames']} & normal.keys() & frozen.keys())
        comparisons.append({'matched_simulation_samples':len(times),
            'max_pointer_distance_m':max(math.dist(normal[t]['p'],frozen[t]['p']) for t in times),
            'max_activation_difference':max(abs(normal[t]['a']-frozen[t]['a']) for t in times),
            'max_association_difference':max(abs(normal[t]['r']-frozen[t]['r']) for t in times)})
    result={'source':str(SOURCE.relative_to(ROOT)),'windows':[{k:v for k,v in s.items() if k!='frames'} for s in (first,second)],
        'same_simulation_time_learning_on_off':comparisons,
        'source_code_fact':'Basic teaching tick(action=None) advances world with no Core motor command; physical wind and body dynamics still apply.',
        'core_rerun':False,'video_rerendered':False}
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'windows':[{k:v for k,v in s.items() if k!='frames'} for s in (first,second)],
                      'matched':comparisons},ensure_ascii=False))

if __name__=='__main__':main()
