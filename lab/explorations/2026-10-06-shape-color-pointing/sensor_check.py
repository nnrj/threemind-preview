"""Offline instrument calibration; known optical slot, not a Core answer head."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from lab.tools.shape_color_world import ShapeColorWorld

WORK=ROOT/'.work/shape-color-20261006'


def main():
    output=WORK/'sensor-calibration.json'
    if output.exists():raise RuntimeError('calibration evidence already exists')
    start=time.monotonic();w=ShapeColorWorld();templates=[];labels=[]
    for view in range(4):
        w.set_scene([(s,4) for s in range(4)],view)
        rays=np.asarray(w.vision()['values']).reshape(4,16,4)
        for shape in range(4):templates.append(rays[shape,:,0]);labels.append(shape)
    templates=np.asarray(templates);trials=[]
    for view in (5,6):
        for color in range(4):
            # Every target geometry is tested at every physical field. The
            # selected field is intentionally known to this calibration oracle.
            for rotation in range(4):
                shapes=np.roll(np.arange(4),rotation).tolist()
                w.set_scene([(s,color) for s in shapes],view)
                rays=np.asarray(w.vision()['values']).reshape(4,16,4)
                for slot,shape in enumerate(shapes):
                    distances=((templates-rays[slot,:,0])**2).sum(-1)
                    prediction=int(labels[int(distances.argmin())])
                    trials.append({'view':view,'color':color,'slot':slot,'shape':shape,
                                   'prediction':prediction,'correct':prediction==shape})
    result={'schema':'threemind.classroom-sensor-calibration/1',
            'scope':'known optical slot; nearest raw depth template; no Core or language; not a deployed solver',
            'training_views':[0,1,2,3],'testing_views':[5,6],'n':len(trials),
            'shape_correct':sum(r['correct'] for r in trials),'trials':trials,
            'wall_seconds':time.monotonic()-start}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},ensure_ascii=False))


if __name__=='__main__':main()
