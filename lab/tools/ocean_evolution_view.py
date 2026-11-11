"""Read-only measured Ocean /2 replay: nutrients, bodies, material traits and costs."""

import argparse
import gzip
import json
from pathlib import Path

from lab.tools.ocean_view import recorded_segments


def create(folder, target):
    frames = []
    for part in recorded_segments(folder):
        with gzip.open(part / "trajectory.jsonl.gz", "rt", encoding="utf-8") as f:
            rows = [json.loads(x) for x in f]
        rows.append(json.loads((part / "result.json").read_bytes()))
        for r in rows:
            value = {
                "t": r["time_us"] / 1e6,
                "food": r["food_positions"],
                "total": r["totals"],
                "b": [
                    {
                        k: m[k]
                        for k in (
                            "id",
                            "parent",
                            "generation",
                            "radius",
                            "position",
                            "angle",
                            "physical",
                            "grains",
                            "children",
                            "storage",
                            "life",
                            "shell",
                            "reflectance",
                            "ligand",
                            "body_maintenance",
                            "motor_energy",
                            "share_sent",
                            "share_received",
                        )
                    }
                    | {"energy": m["core_energy"]["reserve"]}
                    for m in r["members"]
                ],
            }
            if frames and value["t"] == frames[-1]["t"]:
                frames[-1] = value
            elif not frames or value["t"] > frames[-1]["t"]:
                frames.append(value)
            else:
                raise ValueError("time moved backwards")
    protocol = json.loads((folder / "protocol.json").read_bytes())
    if protocol["schema"] != "threemind.ocean/2":
        raise ValueError("Ocean /2 recording required")
    payload = json.dumps(
        {"frames": frames, "protocol": protocol, "case": folder.name}, ensure_ascii=False, separators=(",", ":")
    ).replace("<", "\\u003c")
    html = """<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ThreeMind · 浮游演化观测</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f6f4;color:#183f39;font:15px system-ui,sans-serif}main{max-width:1280px;margin:auto;padding:24px}h1{font-size:26px;margin:5px 0}h2{font-size:18px;margin:0 0 12px}.sub{font-size:12px;color:#58746c}.grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(300px,1fr);gap:20px;margin-top:16px}.panel{background:white;border:1px solid #d6e3dc;border-radius:12px;padding:16px;min-width:0}canvas{width:100%;aspect-ratio:1;display:block;background:#e9f4f2;border-radius:8px}.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0}input[type=range]{flex:1;min-width:80px}button,select{padding:9px;border:1px solid #bfd5cc;border-radius:6px;background:white;color:inherit}button.primary{background:#1f766a;color:white;border-color:#1f766a}p{line-height:1.65}#stats{font-weight:650}table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:7px 4px;border-bottom:1px solid #e0e9e4;text-align:right}td:first-child,th:first-child{text-align:left}tr.selected{background:#e1f0ea}.scroll{max-height:360px;overflow:auto}#detail{white-space:pre-line;line-height:1.7;padding:12px;background:#f5f8f6;border-radius:8px}label{display:flex;gap:5px;align-items:center}a{color:#176e61}@media(max-width:740px){main{padding:12px}.grid{grid-template-columns:1fr}.panel{padding:12px}h1{font-size:22px}.bar{gap:8px}}
</style><main><div class="sub">THREEMIND / E29 / 已记录的真实模拟状态</div><h1>浮游海洋 · 生存、变异与资源</h1><p id="case"></p><div class="grid"><section class="panel"><canvas width="800" height="800" aria-label="浮游躯体和营养颗粒的实测位置"></canvas><div class="bar"><button class="primary" id="play">播放</button><input id="time" type="range" min="0" value="0" aria-label="模拟时间"><select id="speed" aria-label="播放速度"><option value="1">1×</option><option value="10" selected>10×</option><option value="60">60×</option></select></div><div class="bar"><label><input id="food" type="checkbox" checked>营养颗粒</label><label><input id="dead" type="checkbox">失效躯体</label><select id="color" aria-label="身体着色"><option value="lineage">谱系</option><option value="shell">外壳</option><option value="reflectance">反射率</option><option value="ligand">相容表面</option></select><button id="download">下载场景配置</button></div><p id="stats"></p><p class="sub">位置与大小来自每秒记录，不插值、不给轨迹补动作。可点击个体查看身体和能量。颜色用于观察，不是内核收到的标签；反射率模式仅展示属性。</p></section><section class="panel"><h2>个体与后代</h2><div class="scroll"><table><thead><tr><th>身份 / 代次</th><th>摄入</th><th>储备</th><th>后代</th></tr></thead><tbody id="members"></tbody></table></div><p id="detail">选择一个个体查看细节。</p><p>推力命令可能因食物不足而无法全部执行。储备含内核与身体；运动和维持分别收费。相容接触交换不等于已演化出主动合作。</p><p class="sub">实验到时是保存暂停，不是死亡。这里为只读回放，完整群体实时启动仍使用统一Python/CLI协议。配置下载不能代替已训练脑状态和完整世界快照。</p></section></div></main>
<script>const data=PAYLOAD;const slider=document.querySelector('#time'),canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');let selected=null,playing=false;slider.max=data.frames.length-1;document.querySelector('#case').textContent=data.case;const side=data.protocol.side_m;
function ancestry(b,all){const seen=new Set();let x=b;while(x.parent!==null&&!seen.has(x.id)){seen.add(x.id);x=all.find(y=>y.id===x.parent)||x}return x.id}
function draw(){const f=data.frames[Number(slider.value)];ctx.fillStyle='#e9f4f2';ctx.fillRect(0,0,800,800);if(document.querySelector('#food').checked){ctx.fillStyle='#b5852c';for(const p of f.food){ctx.beginPath();ctx.arc(p[0]/side*800,p[1]/side*800,2,0,7);ctx.fill()}}for(const b of f.b){if(!b.physical&&!document.querySelector('#dead').checked)continue;const [x,y]=b.position.map(v=>v/side*800),r=b.radius/side*800,mode=document.querySelector('#color').value;let color=`hsl(${ancestry(b,f.b)*137%360} 50% 42%)`;if(mode==='shell')color=`hsl(185 50% ${80-b.shell*55}%)`;if(mode==='reflectance')color=`hsl(160 25% ${15+b.reflectance*75}%)`;if(mode==='ligand')color=`hsl(${b.ligand*90} 48% 45%)`;ctx.fillStyle=color;ctx.globalAlpha=b.physical?1:.25;ctx.beginPath();ctx.arc(x,y,r,0,7);ctx.fill();ctx.globalAlpha=1;ctx.strokeStyle=selected===b.id?'#101f1a':'white';ctx.lineWidth=selected===b.id?2:1;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+r*Math.cos(b.angle),y+r*Math.sin(b.angle));ctx.stroke();if(selected===b.id){ctx.beginPath();ctx.arc(x,y,r+4,0,7);ctx.stroke()}}document.querySelector('#stats').textContent=`${f.t.toFixed(1)} 模拟秒 · 活体 ${f.b.filter(b=>b.physical).length} · 营养 ${f.food.length} · 累计出生 ${f.total.births}`;const table=document.querySelector('#members');table.replaceChildren();for(const b of [...f.b].sort((a,b)=>Number(b.physical)-Number(a.physical)||a.id-b.id)){const tr=document.createElement('tr');if(b.id===selected)tr.className='selected';for(const v of [`${b.id} / ${b.generation}${b.life==='dead'?' †':''}`,b.grains,Math.round(b.storage+b.energy),b.children]){const td=document.createElement('td');td.textContent=v;tr.append(td)}tr.onclick=()=>{selected=b.id;draw()};table.append(tr)}const b=f.b.find(x=>x.id===selected);document.querySelector('#detail').textContent=b?`个体 ${b.id} · 亲代 ${b.parent??'无'} · 第 ${b.generation} 代\n半径 ${(b.radius*1000).toFixed(2)} mm · 外壳 ${b.shell.toFixed(3)} · 反射率 ${b.reflectance.toFixed(3)}\n身体维持 ${b.body_maintenance.toFixed(1)} · 推进耗能 ${b.motor_energy.toFixed(1)}\n分享送出 ${b.share_sent.toFixed(1)} · 收到 ${b.share_received.toFixed(1)}\n意识 ${b.life} · 躯体 ${b.physical?'存在':'失效'}`:'选择一个个体查看细节。'}
slider.oninput=draw;for(const id of ['food','dead','color'])document.getElementById(id).onchange=draw;document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'暂停':'播放'};canvas.onclick=e=>{const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*side,y=(e.clientY-r.top)/r.height*side,f=data.frames[Number(slider.value)];const hits=f.b.filter(b=>b.physical&&Math.hypot(b.position[0]-x,b.position[1]-y)<Math.max(b.radius,side*.01)).sort((a,b)=>Math.hypot(a.position[0]-x,a.position[1]-y)-Math.hypot(b.position[0]-x,b.position[1]-y));if(hits.length){selected=hits[0].id;draw()}};document.querySelector('#download').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify(data.protocol,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=u;a.download=data.case+'-protocol.json';a.click();URL.revokeObjectURL(u)};setInterval(()=>{if(!playing)return;slider.value=Math.min(Number(slider.max),Number(slider.value)+Number(document.querySelector('#speed').value));draw();if(slider.value===slider.max){playing=false;document.querySelector('#play').textContent='播放'}},1000);draw();</script></html>"""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as f:
        f.write(html.replace("PAYLOAD", payload))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    create(a.folder, a.output)
