"""Render the two completed E68 arms into full-frame HTML chapters and MP4s.

This is an observational exporter. It never creates a subject or advances Core.
Scene drawings are labeled schematics. Retinal colors, times and answers are
the recorded values; frames are held without invented interpolation.
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont
from lab.tools.active_vision_replay import pack

ARMS = ('2', '3.1')
LABELS = {'2':'continuous-memory/2', '3.1':'continuous-memory/3.1',
          '4-adaptive':'continuous-memory/4 · adaptive-half-life',
          '4-legacy':'continuous-memory/4 · legacy-stability'}
STAGES = ['initial-teaching','initial-calibration','development-0']
for r in range(1,4): STAGES += [f'correction-{r}',f'calibration-{r}',f'development-{r}']
STAGES += ['final']
COLORS = ['#ec5353','#e5c749','#416ad6','#46a966','#a5b5b0']
WORDS = ['球体','圆柱体','立方体','圆锥体','红色','黄色','蓝色','绿色']
NAMES = {'initial-teaching':'初次教学与复习','initial-calibration':'初次外设校准采样',
         'development-0':'初教后的开发测试','final':'最终留出位置测试'}
for r in range(1,4):
    NAMES.update({f'correction-{r}':f'第 {r} 轮纠错与强化',
                  f'calibration-{r}':f'第 {r} 轮外设校准采样',
                  f'development-{r}':f'第 {r} 轮后的开发测试'})


def read(path): return json.loads(Path(path).read_bytes())


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024**2): h.update(chunk)
    return h.hexdigest()


def font(size): return ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',size)


class Renderer:
    def __init__(self, trace=()):
        self.trace = trace
        self.times = [f['core_t'] for f in trace]
        self.heading,self.normal,self.small=font(27),font(21),font(16)

    def calibration_summary(self,arm,stage,result):
        if result.get('physical_core_unchanged') is not True:
            raise ValueError('calibration continuity was not verified')
        im=Image.new('RGB',(1280,1024),'#eff5f2');d=ImageDraw.Draw(im)
        d.text((40,28),LABELS[arm],font=self.heading,fill='#153f38')
        d.text((40,76),'个人表达器继续校准 · 已保存结果摘要',font=self.heading,fill='#153f38')
        d.rounded_rectangle((35,140,1245,711),16,fill='white')
        lines=[
            ('阶段：'+stage,190),
            (f"校准材料：{result['n']} 条，保留此前全部材料",251),
            (f"本阶段计算 {result['updates']} 步；累计计算 {result['computed_updates']} 步",312),
            (f"保留的学习状态：第 {result['committed_updates']} 步，包含对应优化器与随机状态",373),
            (f"训练材料正确 {result['training_correct']}/{result['n']}；训练损失 {result['loss']:.6f}",434),
            ('保留最后一步权重、优化器及随机状态；不回退选点。',495),
            (f"Core 与身体未推进：Core 时间保持在 {int(result['time_us'])/1e6:.2f} 秒",556),
            ('以下继续播放完整开发题测试，实际成绩另行计算。',617),
        ]
        for line,y in lines:d.text((62,y),line,font=self.normal,fill='#153f38')
        d.text((40,748),'E68 · 读取已保存的拟合结果；不补画活动，不重新训练或模拟。',font=self.small,fill='#55786e')
        d.text((45,820),'外设计算时内部模拟时钟暂停；此处不生成未测活动曲线。',font=self.normal,fill='#55786e')
        return im

    def frame(self,arm,stage,clip,frame,retinas,index,total,speed,answer_hold=False):
        im=Image.new('RGB',(1280,1024),'#eff5f2');d=ImageDraw.Draw(im)
        def text(x,y,value,size='normal',fill='#153f38'):
            d.text((x,y),str(value),font=getattr(self,size),fill=fill)
        text(28,18,LABELS[arm],'heading')
        text(28,59,f'{NAMES[stage]} · 片段 {index+1}/{total}',fill='#55786e')
        t=frame.get('core_t');text(845,27,f'Core {t:.2f} s' if t is not None else 'Core 时间未记录')
        text(845,59,'答案停留（不推进模拟）' if answer_hold else f'记录回放 {speed:g}×',fill='#55786e')
        d.rounded_rectangle((25,102,608,585),14,fill='white')
        d.rounded_rectangle((628,102,1254,585),14,fill='white')
        text(45,118,'物理场景示意 · 不参与意识读出')
        text(650,118,'真实视网膜采样 · 68 个受体')
        def xy(point):return (315+point[0]*185,360-point[1]*185)
        for i,(shape,color) in enumerate(frame['items']):
            x,y=xy(frame['positions'][i]);fill=COLORS[color]
            if shape==0:d.ellipse((x-30,y-30,x+30,y+30),fill=fill)
            elif shape==1:
                d.rectangle((x-27,y-27,x+27,y+27),fill=fill)
                d.ellipse((x-27,y-37,x+27,y-17),fill=fill,outline='#476b60',width=2)
                d.arc((x-27,y+17,x+27,y+37),0,180,fill='#476b60',width=2)
            elif shape==3:d.polygon(((x,y-37),(x-30,y+30),(x+30,y+30)),fill=fill)
            else:d.rectangle((x-30,y-30,x+30,y+30),fill=fill)
        c=frame['camera'];retina=retinas[frame['retina']];half=retina['half_width']
        def ground(u,v):
            direction=[c['forward'][i]+u*c['right'][i]+v*c['up'][i] for i in range(3)]
            k=(.16-c['origin_m'][2])/direction[2]
            return xy([c['origin_m'][i]+k*direction[i] for i in range(2)])
        points=[ground(u,v) for u,v in [(-half,-half),(half,-half),(half,half),(-half,half),(-half,-half)]]
        d.line(points,fill='#439880',width=2)
        x,y=ground(0,0);d.line((x-7,y,x+7,y),fill='#207f69',width=2);d.line((x,y-7,x,y+7),fill='#207f69',width=2)
        x,y=xy(frame['p']);d.ellipse((x-6,y-6,x+6,y+6),fill='#197f70')
        text(45,520,'固定眼手；绿色框为中央清晰范围','small')
        text(45,548,'同一个体连续作答；题目经历保留到下一题','small')
        left,top,size=650,191,280;a=retina['aperture']
        for j,((u,v),(w,h)) in enumerate(zip(retina['centers'],retina['widths'])):
            rgb=tuple(max(0,min(255,round(x*255))) for x in frame['values'][4*j+1:4*j+4])
            x=left+(u-w/2+a)/(2*a)*size;y=top+(a-v-h/2)/(2*a)*size
            d.rectangle((x,y,x+w/(2*a)*size,y+h/(2*a)*size),fill=rgb,outline='#d6e4dd',width=1)
        text(980,174,'中央区域放大','small')
        text(980,199,'同一组真实采样','small')
        for j,((u,v),(w,h)) in enumerate(zip(retina['centers'],retina['widths'])):
            if abs(u)>half or abs(v)>half:continue
            rgb=tuple(max(0,min(255,round(x*255))) for x in frame['values'][4*j+1:4*j+4])
            x=980+(u-w/2+half)/(2*half)*235;y=234+(half-v-h/2)/(2*half)*235
            d.rectangle((x,y,x+w/(2*half)*235,y+h/(2*half)*235),fill=rgb,outline='#d6e4dd',width=1)
        totals=frame['totals']
        text(650,512,f"激活 {totals['activation']:.3f} · 抑制 {totals['inhibition']:.3f}",'small')
        text(650,542,f"直接触达 {totals['direct']:.3f} · 联想触达 {totals['associative']:.3f}",'small')
        d.rounded_rectangle((25,601,1254,756),14,fill='white')
        utterance=frame.get('teacher_utterance') or clip['label']
        if clip['kind']=='interval':utterance='没有教师文字；物体与物理背景仍然可见'
        prefix='教师' if clip['kind']=='teaching' else '提问' if clip['kind'] in ('question','student-reanswer') else '间隔'
        text(45,619,f'{prefix}：{utterance}','heading')
        expression=frame.get('expression');result=clip.get('result') or {}
        if expression:
            answer=expression.get('word') or '未产生回答'
            text(45,663,'意识及其个人表达器：'+answer,'heading')
            if 'calibration' in stage:
                text(700,671,'外设校准材料采集，非正式成绩',fill='#6e786b')
            elif 'correct' in result:
                expected=WORDS[result['label']]
                text(700,671,('答对' if result['correct'] else '答错')+' · 评分标准：'+expected,
                     fill='#16765e' if result['correct'] else '#b04536')
        else:text(45,671,'本帧没有记录问句结束回答','small',fill='#647f74')
        self.curves(d, frame.get('core_t'))
        text(28,998,'E68 · 原始记录驱动；不重新模拟、不补画行为。完整逐帧资料另见同目录 HTML。','small')
        return im


    def curves(self, draw, now):
        draw.rounded_rectangle((25,767,1254,987),14,fill='white')
        draw.text((42,775),'意识活动 · 真实内部模拟秒 · 最近30秒 · 原始总量，共用线性纵轴',font=self.small,fill='#153f38')
        if now is None or not self.trace:
            draw.text((70,830),'本帧无可用活动记录',font=self.normal,fill='#55786e');return
        left=max(0.,now-30.);right=max(30.,now)
        lo=max(0,bisect.bisect_left(self.times,left)-1);hi=bisect.bisect_right(self.times,now)
        rows=self.trace[lo:hi]
        fields=[('activation','激活','#199c73'),('inhibition','抑制','#df7046'),
                ('direct','直接触达','#438dde'),('associative','联想触达','#8f65cc')]
        maximum=max([float(f['totals'][k]) for f in rows for k,_,_ in fields]+[.001])
        x0,x1,y0,y1=85,1223,823,948
        for fraction in (0,.5,1):
            y=y1-(y1-y0)*fraction
            draw.line((x0,y,x1,y),fill='#e2eae5')
            draw.text((29,y-8),f'{maximum*fraction:.1f}',font=self.small,fill='#668478')
        for k,label,color in fields:
            pts=[(x0+(f['core_t']-left)/(right-left)*(x1-x0),y1-float(f['totals'][k])/maximum*(y1-y0))
                 for f in rows if f['core_t']>=left]
            if len(pts)>1:draw.line(pts,fill=color,width=2)
        x=x0+(now-left)/(right-left)*(x1-x0)
        draw.line((x,y0,x,y1),fill='#253d33',width=2)
        for frac in (0,.25,.5,.75,1):
            draw.text((x0+frac*(x1-x0)-12,955),f'{left+frac*(right-left):.1f}',font=self.small,fill='#668478')
        for i,(key,label,color) in enumerate(fields):
            value=rows[-1]['totals'][key] if rows else 0
            draw.text((100+i*282,797),f'{label} {value:.3f}',font=self.small,fill=color)


def activity_trace(work,arm):
    """One monotonically timed series across all ordinary chapters, never rerun."""
    trace=[];previous=0.
    for stage in STAGES:
        paths=sorted((work/'arms'/arm/stage/'clips').glob('*.json.gz'))
        if not paths:raise ValueError('missing stage '+stage)
        for path in paths:
            with gzip.open(path,'rt',encoding='utf-8') as f:record=json.load(f)
            for row in record['process']:
                t=int(row['activity']['time_us'])/1e6
                if t<=previous:raise ValueError('noncontinuous replay time: '+str(path))
                if abs(t-previous-.05)>1e-7:raise ValueError('missing sampled internal time: '+str(path))
                totals={k:sum(float(n[k]) for n in row['activity']['nodes'])
                        for k in ('activation','inhibition','direct','associative')}
                trace.append(dict(core_t=t,totals=totals,stage=stage));previous=t
    return trace


def speed_for(stage,clip):
    if stage=='final':return 1.,1.25
    if 'development' in stage:return 2.,.65
    if clip['kind']=='student-reanswer':return 2.,.65
    if 'calibration' in stage:return 4.,0.
    return 8.,0.


def export_arm(work,arm,ffmpeg,fps=10):
    out=work/'replays'/arm;out.mkdir(parents=True,exist_ok=True)
    final=out/'replay.mp4';receipt=out/'export.json'
    if final.exists() and receipt.exists():return read(receipt)
    if final.exists():raise ValueError('video without validated receipt; preserve and inspect '+str(final))
    temporary=out/'replay.partial.mp4'
    if temporary.exists():raise ValueError('interrupted video exists; inspect before resuming '+str(temporary))
    process=subprocess.Popen([str(ffmpeg),'-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
        '-s','1280x1024','-r',str(fps),'-i','-','-an','-c:v','libx264','-threads','2','-preset','fast',
        '-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(temporary)],stdin=subprocess.PIPE)
    trace=activity_trace(work,arm)
    renderer=Renderer(trace);count=0;chapters=[];sources=[];raw_frames=0;clips_total=0
    template=(ROOT/'lab/tools/active_vision_replay.html').read_text(encoding='utf-8')
    try:
        for stage in STAGES:
            paths=sorted((work/'arms'/arm/stage/'clips').glob('*.json.gz'))
            if not paths:raise ValueError('missing recorded stage '+stage)
            data=pack(paths,LABELS[arm]+' · '+NAMES[stage])
            for clip in data['clips']:
                clip['case']=stage;clip['case_label']=NAMES[stage]
                if clip['kind']=='interval':clip['label']='复习间隔：无教师文字，场景保持可见'
            original_count=sum(len(c['frames']) for c in data['clips']);raw_frames+=original_count
            chapter=dict(stage=stage,start_s=count/fps,clips=len(data['clips']),original_frames=original_count)
            payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
            htmlpath=out/(stage+'.html')
            with htmlpath.open('x',encoding='utf-8') as f:f.write(template.replace('__DATA__',payload))
            for index,clip in enumerate(data['clips']):
                frames=clip['frames'];speed,hold=speed_for(stage,clip)
                visible=max(1,math.ceil(len(frames)*clip['sample_interval_s']/speed*fps))
                for n in range(visible):
                    j=min(len(frames)-1,math.floor(n/fps*speed/clip['sample_interval_s']))
                    image=renderer.frame(arm,stage,clip,frames[j],data['retinas'],index,len(data['clips']),speed)
                    process.stdin.write(image.tobytes());count+=1
                if hold:
                    image=renderer.frame(arm,stage,clip,frames[-1],data['retinas'],index,len(data['clips']),speed,True)
                    if stage=='final' and index in (0,35,71):image.save(out/f'final-{index:02d}.png')
                    for _ in range(math.ceil(hold*fps)):process.stdin.write(image.tobytes());count+=1
                clips_total+=1
            chapter['end_s']=count/fps;chapters.append(chapter)
            sources.extend({'path':p.relative_to(work).as_posix(),'sha256':digest(p)} for p in paths)
            print(json.dumps({'video':arm,'chapter':stage,'seconds':count/fps}),flush=True)
            if 'calibration' in stage:
                fit_stage='initial-fit' if stage=='initial-calibration' else stage.replace('calibration','fit')
                fit_path=work/'arms'/arm/fit_stage/'result.json'
                summary=renderer.calibration_summary(arm,fit_stage,read(fit_path))
                summary.save(out/(fit_stage+'.png'))
                start=count/fps
                for _ in range(4*fps):process.stdin.write(summary.tobytes());count+=1
                chapters.append(dict(stage=fit_stage,kind='calibration-summary',start_s=start,end_s=count/fps,
                                     clips=0,original_frames=0,source=fit_path.relative_to(work).as_posix()))
                sources.append(dict(path=fit_path.relative_to(work).as_posix(),sha256=digest(fit_path)))
                print(json.dumps({'video':arm,'chapter':fit_stage,'seconds':count/fps}),flush=True)
        process.stdin.close()
        if process.wait()!=0:raise RuntimeError('FFmpeg export failed')
    except BaseException:
        process.stdin.close();process.wait()
        raise
    probe=subprocess.run([str(Path(ffmpeg).with_name('ffprobe.exe')),'-v','error','-show_streams','-show_format',
                         '-of','json',str(temporary)],check=True,capture_output=True)
    info=json.loads(probe.stdout);video=next(v for v in info['streams'] if v['codec_type']=='video')
    assert video['codec_name']=='h264' and video['width']==1280 and video['height']==1024
    assert abs(float(info['format']['duration'])-count/fps)<.15
    temporary.rename(final)
    result=dict(arm=arm,video=final.relative_to(work).as_posix(),sha256=digest(final),fps=fps,
        video_frames=count,duration_s=count/fps,original_frames=raw_frames,clips=clips_total,chapters=chapters,
        sources=sources,activity_curves=['activation','inhibition','direct','associative'],
        curve_time='actual simulated time; continuous across questions',renderer_sha256=digest(Path(__file__)),core_advanced=False,
        playback='teaching 8x, calibration 4x, development 2x, final 1x; explicit answer holds and four-second calibration summaries; 10 fps sample-and-hold')
    receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--ffmpeg',type=Path,default=Path('D:/DevTools/ffmpeg/bin/ffmpeg.exe'))
    p.add_argument('--arm',choices=ARMS);args=p.parse_args();results=[]
    for arm in ([args.arm] if args.arm else ARMS):results.append(export_arm(args.work.resolve(),arm,args.ffmpeg))
    if not args.arm:
        lines=['<!doctype html><meta charset="utf-8"><title>E68 两组形色实验回放</title>',
            '<style>body{font:18px system-ui;margin:40px;color:#153f38;background:#eff5f2}a{color:#147e68}li{margin:12px}</style>',
            '<h1>E68 · /2 与 /3.1 形色教学与测试</h1><p>视频按章节完整呈现；HTML保留全部采样帧。回放不运行意识。两组从新完整空白个体开始；全程连续。视频下方附真实活动曲线。</p>']
        for arm in ARMS:
            lines += [f'<h2>{html.escape(LABELS[arm])}</h2><p><a href="{arm}/replay.mp4">观看 MP4</a></p><ul>']
            for stage in STAGES:lines.append(f'<li><a href="{arm}/{stage}.html">{NAMES[stage]}</a></li>')
            lines.append('</ul>')
            lines.append('<p>表达器拟合摘要（非测试成绩，不推进模拟）：')
            for fit in ['initial-fit',*[f'fit-{r}' for r in range(1,4)]]:
                lines.append(f'<a href="{arm}/{fit}.png">{fit}</a> · ')
            lines.append('</p>')
        (args.work/'replays/index.html').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps([{'arm':r['arm'],'duration_s':r['duration_s'],'clips':r['clips']} for r in results]))


if __name__=='__main__':main()
