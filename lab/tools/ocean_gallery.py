"""Offline comparison gallery for recorded ocean clips, without simulating frames."""
from __future__ import annotations
import argparse
import html
import json
import os
from pathlib import Path


def build(catalog: Path, root: Path, output: Path, *, title: str, description: str):
    clips=json.loads(catalog.read_bytes())['clips']
    groups={}
    def url(value):
        path=(root/value).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('recorded media must exist inside the declared root')
        return html.escape(Path(os.path.relpath(path,output.parent)).as_posix(),quote=True)
    for clip in clips:
        key=clip.get('comparison_group','Recorded trajectories / 实测轨迹')
        groups.setdefault(key,[]).append(clip)
    panels=[]
    for key,items in groups.items():
        cards=[]
        for c in items:
            video=url(c['video']);poster=url(c['poster'])
            cards.append(f'<article><h3>{html.escape(c["title"])}</h3>'
                f'<video controls preload="metadata" poster="{poster}" src="{video}"></video>'
                f'<p>{html.escape(c["description"])}</p><a href="{video}" download>下载 MP4 / Download</a></article>')
        panels.append(f'<section><h2>{html.escape(key)}</h2><div class="controls">'
            '<button data-play>一起播放 / Play together</button><button data-pause>暂停 / Pause</button>'
            '<label>影片秒 / Clip seconds <input type="range" min="0" max="0" step="0.1" value="0"></label>'
            '<output>0.0</output></div><div class="grid">'+''.join(cards)+'</div></section>')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>'''+html.escape(title)+'''</title><style>
body{font-family:system-ui,sans-serif;background:#eff5f2;color:#183e35;margin:0;padding:24px}main{max-width:1440px;margin:auto}h1{font-size:27px}p{line-height:1.65}section{margin:30px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}article{background:white;border:1px solid #ccdcd5;border-radius:12px;padding:16px}h3{margin:0 0 14px;font-size:18px}video{display:block;width:100%;background:#dcebe7;border-radius:6px}button,a{color:#176651}button{padding:10px 16px;border:1px solid #85afa0;border-radius:6px;background:white;cursor:pointer}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0}.controls label{display:flex;align-items:center;gap:8px;flex-wrap:wrap}input{min-width:120px}small{color:#53726a}@media(max-width:600px){body{padding:14px}.grid{grid-template-columns:1fr}h1{font-size:23px}}
</style><main><h1>'''+html.escape(title)+'</h1><p>'+html.escape(description)+'</p>'+''.join(panels)+'''
<small>Recorded trajectories only. Titles, legends and close-up insets are external annotations.</small></main>
<script>
document.querySelectorAll('section').forEach(section=>{
 const videos=[...section.querySelectorAll('video')],seek=section.querySelector('input'),out=section.querySelector('output');
 const update=()=>{const d=videos.map(v=>v.duration).filter(Number.isFinite);seek.max=d.length?Math.min(...d):0};
 videos.forEach(v=>v.addEventListener('loadedmetadata',update));
 section.querySelector('[data-play]').onclick=()=>videos.forEach(v=>{v.currentTime=Number(seek.value);v.play().catch(()=>{})});
 section.querySelector('[data-pause]').onclick=()=>videos.forEach(v=>v.pause());
 seek.oninput=()=>{videos.forEach(v=>{v.pause();v.currentTime=Number(seek.value)});out.textContent=Number(seek.value).toFixed(1)};
 videos[0]?.addEventListener('timeupdate',()=>{seek.value=videos[0].currentTime;out.textContent=videos[0].currentTime.toFixed(1)});
});
</script></html>'''
    output.write_text(page,encoding='utf-8')
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','root','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--title',required=True);p.add_argument('--description',required=True)
    a=p.parse_args();print(build(a.catalog,a.root,a.output,title=a.title,description=a.description))
