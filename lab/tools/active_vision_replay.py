"""Pack all recorded eye/hand frames into a standalone interactive replay.

This only reads evidence. It never runs Core, interpolates behavior or selects
successful trials. Original complete activity records remain beside the replay.
"""
import argparse
import gzip
import json
from pathlib import Path


def pack(paths,title,case_labels=None):
    clips=[];retinas=[];retina_ids={}
    for path in paths:
        path=Path(path)
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                record=json.loads(line);rows=record.get('process',[record])
                label=record.get('text',record.get('task',{}).get('text',record.get('trial',{}).get('text',record.get('phase',record.get('kind','装置观察')))))
                if record.get('kind')=='exploration':
                    label={'guided':'母亲引导：移动玩具、发声和短句','withdrawn':'母亲已停止引导',
                           'explore':'无教师的身体探索','quiet':'等时环境与身体反馈','yoked':'相同行为重放，学前暂关结构学习'}.get(record.get('condition'),'共同环境中的身体活动')
                clip={'case':path.parent.name,'label':label,'kind':record.get('kind','test' if 'task' in record else 'apparatus'),
                      'result':record.get('result',record.get('trial')),'frames':[]}
                if 'phase' in record:
                    clip['kind']=record['phase']
                    development=rows[0].get('development',{})
                    if development:
                        assist=development.get('assistance',0)
                        clip['action_source']=('等时静置对照：执行器阻断，意识与感官持续' if development.get('passive_control')
                            else f'同一个体的中枢与身体 · 教师辅助 {assist:.0%} · 其余为自身输出及已记录波动')
                if record.get('action_source') or rows[0].get('action_source'):
                    clip['action_source']=record.get('action_source',rows[0].get('action_source'))
                clip['case_label']=(case_labels or {}).get(clip['case'],clip['case'])
                if 'scoring_only_eye_targets' in record:
                    from lab.tools.gaze_events import gaze_events
                    clip['gaze_events']=gaze_events(rows,record['scoring_only_eye_targets'])
                for row in rows:
                    ob=row['observation']
                    if ob['schema'] not in ('threemind.grounded-classroom/4','threemind.grounded-classroom/5','threemind.body-playground/1','threemind.developmental-world/1','threemind.centered-observation/1'):
                        raise ValueError('versioned active-eye or body-playground recording required')
                    retina={'centers':ob['retinal_centers'],'widths':ob['retinal_widths'],
                            'half_width':ob['eye_config']['center_half_width'],'aperture':ob['eye_config']['aperture']}
                    key=json.dumps(retina,sort_keys=True)
                    if key not in retina_ids:retina_ids[key]=len(retinas);retinas.append(retina)
                    nodes=row['activity']['nodes'];sums={k:sum(float(n[k]) for n in nodes) for k in ('activation','inhibition','direct','associative')}
                    clip['frames'].append({'t':ob['time_s'],
                        'core_t':int(row['activity']['time_us'])/1e6 if 'time_us' in row['activity'] else None,
                        'items':ob['items'],'positions':ob['positions'],
                        'p':[ob['pointer']['x'],ob['pointer']['y']],'marker':ob['teacher_marker'],
                        'values':ob['values'][:4*len(retina['centers'])],'retina':retina_ids[key],
                        'eye':ob['eye_angle_rad'],'velocity':ob['eye_velocity_rad_s'],'camera':ob['camera'],
                        'eye_action':row['eye_action'],'hand_action':row['hand_action'],'totals':sums,
                        'nose':ob.get('nose',False)})
                    if 'teacher_utterance' in row:
                        clip['frames'][-1]['teacher_utterance']=row['teacher_utterance']
                    if ob['schema']=='threemind.centered-observation/1':
                        clip['action_source']='固定眼手诊断装置 · 表达器只读取意识活动 · 不代表已学会注视'
                    if 'expression' in row:
                        clip['frames'][-1]['expression']=row['expression']
                        clip['action_source']='固定眼手诊断装置 · 表达器只读取意识活动 · 不代表已学会注视'
                    if ob['schema'] in ('threemind.body-playground/1','threemind.developmental-world/1'):
                        clip['frames'][-1]['body_feedback']={'contacts':ob['toy_contacts'],
                            'touch_N':ob['toy_touch_force_N'],'ears':ob['ears_band_pressure'],
                            'mouth':ob['mouth_state'],'motor':row.get('developmental_motor',row.get('development'))}
                if (clip['kind'] in ('interval','apparatus','exploration') and clips
                    and clips[-1]['kind']==clip['kind'] and clips[-1]['case']==clip['case']
                    and clips[-1].get('action_source')==clip.get('action_source')):
                    clips[-1]['frames'].extend(clip['frames'])
                else:clips.append(clip)
    if not clips:raise ValueError('nonempty evidence required')
    for clip in clips:
        intervals=[b['t']-a['t'] for a,b in zip(clip['frames'],clip['frames'][1:]) if b['t']>a['t']]
        clip['sample_interval_s']=sorted(intervals)[len(intervals)//2] if intervals else .05
    return {'schema':'threemind.active-vision-replay/2','title':title,'clips':clips,'retinas':retinas,
            'sampling':'every recorded frame; held between samples; no Core simulation or invented interpolation'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recordings',type=Path,nargs='+')
    p.add_argument('--output',type=Path,required=True);p.add_argument('--title',default='ThreeMind · 视觉焦点与眼手活动')
    p.add_argument('--case-labels',type=Path,help='Optional display-name JSON; original case identities are retained')
    a=p.parse_args();labels=json.loads(a.case_labels.read_text(encoding='utf-8')) if a.case_labels else None
    if labels is not None and (not isinstance(labels,dict) or any(not isinstance(v,str) for v in labels.values())):
        p.error('case labels must be a string-to-string object')
    data=pack(a.recordings,a.title,labels)
    template=Path(__file__).with_suffix('.html').read_text(encoding='utf-8')
    encoded=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as out:out.write(template.replace('__DATA__',encoded))
    print(json.dumps({'output':str(a.output.resolve()),'clips':len(data['clips']),
                      'frames':sum(len(c['frames']) for c in data['clips'])}))


if __name__=='__main__':main()
