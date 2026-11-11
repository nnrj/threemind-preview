"""Compact evidence tables, a scientific figure and an inspectable offline viewer."""
from collections import Counter,defaultdict
import gzip
import json
import statistics
from experiment import ROOT,HERE,WORK,OLD,read_json,new_json


def gz(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def compact(rows,keys):
    groups={}
    for row in rows:
        key=tuple(row[k] for k in keys)
        group=groups.setdefault(key,{k:row[k] for k in keys}|{'correct':0,'cue_specific':0,'total':0})
        for field in ('correct','cue_specific','total'):group[field]+=row[field]
    return list(groups.values())


def main():
    latency=read_json(WORK/'latency-summary.json');latency_rows=gz(WORK/'latency-output.json.gz')
    features=read_json(WORK/'feature-summary.json')
    new=read_json(WORK/'new-expression-summary.json')
    all_summary=read_json(WORK/'all-expression-summary.json')
    decoded=[]
    for scope,folder in (('cross','decoded'),('all','all-decoded')):
        for path in sorted((WORK/folder).glob('*.json')):decoded.extend([row|{'scope':scope} for row in read_json(path)])
    training=[]
    for scope in ('cross','all'):
      for regime in ('identity','two-assignments'):
        for modality in ('vision','words'):
            subset=[r for r in decoded if r['scope']==scope and r['decoder_training'] and r['regime']==regime and r['modality']==modality]
            training.append({'scope':scope,'regime':regime,'modality':modality,'total':len(subset),
                'transformer_correct':sum(r['transformer']['output']['text']==r['target'] for r in subset),
                'prototype_correct':sum(r['prototype']['text']==r['target'] for r in subset)})
    cases=[read_json(p) for p in (WORK/'cases').glob('*/result.json')]
    mediation=read_json(WORK/'known-mediation.json');mediation_summary=[]
    for scope,reference in (('cross',new),('all',all_summary)):
        baseline=sum(r['cue_specific'] for r in reference['summaries'] if r['instrument']=='transformer' and r['regime']=='two-assignments'
                     and r['modality']=='words' and r['condition'] in ('continued','reversal') and r['seconds']==592)
        counts={mask:sum(r['cue_specific'] for r in mediation['rows'] if r['scope']==scope and r['mask']==mask and r['item']>=0)
                for mask in ('target','matched')}
        mediation_summary.append({'scope':scope,'normal_correct':baseline,'total':24,**counts,
            'passed':baseline>0 and counts['target']<=baseline*.5 and counts['matched']>=baseline*.75})
    result={'study':'E47','project':read_json(WORK/'platform.json')['project_id'],
        'latency':{'outputs':len(latency_rows),'mismatches':latency['mismatches'],'readers':latency['readers'],
                   'all_zero_blank':sum(not r['zero_activity_output']['text'] for r in latency['readers']),
                   'timings':[{'variant':variant,'median_batch_seconds':statistics.median(r['batch_decode_seconds'] for r in latency_rows if r['variant']==variant),
                               'median_queue_seconds':statistics.median(r['queue_seconds'] for r in latency_rows if r['variant']==variant)} for variant in sorted({r['variant'] for r in latency_rows})]},
        'features':{'rows':features['rows'],'selected':features['selected'],'candidates':features['candidates'],
                    'compact':compact(features['summaries'],('mode','calibrate','regime','modality','condition','seconds'))},
        'new_expression':{'compact':compact(new['summaries'],('instrument','regime','modality','condition','seconds')),
                          'by_source':new['summaries'],'gates':new['gates'],'training':training},
        'all_expression':{'compact':compact(all_summary['summaries'],('instrument','regime','modality','condition','seconds')),
                          'by_source':all_summary['summaries'],'gates':all_summary['gates']},
        'known_mediation':{'summary':mediation_summary,'masks':mediation['masks'],'rows':mediation['rows']},
        'completed_cases':len(cases),'case_kinds':dict(Counter(r['kind'] for r in cases)),
        'compute_seconds':sum(r['wall_seconds'] for r in cases)+sum(read_json(p)['wall_seconds'] for p in (WORK/'timing').glob('*.json')),
        'core_modified':False,'defaults_modified':False,'usage_latest':read_json(WORK/'usage.json')['used_percent']}
    new_json(HERE/'results.json',result)
    figure(result)
    process_figure()
    viewer(result,latency_rows,decoded)
    print(json.dumps({'cases':len(cases),'minutes':result['compute_seconds']/60,'gates':new['gates'],'training':training}),flush=True)


def figure(r):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(1,3,figsize=(16,4.5),layout='constrained')
    configs=[('absolute','frozen266'),('absolute','refitted'),('paired-inhibition','frozen266'),('paired-inhibition','refitted')]
    for j,modality in enumerate(('vision','words')):
        entries=[next(row for row in r['features']['compact'] if row['mode']==mode and row['regime']==regime and row['modality']==modality
                      and row['condition']=='normal' and row['seconds']==326 and not row['calibrate']) for mode,regime in configs]
        values=[row['cue_specific']/row['total'] for row in entries]
        x=np.arange(4)+j*.36
        bars=axes[0].bar(x,values,.34,label='word → object' if j==0 else 'visual → name')
        axes[0].bar_label(bars,labels=[f"{row['cue_specific']}/{row['total']}" for row in entries],padding=3)
    axes[0].set_xticks(np.arange(4)+.18,['Activation\nfrozen','Activation\nrefit','A+I contrast\nfrozen','A+I contrast\nrefit'])
    axes[0].set_ylim(0,1.16);axes[0].set_title('60s wait: information versus old readout');axes[0].legend(fontsize=8)
    for panel,scope in ((1,'new_expression'),(2,'all_expression')):
      entries=[]
      for regime in ('identity','two-assignments'):
        for modality in ('vision','words'):
            group=[row for row in r[scope]['compact'] if row['instrument']=='transformer' and row['regime']==regime and row['modality']==modality
                   and row['condition'] in ('cycle1','cycle2') and row['seconds']==532]
            entries.append((sum(row['cue_specific'] for row in group),sum(row['total'] for row in group)))
      bars=axes[panel].bar(range(4),[a/b for a,b in entries],color=['#719d92','#9bb4c8','#276b62','#467e9d'])
      axes[panel].bar_label(bars,labels=[f'{a}/{b}' for a,b in entries],padding=3)
      axes[panel].set_xticks(range(4),['Identity\nword→object','Identity\nvisual→name','Two maps\nword→object','Two maps\nvisual→name'])
      axes[panel].set_ylim(0,1.16);axes[panel].axhline(.75,color='#a7703a',linestyle=':',label='registered threshold')
      axes[panel].set_title(('Cross-sensory' if panel==1 else 'All channels')+': unseen assignments');axes[panel].legend(fontsize=8)
    for ax in axes:ax.spines[['top','right']].set_visible(False);ax.set_ylabel('Cue-specific exact proportion')
    fig.suptitle('ThreeMind E47 · Three sources per stage; probes are not independent individuals')
    fig.savefig(HERE/'findings.png',dpi=160);fig.savefig(HERE/'findings.svg');plt.close(fig)


def viewer(result,latency_rows,decoded):
    simple=[{k:r[k] for k in ('seed','condition','seconds','modality','item','variant','target','regime','scope')}|
            {'text':r['transformer']['output']['text'],'finite':r['prototype']['text'],
             'window':r['transformer']['window'],'magnitude':r['contrast_magnitude']} for r in decoded if r['split']=='test']
    data=json.dumps({'result':result,'latency':latency_rows,'items':simple},ensure_ascii=False).replace('<','\\u003c')
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E47 表达与活动</title>
<style>body{margin:0;background:#f2f6f4;color:#203c36;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1200px;margin:auto;padding:24px}h1{font-size:27px;margin:4px 0}h2{font-size:20px}small,.muted{color:#59706a}section{background:white;border:1px solid #dbe5df;border-radius:12px;padding:20px;margin:18px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{padding:16px;background:#e6f1ec;border-radius:8px}.card b{display:block;font-size:23px}select,button{font:inherit;padding:8px;border:1px solid #b4cac0;border-radius:6px;background:white;color:inherit}label{display:inline-flex;gap:8px;align-items:center;margin:4px 12px 8px 0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:9px;border-bottom:1px solid #e5ebe7;vertical-align:top}th{background:#eaf2ef}td.word{word-break:break-all;min-width:80px;max-width:260px}.note{background:#fff6e4;padding:12px;border-radius:6px}.good{color:#126b51}.bad{color:#9c5639}@media(max-width:600px){main{padding:12px}.cards{grid-template-columns:1fr}section{padding:12px}label{display:flex;justify-content:space-between}select{max-width:65%}h1{font-size:23px}}</style>
<main><small>THREEMIND / E47 / 原始活动与原样释读</small><h1>表达延迟、抑制变化与新经历</h1><p>保留模拟采样时间，分别查看仪器校准和冻结表达的新对应检验。所有结果来自真实记录；这里没有重演或生成新模拟。</p>
<div class="cards"><div class="card"><b id="delay"></b>同窗口处理方式导致的文本差异</div><div class="card"><b>48 / 48</b>已校准两种经历的视觉命名（3个意识）</div><div class="card"><b id="gate"></b>冻结表达的新对应门槛</div></div>
<section><h2>逐题查看：表达器有没有跟着新经历改变答案？</h2><p class="note">实际输入强度0.5。表达器训练只见原对应和反对应，循环1/2的答案没有提供给它。表中预期答案仅供研究者核对。空白显示为“∅”，错误文字保持原样。两种范围均读取激活＋抑制的副本差值，并非完整绝对状态。</p>
<label>意识<select id="seed"></select></label><label>方向<select id="modality"><option value="vision">文字→物体</option><option value="words">视觉→名字</option></select></label><label>表达训练<select id="regime"><option value="two-assignments">原对应＋反对应</option><option value="identity">只见原对应</option></select></label><label>经历<select id="condition"><option value="cycle1">未见对应：循环1</option><option value="cycle2">未见对应：循环2</option><option value="normal">首次教学</option><option value="continued">继续原教学</option><option value="reversal">反转教学</option><option value="frozen">内核不学习对照</option></select></label>
<div class="scroll"><table><thead><tr><th>采样模拟秒</th><th>提示项/形式</th><th>预期</th><th>Transformer原文</th><th>有限词表对照</th><th>是否正确</th></tr></thead><tbody id="items"></tbody></table></div><p id="score"></p>
</section><section><h2>延迟核查：晚显示不等于晚活动</h2><p>同一窗口以五种方式处理。排队和解码秒是宿主时间，采样秒是模拟时间；两类时钟不可混算。</p><label>表达器<select id="reader"></select></label><div class="scroll"><table><thead><tr><th>原采样区间</th><th>处理方式</th><th>排队秒</th><th>整批解码秒</th><th>原样输出</th></tr></thead><tbody id="latency"></tbody></table></div></section>
<section><h2>哪些判断不能混在一起</h2><p>当前状态重新校准能区分提示，说明读出有信息；只有冻结表达后还能跟着新经历改变，才支持本轮的新对应学习。被动输出文字不自动等于有目的地说话。一般关系组合、自由推理和自然对话须另有相应任务的证据。</p><p class="muted">内部模式释读可以碎片化；表达工具的次序和语义忠实性则需单独训练、检验。原始激活与抑制均保留。</p></section></main>
<script>const D=DATA;const $=id=>document.getElementById(id);function cell(tr,text,cls=''){let td=document.createElement('td');td.textContent=String(text);td.className=cls;tr.appendChild(td)}function options(id,values){for(let v of values){let x=document.createElement('option');x.value=v;x.textContent=v;$(id).appendChild(x)}}options('seed',[...new Set(D.items.map(r=>r.seed))]);options('reader',[...new Set(D.latency.map(r=>r.reader))]);$('delay').textContent=D.result.latency.mismatches+' / '+D.result.latency.outputs;$('gate').textContent=D.result.new_expression.gates.some(r=>r.passed)?'通过至少一项':'本轮未通过';
function render(){let rows=D.items.filter(r=>r.seed==$('seed').value&&r.modality==$('modality').value&&r.regime==$('regime').value&&r.condition==$('condition').value);$('items').replaceChildren();for(let r of rows){let tr=document.createElement('tr');cell(tr,(Number(r.window.start_us)/1e6).toFixed(1)+'–'+(Number(r.window.end_us)/1e6).toFixed(1));cell(tr,r.item<0?'无提示':(r.modality==='words'?['红球','蓝盒','绿柱','黄块'][r.item]+' / 视角'+r.variant:['甲','乙','丁','戊'][r.item]+(r.variant?'是':'')));cell(tr,r.target||'∅');cell(tr,r.text||'∅','word');cell(tr,r.finite||'∅','word');cell(tr,r.text===r.target?'正确':'未匹配',r.text===r.target?'good':'bad');$('items').appendChild(tr)}let cues=rows.filter(r=>r.item>=0);$('score').textContent='显示 '+rows.length+' 条；提示精确匹配 '+cues.filter(r=>r.text===r.target).length+'/'+cues.length+'（含两个观察时间，完整判据另计无提示差异）。'}function latency(){let rows=D.latency.filter(r=>r.reader==$('reader').value);$('latency').replaceChildren();for(let r of rows){let tr=document.createElement('tr');cell(tr,Number(r.window.start_us)/1e6+'–'+Number(r.window.end_us)/1e6);cell(tr,r.variant);cell(tr,r.queue_seconds.toFixed(4));cell(tr,r.batch_decode_seconds.toFixed(4));cell(tr,r.output.text||'∅','word');$('latency').appendChild(tr)}}for(let id of ['seed','modality','regime','condition'])$(id).addEventListener('change',render);$('reader').addEventListener('change',latency);render();latency();</script></html>'''
    table=''.join('<tr><td>'+('跨感官' if r['scope']=='cross' else '全部通道')+'</td><td>'+str(r['normal_correct'])+'/24</td><td>'+str(r['target'])+'/24</td><td>'+str(r['matched'])+'/24</td></tr>' for r in result['known_mediation']['summary'])
    html=html.replace('<section><h2>哪些判断不能混在一起', '<section><h2>已校准表达是否依赖内部通路</h2><p>同一表达器、592秒、原对应/反对应，共24个视觉命名。目标是跨感官连接；其他连接数量相同，但总权重仅为目标的66.3%～72.7%，拓扑未匹配。</p><div class="scroll"><table><thead><tr><th>范围</th><th>正常答对</th><th>目标通路静默</th><th>其他连接静默</th></tr></thead><tbody>'+table+'</tbody></table></div></section><section><h2>哪些判断不能混在一起')
    html=html.replace('<label>意识<select','<label>观察范围<select id="scope"><option value="all">全部通道</option><option value="cross">排除直接输入感官</option></select></label><label>意识<select')
    html=html.replace("D.result.new_expression.gates.some(r=>r.passed)","[...D.result.new_expression.gates,...D.result.all_expression.gates].some(r=>r.passed)")
    html=html.replace("r.seed==$('seed').value&&r.modality", "r.scope==$('scope').value&&r.seed==$('seed').value&&r.modality")
    html=html.replace("['seed','modality','regime','condition']","['scope','seed','modality','regime','condition']")
    (WORK/'expression-alignment.html').write_text(html.replace('DATA',data),encoding='utf-8')


def process_figure():
    """Physical test inputs versus activity in the other (language) domain."""
    import matplotlib.pyplot as plt
    import numpy as np
    channels=sorted(read_json(WORK/'projection.json')['vision']['excluded_channels'])
    paths=[OLD/'cases'/f's137-normal-t326-words{i}-v9-i0.5-test-none/process.json.gz' for i in range(4)]
    base=gz(OLD/'cases/s137-normal-t326-words-1-v0-i0.5-test-none/process.json.gz')
    bodies=[gz(p) for p in paths]
    fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    labels=['Red sphere','Blue box','Green cylinder','Yellow block']
    for column,field in enumerate(('activation','inhibition')):
        summaries=[]
        for body,label in zip(bodies,labels,strict=True):
            values=[]
            for frame,background in zip(body['trajectory'],base['trajectory'],strict=True):
                measured={int(n['channel']):float(n[field]) for n in frame['nodes']}
                baseline={int(n['channel']):float(n[field]) for n in background['nodes']}
                values.append([measured.get(c,0)-baseline.get(c,0) for c in channels])
            values=np.asarray(values)
            times=[(int(f['time_us'])-int(body['start_us']))/1e6 for f in body['trajectory']]
            axes[0,column].plot(times,values.sum(axis=1),label=label)
            summaries.append(np.trapezoid(values,x=times,axis=0))
        axes[0,column].set(title=f'Language-domain {field} response',xlabel='Seconds after visual prompt',ylabel='Sum of change from no-cue twin')
        axes[0,column].legend(fontsize=8);axes[0,column].spines[['top','right']].set_visible(False)
        array=np.asarray(summaries);limit=max(float(np.abs(array).max()),1e-12)
        image=axes[1,column].imshow(array,aspect='auto',cmap='RdBu_r',vmin=-limit,vmax=limit,interpolation='nearest')
        axes[1,column].set(yticks=range(4),yticklabels=labels,xlabel='Anonymous language-channel column (not a semantic label)',title='Integrated local pattern; original units')
        fig.colorbar(image,ax=axes[1,column],label=f'{field} × simulated seconds')
    fig.suptitle('E47 · Same326s state, four held-out physical views · Input visual channels not shown')
    fig.savefig(HERE/'process-patterns.png',dpi=160);plt.close(fig)


if __name__=='__main__':main()
