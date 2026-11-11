"""All completed E56 pointing trials, not a selection of successes."""
import argparse
import gzip
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/vision-correction-20261006'


def compact(rows):
    values=[]
    for row in rows:
        o=dict(row['observation']);values_raw=o.pop('values')
        values.append({'observation':o,'time':int(row['activity']['time_us'])/1e6,
             'visual_values':values_raw[:16*o['vision_resolution']**2],
             'activation':sum(n['activation'] for n in row['activity']['nodes']),
             'association':sum(n['associative'] for n in row['activity']['nodes']),
             'inhibition':sum(n['inhibition'] for n in row['activity']['nodes']),
             **({k:row[k] for k in ('action','pointer_after') if k in row})})
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=WORK/'replay.html')
    args=parser.parse_args();output=args.output.resolve()
    if not output.is_relative_to(WORK.resolve()) or output.suffix!='.html':
        raise ValueError('new HTML replay within this study work directory required')
    if output.exists() or output.with_suffix('.json').exists():raise FileExistsError('preserve existing replay')
    clips=[]
    for path in sorted((WORK/'cases').glob('*/process.jsonl.gz')):
        stopped=(path.parent/'stopped.json').exists()
        if not (path.parent/'result.json').exists() and not stopped:continue
        result=json.loads((path.parent/'result.json').read_bytes()) if not stopped else {'mode':'normal'}
        mode=result.get('mode')
        if mode not in ('normal','silence','rescue','zero'):continue
        with gzip.open(path,'rt',encoding='utf-8') as stream:
            for index,line in enumerate(stream):
                row=json.loads(line);task=row['trial'];first=row['process'][0]['observation'];n=first['vision_resolution']
                branch='纠错教学后' if '-corrected-' in path.parent.name else '等时观察后' if '-exposure-' in path.parent.name else '补课前'
                if '-nolearning-' in path.parent.name:branch='关闭Core结构可塑性 · '+branch
                phase='练习' if '-practice-' in path.parent.name else '独立确认' if '-confirmation-' in path.parent.name else '正式检验'
                if stopped:phase='已中止组 · 完整记录试次'
                reader='区域共享读头' if '-shared-' in path.parent.name else '原读头'
                if result.get('reader_source',result.get('source'))!=result.get('source'):
                    reader+='（固定等时观察来源读头）'
                reader+=' · '+{'normal':'正常活动','silence':'原连接静默','rescue':'原连接恢复','zero':'零活动读出'}[mode]
                clips.append({'title':f'{n}×{n} · {branch} · {reader} · {phase} {index+1} · {task["text"]}',
                      'trial':task|{'answer':f'选择第{task["selected"]+1}个位置；正确为第{task["slot"]+1}个位置'},
                      'frames':compact(row['process']),'sensor_values':first['values'][:16*n*n],
                      'reader':reader,'evidence':str(path.relative_to(ROOT))})
    if not clips:raise RuntimeError('no completed action trials')
    template=(HERE.parent/'2026-10-06-shape-color-pointing/replay-template.html').read_text(encoding='utf-8')
    template=template.replace('E54','E56').replace('形状、颜色与指向','看清、纠错与实际指认')
    template=template.replace('右侧答案与评分属于整段检验的最终结果，不是当前播放帧刚刚产生的回答。',
        '全部完成的正式/练习指向均保留。选物头只读意识活动；伺服执行它所选的位置，不接收正确答案。右侧评分是本题最终结果。')
    template=template.replace('实际低分辨率RGB输入','实际4×4或6×6 RGB输入')
    template=template.replace('<h2>问题与实际结果</h2>','<h2>问题与本题最终记录</h2><p id="control"></p>')
    template=template.replace("$('time').textContent=f.time.toFixed(2)+' 模拟秒';",
        "$('time').textContent=f.time.toFixed(2)+' 模拟秒';$('control').textContent=(f.action?'当前：伺服执行活动读头的选择':'当前：感官输入，环境风力推动身体，尚未执行选择')+' · '+c.reader;")
    template=template.replace('r.observation.pointer.x,r.observation.pointer.y','(r.pointer_after||r.observation.pointer).x,(r.pointer_after||r.observation.pointer).y')
    template=template.replace('const p=xy([o.pointer.x,o.pointer.y]);ctx.fillStyle','const pp=f.pointer_after||o.pointer;const p=xy([pp.x,pp.y]);ctx.fillStyle')
    old="if(!o.motor_only)for(let slot=0;slot<4;slot++)for(let pixel=0;pixel<16;pixel++){const j=(slot*16+pixel)*4, rgb=o.values.slice(j+1,j+4).map(x=>Math.round(x*255));vis.fillStyle=`rgb(${rgb.join(',')})`;vis.fillRect(7+slot*94+pixel%4*20,28+Math.floor(pixel/4)*20,19,19)}"
    new="const n=o.vision_resolution||4,cell=80/n,values=f.visual_values||c.sensor_values;if(!o.motor_only)for(let slot=0;slot<4;slot++)for(let pixel=0;pixel<n*n;pixel++){const j=(slot*n*n+pixel)*4,rgb=values.slice(j+1,j+4).map(x=>Math.round(x*255));vis.fillStyle=`rgb(${rgb.join(',')})`;vis.fillRect(7+slot*94+pixel%n*cell,28+Math.floor(pixel/n)*cell,cell,cell)}vis.fillStyle='#304f47';vis.font='12px system-ui';['1 左下','2 右下','3 左上','4 右上'].forEach((v,i)=>vis.fillText(v,7+i*94,20));vis.fillText('每视场 '+n+'×'+n+'；输入另含深度通道',7,134);"
    if old not in template:raise RuntimeError('viewer sensor template changed')
    template=template.replace(old,new)
    template=template.replace("$('raw').textContent=", "$('score').textContent=(c.trial.correct?'选对物体':'选错物体')+' · '+(c.trial.selected_endpoint_reached?'执行器抵达所选位置':'执行器未抵达所选位置')+' · 请求目标误差 '+c.trial.target_error_m.toFixed(3)+' 米';$('raw').textContent=")
    data={'schema':'threemind.classroom-replay/2','clips':clips}
    with output.with_suffix('.json').open('x',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,separators=(',',':'))
    template=template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
    export=(ROOT/'lab/tools/classroom_trial_export.js').read_text(encoding='utf-8')
    template=template.replace('</html>', '<script>'+export+'</script></html>')
    with output.open('x',encoding='utf-8') as stream:stream.write(template)
    print(json.dumps({'clips':len(clips),'path':str(output),'bytes':output.stat().st_size}))

if __name__=='__main__':main()
