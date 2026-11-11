"""Matched external optimization dose; all Core records remain unchanged."""
import time
import numpy as np
from experiment import study,Case,WORK,OLD,old,read_json,new_json,DetailedClassroom,cached
from lab.tools.spatial_choice import SpatialChoice


def main():
    s=study();src=WORK/'cases/A-recorded-inputs'
    try:
        for seed in (223,279,337):
            for steps in (100,300,1200):
                for mode in ('learned','unlearned','incoming'):
                    key=f'D-{mode}-s{seed}-steps{steps}'
                    if cached(key):continue
                    case=Case(s,key);origin='unlearned' if mode=='unlearned' else 'learned'
                    field='incoming' if mode=='incoming' else 'activity'
                    train=np.load(src/f'{origin}-train.npz');test=np.load(src/f'{origin}-test.npz')
                    if steps==1200:
                        head,_=SpatialChoice.restore(WORK/f'cases/A-{mode}-s{seed}/controller',old.device())
                        fit={'reused':True,'source':f'A-{mode}-s{seed}'}
                    else:
                        head=SpatialChoice(read_json(src/f'{origin}-layout.json'),DetailedClassroom(91,resolution=4).channels[:256],seed=seed).to(old.device())
                        fit=head.fit(train[field],train['y'],steps=steps,check=s.guard);head.save(case.path/'controller')
                    head.predict(test[field])  # one warmup; .predict synchronizes via CPU output
                    inference_start=time.perf_counter()
                    pred=head.predict(test[field]).argmax(-1)
                    inference_ms=1000*(time.perf_counter()-inference_start)
                    truth=test['y'];rows={'normal':pred.tolist()}
                    result={'seed':seed,'steps':steps,'mode':mode,'fit':fit,
                            'train_correct':int((head.predict(train[field]).argmax(-1)==train['y']).sum()),
                            'correct':int((pred==truth).sum()),'n':len(truth),
                            'inference_batch_ms':inference_ms,'timing_scope':'24query batch including CPU return; descriptive, no speed claim'}
                    if mode=='learned':
                        for condition in ('silence','rescue'):
                            data=np.load(OLD/f'cases/r4-exposure-shared-confirmation-{condition}/features.npz')
                            if not np.array_equal(data['y'],truth):raise ValueError('unaligned paired E56 trials')
                            other=head.predict(data['x']).argmax(-1);rows[condition]=other.tolist()
                            result[condition]={'correct':int((other==truth).sum()),'changed':int((pred!=other).sum()),
                               'lost_correct':int(((pred==truth)&(other!=truth)).sum()),
                               'gained_correct':int(((pred!=truth)&(other==truth)).sum())}
                    new_json(case.path/'predictions.json',rows|{'targets':truth.tolist()})
                    case.finish(result)
    finally:s.db.close()


if __name__=='__main__':main()
