"""Chapter every completed E66 process without simulation or frame selection."""
import html
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.active_vision_replay import pack
from lab.tools.service_study import read_json,new_json
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/centered-correction-cycles-20261008'


def main():
    completion=read_json(WORK/'completion.json');rounds=completion['rounds']
    labels={'initial-teaching':'空白初教 · 全部104课与间隔','initial-calibration':'初次外设校准 · 全部48次问答','development-0':'纠错前开发检查 · 全部72题'}
    if (WORK/'cases/confirmation-0/result.json').exists():labels['confirmation-0']='第0轮新位置确认 · 全部72题'
    for r in range(1,rounds+1):
        labels.update({f'correction-{r}':f'第{r}轮 · 错题重答、即时示范、相似题及旧例复习',
                       f'calibration-{r}':f'第{r}轮 · 外设续校材料72题',f'development-{r}':f'第{r}轮 · 固定开发题72题'})
        if (WORK/f'cases/confirmation-{r}/result.json').exists():labels[f'confirmation-{r}']=f'第{r}轮 · 新位置确认72题'
    if (WORK/'cases/retention-retest/result.json').exists():labels['retention-retest']='结项开发复查 · 已接受教师纠正的旧确认错题及易混题'
    target=WORK/'replays';target.mkdir(exist_ok=True)
    template=(ROOT/'lab/tools/active_vision_replay.html').read_text(encoding='utf-8')
    chapters=[]
    for name,label in labels.items():
        path=WORK/f'cases/{name}/process.jsonl.gz'
        if not (path.parent/'result.json').exists():raise RuntimeError('incomplete phase')
        data=pack([path],'ThreeMind · E66 · '+label,{name:label})
        payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
        out=target/(name+'.html')
        with out.open('x',encoding='utf-8') as f:f.write(template.replace('__DATA__',payload))
        chapters.append(dict(case=name,label=label,file=out.name,clips=len(data['clips']),frames=sum(len(c['frames']) for c in data['clips']),bytes=out.stat().st_size))
        print(json.dumps(chapters[-1],ensure_ascii=False),flush=True)
        del data,payload
    result=dict(chapters=chapters,clips=sum(c['clips'] for c in chapters),frames=sum(c['frames'] for c in chapters),bytes=sum(c['bytes'] for c in chapters))
    expected=read_json(HERE/'results.json')['process_audit']['total_frames']
    if result['frames']!=expected:raise AssertionError('replay omitted frames')
    rows=''.join(f'<tr><td><a href="{c["file"]}">{html.escape(c["label"])}</a></td><td>{c["clips"]}</td><td>{c["frames"]}</td></tr>' for c in chapters)
    index=f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E66 多轮纠错全程回放</title><style>body{{background:#0b1220;color:#e6edf5;font:16px/1.7 system-ui;max-width:1080px;margin:40px auto;padding:0 20px}}a{{color:#7dd3fc}}table{{border-collapse:collapse;width:100%}}td,th{{padding:14px;text-align:left;border-bottom:1px solid #293548}}p{{color:#b7c6d8}}</style><h1>E66 空白起点 · 多轮纠错</h1><p>完整过程共 {result["clips"]} 段、{result["frames"]} 帧。包括原错误、学生重答、即时教师示范、相似题与旧题复习，以及全部校准和测试。章节只读原始记录，不重新模拟。</p><p>组合成绩指同一完整来源分别回答形状、颜色都正确。固定眼手是本实验的装置条件。</p><table><tr><th>阶段</th><th>片段</th><th>帧</th></tr>{rows}</table></html>'
    with (target/'index.html').open('x',encoding='utf-8') as f:f.write(index)
    new_json(HERE/'replay-manifest.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='chapters'}),flush=True)


if __name__=='__main__':main()
