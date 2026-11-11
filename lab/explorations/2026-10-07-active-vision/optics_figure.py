"""Physical central-retina visibility check; no recognition scores or Core edits."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.service_study import new_json

work=ROOT/'.work/active-vision-20261007'
w=ActiveEyeClassroom();w.visible_self=False
target=np.array([-.55,-.55,.16]);v=target-w.origin
base=-w.origin/np.linalg.norm(w.origin);right=np.array([1.,0.,0.]);up=np.cross(right,base)
w.eye_angle=np.array([np.arctan2(v@right,v@base),np.arctan2(v@up,np.hypot(v@right,v@base))])
fig,axes=plt.subplots(2,4,figsize=(10,5));arrays=[]
for shape,name in enumerate(('sphere','cylinder','cube','cone')):
    w.set_scene([(shape,4),(0,0),(2,2),(3,3)])
    array=np.array(w.vision()['values']).reshape(68,4)[:36].reshape(6,6,4);arrays.append(array)
    axes[0,shape].imshow(array[:,:,1:],origin='lower');axes[0,shape].set_title(name)
    axes[1,shape].imshow(array[:,:,0],origin='lower',vmin=.19,vmax=.26,cmap='viridis')
    for ax in axes[:,shape]:ax.set_xticks([]);ax.set_yticks([])
axes[0,0].set_ylabel('actual RGB');axes[1,0].set_ylabel('actual reciprocal range')
fig.suptitle('Same physical location, same gray material; optical calibration only')
fig.tight_layout();fig.savefig(work/'central-optics.png',dpi=150)
metrics={'eye_angle_rad':w.eye_angle.tolist(),'shape_raw_distances':[[float(np.linalg.norm(a-b)) for b in arrays] for a in arrays],
         'meaning':'physical sensor distinguishability, not learned recognition','camera_count':1,'receptors':68}
new_json(work/'central-optics.json',metrics)
print(metrics)
