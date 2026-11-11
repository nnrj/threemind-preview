"""Post-initial diagnostic; same brains/features/network, different calibration source."""
import gzip
import json
import time
from types import SimpleNamespace

import numpy as np
import torch

from experiment import WORK, SEEDS, NAMES, WORDS, study, guard, read_json, new_json
from expression import dataset, fit_rows
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.native_readout import PrototypeLanguage
from threemind_transformer.development_model import fit


def main():
    torch.set_num_threads(2);s=study();rows,projections=dataset()
    device='cuda' if torch.cuda.is_available() else 'cpu'
    try:
        for seed in SEEDS:
            for modality,projection in projections.items():
                key=f'direct-s{seed}-{modality}'
                target=WORK/'models'/f'{key}.json'
                if target.exists():continue
                guard(s,True);start=time.monotonic();s.active_case=SimpleNamespace(born_wall=start)
                selected=[r for r in rows if r['seed']==seed and r['condition']=='normal' and r['seconds']==266
                          and r['split']=='train' and r['modality']!=modality and r['intervention']=='none']
                if len(selected)!=9:raise ValueError('eight direct sensory samples and one no-cue sample required')
                training=[]
                for r in selected:
                    with gzip.open(WORK/'cases'/r['id']/'process.json.gz','rt',encoding='utf-8') as f:
                        process=json.load(f)
                    values=projection.project(process)['values']
                    text='' if r['item']<0 else (WORDS if modality=='vision' else NAMES)[r['item']]+'。'
                    training.append({'id':r['id'],'split':'train','values':values,'text':text})
                calibration=FeatureCalibration.fit(training)
                converted=fit_rows(training,calibration,projection.basis)
                output=WORK/'models'/f'{key}.safetensors'
                receipt=fit(converted,projection.basis,output,seed=seed+1009,steps=1200,batch_size=16,
                    device=device,check=lambda:guard(s),checkpoints=())
                new_json(target,{'seed':seed,'modality':modality,'regime':'direct','training_ids':[r['id'] for r in training],
                    'projection':projection.to_dict(),'feature_calibration':calibration.to_dict(),
                    'checkpoint':output.name,'receipts':[receipt],'supplementary':True,
                    'calibration_source':'direct_sensation; no taught assignment labels',
                    'adapter_role':'language-central-adapter','function':'passive-interpretation',
                    'prototype':PrototypeLanguage(converted).to_dict(),'raw_prototype':PrototypeLanguage(training).to_dict()})
                new_json(WORK/'timing'/f'train-{key}.json',{'wall_seconds':time.monotonic()-start})
                s.active_case=None
                print(json.dumps({'trained':key,'seconds':round(time.monotonic()-start,1)}),flush=True)
    finally:s.db.close()


if __name__=='__main__':main()
