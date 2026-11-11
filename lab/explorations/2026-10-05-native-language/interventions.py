"""Supplementary local mediation, selected before interventions, external only."""
import gzip
import json
import time
from types import SimpleNamespace

import numpy as np
import torch

from analyse import decoded
from experiment import HERE, WORK, SEEDS, WIRING, e45, inp, probe, study, guard, read_json, new_json
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.native_readout import NativeProjection, PrototypeLanguage
from threemind_transformer.development_model import load


def matched_masks(image,left,right):
    nodes={int(n['id']):int(n['channel']) for n in image['nodes']}
    def target(edge):
        a,b=nodes[int(edge['source'])],nodes[int(edge['target'])]
        return a in left and b in right or b in left and a in right
    selected=[e for e in image['edges'] if target(e)]
    rest=[e for e in image['edges'] if not target(e)]
    if not selected or len(rest)<len(selected):return None
    control=[];errors=[]
    for edge in sorted(selected,key=lambda e:-e['weight']):
        i=min(range(len(rest)),key=lambda j:abs(rest[j]['weight']-edge['weight']))
        other=rest.pop(i);control.append(other);errors.append(abs(other['weight']-edge['weight']))
    return {'target':[(int(e['source']),int(e['target'])) for e in selected],
            'matched':[(int(e['source']),int(e['target'])) for e in control],
            'max_weight_error':max(errors),'mean_weight_error':float(np.mean(errors)),
            'topology_matched':False}


def run():
    torch.set_num_threads(2);s=study();input_adapter=inp();base=decoded()
    base=[r for r in base if r['regime']=='individual' and r['condition']=='normal'
          and r['seconds']==266 and r['split']=='test' and r['intervention']=='none']
    selected=[]
    for seed in SEEDS:
        for modality in ('vision','words'):
            rows=[r for r in base if r['seed']==seed and r['modality']==modality]
            background=next(r for r in rows if r['item']<0)
            correct=[r['id'] for r in rows if r['item']>=0 and r['transformer']['text']==r['target']
                     and r['transformer']['text']!=background['transformer']['text']]
            if correct:selected.append({'seed':seed,'modality':modality,'initial_correct_ids':correct})
    selection=WORK/'initial-mediation-selection.json'
    if not selection.exists():new_json(selection,{'sources':selected,'selection':'any initial cue-specific success; all prompts retested'})
    elif read_json(selection)['sources']!=selected:raise RuntimeError('selection changed')
    domains=read_json(WORK/'projection.json');rows=[];masks_by_seed={}
    try:
        for item in selected:
            seed,modality=item['seed'],item['modality'];parent=WORK/'cases'/f's{seed}-normal'
            if seed not in masks_by_seed:
                value=e45.previous.restore(parent/'checkpoint-266',WIRING)
                masks_by_seed[seed]=matched_masks(value.engine.capture_state().to_dict(),
                    set(domains['vision']['excluded_channels']),set(domains['words']['excluded_channels']))
            masks=masks_by_seed[seed]
            if masks is None:continue
            manifest=read_json(WORK/'models'/f'individual-s{seed}-{modality}.json')
            projection=NativeProjection(**manifest['projection']);calibration=FeatureCalibration(**manifest['feature_calibration'])
            model,_=load(WORK/'models'/manifest['checkpoint'],'cuda' if torch.cuda.is_available() else 'cpu')
            proto=PrototypeLanguage.from_dict(manifest['prototype'])
            for mask in ('target','matched'):
                cases=[probe(s,input_adapter,parent,266,modality,-1,0,.5,'test','cross-sensory-'+mask,masks[mask])]
                for cue in range(4):
                    for variant in ((0,1) if modality=='vision' else (9,)):
                        cases.append(probe(s,input_adapter,parent,266,modality,cue,variant,.5,'test',
                            'cross-sensory-'+mask,masks[mask]))
                start=time.monotonic();s.active_case=SimpleNamespace(born_wall=start)
                features=[]
                for path in cases:
                    with gzip.open(path/'process.json.gz','rt',encoding='utf-8') as f:features.append(projection.project(json.load(f)))
                values=calibration.transform([f['values'] for f in features])
                outputs=model.decode(values);prototypes=proto.decode(values)
                guard(s)
                for path,out,p in zip(cases,outputs,prototypes,strict=True):
                    r=read_json(path/'result.json')
                    rows.append({k:r[k] for k in ('seed','source','modality','item','variant','target','intervention')}|
                                {'id':path.name,'transformer':out,'prototype':p,'mask':mask})
                new_json(WORK/'timing'/f'mediation-{seed}-{modality}-{mask}.json',{'wall_seconds':time.monotonic()-start})
                s.active_case=None
            print(json.dumps({'mediated_seed':seed,'modality':modality,'edges':len(masks['target'])}),flush=True)
        new_json(HERE/'initial-mediation.json',{'selected':selected,'masks':masks_by_seed,'rows':rows,
            'scope':'initial individualized expression only; original reversal gate remains failed'})
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':run()
