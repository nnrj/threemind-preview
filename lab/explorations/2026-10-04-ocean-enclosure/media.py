"""Full-habitat lineage movie and natural-event excerpts, from measured frames."""
import argparse
import json
import subprocess

from experiment import WORK
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_video import export_recording

FFMPEG='D:/DevTools/ffmpeg/bin/ffmpeg.exe'


def main():
    media=WORK/'media';media.mkdir(exist_ok=True)
    cases=sorted(p.parent for p in (WORK/'cases').glob('*/result.json'))
    clips=[];parts=[];duration=0.
    for case in cases:
        result=read_json(case/'result.json');seconds=result['observed_us']/1e6
        if seconds<=0:continue
        plan={'title':'ThreeMind · 全意识驱动 · 仅包裹吞食','focus':None,'view_m':None,
            'start_s':0.,'end_s':seconds,'speed':6,'fps':10,'width':1440,'height':1000,
            'show_evolution':True,'show_generation':True,'show_trail':False}
        path=media/(case.name+'.mp4')
        if not path.exists():export_recording(case,path,plan,ffmpeg=FFMPEG)
        parts.append(path);duration+=seconds/6
    target=media/'core-enclosure-generations.mp4'
    if not target.exists():
        listing=media/'concat.txt';listing.write_text(''.join("file '"+p.as_posix()+"'\n" for p in parts),encoding='utf-8')
        subprocess.run([FFMPEG,'-v','error','-nostdin','-n','-f','concat','-safe','0','-i',str(listing),
            '-c','copy','-movflags','+faststart',str(target)],check=True)
        write_json(target.with_suffix('.mp4.json'),{'schema':'threemind.measured-concatenation/1',
            'parts':[str(p) for p in parts],'speed':6,'expected_seconds':duration,
            'complete_habitat':True,'core_advanced':False,'source_gaps':False})
    last=cases[-1];res=read_json(last/'result.json')
    poster=media/'core-enclosure-generations.png'
    if not poster.exists():export_recording(last,poster,plan,at=max(0,res['observed_us']/1e6-.2))
    clips.append({'id':'overview','title':'全意识驱动 · 包裹吞食与代际变化','video':str(target.relative_to(WORK)),
        'poster':str(poster.relative_to(WORK)),'description':f'完整连续过程，6倍速，影片约{duration:.1f}秒；颜色表示代次，所有个体均为意识驱动。'})
    # First natural event in each segment, at most three: explicit selection,
    # no replacing the complete movie with a cherry-picked isolated arena.
    for case in cases:
        if len(clips)>=4:break
        es=[e for e in read_json(case/'events.json') if e['kind']=='body_engulfed']
        if not es:continue
        e=es[0];res=read_json(case/'result.json');origin=(res['time_us']-res['observed_us'])/1e6
        at=e['time_us']/1e6-origin;lo=max(0,at-6);hi=min(res['observed_us']/1e6,at+4)
        event_plan={'title':f"完整海洋 · #{e['predator']} 包裹 #{e['individual']}",
            'focus':e['predator'],'view_m':None,'inset_m':.12,'start_s':lo,'end_s':hi,
            'speed':1,'fps':10,'width':1440,'height':1000}
        key='enclosure-'+case.name;mp4=media/(key+'.mp4');png=media/(key+'.png')
        if not mp4.exists():export_recording(case,mp4,event_plan,ffmpeg=FFMPEG)
        if not png.exists():export_recording(case,png,event_plan,at=max(lo,at-.2))
        clips.append({'id':key,'title':f"#{e['predator']} 包裹吞食 #{e['individual']}",
            'video':str(mp4.relative_to(WORK)),'poster':str(png.relative_to(WORK)),
            'description':f"实测事件 {e['time_us']/1e6:.2f}模拟秒；1倍速；左侧完整海洋、右侧局部放大。"})
    write_json(media/'catalog.json',{'schema':'threemind.measured-video-catalog/1','clips':clips})
    print(json.dumps({'clips':clips,'duration':duration},ensure_ascii=False))


if __name__=='__main__':main()
