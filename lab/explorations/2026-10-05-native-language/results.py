"""Produce measured summaries and a bounded, local activity/text viewer."""
from collections import Counter
import gzip
import json
import shutil
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import psutil

from analyse import analyze, compact, decoded
from experiment import HERE, ROOT, WORK, read_json, new_json


def collect():
    result=analyze();result['compact']=compact(result)
    direct=read_json(HERE/'direct-acceptance.json')['rows']
    result['direct_acceptance']=[{'modality':m,'split':split,'no_cue':no_cue,
        'correct':sum(r['correct'] for r in direct if r['modality']==m and r['split']==split and (r['item']<0)==no_cue),
        'count':sum(r['modality']==m and r['split']==split and (r['item']<0)==no_cue for r in direct)}
        for m in ('vision','words') for split in ('train','test') for no_cue in (False,True)]
    intervention=read_json(HERE/'initial-mediation.json');base={r['id']:r for r in decoded() if r['regime']=='individual'}
    mediation=[]
    for selected in intervention['selected']:
        for ident in selected['initial_correct_ids']:
            before=base[ident]
            for mask in ('target','matched'):
                candidates=[r for r in intervention['rows'] if r['seed']==before['seed'] and r['modality']==before['modality'] and r['mask']==mask]
                if not candidates:continue
                after=next(r for r in candidates if r['item']==before['item'] and r['variant']==before['variant'])
                null=next(r for r in candidates if r['item']<0)
                mediation.append({'seed':before['seed'],'modality':before['modality'],'before_case':ident,
                    'after_case':after['id'],'target':before['target'],'before':before['transformer']['text'],
                    'after':after['transformer']['text'],'no_cue':null['transformer']['text'],'mask':mask,
                    'retained':after['transformer']['text']==before['target'],
                    'cue_specific_retained':after['transformer']['text']==before['target'] and after['transformer']['text']!=null['transformer']['text']})
    result['mediation']=mediation
    result['mediation_summary']=[{'modality':modality,'mask':mask,
        'count':sum(r['modality']==modality and r['mask']==mask for r in mediation),
        'retained':sum(r['modality']==modality and r['mask']==mask and r['retained'] for r in mediation),
        'cue_specific_retained':sum(r['modality']==modality and r['mask']==mask and r['cue_specific_retained'] for r in mediation)}
        for modality in ('vision','words') for mask in ('target','matched')]
    result['continuous']=read_json(HERE/'continuous-results.json')
    cases=[read_json(p) for p in (WORK/'cases').glob('*/result.json')]
    timings=[read_json(p)['wall_seconds'] for p in (WORK/'timing').glob('*.json')]
    result['completed_cases']=len(cases)
    result['case_kinds']=dict(Counter(r['kind'] for r in cases))
    result['resources']={'compute_seconds':sum(r['wall_seconds'] for r in cases)+sum(timings),
        'case_wall_seconds':sum(r['wall_seconds'] for r in cases),'additional_compute_seconds':sum(timings),
        'elapsed_seconds':time.time()-read_json(WORK/'platform.json')['started_at_epoch'],
        'work_bytes_before_archive':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
        'available_memory':psutil.virtual_memory().available,
        'free_c':shutil.disk_usage('C:/').free,'free_e':shutil.disk_usage('E:/').free,
        'account_start':41,'account_latest':read_json(WORK/'usage.json')['used_percent'],
        'account_scope':'shared account, conservatively includes other work'}
    result['gates']={}
    for regime in ('individual','shared','developmental','history-cold','direct'):
        for modality,threshold in (('vision',6),('words',3)):
            rows=[r for r in result['joint_summary'] if r['regime']==regime and r['modality']==modality and r['instrument']=='transformer' and r['seconds']==532]
            result['gates'][regime+':'+modality]={'passing_seeds':sum(r['correct']>=threshold for r in rows),
                'cue_specific_passing_seeds':sum(r['cue_specific_correct']>=threshold for r in rows),'required_seeds':2,
                'passed':sum(r['correct']>=threshold for r in rows)>=2}
    result['decisions']={'relational_composition':'not_started_original_basic_gate_failed',
        'autonomous_reentry_interventions':'not_run_no_registered_candidates',
        'active_expression_selection':'not_tested','core_or_defaults_changed':False,
        'followup':'align expression with evolving representations; retain original criteria'}
    return result


