"""Causal localization of sensory influence, separate from correct word retrieval."""
import numpy as np
import torch
from experiment import HERE, WORK, Input, analyse, model, previous, probe, read_json, study
from interventions import matched_masks

from lab.tools.service_study import new_json


def run():
    torch.set_num_threads(2);s=study();selected=read_json(WORK/'parameter-selection.json');chosen=[];out=[]
    try:
        rows=analyse('formal')['rows']
        for seed in (71,89,107):
            inp=Input(selected['route'],seed,model(s,seed))
            for condition in ('normal','reversed'):
                eligible=[r for r in rows if r['seed']==seed and r['condition']==condition and r['direction']=='words'
                          and r['reading']['activity_l1']>1e-8]
                if not eligible:continue
                row=min(eligible,key=lambda r:(r['seconds'],r['cue_index']));chosen.append(row)
                parent=WORK/'cases'/row['source'];definition=read_json(parent/'definition.json')
                value=previous.restore(parent/f"checkpoint-{row['seconds']}",seed)
                masks=matched_masks(value.engine.capture_state().to_dict(),set(definition['libraries']['words']['channels']),
                                    set(definition['libraries']['vision']['channels']))
                if masks is None:raise RuntimeError('insufficient matched edges for registered reciprocal check')
                for mask in ('target','matched'):
                    reading=probe(s,inp,parent,row['seconds'],row['cue_index'],'reciprocal-'+mask,masks[mask])
                    base=probe(s,inp,parent,row['seconds'],-1,'reciprocal-'+mask,masks[mask])
                    delta=np.array(reading['vectors']['words']['whole'])-base['vectors']['words']['whole']
                    amount=float(np.abs(delta).sum())
                    out.append({'source':parent.name,'seed':seed,'condition':condition,'seconds':row['seconds'],
                        'cue_index':row['cue_index'],'mask':mask,'edges':len(masks[mask]),
                        'baseline_l1':row['reading']['activity_l1'],'response_l1':amount,'ratio':amount/row['reading']['activity_l1'],
                        'max_weight_error':masks['max_weight_error'],'mean_weight_error':masks['mean_weight_error']})
        new_json(HERE/'reciprocal-effects.json',{'chosen':chosen,'rows':out,'posthoc_registered_diagnostic':True,
            'scope':'sensory influence; does not change primary correct-name criteria'})
        print('reciprocal sensory influence checks complete')
    finally:s.db.close()


if __name__=='__main__':run()
