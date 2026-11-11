"""Render complete sampled-node rankings and a compact evidence figure."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run import HERE,WORK,encoded


def make():
    data=json.loads((HERE/'analysis.json').read_bytes())
    records=[json.loads(line) for line in (HERE/'node-rankings.jsonl').read_text(encoding='utf-8').splitlines()]
    maps={(r['seed'],r['group']):r['contextual']['masks'] for r in json.loads((HERE/'mapping.json').read_bytes())}
    rows=[]
    for r in records:
        masks=maps[r['seed'],r['group']]
        nodes=[dict(rank=n['rank'],id=n['node_id'],channel=n['channel'],end=n['last_activation'],
                    peak=n['peak_activation'],candidate=n['candidate'],
                    reference='、'.join(k for k,v in masks.items() if str(n['channel']) in v))
               for n in r['rankings']['end_activation']]
        rows.append(dict(seed=r['seed'],stage=r['stage'],cue=r['cue'],dose=r['dose'],
                         classification=r['classification'],duration=r['duration_s'],nodes=nodes))
    rows.sort(key=lambda r:(r['stage']!='each20',r['dose']==0,r['seed'],r['stage'],r['cue']))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>背景配对：完整窗末排名</title>
<style>body{font:16px system-ui;background:#f5f8f5;color:#233f34;margin:30px}main{max-width:1200px;margin:auto}select{width:100%;padding:12px}table{border-collapse:collapse;width:100%;background:white}th,td{padding:10px;text-align:left;border-bottom:1px solid #ddd}th{position:sticky;top:0;background:#e5f0e9}.table{max-height:65vh;overflow:auto}#info{padding:16px;background:#fff2d8}</style>
<main><h1>宿主机背景配对：全部节点按窗末激活排序</h1><p>背景0.25，教学0.9，检验0.5；每10模拟秒一句。保留全部节点，不过滤背景或非候选。1e-12内并列。外部参照不是内核词义。</p>
<p><strong>本轮没有converged窗口。</strong>下表展示衰减或瞬态窗口的真实终态，不能冒称收敛答案。</p>
<label>选择观测窗口<select id="window"></select></label><p id="info"></p><div class="table"><table><thead><tr><th>强度排名</th><th>节点</th><th>通道</th><th>窗末激活</th><th>窗内峰值</th><th>原候选</th><th>外部配对参照</th></tr></thead><tbody id="nodes"></tbody></table></div><p id="total"></p></main>
<script id="data" type="application/json">PAYLOAD</script><script>
const rows=JSON.parse(document.querySelector('#data').textContent),select=document.querySelector('#window');
rows.forEach((r,i)=>{let o=document.createElement('option');o.value=i;o.textContent=`${r.seed} · ${r.stage} · ${r.cue} · 剂量${r.dose} · ${r.classification}`;select.append(o)});
function show(){const r=rows[Number(select.value)],body=document.querySelector('#nodes');body.replaceChildren();document.querySelector('#info').textContent=`${r.classification}；窗口${r.duration}模拟秒；${r.nodes.length}个实际节点。`;
r.nodes.forEach(n=>{const tr=document.createElement('tr');[n.rank,n.id,n.channel,n.end.toPrecision(17),n.peak.toPrecision(17),n.candidate?'是':'否',n.reference].forEach(v=>{let td=document.createElement('td');td.textContent=v;tr.append(td)});body.append(tr)});}
select.addEventListener('change',show);document.querySelector('#total').textContent=`共${rows.length}个窗口、${rows.reduce((n,r)=>n+r.nodes.length,0)}条实际节点记录；未删减。`;show();</script></html>'''
    (HERE/'rankings.html').write_text(page.replace('PAYLOAD',json.dumps(rows,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')),encoding='utf-8')
    fig,ax=plt.subplots(1,3,figsize=(13,3.6),layout='constrained')
    for p in sorted(WORK.glob('seed-*-trace.jsonl')):
        rs=[json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
        for arm in ('host','no-background'):
            series=[r for r in rs if r['arm']==arm]
            ax[0].plot([r['time_us']/1e6 for r in series],[r['metrics']['activation'] for r in series],
                       marker='.' if arm=='no-background' else None,label=f"{rs[0]['seed']} {arm}")
    ax[0].set(title='Whole-network activity',xlabel='Simulation seconds',ylabel='Sum of node activation');ax[0].legend(fontsize=7)
    ax[1].bar(['Converged','Residual decay','Transient'],[0,60,12],color=['#167263','#cd9853','#abb9b2'])
    ax[1].set(title='All 72 temporal windows',ylabel='Windows');ax[1].tick_params(axis='x',labelsize=8)
    labels=['41701','41702'];host=[1458,1458];text=[1866,1832]
    ax[2].bar(labels,host,label='Host to host');ax[2].bar(labels,text,bottom=host,label='Text to text')
    ax[2].set(title='Edges at 400 s: cross-source = 0',xlabel='Sensory seed',ylabel='Existing edges');ax[2].legend(fontsize=8)
    fig.savefig(HERE/'results.png',dpi=160);plt.close(fig)
    (HERE/'viewer-manifest.json').write_bytes(encoded(dict(windows=len(rows),node_rows=sum(len(r['nodes']) for r in rows),
        all_nodes=True,primary_converged_windows=0,ranking='last_activation, descending, tolerance=1e-12')))


if __name__=='__main__':make()
