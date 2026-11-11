"""Separate all-Core full-habitat branch movies; never combine random controllers."""
import json
import subprocess
from experiment import WORK
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_video import export_recording

FFMPEG='D:/DevTools/ffmpeg/bin/ffmpeg.exe'


def main():
    media=WORK/'media';media.mkdir(exist_ok=True);catalog=[]
    common=WORK/'cases/shared-00'
    for branch in ('control','reduced'):
        cases=[common]+sorted(p for p in (WORK/'cases').glob(branch+'-*') if (p/'result.json').exists())
        if len(cases)==1:continue
        parts=[];duration=0.
        title='ThreeMind · 候选谱系 · '+('原营养供给' if branch=='control' else '300秒后营养减半')
        for case in cases:
            r=read_json(case/'result.json');seconds=r['observed_us']/1e6
            plan={'title':title,'focus':None,'view_m':None,'start_s':0.,'end_s':seconds,
                'speed':6,'fps':10,'width':1440,'height':1000,'show_evolution':True,'show_trail':False}
            part=media/(branch+'-'+case.name+'.mp4')
            if not part.exists():export_recording(case,part,plan,ffmpeg=FFMPEG)
            parts.append(part);duration+=seconds/6
        target=media/(branch+'-generations.mp4');listing=media/(branch+'-concat.txt')
        listing.write_text(''.join("file '"+p.as_posix()+"'\n" for p in parts),encoding='utf-8')
        if not target.exists():
            subprocess.run([FFMPEG,'-v','error','-nostdin','-n','-f','concat','-safe','0','-i',str(listing),
                '-c','copy','-movflags','+faststart',str(target)],check=True)
            write_json(target.with_suffix('.mp4.json'),{'schema':'threemind.measured-concatenation/1',
                'parts':[str(p) for p in parts],'speed':6,'expected_seconds':duration,'core_advanced':False})
        poster=media/(branch+'-generations.png')
        if not poster.exists():export_recording(cases[-1],poster,plan,at=max(0,seconds-.2))
        catalog.append({'id':branch,'title':title,'video':str(target.relative_to(WORK)),
                        'poster':str(poster.relative_to(WORK)),'description':f'完整海洋，全部意识驱动，6倍速，{duration:g}秒。'})
    # Actual first candidate-lineage success, if any. No invented demonstration.
    for case in sorted(p.parent for p in (WORK/'cases').glob('*/result.json')):
        r=read_json(case/'result.json');members={m['id']:m for m in r['members']}
        es=[e for e in read_json(case/'events.json') if e['kind']=='body_engulfed' and members[e['predator']]['cohort']=='candidate']
        if not es:continue
        e=es[0];origin=(r['time_us']-r['observed_us'])/1e6;at=e['time_us']/1e6-origin
        plan={'title':f"候选谱系 · #{e['predator']} 包裹 #{e['individual']}",'focus':e['predator'],
              'view_m':None,'inset_m':.12,'start_s':max(0,at-6),'end_s':min(r['observed_us']/1e6,at+4),
              'speed':1,'fps':10,'width':1440,'height':1000}
        video=media/'candidate-enclosure.mp4';poster=media/'candidate-enclosure.png'
        if not video.exists():export_recording(case,video,plan,ffmpeg=FFMPEG)
        if not poster.exists():export_recording(case,poster,plan,at=max(0,at-.1))
        catalog.append({'id':'candidate-enclosure','title':plan['title'],'video':str(video.relative_to(WORK)),
            'poster':str(poster.relative_to(WORK)),'description':f'原速实测片段，{case.name}，{e["time_us"]/1e6:g}模拟秒；完整海洋和局部放大。'})
        break
    if (media/'turning-catalog.json').exists():
        catalog.extend(read_json(media/'turning-catalog.json')['clips'])
    write_json(media/'catalog.json',{'schema':'threemind.measured-video-catalog/1','clips':catalog})
    print(json.dumps(catalog,ensure_ascii=False))


if __name__=='__main__':main()