def figure(result):
    def value(regime,modality,condition='normal',seconds=266):
        return next(r for r in result['compact'] if r['regime']==regime and r['modality']==modality and r['condition']==condition
                    and r['seconds']==seconds and not r['no_cue'] and r['instrument']=='transformer')
    methods=['direct','shared','individual','developmental','history-cold']
    names=['Direct sensation','Shared','Individual','Developmental','History cold-start']
    fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    for axis,modality,title in zip(axes[:2],('vision','words'),('Word to object','Vision to name'),strict=True):
        rows=[value(m,modality) for m in methods];x=np.arange(len(rows))
        axis.barh(x,[r['correct']/r['n'] for r in rows],color='#cbd9d8',label='Exact match')
        axis.barh(x,[r['specific']/r['n'] for r in rows],color='#177567',label='Also differs from no cue')
        for i,r in enumerate(rows):axis.text(r['correct']/r['n']+.012,i,f"{r['correct']}/{r['n']} ({r['specific']})",va='center',fontsize=9)
        axis.set_yticks(x,names);axis.invert_yaxis();axis.set_xlim(0,1);axis.set_title(title+' at266s');axis.set_xlabel('Fraction of held-out prompts')
        axis.spines[['top','right']].set_visible(False)
    ax=axes[2]
    for modality,marker in (('vision','o'),('words','s')):
        rows=[value('individual',modality,condition,seconds) for condition,seconds in (('normal',266),('normal',326),('continued',532),('reversal',532))]
        ax.plot(range(4),[r['specific']/r['n'] for r in rows],marker=marker,label='Word→object' if modality=='vision' else 'Vision→name')
    ax.set_xticks(range(4),['Initial','+60s','More teaching','Reversed'],rotation=18);ax.set_ylim(-.025,1)
    ax.set_title('Frozen individual decoder');ax.set_ylabel('Cue-specific correct fraction');ax.legend(fontsize=8)
    ax.spines[['top','right']].set_visible(False)
    fig.suptitle('E46: personal calibration improves initial expression; frozen transfer fails\n3 source instances; repeated prompts are not independent brains',fontsize=13)
    axes[0].legend(fontsize=8,loc='lower right')
    fig.savefig(HERE/'findings.png',dpi=150);fig.savefig(HERE/'findings.svg');plt.close(fig)
    svg=HERE/'findings.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')


