"""Record-driven E69 eye/hand replay, HTML and MP4. No simulation imports."""
from __future__ import annotations

import argparse
import bisect
import csv
import html
import json
import math
import subprocess
from itertools import pairwise
from pathlib import Path

from analyze import FIELDS, load_clip, ordered_clips, require, score_path
from journal import fixed_json, put, read, sha
from PIL import Image, ImageDraw, ImageFont

SIZE = (1440, 1080)
COLORS = ('#e85252', '#dfbf35', '#3976d4', '#44a965', '#a9b4b0')
WORDS = ('球体', '圆柱体', '立方体', '圆锥体', '红色', '黄色', '蓝色', '绿色')
CURVES = (('activation', '激活', '#199c73'), ('inhibition', '抑制', '#df7046'),
          ('direct', '直接触达', '#438dde'), ('associative', '联想触达', '#8f65cc'))


def pack(path):
    record = load_clip(path)
    result_path = score_path(path)
    value = {'stage': path.parents[1].name, 'kind': record.get('kind', 'recorded'),
             'task': record.get('task') or {}, 'score': read(result_path) if result_path.exists() else {}, 'frames': []}
    for row in record['process']:
        ob = row['observation']
        value['frames'].append({
            't': int(row['activity']['time_us']) / 1e6, 'world_t': ob['time_s'],
            'items': ob['items'], 'positions': ob['positions'],
            'pointer': [ob['pointer']['x'], ob['pointer']['y']], 'marker': ob.get('teacher_marker'),
            'camera': ob['camera'], 'eye': ob['eye_angle_rad'], 'velocity': ob['eye_velocity_rad_s'],
            'centers': ob['retinal_centers'], 'widths': ob['retinal_widths'],
            'half_width': ob['eye_config']['center_half_width'], 'aperture': ob['eye_config']['aperture'],
            'values': ob['values'][:4 * len(ob['retinal_centers'])],
            'totals': {key: sum(float(n[key]) for n in row['activity']['nodes']) for key in FIELDS},
            'own_intent': row.get('own_intent'), 'own_eye': row.get('own_eye_action'),
            'own_hand': row.get('own_hand_action'), 'eye_action': row.get('eye_action'),
            'hand_action': row.get('hand_action'), 'assistance': row.get('assistance'),
            'teacher_eye': row.get('teacher_eye_action'), 'teacher_hand': row.get('teacher_hand_action'),
            'utterance': row.get('utterance', ''), 'expression': row.get('expression'),
            'executor': row.get('executor')})
    require(bool(value['frames']), 'empty replay clip')
    return value


def font(size):
    for path in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf'):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise ValueError('a Chinese font is required for legible evidence video')


def point(camera, u, v):
    direction = [camera['forward'][i] + u * camera['right'][i] + v * camera['up'][i] for i in range(3)]
    if abs(direction[2]) < 1e-8:
        return None
    scale = (.16 - camera['origin_m'][2]) / direction[2]
    if scale < 0:
        return None
    return [camera['origin_m'][i] + scale * direction[i] for i in range(2)]


def vector(value):
    return '本帧未另记' if value is None else ' / '.join(f'{x:+.3f}' for x in value)


