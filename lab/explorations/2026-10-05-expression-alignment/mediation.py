"""Registered copied-state pathway interventions for already calibrated naming."""
import shutil
import time
from types import SimpleNamespace
import torch
from experiment import ROOT,WORK,study,guard,helpers,e46,read_json,new_json
from new_experience import NEW_SEEDS
from features import load_process
from lab.tools.connection_controls import cross_domain_masks
from lab.tools.expression_observation import ExpressionObservation,decode_timed
from lab.tools.native_expression import FeatureCalibration
from threemind_transformer.development_model import load


def main():
    torch.set_num_threads(2);s=study();adapter=helpers();rows=[];masks_by_source={}
    device='cuda' if torch.cuda.is_available() else 'cpu'
    domains=read_json(WORK/'projection.json')
    try:
        copied=WORK/'frozen-tools/lab/tools/connection_controls.py';copied.parent.mkdir(parents=True,exist_ok=True)
        if not copied.exists():shutil.copy2(ROOT/'lab/tools/connection_controls.py',copied)
        for seed in NEW_SEEDS:
            models={}
            for scope,folder in (('cross','models'),('all','all-models')):
                manifest=read_json(WORK/folder/f'two-assignments-s{seed}-words.json')
                models[scope]=(load(WORK/folder/manifest['checkpoint'],device)[0],ExpressionObservation(**manifest['observation']),
                               FeatureCalibration(**manifest['feature_calibration']))
            for condition in ('continued','reversal'):
                parent=WORK/'cases'/f's{seed}-{condition}'
                value=e46.e45.previous.restore(parent/'checkpoint-592',71)
                masks=cross_domain_masks(value.engine.capture_state().to_dict(),
                    domains['vision']['excluded_channels'],domains['words']['excluded_channels'])
                if masks is None:raise RuntimeError('count-matched control unavailable')
                masks_by_source[parent.name]=masks
                for mask in ('target','matched'):
                    cases=[e46.probe(s,adapter,parent,592,'words',-1,0,.5,'test','known-'+mask,masks[mask])]
                    cases += [e46.probe(s,adapter,parent,592,'words',item,9,.5,'test','known-'+mask,masks[mask]) for item in range(4)]
                    tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
                    processes=[load_process(p/'process.json.gz') for p in cases]
                    for scope,(model,instrument,calibration) in models.items():
                        features=[instrument.project(process,processes[0]) for process in processes]
                        generated=decode_timed(model,calibration.transform([r['values'] for r in features]),
                            [{'id':p.name,'start_us':r['start_us'],'end_us':r['end_us']} for p,r in zip(cases,processes,strict=True)])
                        no_cue=generated[0]['output']['text']
                        for path,output in zip(cases,generated,strict=True):
                            meta=read_json(path/'result.json')
                            rows.append({k:meta[k] for k in ('seed','condition','seconds','modality','item','variant','target')}|
                                {'mask':mask,'scope':scope,'output':output,'cue_specific':output['output']['text']==meta['target'] and meta['target']!=no_cue})
                    new_json(WORK/'timing'/f'mediation-{seed}-{condition}-{mask}.json',{'wall_seconds':time.monotonic()-tick})
                    s.active_case=None
                print({'mediated':parent.name,'edges':len(masks['target']),'mean_error':masks['mean_weight_error']},flush=True)
        new_json(WORK/'known-mediation.json',{'masks':masks_by_source,'rows':rows,'purpose':'known calibrated naming, not unseen-map success'})
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':main()
