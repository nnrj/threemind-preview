"""Measured full-habitat movies and original-speed behavioral excerpts."""
import json
import subprocess
from experiment import WORK,HERE
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_video import export_recording

FFMPEG='D:/DevTools/ffmpeg/bin/ffmpeg.exe'


def main():
    media=WORK/'media';media.mkdir(exist_ok=True);catalog=[]
    analysis=read_json(HERE/'results.json')
    common=WORK/'cases/shared-00'
    for branch in ('culture','sharing'):
        cases=[common]+sorted(p for p in (WORK/'cases').glob(branch+'-*') if (p/'result.json').exists())
        if len(cases)==1:continue
        parts=[];duration=0.
        title='ThreeMind · 三谱系共同培养 · '+('不分享' if branch=='culture' else '300秒后邻近分享')
        for case in cases:
            r=read_json(case/'result.json');seconds=r['observed_us']/1e6
            if seconds<=0:continue
            plan={'title':'ThreeMind · 三谱系共同培养 · 分叉前' if case==common else title,
                'focus':None,'view_m':None,'start_s':0.,'end_s':seconds,
                'speed':6,'fps':10,'width':1440,'height':1000,'show_evolution':True,'show_trail':False}
            part=media/('shared-prefix.mp4' if case==common else branch+'-'+case.name+'.mp4')
            if not part.exists():export_recording(case,part,plan,ffmpeg=FFMPEG)
            parts.append(part);duration+=seconds/6
        if not parts:continue
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
                        'poster':str(poster.relative_to(WORK)),
                        'description':f'完整海洋，全部意识驱动，包裹吞食，6倍速，共{duration:g}秒。两条录像各自包含相同的0～300秒共同段。'})
    chosen=[]
    observations=analysis['observations']
    # Favor descendants and repeated/combined observations; all come from
    # recorded live events. Never construct an empty demonstration arena.
    for label,predicate in (
        ('combined',lambda o:'both' in o['flags']),
        ('improvement',lambda o:any(f.startswith('improved-') for f in o['flags'])),
        ('offspring-turn',lambda o:o['generation']>0 and any(e['kind']=='turning_food' for e in o['events'])),
        ('repeat-turn',lambda o:o['counts']['turns']>=3 and any(e['kind']=='turning_food' for e in o['events']))):
        candidates=[o for o in observations if predicate(o)]
        if candidates:
            description={'combined':'转弯摄食与吞食兼具','improvement':'相对亲代改善候选',
                         'offspring-turn':'自然后代转弯摄食','repeat-turn':'反复转弯后摄食'}[label]
            o=candidates[0];chosen.append((label,o['case'],o['time_us'],o['individual'],
                f"{description} · #{o['individual']} · {o['cohort']} · 第{o['generation']}代"))
    if analysis['consumptions']:
        e=analysis['consumptions'][0]
        chosen.append(('enclosure',e['case'],e['time_us'],e['predator'],
                       f"包裹吞食 · #{e['predator']} → #{e['individual']}"))
    if analysis['sharing_events']:
        e=analysis['sharing_events'][0]
        chosen.append(('sharing-event',e['case'],e['time_us'],e['donor'],
                       f"邻近分享 · {e['time_us']/1e6:.2f}秒 · #{e['donor']} → #{e['receiver']} · 实收 {e['received']:.2f}"))
    for label,case_name,time_us,individual,title in chosen:
        case=WORK/'cases'/case_name;r=read_json(case/'result.json')
        at=(time_us-(r['time_us']-r['observed_us']))/1e6
        plan={'title':title,'focus':individual,'view_m':None,'inset_m':.12,
              'start_s':max(0,at-6),'end_s':min(r['observed_us']/1e6,at+4),
              'speed':1,'fps':10,'width':1440,'height':1000}
        video=media/(label+'.mp4');poster=media/(label+'.png')
        if not video.exists():export_recording(case,video,plan,ffmpeg=FFMPEG)
        if not poster.exists():export_recording(case,poster,plan,at=max(0,at-.1))
        catalog.append({'id':label,'title':title,'video':str(video.relative_to(WORK)),
            'poster':str(poster.relative_to(WORK)),
            'description':f'原速记录，{case_name}，{time_us/1e6:g}模拟秒；完整环境并列局部放大，不删其他个体或营养。'})
    write_json(media/'catalog.json',{'schema':'threemind.measured-video-catalog/1','clips':catalog})
    print(json.dumps(catalog,ensure_ascii=False))


if __name__=='__main__':main()
