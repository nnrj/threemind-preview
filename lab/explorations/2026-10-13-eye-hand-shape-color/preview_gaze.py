"""Read recorded E69 gaze lessons/tests and render an interim video; no subject imports.

Separate from the frozen final publisher. All 24 questions of each completed
development round are included. Teaching excerpts and omitted time are labelled.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

from analyze import FIELDS, require, score_path
from journal import encoded, fixed_json, put, read, sha
from replay import COLORS, CURVES, SIZE, Renderer, font, pack

font = lru_cache(maxsize=16)(font)

TITLE = 'E69_注视学习阶段回放_第1版'
SELECTION = (
    ('gaze-initial', '初次教学 · 四个方位示范', (0, 10, 20, 30)),
    ('gaze-dev-0', '初教后自主测试 · 0 / 24', tuple(range(24))),
    ('gaze-correction-1', '第一轮纠错 · 教师示范节选', (0, 12, 24, 36)),
    ('gaze-dev-1', '第一轮纠错后 · 15 / 24', tuple(range(24))),
    ('gaze-correction-2', '第二轮纠错 · 教师示范节选', (0, 4, 8, 12)),
    ('gaze-dev-2', '第二轮纠错后 · 16 / 24', tuple(range(24))),
)


def control_snapshot(work):
    return {name: sha(work / name) if (work / name).is_file() else None
            for name in ('subject/latest.json', 'subject/in-flight.json', 'STOP',
                         'continuation-envelope.json', '.continuation/prepared.json')}


def selected_sources(work):
    latest = read(work / 'subject/latest.json')
    chain, previous = {}, None
    for seq in range(latest['sequence'] + 1):
        row = read(work / 'subject/chain' / f'{seq:06d}.json')
        require(hashlib.sha256(encoded({k: v for k, v in row.items() if k != 'boundary_sha256'})).hexdigest()
                == row['boundary_sha256'], 'invalid current branch boundary')
        require(row['identity'] == 'e69-5.1-223' and row['sequence'] == seq, 'subject identity differs')
        if previous:
            require(row['parent'] == previous['boundary_sha256'] and row['start_us'] == previous['end_us'],
                    'current branch time or ancestry gap')
        chain[row['key']] = row
        previous = row
    require(previous == latest, 'latest pointer is not its committed chain record')
    selected, results = [], {}
    for stage, title, indices in SELECTION:
        result_path = work / 'stages' / stage / 'result.json'
        result = read(result_path)
        require(result['identity'] == latest['identity'], 'stage belongs to a different individual')
        if '-dev-' in stage:
            require(len(result['results']) == 24 and result['summary']['n'] == 24, 'incomplete development test')
            require(result['summary']['correct'] == sum(r['success'] for r in result['results']), 'score mismatch')
        results[stage] = {'summary': result['summary'], 'path': result_path.relative_to(work).as_posix(),
                          'sha256': sha(result_path)}
        for index in indices:
            key = f'{stage}:{index:06d}'
            require(key in chain, 'selected clip has no committed boundary')
            row = chain[key]
            selected.append({'stage': stage, 'title': title, 'index': index, 'boundary': row,
                             'path': work / 'stages' / stage / 'clips' / f'{index:06d}.json.gz'})
    require(all(b['boundary']['start_us'] >= a['boundary']['end_us'] for a, b in zip(selected, selected[1:])),
            'preview selection would reverse time')
    return latest, chain, selected, results


def trace_sources(work, chain, selected):
    intervals = [(max(0, s['boundary']['start_us'] - 30_000_000), s['boundary']['end_us']) for s in selected]
    entries = []
    for row in chain.values():
        parts = row['key'].split(':')
        if len(parts) == 2 and parts[1].isdigit():
            name = parts[1]
        elif len(parts) == 3 and parts[1] in ('gap', 'reanswer'):
            name = parts[1] + '-' + parts[2]
        else:
            continue
        if any(row['end_us'] > start and row['start_us'] < end for start, end in intervals):
            entries.append((row, work / 'stages' / parts[0] / 'clips' / (name + '.json.gz')))
    return sorted(entries, key=lambda pair: pair[0]['start_us'])


def plane_point(camera, u, v, height=.52):
    direction = [camera['forward'][i] + u * camera['right'][i] + v * camera['up'][i] for i in range(3)]
    if abs(direction[2]) < 1e-8:
        return None
    scale = (height - camera['origin_m'][2]) / direction[2]
    return None if scale <= 0 else [camera['origin_m'][i] + scale * direction[i] for i in range(2)]


class GazeRenderer(Renderer):
    def curves(self, draw, now):
        draw.rounded_rectangle((24, 831, 1416, 1044), 14, fill='white')
        draw.text((42, 839), '真实意识活动 · 最近30模拟秒 · 四图各用独立线性纵轴', font=self.small, fill='#153f38')
        left, right = max(0, now-30), max(30, now)
        rows = self.trace[max(0, bisect.bisect_left(self.times, left)-1):bisect.bisect_right(self.times, now)]
        for j, (key, name, color) in enumerate(CURVES):
            x, y = 44 + (j % 2)*686, 870 + (j // 2)*84
            visible = [r for r in rows if r['t'] >= left]
            maximum = max([r['totals'][key] for r in visible] + [.001])
            value = visible[-1]['totals'][key] if visible else None
            draw.text((x, y), f'{name}  {value:.3f}' if value is not None else name + '  未采样',
                      font=self.small, fill=color)
            draw.text((x+400, y), f'纵轴 0—{maximum:.2f}', font=self.small, fill='#71837e')
            x0, x1, y0, y1 = x+12, x+626, y+23, y+61
            draw.line((x0, y1, x1, y1), fill='#d9e7e1')
            segment, prior = [], None
            for row in visible:
                if prior is not None and row['t'] - prior > .051:
                    if len(segment) > 1:
                        draw.line(segment, fill=color, width=2)
                    segment = []
                segment.append((x0+(row['t']-left)/(right-left)*(x1-x0), y1-row['totals'][key]/maximum*(y1-y0)))
                prior = row['t']
            if len(segment) > 1:
                draw.line(segment, fill=color, width=2)
            draw.text((x0, y+62), f'{left:.1f}s', font=self.small, fill='#71837e')
            draw.text((x1-65, y+62), f'{right:.1f}s', font=self.small, fill='#71837e')

    def frame(self, clip, index, *, title, number, score, hold=False):
        image = super().frame(clip, index, speed=2, hold=hold)
        draw = ImageDraw.Draw(image)
        f = clip['frames'][index]
        draw.rectangle((0, 0, 1439, 82), fill='#edf4f1')
        draw.text((28, 11), 'E69 · 注视学习的进步', font=font(29), fill='#153f38')
        draw.text((28, 49), title + '  |  ' + number, font=self.normal, fill='#43665d')
        draw.text((1080, 12), f"模拟 {f['t']:.2f}s", font=self.normal, fill='#153f38')
        draw.text((1080, 46), '结果停留 · 模拟不推进' if hold else '真实记录 · 2倍速', font=self.small, fill='#43665d')
        # Show the gaze footprint at the marker's measured height. Object xy
        # positions remain a labelled top-view reference, not invented pixels.
        draw.rounded_rectangle((24, 85, 704, 587), 14, fill='white')
        draw.text((44, 99), '场景俯视示意 · 蓝框为标记高度的清晰区', font=self.normal, fill='#153f38')
        xy = lambda p: (364 + p[0]*220, 345-p[1]*190)
        for (shape, color), pos in zip(f['items'], f['positions']):
            x, y = xy(pos)
            fill = COLORS[color]
            if shape == 0:
                draw.ellipse((x-26, y-26, x+26, y+26), fill=fill)
            elif shape == 3:
                draw.polygon(((x, y-30), (x-27, y+27), (x+27, y+27)), fill=fill)
            else:
                draw.rectangle((x-25, y-25, x+25, y+25), fill=fill)
                if shape == 1:
                    draw.ellipse((x-25, y-32, x+25, y-14), fill=fill, outline='#496d63', width=2)
        trail = [xy(v['pointer']) for v in clip['frames'][:index+1]]
        if len(trail) > 1:
            draw.line(trail, fill='#92c6b5', width=3)
        x, y = xy(f['pointer']); draw.ellipse((x-7,y-7,x+7,y+7), fill='#137d65')
        h = f['half_width']
        points = [plane_point(f['camera'], u, v) for u, v in ((-h,-h),(h,-h),(h,h),(-h,h),(-h,-h))]
        if all(p is not None and max(map(abs,p)) < 1.4 for p in points):
            draw.line([xy(p) for p in points], fill='#3e89c3', width=3)
        center = plane_point(f['camera'],0,0)
        if center is not None and max(map(abs,center)) < 1.2:
            x,y=xy(center); draw.line((x-10,y,x+10,y),fill='#3e89c3',width=3);draw.line((x,y-10,x,y+10),fill='#3e89c3',width=3)
        if f['marker'] is not None:
            x,y=xy(f['marker']); draw.ellipse((x-10,y-10,x+10,y+10),fill='#dc83dc',outline='#8a3f9b',width=2)
        draw.text((44,516),'紫点：真实可见标记；蓝十字：视线落点',font=self.small,fill='#43665d')
        draw.text((44,544),'绿点/轨迹：真实手位；右侧为实际视网膜输入',font=self.small,fill='#43665d')
        draw.rectangle((25,602,1415,818),fill='white')
        assisted = bool(f['assistance'])
        draw.text((44,615), '教师示范（有动作辅助）' if assisted else '自主测试（无教师动作辅助）',
                  font=font(26),fill='#8c5578' if assisted else '#16775d')
        utterance = f['utterance'] or clip['task'].get('statement' if assisted else 'text', '')
        draw.text((44,657),'教师/问句：'+utterance,font=self.normal,fill='#153f38')
        intent=f['own_intent']
        intent_label = ('本帧未另记新意图；实际眼位与运动见上方' if intent is None else
                        f"自身眼选点：{intent['eye_receptor']}    手：{'MOVE' if intent['move'] else 'WAIT'}")
        draw.text((44,692),intent_label,
                  font=self.normal,fill='#43665d')
        draw.text((44,727),'通过条件：进入中央清晰区，末6帧低速稳定注视',font=self.normal,fill='#43665d')
        draw.text((44,765),'每题6模拟秒；0.30秒名义驻留；只评价本阶段注视能力',font=self.small,fill='#71837e')
        draw.text((990,615),'本阶段整套成绩',font=self.normal,fill='#43665d')
        draw.text((1000,652),score,font=font(39),fill='#15785d')
        if hold:
            ok=clip['score'].get('eye_success')
            label='示范达成' if assisted and ok else '示范未达成' if assisted else '本题：注视成功' if ok else '本题：未达标'
            draw.text((990,718),label,font=font(25),fill='#8c5578' if assisted else '#15785d' if ok else '#b74d3d')
            if not assisted and clip['score'].get('eye_initially_inside'):
                draw.text((990,756),'起点已居中 · 维持类',font=self.small,fill='#71837e')
        draw.rectangle((0,1048,1439,1079),fill='#edf4f1')
        draw.text((28,1052),'阶段原件回放 · 成功与失败均保留 · 视频制作不运行或恢复意识',font=self.small,fill='#43665d')
        return image


def card(title, lines, *, scores=False):
    image=Image.new('RGB',SIZE,'#edf4f1');d=ImageDraw.Draw(image)
    d.rounded_rectangle((70,80,1370,1000),24,fill='white')
    d.text((115,125),'THREEMIND  /  E69',font=font(22),fill='#19866d')
    d.text((115,200),title,font=font(42),fill='#153f38')
    for i,line in enumerate(lines):
        d.text((115,285+i*47),line,font=font(24),fill='#43665d')
    if scores:
        for i,(name,value,label) in enumerate((('初教后',0,'0 / 24'),('第一轮纠错后',15/24,'15 / 24'),('第二轮纠错后',16/24,'16 / 24'))):
            y=590+i*104
            d.text((115,y),name,font=font(24),fill='#153f38')
            d.rounded_rectangle((365,y,1125,y+35),8,fill='#e5eee9')
            if value:
                d.rounded_rectangle((365,y,365+760*value,y+35),8,fill='#238f70')
            d.text((1160,y),label,font=font(24),fill='#153f38')
    return image


def export(work,out,ffmpeg,fps=12):
    work,out=Path(work).resolve(),Path(out).resolve()
    require(out.is_relative_to(work/'previews'),'preview output must be a separate managed previews directory')
    require(not out.exists(),'use a new preview version; never overwrite an existing video')
    require(1 <= fps <= 24,'unsupported frame rate')
    before=control_snapshot(work)
    latest,chain,selection,results=selected_sources(work)
    trace,sources=[],{r['path']: r['sha256'] for r in results.values()}
    for boundary,path in trace_sources(work,chain,selection):
        digest=sha(path);clip=pack(path)
        require(round(clip['frames'][0]['t']*1e6)==boundary['start_us']+50000 and
                round(clip['frames'][-1]['t']*1e6)==boundary['end_us'],'clip time disagrees with committed boundary')
        for f in clip['frames']:
            require(all(math.isfinite(v) for v in f['totals'].values()),'nonfinite measured activity')
            trace.append({'t':f['t'],'totals':f['totals']})
        sources[path.relative_to(work).as_posix()]=digest
    require(all(b['t']>a['t'] for a,b in zip(trace,trace[1:])),'curve order is not increasing')
    out.mkdir(parents=True)
    final=out/(TITLE+'.mp4');temporary=out/(TITLE+'.partial.mp4')
    renderer=GazeRenderer(trace);frames_out=0;chapters=[];screens=[]
    command=[str(ffmpeg),'-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1440x1080',
             '-r',str(fps),'-i','-','-an','-c:v','libx264','-threads','2','-preset','veryfast','-crf','21',
             '-pix_fmt','yuv420p','-movflags','+faststart',str(temporary)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    def emit(image,seconds=None):
        nonlocal frames_out
        for _ in range(1 if seconds is None else round(seconds*fps)):
            process.stdin.write(image.tobytes());frames_out+=1
    try:
        intro=card('从不会注视，到 16 / 24',[
            '同一个 continuous-memory/5.1 个体 · 阶段性学习记录',
            '教学采用节选；三轮各24题自主测试完整保留，包括失败题。',
            '真实活动曲线始终随实验画面显示；记录按内部时间向前播放。',
            '本片不是终试结果；手眼协调和形色阶段尚未开始。'],scores=True)
        intro.save(out/'封面.png');emit(intro,7)
        previous_end=None;current=None
        for entry in selection:
            boundary,path=entry['boundary'],entry['path'];stage=entry['stage']
            if current!=stage:
                chapters.append({'stage':stage,'title':entry['title'],'video_start_s':frames_out/fps})
                lines=['以下为教学节选，教师动作辅助明确标记。' if '-dev-' not in stage else '以下24题全部播放，成功和失败使用相同播放方式。',
                       '模拟时间在省略区间向前跳转；没有逐题恢复或重跑。']
                if stage=='gaze-dev-1':
                    lines+=['本实验曾在2004秒获准恢复；原中断支线另行保留。','这里播放同一个体r1分支的真实后续记录。']
                emit(card(entry['title'],lines),4 if stage=='gaze-dev-1' else 3)
                current=stage
            if previous_end is not None and boundary['start_us']>previous_end:
                emit(card('省略区间 · 时间向前跳转',[
                    f"{previous_end/1e6:.2f} s  →  {boundary['start_us']/1e6:.2f} s",
                    '中间教学、采样或复习未收入本短片；原件完整保留。',
                    '接下来播放实际记录；曲线采用对应时段的真实采样。']),1.5)
            require(sha(path)==sources[path.relative_to(work).as_posix()],'selected source changed')
            clip=pack(path)
            result_path=score_path(path)
            sources[result_path.relative_to(work).as_posix()]=sha(result_path)
            assisted='-dev-' not in stage
            require(all(bool(f['assistance'])==assisted for f in clip['frames']),'assistance label differs from original')
            score='辅助示范' if assisted else f"{results[stage]['summary']['correct']} / 24"
            number=('示范节选 '+str(entry['index']+1)) if assisted else f"第 {entry['index']+1:02d} / 24 题"
            for i in range(math.ceil(len(clip['frames'])*.05/2*fps)):
                index=min(len(clip['frames'])-1,math.floor(i/fps*2/.05))
                emit(renderer.frame(clip,index,title=entry['title'],number=number,score=score))
            image=renderer.frame(clip,len(clip['frames'])-1,title=entry['title'],number=number,score=score,hold=True)
            emit(image,1 if not assisted else .5)
            if entry['index']==0 or (stage=='gaze-dev-2' and entry['index'] in (2,5,23)):
                name=f"画面_{stage}_{entry['index']:02d}.png";image.save(out/name);screens.append(name)
            previous_end=boundary['end_us']
            if entry['index'] % 6 == 0:
                print(json.dumps({'render_stage':stage,'question':entry['index']+1,'video_s':frames_out/fps}),flush=True)
        emit(card('眼睛已经学会了一部分寻找与注视',[
            '最近一轮16道成功中，15道从清晰区外转入，1道为居中维持。',
            '仍有8道未达标；当前继续训练目标是稳定性与迁移。',
            '普通教学与测试承接当前状态；本片只读取保存的原件。',
            '后续：完成眼动第三轮纠错，再进入手眼协调与形色教学。'],scores=True),8)
        process.stdin.close();require(process.wait()==0,'encoder failed')
    except BaseException:
        if not process.stdin.closed:process.stdin.close()
        process.wait();raise
    probe=json.loads(subprocess.run([str(Path(ffmpeg).with_name('ffprobe.exe')),'-v','error','-show_streams',
                                    '-show_format','-of','json',str(temporary)],capture_output=True,check=True).stdout)
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    require(video['codec_name']=='h264' and (video['width'],video['height'])==SIZE,'unexpected video format')
    require(abs(float(probe['format']['duration'])-frames_out/fps)<.15,'duration mismatch')
    subprocess.run([str(ffmpeg),'-v','error','-threads','2','-i',str(temporary),'-f','null','-'],check=True)
    require(all(sha(work/path)==digest for path,digest in sources.items()),'originals changed during rendering')
    require(not any(name in sys.modules for name in ('system','experiment','threemind_native','_threemind_native')),
            'unexpected subject or native module imported')
    temporary.rename(final)
    receipt={'schema':'threemind.e69-interim-gaze-video/1','scope':'interim teaching excerpts plus all 72 development questions',
             'identity':latest['identity'],'current_boundary_at_start':latest['sequence'],'video':final.name,'sha256':sha(final),
             'duration_s':frames_out/fps,'fps':fps,'frames':frames_out,'playback_speed':2,'chapters':chapters,
             'sources':sources,'stage_results':results,'curve_fields':list(FIELDS),'curve_context_s':30,
             'curve_axes':'four separate linear axes; no interpolation over recording gaps',
             'ordinary_questions_reset':False,'historical_authorized_rollback_count':1,
             'subject_imported':False,'core_advanced':False,'control_before':before,'control_after':control_snapshot(work),
             'control_unchanged':before==control_snapshot(work),'full_decode_verified':True,'visual_reviewed':False,
             'renderer_sha256':sha(Path(__file__)),'frozen_renderer_sha256':sha(Path(__file__).with_name('replay.py')),
             'preview_images':screens}
    fixed_json(out/'export.json',receipt)
    put(out/'说明.txt',('E69 注视学习阶段回放（第1版）\n教学节选、三轮完整开发测试；包括全部成功和失败。\n'
        '视频2倍速，结题停留仅改变视频时长；意识不会因观看或制作视频而运行。\n'
        '各段模拟时间按原件向前；省略区间明确提示。2004秒曾获准恢复，原失败支线保留。\n'
        '底部为真实激活、抑制、直接、联想四曲线，使用各自纵轴。\n'
        '本文件是中期预览，不作为完整实验结项或终试成绩。\n').encode('utf-8'))
    print(json.dumps({k:receipt[k] for k in ('video','duration_s','sha256','control_unchanged')},ensure_ascii=False))
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--ffmpeg',type=Path,default=Path('D:/DevTools/ffmpeg/bin/ffmpeg.exe'))
    args=parser.parse_args()
    export(args.work,args.out,args.ffmpeg)
