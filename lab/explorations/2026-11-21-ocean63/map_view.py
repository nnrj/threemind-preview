"""Read-only water-world map; takes coordinates solely from saved observations."""
import argparse
import gzip
import json
from pathlib import Path
from execution import restore,read


def frame(time_us,members,food):
    bodies = [[m["id"],*m["position"],m["radius"],m["angle"],int(not m["physical"])]
              for m in members if m["physical"] or m.get("carcass_present")]
    return [time_us/1e6,bodies,food]


def write_map(path,title,side,frames):
    import html
    if not frames:
        raise ValueError("no recorded frame")
    data=json.dumps(frames,separators=(",",":"),allow_nan=False)
    page = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>TITLE</title><style>body{max-width:720px;margin:20px auto;padding:0 16px;font:16px system-ui;color:#20282a}h1{font-size:21px}canvas{width:100%;background:#f4f8f8;border:1px solid #b3c4c4}input{width:64%}output{margin-left:10px}.live{color:#176a59}.dead{color:#915327}.food{color:#886100}</style>
<h1>TITLE</h1><p><span class="live">● 活体</span>　<span class="dead">⊗ 遗体</span>　<span class="food">· 营养颗粒</span></p>
<canvas width="720" height="720" aria-label="按真实坐标绘制的水域地图"></canvas>
<p><label>时刻 <input type="range" id="t" min="0" value="0" step="1"></label><output></output></p>
<script>const frames=DATA,side=SIDE,canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d'),t=document.querySelector('input'),out=document.querySelector('output');
t.max=frames.length-1;function draw(){const [s,bodies,food]=frames[+t.value],scale=canvas.width/side;
ctx.clearRect(0,0,720,720);ctx.fillStyle='#aa7b18';for(const [x,y] of food){ctx.fillRect(x*scale-1,y*scale-1,2,2);}
for(const [id,x,y,r,a,dead] of bodies){const radius=Math.max(3,r*scale);ctx.save();ctx.translate(x*scale,y*scale);ctx.strokeStyle=dead?'#915327':'#176a59';ctx.fillStyle=dead?'#f1d4b5':'#268871';
ctx.beginPath();ctx.arc(0,0,radius,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.beginPath();if(dead){const h=radius*.55;ctx.moveTo(-h,-h);ctx.lineTo(h,h);ctx.moveTo(h,-h);ctx.lineTo(-h,h);}else{ctx.strokeStyle='white';ctx.moveTo(0,0);ctx.lineTo(radius*Math.cos(a),radius*Math.sin(a));}ctx.stroke();ctx.fillStyle='#263636';ctx.font='10px system-ui';ctx.fillText(id,radius+1,0);ctx.restore();}
out.textContent=s.toFixed(2)+' 内部秒';}t.oninput=draw;draw();</script></html>'''
    path.write_text(page.replace("TITLE",html.escape(title)).replace("SIDE",str(float(side))).replace("DATA",data),encoding="utf8")


def from_case(folder,target):
    segments=sorted(folder.glob("seg-*/segment.json"))
    horizon=read(segments[-1])["end_us"]
    stride=max(1,(horizon//1_000_000+299)//300)
    frames=[]
    for s in segments:
        with gzip.open(s.parent/"trajectory.jsonl.gz","rt",encoding="utf8") as f:
            for line in f:
                row=json.loads(line)
                if row["time_us"]//1_000_000 % stride==0:
                    frames.append(frame(row["time_us"],row["members"],row["food_positions"]))
    world=restore(segments[-1].parent/"end.zip")
    frames.append(frame(world.time_us,world.metrics()["members"],world.food.tolist()))
    write_map(target,folder.name,world.p.side_m,frames)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("case",type=Path);p.add_argument("output",type=Path)
    args=p.parse_args()
    from_case(args.case,args.output)