class Renderer:
    def __init__(self, trace):
        self.trace = trace
        self.times = [f['t'] for f in trace]
        self.heading, self.normal, self.small = font(25), font(20), font(16)

    def frame(self, clip, index, *, speed=1, hold=False):
        frame = clip['frames'][index]
        image = Image.new('RGB', SIZE, '#edf4f1')
        draw = ImageDraw.Draw(image)

        def text(x, y, value, *, small=False, color='#153f38'):
            draw.text((x, y), str(value), font=self.small if small else self.normal, fill=color)

        text(28, 15, 'E69 · continuous-memory/5.1 · 连续眼动、手眼协调、形色')
        text(28, 49, f"{clip['stage']} · {clip['kind']} · 第 {index + 1}/{len(clip['frames'])} 个真实采样", small=True)
        text(1070, 15, f"Core {frame['t']:.2f} s")
        text(1070, 47, '答案停留（不推进模拟）' if hold else f'记录回放 {speed:g}×', small=True)
        draw.rounded_rectangle((24, 85, 704, 587), 14, fill='white')
        draw.rounded_rectangle((724, 85, 1416, 587), 14, fill='white')
        text(44, 99, '物理场景示意 · 真值只作回放评分叠层')
        text(744, 99, '真实视网膜采样 · 右侧放大中央清晰区')

        def xy(p):
            return (364 + float(p[0]) * 220, 345 - float(p[1]) * 190)

        for shape_color, position in zip(frame['items'], frame['positions']):
            shape, color = shape_color
            x, y = xy(position)
            fill = COLORS[color]
            if shape == 0:
                draw.ellipse((x-26, y-26, x+26, y+26), fill=fill)
            elif shape == 1:
                draw.rectangle((x-23, y-23, x+23, y+23), fill=fill)
                draw.ellipse((x-23, y-31, x+23, y-13), fill=fill, outline='#3e665d', width=2)
                draw.arc((x-23, y+13, x+23, y+31), 0, 180, fill='#3e665d', width=2)
            elif shape == 3:
                draw.polygon(((x, y-30), (x-27, y+27), (x+27, y+27)), fill=fill)
            else:
                draw.rectangle((x-26, y-26, x+26, y+26), fill=fill)
        trail = [xy(f['pointer']) for f in clip['frames'][max(0, index-80):index+1]]
        if len(trail) > 1:
            draw.line(trail, fill='#86c7b6', width=3)
        x, y = xy(frame['pointer'])
        draw.ellipse((x-7, y-7, x+7, y+7), fill='#097c6c')
        if frame['marker'] is not None:
            x, y = xy(frame['marker'])
            draw.ellipse((x-10, y-10, x+10, y+10), fill='#d980dd', outline='#83428a', width=2)
        target = clip['task'].get('target')
        if target is not None:
            x, y = xy(frame['positions'][target])
            draw.ellipse((x-36, y-36, x+36, y+36), outline='#bf954b', width=2)
        half = frame['half_width']
        projection = [point(frame['camera'], u, v) for u, v in (
            (-half, -half), (half, -half), (half, half), (-half, half), (-half, -half))]
        if all(p is not None and max(abs(a) for a in p) < 4 for p in projection):
            draw.line([xy(p) for p in projection], fill='#1b986d', width=3)
        center = point(frame['camera'], 0, 0)
        if center is not None and max(abs(a) for a in center) < 3:
            x, y = xy(center)
            draw.line((x-9, y, x+9, y), fill='#095f48', width=2)
            draw.line((x, y-9, x, y+9), fill='#095f48', width=2)
        text(44, 514, '绿框/十字：清晰区/光轴；绿点/线：真实手位/轨迹', small=True)
        text(44, 541, '紫点：实际教师标记；金圈：评分目标（不输入意识）', small=True)
        text(44, 564, f"场景采样 {frame['world_t']:.2f} s；Core 数值为这一步接收后的状态", small=True)

        def retina(left, top, side, aperture, central=False):
            for i, ((u, v), (w, h)) in enumerate(zip(frame['centers'], frame['widths'])):
                if central and (abs(u) > half or abs(v) > half):
                    continue
                rgb = tuple(max(0, min(255, round(float(c)*255))) for c in frame['values'][4*i+1:4*i+4])
                x = left + (u-w/2+aperture)/(2*aperture)*side
                y = top + (aperture-v-h/2)/(2*aperture)*side
                draw.rectangle((x, y, x+w/(2*aperture)*side, y+h/(2*aperture)*side), fill=rgb, outline='#d6e4dd')
        retina(748, 162, 310, frame['aperture'])
        retina(1103, 196, 263, half, True)
        text(1103, 152, '同一批采样放大', small=True)
        text(746, 509, '眼位 rad：' + vector(frame['eye']), small=True)
        text(746, 540, '眼速度 rad/s：' + vector(frame['velocity']), small=True)
        draw.rounded_rectangle((24, 601, 1416, 819), 14, fill='white')
        utterance = frame['utterance'] or clip['task'].get('text') or '复习间隔：场景与身体继续，沿用自身命令'
        text(44, 615, '教师/问句：' + utterance[:55])
        intent = frame['own_intent']
        intent_text = ('本帧未记录新意图，实际执行命令如下' if intent is None else
                       f"眼选点 {intent['eye_receptor']}；手选点 {intent['hand_receptor']}；手 {'MOVE' if intent['move'] else 'WAIT'}")
        text(44, 650, intent_text, small=True)
        text(44, 678, '自身眼命令 ' + vector(frame['own_eye']) + '；自身手命令 ' + vector(frame['own_hand']), small=True)
        text(44, 705, '实际眼命令 ' + vector(frame['eye_action']) + '；实际手命令 ' + vector(frame['hand_action']), small=True)
        text(44, 734, '教师动作示范：' + ('有，已单独记录' if frame['assistance'] else '无'), small=True,
             color='#8b526b' if frame['assistance'] else '#16775d')
        expression = frame['expression']
        if expression and expression.get('selected') is not None:
            expected = expression.get('expected_for_scoring')
            answer = WORDS[expression['selected']]
            text(780, 651, '实际回答：' + answer, color='#153f38')
            text(780, 684, '期望（仅评分）：' + (WORDS[expected] if expected is not None else '不提问'), small=True)
        else:
            text(780, 651, '本帧未产生属性回答', small=True)
        if index == len(clip['frames'])-1 and clip['score']:
            result = clip['score']
            labels = [('eye_success', '注视'), ('hand_success', '指认'), ('eye_before_hand', '先看后指')]
            text(780, 721, ' · '.join(name + ('—' if result.get(key) is None else
                                            '✓' if result[key] else '×') for key, name in labels), small=True)
            assisted = 'autonomous_success' in result and result['autonomous_success'] is None
            value = result.get('autonomous_success', result.get('success'))
            text(780, 754, '辅助示范，不计自主成绩' if assisted else '自主结果：' + ('成功' if value else '未达标'),
                 color='#8b526b' if assisted else '#16775d' if value else '#b44939')
        text(44, 782, '测试不作教师纠正、不用真值控制动作；末态直接承接下一题。教学帮助独立标出。', small=True)
        self.curves(draw, frame['t'])
        text(28, 1054, 'E69 · 原件驱动，无重演、理想轨迹补画或内核推进。完整逐帧 HTML 与评分原件同时保存。', small=True)
        return image

    def curves(self, draw, now):
        draw.rounded_rectangle((24, 831, 1416, 1044), 14, fill='white')
        draw.text((43, 840), '四类真实活动 · 最近 30 个内部模拟秒 · 共用线性纵轴', font=self.small, fill='#153f38')
        left, right = max(0, now-30), max(30, now)
        rows = self.trace[max(0, bisect.bisect_left(self.times, left)-1):bisect.bisect_right(self.times, now)]
        maximum = max([float(row['totals'][key]) for row in rows for key in FIELDS] + [.001])
        x0, x1, y0, y1 = 85, 1374, 897, 1001
        for fraction in (0, .5, 1):
            y = y1 - fraction*(y1-y0)
            draw.line((x0, y, x1, y), fill='#e0ebe5')
            draw.text((30, y-8), f'{maximum*fraction:.1f}', font=self.small, fill='#668478')
        for j, (key, name, color) in enumerate(CURVES):
            points = [(x0+(row['t']-left)/(right-left)*(x1-x0), y1-row['totals'][key]/maximum*(y1-y0))
                      for row in rows if row['t'] >= left]
            if len(points) > 1:
                draw.line(points, fill=color, width=2)
            value = rows[-1]['totals'][key] if rows else 0
            draw.text((92+j*310, 867), f'{name} {value:.3f}', font=self.small, fill=color)
        for fraction in (0, .25, .5, .75, 1):
            draw.text((x0+fraction*(x1-x0)-14, 1013), f'{left+fraction*(right-left):.1f}', font=self.small, fill='#668478')


