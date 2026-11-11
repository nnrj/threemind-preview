"""Check that direct-sensation readers can actually decode direct sensation."""
import gzip
import json
import time
from types import SimpleNamespace

import torch

from experiment import HERE, WORK, SEEDS, NAMES, WORDS, study, guard, read_json, new_json
from expression import dataset
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.native_readout import NativeProjection
from threemind_transformer.development_model import load


def run():
    torch.set_num_threads(2);s=study();started=time.monotonic()
    s.active_case=SimpleNamespace(born_wall=started);rows,_=dataset();outputs=[]
    try:
        for seed in SEEDS:
            for modality in ('vision','words'):
                manifest=read_json(WORK/'models'/f'direct-s{seed}-{modality}.json')
                projection=NativeProjection(**manifest['projection']);calibration=FeatureCalibration(**manifest['feature_calibration'])
                model,_=load(WORK/'models'/manifest['checkpoint'],'cuda' if torch.cuda.is_available() else 'cpu')
                selected=[r for r in rows if r['seed']==seed and r['condition']=='normal' and r['seconds']==266
                          and r['intervention']=='none' and r['modality']!=modality]
                features=[]
                for r in selected:
                    with gzip.open(WORK/'cases'/r['id']/'process.json.gz','rt',encoding='utf-8') as f:
                        features.append(projection.project(json.load(f))['values'])
                decoded=model.decode(calibration.transform(features));guard(s)
                for r,text in zip(selected,decoded,strict=True):
                    target='' if r['item']<0 else (WORDS if modality=='vision' else NAMES)[r['item']]+'。'
                    outputs.append({'id':r['id'],'seed':seed,'modality':modality,'split':r['split'],
                        'item':r['item'],'target':target,'output':text,'correct':target==text['text']})
        new_json(HERE/'direct-acceptance.json',{'rows':outputs,
            'scope':'direct sensory positive control, not a recall or new-knowledge success'})
        new_json(WORK/'timing'/'direct-acceptance.json',{'wall_seconds':time.monotonic()-started})
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':run()
