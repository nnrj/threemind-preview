"""Explicit OFFLINE readout interventions; never alter Core or live outputs."""
import numpy as np
from experiment import study,Case,WORK,old,new_json,DetailedClassroom,paired_scores,cached
from lab.tools.spatial_choice import SpatialChoice


def main():
    s=study()
    try:
        for seed in (223,279):
            key=f'E-s{seed}-reader-sensitivity'
            if cached(key):continue
            source=WORK/f'cases/B-s{seed}-learned-fit/controller'
            if not source.exists():continue
            case=Case(s,key);model,layout=SpatialChoice.restore(source,old.device())
            d=[np.load(WORK/f'cases/B-s{seed}-p1-h{h}-teach-test-normal/features.npz') for h in (0,1)]
            x=np.stack([a['activity'] for a in d]);y=np.stack([a['y'] for a in d])
            channels=DetailedClassroom(91,resolution=4).channels
            groups={'vision':channels[:256],'teacher_marker':channels[264:270],
                    'body_environment':[*channels[256:264],*channels[270:]],
                    'text':[c for c in layout.channels if c not in channels]}
            columns={name:[layout.index[c]*4+k for c in members for k in range(4)] for name,members in groups.items()}
            columns.update({name:list(range(k,layout.width,4)) for k,name in enumerate(('activation','inhibition','direct','associative'))})
            predictions=[]
            for name,indices in columns.items():
                for mode in ('zero','history-swap'):
                    altered=x.copy()
                    altered[:,:,:,indices]=0 if mode=='zero' else x[::-1,:,:,indices]
                    pred=model.predict(altered.reshape(-1,*x.shape[2:])).argmax(-1).reshape(2,-1)
                    predictions.append({'group':name,'mode':mode,**paired_scores(pred,y),
                                        'donor_correct':int((pred==y[::-1]).sum()),'predictions':pred.tolist()})
            new_json(case.path/'predictions.json',predictions)
            case.finish({'seed':seed,'diagnostics':[{k:v for k,v in row.items() if k!='predictions'} for row in predictions],
               'scope':'offline decoder sensitivity; altered arrays are not original observations or Core intervention evidence'})
    finally:s.db.close()


if __name__=='__main__':main()
