"""Physical feasibility checks, not ThreeMind learning or demonstrations."""

import argparse
import json
import math
import time
from pathlib import Path

import mujoco as mj
import numpy as np
from PIL import Image

from physical import TransferWorld, engineering_action


def controller_check(output,attached=False):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    trace = []
    with TransferWorld({'restock_us':120000000, 'period_us':2000, 'attached':attached}) as w:
        source = w.source_start.copy()
        target = w.receiver_start.copy()
        down = np.diag([1., -1., -1.])
        current = w.data.site_xpos[w.site].copy()
        phases = [
            ('approach', 3., source+[0,0,.17], down, .04),
            ('lower', 4., source+[0,0,.007], down, .04),
            ('close', 2., source+[0,0,.007], down, .018),
            ('lift', 4., source+[0,0,.18], down, .018),
            ('carry', 5., target+[0,-.03,.18], down, .018),
        ]
        for a in np.linspace(0,2.25,9)[1:]:
            rx=np.array([[1,0,0],[0,math.cos(a),-math.sin(a)],[0,math.sin(a),math.cos(a)]])
            phases.append(('pour',1.,target+[0,-.015,.15],rx@down,.018))
        phases.append(('hold',3.,target+[0,-.015,.15],phases[-1][3],.018))
        renderer = mj.Renderer(w.model,height=480,width=640)
        last_rotation = down.copy()
        for index,(name,seconds,pos,rotation,opening) in enumerate(phases):
            initial = current.copy()
            n=int(seconds*1e6/w.cfg['period_us'])
            for i in range(n):
                fraction=min(1.,(i+1)/(.8*n))
                location=initial+(pos-initial)*fraction
                # Small successive rotation targets avoid discontinuous inverses.
                w.step(engineering_action(w,location,rotation,opening))
                if i % 250 == 0:
                    trace.append(dict(time_us=w.time_us,phase=name,site=w.data.site_xpos[w.site].tolist(),
                        source=w.data.xpos[w.source].tolist(),grasp=w.ever_grasped,lift=w.ever_lifted,
                        contacts=w.contacts,transferred=w.transferred))
            current=pos.copy()
            last_rotation=rotation
            renderer.update_scene(w.data,camera='observer')
            Image.fromarray(renderer.render()).save(output/f'{index:02d}-{name}.png')
            print(json.dumps(trace[-1]),flush=True)
        renderer.close()
        result=dict(schema='threemind.granular-engineering/1',controller='privileged IK/PD only',
            core_used=False,config=w.cfg,xml_hash=w.xml_hash,mujoco=mj.__version__,
            transferred=w.transferred,grasp=w.ever_grasped,lift=w.ever_lifted,
            events=w.events,work_j=w.work_j,peak_contact_n=w.peak_contact_n,
            wall_seconds=time.monotonic()-started,trace=trace)
        (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (output/'final-world.json').write_text(json.dumps(w.capture()),encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('transferred','grasp','lift','wall_seconds')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output',type=Path)
    p.add_argument('--attached',action='store_true')
    args=p.parse_args()
    controller_check(args.output,args.attached)