HTML = r'''<!doctype html><meta charset="utf-8"><title>E69 逐帧回放</title>
<style>body{margin:20px;background:#eef5f1;color:#153f38;font:17px system-ui}canvas{width:100%;max-width:1440px;background:white}button,select,input{font:inherit;margin:6px}small{display:block;max-width:1400px}#seek{width:55%}</style>
<h1>E69 · 真实眼手活动逐帧回放</h1><select id="clip"></select><div><button id="play">播放</button><input id="seek" type="range" min="0"><select id="speed"><option>1</option><option>2</option><option>4</option><option>8</option></select><span id="clock"></span></div><canvas id="view" width="1440" height="1080"></canvas>
<small>图为原件示意：绿框/十字是眼睛清晰区/光轴，绿点是手，紫点为真实教师标记，金圈仅标评分目标。浏览与拖动回放不改变意识。所有帧均保留，无插值造行为；四曲线采用本章真实活动。教师帮助与自身命令分别标记。</small>
<script>const DATA=__DATA__, $=x=>document.getElementById(x),ctx=$('view').getContext('2d'),colors=['#e85252','#dfbf35','#3976d4','#44a965','#a9b4b0'],words=['球体','圆柱体','立方体','圆锥体','红色','黄色','蓝色','绿色'];let ci=0,fi=0,playing=false,last=0,carry=0;
const curves=[['activation','激活','#199c73'],['inhibition','抑制','#df7046'],['direct','直接触达','#438dde'],['associative','联想触达','#8f65cc']],trace=DATA.clips.flatMap(c=>c.frames.map(f=>({t:f.t,totals:f.totals})));
function text(s,x,y,size=18,color='#153f38'){ctx.fillStyle=color;ctx.font=size+'px system-ui';ctx.fillText(s,x,y)}function line(ps,color,width=2){if(!ps.length)return;ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ps.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke()}function circle(x,y,r,color,stroke=false){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);if(stroke){ctx.strokeStyle=color;ctx.stroke()}else{ctx.fillStyle=color;ctx.fill()}}const xy=p=>[364+p[0]*220,345-p[1]*190],vec=v=>v==null?'本帧未另记':v.map(x=>Number(x).toFixed(3)).join(' / ');
function ground(c,u,v){const d=c.forward.map((x,i)=>x+u*c.right[i]+v*c.up[i]);if(Math.abs(d[2])<1e-8)return null;let k=(.16-c.origin_m[2])/d[2];return k<=0?null:c.origin_m.slice(0,2).map((x,i)=>x+k*d[i])}
function draw(){const c=DATA.clips[ci],f=c.frames[fi];ctx.fillStyle='#edf4f1';ctx.fillRect(0,0,1440,1080);ctx.fillStyle='white';ctx.fillRect(24,85,680,502);ctx.fillRect(724,85,692,502);ctx.fillRect(24,601,1392,218);ctx.fillRect(24,831,1392,213);text('E69 · continuous-memory/5.1 · '+c.stage,28,35,25);text('Core '+f.t.toFixed(2)+' s；场景采样 '+f.world_t.toFixed(2)+' s',880,35);text(c.kind+' · 真实第 '+(fi+1)+'/'+c.frames.length+' 帧',28,66);text('物理场景示意（评分叠层不输入意识）',44,120);text('真实视网膜 / 中央区放大',744,120);
c.frames.slice(Math.max(0,fi-80),fi+1).map(v=>v.pointer);line(c.frames.slice(Math.max(0,fi-80),fi+1).map(v=>xy(v.pointer)),'#86c7b6',3);f.items.forEach(([s,col],i)=>{let[x,y]=xy(f.positions[i]);ctx.fillStyle=colors[col];if(s===0)circle(x,y,26,colors[col]);else if(s===3){ctx.beginPath();ctx.moveTo(x,y-30);ctx.lineTo(x-27,y+27);ctx.lineTo(x+27,y+27);ctx.fill()}else{ctx.fillRect(x-26,y-26,52,52);if(s===1){ctx.beginPath();ctx.ellipse(x,y-22,26,9,0,0,Math.PI*2);ctx.strokeStyle='#45655c';ctx.stroke()}}});circle(...xy(f.pointer),7,'#087a6a');if(f.marker)circle(...xy(f.marker),10,'#d980dd');if(c.task.target!=null)circle(...xy(f.positions[c.task.target]),36,'#bf954b',true);let h=f.half_width,ps=[[-h,-h],[h,-h],[h,h],[-h,h],[-h,-h]].map(([u,v])=>ground(f.camera,u,v));if(ps.every(p=>p&&p.every(a=>Math.abs(a)<4)))line(ps.map(xy),'#179668',3);let center=ground(f.camera,0,0);if(center&&center.every(a=>Math.abs(a)<3)){let[x,y]=xy(center);line([[x-9,y],[x+9,y]],'#095f48');line([[x,y-9],[x,y+9]],'#095f48')}
function retina(l,t,size,a,central){f.centers.forEach(([u,v],i)=>{if(central&&(Math.abs(u)>h||Math.abs(v)>h))return;let[w,hh]=f.widths[i];ctx.fillStyle='rgb('+f.values.slice(i*4+1,i*4+4).map(x=>Math.max(0,Math.min(255,Math.round(x*255)))).join(',')+')';ctx.fillRect(l+(u-w/2+a)/(2*a)*size,t+(a-v-hh/2)/(2*a)*size,w/(2*a)*size,hh/(2*a)*size)})}retina(748,162,310,f.aperture,false);retina(1103,196,263,h,true);text('绿：眼光轴/清晰区、手位；紫：实际教师标记；金：评分目标',44,544,15);text('眼位 '+vec(f.eye)+' rad；眼速度 '+vec(f.velocity),746,540,16);
text('教师/问句：'+(f.utterance||c.task.text||'复习间隔，场景和身体继续'),44,637,20);let i=f.own_intent;text(i?('眼选点 '+i.eye_receptor+'；手选点 '+i.hand_receptor+'；'+(i.move?'MOVE':'WAIT')):'本帧未另记新意图，实际命令保持可查',44,674,17);text('自身眼 '+vec(f.own_eye)+'；自身手 '+vec(f.own_hand),44,704,16);text('实际眼 '+vec(f.eye_action)+'；实际手 '+vec(f.hand_action),44,734,16);text('教师动作示范：'+(f.assistance?'有，单独记录':'无'),44,770,18);if(f.expression&&f.expression.selected!=null){text('回答：'+words[f.expression.selected],840,674,24);text('期望仅评分：'+words[f.expression.expected_for_scoring],840,710,18)}if(fi===c.frames.length-1&&Object.keys(c.score).length){let assisted='autonomous_success' in c.score&&c.score.autonomous_success===null,ok=c.score.autonomous_success??c.score.success;text(assisted?'辅助示范，不计自主成绩':('自主结果：'+(ok?'成功':'未达标')),840,758,20,assisted?'#8b526b':ok?'#16775d':'#b44939')}
let left=Math.max(0,f.t-30),right=Math.max(30,f.t),rows=trace.filter(r=>r.t>=left&&r.t<=f.t),max=.001;rows.forEach(r=>curves.forEach(([k])=>max=Math.max(max,r.totals[k])));text('四类真实活动 · 内部模拟秒 · 共用线性纵轴',44,855,17);curves.forEach(([k,n,col],j)=>{line(rows.map(r=>[85+(r.t-left)/(right-left)*1289,1001-r.totals[k]/max*104]),col);text(n+' '+f.totals[k].toFixed(3),92+j*310,888,17,col)});text('0',35,1004,14);text(max.toFixed(1),30,902,14);[0,.25,.5,.75,1].forEach(q=>text((left+q*(right-left)).toFixed(1),85+q*1289-14,1032,14));$('seek').max=c.frames.length-1;$('seek').value=fi;$('clock').textContent='Core '+f.t.toFixed(2)+' s'}
DATA.clips.forEach((c,i)=>{let o=document.createElement('option');o.value=i;o.textContent=(i+1)+' · '+c.stage+' · '+(c.task.text||c.kind);$('clip').append(o)});$('clip').onchange=()=>{ci=+$('clip').value;fi=0;carry=0;draw()};$('seek').oninput=()=>{fi=+$('seek').value;draw()};$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'暂停':'播放';last=0};function tick(t){if(playing&&last){carry+=(t-last)/1000*+$('speed').value;while(carry>=.05){carry-=.05;fi++;if(fi>=DATA.clips[ci].frames.length){fi=0;ci++;if(ci>=DATA.clips.length){ci=DATA.clips.length-1;fi=DATA.clips[ci].frames.length-1;playing=false;break}$('clip').value=ci}}draw()}last=t;requestAnimationFrame(tick)}draw();requestAnimationFrame(tick);</script>'''


