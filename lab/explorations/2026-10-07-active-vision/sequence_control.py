"""Registered readout-only full-sequence control after E59 B-stage failure."""
import argparse
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from experiment import HERE,WORK,study,run,device
from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.activity_controller import ActivityLayout
from lab.tools.choice_attribution import raw_window
from lab.tools.foveal_sequence import FovealSequence
from lab.tools.service_study import new_json,read_json


def build(s,policy,split):
    def execute(p):
        source=WORK/f'cases/B-{policy}-{split}';layout=ActivityLayout(read_json(WORK/f'cases/B-teach-{policy}/layout.json'))
        examples=[e for e in read_json(source/'examples.json') if e['sample_index']==59]
        old=np.load(source/'features.npz');data={'activity':[],'incoming':[],'y':old['y'][2::3]};audit=[]
        world=ActiveEyeClassroom();world_ports=set(world.channels)
        with gzip.open(source/'process.jsonl.gz','rt',encoding='utf-8') as stream:
            for i,line in enumerate(stream):
                s.guard();record=json.loads(line);rows=record['process']
                for kind in ('activity','incoming'):data[kind].append(raw_window(layout,rows,kind=kind,count=None))
                text_indices=[j for j,r in enumerate(rows) if any(int(ch) not in world_ports for ch,_ in r['stimulus']['channels'])]
                sparse=set(np.rint(np.linspace(0,len(rows)-1,16)).astype(int))
                audit.append({'question':record['task']['text'],'actual_language_frames':len(text_indices),
                              'retained_by_16_frame_readout':sum(j in sparse for j in text_indices),
                              'all_samples':len(rows),'original_stimulus_changed':False})
        np.savez_compressed(p/'features.npz',**data);new_json(p/'examples.json',examples);new_json(p/'sampling-audit.json',audit)
        return {'policy':policy,'split':split,'samples':len(examples),'frames_per_sample':60,
                'actual_language_frames':sum(r['actual_language_frames'] for r in audit),
                'retained_by_16_frame_readout':sum(r['retained_by_16_frame_readout'] for r in audit)}
    return run(s,f'S-data-{policy}-{split}',execute)


def fit(s,policy,kind,sampling,role):
    def execute(p):
        def data(split):
            x=np.load(WORK/f'cases/S-data-{policy}-{split}/features.npz')
            ix=np.rint(np.linspace(0,59,16)).astype(int) if sampling=='sparse' else np.arange(60)
            return x[kind][:,ix],x['y']
        w=ActiveEyeClassroom();head=FovealSequence(read_json(WORK/f'cases/B-teach-{policy}/layout.json'),
            w.channels[:w.vision_width],w.retinal_centers,w.retinal_widths,seed=223 if role=='hand' else 501).to(device())
        x,y=data('train');vx,vy=data('validation')
        fitted=head.fit(x,y,steps=1200,validation=(vx,vy),check=s.guard,batch_size=4);head.save(p/'controller')
        result={'policy':policy,'kind':kind,'sampling':sampling,'role':role,'fit':fitted}
        for split in ('train','validation','test'):
            if not (WORK/f'cases/S-data-{policy}-{split}/features.npz').exists():continue
            x,y=data(split);pred=np.concatenate([head.predict(x[i:i+4]).argmax(-1) for i in range(0,len(y),4)])
            examples=read_json(WORK/f'cases/S-data-{policy}-{split}/examples.json');rows=[]
            for pixel,e in zip(pred,examples):
                world=ActiveEyeClassroom.restore(e['world']);endpoint=np.asarray(e['receptor_ground_points'][int(pixel)])
                for _ in range(40):world.advance_physics(world.pointer.teacher_action(endpoint))
                actual=np.array([world.pointer.x,world.pointer.y]);distances=np.linalg.norm(np.array(e['positions'])-actual,axis=1)
                chosen=int(np.argmin(distances));rows.append({k:v for k,v in e.items() if k not in ('world','receptor_ground_points')}|
                    {'receptor':int(pixel),'target_receptor':int(y[len(rows)]),'endpoint':endpoint.tolist(),'actual':actual.tolist(),
                     'chosen':chosen,'correct':chosen==e['slot'],'target_distance':float(distances[e['slot']])})
            new_json(p/f'{split}-predictions.json',rows)
            result[split]={'n':len(rows),'correct':sum(r['correct'] for r in rows),'arrived':sum(r['target_distance']<=.2 for r in rows),
                          'exact_target_rate':float(np.mean(pred==y)),
                          'by_category':{cat:sum(r['correct'] for r in rows if r['category']==cat) for cat in ('color','shape','pair')}}
        return result
    return run(s,f'S-fit-{policy}-{kind}-{sampling}'+('' if role=='hand' else '-eye'),execute)


