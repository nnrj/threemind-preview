"""Independently replay the frozen personal peripheral against all recorded final windows."""
import argparse,json
from pathlib import Path
import numpy as np
import torch
import driver as d
from student import load,save,sha,FRAME_INDEX,CalibratedActivity

def verify(work):
 assert load(work/'status.json')['state']=='awaiting-analysis'
 torch.set_num_threads(1);results=[]
 for o in range(8):
  for arm in ('normal','shuffled'):
   f=work/f'origins/o{o}/{arm}';state=load(f/'whole-test-026.json.gz');ref=state['reader_ref']
   reader=CalibratedActivity.restore(f/ref['path']);buffer=[];logits=[];predictions=[];n=0;maxdiff=0.
   def flush():
    nonlocal n,maxdiff
    if not buffer:return
    actual=reader.predict(buffer);old=np.array(logits)
    diff=float(np.abs(actual-old).max());maxdiff=max(maxdiff,diff)
    assert np.allclose(actual,old,atol=5e-5,rtol=1e-5),(o,arm,diff)
    assert np.array_equal(actual.argmax(-1),np.array(predictions)),(o,arm)
    n+=len(buffer);buffer.clear();logits.clear();predictions.clear()
   for i in range(26):
    for st in load(f/f'result-{i:03d}.json.gz')['steps']:
     for q in st['queries']:
      buffer.append([q['frames'][j] for j in FRAME_INDEX]);logits.append(q['logits']);predictions.append(q['prediction'])
      if len(buffer)==128:flush()
   flush();results.append(dict(origin=o,arm=arm,questions=n,predictions_equal=True,maximum_logit_difference=maxdiff))
 result=dict(passed=True,students=16,questions=sum(r['questions'] for r in results),results=results,
             statement='Read-only peripheral replay; no Core loaded, no teaching, no subject time advanced.')
 save(work/'reader-replay.json',result);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=d.WORK);a=p.parse_args();verify(a.work.resolve())
