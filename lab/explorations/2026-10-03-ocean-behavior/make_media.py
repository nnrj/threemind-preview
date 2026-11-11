"""Illustrative clips from measured records; selection is not a statistical sample."""
import json
from experiment import WORK,OLD
from lab.tools.ocean_video import export_recording
from lab.tools.ocean_cli import write_json

CLIPS=[
 ('01-food',WORK/'cases/g0-i15-food-s1-intact','E31 · 接近营养并摄食',0,6,0,.18,
  '实际于202.965、203.010、203.255秒摄入三颗营养。此例不单独证明主动寻找；反向动作回放也能摄入。',
  'Three observed food contacts. This clip alone does not establish directed foraging; opposite-side replay also eats them.'),
 ('02-capture',WORK/'cases/g0-i10-hunt-s1-intact-paired-noise','E31 · 接触钳制与吞食',0,6,0,.18,
  '0号在203.26秒捕获1号。是否主动追猎由成组对照判断，不能从一次接触断言。',
  'Individual0 captures1 at203.26s. Active pursuit must be assessed with the controls, not inferred from one contact.'),
 ('03-separation',WORK/'cases/g0-i13-escape-s1-intact','E31 · 强邻体场景中的分离',0,8,0,.25,
  '展示强邻体场景中的实际移动和分离；不把尚未确认的定向逃命写成结论。',
  'Measured motion/separation in the stronger-neighbor assay, without claiming confirmed directed escape.'),
 ('04-prior-intact',OLD/'closed-loop/g1-sham','E30 · 37号原样对照',10,28,37,.22,
  '旧E30的已报告事件重绘：37号在这段时间存活。每秒记录保持显示，没有补造中间运动；不计作E31新实验。',
  'Existing E30 evidence replay: individual37 survives this interval. One-second samples are held; this is not a new E31 trial.'),
 ('05-prior-silenced',OLD/'closed-loop/g1-region','E30 · 全群区域阻断，追踪37号',10,28,37,.22,
  '同源旧E30分叉，对全群适用个体施加区域阻断后，37号在220.14秒被42号捕获。视频追踪37号，但不是仅干预37号；不能据此把变化全部归于37号自身。E31原位补试才只干预一个焦点。',
  'Old E30 population intervention: silence regions in all applicable individuals;42 captures37 at220.14s. The camera follows37, but37 was not the only intervention target. E31 natural probes intervene on a single focal individual.'),
]


def generate():
    out=WORK/'media/clips-v2';out.mkdir(parents=True,exist_ok=True);rows=[]
    for name,source,title,start,end,focus,view,zh,en in CLIPS:
        plan={'title':title,'start_s':start,'end_s':end,'focus':focus,'view_m':view,'fps':20}
        video=out/(name+'.mp4');poster=out/(name+'.png')
        if not video.exists():export_recording(source,video,plan,ffmpeg='D:/DevTools/ffmpeg/bin/ffmpeg.exe')
        if not poster.exists():export_recording(source,poster,plan,at=start+1)
        rows.append({'id':name,'title':title,'description_zh':zh,'description_en':en,
                     'source':str(source),'video':str(video.relative_to(WORK)),'poster':str(poster.relative_to(WORK))})
    path=out/'catalog-v2.json'
    if not path.exists():write_json(path,{'selection':'illustrations selected after observing events; no statistical independence implied','clips':rows})
    print(json.dumps({'clips':len(rows),'bytes':sum((WORK/r['video']).stat().st_size for r in rows)}))


if __name__=='__main__':generate()
