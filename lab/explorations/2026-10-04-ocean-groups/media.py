"""The original mixed habitat, colored by the actual recorded controller."""
from pathlib import Path
from experiment import WORK
from lab.tools.ocean_cli import write_json
from lab.tools.ocean_video import export_recording
from lab.tools.ocean_gallery import build as gallery


def build():
    clips=[];destination=WORK/'media';destination.mkdir(exist_ok=True)
    for g,swap in ((g,swap) for g in (0,1) for swap in (0,1)):
        key=f'mixed-g{g}-swap{swap}';folder=WORK/'cases'/key
        plan={'title':f'E36 海洋{g+1} · 位置分配{swap+1} · 绿意识 / 紫随机','focus':None,
            'view_m':None,'inset_m':None,'start_s':0,'end_s':120,'speed':2,'fps':10}
        video=destination/(key+'.mp4');poster=destination/(key+'.png')
        if not video.exists():export_recording(folder,video,plan,ffmpeg=Path('D:/DevTools/ffmpeg/bin/ffmpeg.exe'))
        if not poster.exists():export_recording(folder,poster,plan,at=60)
        clips.append({'id':key,'title':plan['title'],'comparison_group':f'海洋{g+1} / World {g+1}',
            'video':video.relative_to(WORK).as_posix(),
            'poster':poster.relative_to(WORK).as_posix(),'description':'完整106个初始个体及营养，真实100毫秒记录；2倍速。组内禁止吞食，组间允许。/ Complete recorded habitat,not a recreated toy scene.'})
    if not (destination/'catalog.json').exists():write_json(destination/'catalog.json',{'clips':clips,'measured':True,'independent_samples_added':0})
    gallery(destination/'catalog.json',WORK,destination/'gallery.html',title='E36 意识组与随机组共同海洋',
        description='同一完整世界的两种位置分配：只交换哪组由意识控制。106个初始个体，组内不可吞食，组间可以；绿色为意识控制，紫色为随机控制。两倍速重放真实轨迹。')


if __name__=='__main__':build()
