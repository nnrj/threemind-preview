"""Compact evidence-only viewer. No new simulation or synthetic answers."""
import gzip,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'.work/shape-color-20261006'
HERE=Path(__file__).resolve().parent


def lines(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for row in f:yield json.loads(row)


def compact(row):
    frames=[]
    for sample in row.get('steps',row.get('process',[])):
        obs=sample['observation'];nodes=sample['activity']['nodes']
        frames.append({'time':int(sample['activity']['time_us'])/1e6,'observation':obs,
                       'action':sample.get('action',sample.get('demonstration_action')),
                       'activation':sum(n['activation'] for n in nodes),'association':sum(n['associative'] for n in nodes),
                       'inhibition':sum(n['inhibition'] for n in nodes)})
    return frames


def main():
    clips=[]
    for mode in ('normal','zero','shuffled'):
        file=WORK/f'cases/motor-test-{mode}/process.jsonl.gz'
        for index,row in enumerate(lines(file)):
            if index>6:break
            if index in (2,6):clips.append({'title':f'可见标记 · {mode} · 第{index+1}次','frames':compact(row),
                'trial':row['trial'],'evidence':str(file.relative_to(ROOT))})
    for key in ('s223','s279','s223-frozen'):
        predfile=WORK/f'cases/{key}-expression/predictions.json'
        if not predfile.exists():continue
        predictions=json.loads(predfile.read_text(encoding='utf-8'))
        for split in ('layouts','combinations'):
            answers=[r for r in predictions if r['split']==split]
            file=WORK/f'cases/{key}-{split}/process.jsonl.gz'
            for i,row in enumerate(lines(file)):
                if i>=4:break
                if i<4:clips.append({'title':f'{key} · {split} · {row["trial"]["text"]}',
                    'frames':compact(row),'trial':answers[i],'evidence':str(file.relative_to(ROOT))})
        # Adjacent clips keep the complete scene fixed and change only the
        # teacher's marker/category. Show successes and failures without selection.
        for suffix in ('reference','corrected-reference'):
            file=WORK/f'cases/{key}-{suffix}/process.jsonl.gz'
            if file.exists():
                for i,row in enumerate(lines(file)):
                    if i>=8:break
                    if i<8:clips.append({'title':f'{key} · {suffix} · 指向{row["trial"]["slot"]+1}',
                        'frames':compact(row),'trial':row['trial']|{
                            'text':'这是什么形状？' if row['trial']['category']==0 else '这是什么颜色？',
                            'text_source':'fixed E54 question from recorded category and frozen runner'},
                        'evidence':str(file.relative_to(ROOT))})
    for mode in ('normal','wrong-request','silence'):
        goal=WORK/f'cases/s223-goal-test-{mode}/process.jsonl.gz'
        if goal.exists():
            for i,row in enumerate(lines(goal)):
                if i>=6:break
                trial=row['trial']
                if mode=='wrong-request':
                    positions=((-0.55,-0.55),(0.55,-0.55),(-0.55,0.55),(0.55,0.55))
                    target=positions[trial['requested_slot']];p=trial['final_pointer']
                    error=((p['x']-target[0])**2+(p['y']-target[1])**2)**.5
                    trial=trial|{'original_target_error':trial['error'],'original_target_reached':trial['reached'],
                                 'error':error,'reached':error<=.15,'display_score':'distance to the object actually requested'}
                if i<6:clips.append({'title':f'语言指向 · {mode} · '+trial['text'],'frames':compact(row),
                                    'trial':trial,'evidence':str(goal.relative_to(ROOT))})
    imitation=WORK/'cases/imitation-retry/tests.jsonl.gz'
    seen={}
    for row in lines(imitation):
        mode=row['trial']['mode'];seen[mode]=seen.get(mode,0)+1
        if seen[mode]<=2 and mode in ('normal','full-normal','full-cross-silenced','full-hidden'):
            clips.append({'title':'示范模仿 · '+mode,'frames':compact(row),'trial':row['trial'],
                          'evidence':str(imitation.relative_to(ROOT))})
    data={'schema':'threemind.classroom-replay/1','clips':clips}
    out=WORK/'replay.html'
    if out.exists():raise RuntimeError('replay already exists; preserve original')
    template=(HERE/'replay-template.html').read_text(encoding='utf-8')
    out.write_text(template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')),encoding='utf-8')
    print(str(out))


if __name__=='__main__':main()
