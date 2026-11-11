"""Render recorded capsules, captures and shell defenses; no simulation in UI."""
import argparse
import gzip
import json
from pathlib import Path


def create(folder,target):
    protocol=json.loads((folder/'protocol.json').read_text())
    if protocol['schema']!='threemind.ocean/3':raise ValueError('Ocean /3 required')
    with gzip.open(folder/'trajectory.jsonl.gz','rt',encoding='utf-8') as f:
        rows=[json.loads(x) for x in f]
    final=json.loads((folder/'result.json').read_text())
    # Some recorders keep the final food state in the complete snapshot instead
    # of duplicating it in the scalar result. Use that recorded state only.
    if 'food_positions' not in final:
        context=json.loads((folder/'final/manifest.json').read_text())['context']
        final['food_positions']=context.get('world',context)['food']
    rows.append(final)
    frames=[]
    for row in rows:
        frames.append({'t':row['time_us']/1e6,'food':row['food_positions'],'predations':row['totals']['predations'],
            'members':[{k:m[k] for k in ('id','parent','generation','position','radius','elongation','angle','physical','shell',
                                        'grip','grains','children','storage','captured','motor_energy')}
                       |{'energy':m['core_energy']['reserve']} for m in row['members']]})
    payload=json.dumps({'protocol':protocol,'frames':frames,'events':json.loads((folder/'events.json').read_text()),
                        'case':folder.name},ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    html='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ThreeMind · 捕获与内部控制实验</title><style>
*{box-sizing:border-box}body{margin:0;color:#173f35;background:#f1f5f3;font:15px system-ui}main{max-width:1200px;margin:auto;padding:24px}h1{font-size:25px}.layout{display:grid;grid-template-columns: minmax(0,1.5fr) minmax(270px,1fr);gap:20px}.card{background:white;padding:16px;border:1px solid #d5e2dc;border-radius:12px}canvas{width:100%;aspect-ratio:1;background:#e8f1ee;display:block}button,select{background:white;color:inherit;border:1px solid #bdd2c8;border-radius:6px;padding:8px}button{cursor:pointer}.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0}input{flex:1;min-width:90px}small{color:#5b756a}#detail{white-space:pre-line;line-height:1.8}#events{max-height:400px;overflow:auto;font-size:13px;line-height:1.7}li{margin:8px 0}@media(max-width:750px){main{padding:12px}.layout{grid-template-columns:1fr}}
</style><main><h1>浮游海洋：捕获、外壳与控制</h1><p id="name"></p><div class="layout"><section class="card"><canvas width="850" height="850" aria-label="真实记录的胶囊形浮游躯体与食物"></canvas><div class="controls"><button id="play">播放</button><input id="time" type="range" min="0" value="0" aria-label="模拟时间"><select id="speed" aria-label="回放速度"><option value="1">1×</option><option value="10" selected>10×</option><option value="30">30×</option></select></div><p id="status"></p><small>按实际采样状态回放，形状、角度和位置均来自记录。颜色表示外壳厚度；点击个体查看。回放不向意识输入刺激。</small></section><section class="card"><h2>个体</h2><div id="detail">点击一个躯体。</div><h2>附近时刻的事件</h2><ul id="events"></ul></section></div></main><script>
const d=PAYLOAD,s=document.querySelector('#time'),c=document.querySelector('canvas'),ctx=c.getContext('2d'),side=d.protocol.side_m;
let selected=null,playing=false,last=0,clock=d.frames[0].t;s.max=d.frames.length-1;document.querySelector('#name').textContent=d.case;
function draw(){const f=d.frames[+s.value];ctx.clearRect(0,0,850,850);ctx.fillStyle='#b18c39';for(const p of f.food){ctx.beginPath();ctx.arc(p[0]/side*850,p[1]/side*850,2,0,7);ctx.fill()}
for(const b of f.members.filter(x=>x.physical)){const r=b.radius/Math.sqrt(1+4*b.elongation/Math.PI)/side*850,l=b.elongation*r;ctx.save();ctx.translate(b.position[0]/side*850,b.position[1]/side*850);ctx.rotate(b.angle);ctx.fillStyle=`hsl(164 42% ${68-42*b.shell}%)`;ctx.strokeStyle=b.id===selected?'#ff9e18':'#306756';ctx.lineWidth=b.id===selected?3:1;ctx.beginPath();ctx.moveTo(-l,-r);ctx.lineTo(l,-r);ctx.arc(l,0,r,-Math.PI/2,Math.PI/2);ctx.lineTo(-l,r);ctx.arc(-l,0,r,Math.PI/2,3*Math.PI/2);ctx.fill();ctx.stroke();ctx.restore()}
document.querySelector('#status').textContent=`${f.t.toFixed(1)} 秒 · 存活躯体 ${f.members.filter(x=>x.physical).length} · 吞食 ${f.predations} · 食物 ${f.food.length}`;
const b=f.members.find(x=>x.id===selected);document.querySelector('#detail').textContent=b?`个体 ${b.id} · 第${b.generation}代 · 亲代 ${b.parent??'无'}\n${b.physical?'躯体活动中':'躯体失效'}\n形状伸长 ${b.elongation.toFixed(2)} · 外壳 ${b.shell.toFixed(2)}\n营养颗粒 ${b.grains} · 捕获 ${b.captured} · 后代 ${b.children}\n身体储备 ${b.storage.toFixed(1)} · 内核储备 ${b.energy.toFixed(1)}\n推进消耗 ${b.motor_energy.toFixed(1)}`:'点击一个躯体。';
const ul=document.querySelector('#events');ul.replaceChildren();for(const e of d.events.filter(e=>Math.abs(e.time_us/1e6-f.t)<5&&['body_engulfed','capture_released','birth','consciousness_dead'].includes(e.kind)).slice(-15)){const li=document.createElement('li');li.textContent=e.kind==='body_engulfed'?`${(e.time_us/1e6).toFixed(2)}s：${e.predator} 捕获 ${e.individual}，外壳 ${e.shell.toFixed(2)}，持续 ${(e.contact_us/1e6).toFixed(2)}s`:e.kind==='capture_released'?`${(e.time_us/1e6).toFixed(2)}s：${e.individual} 与 ${e.predator} 脱离`:e.kind==='birth'?`${(e.time_us/1e6).toFixed(2)}s：${e.parent} 繁殖 ${e.individual}`:`${(e.time_us/1e6).toFixed(2)}s：意识 ${e.individual} 活动死亡`;ul.append(li)}}
s.oninput=()=>{clock=d.frames[+s.value].t;draw()};document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'暂停':'播放';last=0};
c.onclick=e=>{const r=c.getBoundingClientRect(),p=[(e.clientX-r.left)/r.width*side,(e.clientY-r.top)/r.height*side];const bs=d.frames[+s.value].members.filter(b=>b.physical).sort((a,b)=>Math.hypot(...a.position.map((v,i)=>v-p[i]))-Math.hypot(...b.position.map((v,i)=>v-p[i])));if(bs.length){selected=bs[0].id;draw()}};
function tick(t){if(playing){if(last){clock+=(t-last)/1000*+document.querySelector('#speed').value;while(+s.value<+s.max&&d.frames[+s.value+1].t<=clock)s.value=+s.value+1;draw();if(+s.value===+s.max){playing=false;document.querySelector('#play').textContent='播放'}}last=t}requestAnimationFrame(tick)}draw();requestAnimationFrame(tick);
</script></html>'''
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:f.write(html.replace('PAYLOAD',payload))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();create(a.case,a.output)
