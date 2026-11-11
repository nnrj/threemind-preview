"""Real full-ocean footage, with area-coverage events labeled explicitly."""
import subprocess
from experiment import HERE,WORK,PRIOR
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_video import export_recording

FFMPEG='D:/DevTools/ffmpeg/bin/ffmpeg.exe'


def main():
    analysis=read_json(HERE/'results.json');media=WORK/'media';media.mkdir(exist_ok=True)
    catalog=[]
    for branch in ('turning','coverage'):
        cases=sorted(p for p in (WORK/'cases').glob(branch+'-*') if (p/'result.json').exists())
        parts=[];duration=0.
        title='ThreeMind · '+('转弯摄食培养 · 禁个体吞食' if branch=='turning' else '至少半包裹吞食 · 躯体能力竞争')
        for case in cases:
            seconds=read_json(case/'result.json')['observed_us']/1e6
            if seconds<=0:continue
            plan={'title':title,'focus':None,'view_m':None,'start_s':0.,'end_s':seconds,
                  'speed':6,'fps':10,'width':1440,'height':1000,'show_evolution':True}
            part=media/(case.name+'.mp4')
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
            'poster':str(poster.relative_to(WORK)),'description':'全部意识驱动的完整海洋；从300模拟秒共同快照开始，6倍速。'})
    chosen=[]
    captures=analysis['consumptions']
    if captures:
        e=captures[0];chosen.append(('coverage-event',e['case'],e['time_us'],e['predator'],
            f"部分包裹吞食 · #{e['predator']} → #{e['individual']} · 面积 {e['coverage_measured']:.1%}"))
    for label,predicate in (
        ('combined',lambda o:'both' in o['flags']),
        ('offspring-combined',lambda o:'both' in o['flags'] and o['generation']>0),
        ('parent-improvement',lambda o:any(f.startswith('improved-') for f in o['flags'])),
        ('turning-offspring',lambda o:o['case'].startswith('turning') and o['generation']>0),
        ('turning-repeat',lambda o:o['case'].startswith('turning') and o['counts']['turns']>=3)):
        selected=[o for o in analysis['observations'] if predicate(o)]
        if selected:
            o=selected[0];chosen.append((label,o['case'],o['time_us'],o['individual'],
                f"实测候选 · #{o['individual']} · {o['cohort']} · 第{o['generation']}代 · {label}"))
    for label,case_name,time_us,identity,title in chosen:
        case=WORK/'cases'/case_name;r=read_json(case/'result.json')
        at=(time_us-(r['time_us']-r['observed_us']))/1e6
        plan={'title':title,'focus':identity,'view_m':None,'inset_m':.12,
              'start_s':max(0,at-6),'end_s':min(r['observed_us']/1e6,at+4),
              'speed':1,'fps':10,'width':1440,'height':1000}
        video=media/(label+'.mp4');poster=media/(label+'.png')
        if not video.exists():export_recording(case,video,plan,ffmpeg=FFMPEG)
        if not poster.exists():export_recording(case,poster,plan,at=max(0,at-.1))
        catalog.append({'id':label,'title':title,'video':str(video.relative_to(WORK)),
            'poster':str(poster.relative_to(WORK)),
            'description':f'原速，{time_us/1e6:g}模拟秒，完整环境和局部放大同时保留。'
                + ('标题面积为吞食发生时的记录值；逐帧模拟时间见画面底部。' if label=='coverage-event' else '')})
    for group,combined in (
        ('combined',next((o for o in analysis['observations'] if 'both' in o['flags']),None)),
        ('offspring-combined',next((o for o in analysis['observations'] if 'both' in o['flags'] and o['generation']>0),None))):
        if combined is None:continue
        identity=combined['individual'];branch=combined['case'].rsplit('-',1)[0]
        current_is_consumption=any(e['kind']=='body_consumed_by_coverage' for e in combined['events'])
        opposite='turning_food' if current_is_consumption else 'body_consumed_by_coverage'
        earlier=[(WORK/'cases'/o['case'],o) for o in analysis['observations']
            if o['case'].startswith(branch+'-') and o['individual']==identity
            and o['time_us']<combined['time_us'] and any(e['kind']==opposite for e in o['events'])]
        if not earlier:
            prior=read_json(HERE.parent/'2026-10-04-ocean-culture/results.json')
            earlier=[(PRIOR/'cases/shared-00',o) for o in prior['observations']
                if o['case']=='shared-00' and o['individual']==identity
                and any(e['kind']==opposite for e in o['events'])]
        if earlier:
            case,o=max(earlier,key=lambda pair:pair[1]['time_us']);r=read_json(case/'result.json')
            at=(o['time_us']-(r['time_us']-r['observed_us']))/1e6
            title=f"同一个体 #{identity} · 较早的"+('转弯摄食' if opposite=='turning_food' else '部分包裹吞食')
            plan={'title':title,'focus':identity,'view_m':None,'inset_m':.12,
                'start_s':max(0,at-6),'end_s':min(r['observed_us']/1e6,at+4),
                'speed':1,'fps':10,'width':1440,'height':1000}
            before=media/(group+'-earlier.mp4');poster=media/(group+'-earlier.png')
            if not before.exists():export_recording(case,before,plan,ffmpeg=FFMPEG)
            if not poster.exists():export_recording(case,poster,plan,at=max(0,at-.1))
            parts=[before,media/(group+'.mp4')];listing=media/(group+'-both-concat.txt')
            listing.write_text(''.join("file '"+p.as_posix()+"'\n" for p in parts),encoding='utf-8')
            target=media/(group+'-both.mp4')
            if not target.exists():
                subprocess.run([FFMPEG,'-v','error','-nostdin','-n','-f','concat','-safe','0','-i',str(listing),
                    '-c','copy','-movflags','+faststart',str(target)],check=True)
                write_json(target.with_suffix('.mp4.json'),{'schema':'threemind.measured-concatenation/1',
                    'parts':[str(p) for p in parts],'core_advanced':False,'speed':1,
                    'continuous':False,'same_individual':identity,
                    'event_times_us':[o['time_us'],combined['time_us']],
                    'earlier_source_recording':str(case)})
            catalog.append({'id':group+'-both','title':f'同一个体 #{identity} · 第{combined["generation"]}代 · 两类行为的实际片段',
                'video':str(target.relative_to(WORK)),'poster':str(poster.relative_to(WORK)),
                'environments':[read_json(case/'protocol.json')['schema'],'threemind.ocean-enclosure/3'],
                'description':f"两段原速实测，分别在{o['time_us']/1e6:g}和{combined['time_us']/1e6:g}模拟秒；省略中间等待，并非连续录像。较早片段取自该个体实际共有历史，完整海洋保留，无重新模拟。"})
    write_json(media/'catalog.json',{'schema':'threemind.measured-video-catalog/1','clips':catalog})
    print('Measured E41 videos exported:',len(catalog))


if __name__=='__main__':main()
