"""All recorded E55 teaching/control groups, without new Core or inference work."""
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/grounded-reviews-20261006'
OUT=WORK/'complete-media'
LABELS=('球体','圆柱体','立方体','圆锥体','红色','黄色','蓝色','绿色')


def read(path): return json.loads(path.read_bytes())


def compact(row):
    o=row['observation'];a=row['activity'];p=row.get('pointer_after',o['pointer'])
    return {'t':int(a['time_us'])/1e6,'p':[p['x'],p['y']],
        'before':[o['pointer']['x'],o['pointer']['y']],
        'items':o['items'],'marker':o.get('teacher_marker'),
        'rgb':[round(255*v) for i,v in enumerate(o['values'][:256]) if i%4!=0],
        'a':sum(n['activation'] for n in a['nodes']),
        'i':sum(n['inhibition'] for n in a['nodes']),
        'r':sum(n['associative'] for n in a['nodes']),
        'force':row.get('action'),
        'body':o['physical_background']}


def source_rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream: yield json.loads(line)


def prepare():
    OUT.mkdir(exist_ok=True)
    html=OUT/'complete-replay.html'
    if html.exists(): raise RuntimeError('preserve existing complete replay')
    chapters=[];at=12.

    def chapter(case,title,kind,score=None,split=None):
        nonlocal at
        folder=WORK/'cases'/case
        if not (folder/'result.json').exists():raise ValueError('incomplete case '+case)
        source=folder/('teaching.jsonl.gz' if kind=='teaching' else 'process.jsonl.gz')
        answers=read(score) if score else []
        if split:answers=[a for a in answers if a['split']==split]
        clips=[];interval=[];idx=0
        def emit(frames,trial,mode):
            if not frames:return
            # Preserve every original sample in the interactive file. Video
            # can run teaching/waits faster, with explicit speed on screen.
            speed=8. if mode=='interval' else 4. if mode in ('teaching','motor-teaching','calibration') else 1.
            hold=.3 if mode in ('teaching','motor-teaching','calibration') else 1.4 if mode=='question' else 1.2 if mode=='motor' else 0.
            clips.append({'frames':frames,'trial':trial,'mode':mode,'speed':speed,
                          'duration':len(frames)*.05/speed+hold,'hold':hold})
        for row in source_rows(source):
            process=row['process'];process=process if isinstance(process,list) else [process]
            frames=[compact(r) for r in process]
            if row.get('kind')=='interval':
                interval.extend(frames);continue
            if interval:emit(interval,{'text':'复习间隔：场景与身体环境仍持续输入'},'interval');interval=[]
            trial=dict(row.get('trial',row.get('lesson',{})))
            if kind in ('teaching','motor-teaching'):
                if 'teacher_final_error' in row:trial['teacher_final_error']=row['teacher_final_error']
                trial['ordinal']=idx+1
            elif kind=='question':
                answer=answers[idx]
                for key in ('target','slot','text','variant'):
                    if key in answer and answer[key]!=trial[key]:raise ValueError('prediction alignment '+case)
                trial.update(answer)
            elif kind=='calibration':trial['teacher_label']=LABELS[trial['target']]
            emit(frames,trial,kind);idx+=1
        if interval:emit(interval,{'text':'复习间隔：持续环境输入'},'interval')
        if kind=='question' and idx!=len(answers):raise ValueError('prediction count')
        start=at;at+=4
        for clip in clips:clip['start']=at;at+=clip['duration']
        chapters.append({'title':title,'case':case,'kind':kind,'start':start,'end':at,'trials':idx,
                         'source':str(source.relative_to(ROOT)),'result':read(folder/'result.json'),'clips':clips})
        print(json.dumps({'chapter':title,'trials':idx,'samples':sum(len(c['frames']) for c in clips)},ensure_ascii=True),flush=True)

    for condition,caption in [('spaced','正常学习'),('frozen','关闭Core可塑学习')]:
        key='s223-'+condition
        chapter(key+'-teaching',caption+'：完整168课与间隔','teaching')
        chapter(key+'-train',caption+'：全部96项外设校准','calibration')
        for split,title in [('familiar','已教组合／新视角'),('held','未教组合')]:
            chapter(key+'-'+split,caption+'：'+title,'question',WORK/f'cases/{key}-expression/predictions.json',split)
        chapter(key+'-permutations',caption+'：已见视角／新排列','question',WORK/f'cases/{key}-permutations-score/predictions.json')
        if condition=='spaced':
            for suffix,title in [('silence','已有连接静默'),('rescue','解除静默恢复')]:
                chapter(key+'-familiar-'+suffix,caption+'：'+title,'question',WORK/f'cases/{key}-familiar-{suffix}-score/predictions.json')
    chapter('s223-motor-teaching','运动教学：全部180课与间隔','motor-teaching')
    for name,title in [('recent','最近4帧'),('episode','完整过程16帧'),('episode-validated','整段留出选模（探索性）')]:
        chapter('s223-motor-test-'+name+'-normal','实际指向：'+title+'／全部32次','motor')
    data={'schema':'threemind.classroom-complete-replay/1','chapters':chapters,'duration':at+15,
          'intro':12,'results':read(HERE/'results.json'),'analysis':read(HERE/'analysis.json')}
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    (OUT/'complete-replay.json').write_text(payload,encoding='utf-8')
    template=(ROOT/'lab/tools/classroom_replay.html').read_text(encoding='utf-8')
    html.write_text(template.replace('__DATA__',payload),encoding='utf-8')
    manifest={'schema':data['schema'],'core_advanced':False,'answers_regenerated':False,
        'scope':'all completed E55 recorded teaching, calibration, question controls and all three motor groups',
        'duration_s':data['duration'],'samples':sum(len(c['frames']) for ch in chapters for c in ch['clips']),
        'chapters':[{k:v for k,v in ch.items() if k not in ('clips','result')} for ch in chapters],
        'simulations_unexecuted':read(HERE/'results.json')['incomplete_or_failed'],
        'display_only':{'teacher_and_calibration_speed':4,'interval_speed':8,'formal_test_speed':1,
                        'positions':'recorded; sample hold, no invented motion','rgb':'display conversion to 8-bit, original samples in evidence'}}
    (OUT/'media-plan.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (HERE/'media-plan.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'duration':data['duration'],'chapters':len(chapters),'bytes':len(payload.encode('utf-8'))}))


