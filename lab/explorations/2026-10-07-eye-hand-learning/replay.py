"""Complete E60 replay with human-readable case labels and action provenance."""
import json
import html
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from lab.tools.active_vision_replay import pack

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/eye-hand-learning-20261007'


def label(case, value):
    if case == 'B-teach': return '基础教学：52课及全部复习间隔'
    if case == 'B-teach-nose': return '鼻子对照：52课及全部复习间隔'
    if case.startswith('B-validation'): return '独立副本上的验证示范：'+value['source']
    if case.startswith('E-correct'): return '学生先尝试，教师再纠正：全部12题'
    if case.startswith('D-'):
        if 'fit2' not in case: return '工具失败保留：当时读取器未实际学到动作'
        origin = '补课后意识' if value['source'].startswith('E-correct') else '鼻子意识' if 'nose' in value['source'] else '原教学意识'
        head = '新中枢' if 'E-correct' in value['model'] else '独立中枢' if 'separate' in value['model'] else '共同中枢'
        mode = {'normal':'正常', 'empty':'切断输出', 'silence':'既有连接静默', 'rescue':'连接恢复'}[value['mode']]
        if value['input_source'] == 'incoming': mode = '直接感官旁路（不算意识控制）'
        holdout = '最终留出' if 'confirmation' in case else '原型诊断'
        return f'{holdout} · {origin}＋{head} · {mode} · '+('持续可见指示' if value['cue']=='visible' else '短暂指示')
    return case


def main():
    paths = []
    labels = {}
    for path in (WORK/'cases').glob('*/process.jsonl.gz'):
        result = path.parent/'result.json'
        if not result.exists(): continue
        value = json.loads(result.read_text(encoding='utf-8'))
        # Every completed recording, including the identified tooling failure.
        labels[path.parent.name] = label(path.parent.name, value)
        paths.append(path)
    paths.sort(key=lambda p: json.loads((p.parent/'started.json').read_text())['epoch'])
    template = (ROOT/'lab/tools/active_vision_replay.html').read_text(encoding='utf-8')
    folder = WORK/'replay-chapters'; folder.mkdir(exist_ok=True)
    chapters = []; events = []; cards = []
    for i, path in enumerate(paths):
        name = labels[path.parent.name]
        data = pack([path], 'E60 · '+name, labels)
        encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
        relative = f'replay-chapters/chapter-{i+1:02}.html'
        with (WORK/relative).open('x', encoding='utf-8') as f: f.write(template.replace('__DATA__', encoded))
        clips = len(data['clips']); frames = sum(len(c['frames']) for c in data['clips'])
        chapters.append({'case':path.parent.name, 'title':name, 'path':relative, 'clips':clips, 'frames':frames,
                         'bytes':(WORK/relative).stat().st_size})
        events.extend({'case': c['case'], 'label': c['label'], 'kind': c['kind'], 'gaze_events': c['gaze_events']}
                      for c in data['clips'] if 'gaze_events' in c)
        cards.append(f'<article><a href="{relative}">{i+1:02} · {html.escape(name)}</a>'
                     f'<p>{clips}段 · {frames}个原始采样帧 · {(WORK/relative).stat().st_size/2**20:.1f} MiB</p>'
                     f'<details><summary>证据编号</summary><code>{html.escape(path.parent.name)}</code></details></article>')
        print(json.dumps({'chapter':i+1, 'frames':frames}), flush=True)
    index = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ThreeMind E60 · 完整实验回放</title><style>body{margin:0;background:#edf4f1;color:#153f38;font:16px/1.65 system-ui}main{max-width:1100px;margin:auto;padding:24px}h1{font-size:28px}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}article{background:white;padding:18px;border-radius:12px;border:1px solid #c9ddd3}a{color:#126451;font-size:18px;font-weight:600}p{color:#547469;margin:10px 0}code{overflow-wrap:anywhere}summary{cursor:pointer}details{font-size:13px}@media(max-width:600px){main{padding:12px}section{grid-template-columns:1fr}}</style>
<main><h1>ThreeMind · E60 转眼、注视与眼手配合</h1><p>全部已完成实验按执行顺序分章。每章只加载本组记录，包含全部题目、失败与原始采样帧；可逐帧、倍速、截图和导出WebM。旧工具失败另有明确标注，不计作意识能力结论。教师示范成功不算自主控制成功。</p><section>'''+''.join(cards)+'''</section><p>左侧场景示意不替代右侧的实际视网膜输入。动作来源、世界采样时间和Core时间分别显示。回放不运行Core，也不补画理想轨迹。</p></main></html>'''
    target = WORK/'eye-hand-learning.html'
    with target.open('x', encoding='utf-8') as f: f.write(index)
    with (WORK/'gaze-events.json').open('x', encoding='utf-8') as f: json.dump(events, f, ensure_ascii=False)
    with (WORK/'replay-manifest.json').open('x', encoding='utf-8') as f:
        json.dump({'cases':labels, 'chapters':chapters, 'clips':sum(c['clips'] for c in chapters),
                   'frames':sum(c['frames'] for c in chapters), 'file_bytes':sum(c['bytes'] for c in chapters),
                   'every_recorded_frame':True}, f, ensure_ascii=False, indent=2)
    print(json.dumps({'output':str(target), 'chapters':len(chapters)}))


if __name__ == '__main__': main()
