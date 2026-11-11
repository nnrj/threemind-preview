"""Compact scientific figure and paginated raw-output inspection."""
import html
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiment import *


def main():
    r=read_json(HERE/'results.json')
    models={m['name']:m for m in r['decoders']}
    selected=[('A + I','223-words-activity-all'),('History /1200','223-words-history-all'),
        ('Graph /1200','223-graph'),('History /6000','223-words-history-all-steps6000'),
        ('101 samples','223-words-history-all-samples101'),('No blank teaching','223-words-history-all-steps6000-unlabelled-no-cue')]
    selected=[x for x in selected if x[1] in models]
    fig,axes=plt.subplots(1,2,figsize=(11,4.7),layout='constrained')
    ax=axes[0];rates=[models[k]['fit_correct']/models[k]['fit_count'] for _,k in selected]
    ax.barh([x[0] for x in selected],rates,color='#167d91');ax.set_xlim(0,1.12);ax.invert_yaxis()
    for i,(_,key) in enumerate(selected):
        m=models[key];ax.text(rates[i]+.025,i,f"{m['fit_correct']}/{m['fit_count']}",va='center',fontsize=9)
    ax.set_title('Decoder calibration, source223');ax.set_xlabel('Training items answered correctly')
    ax=axes[1];labels=['Joint','Separate','Learning off'];x=np.arange(3)
    events=r['events']['summary'];a=[];b=[]
    for mode in ('joint','split','frozen'):
        for scope,target in (('all',a),('cross',b)):
            rows=[v for v in events if v['mode']==mode and v['scope']==scope]
            target.append(sum(v['raw_correct'] for v in rows)/sum(v['count'] for v in rows))
    ax.bar(x-.18,a,.36,label='All nodes',color='#167d91');ax.bar(x+.18,b,.36,label='Direct sensors excluded',color='#ce8658')
    ax.axhline(.5,color='#667577',ls=':',lw=1,label='Two-class chance');ax.set_xticks(x,labels);ax.set_ylim(0,1.15)
    ax.set_title('Event direction on new objects');ax.set_ylabel('Actual correct outputs');ax.legend(fontsize=8,loc='lower left')
    fig.suptitle('E48 | Raw state and temporal experience | Core unchanged',fontsize=13)
    fig.savefig(HERE/'findings.png',dpi=160);fig.savefig(HERE/'findings.svg');plt.close(fig)
    rows=[]
    for folder in ('raw-models','graph-models'):
        for path in sorted((WORK/folder).glob('*.json')):
            model=read_json(path)
            for row in model['rows']:
                rows.append({'model':path.stem,**{k:row[k] for k in ('seed','condition','seconds','item','target','output','correct')}})
    payload=json.dumps(rows,ensure_ascii=False).replace('<','\\u003c')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E48原始表达核对</title>
<style>body{font:15px system-ui;background:#f0f6f5;color:#173939;max-width:1250px;margin:auto;padding:24px}h1{font-size:26px}select,button{padding:8px;border:1px solid #bbcecc;border-radius:6px;background:white;color:inherit}table{border-collapse:collapse;background:white;min-width:950px;width:100%}td,th{padding:9px;border-bottom:1px solid #e0ebe8;text-align:left}th{background:#dcebe8}.scroll{overflow:auto}.muted{color:#56716c}nav{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:20px 0}</style>
<h1>E48 · 原始表达核对</h1><p>模型直接读取已登记的原始状态与过程，没有无提示相减或单样本归一化；没有跨轮对话缓存。</p>
<p>“实际答对”比较教学对应；“旧提示特异”额外要求不同于无提示输出。后者扣分不等于没有回应。无提示条目没有已知语义真值，原样展示。</p>
<nav><label>表达器 <select id="model"></select></label><label>经历 <select id="condition"><option value="">全部</option></select></label><button id="prev">上一页</button><button id="next">下一页</button><span id="count"></span></nav>
<div class="scroll"><table><thead><tr><th>来源/秒</th><th>经历</th><th>物体</th><th>教学对应</th><th>原样输出</th><th>实际答对</th><th>旧提示特异</th></tr></thead><tbody id="body"></tbody></table></div>
<p class="muted">每页80条；完整轨迹、五时刻状态、训练模型与旧证据依赖见证据包。这是研究表达器输出，不是已验证的内心独白。</p>
<script>const rows=PAYLOAD;let page=0;const m=document.getElementById('model'),c=document.getElementById('condition');
for(const x of [...new Set(rows.map(r=>r.model))])m.add(new Option(x,x));for(const x of [...new Set(rows.map(r=>r.condition))])c.add(new Option(x,x));
function draw(){const chosen=rows.filter(r=>r.model===m.value&&(!c.value||r.condition===c.value));page=Math.max(0,Math.min(page,Math.ceil(chosen.length/80)-1));document.getElementById('count').textContent=`${chosen.length}条，第${page+1}页`;const b=document.getElementById('body');b.replaceChildren();
for(const r of chosen.slice(page*80,page*80+80)){const tr=document.createElement('tr');const actual=r.item<0?'无真值':r.output===r.target?'是':'否';for(const text of [`${r.seed} / ${r.seconds}`,r.condition,r.item<0?'无提示':r.item,r.item<0?'未提供真值':r.target,r.output||'（空白）',actual,r.item<0?'不计分':r.correct?'是':'否']){const td=document.createElement('td');td.textContent=text;tr.append(td)}b.append(tr)}}m.onchange=c.onchange=()=>{page=0;draw()};document.getElementById('prev').onclick=()=>{page--;draw()};document.getElementById('next').onclick=()=>{page++;draw()};draw();</script></html>'''
    (WORK/'raw-expression.html').write_text(page.replace('PAYLOAD',payload),encoding='utf-8')
    print({'viewer_rows':len(rows),'models':len(models)})


if __name__=='__main__':main()
