"""Full-habitat measured video catalog. Excerpts illustrate, not add samples."""
import argparse
from pathlib import Path
from experiment import WORK
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_video import export_recording,load_recording
from lab.tools.ocean_contact_view import create

FFMPEG=Path('D:/DevTools/ffmpeg/bin/ffmpeg.exe')


def clip(key,case,title,focus,start,end,description,speed=1,inset=True):
    source=WORK/'cases'/case;dest=WORK/'media/final';dest.mkdir(parents=True,exist_ok=True)
    plan={'title':title,'view_m':None,'focus':focus,'start_s':start,'end_s':end,'speed':speed,'fps':10,
          'inset_m':.2 if inset else None}
    video=dest/(key+'.mp4');poster=dest/(key+'.png')
    if not video.exists():export_recording(source,video,plan,ffmpeg=FFMPEG)
    if not poster.exists():export_recording(source,poster,plan,at=min(end-.1,start+2))
    return {'id':key,'case':case,'title':title,'description':description,
        'video':video.relative_to(WORK).as_posix(),'poster':poster.relative_to(WORK).as_posix(),'plan':plan}


def build():
    catalog=[]
    for mode,title in (('core','意识驱动'),('random','独立随机驱动')):
        catalog.append(clip('overview-'+mode,'g0-'+mode,'E32 完整海洋 · '+title,None,0,120,
            '同一初始环境：53个体、360颗营养，持续随机刷新。完整120模拟秒以2倍速展示；是真实记录，不是新增实验。',2,False))
    events=read_json(WORK/'cases/g0-core/events.json')
    feeding=next(e for e in events if e['kind']=='nutrient_contact' and e['individual']==0 and e['time_us']>=60000000)
    when=feeding['time_us']/1e6
    catalog.append(clip('focal-food','g0-core','E32 0号接近并摄入营养 · 完整环境',0,when-4,when+4,
        f'实测摄入发生在{when:.3f}模拟秒；左侧保留全海，右侧为同一记录的局部放大。该过程的内部作用由报告中的原位分叉另行判断。'))
    capture=next(e for e in events if e['kind']=='body_engulfed' and e['time_us']>=60000000)
    when=capture['time_us']/1e6
    catalog.append(clip('contact-capture','g0-core',f'E32 {capture["predator"]}号捕获{capture["individual"]}号 · 完整环境',
        capture['predator'],when-4,when+3,
        f'接触捕获于{when:.2f}模拟秒完成，外壳要求的接触时间为{capture["required_us"]/1e6:.3f}秒。影片显示捕获事实，不能单凭此段判定主动追猎。'))
    recording=load_recording(WORK/'cases/g0-core')
    release=None
    for event in events:
        if event['kind']!='capture_released':continue
        after=next((f for f in recording['frames'] if f['time_us']>event['time_us']),None)
        if after and any(b['id']==event['individual'] and b['physical'] for b in after['members']):release=event;break
    if release:
        when=release['time_us']/1e6
        catalog.append(clip('contact-release','g0-core',f'E32 {release["individual"]}号接触后脱离 · 完整环境',
            release['individual'],max(0,when-4),when+4,
            f'{when:.2f}模拟秒发生脱离，随后躯体仍存活。是否由特定内部活动带来逃脱收益，不能只由画面断言。'))
    for case in ('g0-core','g0-random','g1-core','g1-random'):
        target=WORK/'media/final'/f'{case}-replay.html'
        if not target.exists():create(WORK/'cases'/case,target)
    write_json(WORK/'media/final/catalog.json',{'schema':'threemind.ocean-video-catalog/1','clips':catalog,
        'primary_view':'complete habitat, optional supplementary inset','adds_independent_samples':False})


if __name__=='__main__':build()
