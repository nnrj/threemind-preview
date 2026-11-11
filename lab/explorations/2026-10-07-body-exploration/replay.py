"""Complete E61 replay with human-readable case labels and action provenance."""
import json
import html
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from lab.tools.active_vision_replay import pack

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/body-exploration-20261007'


def label(case, value):
    names={'explore':'自由探索','quiet':'等时环境','yoked':'同动作，学前暂关结构学习','guided':'母亲引导120秒，再停止60秒'}
    source='来源'+str(value.get('source','装置'))
    group=names.get(value.get('group'),value.get('group',''))
    if case.startswith('pilot'):return '装置试运行 · '+case
    if case.startswith('A-'):return source+' · '+group+(' · 原力增益，探索不足' if 'gain01' not in case else '')
    if case.startswith('B-'):return source+' · '+group+'后相同52课及复习'
    if case.startswith('V-'):return source+' · '+group+'后的独立验证示范'
    if case.startswith(('W-','W2-')):return source+' · '+group+'共同环境撤去引导 · '+('保留学前接线' if case.startswith('W2-') else '旧探针：接线同时被更换')+' · '+('切断Core至动作' if value['cut'] else '正常接线')
    if case.startswith('P-'):return source+' · '+group+' · 姿态输出与伺服诊断 · '+{'normal':'正常','silence':'既有连接静默','rescue':'连接恢复','empty':'零命令'}.get(value.get('mode','normal'),'正常')
    if case.startswith('D-'):
        mode={'normal':'正常','silence':'既有连接静默','rescue':'连接恢复','empty':'零运动命令'}[value['mode']]
        return source+' · '+group+' · '+mode+' · 读取器来自'+names[value['model_group']]
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
    paths.sort(key=lambda p: json.loads((p.parent/'started.json').read_text(encoding='utf-8'))['epoch'])
    template = (ROOT/'lab/tools/active_vision_replay.html').read_text(encoding='utf-8')
    notice = ('<aside style="padding:12px;background:#fff0d5;color:#633f11;font:15px/1.5 system-ui">'
              'E61 方法更正：学前固定接线、教学教师带动、随后新训Transformer。'
              '本回放保留真实记录，但不能据此判断同一个意识＋Transformer持续成长的效果。'
              ' Continuous joint development was not tested.</aside>')
    if '<main>' not in template: raise ValueError('replay template main required for correction notice')
    template = template.replace('<main>', '<main>'+notice, 1)
    template = template.replace('const narrow=innerWidth<680;',
        "text('E61 分段流程：不能判断完整系统连续成长',640,755,14,'#9b582e');const narrow=innerWidth<680;", 1)
    template = template.replace('联想触达曲线 · 完整记录','E61 分段流程：不代表完整系统连续发育')
    folder = WORK/'replay-chapters'; folder.mkdir(exist_ok=True)
    chapters = []; events = []; cards = []
    for i, path in enumerate(paths):
        name = labels[path.parent.name]
        data = pack([path], 'E61 · '+name, labels)
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
<title>ThreeMind E61 · 完整实验回放</title><style>body{margin:0;background:#edf4f1;color:#153f38;font:16px/1.65 system-ui}main{max-width:1100px;margin:auto;padding:24px}h1{font-size:28px}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}article{background:white;padding:18px;border-radius:12px;border:1px solid #c9ddd3}a{color:#126451;font-size:18px;font-weight:600}p{color:#547469;margin:10px 0}code{overflow-wrap:anywhere}summary{cursor:pointer}details{font-size:13px}@media(max-width:600px){main{padding:12px}section{grid-template-columns:1fr}}</style>
<main><h1>ThreeMind · E61 学前探索、教学与母亲引导</h1>'''+notice+'''<p>全部已完成实验按执行顺序分章。每章只加载本组记录，包含全部题目、失败与原始采样帧；可逐帧、倍速、截图和导出WebM。初期探索不足另列，全部探索、教学和对照均保留。教师示范成功不算自主控制成功。</p><section>'''+''.join(cards)+'''</section><p>左侧场景示意不替代右侧的实际视网膜输入。动作来源、世界采样时间和Core时间分别显示。回放不运行Core，也不补画理想轨迹。</p></main></html>'''
    target = WORK/'body-exploration.html'
    with target.open('x', encoding='utf-8') as f: f.write(index)
    with (WORK/'gaze-events.json').open('x', encoding='utf-8') as f: json.dump(events, f, ensure_ascii=False)
    with (WORK/'replay-manifest.json').open('x', encoding='utf-8') as f:
        json.dump({'cases':labels, 'chapters':chapters, 'clips':sum(c['clips'] for c in chapters),
                   'frames':sum(c['frames'] for c in chapters), 'file_bytes':sum(c['bytes'] for c in chapters),
                   'every_recorded_frame':True}, f, ensure_ascii=False, indent=2)
    print(json.dumps({'output':str(target), 'chapters':len(chapters)}))


if __name__ == '__main__': main()
