"""Figures, a complete endpoint-ranking viewer, and bilingual evidence reports."""
import html
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from run import HERE,WORK,encoded


def make():
    data=json.loads((HERE/'analysis.json').read_bytes())
    audit=json.loads((HERE/'acceptance-prepublish.json').read_bytes())
    maps={(m['seed'],m['group']):m for m in json.loads((HERE/'mapping.json').read_bytes())}
    cases=data['cases']; final=[c for c in cases if c['stage']=='each200' and c['dose']==1]
    assert len(final)==36 and all(c['converged'] and c['context_outcome']['classification']=='tie' for c in final)
    # The viewer shows every recorded node, not only candidates or matched terms.
    rows=[]
    for line in (HERE/'node-rankings.jsonl').read_text(encoding='utf-8').splitlines():
        record=json.loads(line)
        mask=maps[(record['seed'],record['group'])]['contextual']['masks']
        table=[]
        for n in record['rankings']['end_activation']:
            matched=[term for term,weights in mask.items() if str(n['channel']) in weights]
            table.append([n['rank'],n['node_id'],n['channel'],n['last_activation'],n['peak_activation'],
                          bool(n['candidate']),n['score'],' / '.join(matched)])
        rows.append(dict(seed=record['seed'],arm=record['arm'],stage=record['stage'],cue=record['cue'],
          dose=record['dose'],classification=record['classification'],reason=record['reason'],
          duration_s=record['duration_s'],calibration_id=record['calibration_id'],case_id=record['case_id'],
          window_id=record['window_id'],table=table))
    rows.sort(key=lambda r:(r['stage']!='each200',r['dose']!=1,r['seed'],r['arm'],r['cue']))
    payload=json.dumps(rows,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    viewer='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>松子铃铛：时序窗末完整强度排序</title><style>
body{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#f6f8f5;color:#223c35;margin:0;padding:24px}main{max-width:1150px;margin:auto}
h1{font-size:24px}p{line-height:1.6}select{padding:10px;width:100%;background:white;border:1px solid #9baea4;border-radius:6px}
table{border-collapse:collapse;width:100%;background:white;font-variant-numeric:tabular-nums;font-size:13px}th,td{padding:8px;border-bottom:1px solid #dce4de;text-align:left}
th{position:sticky;top:0;background:#e5eee9}#meta{padding:16px;background:#e9f2ed;margin:12px 0}#table{max-height:70vh;overflow:auto}.note{font-size:13px;color:#506d63}
</style><main><h1>时序窗末：全部节点按激活强度排序</h1>
<p>训练原文只有“甲是松子”“乙是铃铛”。选择一个实际测量窗口；非收敛窗口保留原分类。数值容差1e-12内并列，编号只用于稳定显示。外部通道索引不是节点语义，也没有参与内核计算。</p>
<label for="case">选择窗口（AB／BA仅改变教学先后；剂量0为对照）</label><select id="case"></select><div id="meta" aria-live="polite"></div>
<div id="table"><table><thead><tr><th>强度排名</th><th>节点</th><th>通道</th><th>窗末激活</th><th>窗内峰值</th><th>原候选</th><th>原综合分数</th><th>外部配对索引</th></tr></thead><tbody id="body"></tbody></table></div>
<p class="note">本页面由固定证据生成，完整节点未按候选、语义或预期答案过滤。独立词模板的覆盖率、原始窗口及全部曲线另见报告和证据ZIP。</p></main>
<script id="data" type="application/json">PAYLOAD</script><script>
const data=JSON.parse(document.getElementById('data').textContent),picker=document.getElementById('case');
for(let i=0;i<data.length;i++){const r=data[i],o=document.createElement('option');o.value=i;o.textContent=`${r.seed} · ${r.arm} · ${r.stage} · ${r.cue} · 剂量${r.dose} · ${r.classification}`;picker.appendChild(o)}
function render(){const r=data[Number(picker.value)],body=document.getElementById('body');body.replaceChildren();document.getElementById('meta').textContent=`${r.classification} / ${r.reason}；窗口 ${r.duration_s} 秒；${r.table.length} 个已记录节点；window_id：${r.window_id}`;
for(const row of r.table){const tr=document.createElement('tr');row.forEach((v,i)=>{const td=document.createElement('td');td.textContent=i===5?(v?'是':'否'):(i===3||i===4||i===6?Number(v).toPrecision(15):v);tr.appendChild(td)});body.appendChild(tr)}}
picker.addEventListener('change',render);render();</script></html>'''.replace('PAYLOAD',payload)
    (HERE/'rankings.html').write_text(viewer,encoding='utf-8',newline='\n')

    fig,ax=plt.subplots(1,3,figsize=(13.8,4.3),layout='constrained')
    stages=['untrained','each20','each200']
    conv=[sum(c['stage']==s and c['dose']==1 and c['converged'] for c in cases) for s in stages]
    other=[sum(c['stage']==s and c['dose']==1 and not c['converged'] for c in cases) for s in stages]
    ax[0].bar(stages,conv,color='#198575',label='Converged')
    ax[0].bar(stages,other,bottom=conv,color='#b5beb7',label='Residual decay')
    ax[0].set(xticks=range(3),xticklabels=['Untrained','20 / sentence','200 / sentence'],ylabel='Positive-dose windows',title='Temporal classification')
    ax[0].legend(frameon=False,fontsize=9)
    for p in sorted(WORK.glob('seed-*-trace.jsonl')):
        trace=[json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
        for arm in ('AB','BA'):
            subset=[r for r in trace if r['arm']==arm]
            ax[1].plot([r['count'] for r in subset],[r['metrics']['mean_weight'] for r in subset],
                       label=f"{subset[0]['seed']} {arm}",linestyle='-' if arm=='AB' else '--',alpha=.8)
    ax[1].set(xlabel='Cumulative teaching inputs',ylabel='Mean edge weight',title='Repetition changes the network',ylim=(0,1.04))
    ax[1].legend(frameon=False,fontsize=7,ncol=2)
    cues=['甲是','乙是','甲','乙','松子','铃铛']
    for i,cue in enumerate(cues):
        values=[c['context_outcome']['margin'] for c in final if c['cue']==cue]
        ax[2].scatter([i]*len(values),values,color='#198575',alpha=.55)
    ax[2].axhline(0,color='#849c91',linewidth=.8)
    ax[2].set(xticks=range(6),xticklabels=['A-is','B-is','A','B','pine nut','bell'],ylim=(-.02,.02),
              ylabel='Expected minus alternative activation',title='Contextual endpoint contrast: ties')
    fig.savefig(HERE/'pair-results.png',dpi=160);plt.close(fig)

    (HERE/'measurement-summary.json').write_bytes(encoded(dict(
      classification_counts=dict(Counter(c['classification'] for c in cases)),
      final_positive_converged=len(final),final_context_ties=len(final),
      final_duration_range=[min(c['duration_s'] for c in final),max(c['duration_s'] for c in final)],
      strongest_tie_count_range=[min(c['highest_activation_tie_count'] for c in final),max(c['highest_activation_tie_count'] for c in final)],
      fixed_endpoint_delta_max=max(abs(row['endpoint'][t]-next(x for x in f['rows'] if x['cue'] is None)['endpoint'][t])
             for f in data['secondary_fixed'] for row in f['rows'] if row['intensity']==1 for t in row['endpoint']),
      ranking_viewer_windows=len(rows),ranking_viewer_rows=sum(len(r['table']) for r in rows)),))
    print('Generated full-node ranking viewer, figures, and numerical summary.')


if __name__=='__main__':make()
