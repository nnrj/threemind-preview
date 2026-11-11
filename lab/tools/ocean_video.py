"""Deterministic screenshot/video export of measured ocean observations.

No simulator or Core is advanced. Recorded samples are held, never interpolated
into invented motion. The validated plan is also an Agent-facing Python API.
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, Field, model_validator

from lab.tools.ocean import difference
from lab.tools.ocean_contact import capsule, ContactBody
from lab.tools.ocean_cli import read_json,write_json


class ExportPlan(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_id:str=Field(default='threemind.visual-export/1',alias='schema')
    title:str=Field(default='ThreeMind',max_length=200)
    start_s:float=Field(default=0,ge=0,allow_inf_nan=False)
    end_s:float|None=Field(default=None,gt=0,allow_inf_nan=False)
    width:int=Field(default=1280,ge=480,le=1920)
    height:int=Field(default=900,ge=480,le=1080)
    fps:int=Field(default=20,ge=1,le=30)
    speed:float=Field(default=1,ge=.1,le=20,allow_inf_nan=False)
    focus:int|None=Field(default=0,ge=0)
    view_m:float|None=Field(default=.20,gt=0,allow_inf_nan=False)
    show_title:bool=True
    show_legend:bool=True
    show_world:bool=True
    show_generation:bool=True
    show_time:bool=True
    show_trail:bool=True
    show_population:bool=True
    show_evolution:bool=False
    inset_m:float|None=Field(default=None,gt=0,allow_inf_nan=False)
    @model_validator(mode='after')
    def valid(self):
        if self.schema_id!='threemind.visual-export/1':raise ValueError('unsupported visual export schema')
        if self.width%2 or self.height%2:raise ValueError('video dimensions must be even')
        if self.end_s is not None and self.end_s<=self.start_s:raise ValueError('end must follow start')
        if self.inset_m is not None and (self.view_m is not None or self.focus is None or self.width<1200):
            raise ValueError('focal inset requires full-habitat view, a focus and width >= 1200')
        if self.show_evolution and (self.inset_m is not None or self.view_m is not None or self.width<1200):
            raise ValueError('evolution panel requires a full-habitat view and width >= 1200')
        return self


def load_recording(folder):
    folder=Path(folder)
    if (folder/'assay.json').exists():
        info=read_json(folder/'assay.json')
        with gzip.open(folder/'trajectory.json.gz','rt',encoding='utf-8') as f:rows=json.load(f)
        frames=[{'t':r['t'],'time_us':r['world_time_us'],'members':r['bodies'],
                 'food':r['food_positions']} for r in rows if 'bodies' in r]
        return {'case':folder.name,'protocol':info['protocol'],'frames':frames,
                'events':read_json(folder/'events.json'),'sampling':'recorded 100 ms samples; held without interpolation'}
    with gzip.open(folder/'trajectory.jsonl.gz','rt',encoding='utf-8') as f:rows=[json.loads(line) for line in f]
    first=rows[0]['time_us']
    return {'case':folder.name,'protocol':read_json(folder/'protocol.json'),
            'frames':[{'t':(r['time_us']-first)/1e6,'time_us':r['time_us'],'members':r['members'],
                       'food':r['food_positions']} for r in rows],
            'events':read_json(folder/'events.json'),'sampling':'recorded samples; held without interpolation'}


def font(size):
    for path in ('C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():return ImageFont.truetype(path,size)
    return ImageFont.load_default(size=size)


class Renderer:
    def __init__(self,recording,plan):
        self.r,self.p=recording,plan
        self.times=[x['t'] for x in recording['frames']]
        if not self.times:raise ValueError('empty recording')
        self.font,self.small,self.heading=font(21),font(17),font(30)
        self.inset=None
        if plan.inset_m is not None:
            self.inset=Renderer(recording,plan.model_copy(update={'width':480,'height':480,'view_m':plan.inset_m,
                'inset_m':None,'show_title':False,'show_population':False,'show_legend':False,
                'show_world':False,'show_generation':False,'show_time':False}))
    def frame(self,at):
        p,r=self.p,self.r
        k=max(0,bisect.bisect_right(self.times,at)-1);f=r['frames'][k]
        image=Image.new('RGB',(p.width,p.height),'#eff5f2');d=ImageDraw.Draw(image)
        header=65 if p.show_title else 16
        footer=130
        size=min(p.width-42,p.height-header-footer);left=24 if p.inset_m or p.show_evolution else (p.width-size)//2;top=header
        d.rectangle((left,top,left+size,top+size),fill='#dcece8',outline='#aac8bd',width=2)
        members=f['members'];focus=next((b for b in members if b['id']==p.focus),None)
        center=np.asarray(focus['position'] if focus and p.view_m else [r['protocol']['side_m']/2]*2)
        side=r['protocol']['side_m'];span=p.view_m or side;scale=size/span
        def xy(pos):
            delta=difference(pos,center,side)
            return (left+size/2+delta[0]*scale,top+size/2-delta[1]*scale)
        # Fixed-coordinate reference grid makes a following camera explicit.
        spacing=.025 if span<.4 else .1
        for axis in (0,1):
            for coordinate in np.arange(0,side+spacing/2,spacing):
                pos=center.copy();pos[axis]=coordinate
                q=xy(pos)[axis]
                if axis==0 and left<=q<=left+size:d.line((q,top,q,top+size),fill='#cadfd6')
                if axis==1 and top<=q<=top+size:d.line((left,q,left+size,q),fill='#cadfd6')
        if p.show_trail and focus:
            track=[]
            for previous in r['frames'][max(0,k-40):k+1]:
                b=next((b for b in previous['members'] if b['id']==p.focus),None)
                if b:track.append(xy(b['position']))
            for a,b in zip(track,track[1:]):
                # Do not join opposite periodic images with a fictitious long line.
                if math.dist(a,b)<side*scale/2:d.line((a,b),fill='#509c83',width=3)
        radius=max(2,r['protocol']['nutrient_radius_m']*scale)
        for point in f['food']:
            x,y=xy(point)
            if left<=x<=left+size and top<=y<=top+size:d.ellipse((x-radius,y-radius,x+radius,y+radius),fill='#c2982f')
        for body in members:
            if not body['physical']:continue
            x,y=xy(body['position'])
            if x<left-30 or x>left+size+30 or y<top-30 or y>top+size+30:continue
            rad=body['radius']/math.sqrt(1+4*body.get('elongation',0)/math.pi)
            half=body.get('elongation',0)*rad
            angle=body['angle'];hx,hy=half*scale*math.cos(angle),-half*scale*math.sin(angle)
            # Unwrap the entire capsule around its center. Independently wrapping
            # its endpoints draws a fictitious world-spanning bar at a seam.
            thick=max(2,round(rad*scale*2))
            color=({'core':'#297d67','random-shadow':'#8b6a9c','random-stopped':'#377aa3'}.get(body.get('controller'))
                   or ('#297d67' if body['id']==p.focus else '#8b6a9c'))
            if p.show_evolution:color=GENERATION_COLORS[min(body['generation'],len(GENERATION_COLORS)-1)]
            shell=max(1,round(1+body.get('shell',0)*6))
            offsets=(-side*scale,0.,side*scale) if p.view_m is None else (0.,)
            margin=(half+rad)*scale+shell
            for dx in offsets:
                for dy in offsets:
                    cx,cy=x+dx,y+dy
                    if cx+margin<left or cx-margin>left+size or cy+margin<top or cy-margin>top+size:continue
                    x1,y1,x2,y2=cx-hx,cy-hy,cx+hx,cy+hy
                    d.line((x1,y1,x2,y2),fill='#384b47',width=thick+2*shell)
                    for qx,qy in ((x1,y1),(x2,y2)):
                        rr=thick/2+shell;d.ellipse((qx-rr,qy-rr,qx+rr,qy+rr),fill='#384b47')
                    d.line((x1,y1,x2,y2),fill=color,width=thick)
                    for qx,qy in ((x1,y1),(x2,y2)):
                        rr=thick/2;d.ellipse((qx-rr,qy-rr,qx+rr,qy+rr),fill=color)
                    d.line((cx,cy,cx+rad*scale*math.cos(angle),cy-rad*scale*math.sin(angle)),fill='white',width=2)
                    d.text((cx+thick/2+5,cy-thick/2),str(body['id']),font=self.small,fill='#143d34')
        # Clip trajectories, bodies and labels to the physical viewport.
        panel=image.crop((left,top,left+size+1,top+size+1))
        image=Image.new('RGB',(p.width,p.height),'#eff5f2');image.paste(panel,(left,top));d=ImageDraw.Draw(image)
        if p.show_evolution:self.evolution_panel(d,f,left+size+26,top,p.width-left-size-48)
        if p.inset_m is not None:
            # A supplemental view never replaces or crops the complete habitat.
            detail=self.inset.frame(at).crop((73,16,408,351))
            x=left+size+32;inset_size=min(p.width-x-24,335)
            image.paste(detail.resize((inset_size,inset_size)),(x,top+38));d=ImageDraw.Draw(image)
            d.text((x,top),f'局部放大 · {p.inset_m:g} m',font=self.font,fill='#143d34')
            d.text((x,top+inset_size+56),'左侧始终保留完整海洋',font=self.small,fill='#294f43')
            if focus:
                for j,text in enumerate((f"个体 {focus['id']} · 第 {focus['generation']} 代",
                    f"摄食 {focus['grains']} · 捕获 {focus.get('captured',0)}",
                    f"当前存活 {sum(b['physical'] for b in members)} · 营养 {len(f['food'])}")):
                    d.text((x,top+inset_size+92+j*30),text,font=self.small,fill='#294f43')
        if p.show_title:d.text((22,16),p.title,fill='#143d34',font=self.heading)
        if focus and not focus['physical']:
            d.text((left+18,top+18),f"个体 {p.focus} 已被捕获" if focus.get('consumed_by') is not None else f"个体 {p.focus} 已停止躯体活动",font=self.font,fill='#973d37')
        lines=[]
        if p.show_time:
            population=f" · 存活 {sum(b['physical'] for b in members)} · 营养 {len(f['food'])}" if p.show_population else ''
            lines.append(f"模拟时间 {f['time_us']/1e6:.2f} s · 片段 {at:.2f} s · {p.speed:g}×"+population)
        if p.show_world:
            version=r['protocol'].get('schema','threemind.ocean/3').removeprefix('threemind.')
            lines.append(f"{version} · 二维水层 {side:g} m · seed {r['protocol']['environment_seed']} · {r['case']}")
        if p.show_generation and focus:lines.append(f"个体 {focus['id']} · 第 {focus['generation']} 代 · 摄食 {focus['grains']} · 捕获 {focus.get('captured',0)}")
        if p.show_legend:
            if p.show_evolution:
                controls={b.get('controller',r['protocol'].get('mode')) for b in members}
                prefix='全部意识驱动 · ' if controls=={'core'} else ''
                lines.append(prefix+'颜色表示代次（见右栏） · 金色：营养 · 深色边缘：外壳')
            elif any('controller' in b for b in members):
                counts={c:sum(b['physical'] and b.get('controller')==c for b in members)
                        for c in ('core','random-shadow','random-stopped')}
                lines.append(f"绿：意识 {counts['core']}  紫：随机保留耗能 {counts['random-shadow']}  蓝：随机停核 {counts['random-stopped']}  金：营养")
            else:lines.append('绿色：焦点个体  紫色：邻体  金色：营养  深色边缘：外壳  线：实测轨迹')
        for j,text in enumerate(lines):d.text((22,top+size+12+j*26),text,font=self.small,fill='#294f43')
        return image

    def evolution_panel(self,d,f,x,y,width):
        """Measured ancestry and sizes; no simulated state is changed."""
        members=f['members'];alive=[b for b in members if b['physical']]
        rows={b['id']:b for b in members}
        d.text((x,y),'代际变化 · 完整海洋',font=self.font,fill='#143d34');y+=34
        protocol=self.r['protocol']
        if not protocol.get('predation',True):mode='互相吞食关闭 · 营养觅食培养'
        elif protocol.get('enclosure_fraction',1)<1:
            mode=f"覆盖至少{protocol['enclosure_fraction']*100:g}%后吞食；接触不吞食"
        else:mode=('仅完全包裹吞食；接触不会吞食' if not protocol.get('capture_enabled',True)
                   else '接触捕获与包裹吞食均开启')
        d.text((x,y),mode,font=self.small,fill='#294f43');y+=30
        d.text((x,y),f"出生 {sum(b['parent'] is not None for b in members)} · 吞食 {sum(b.get('captured',0) for b in members)}",font=self.small,fill='#294f43');y+=32
        counts={g:sum(b['generation']==g for b in alive) for g in sorted({b['generation'] for b in alive})}
        for g,n in list(counts.items())[:8]:
            color=GENERATION_COLORS[min(g,len(GENERATION_COLORS)-1)]
            d.rectangle((x,y+5,x+16,y+21),fill=color)
            d.text((x+25,y),f'第 {g} 代 · 存活 {n}',font=self.small,fill='#294f43');y+=27
        if not alive:return
        radii=sorted(b['radius']*1000 for b in alive)
        y+=12;d.text((x,y),'存活个体的等面积半径（毫米）',font=self.small,fill='#143d34');y+=28
        d.text((x,y),f'最小 {radii[0]:.2f} · 中位 {float(np.median(radii)):.2f} · 最大 {radii[-1]:.2f}',font=self.small,fill='#294f43');y+=40
        chosen=min(alive,key=lambda b:(-b['generation'],b['id']))
        chain=[chosen]
        while chain[-1]['parent'] in rows:chain.append(rows[chain[-1]['parent']])
        d.text((x,y),'示例谱系 · 当前最深代次',font=self.font,fill='#143d34');y+=29
        d.text((x,y),'从亲代继承，再随机变化；不是每代变大',font=self.small,fill='#294f43');y+=31
        for b in list(reversed(chain))[-6:]:
            text=f"#{b['id']}  第{b['generation']}代  半径 {b['radius']*1000:.2f}"
            d.text((x,y),text,font=self.small,fill='#294f43');y+=24
            d.text((x+12,y),f"外壳 {b.get('shell',0):.2f} · 伸长 {b.get('elongation',0):.2f}",font=self.small,fill='#516c62');y+=29


GENERATION_COLORS=('#297d67','#2f899c','#647cc4','#9b65ac','#bc7442','#83942c','#a55361','#4c4c79')


def export_recording(folder,output,plan,*,at=None,ffmpeg=None):
    plan=plan if isinstance(plan,ExportPlan) else ExportPlan.model_validate(plan)
    output=Path(output)
    if output.exists():raise ValueError('new export path required')
    output.parent.mkdir(parents=True,exist_ok=True)
    recording=load_recording(folder);renderer=Renderer(recording,plan)
    samples=renderer.times;dt=samples[-1]-samples[-2] if len(samples)>1 else .1
    end=plan.end_s if plan.end_s is not None else samples[-1]+dt
    if plan.start_s<samples[0] or end>samples[-1]+dt+1e-8:raise ValueError('requested interval exceeds actual recording')
    duration=(end-plan.start_s)/plan.speed
    if duration>300 or duration<=0:raise ValueError('export duration must be within 300 seconds')
    if output.suffix.lower()=='.png':
        value=plan.start_s if at is None else at
        if not samples[0]<=value<samples[-1]+dt:raise ValueError('screenshot outside recording')
        renderer.frame(value).save(output)
    elif output.suffix.lower()=='.mp4':
        encoder=ffmpeg or shutil.which('ffmpeg')
        if not encoder:raise RuntimeError('FFmpeg unavailable; PNG export remains available')
        command=[str(encoder),'-v','error','-nostdin','-n','-f','rawvideo','-pix_fmt','rgb24',
                 '-s',f'{plan.width}x{plan.height}','-r',str(plan.fps),'-i','pipe:0','-an',
                 '-c:v','libx264','-threads','2','-preset','fast','-crf','21','-pix_fmt','yuv420p',
                 '-movflags','+faststart',str(output)]
        with subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE) as child:
            try:
                for n in range(max(1,math.ceil(duration*plan.fps-1e-8))):
                    child.stdin.write(renderer.frame(plan.start_s+n*plan.speed/plan.fps).tobytes())
                child.stdin.close()
                error=child.stderr.read().decode(errors='replace')
                code=child.wait(timeout=60)
                if code:raise RuntimeError(error)
            except BaseException:
                child.kill();child.wait();raise
    else:raise ValueError('supported exports: PNG or MP4')
    receipt={'schema':'threemind.visual-export-receipt/1','source':str(Path(folder).resolve()),
             'renderer_version':'ocean-observation/6',
             'plan':plan.model_dump(by_alias=True),'source_sampling':recording['sampling'],
             'source_samples':len(samples),'recorded_interval':[samples[0],samples[-1]+dt],
             'image_at_s':at,'output_bytes':output.stat().st_size,'core_advanced':False,
             'interpolation':False}
    write_json(output.with_suffix(output.suffix+'.json'),receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path,nargs='?');p.add_argument('output',type=Path,nargs='?')
    p.add_argument('--plan',type=Path);p.add_argument('--at',type=float);p.add_argument('--template',action='store_true')
    args=p.parse_args()
    if args.template:print(ExportPlan().model_dump_json(by_alias=True,indent=2))
    else:
        if not args.source or not args.output:p.error('source and output are required')
        print(json.dumps(export_recording(args.source,args.output,read_json(args.plan) if args.plan else {},at=args.at),ensure_ascii=False))
