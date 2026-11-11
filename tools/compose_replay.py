"""Compose existing recorded videos at a declared speed; never runs a simulation.

Writes a new derivative and provenance receipt. No input is overwritten. Use
--plan-only to inspect the exact FFmpeg invocation without encoding anything.
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def tempo(speed):
    values=[]
    while speed>2:values.append(2.0);speed/=2
    while speed<.5:values.append(.5);speed/=.5
    values.append(speed)
    return ','.join(f'atempo={v:.10g}' for v in values)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def plan(inputs,output,ffmpeg,speed=1,without_audio=False,width=1280,height=800):
    if not math.isfinite(speed) or not .25<=speed<=8:raise ValueError('Speed must be between 0.25 and 8')
    if not 1<=len(inputs)<=16:raise ValueError('Choose 1–16 completed videos')
    if width%2 or height%2 or width<64 or height<64:raise ValueError('Even positive dimensions >= 64 required')
    output=output.resolve();inputs=[p.resolve(strict=True) for p in inputs]
    if output in inputs or output.exists() or output.with_suffix('.provenance.json').exists():raise ValueError('Refusing to replace existing evidence')
    if output.suffix.lower()!='.mp4':raise ValueError('Output must end in .mp4')
    if output.is_relative_to(ROOT) and output.relative_to(ROOT).parts[0] not in ('.work','data'):
        raise ValueError('Generated videos belong in ignored data storage, not source/docs')
    probe=ffmpeg.with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe');metadata=[]
    for p in inputs:
        if p.is_symlink() or not p.is_file():raise ValueError('Regular completed video required')
        result=subprocess.run([str(probe),'-v','error','-show_streams','-show_format','-of','json',str(p)],capture_output=True,text=True,check=True)
        info=json.loads(result.stdout)
        if not any(s['codec_type']=='video' for s in info['streams']):raise ValueError('Missing video')
        metadata.append({'path':str(p),'duration_s':float(info['format']['duration']),
            'has_audio':any(s['codec_type']=='audio' for s in info['streams']),
            'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns})
    audio=not without_audio and any(m['has_audio'] for m in metadata)
    if audio and not all(m['has_audio'] for m in metadata):raise ValueError('Mixed audio presence: supply matching tracks or explicitly use --without-audio')
    filters=[]
    for i in range(len(inputs)):
        filters.append(f'[{i}:v]setpts=(PTS-STARTPTS)/{speed:.10g},scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25[v{i}]')
        if audio:filters.append(f'[{i}:a]asetpts=PTS-STARTPTS,{tempo(speed)}[a{i}]')
    concat=''.join(f'[v{i}]'+(f'[a{i}]' if audio else '') for i in range(len(inputs)))
    filters.append(concat+f'concat=n={len(inputs)}:v=1:a={int(audio)}[v]'+('[a]' if audio else ''))
    partial=output.with_name(output.stem+'.partial.mp4')
    if partial.exists():raise ValueError('Partial derivative exists; inspect before retrying')
    cmd=[str(ffmpeg),'-hide_banner','-loglevel','error','-n','-filter_complex_threads','1']
    for p in inputs:cmd+=['-i',str(p)]
    cmd+=['-filter_complex',';'.join(filters),'-map','[v]']
    if audio:cmd+=['-map','[a]','-c:a','aac']
    cmd+=['-c:v','libx264','-threads','1','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(partial)]
    return cmd,metadata,partial


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ffmpeg',type=Path,default=Path('D:/DevTools/ffmpeg/bin/ffmpeg.exe'));p.add_argument('--speed',type=float,default=1)
    p.add_argument('--without-audio',action='store_true');p.add_argument('--plan-only',action='store_true');args=p.parse_args()
    command,metadata,partial=plan(args.input,args.output,args.ffmpeg,args.speed,args.without_audio)
    if args.plan_only:
        print(json.dumps({'command':command,'inputs':metadata,'simulation_executed':False},ensure_ascii=False,indent=2));return
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for m in metadata:m['sha256']=digest(Path(m['path']))
    subprocess.run(command,check=True)
    for m in metadata:
        path=Path(m['path'])
        if path.stat().st_mtime_ns!=m['mtime_ns'] or path.stat().st_size!=m['bytes'] or digest(path)!=m['sha256']:
            raise RuntimeError('Input changed during composition; partial retained, no final receipt')
    probe=args.ffmpeg.with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe')
    check=json.loads(subprocess.run([str(probe),'-v','error','-show_format','-of','json',str(partial)],capture_output=True,text=True,check=True).stdout)
    actual=float(check['format']['duration']);expected=sum(m['duration_s'] for m in metadata)/args.speed
    if abs(actual-expected)>max(.25,.01*expected):raise RuntimeError('Unexpected derivative duration; partial preserved')
    receipt={'schema':'threemind.replay-derivative/1','simulation_executed':False,'inputs':metadata,'speed':args.speed,
        'audio_explicitly_removed':args.without_audio,'expected_duration_s':expected,'duration_s':actual,
        'output':str(args.output.resolve()),'sha256':digest(partial),'bytes':partial.stat().st_size,'command':command}
    # link gives exclusive final-name creation; never replace another worker's result.
    os.link(partial,args.output);partial.unlink()
    with args.output.with_suffix('.provenance.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
    print(json.dumps({'output':str(args.output),'duration_s':actual,'sha256':receipt['sha256']}))


if __name__=='__main__':main()
