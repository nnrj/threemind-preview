"""Portable, offline gallery of measured videos; no simulation or invented frames."""
import html
from experiment import WORK
from lab.tools.ocean_cli import read_json


def build():
    clips=read_json(WORK/'media/final/catalog.json')['clips']
    def panel(item):
        file=html.escape(item['video'].split('/')[-1],quote=True)
        poster=html.escape(item['poster'].split('/')[-1],quote=True)
        causal=' data-causal' if item['id'].startswith('causal-') else ''
        return f'<article><h3>{html.escape(item["title"])}</h3><video controls preload="metadata" poster="{poster}"{causal}><source src="{file}" type="video/mp4"></video><p>{html.escape(item["description"])}</p><a href="{file}" download>下载 MP4 / Download</a></article>'
    causal=''.join(panel(c) for c in clips if c['id'].startswith('causal-'))
    remaining=''.join(panel(c) for c in clips if not c['id'].startswith('causal-'))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>E32 完整海洋 · 实测行为与对照</title><style>
body{font-family:system-ui,sans-serif;background:#eff5f2;color:#183e35;margin:0;padding:24px}main{max-width:1440px;margin:auto}h1{font-size:27px}p{line-height:1.65}section{margin:30px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}article{background:white;border:1px solid #ccdcd5;border-radius:12px;padding:16px}h3{margin:0 0 14px;font-size:18px}video{display:block;width:100%;background:#dcebe7;border-radius:6px}button,a{color:#176651}button{padding:10px 16px;border:1px solid #85afa0;border-radius:6px;background:white;cursor:pointer}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0}input{min-width:160px;flex:1}small{color:#53726a}@media(max-width:600px){body{padding:14px}.grid{grid-template-columns:1fr}}
</style><main><h1>E32 完整海洋：实际行为与同源对照</h1>
<p>53 个初始个体、360 颗营养、持续随机刷新。下列影片都来自真实状态记录，保留完整水域；局部放大只是辅助。原始采样为 100 毫秒，不补造中间活动。影片是观察证据，因果解释请结合报告。</p>
<section><h2>同一时刻：原意识、目标静默、匹配静默</h2><p>三个分支均从 60 秒的完整海洋出发。这里展示 102–115 秒。原意识和匹配静默取得营养 50，目标静默没有取得该次摄入；这是一个来源的反事实对照。</p>
<div class="controls"><button id="play">一起播放</button><button id="pause">一起暂停</button><label for="seek">共同位置</label><input id="seek" type="range" min="0" max="13" step="0.1" value="0"><output id="time">102.0 模拟秒</output></div><div class="grid">'''+causal+'''</div></section>
<section><h2>全程和行为片段</h2><div class="grid">'''+remaining+'''</div></section><small>Recorded trajectories only. No new experiment samples are created by these clips.</small></main>
<script>const vs=[...document.querySelectorAll('video[data-causal]')],seek=document.getElementById('seek'),clock=document.getElementById('time');document.getElementById('play').onclick=()=>vs.forEach(v=>{v.currentTime=Number(seek.value);v.play().catch(()=>{})});document.getElementById('pause').onclick=()=>vs.forEach(v=>v.pause());seek.oninput=()=>{vs.forEach(v=>{v.pause();v.currentTime=Number(seek.value)});clock.textContent=(102+Number(seek.value)).toFixed(1)+' 模拟秒'};vs[0]?.addEventListener('timeupdate',()=>{seek.value=vs[0].currentTime;clock.textContent=(102+vs[0].currentTime).toFixed(1)+' 模拟秒'});</script></html>'''
    (WORK/'media/final/gallery.html').write_text(page,encoding='utf-8')


if __name__=='__main__':build()