def viewer(result):
    histories={}
    for path in sorted((WORK/'continuous').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf-8') as f:
            histories[path.name.removesuffix('.jsonl.gz')]=[
                {'time':int(r['end_us'])/1e6,'start':int(r['start_us'])/1e6,
                 'activity':r['activity'],'text':{k:v['text'] for k,v in r['text'].items()}}
                for r in map(json.loads,f)]
    payload=json.dumps({'histories':histories,'mediation':result['mediation']},ensure_ascii=True).replace('</','<\\/')
    page=r'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>E46 内部活动与原样释读</title><style>
body{font:15px system-ui;color:#203c38;background:#f2f6f5;margin:0;padding:24px;max-width:1300px;margin:auto}h1{font-size:26px}h2{font-size:19px}section{background:white;border:1px solid #d3e1dd;border-radius:10px;padding:20px;margin:16px 0}select,input,button{font:inherit;padding:7px;border:1px solid #bccfc7;border-radius:5px}canvas{width:100%;height:260px}.controls{display:flex;gap:12px;flex-wrap:wrap}.muted{color:#576f66;line-height:1.6}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf4f1;padding:12px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd}.table{overflow:auto}input[type=range]{flex:1;min-width:150px}@media(max-width:600px){body{padding:12px}section{padding:12px}h1{font-size:22px}}
</style><h1>E46 · 内部活动与原样释读</h1><p class="muted">真实连续记录，保留物理遥测背景，没有新教学。文字是观察工具的输出，不自动代表意识选择发言。每个读出使用2秒过程，步移0.5秒；窗口重叠，不是独立重复实验。Raw passive interpretation, not voluntary speech.</p>
<section><div class="controls"><select id="source" aria-label="来源"></select><select id="head" aria-label="表达器"><option value="individual">个体表达器 / Individual</option><option value="developmental">随发育训练 / Developmental</option></select></div><canvas id="chart"></canvas><p>绿色：语言通道　蓝色：视觉通道　灰色：背景　橙色：全网抑制（各自归一化，仅看变化）</p><div class="controls"><button id="play">播放</button><input id="time" type="range" min="0" value="0" aria-label="模拟时刻"><output id="when"></output></div><pre id="text"></pre><p id="amount" class="muted"></p></section>
<section><h2>最初正确响应的局部连接对照</h2><p class="muted">目标：语言与视觉之间的连接。匹配：相同数量、近似权重的其他连接。来源根据干预前的正确输出选取，不是新增独立准确率样本。</p><div class="table"><table><thead><tr><th>种子/方向</th><th>干预</th><th>原响应</th><th>干预后</th><th>同状态无提示</th></tr></thead><tbody id="mediation"></tbody></table></div></section>
<script>const data=__DATA__;const source=document.querySelector('#source'),head=document.querySelector('#head'),range=document.querySelector('#time'),canvas=document.querySelector('#chart');let timer=null;
for(const key of Object.keys(data.histories)){let o=document.createElement('option');o.value=key;o.textContent=key;source.append(o)}
function draw(){const rows=data.histories[source.value],idx=Math.min(+range.value,rows.length-1);range.max=rows.length-1;const r=rows[idx];document.querySelector('#when').textContent=r.start.toFixed(1)+'–'+r.time.toFixed(1)+' 模拟秒';document.querySelector('#text').textContent='物体词释读：'+JSON.stringify(r.text[head.value+':vision'])+'\n名字释读：'+JSON.stringify(r.text[head.value+':words']);document.querySelector('#amount').textContent='窗内峰值：语言 '+r.activity.language.peak.toExponential(3)+'；视觉 '+r.activity.vision.peak.toExponential(3)+'；背景 '+r.activity.background.peak.toExponential(3)+'；全网抑制 '+r.activity.inhibition.peak.toExponential(3);let dpr=devicePixelRatio||1,w=canvas.clientWidth,h=260;canvas.width=w*dpr;canvas.height=h*dpr;let c=canvas.getContext('2d');c.scale(dpr,dpr);c.fillStyle='#f5f8f7';c.fillRect(0,0,w,h);for(const [key,color] of [['language','#157567'],['vision','#367bb2'],['background','#8b9391'],['inhibition','#bb8238']]){let maximum=Math.max(1e-8,...rows.map(x=>x.activity[key].peak));c.beginPath();c.strokeStyle=color;c.lineWidth=1.4;rows.forEach((x,i)=>{let a=i/(rows.length-1)*(w-30)+15,b=h-15-x.activity[key].peak/maximum*(h-35);if(i)c.lineTo(a,b);else c.moveTo(a,b)});c.stroke()}c.beginPath();c.strokeStyle='#111';let x=idx/(rows.length-1)*(w-30)+15;c.moveTo(x,5);c.lineTo(x,h-5);c.stroke()}
source.onchange=()=>{range.value=0;draw()};head.onchange=draw;range.oninput=draw;addEventListener('resize',draw);document.querySelector('#play').onclick=()=>{if(timer){clearInterval(timer);timer=null;document.querySelector('#play').textContent='播放';return}document.querySelector('#play').textContent='暂停';timer=setInterval(()=>{range.value=(+range.value+1)%(+range.max+1);draw()},200)};
for(const r of data.mediation){let tr=document.createElement('tr');for(const v of [r.seed+' / '+r.modality,r.mask,r.before,r.after,r.no_cue]){let td=document.createElement('td');td.textContent=v;tr.append(td)}document.querySelector('#mediation').append(tr)}draw();</script></html>'''.replace('__DATA__',payload)
    with (WORK/'native-expression.html').open('x',encoding='utf-8') as f:f.write(page)


if __name__=='__main__':
    result=collect();new_json(HERE/'results.json',result);figure(result);viewer(result)
    print(json.dumps({'cases':result['completed_cases'],'resources':result['resources'],
        'direct':result['direct_acceptance'],'mediation':result['mediation_summary'],'gates':result['gates']},ensure_ascii=True))