def speed_for(stage):
    if 'final' in stage or 'transfer' in stage:
        return 1.
    if 'dev' in stage or 'reanswer' in stage:
        return 2.
    if 'cal' in stage:
        return 4.
    return 8.


def export(work, ffmpeg, *, fps=10, multiplier=1):
    work = Path(work).resolve()
    require((work / 'analysis/verified-results.json').exists(), 'independent continuity audit required before video')
    require(1 <= fps <= 30 and .1 <= multiplier <= 64, 'bounded positive playback settings required')
    out = work / 'replays'
    out.mkdir(exist_ok=True)
    receipt = out / 'export.json'
    if receipt.exists():
        old = read(receipt)
        require(sha(work / old['video']) == old['sha256'], 'saved video changed')
        require(old['fps'] == fps and old['speed_multiplier'] == multiplier, 'use a separate export version for a new playback setting')
        return old
    final, temporary = out / 'replay.mp4', out / 'replay.partial.mp4'
    require(not final.exists() and not temporary.exists(), 'unreviewed prior export exists; preserve and inspect before replacing')
    evidence = read(work / 'analysis/verified-results.json')
    require(read(work / 'subject/latest.json')['boundary_sha256'] == evidence['last_boundary'],
            'subject advanced after the audited evidence')
    activity = work / 'analysis/activity.csv'
    require(sha(activity) == evidence['activity_sha256'], 'audited activity curve changed')
    with activity.open(encoding='utf-8', newline='') as source:
        trace = [{'t': int(row['time_us']) / 1e6, 'totals': {key: float(row[key]) for key in FIELDS}}
                 for row in csv.DictReader(source)]
    paths = ordered_clips(work)
    expected = {row['path']: row['sha256'] for row in evidence['sources']}
    require({p.relative_to(work).as_posix() for p in paths} == set(expected), 'replay clip inventory differs from audited originals')
    require(all(b['t'] > a['t'] for a, b in pairwise(trace)), 'video times are not strictly increasing')
    renderer = Renderer(trace)
    process = subprocess.Popen([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo',
        '-pix_fmt', 'rgb24', '-s', '1440x1080', '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264',
        '-threads', '2', '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)],
        stdin=subprocess.PIPE)
    frames_out, originals = 0, 0
    chapters, sources, current, clips = [], [], None, []

    def finish_chapter():
        if not clips:
            return
        payload = json.dumps({'clips': clips}, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
        filename = f'{len(chapters):03d}-{current}.html'
        put(out / filename, HTML.replace('__DATA__', payload).encode('utf-8'))
        chapters[-1].update(end_s=frames_out/fps, html=filename)

    try:
        for path in paths:
            require(sha(path) == expected[path.relative_to(work).as_posix()], 'audited recording changed: ' + str(path))
            clip = pack(path)
            if clip['stage'] != current:
                finish_chapter()
                current, clips = clip['stage'], []
                chapters.append({'stage': current, 'start_s': frames_out/fps})
            clips.append(clip)
            speed = speed_for(current) * multiplier
            original_frames = clip['frames']
            count = max(1, math.ceil(len(original_frames)*.05/speed*fps))
            for i in range(count):
                index = min(len(original_frames)-1, math.floor(i/fps*speed/.05))
                image = renderer.frame(clip, index, speed=speed)
                process.stdin.write(image.tobytes())
                frames_out += 1
            # End-of-question results are deliberately held in external video time only.
            if 'dev' in current or 'final' in current or 'transfer' in current:
                image = renderer.frame(clip, len(original_frames)-1, speed=speed, hold=True)
                for _ in range(fps):
                    process.stdin.write(image.tobytes())
                    frames_out += 1
            if originals == 0 or ('final' in current and not (out / 'final-example.png').exists()):
                image.save(out / ('first-example.png' if originals == 0 else 'final-example.png'))
            originals += len(original_frames)
            sources.append({'path': path.relative_to(work).as_posix(), 'sha256': sha(path)})
        finish_chapter()
        process.stdin.close()
        require(process.wait() == 0, 'video encoding failed')
    except BaseException:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        process.wait()
        raise
    probe = subprocess.run([str(Path(ffmpeg).with_name('ffprobe.exe')), '-v', 'error', '-show_streams',
                            '-show_format', '-of', 'json', str(temporary)], check=True, capture_output=True)
    info = json.loads(probe.stdout)
    video = next(v for v in info['streams'] if v['codec_type'] == 'video')
    require(video['codec_name'] == 'h264' and (video['width'], video['height']) == SIZE,
            'unexpected encoded video format')
    require(abs(float(info['format']['duration']) - frames_out/fps) < .15, 'video duration mismatch')
    subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-i', str(temporary), '-f', 'null', '-'], check=True)
    temporary.rename(final)
    result = {'video': final.relative_to(work).as_posix(), 'sha256': sha(final), 'fps': fps,
              'video_frames': frames_out, 'duration_s': frames_out/fps, 'original_frames': originals,
              'speed_multiplier': multiplier, 'chapters': chapters, 'sources': sources,
              'activity_curves': list(FIELDS), 'curve_time': 'actual simulated time; continuous across questions',
              'core_advanced': False, 'full_decode_verified': True, 'visual_reviewed': False,
              'renderer_sha256': sha(Path(__file__)),
              'playback': 'teaching 8x, calibration 4x, development 2x, final/transfer 1x, multiplied by requested factor; answer hold 1 external second'}
    fixed_json(receipt, result)
    links = ''.join(f'<li><a href="{html.escape(ch["html"])}">{html.escape(ch["stage"])}</a></li>' for ch in chapters)
    put(out / 'index.html', (f'<!doctype html><meta charset="utf-8"><title>E69 回放</title><h1>E69 连续眼手形色实验</h1>'
                            f'<p><a href="replay.mp4">观看完整视频</a> · 四类真实活动曲线；原件驱动，不运行意识。</p><ul>{links}</ul>').encode())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--ffmpeg', type=Path, default=Path('D:/DevTools/ffmpeg/bin/ffmpeg.exe'))
    parser.add_argument('--fps', type=int, default=10)
    parser.add_argument('--speed', type=float, default=1, help='multiply declared per-stage playback speeds')
    args = parser.parse_args()
    value = export(args.work, args.ffmpeg, fps=args.fps, multiplier=args.speed)
    print(json.dumps({k: value[k] for k in ('video', 'duration_s', 'original_frames', 'video_frames')}))


if __name__ == '__main__':
    main()