def publish():
    sys.path.insert(0,str(ROOT))
    from lab.tools.study_publication import ArchivedStudy,Publication
    from lab.tools.evidence_archive import artifact_once
    s=ArchivedStudy(WORK);p=Publication(s)
    try:
        plan=read(OUT/'media-plan.json');render=read(OUT/'video-manifest.json')
        artifacts={}
        for key,name,mime in [('video','e55-complete.mp4','video/mp4'),('replay','complete-replay.html','text/html'),
                              ('plan','media-plan.json','application/json'),('poster','poster.png','image/png'),
                              ('approach','approach-description.json','application/json')]:
            artifacts[key]=artifact_once(p,'complete-media:'+key,OUT/name,'E55 完整实验 · '+name,mime,
                metadata={'schema':'threemind.classroom-complete-media/1','core_advanced':False,'duration_s':plan['duration_s']})
        url=lambda key:f"/api/v2/projects/{s.project}/artifacts/{artifacts[key]['artifact_id']}"
        note=p.document('complete-media:record','record','E55 完整教学与多组检验录像 / Complete study replay',
            f"[完整视频 / Video]({url('video')}) · [交互回放 / Interactive replay]({url('replay')}) · [章节 / Chapters]({url('plan')}) · [轨迹描述 / Approach]({url('approach')})\n\n"
            '含正常学习、关闭Core学习、旧连接静默/恢复、三种运动头；正确与错误均保留。全部教学与间隔保留，教学/校准4倍速、间隔8倍速，正式检验1倍速，结果额外停留。'
            '运动检验的橙色评分目标只在回放中显示；问答仍保留原始教师指向感官。全部问答/动作测试来自来源快照的独立副本，不冒充一条连续教学轨迹。\n\n'
            'All completed recorded groups are included, not success-selected examples. Teaching/calibration4x, intervals8x, formal tests1x. '
            'Observer goal outlines and scores are display-only. Recorded samples are held without interpolation; answers are not regenerated. '
            'Core dynamics/defaults and original reports remain unchanged.\n\n'
            '短窗组0.25秒时23/32更近，2秒时17/32更近，最终到达1/32；同时0.25秒时30/32向场景中心移动，须区分两者。此为描述性趋势，不等于已可靠指认。其他两头均完整显示。')
        delivery={'project_id':s.project,'artifacts':artifacts,'record_id':str(note['id']),'render':render}
        p.guard()
        with s.db.tx() as tx:dbbytes=tx.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        delivery['local_study_bytes']=sum(f.stat().st_size for f in WORK.rglob('*') if f.is_file())
        delivery['database_growth_bytes']=max(0,dbbytes-s.meta['database_bytes_before'])
        (HERE/'media-delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(delivery))
    finally:s.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('prepare','publish'))
    {'prepare':prepare,'publish':publish}[p.parse_args().command]()
