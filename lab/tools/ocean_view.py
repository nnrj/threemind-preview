"""Build an offline viewer from measured population trajectories, without Core."""

import argparse
import gzip
import json
from pathlib import Path


def recorded_segments(folder):
    """Follow saved continuations, without reading outside the original case."""
    root = folder.resolve()
    result = [root]
    while (result[-1] / "completion.json").exists():
        pointer = json.loads((result[-1] / "completion.json").read_bytes())
        path = (result[-1] / pointer["segment"]).resolve()
        if not path.is_relative_to(root) or path in result:
            raise ValueError("invalid ocean continuation path")
        result.append(path)
    return result


def create(folder, target):
    frames = []

    def append(row):
        value = {
            "t": row["time_us"] / 1e6,
            "food": row["nutrient_count"],
            "births": row["totals"]["births"],
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
                    )
                }
                | {"energy": m["core_energy"]["reserve"]}
                for m in row["members"]
            ],
        }
        if frames and value["t"] == frames[-1]["t"]:
            frames[-1] = value
        elif not frames or value["t"] > frames[-1]["t"]:
            frames.append(value)
        else:
            raise ValueError("ocean observation time moved backwards")

    for segment in recorded_segments(folder):
        with gzip.open(segment / "trajectory.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                append(json.loads(line))
        append(json.loads((segment / "result.json").read_bytes()))
    protocol = json.loads((folder / "protocol.json").read_bytes())
    payload = json.dumps({"frames": frames, "side": protocol["side_m"], "case": folder.name}, ensure_ascii=False)
    html = """<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ThreeMind · 原始海洋观测</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f7f5;color:#153f3c;font:15px system-ui,sans-serif}main{max-width:1160px;margin:auto;padding:24px}h1{font-size:25px;margin:8px 0}p{line-height:1.65;color:#496966}.grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(260px,1fr);gap:22px}.panel{background:white;border:1px solid #d8e5df;border-radius:14px;padding:18px}canvas{display:block;width:100%;aspect-ratio:1;background:#e5f4f3;border-radius:10px}.controls{display:flex;gap:12px;align-items:center;margin-top:16px}input{flex:1;min-width:60px}button{border:0;border-radius:7px;background:#1c766d;color:white;padding:10px 17px;cursor:pointer}select{padding:8px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #e2ebe6;text-align:right;padding:7px 4px}th:first-child,td:first-child{text-align:left}.scroll{max-height:440px;overflow:auto}.stats{display:flex;gap:20px;margin:14px 0;font-size:17px;font-weight:600}.sub{font-size:12px;color:#58746f}a{color:#15665d}@media(max-width:720px){main{padding:12px}.grid{grid-template-columns:1fr}.panel{padding:12px}h1{font-size:21px}.stats{font-size:15px;gap:12px}}</style>
<main><div class="sub">THREEMIND / E28 / 只读观测</div><h1>原始海洋 · 浮游群体</h1><p id="case"></p>
<div class="grid"><section class="panel"><canvas width="700" height="700" id="ocean" aria-label="浮游个体真实位置和大小"></canvas><div class="controls"><button id="play">播放</button><input aria-label="模拟时间" id="time" type="range" min="0" value="0"><select id="speed" aria-label="播放速度"><option value="1">1×</option><option value="5" selected>5×</option><option value="20">20×</option></select></div><div class="stats" id="stats"></div><div class="sub">圆点：躯体；颜色：创始谱系；白线：朝向；十字：躯体已失效。边界相连。轨迹来自每秒观测；未采样的中间运动不作插值，营养位置没有被伪造。</div></section>
<section class="panel"><h2>当前个体</h2><div class="scroll"><table><thead><tr><th>身份 / 代次</th><th>摄入</th><th>储备</th><th>后代</th></tr></thead><tbody id="members"></tbody></table></div><p>摄入是实际接触的颗粒数。储备显示内核与身体合计的模拟能量。查看或播放这份记录不会向意识发送刺激。</p><p class="sub">观察期限结束表示暂停保存，不能据此判定死亡。大小差异、繁殖差异和新物种是不同结论。</p></section></div></main>
<script>const data=PAYLOAD; const slider=document.querySelector('#time'), canvas=document.querySelector('canvas'), ctx=canvas.getContext('2d');let playing=false;slider.max=data.frames.length-1;document.querySelector('#case').textContent=data.case;
function root(b,all){let x=b;const seen=new Set();while(x.parent!==null&&!seen.has(x.id)){seen.add(x.id);x=all.find(v=>v.id===x.parent)||x;}return x.id}
function draw(){const f=data.frames[Number(slider.value)];ctx.clearRect(0,0,700,700);ctx.fillStyle='#e5f4f3';ctx.fillRect(0,0,700,700);for(const b of f.b){const [x,y]=b.position.map(v=>v/data.side*700),r=b.radius/data.side*700;ctx.fillStyle=`hsl(${(root(b,f.b)*137)%360} 50% 43%)`;ctx.globalAlpha=b.physical?0.8:0.2;ctx.beginPath();ctx.arc(x,y,r,0,2*Math.PI);ctx.fill();ctx.globalAlpha=1;ctx.strokeStyle=b.physical?'white':'#57666a';ctx.beginPath();if(b.physical){ctx.moveTo(x,y);ctx.lineTo(x+r*Math.cos(b.angle),y+r*Math.sin(b.angle));}else{ctx.moveTo(x-r/2,y-r/2);ctx.lineTo(x+r/2,y+r/2);ctx.moveTo(x+r/2,y-r/2);ctx.lineTo(x-r/2,y+r/2);}ctx.stroke();ctx.fillStyle='#173c39';ctx.font='12px sans-serif';ctx.fillText(b.id,x+2,y-3)}document.querySelector('#stats').textContent=`${f.t.toFixed(0)} 模拟秒 · 躯体 ${f.b.filter(b=>b.physical).length} · 营养 ${f.food} · 出生 ${f.births}`;const body=document.querySelector('#members');body.replaceChildren();for(const b of f.b){const tr=document.createElement('tr');for(const v of [`${b.id} / ${b.generation}代${b.life==='dead'?' †':''}`,b.grains,Math.round(b.energy+b.storage),b.children]){const td=document.createElement('td');td.textContent=v;tr.append(td)}body.append(tr)}}
slider.oninput=draw;document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'暂停':'播放'};setInterval(()=>{if(!playing)return;slider.value=Math.min(Number(slider.max),Number(slider.value)+Number(document.querySelector('#speed').value));draw();if(slider.value===slider.max){playing=false;document.querySelector('#play').textContent='播放'}},1000);draw();</script></html>"""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(html.replace("PAYLOAD", payload.replace("<", "\\u003c")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    create(args.folder, args.output)
