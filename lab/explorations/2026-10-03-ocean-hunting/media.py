"""Illustrate one actual encounter in intact/target/matched whole-world footage."""
from pathlib import Path
from experiment import WORK
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_video import export_recording
from lab.tools.ocean_gallery import build as gallery


def build():
    sources=read_json(WORK/'findings.json')['sources']
    # Outcome-based illustration selection is explicit; all registered cases stay
    # in the tables and this choice does not add or select statistical samples.
    key=next((k for k,s in sources.items() if s['arms']['experienced']['target_captured_by_focal']!=s['arms']['blank']['target_captured_by_focal']),
        next((k for k,s in sources.items() if s['arms']['intact']['captured']),next(iter(sources))))
    focus=sources[key]['focal'];clips=[];dest=WORK/'media';dest.mkdir(exist_ok=True)
    choices=[(key,op,label) for op,label in (('experienced','保留经历'),('blank','空白副本'),('graft','目标连接移植'),('graft-matched','匹配连接移植'))]
    capture_source=next((k for k,s in sources.items() if s['arms']['intact']['captured']),None)
    if capture_source:
        choices.extend((capture_source,op,label) for op,label in
                       (('intact','原意识捕获过程'),('target','目标连接静默'),('matched','匹配连接静默')))
    for source,op,label in choices:
        focus=sources[source]['focal']
        name=source+'-'+op;title=f'E34 个体{focus} · {label} · 完整海洋'
        plan={'title':title,'focus':focus,'view_m':None,'inset_m':.12,'start_s':0,'end_s':20,'speed':1,'fps':10}
        video=dest/(name+'.mp4');poster=dest/(name+'.png')
        if not video.exists():export_recording(WORK/'cases'/name,video,plan,ffmpeg=Path('D:/DevTools/ffmpeg/bin/ffmpeg.exe'))
        if not poster.exists():export_recording(WORK/'cases'/name,poster,plan,at=2)
        clips.append({'id':name,'title':title,'comparison_group':source,'video':video.relative_to(WORK).as_posix(),
            'poster':poster.relative_to(WORK).as_posix(),'description':'真实全景与补充近景，20秒，1倍速。为说明过程选择；全部来源/阴性结果均列入报告，不新增样本。'})
    if not (dest/'catalog.json').exists():write_json(dest/'catalog.json',{'clips':clips,'selection':key,'illustration_only':True})
    gallery(dest/'catalog.json',WORK,dest/'gallery.html',title='E34 完整海洋中的连接与捕获',
        description='全部影片均重放实测完整海洋；近景是辅助。每组一起播放，观察同一来源在不同干预下的分歧。影片按过程说明价值选取，全部实验结果见报告。')


if __name__=='__main__':build()