def select(s,policy):
    choices={}
    for kind in ('activity','incoming'):
        values={v:read_json(WORK/f'cases/S-fit-{policy}-{kind}-{v}/result.json') for v in ('full','sparse')}
        choice=min(values,key=lambda k:(-values[k]['validation']['correct'],values[k]['fit']['loss']))
        choices[kind]={'sampling':choice,'reason':'validation correct, then validation loss only',
            'validation':{k:{'correct':v['validation']['correct'],'loss':v['fit']['loss']} for k,v in values.items()}}
    new_json(WORK/f'sequence-selection-{policy}.json',choices)
    print(json.dumps(choices))


def evaluate(s,policy,kind,sampling):
    if not (WORK/f'sequence-selection-{policy}.json').exists():raise ValueError('freeze selection before revealing holdout')
    def execute(p):
        head,_=FovealSequence.restore(WORK/f'cases/S-fit-{policy}-{kind}-{sampling}/controller',device())
        data=np.load(WORK/f'cases/S-data-{policy}-holdout/features.npz')
        ix=np.rint(np.linspace(0,59,16)).astype(int) if sampling=='sparse' else np.arange(60)
        x=data[kind][:,ix];pred=np.concatenate([head.predict(x[i:i+4]).argmax(-1) for i in range(0,len(x),4)])
        examples=read_json(WORK/f'cases/S-data-{policy}-holdout/examples.json');rows=[]
        for pixel,e in zip(pred,examples):
            world=ActiveEyeClassroom.restore(e['world']);endpoint=np.asarray(e['receptor_ground_points'][int(pixel)])
            for _ in range(40):world.advance_physics(world.pointer.teacher_action(endpoint))
            actual=np.array([world.pointer.x,world.pointer.y]);distances=np.linalg.norm(np.array(e['positions'])-actual,axis=1)
            chosen=int(np.argmin(distances));rows.append({k:v for k,v in e.items() if k not in ('world','receptor_ground_points')}|
                {'receptor':int(pixel),'chosen':chosen,'correct':chosen==e['slot'],'actual':actual.tolist(),
                 'target_distance':float(distances[e['slot']])})
        new_json(p/'predictions.json',rows)
        return {'policy':policy,'kind':kind,'sampling':sampling,'n':len(rows),'correct':sum(r['correct'] for r in rows),
                'arrived':sum(r['target_distance']<=.2 for r in rows),
                'by_category':{cat:sum(r['correct'] for r in rows if r['category']==cat) for cat in ('color','shape','pair')}}
    return run(s,f'S-holdout-{policy}-{kind}-{sampling}',execute)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['build','fit','select','evaluate'])
    p.add_argument('--policy',choices=['fixed','scan'],default='scan');p.add_argument('--split',choices=['train','validation','test','holdout'],default='train')
    p.add_argument('--kind',choices=['activity','incoming'],default='activity');p.add_argument('--sampling',choices=['full','sparse'],default='full')
    p.add_argument('--role',choices=['hand','eye'],default='hand');a=p.parse_args();s=study()
    try:
        if a.stage=='build':build(s,a.policy,a.split)
        elif a.stage=='select':select(s,a.policy)
        elif a.stage=='evaluate':evaluate(s,a.policy,a.kind,a.sampling)
        else:fit(s,a.policy,a.kind,a.sampling,a.role)
    finally:s.db.close()


if __name__=='__main__':main()
