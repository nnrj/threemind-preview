"""Grounded classroom evidence viewer, with actual physical measurements."""
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/grounded-reviews-20261006'


def rows(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for line in f:yield json.loads(line)


def compact(process):
    return [{'time':int(r['activity']['time_us'])/1e6,'observation':r['observation'],
             'activation':sum(n['activation'] for n in r['activity']['nodes']),
             'association':sum(n['associative'] for n in r['activity']['nodes']),
             'inhibition':sum(n['inhibition'] for n in r['activity']['nodes']),
             **({key:r[key] for key in ('action','pointer_after') if key in r})} for r in process]


def main():
    clips=[]
    # Keep all primary action trials, including failures. Place the user's main
    # task first; bodily measurements remain an expandable supporting panel.
    paths=sorted((WORK/'cases').glob('s223-motor-test-*/process.jsonl.gz'),
                 key=lambda p:('episode-normal' not in p.parent.name,p.parent.name))
    for source in paths:
        if not (source.parent/'result.json').exists():continue
        for index,row in enumerate(rows(source)):
            if 'normal' not in source.parent.name and index>=8:break
            trial=row['trial'];mode=trial['mode'];scope=trial.get('reader_name',trial['action_source'])
            clips.append({'title':f'实际动作 · {scope}/{mode} · {index+1} · {trial["text"]}',
                'trial':trial,'frames':compact(row['process']),'evidence':str(source.relative_to(ROOT))})
    motor=WORK/'cases/s223-motor-teaching/process.jsonl.gz'
    if (motor.parent/'result.json').exists():
        for row in rows(motor):
            if row['kind']!='lesson' or row['index'] not in (0,12,36,144,156,168,179):continue
            task=row['lesson']
            clips.append({'title':f'教师引导移动 · {task["phase"]} · {task["text"]}',
                'trial':task|{'answer':'教师施力示范；不是意识自主动作'},
                'frames':compact(row['process']),'evidence':str(motor.relative_to(ROOT))})
    for path in sorted((WORK/'cases').glob('*-expression/predictions.json')):
        key=path.parent.name.removesuffix('-expression');pred=json.loads(path.read_bytes())
        for split in ('familiar','held'):
            answers=[p for p in pred if p['split']==split]
            source=WORK/f'cases/{key}-{split}/process.jsonl.gz'
            for index,row in enumerate(rows(source)):
                if index>=8:break
                clips.append({'title':f'{key} · {split} · 指向{row["trial"]["slot"]+1}',
                  'trial':answers[index],'frames':compact(row['process']),'evidence':str(source.relative_to(ROOT))})
        source=WORK/f'cases/{key}-teaching/teaching.jsonl.gz'
        picked=0
        for row in rows(source):
            if row['kind']=='lesson' and row['index'] in (0,12,96,112,128,144,160):
                task=row['lesson']
                clips.append({'title':f'{key} · 教学 {task["phase"]} · {task["text"]}',
                    'trial':task|{'answer':'教师示范；此段不评分意识回答'},
                    'frames':compact(row['process']),'evidence':str(source.relative_to(ROOT))})
                picked+=1
            if picked==7:break
    if not clips:raise RuntimeError('no completed evidence')
    template=(HERE.parent/'2026-10-06-shape-color-pointing/replay-template.html').read_text(encoding='utf-8')
    template=template.replace('E54','E55').replace('<h1>形状、颜色与指向</h1>','<h1>辨认形色与按话指向</h1>')
    template=template.replace('<p id="activity"></p>','<p id="activity"></p><details><summary>身体与环境测量</summary><pre id="physical"></pre></details>')
    template=template.replace("$('raw').textContent=", "$('physical').textContent=JSON.stringify(o.physical_background,null,2);$('raw').textContent=")
    template=template.replace("r.observation.pointer.x,r.observation.pointer.y", "(r.pointer_after||r.observation.pointer).x,(r.pointer_after||r.observation.pointer).y")
    template=template.replace("const p=xy([o.pointer.x,o.pointer.y]);ctx.fillStyle", "const shownPointer=f.pointer_after||o.pointer;const p=xy([shownPointer.x,shownPointer.y]);ctx.fillStyle")
    template=template.replace("$('score').textContent='correct'in", "if('requested_slot'in c.trial){$('answer').textContent=c.trial.reached?'到达请求对象':(c.trial.choice_correct?'方向最近的对象正确，但未到达':'未指出请求对象');} $('score').textContent='correct'in")
    template=template.replace('右侧答案与评分属于整段检验的最终结果，不是当前播放帧刚刚产生的回答。',
       '右侧评分属于整段检验最终结果。动作帧的自身指针显示该步实际移动后的位置，像素格为驱动这一步前收到的真实采样。教师施力示范与自主测试分列。')
    template=template.replace('__DATA__',json.dumps({'schema':'threemind.classroom-replay/1','clips':clips},ensure_ascii=False).replace('<','\\u003c'))
    path=WORK/'replay.html'
    if path.exists():raise RuntimeError('preserve previously published replay')
    path.write_text(template,encoding='utf-8');print(json.dumps({'clips':len(clips),'path':str(path),'bytes':path.stat().st_size}))


if __name__=='__main__':main()
