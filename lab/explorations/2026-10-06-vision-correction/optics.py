"""Read-only sensory audit: no Core, answer injection or learned policy."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from lab.tools.classroom_eye import DetailedClassroom
from lab.tools.service_study import new_json

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/vision-correction-20261006'


def main():
    WORK.mkdir(exist_ok=True)
    results={}; raw={}
    image=Image.new('RGB',(1050,720),'#f0f6f5'); d=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
    d.text((20,15),'实际感官采样：灰色形状的 RGB（左）和距离（右）；固定视角',font=font,fill='#173a3c')
    for column,n in enumerate((4,6,8)):
        w=DetailedClassroom(resolution=n); xs=[];ys=[];vs=[]
        for variant in range(7):
            for shape in range(4):
                w.set_scene([(shape,4)]*4,variant)
                xs.append(np.asarray(w.vision()['values']).reshape(4,n,n,4)[0].ravel())
                ys.append(shape);vs.append(variant)
        x=np.array(xs);y=np.array(ys);v=np.array(vs);raw[str(n)]=x.tolist()
        train=v<4;test=v>=5
        def evaluate(mask):
            xx=x.reshape(len(x),-1,4)[:,:,mask].reshape(len(x),-1)
            dist=np.mean((xx[test,None,:]-xx[None,train,:])**2,axis=-1)
            pred=y[train][dist.argmin(1)]
            return {'correct':int((pred==y[test]).sum()),'n':int(test.sum()),'predictions':pred.tolist()}
        collision=[];minimum=[]
        for variant in range(7):
            z=x[v==variant];diff=np.max(np.abs(z[:,None]-z[None,:]),axis=-1)
            for a in range(4):
                for b in range(a+1,4):
                    if diff[a,b]<1e-12:collision.append([variant,a,b])
                    minimum.append(float(diff[a,b]))
        results[str(n)]={'raw_rgb_depth_nearest':evaluate([0,1,2,3]),'rgb_only_nearest':evaluate([1,2,3]),
                         'depth_only_nearest':evaluate([0]),'identical_shape_pairs':collision,
                         'minimum_pair_max_component_difference':min(minimum),'total_ports':len(w.channels),
                         'visual_gain_per_channel':.03*16/n**2}
        d.text((25+column*345,55),f'{n}×{n} / 区域',font=font,fill='#173a3c')
        for shape,label in enumerate(('球体','圆柱体','立方体','圆锥体')):
            patch=x[(v==3)&(y==shape)][0].reshape(n,n,4)
            for row,arr in enumerate((patch[:,:,1:]*255,np.repeat(patch[:,:,:1]*255,3,axis=-1))):
                tile=Image.fromarray(arr.astype('uint8')).resize((120,120),Image.Resampling.NEAREST)
                image.paste(tile,(column*345+30+row*145,90+shape*150))
            d.text((column*345+30,212+shape*150),label,font=font,fill='#173a3c')
    image.save(WORK/'optical-samples.png')
    if not (HERE/'optical-audit.json').exists():
        new_json(HERE/'optical-audit.json',{'scope':'sensor-only diagnostic, not consciousness accuracy',
                 'train_views':[0,1,2,3],'test_views':[5,6],'results':results})
        new_json(WORK/'optical-raw.json',raw)
    print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':main()
