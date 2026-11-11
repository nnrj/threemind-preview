"""Predeclared first-success local mediation controls, not new accuracy samples."""
import json

import numpy as np
import torch
from experiment import HERE, WORK, Input, analyse, model, previous, probe, read_json, study

from lab.tools.sensory_calibration import SensoryResponseLibrary
from lab.tools.service_study import new_json


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
        index=min(range(len(rest)),key=lambda i:abs(rest[i]['weight']-edge['weight']))
        match=rest.pop(index);control.append(match);errors.append(abs(match['weight']-edge['weight']))
    return {'target':[(int(e['source']),int(e['target'])) for e in selected],
            'matched':[(int(e['source']),int(e['target'])) for e in control],
            'max_weight_error':max(errors),'mean_weight_error':float(np.mean(errors))}


def run(stage='formal'):
    torch.set_num_threads(2);s=study()
    try:
        selected=read_json(WORK/'parameter-selection.json');out=HERE/f'{stage}-interventions.json'
        if out.exists():return
        selection_file=WORK/f'{stage}-intervention-selection.json'
        if selection_file.exists():chosen=read_json(selection_file)['chosen']
        else:
            pairs=analyse(stage)['pairs'];chosen=[]
            for seed in ((71,89,107) if stage=='formal' else (71,89)):
                for direction in (('vision','words') if stage=='formal' else ('audio',)):
                    options=[r for r in pairs if r['seed']==seed and r['parameter']==selected['parameter'] and r['direction']==direction and r['correct']]
                    if options:chosen.append(min(options,key=lambda r:(r['seconds'],r['cue_index'])))
            new_json(selection_file,{'chosen':chosen,'selection':'first whole-window joint success per seed/direction; no success means none'})
        results=[]
        for item in chosen:
            inp=Input(selected['route'],item['seed'],model(s,item['seed']))
            for condition in ('normal','reversed'):
                parent=WORK/'cases'/f"{stage}-{selected['route']}-{selected['parameter']}-s{item['seed']}-{condition}"
                definition=read_json(parent/'definition.json')
                value=previous.restore(parent/f"checkpoint-{item['seconds']}",inp.seed)
                image=value.engine.capture_state().to_dict()
                modality={k:set(v['channels']) for k,v in definition['libraries'].items()}
                links=[('language-vision','words','vision')]
                if stage=='composition':links.append(('vision-sound','vision','audio'))
                for label,left,right in links:
                    masks=matched_masks(image,modality[left],modality[right])
                    if not masks:
                        results.append({'seed':inp.seed,'condition':condition,'link':label,'status':'insufficient_edges'});continue
                    library=SensoryResponseLibrary(**definition['libraries'][item['direction']])
                    for mask in ('target','matched'):
                        reading=probe(s,inp,parent,item['seconds'],item['cue_index'],label+'-'+mask,masks[mask])
                        baseline=probe(s,inp,parent,item['seconds'],-1,label+'-'+mask,masks[mask])
                        vector=np.array(reading['vectors'][item['direction']]['whole'])-baseline['vectors'][item['direction']]['whole']
                        decoded=library.read(vector)
                        results.append({'source':parent.name,'seed':inp.seed,'condition':condition,'seconds':item['seconds'],
                            'cue_index':item['cue_index'],'direction':item['direction'],'link':label,'mask':mask,
                            'edges':len(masks[mask]),'max_weight_error':masks['max_weight_error'],
                            'mean_weight_error':masks['mean_weight_error'],'reading':decoded,'target':reading['target'],
                            'correct':decoded['prediction']==reading['target']})
        new_json(out,{'chosen':chosen,'rows':results,'scope':'selected localized effects, not independent general accuracy'})
        print(json.dumps({'stage':stage,'selected':len(chosen),'interventions':len(results)}),flush=True)
    finally:s.db.close()


if __name__=='__main__':
    import sys
    run(sys.argv[1] if len(sys.argv)>1 else 'formal')
