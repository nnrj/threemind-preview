"""Illustrative turns with measured paths; full habitats remain visible."""
import json
from experiment import ROOT, WORK
from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_video import export_recording


def main():
    media=WORK/'media';media.mkdir(exist_ok=True)
    clips=[]
    for name,case,i in [('E37',ROOT/'.work/ocean-enclosure-20261004/cases/segment-01',35),
                        ('E38',WORK/'cases/shared-00',20)]:
        cache=WORK/('turning-e37-segment-01.json' if name=='E37' else 'turning-shared-00.json')
        event=next(e for e in read_json(cache)['passing_events'] if e['individual']==i)
        result=read_json(case/'result.json');origin=(result['time_us']-result['observed_us'])/1e6
        at=event['time_us']/1e6-origin
        plan={'title':f'{name} · 意识驱动 · #{i} 转弯后摄食', 'focus':i,'view_m':None,'inset_m':.15,
              'start_s':max(0,at-7),'end_s':min(result['observed_us']/1e6,at+3),
              'speed':1,'fps':10,'width':1440,'height':1000,'show_trail':True}
        movie=media/f'{name.lower()}-turning-{i}.mp4';poster=movie.with_suffix('.png')
        if not movie.exists():export_recording(case,movie,plan,ffmpeg='D:/DevTools/ffmpeg/bin/ffmpeg.exe')
        if not poster.exists():export_recording(case,poster,plan,at=at-.2)
        clips.append({'id':f'{name.lower()}-turning-{i}','title':plan['title'],'video':str(movie.relative_to(WORK)),
            'poster':str(poster.relative_to(WORK)),'description':f'原速实测完整海洋＋局部放大；{event["time_us"]/1e6:g}秒摄食。候选片段，不代表已证明稳定觅食策略。',
            'event':event})
    write_json(media/'turning-catalog.json',{'schema':'threemind.measured-video-catalog/1','clips':clips})
    print(json.dumps({'clips':[c['video'] for c in clips]},ensure_ascii=False))


if __name__=='__main__':main()
